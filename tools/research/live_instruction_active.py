"""Bounded non-admin user-RIP observations at Heng x1; restores the test copy.

PSS captures thread contexts without a VA clone or stack unwinding. Sparse
observations do not constitute time-weighted CPU percentages or a speedup.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
for folder in (ROOT, ROOT/'mcp-server', ROOT/'tests'): sys.path.insert(0, str(folder))
import psutil
from analyze_pause_cpu import validate_phase_state
from benchmark import simulation_progress
from environment_diagnostics import collect as environment
from instruction_diagnostics import validate, summarize
from instruction_snapshot import WindowsInstructionSnapshot
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready, wait_loaded
from probe import config, read_runtime_state
from resources import ProcessResources


async def main(source, count=12, client=None):
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 120:
        raise ValueError('Requires 1..120 bounded captures')
    c = client; cfg = config()
    if time.time()+1800 >= cfg['session_until']: raise RuntimeError('Closure window reserved')
    source = Path(source).resolve(); raw = source.read_bytes(); baseline = json.loads(raw)
    if baseline.get('completed') is not True: raise RuntimeError('Requires completed CPU baseline')
    phase = next(x for x in baseline['phases'] if x['label'] == 'running_x1' and x['completed'])
    pid = baseline['pid']; created = phase['process_resources']['before']['created_at']
    state_path = Path(cfg['runtime'])/'state.json'
    provider = WindowsInstructionSnapshot()

    def identity():
        p = psutil.Process(pid)
        if p.create_time() != created or Path(p.exe()).resolve() != Path(cfg['executable']).resolve() or p.cmdline() != [p.exe(), '--norestart']:
            raise RuntimeError('Game identity changed')
        return dict(pid=pid, created_at=created, executable=p.exe(), cmdline=p.cmdline())

    identity()
    if (await read_runtime_state(state_path))['pid'] != pid: raise RuntimeError('Baseline belongs to older game')
    # Native exact creation identity, independent of a float roundtrip.
    handle = provider.k.OpenProcess(0x400, False, pid)
    if not handle: raise C.WinError(C.get_last_error())
    try:
        times = [W.FILETIME() for _ in range(4)]
        if provider.k.GetProcessId(handle) != pid or not provider.k.GetProcessTimes(handle, *[C.byref(t) for t in times]):
            raise RuntimeError('Native process binding failed')
        exact_created = str(provider.ticks(times[0])); identity()
    finally:
        if not provider.k.CloseHandle(handle): raise RuntimeError('Native binding handle did not close')
    selected = sorted(phase['process_resources']['thread_cpu']['threads'], key=lambda x: x['cpu_seconds'], reverse=True)[:4]
    lifetimes = [(r['tid'], r['created_filetime']) for r in selected]
    proof = json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot = json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path = Path(snapshot['snapshot_path']); save_root = snapshot_path.parent

    def protected():
        return all(manifest(save_root/k) == v['files'] for k,v in proof['save_manifests'].items()) and manifest(snapshot_path) == snapshot['snapshot_manifest']

    if not protected(): raise RuntimeError('Protected saves differ before capture')
    initial = await c.call('get_scene_state')
    if not initial['paused'] or initial['battle']['active'] or initial['free_camera'] or initial['scene_camera_control_owned']:
        raise RuntimeError('Requires restored paused copy')
    settings = Path(cfg['working_directory'])/'settings.cfg'; settings_before = settings.read_bytes()
    folder = ROOT/'runtime/instruction-active'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True); output = folder/'controller.json'
    seed = time.time_ns(); rng = random.Random(seed)
    data = dict(identity(), process_created_filetime=exact_created, source=str(source), source_sha256=hashlib.sha256(raw).hexdigest(),
        selected_lifetimes=selected, requested_count=count, jitter_seed=seed, jitter_seconds=[.8,1.2],
        capture_budget_seconds_per_call=.25, capture_schedule='scene_then_jitter_then_pss',
        completed=False, samples=[], observations=[],
        admin=bool(C.windll.shell32.IsUserAnAdmin()), transport=c.transport,
        scope='Sparse current user RIP observations; no stacks, CPU sampling percentages or exclusive function CPU.')
    reference = None; mutations = False
    def publish(): output.write_text(json.dumps(data, indent=2), encoding='utf-8')
    try:
        data['initial_ping'] = await c.call('ping')
        if data['initial_ping']['system_hook_count'] != 3: raise RuntimeError('Unexpected system hooks')
        mutations = True; publish()
        reference = await restore_test(c, False, lock_edge=True); data['source_reference'] = reference
        data['town'] = await c.call('prepare_town_scene', name='Heng')
        await pause_ready(c, False); await asyncio.sleep(10); await wait_loaded(c, 0, stable_seconds=3)
        await pause_ready(c, True)
        data['environment_before'] = await environment(c, 500)
        data['roles_before'] = await c.call('get_scene_state', thread_details=True)
        await c.call('set_game_speed', speed=1); await asyncio.sleep(3)
        camera = data['scene_before'] = await c.call('get_scene_state')
        validate_phase_state(camera, camera, False)
        if not camera['scene_camera_control_owned']: raise RuntimeError('Camera guard not owned')
        resources = ProcessResources(pid, cfg['executable'], sample_threads=True)
        for index in range(count):
            if time.time()+300 >= cfg['session_until']: raise RuntimeError('Restoration time reserved')
            # Do not anchor each capture to a just-serviced game-thread RPC.
            observation = await c.call('get_scene_state'); validate_phase_state(camera, observation, False)
            observed_at = time.time(); jitter = rng.uniform(.8, 1.2)
            await asyncio.sleep(jitter); identity()
            if (await read_runtime_state(state_path))['pid'] != pid: raise RuntimeError('Watchdog PID changed')
            started = time.perf_counter()
            captured = provider.capture(pid, cfg['executable'], lifetimes)
            caller_seconds = time.perf_counter()-started
            data['samples'].append(captured)
            data['observations'].append(dict(index=index, scene=observation, scene_observed_at=observed_at,
                jitter_seconds=jitter, capture_delay_after_scene_seconds=captured['started_at']-observed_at,
                caller_seconds=caller_seconds))
            validate(captured, pid, cfg['executable'], exact_created, lifetimes)
            if caller_seconds > .25: raise RuntimeError('Single-capture helper budget exceeded; no repeated attempt')
            publish()
        data['scene_after'] = await c.call('get_scene_state'); validate_phase_state(camera, data['scene_after'], False)
        data['process_resources'] = resources.finish()
        data['simulation_progress'] = simulation_progress(camera, data['scene_after'])
        if data['simulation_progress']['game_hours'] <= 0: raise RuntimeError('Active simulation did not advance')
        await c.call('pause', paused=True)
        data['roles_after'] = await c.call('get_scene_state', thread_details=True)
        data['environment_after'] = await environment(c, 500)
        data['summary'] = summarize(data['samples'], pid, cfg['executable'], exact_created, lifetimes)
        identity(); data['capture_valid'] = True
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        if mutations:
            try:
                identity(); data['restored'] = await restore_test(c, False, reference, lock_edge=True)
                if reference is not None and data['restored']['game_total_hours'] != reference['game_total_hours']:
                    raise RuntimeError('Restored simulation hour differs')
            except Exception as exc: data['restoration_error'] = str(exc)
            try:
                identity(); await c.call('pause', paused=True)
                data['camera_release'] = await c.call('set_camera_free', enabled=False, release_edge=True)
            except Exception as exc: data['camera_release_error'] = str(exc)
        data['protected_files_unchanged'] = protected(); data['settings_unchanged'] = settings.read_bytes() == settings_before
        data['final_scene'] = await c.call('get_scene_state')
        data['watchdog'] = await read_runtime_state(state_path)
        data['completed'] = bool(data.get('capture_valid') and not any(data.get(k) for k in ('error','restoration_error','camera_release_error')) and
            data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and
            not data['final_scene']['scene_camera_control_owned'] and data['watchdog']['pid'] == pid)
        publish()
        print(json.dumps(dict(output=str(output), completed=data['completed'], samples=len(data['samples']),
            error=data.get('error'), restoration_error=data.get('restoration_error'), admin=data['admin'],
            helper_seconds_max=data.get('summary',{}).get('helper_seconds_max'), protected=data['protected_files_unchanged'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('source', type=Path); parser.add_argument('--count', type=int, default=12)
    args = parser.parse_args(); os.chdir(ROOT); asyncio.run(run(main, args.source, args.count))
