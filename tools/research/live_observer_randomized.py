"""Preregistered randomized observer confirmation with separate MCP-server CPU."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for folder in (ROOT, ROOT / 'mcp-server', ROOT / 'tests'):
    sys.path.insert(0, str(folder))

import psutil
from analyze_observer_randomized import make_plan, PROTOCOL, BLOCK_SECONDS, REQUEST_FRAMES
from analyze_pause_cpu import bounded_tail_count
from benchmark import validate_camera_stability, validate_nav_diagnostics
from command_service import validate as validate_service
from function_diagnostics import validate as validate_function
from observer_mcp_transport import run_observer
from live_scene_snapshot import manifest
from probe import Client, config, read_runtime_state
from session_budget import require_session_budget
from resources import ProcessResources
from statistics_aggregate_budget import collect as collect_aggregates
from statistics_detail import validate as validate_detail

WARMUP_SECONDS = 1
CLOSURE_RESERVE_SECONDS = 1800
clock = time.perf_counter

OWN_SOURCES = (
    'tools/research/_research_bootstrap.py', 'mcp-server/research_support.py',
    'tools/research/live_observer_randomized.py', 'tools/research/observer_mcp_server.py',
    'tools/research/observer_mcp_transport.py', 'tools/research/analyze_observer_randomized.py',
    'tools/research/analyze_observer_overhead.py', 'mcp-server/server.py',
    'mcp-server/probe.py', 'mcp-server/resources.py', 'tools/research/thread_resources.py',
    'tools/research/statistics_detail.py', 'tools/research/command_service.py',
    'tools/research/benchmark.py', 'tools/research/function_diagnostics.py',
    'tools/research/live_mcp_battle.py', 'mcp-server/session_budget.py',
    'tools/research/statistics_aggregate_budget.py', 'tools/research/statistics_budget.py',
    'tools/research/analyze_pause_cpu.py', 'tools/research/chars_diagnostics.py',
    'tools/research/live_scene_snapshot.py',
)


def source_hashes(root=ROOT):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in OWN_SOURCES}


def registration_for_run(path, expected_version, seed, *, root=ROOT, wall_clock=time.time):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root / 'runtime'):
        raise RuntimeError('Registration must be inside this project runtime')
    raw = path.read_bytes()
    registered = json.loads(raw)
    plan = make_plan(seed)
    if (expected_version != '0.8.20' or registered['protocol'] != PROTOCOL or
            type(registered['randomization_seed']) is not int or registered['randomization_seed'] != seed or
            registered['plan'] != plan or registered['plugin_version'] != expected_version):
        raise RuntimeError('Preregistered plan/version differs')
    if set(registered['source_sha256']) != set(OWN_SOURCES):
        raise RuntimeError('Preregistered source inventory differs')
    if source_hashes(root) != registered['source_sha256']:
        raise RuntimeError('Source differs from preregistration')
    protocol_doc = registered['protocol_document']
    if (protocol_doc['path'] != 'docs/research/randomized-observer-protocol.md' or
            hashlib.sha256((root / protocol_doc['path']).read_bytes()).hexdigest() != protocol_doc['sha256']):
        raise RuntimeError('Protocol differs from preregistration')
    symbols = registered['symbol_manifest']
    if (symbols['path'] != 'runtime/symbols/0.8.20/manifest.json' or
            hashlib.sha256((root / symbols['path']).read_bytes()).hexdigest() != symbols['sha256']):
        raise RuntimeError('Symbol manifest differs from preregistration')
    started = wall_clock()
    timestamp = registered['registered_at']
    if (type(timestamp) not in (int, float) or not math.isfinite(timestamp) or
            not 0 < timestamp <= started or not math.isfinite(started)):
        raise RuntimeError('Invalid preregistration time')
    return registered, raw, started


async def cleanup_call(client, direct, identity, events, command, **params):
    """Only idempotent cleanup may fall back to TCP after a fresh game identity check."""
    allowed = ((command == 'pause' and params == {'paused': True}) or
               (command == 'set_camera_free' and params == {'enabled': False, 'release_edge': True}))
    if not allowed:
        raise ValueError('Only known idempotent cleanup commands may use fallback')
    identity()
    try:
        return await client.call(command, **params)
    except Exception as exc:
        events.append(dict(command=command, mcp_error=str(exc), fallback='direct-tcp', recovered=False))
        identity()
        result = await direct.call(command, **params)
        events[-1]['recovered'] = True
        return result


async def wait_until(target):
    """Recheck QPC after every wake; Windows timers may resume ahead of target."""
    while True:
        remaining = target - clock()
        if remaining <= 0:
            return
        await asyncio.sleep(max(.001, remaining))


def camera_delta(before, after):
    return dict(camera_position_distance=math.dist(before['camera_position'], after['camera_position']),
                camera_center_distance=math.dist(before['camera_center'], after['camera_center']))


async def stabilize_camera(client, check, records, timeout=10):
    """Require two locked paused scene reads one second apart, within a hard bound."""
    deadline = clock() + timeout
    previous = None
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            raise RuntimeError('Locked camera did not stabilize within ten seconds')
        scene = await asyncio.wait_for(client.call('get_scene_state'), timeout=remaining)
        records.append(dict(scene=scene, observed_monotonic_seconds=clock()))
        check(scene)
        if previous is not None:
            try:
                validate_camera_stability(previous, scene)
            except RuntimeError:
                pass
            else:
                return scene
        previous = scene
        if deadline - clock() < 1:
            raise RuntimeError('Locked camera did not stabilize within ten seconds')
        await wait_until(clock() + 1)


async def collect_slots(client, row):
    """No serialization, validation, file IO or additional getters inside the block."""
    frequency = row['plan']['frequency_hz']
    condition = row['plan']['condition']
    period = 1 / frequency
    slots = int(BLOCK_SECONDS * frequency)
    row.update(scheduled_slots=slots, expected_requests=0 if condition == 'baseline' else slots,
               requests=[], skipped_slots=[], wakeups=[], baseline_wakes=[])
    started = clock()
    row['measured_start_monotonic_seconds'] = started
    last_request_finished = None
    try:
        for slot in range(slots):
            offset = slot * period
            target = started + offset
            if last_request_finished is not None and target < last_request_finished:
                row['skipped_slots'].append(dict(slot=slot, scheduled_offset_seconds=offset,
                    lateness_seconds=clock() - target, reason='previous_request_overrun'))
                continue
            await wait_until(target)
            observed = clock()
            lateness = observed - target
            if lateness >= period:
                row['skipped_slots'].append(dict(slot=slot, scheduled_offset_seconds=offset,
                    lateness_seconds=lateness, reason='wake_late'))
                continue
            wake = dict(slot=slot, scheduled_offset_seconds=offset,
                        started_monotonic_seconds=observed, lateness_seconds=lateness)
            row['wakeups'].append(wake)
            if condition == 'baseline':
                row['baseline_wakes'].append(wake)
                continue
            request = dict(slot=slot, scheduled_offset_seconds=offset,
                           started_monotonic_seconds=observed, lateness_seconds=lateness)
            row['requests'].append(request)
            try:
                request['result'] = await client.call('get_frame_stats', n=REQUEST_FRAMES, detail=condition)
            except Exception as exc:
                request['error'] = dict(type=type(exc).__name__, message=str(exc))
                raise
            finally:
                finished = clock()
                request['finished_monotonic_seconds'] = finished
                request['client_ms'] = (finished - observed) * 1000
                request['overrun_seconds'] = max(0, finished - (started + BLOCK_SECONDS))
                last_request_finished = finished
        await wait_until(started + BLOCK_SECONDS)
    finally:
        row['measured_end_monotonic_seconds'] = clock()


async def main(*, client=None, expected_version='0.8.20', seed, registration):
    c = client
    cfg = config()
    plan = make_plan(seed)
    registration = Path(registration).resolve()
    registered, registration_raw, started_at_wall_seconds = registration_for_run(registration, expected_version, seed)
    server_identity = dict(c.server_identity)
    direct = Client(cfg['port'], cfg['timeout'])
    c.sample_server_cpu()  # Verify owned server identity before any game mutation.
    # Includes four seconds per block for common endpoint collection and validation.
    estimated = len(plan) * (BLOCK_SECONDS + WARMUP_SECONDS + 4)
    require_session_budget(cfg, estimated + CLOSURE_RESERVE_SECONDS)
    state_path = Path(cfg['runtime']) / 'state.json'
    watchdog = await read_runtime_state(state_path)
    if time.time() - watchdog['updated_at'] > 10 or not watchdog['running'] or watchdog['loading']:
        raise RuntimeError('Watchdog is stale or not ready')
    pid = watchdog['pid']
    process = psutil.Process(pid)
    created, executable, command = process.create_time(), process.exe(), process.cmdline()
    def identity():
        p = psutil.Process(pid)
        if (p.create_time() != created or p.exe() != executable or p.cmdline() != command or
            Path(executable).resolve() != Path(cfg['executable']).resolve() or command != [executable, '--norestart']):
            raise RuntimeError('Game process identity changed')
    identity()
    baseline = json.loads((ROOT / 'runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot = json.loads((ROOT / 'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path = Path(snapshot['snapshot_path'])
    save_root = snapshot_path.parent
    def protected():
        return (all(manifest(save_root / name) == info['files'] for name, info in baseline['save_manifests'].items())
                and manifest(snapshot_path) == snapshot['snapshot_manifest'])
    guard_paths = [ROOT / 'runtime/scene-snapshot-state.json', ROOT / 'runtime/snapshot-settle-state.json']
    def guards():
        return {str(p): json.loads(p.read_text(encoding='utf-8'))['restore_required'] for p in guard_paths}
    if not protected() or any(guards().values()):
        raise RuntimeError('Protected files or restore guards differ')
    settings = Path(cfg['working_directory']) / 'settings.cfg'
    settings_before = settings.read_bytes()
    dll = ROOT / 'Re_Kenshi/mods/KenshiProbe/KenshiProbe.dll'
    dll_before = hashlib.sha256(dll.read_bytes()).hexdigest()
    if expected_version != '0.8.20':
        raise ValueError('Unsupported observer plugin version')
    installed = json.loads((ROOT / 'runtime/symbols' / expected_version / 'manifest.json').read_text(encoding='utf-8'))
    if dll_before != installed['files']['KenshiProbe.dll']['sha256'] or dll_before != registered['dll_sha256']:
        raise RuntimeError('Installed plugin differs from frozen ' + expected_version)
    initial = await c.call('get_scene_state')
    if (not initial['paused'] or initial['frame_speed_multiplier'] != 0 or initial['free_camera'] or
        initial['battle']['active'] or initial['scene_camera_control_owned']):
        raise RuntimeError('Requires restored paused disposable copy')
    ping = await c.call('ping')
    if (ping['plugin_version'] != expected_version or not ping['frame_stats_aggregates_available'] or
        not ping['command_service_timing_enabled'] or not ping['function_thread_cpu_enabled'] or
        ping['profiled_function'] != 'Ogre::Root::renderOneFrame' or
        (ping['system_hook_count'], ping['dedicated_system_hook_count'], ping['service_hook_count'], ping['installed_hook_count']) != (3, 3, 2, 5)):
        raise RuntimeError('Observer contract differs')
    tools = await c.session.list_tools()
    if len(tools.tools) != 17:
        raise RuntimeError('Unexpected MCP registry')
    output = ROOT / 'runtime/scenarios' / ('observer-randomized-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    controller = psutil.Process()
    if source_hashes() != registered['source_sha256']:
        raise RuntimeError('Preregistered source inventory differs')
    clock_info = time.get_clock_info('perf_counter')
    data = dict(protocol=PROTOCOL, pid=pid, created_at=created, executable=executable, cmdline=command,
        measurement_clock=dict(name='perf_counter', implementation=clock_info.implementation,
            monotonic=clock_info.monotonic, adjustable=clock_info.adjustable, resolution=clock_info.resolution),
        transport=c.transport, initial_ping=ping, initial_scene=initial, plan=plan, blocks=[], completed=False,
        randomization_seed=seed, started_at_wall_seconds=started_at_wall_seconds,
        pre_registration=dict(path=str(registration), sha256=hashlib.sha256(registration_raw).hexdigest(), document=registered),
        mcp_server_identity=server_identity,
        mcp_server_launch_provenance=c.server_launch_provenance,
        requested_block_seconds=BLOCK_SECONDS, requested_frames=REQUEST_FRAMES,
        warmup_seconds=WARMUP_SECONDS, warmup_condition='Neutral wait without commands before common scene/heartbeat endpoints',
        schedule='Absolute perf_counter deadlines rechecked after each wake; expired in-flight slots and timer delays of one period are skipped; no burst catch-up',
        estimated_duration_seconds=estimated, closure_reserve_seconds=CLOSURE_RESERVE_SECONDS,
        session_until=cfg.get('session_until'), expected_plugin_version=expected_version,
        controller_identity=dict(c.server_launch_provenance['controller_identity']),
        controller_cpu_scope='Controller only; excludes the separate MCP server. Counter snapshots slightly enclose the measured span.',
        mcp_server_cpu=dict(available=True,
            scope='Owned MCP server process only; excludes its Python launcher. Verified identity, cumulative CPU snapshots at separately timestamped QPC endpoints; not added to controller CPU.'),
        endpoint_scope='Common endpoint getters and serialization occur after the game CPU endpoint; callback statistics have separate scene/frame bounds. Carry-over into later blocks remains possible.',
        byte_scope='Compact JSON re-encoding of returned results, not TCP or MCP wire bytes',
        settings_sha256_before=hashlib.sha256(settings_before).hexdigest(), installed_dll_sha256_before=dll_before,
        protected_files_before=True, guards_before=guards(), own_source_sha256=source_hashes())
    published = False
    def publish():
        nonlocal published
        with output.open('w' if published else 'x', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
        published = True
    def paused(scene, owned, reference=None):
        if (not scene['paused'] or scene['frame_speed_multiplier'] != 0 or scene['free_camera'] or
            scene['battle']['active'] or scene['game_total_hours'] != initial['game_total_hours'] or
            scene['scene_camera_control_owned'] is not owned or owned and scene['edge_scrolling']):
            raise RuntimeError('Pause, clock or camera ownership changed')
        if reference is not None:
            validate_camera_stability(reference, scene)
            if any(scene[key] != reference[key] for key in ('loaded_character_count', 'active_town_count')):
                raise RuntimeError('Loaded population changed during measured locked-camera period')
    lock_requested = False
    try:
        identity()
        lock_requested = True
        data['camera_lock'] = await c.call('set_camera_free', enabled=False, lock_edge=True)
        if not data['camera_lock']['scene_camera_control_owned'] or data['camera_lock']['edge_scrolling']:
            raise RuntimeError('Temporary camera lock unavailable')
        data['camera_stabilization'] = []
        data['camera_stabilization_timeout_seconds'] = 10
        data['camera_reference'] = await stabilize_camera(c, lambda scene: paused(scene, True), data['camera_stabilization'])
        data['pre_lock_camera_delta'] = dict(camera_delta(initial, data['camera_reference']),
            scope='Observed displacement before a stable locked reference; no initial-position restoration claimed')
        publish()
        for item in plan:
            require_session_budget(cfg, BLOCK_SECONDS + WARMUP_SECONDS + CLOSURE_RESERVE_SECONDS)
            identity()
            watchdog = await read_runtime_state(state_path)
            if watchdog['pid'] != pid or time.time() - watchdog['updated_at'] > 10 or not watchdog['running']:
                raise RuntimeError('Watchdog PID changed or status stale')
            row = dict(plan=dict(item), completed=False, warmup_seconds=WARMUP_SECONDS)
            data['blocks'].append(row)
            row['warmup_start_monotonic_seconds'] = clock()
            await wait_until(row['warmup_start_monotonic_seconds'] + WARMUP_SECONDS)
            row['warmup_end_monotonic_seconds'] = clock()
            row['scene_before'] = await c.call('get_scene_state')
            paused(row['scene_before'], True, data['camera_reference'])
            row['roles_before'] = await c.call('heartbeat')
            row['mcp_server_cpu_before'] = c.sample_server_cpu()
            cpu = controller.cpu_times()
            row['controller_cpu_before'] = dict(user=cpu.user, system=cpu.system, monotonic_seconds=clock())
            resources = ProcessResources(pid, cfg['executable'], sample_threads=True, clock=clock)
            try:
                await collect_slots(c, row)
            finally:
                row['process_resources'] = resources.finish()
                row['mcp_server_cpu_after'] = c.sample_server_cpu()
                cpu = controller.cpu_times()
                row['controller_cpu_after'] = dict(user=cpu.user, system=cpu.system, monotonic_seconds=clock())
            if row['skipped_slots'] or len(row['requests']) != row['expected_requests']:
                raise RuntimeError('Randomized confirmation requires every planned request slot')
            row['selection_scene'] = await c.call('get_scene_state')
            paused(row['selection_scene'], True, data['camera_reference'])
            if row['selection_scene']['frame'] - row['scene_before']['frame'] - 1 > 3600:
                raise RuntimeError('Endpoint exceeds full-window retention budget')
            row['requested_frames'] = bounded_tail_count(row['scene_before']['frame'], row['selection_scene']['frame'], 3600)
            row['statistics_collection'] = {}
            row['statistics_tail'], _ = await collect_aggregates(c, row['requested_frames'], row['statistics_collection'])
            row['scene_after'] = await c.call('get_scene_state')
            paused(row['scene_after'], True, data['camera_reference'])
            row['roles_after'] = await c.call('heartbeat')
            stats = row['statistics_tail']
            if not row['scene_before']['frame'] < stats['first_frame'] <= stats['last_frame'] <= row['scene_after']['frame']:
                raise RuntimeError('Endpoint statistics outside scene bounds')
            validate_nav_diagnostics(stats)
            validate_function(stats)
            validate_service(stats, 'get_frame_stats')
            for request in row['requests']:
                result = request['result']
                if validate_detail(result) != item['condition'] or result['count'] != REQUEST_FRAMES:
                    raise RuntimeError('Observer response detail or frame count differs')
                validate_nav_diagnostics(result)
                validate_function(result)
                validate_service(result, 'get_frame_stats')
                request['compact_result_bytes'] = len(json.dumps(result, separators=(',', ':'), allow_nan=False).encode('utf-8'))
            row['completed'] = True
            publish()
            print(json.dumps(dict(block=len(data['blocks']), plan=item, requests=len(row['requests']),
                skipped=len(row['skipped_slots']), game_logical_cpus=row['process_resources']['logical_cpu_equivalents'])), flush=True)
        data['measurement_valid'] = True
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        data['cleanup_events'] = []
        if lock_requested:
            try:
                identity()
                await cleanup_call(c, direct, identity, data['cleanup_events'], 'pause', paused=True)
                identity()
                data['pre_release_scene'] = await direct.call('get_scene_state')
                paused(data['pre_release_scene'], True, data.get('camera_reference'))
            except Exception as exc:
                data['pre_release_error'] = str(exc)
            try:
                identity()
                data['camera_release'] = await cleanup_call(c, direct, identity, data['cleanup_events'],
                    'set_camera_free', enabled=False, release_edge=True)
            except Exception as exc:
                data['restoration_error'] = str(exc)
        try:
            identity()
            data['final_scene_transport'] = 'direct-tcp'
            data['final_scene'] = await direct.call('get_scene_state')
            paused(data['final_scene'], False)
            if 'pre_release_scene' in data:
                data['release_camera_delta'] = dict(camera_delta(data['pre_release_scene'], data['final_scene']),
                    scope='Observed movement after returning Edge control; outside measured locked-camera blocks, not a failed restoration of the initial position')
            if data['final_scene']['edge_scrolling'] != initial['edge_scrolling']:
                raise RuntimeError('Original Edge scrolling state not restored')
        except Exception as exc:
            data['final_scene_error'] = str(exc)
        try:
            data['protected_files_unchanged'] = protected()
            data['settings_unchanged'] = settings.read_bytes() == settings_before
            data['installed_dll_sha256_after'] = hashlib.sha256(dll.read_bytes()).hexdigest()
            data['guards_after'] = guards()
            data['own_sources_unchanged'] = source_hashes() == data['own_source_sha256']
            if (not data['protected_files_unchanged'] or not data['settings_unchanged'] or
                data['installed_dll_sha256_after'] != dll_before or any(data['guards_after'].values()) or
                not data['own_sources_unchanged']):
                raise RuntimeError('Final files or guards differ')
        except Exception as exc:
            data['final_audit_error'] = str(exc)
        if data['cleanup_events']:
            data['cleanup_transport_error'] = 'MCP failed during cleanup; direct TCP restitution attempted'
        data['completed'] = bool(data.get('measurement_valid') and len(data['blocks']) == len(plan) and
            all(r.get('completed') for r in data['blocks']) and
            not any(data.get(k) for k in ('error', 'pre_release_error', 'restoration_error', 'final_scene_error', 'final_audit_error', 'cleanup_transport_error')))
        publish()
        print(json.dumps(dict(output=str(output), completed=data['completed'], blocks=len(data['blocks']),
            error=data.get('error'), restoration_error=data.get('restoration_error'), final_audit_error=data.get('final_audit_error'))), flush=True)


if __name__ == '__main__':
    os.chdir(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-version', default='0.8.20', choices=('0.8.20',))
    parser.add_argument('--registration', type=Path, required=True)
    args = parser.parse_args()
    registration = args.registration.resolve()
    seed = json.loads(registration.read_text(encoding='utf-8'))['randomization_seed']
    registration_for_run(registration, args.expected_version, seed)
    asyncio.run(run_observer(main, registration.parent, expected_version=args.expected_version,
                            seed=seed, registration=registration))
