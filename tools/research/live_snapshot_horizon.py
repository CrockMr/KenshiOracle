"""Observe x1/x5 from one owned snapshot to a common clock horizon via MCP.

No spawning, save writes, process stops, or settings writes. A rejected baseline
aborts the campaign and is retained. Finally reloads the pristine test copy.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import time

from benchmark import simulation_progress, validate_camera_stability, validate_nav_diagnostics
from environment_diagnostics import collect as collect_environment, admission as environment_admission
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest, visible_comparison
from live_suite import wait_loaded
from probe import config, read_runtime_state
from resources import ProcessResources
from thread_resources import assign_roles


def validate_baseline(reference, scene):
    """Validate observed pose/medical state only, never claim full determinism."""
    for sample in (reference, scene):
        rows = sample['battle']['members']
        names = [row['name'] for row in rows]
        if not rows or len(set(names)) != len(names):
            raise ValueError('Missing or duplicate cohort names')
        if not sample['paused'] or not sample['battle']['active']:
            raise ValueError('Snapshot is not a paused tracked cohort')
        if sample['battle']['matched_loaded'] != len(rows):
            raise ValueError('Incomplete tracked cohort')
        for row in rows:
            parts = row['health']['parts_flesh_stun_max']
            if (len(row['position']) != 3 or not parts or
                any(len(part) != 3 for part in parts) or
                row['health']['part_count'] != len(parts) or
                row['health']['sampled_count'] != len(parts)):
                raise ValueError('Incomplete pose or body shape')
            numbers = row['position']+[row['blood']]+sum(parts, [])
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in numbers):
                raise ValueError('Nonfinite visible baseline')
        if not math.isfinite(sample['game_total_hours']):
            raise ValueError('Invalid baseline clock')
        for key in ('camera_center','camera_position'):
            if len(sample[key]) != 3 or any(not math.isfinite(x) for x in sample[key]):
                raise ValueError('Invalid camera pose')
    validate_camera_stability(reference, scene)
    comparison = visible_comparison(reference, scene)
    comparison['clock_difference_hours'] = abs(reference['game_total_hours']-scene['game_total_hours'])
    comparison['matches'] = comparison['matches'] and comparison['clock_difference_hours'] <= 1e-7
    return comparison


async def main(proof_path, baseline_path, hours=.5, order=(1,5,5,1), client=None,environment_limit=500):
    if isinstance(environment_limit,bool) or not isinstance(environment_limit,int) or not 1<=environment_limit<=500:
        raise ValueError('environment_limit must be an integer in 1..500')
    c = client
    cfg = config()
    if time.time()+1800 >= cfg['session_until']:
        raise RuntimeError('Too close to authorized session deadline')
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    baseline_proof = json.loads(baseline_path.read_text(encoding='utf-8'))
    name = proof['name']
    if not name.startswith('KenshiProbe_test_scene_') or baseline_proof['name'] != name:
        raise ValueError('Expected matching disposable snapshot proofs')
    expected = baseline_proof['runs'][0]['observations'][0]['scene']
    validate_baseline(expected, expected)
    snapshot = Path(proof['snapshot_path'])
    if manifest(snapshot) != proof['snapshot_manifest']:
        raise ValueError('Snapshot manifest changed before trial')
    save_root = Path.home()/'AppData/Local/kenshi/save'
    source_proof = Path('runtime/scenarios/battle-campaign-073-final.json')
    source_reference = json.loads(source_proof.read_text(encoding='utf-8'))
    source_files = source_reference['save_manifests']
    for slot, original in source_files.items():
        if manifest(save_root/slot) != original['files']:
            raise ValueError('Source/pristine copy manifest changed before trial')
    settings = Path(cfg['working_directory'])/'settings.cfg'
    original_settings = settings.read_bytes()
    state_path = Path(cfg['runtime'])/'state.json'
    pid = (await read_runtime_state(state_path))['pid']
    reference = await c.call('get_scene_state')
    if (not reference['paused'] or reference['battle']['active'] or reference['free_camera'] or
        reference['scene_camera_control_owned']):
        raise RuntimeError('Requires the paused restored test copy')
    validate_camera_stability(source_reference['scene'], reference)
    output = Path('runtime/scenarios')/time.strftime('snapshot-horizon-%Y%m%dT%H%M%SZ.json',time.gmtime())
    data = dict(pid=pid, snapshot=name, transport=c.transport, target_game_hours=hours, order=list(order),
        baseline_proof=str(baseline_path), baseline_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        snapshot_proof=str(proof_path), snapshot_proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        runs=[], sampling_interval_seconds=.2, limits=[
            'Visible baseline guard does not cover all equipment, AI, reinforcement or streaming state.',
            'Clock horizon is sampled, not exact; overshoot retained, no hit or task completion count inferred.',
            'CPU interval includes commands, OS endpoint samples and paused boundaries.'])
    environment_reference = None
    data['environment_gate'] = 'Complete paused update list, labels and exact positions, relative to first admitted run; not full world state'
    data['environment_limit'] = environment_limit
    try:
        for speed in order:
            if time.time()+300 >= cfg['session_until']:
                raise RuntimeError('Leaving time for restoration before deadline')
            row = dict(speed=speed, observations=[])
            data['runs'].append(row)
            await c.call('set_camera_free', enabled=True)
            before = await c.call('ping')
            row['load'] = await c.call('load_save', name=name)
            if not row['load']['battle_tracking_restored'] or not row['load']['pause_on_ready']:
                raise RuntimeError('Snapshot ownership unavailable; no replacement spawning')
            row['first_ready'] = await wait_loaded(c, before['frame'])
            if not row['first_ready']['paused']:
                raise RuntimeError('Snapshot resumed before ready')
            await c.call('set_camera_free', enabled=True, lock_edge=True)
            row['initial'] = await c.call('get_scene_state')
            row['baseline_comparison'] = validate_baseline(expected, row['initial'])
            if not row['baseline_comparison']['matches']:
                row['excluded'] = 'Visible baseline differs; no simulation measurement started'
                raise RuntimeError(row['excluded'])
            # Equal cohort health/pose alone did not reproduce the surrounding
            # update list. Require a full visible inventory before any speed call.
            row['environment'] = await collect_environment(c,environment_limit)
            current_environment = row['environment']['summary']
            row['environment_admission'] = environment_admission(environment_reference,current_environment)
            if not row['environment_admission']['accepted']:
                row['excluded'] = 'Visible environment differs or inventory incomplete; no simulation measurement started'
                raise RuntimeError(row['excluded'])
            if environment_reference is None:
                environment_reference = current_environment
            # Native setGameSpeed(speed,false) was observed to unpause. Keep the
            # clock baseline before that command and include it in the CPU span.
            row['clock_start'] = await c.call('get_scene_state')
            if not row['clock_start']['paused']:
                raise RuntimeError('Snapshot resumed before measurement boundary')
            roles_before = await c.call('heartbeat')
            resources = ProcessResources(pid, cfg['executable'], sample_threads=True)
            start = time.monotonic()
            row['speed_activation'] = await c.call('set_game_speed', speed=speed)
            if row['speed_activation']['paused']:
                await c.call('pause', paused=False)
            while time.monotonic()-start < 120:
                if time.time()+180 >= cfg['session_until']:
                    raise RuntimeError('Restoration deadline reached')
                await asyncio.sleep(.2)
                scene = await c.call('get_scene_state')
                row['observations'].append(dict(elapsed=time.monotonic()-start, scene=scene))
                if (await read_runtime_state(state_path))['pid'] != pid:
                    raise RuntimeError('Game process changed')
                if scene['paused'] or scene['frame_speed_multiplier'] != speed:
                    raise RuntimeError('Simulation speed changed')
                validate_camera_stability(row['initial'], scene)
                if scene['battle']['matched_loaded'] != len(expected['battle']['members']):
                    raise RuntimeError('Cohort member missing')
                progress = simulation_progress(row['clock_start'], scene)
                if progress['game_hours'] >= hours:
                    break
            else:
                raise TimeoutError('Clock horizon not reached')
            await c.call('pause', paused=True)
            row['final'] = await c.call('get_scene_state')
            roles_after = await c.call('heartbeat')
            row['process_resources'] = resources.finish()
            row['progress'] = simulation_progress(row['clock_start'], row['final'])
            row['horizon_overshoot_hours'] = row['progress']['game_hours']-hours
            validate_camera_stability(row['initial'], row['final'])
            row['statistics_tail'] = await c.call('get_frame_stats', n=600, detail='full')
            context = await c.call('get_frame_stats', n=3600, detail='full')
            validate_nav_diagnostics(row['statistics_tail'])
            validate_nav_diagnostics(context)
            row['thread_attribution_statistics'] = context
            game = {roles_before['game_thread']} if roles_before['game_thread']==roles_after['game_thread'] else set()
            renderer = {roles_before['service_thread']} if roles_before['service_thread']==roles_after['service_thread'] else set()
            nav = {x['thread_id'] for x in context['navmesh_slow_calls']
                   if roles_before['frame'] <= x['completion_frame'] <= roles_after['frame']}
            assign_roles(row['process_resources']['thread_cpu'], game, renderer, nav)
            row['roles_before'], row['roles_after'] = roles_before, roles_after
            row['completed'] = True
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(speed=speed,progress=row['progress'],cpu_seconds=row['process_resources']['thread_cpu']['process_cpu_seconds'])),flush=True)
        data['completed'] = True
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__,message=str(exc))
        raise
    finally:
        try:
            data['restored'] = await restore_test(c,False,reference)
        except Exception as exc:
            data['restoration_error'] = str(exc)
            raise
        finally:
            data['snapshot_files_unchanged'] = manifest(snapshot)==proof['snapshot_manifest']
            data['source_and_copy_unchanged'] = all(manifest(save_root/slot)==v['files'] for slot,v in source_files.items())
            data['settings_unchanged'] = settings.read_bytes()==original_settings
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(output=str(output),completed=data.get('completed'),error=data.get('error'),
                restored=bool(data.get('restored')),snapshot_unchanged=data['snapshot_files_unchanged'],
                source_and_copy_unchanged=data['source_and_copy_unchanged'],settings_unchanged=data['settings_unchanged'])),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot-proof',type=Path,required=True)
    p.add_argument('--baseline-proof',type=Path,required=True)
    p.add_argument('--hours',type=float,default=.5)
    p.add_argument('--environment-limit',type=int,default=500,choices=range(1,501))
    args=p.parse_args()
    if not math.isfinite(args.hours) or not .1 <= args.hours <= .75:
        p.error('hours must be finite in 0.1..0.75')
    asyncio.run(run(main,args.snapshot_proof,args.baseline_proof,args.hours,environment_limit=args.environment_limit))
