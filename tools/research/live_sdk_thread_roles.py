"""Read optional paused SDK roles around one x1 CPU interval in Heng via MCP."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio
import hashlib
import json
from pathlib import Path
import time
from benchmark import validate_camera_stability,simulation_progress,validate_nav_diagnostics
from physics_diagnostics import validate as validate_physics
from ai_diagnostics import validate as validate_ai
from sdk_thread_roles import validate as validate_roles,join_cpu
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready,wait_loaded
from probe import config,read_runtime_state,ProbeError
from resources import ProcessResources
from thread_resources import assign_roles


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    expected=json.loads(Path('runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    save_root=Path.home()/'AppData/Local/kenshi/save'
    if any(manifest(save_root/k)!=v['files'] for k,v in expected['save_manifests'].items()):raise RuntimeError('Protected save changed')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid']
    reference=await c.call('get_scene_state');validate_camera_stability(expected['scene'],reference)
    if not reference['paused'] or reference['free_camera'] or reference['battle']['active']:raise RuntimeError('Requires restored paused copy')
    settings=Path(cfg['working_directory'])/'settings.cfg';initial_settings=settings.read_bytes()
    output=Path('runtime/scenarios')/time.strftime('sdk-roles-%Y%m%dT%H%M%SZ.json',time.gmtime())
    data=dict(pid=pid,transport=c.transport,observations=[],seconds_requested=20,
        scope='Whole-thread CPU joined to SDK object roles, not exclusive function costs')
    try:
        data['initial_ping']=await c.call('ping')
        if data['initial_ping']['plugin_version'] not in {'0.7.7','0.7.8','0.7.9','0.8.0','0.8.1'}:raise RuntimeError('Requires thread-details build')
        data['copy_loaded']=await restore_test(c,False,reference)
        data['town']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True);await asyncio.sleep(3)
        data['roles_before']=await c.call('get_scene_state',thread_details=True)
        validate_roles(data['roles_before'],pid)
        await c.call('set_game_speed',speed=1);await asyncio.sleep(3)
        # Read-only details are intentionally refused while the world runs.
        try: await c.call('get_scene_state',thread_details=True)
        except ProbeError as exc:
            if 'require a paused world' not in str(exc):raise
            data['running_details_rejected']=True
        else:raise RuntimeError('Running thread-details query was not rejected')
        data['scene_before']=await c.call('get_scene_state');data['heartbeat_before']=await c.call('heartbeat')
        camera=data['scene_before'];resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
        started=time.monotonic()
        while time.monotonic()-started<20:
            await asyncio.sleep(.5);scene=await c.call('get_scene_state')
            data['observations'].append(dict(elapsed=time.monotonic()-started,scene=scene))
            validate_camera_stability(camera,scene)
            if scene['paused'] or scene['frame_speed_multiplier']!=1:raise RuntimeError('Simulation state changed')
            if (await read_runtime_state(state_path))['pid']!=pid:raise RuntimeError('Process changed')
        data['scene_after']=await c.call('get_scene_state');data['heartbeat_after']=await c.call('heartbeat')
        data['process_resources']=resources.finish()
        data['statistics_tail']=await c.call('get_frame_stats',n=600,detail='full')
        validate_nav_diagnostics(data['statistics_tail']);validate_physics(data['statistics_tail'])
        validate_ai(data['statistics_tail'])
        await c.call('pause',paused=True);await asyncio.sleep(3)
        data['roles_after']=await c.call('get_scene_state',thread_details=True)
        validate_roles(data['roles_after'],pid);validate_camera_stability(camera,data['roles_after'])
        data['simulation_progress']=simulation_progress(data['scene_before'],data['scene_after'])
        a,b=data['heartbeat_before'],data['heartbeat_after']
        assign_roles(data['process_resources']['thread_cpu'],{a['game_thread']} if a['game_thread']==b['game_thread'] else set(),
            {a['service_thread']} if a['service_thread']==b['service_thread'] else set(),set())
        data['role_cpu_join']=join_cpu(data['roles_before'],data['roles_after'],data['process_resources'],pid)
        data['completed']=True
    except Exception as exc:
        data['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        try:data['restored']=await restore_test(c,False,reference)
        except Exception as exc:data['restoration_error']=str(exc);raise
        finally:
            data['source_and_copy_unchanged']=all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items())
            data['settings_unchanged']=settings.read_bytes()==initial_settings
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(output=str(output),completed=data.get('completed'),error=data.get('error'),
                restored=bool(data.get('restored')),source_and_copy_unchanged=data['source_and_copy_unchanged'],
                settings_unchanged=data['settings_unchanged'],join=data.get('role_cpu_join'))),flush=True)


if __name__=='__main__':asyncio.run(run(main))
