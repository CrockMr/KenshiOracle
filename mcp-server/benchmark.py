"""Collect non-overlapping frame windows; retain raw responses and scenario metadata."""
import argparse
import asyncio
import hashlib
import json
import math
import platform
import time
from pathlib import Path
from probe import Client, config
from physics_diagnostics import validate as validate_physics_diagnostics
from statistics_detail import validate as validate_statistics_detail, navmesh_slow_rows


def validate_camera_stability(reference, observed, tolerance=5):
    if reference['free_camera'] != observed['free_camera']:
        raise RuntimeError('Camera mode changed during measurement')
    for key in ('camera_center', 'camera_position'):
        if math.dist(reference[key], observed[key]) > tolerance:
            raise RuntimeError('Camera moved during measurement')


def simulation_progress(before, after):
    if any(key not in scene for scene in (before, after) for key in ('game_total_hours', 'observed_qpc_ms')):
        return None
    values = [scene[key] for scene in (before, after) for key in ('game_total_hours', 'observed_qpc_ms')]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise RuntimeError('Invalid simulation clock interval')
    wall = (after['observed_qpc_ms']-before['observed_qpc_ms'])/1000
    hours = after['game_total_hours']-before['game_total_hours']
    if not math.isfinite(wall) or not math.isfinite(hours) or wall <= 0 or hours < 0:
        raise RuntimeError('Invalid simulation clock interval')
    return dict(wall_seconds=wall, game_hours=hours, game_hours_per_wall_second=hours/wall,
                first_frame=before['frame'], last_frame=after['frame'],
                scope='Between scene snapshots, including request gaps; not exactly the frame-statistics window')


def validate_nav_diagnostics(stats):
    detail=validate_statistics_detail(stats)
    systems = stats.get('systems', {})
    split = systems.get('navmesh_findPath_threads')
    if split is None:
        return  # Older plugins and an unavailable navigation hook remain readable.
    if set(split) != {'game_thread', 'other_threads', 'unclassified'}:
        raise RuntimeError('Unexpected navigation thread categories')
    if sum(row['calls_total'] for row in split.values()) != systems['navmesh_findPath_calls_total']:
        raise RuntimeError('Navigation thread counts do not match total')
    if not math.isclose(sum(row['mean_ms'] for row in split.values()), systems['navmesh_findPath_mean_ms'], abs_tol=1e-7, rel_tol=1e-7):
        raise RuntimeError('Navigation thread durations do not match total')
    if not math.isclose(max(row['max_call_ms'] for row in split.values()), systems['navmesh_findPath_max_call_ms'], abs_tol=1e-7, rel_tol=1e-7):
        raise RuntimeError('Navigation thread maxima do not match total')
    returned = systems.get('navmesh_findPath_results')
    if returned is not None:
        if set(returned) != {'true', 'false'} or sum(row['calls_total'] for row in returned.values()) != systems['navmesh_findPath_calls_total']:
            raise RuntimeError('Navigation result counts do not match total')
        if not math.isclose(sum(row['mean_ms'] for row in returned.values()), systems['navmesh_findPath_mean_ms'], abs_tol=1e-7, rel_tol=1e-7):
            raise RuntimeError('Navigation result durations do not match total')
        if not math.isclose(max(row['max_call_ms'] for row in returned.values()), systems['navmesh_findPath_max_call_ms'], abs_tol=1e-7, rel_tol=1e-7):
            raise RuntimeError('Navigation result maxima do not match total')
        if any(not 0 <= row['hierarchical_calls_total'] <= row['calls_total'] for row in returned.values()):
            raise RuntimeError('Invalid hierarchical navigation result counts')
    calls = navmesh_slow_rows(stats)
    retained_rows=stats['statistics_detail']['navmesh_slow_rows_omitted'] if detail=='aggregates' else len(calls)
    if retained_rows > stats['navmesh_slow_calls_capacity'] or retained_rows > stats['navmesh_slow_calls_total']:
        raise RuntimeError('Invalid navigation slow-call retention')
    if stats['navmesh_slow_calls_retention_truncated'] != (retained_rows < stats['navmesh_slow_calls_total']):
        raise RuntimeError('Invalid navigation truncation flag')
    for call in calls:
        if not stats['first_frame'] <= call['completion_frame'] <= stats['last_frame'] or call['start_frame'] > call['completion_frame']:
            raise RuntimeError('Navigation slow call outside frame window')
        if call['elapsed_ms'] < stats['navmesh_slow_calls_threshold_ms']:
            raise RuntimeError('Navigation slow call below threshold')
        kind = call['thread_kind']
        expected = 'unclassified' if not call['game_thread_id_at_start'] else ('game_thread' if call['thread_id'] == call['game_thread_id_at_start'] else 'other_threads')
        if kind != expected:
            raise RuntimeError('Navigation thread identity mismatch')
        if 'thread_cpu_user_ms' in call:
            cpu = (call['thread_cpu_user_ms'], call['thread_cpu_kernel_ms'])
            if cpu != (None, None) and any(value is None or not math.isfinite(value) or value < 0 for value in cpu):
                raise RuntimeError('Invalid navigation thread CPU counters')
        for key in ('start_vector', 'goal_vector'):
            if key in call and (len(call[key]) != 4 or any(value is not None and not math.isfinite(value) for value in call[key])):
                raise RuntimeError('Invalid navigation argument vector')
        if any(key in call and (not isinstance(call[key], int) or call[key] < 0) for key in ('output_size_before', 'output_size_after')):
            raise RuntimeError('Invalid navigation output size')


async def collect(client, samples, frames, label, context, wait_timeout=120):
    if samples < 1 or not 1 <= frames <= 3600:
        raise ValueError('samples >= 1 and frames in 1..3600 required')
    result = dict(label=label, context=context, started_at=time.time(), platform=platform.platform(), windows=[])
    initial = await client.call('ping')
    if not initial.get('world_ready'):
        raise RuntimeError('Load a test save before measuring')
    result['initial'] = initial
    cursor = initial['frame']
    previous_last_frame = None
    previous_scene = context.get('camera')
    for _ in range(samples):
        deadline = time.monotonic() + wait_timeout
        while True:
            state = await client.call('ping')
            if state['frame'] < cursor:
                raise RuntimeError('Frame counter reset during measurement')
            if (state.get('paused'), state.get('frame_speed_multiplier')) != (initial.get('paused'), initial.get('frame_speed_multiplier')):
                raise RuntimeError('Pause or speed changed during measurement')
            if state['frame'] - cursor >= frames + 2:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Not enough progressing frames for a complete window')
            await asyncio.sleep(.1)
        stats = await client.call('get_frame_stats', n=frames, detail='full')
        after = await client.call('ping')
        if stats['count'] != frames:
            raise RuntimeError('Incomplete frame window')
        validate_nav_diagnostics(stats)
        validate_physics_diagnostics(stats)
        if 'first_frame' in stats and 'last_frame' in stats:
            if stats['last_frame']-stats['first_frame']+1 != frames:
                raise RuntimeError('Frame identifiers do not match sample count')
            if previous_last_frame is not None and stats['first_frame'] <= previous_last_frame:
                raise RuntimeError('Overlapping frame windows')
            previous_last_frame = stats['last_frame']
        if after['frame'] < state['frame']:
            raise RuntimeError('Game restarted during measurement')
        if (after.get('paused'), after.get('frame_speed_multiplier')) != (initial.get('paused'), initial.get('frame_speed_multiplier')):
            raise RuntimeError('Pause or speed changed while reading statistics')
        window = dict(observed_before=state, statistics=stats, observed_after=after)
        if context.get('enforce_scene_stability'):
            scene = await client.call('get_scene_state')
            validate_camera_stability(context['camera'], scene)
            window['observed_scene'] = scene
            window['simulation_progress'] = simulation_progress(previous_scene, scene)
            previous_scene = scene
        result['windows'].append(window)
        cursor = after['frame']
    result['finished_at'] = time.time()
    result['final'] = await client.call('ping')
    return result


async def main(args):
    cfg = config(args.config)
    root = Path(cfg.get('working_directory', Path(cfg['executable']).parent))
    mods = root/'data/mods.cfg'
    context = dict(save=args.save, scene=args.scene, camera=args.camera,
                   resolution=args.resolution, warmup_seconds=args.warmup,
                   concurrent_load=args.concurrent_load,
                   mods_sha256=hashlib.sha256(mods.read_bytes()).hexdigest() if mods.exists() else None)
    await asyncio.sleep(args.warmup)
    data = await collect(Client(cfg.get('port', 47800), cfg.get('timeout', 10)),
                         args.samples, args.frames, args.label, context)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for i, window in enumerate(data['windows'], 1):
        stats = dict(window['statistics'])
        stats.pop('per_frame', None)
        print(json.dumps(dict(window=i, stats=stats)), flush=True)
    print(str(output.resolve()), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', default='config.json')
    p.add_argument('--samples', type=int, default=3)
    p.add_argument('--frames', type=int, default=300)
    p.add_argument('--warmup', type=float, default=10)
    p.add_argument('--label', required=True)
    p.add_argument('--save', required=True)
    p.add_argument('--scene', required=True)
    p.add_argument('--camera', default='unchanged after load')
    p.add_argument('--resolution', default='1280x720')
    p.add_argument('--concurrent-load', default='not recorded')
    p.add_argument('--output', required=True)
    asyncio.run(main(p.parse_args()))
