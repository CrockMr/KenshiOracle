"""Admin-only ten-second CPU stack capture in Heng; always restore test copy.

Run this file by absolute path. No PYTHONPATH or caller working directory is
required. CPU/process/image metadata is system-wide; reports must filter Kenshi.
"""
import asyncio
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
for directory in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(directory))
import psutil
from wpr_recording import Recording
from probe import config,read_runtime_state
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready,wait_loaded
from benchmark import validate_camera_stability,simulation_progress
from sdk_thread_roles import validate as validate_roles,join_cpu
from resources import ProcessResources


async def capture(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Run this script from PowerShell administrator')
    instance='KenshiProbeHeng_'+uuid.uuid4().hex[:12];root=ROOT/'runtime/etw'/instance;root.mkdir()
    trace=root/'cpu.etl';output=root/'controller.json'
    session=Recording(instance,ROOT/'tests/cpu-sampling.wprp',root)
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    settings=Path(cfg['working_directory'])/'settings.cfg'
    data=dict(instance=instance,requested_seconds=10,condition='Heng x1 CPU stacks',session_until=cfg['session_until'],transport=c.transport,
        profile_sha256=hashlib.sha256(session.profile.read_bytes()).hexdigest(),observations=[],world_mutations_started=False)
    reference=None;initial_settings=None
    def publish():
        data.update(wpr_commands=session.commands,cleanup_required=session.cleanup_required)
        output.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    def identity(pid):
        p=psutil.Process(pid)
        if Path(p.exe()).resolve()!=Path(cfg['executable']).resolve():raise RuntimeError('Unexpected executable')
        return dict(pid=pid,executable=p.exe(),created_at=p.create_time(),cmdline=p.cmdline())
    try:
        session.verify_idle()
        if any(manifest(save_root/k)!=v['files'] for k,v in expected['save_manifests'].items()):raise RuntimeError('Protected save mismatch')
        if manifest(snapshot_path)!=snapshot['snapshot_manifest']:raise RuntimeError('Protected snapshot mismatch')
        initial_settings=settings.read_bytes();(root/'settings-before.cfg').write_bytes(initial_settings)
        data['configuration_fingerprints']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [settings,Path(cfg['executable']),Path(cfg['working_directory'])/'data/mods.cfg',Path(cfg['working_directory'])/'mods/KenshiProbe/KenshiProbe.dll',Path(__file__)]}
        state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid'];data.update(identity(pid))
        reference=await c.call('get_scene_state');data['entry_scene']=reference
        if not reference['paused'] or reference['free_camera'] or reference['battle']['active']:raise RuntimeError('Requires restored paused test copy')
        data['initial_ping']=await c.call('ping')
        if not data['initial_ping'].get('camera_load_edge_lock_available'):raise RuntimeError('Requires the load camera-lock build')
        data['world_mutations_started']=True;publish();print(json.dumps(dict(stage='prepare_heng',output=str(output))),flush=True)
        data['copy_loaded']=await restore_test(c,False,lock_edge=True)
        reference=data['copy_loaded'];data['source_reference']=reference
        data['town']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True);await asyncio.sleep(3)
        data['roles_before']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_before'],pid)
        await c.call('set_game_speed',speed=1);await asyncio.sleep(3)
        data['scene_before']=await c.call('get_scene_state');camera=data['scene_before']
        if camera['paused'] or camera['frame_speed_multiplier']!=1:raise RuntimeError('x1 not active')
        resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
        data['start_requested_at']=time.time();session.start();data['recording_started_at']=time.time();publish()
        print(json.dumps(dict(stage='capture_10_seconds',instance=instance)),flush=True)
        started=time.monotonic()
        while time.monotonic()-started<10:
            await asyncio.sleep(.5);scene=await c.call('get_scene_state')
            data['observations'].append(dict(elapsed=time.monotonic()-started,scene=scene))
            validate_camera_stability(camera,scene)
            if scene['paused'] or scene['frame_speed_multiplier']!=1:raise RuntimeError('Simulation state changed')
            if identity(pid)['created_at']!=data['created_at'] or (await read_runtime_state(state_path))['pid']!=pid:raise RuntimeError('Game lifetime changed')
        data['recording_status']=session.call('recording_status','-status','collectors','-details','-instancename',instance)
        data['stop_requested_at']=time.time();session.stop(trace);data['recording_stopped_at']=time.time();publish()
        data['scene_after']=await c.call('get_scene_state');validate_camera_stability(camera,data['scene_after'])
        data['process_resources']=resources.finish();data['cpu_interval_scope']='Encloses WPR start/stop and MCP observation gaps; not exactly the ETL time range'
        data['simulation_progress']=simulation_progress(data['scene_before'],data['scene_after'])
        data['statistics_tail']=await c.call('get_frame_stats',n=600,detail='full')
        await pause_ready(c,True);await asyncio.sleep(1)
        data['roles_after']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_after'],pid)
        data['role_cpu_join']=join_cpu(data['roles_before'],data['roles_after'],data['process_resources'],pid)
        if identity(pid)['created_at']!=data['created_at']:raise RuntimeError('Game lifetime changed')
        data['trace_exists']=trace.is_file()
        if not data['trace_exists']:raise RuntimeError('WPR did not save a trace')
        data['trace_bytes']=trace.stat().st_size;data['trace_sha256']=hashlib.sha256(trace.read_bytes()).hexdigest()
        data['completed']=True
    except Exception as e:data['error']=dict(type=type(e).__name__,message=str(e))
    finally:
        try:session.stop(trace)
        except Exception as e:data['cleanup_error']=str(e);data['completed']=False
        if data['world_mutations_started'] and reference is not None:
            try:data['restored']=await restore_test(c,False,reference,lock_edge=True)
            except Exception as e:data['restoration_error']=str(e);data['completed']=False
            try:
                await c.call('pause',paused=True)
                data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as e:data['camera_release_error']=str(e);data['completed']=False
        try:
            data['source_and_copy_unchanged']=all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items())
            settings_after=settings.read_bytes();(root/'settings-after.cfg').write_bytes(settings_after)
            data['settings_after_sha256']=hashlib.sha256(settings_after).hexdigest()
            data['settings_unchanged']=initial_settings is None or settings_after==initial_settings
            data['old_snapshot_unchanged']=manifest(snapshot_path)==snapshot['snapshot_manifest']
            if not data['source_and_copy_unchanged'] or not data['settings_unchanged'] or not data['old_snapshot_unchanged']:data['completed']=False
        except Exception as e:data['verification_error']=str(e);data['completed']=False
        publish()
        print(json.dumps(dict(output=str(output),completed=data.get('completed',False),error=data.get('error'),cleanup_required=session.cleanup_required,
            trace_exists=trace.is_file(),restored=bool(data.get('restored')),source_and_copy_unchanged=data.get('source_and_copy_unchanged'))),flush=True)


if __name__=='__main__':
    os.chdir(ROOT)
    asyncio.run(run(capture))
