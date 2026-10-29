"""Descriptive paused/active/paused CPU sequence in one city through real MCP.

Does not reset the city between phases or infer a causal subsystem cost. Keeps
thread identities, scene clocks, inventory bounds and restores the test copy.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time
from benchmark import simulation_progress,validate_camera_stability,validate_nav_diagnostics
from analyze_pause_cpu import validate_phase_state,validate_active_speed,bounded_tail_count
from environment_diagnostics import collect as environment,compare
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import wait_loaded,pause_ready
from probe import config,read_runtime_state
from resources import ProcessResources
from thread_resources import assign_roles
from physics_diagnostics import validate as validate_physics_diagnostics
from function_diagnostics import validate as validate_function


async def main(client=None,active_speed=1,adaptive_tail=False,tail_max=600):
    validate_active_speed(active_speed)
    if not isinstance(adaptive_tail,bool):raise ValueError('Adaptive-tail flag must be boolean')
    if isinstance(tail_max,bool) or not isinstance(tail_max,int) or not 1<=tail_max<=3600:
        raise ValueError('Tail maximum must be 1..3600')
    if not adaptive_tail and tail_max!=600:raise ValueError('Custom tail maximum requires adaptive mode')
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:
        raise RuntimeError('Final thirty minutes reserved for closure')
    proof_path=Path('runtime/scenarios/battle-campaign-073-final.json')
    proof=json.loads(proof_path.read_text(encoding='utf-8'))
    snapshot=json.loads(Path('runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    if manifest(snapshot_path)!=snapshot['snapshot_manifest']:raise RuntimeError('Protected snapshot changed')
    if any(manifest(save_root/slot)!=v['files'] for slot,v in proof['save_manifests'].items()):
        raise RuntimeError('Protected save manifest changed')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid']
    reference=await c.call('get_scene_state')
    if not reference['paused'] or reference['free_camera'] or reference['battle']['active']:
        raise RuntimeError('Requires restored test copy paused in normal camera mode')
    wd=Path(cfg['working_directory']);settings=wd/'settings.cfg';original_settings=settings.read_bytes()
    prefix='pause-cpu-' if active_speed==1 and not adaptive_tail else 'pause-cpu-x'+str(active_speed)+('-adaptive-' if adaptive_tail else '-')
    output=Path('runtime/scenarios')/time.strftime(prefix+'%Y%m%dT%H%M%SZ.json',time.gmtime())
    data=dict(pid=pid,transport=c.transport,town='Heng',phases=[],seconds_requested=20,
        warmup_seconds_per_phase=3,observation_interval_seconds=.5,
        configuration_fingerprints={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [settings,wd/'data/mods.cfg',wd/'mods/KenshiProbe/KenshiProbe.dll']},
        limits=['Single city sequence; time, population and streaming can evolve between phases.',
                'Whole-process and whole-thread CPU, including modules and observer requests.',
                'Navigation labels use retained calls only; absence is not zero navigation CPU.',
                'Other application CPU is not fixed or quantified.'])
    data['initial_ping']=await c.call('ping')
    if active_speed!=1 or adaptive_tail:data.update(active_speed=active_speed,adaptive_tail=adaptive_tail,tail_max=tail_max)
    try:
        data['copy_loaded']=await restore_test(c,False,lock_edge=True)
        reference=data['copy_loaded'];data['source_reference']=reference
        data['town_preparation']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False)
        await asyncio.sleep(10)
        await wait_loaded(c,0,stable_seconds=3)
        camera=await c.call('get_scene_state')
        if adaptive_tail and not camera['scene_camera_control_owned']:raise RuntimeError('Adaptive campaign requires camera guard')
        for label,paused in [('paused_before',True),('running_x'+str(active_speed),False),('paused_after',True)]:
            if time.time()+300>=cfg['session_until']:
                raise RuntimeError('Leaving time for restoration')
            row=dict(label=label,expected_paused=paused,observations=[]);data['phases'].append(row)
            if active_speed!=1 or adaptive_tail:row['active_speed']=active_speed
            row['activation']=await c.call('pause',paused=True) if paused else await c.call('set_game_speed',speed=active_speed)
            await asyncio.sleep(3)
            row['environment_before']=await environment(c,500)
            if adaptive_tail and not row['environment_before']['summary']['complete']:
                raise RuntimeError('Adaptive campaign inventory incomplete before phase')
            if paused:row['sdk_roles_before']=await c.call('get_scene_state',thread_details=True)
            row['scene_before']=await c.call('get_scene_state')
            validate_phase_state(camera,row['scene_before'],paused,active_speed)
            row['roles_before']=await c.call('heartbeat')
            resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
            started=time.monotonic()
            while time.monotonic()-started<20:
                await asyncio.sleep(.5)
                scene=await c.call('get_scene_state')
                row['observations'].append(dict(elapsed=time.monotonic()-started,scene=scene))
                validate_phase_state(camera,scene,paused,active_speed)
                if (await read_runtime_state(state_path))['pid']!=pid:
                    raise RuntimeError('Game process changed')
                progress=simulation_progress(row['scene_before'],scene)
                if paused and progress['game_hours']>1e-7:
                    raise RuntimeError('Paused clock advanced')
            count=600
            if adaptive_tail:
                observed=await c.call('get_scene_state')
                validate_phase_state(camera,observed,paused,active_speed)
                count=bounded_tail_count(row['scene_before']['frame'],observed['frame'],tail_max)
                row['statistics_tail_selection']=dict(policy='bounded_since_phase_start',maximum=tail_max,
                    observed_scene=observed,requested_count=count)
            row['statistics_tail']=await c.call('get_frame_stats',n=count,detail='full')
            row['scene_after']=await c.call('get_scene_state')
            row['roles_after']=await c.call('heartbeat')
            row['process_resources']=resources.finish()
            row['simulation_progress']=simulation_progress(row['scene_before'],row['scene_after'])
            context=await c.call('get_frame_stats',n=3600,detail='full')
            validate_nav_diagnostics(row['statistics_tail']);validate_nav_diagnostics(context)
            validate_physics_diagnostics(row['statistics_tail']);validate_physics_diagnostics(context)
            validate_function(row['statistics_tail']);validate_function(context)
            if not row['scene_before']['frame']<=row['statistics_tail']['first_frame']<=row['statistics_tail']['last_frame']<=row['scene_after']['frame']:
                raise RuntimeError('Function tail outside scene interval')
            row['thread_attribution_statistics']=context
            a,b=row['roles_before'],row['roles_after']
            game={a['game_thread']} if a['game_thread']==b['game_thread'] else set()
            renderer={a['service_thread']} if a['service_thread']==b['service_thread'] else set()
            nav={x['thread_id'] for x in context['navmesh_slow_calls'] if a['frame']<=x['completion_frame']<=b['frame']}
            assign_roles(row['process_resources']['thread_cpu'],game,renderer,nav)
            row['environment_after']=await environment(c,500)
            if adaptive_tail and not row['environment_after']['summary']['complete']:
                raise RuntimeError('Adaptive campaign inventory incomplete after phase')
            if paused:row['sdk_roles_after']=await c.call('get_scene_state',thread_details=True)
            row['environment_comparison']=compare(row['environment_before']['summary'],row['environment_after']['summary'])
            validate_camera_stability(camera,row['environment_after']['scene_after'])
            row['completed']=True
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(phase=label,logical_cpu_equivalents=row['process_resources']['logical_cpu_equivalents'],
                game_hours=row['simulation_progress']['game_hours'],
                populations=[row['environment_before']['summary']['total_update_list'],row['environment_after']['summary']['total_update_list']])),flush=True)
        data['completed']=True
    except Exception as exc:
        data['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        try:
            data['restored']=await restore_test(c,False,reference,lock_edge=True)
        except Exception as exc:
            data['restoration_error']=str(exc);data['completed']=False
        try:
            await c.call('pause',paused=True)
            data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
        except Exception as exc:
            data['camera_release_error']=str(exc);data['completed']=False
        try:
            data['source_and_copy_unchanged']=all(manifest(save_root/slot)==v['files'] for slot,v in proof['save_manifests'].items())
            data['old_snapshot_unchanged']=manifest(snapshot_path)==snapshot['snapshot_manifest']
            data['settings_unchanged']=settings.read_bytes()==original_settings
            if not data['source_and_copy_unchanged'] or not data['old_snapshot_unchanged'] or not data['settings_unchanged']:data['completed']=False
        except Exception as exc:data['verification_error']=str(exc);data['completed']=False
        output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(output=str(output),completed=data.get('completed'),error=data.get('error'),
            restored=bool(data.get('restored')),source_and_copy_unchanged=data.get('source_and_copy_unchanged'),
            settings_unchanged=data.get('settings_unchanged'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--speed',type=int,choices=(1,5),default=1)
    parser.add_argument('--adaptive-tail',action='store_true');parser.add_argument('--tail-max',type=int,default=600)
    args=parser.parse_args()
    asyncio.run(run(main,active_speed=args.speed,adaptive_tail=args.adaptive_tail,tail_max=args.tail_max))
