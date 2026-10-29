"""Pause/x5/pause original Ogre root frame wall through a loaded named export at Heng."""
import asyncio,hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from chars_diagnostics import validate as chars
from function_diagnostics import validate as function
from benchmark import simulation_progress,validate_camera_stability,validate_nav_diagnostics
from analyze_pause_cpu import bounded_tail_count,validate_phase_state
from environment_diagnostics import collect as environment
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import wait_loaded,pause_ready
from probe import config,read_runtime_state
from resources import ProcessResources
from sdk_thread_roles import validate as roles
from statistics_budget import collect as bounded_statistics


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid'];p=psutil.Process(pid)
    created=p.create_time();exe=p.exe();cmdline=p.cmdline()
    def identity():
        proc=psutil.Process(pid)
        if proc.create_time()!=created or proc.exe()!=exe or proc.cmdline()!=cmdline or Path(exe).resolve()!=Path(cfg['executable']).resolve() or cmdline!=[exe,'--norestart']:raise RuntimeError('Game identity changed')
    identity();proof=json.loads(Path('runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot=json.loads(Path('runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'));snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():return all(manifest(save_root/k)==v['files'] for k,v in proof['save_manifests'].items()) and manifest(snapshot_path)==snapshot['snapshot_manifest']
    if not protected():raise RuntimeError('Protected save manifests differ')
    initial=await c.call('get_scene_state')
    if not initial['paused'] or initial['free_camera'] or initial['battle']['active'] or initial['scene_camera_control_owned']:raise RuntimeError('Requires restored paused copy')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    output=Path('runtime/scenarios')/('root-cpu-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data=dict(pid=pid,created_at=created,executable=exe,cmdline=cmdline,transport=c.transport,town='Heng',active_speed=5,seconds_requested=12,
        observation_interval_seconds=.5,warmup_seconds_per_phase=3,expected_function_cpu_enabled=True,phases=[],completed=False)
    reference=None;mutations=False
    def publish():output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    try:
        data['initial_ping']=await c.call('ping');ping=data['initial_ping']
        data['calibration_reference']=dict(path='runtime/thread-cpu-calibration-analysis.json',sha256=hashlib.sha256(Path('runtime/thread-cpu-calibration-analysis.json').read_bytes()).hexdigest(),scope='Separate own-helper observations, not guaranteed in-game precision')
        if ping['plugin_version']!='0.8.18' or ping['system_hook_count']!=3 or not ping['chars_update_split_profiling'] or ping['chars_update_bucket_bytes']!=696 or ping['telemetry_sample_bytes']!=696 or ping['chars_update_history_bytes']!=2523600:raise RuntimeError('New split/capacity unavailable')
        if ping['profiled_function']!='Ogre::Root::renderOneFrame' or ping['function_hook_reuses_service'] or ping['dedicated_system_hook_count']!=3 or ping['service_hook_count']!=2 or ping['installed_hook_count']!=5 or ping['havok_character_update_profiling'] or not ping['function_thread_cpu_enabled'] or ping['renderer_update_profiling'] or not ping['ogre_render_one_frame_profiling'] or ping['main_loop_gpu_sensitive_profiling']:raise RuntimeError('Root export contract differs')
        from sdk_address_map import _PE
        from thread_metadata import WindowsThreadMetadata
        module_path=Path(ping['function_binding_module_path']);expected_module=ROOT/'Re_Kenshi/OgreMain_x64.dll'
        if module_path.resolve()!=expected_module.resolve():raise RuntimeError('Unexpected Ogre module path')
        module_bytes=module_path.read_bytes();module_sha=hashlib.sha256(module_bytes).hexdigest()
        if module_sha!='7d3888d21398647519f10a89b1f300d8606f761ad159e6021a797b1b9b3df5f6':raise RuntimeError('Ogre module changed')
        image=_PE(module_bytes);exports,_=image.exports();entries=[e for e in exports if e['name']==ping['function_binding_symbol']]
        loaded=[m for m in WindowsThreadMetadata().modules(pid) if Path(m['path']).resolve()==module_path.resolve()]
        if len(entries)!=1 or entries[0]['forwarder'] is not None or len(loaded)!=1 or loaded[0]['size']!=image.size_image or int(ping['function_binding_address'],16)!=int(loaded[0]['base'],16)+entries[0]['rva']:raise RuntimeError('Loaded Root export address differs')
        data['function_module']=dict(path=str(module_path),sha256=module_sha,bytes=len(module_bytes),loaded=loaded[0],export=entries[0])
        mutations=True;publish();reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        data['town_preparation']=await c.call('prepare_town_scene',name='Heng');await pause_ready(c,False);await asyncio.sleep(10)
        await wait_loaded(c,0,stable_seconds=3);await pause_ready(c,True);data['camera_reference']=await c.call('get_scene_state')
        data['sdk_roles_before']=await c.call('get_scene_state',thread_details=True);roles(data['sdk_roles_before'],pid)
        for label,paused in [('paused_before',True),('running_x5',False),('paused_after',True)]:
            if time.time()+300>=cfg['session_until']:raise RuntimeError('Restoration time reserved')
            identity();row=dict(label=label,expected_paused=paused,observations=[],completed=False);data['phases'].append(row)
            row['activation']=await c.call('pause',paused=True) if paused else await c.call('set_game_speed',speed=5)
            await asyncio.sleep(3);row['environment_before']=await environment(c,500)
            if not row['environment_before']['summary']['complete']:raise RuntimeError('Incomplete city inventory before phase')
            row['scene_before']=await c.call('get_scene_state');validate_phase_state(data['camera_reference'],row['scene_before'],paused,5)
            row['roles_before']=await c.call('heartbeat');resources=ProcessResources(pid,cfg['executable'],sample_threads=True);started=time.monotonic()
            while time.monotonic()-started<12:
                await asyncio.sleep(.5);scene=await c.call('get_scene_state');row['observations'].append(dict(elapsed=time.monotonic()-started,scene=scene))
                validate_phase_state(data['camera_reference'],scene,paused,5)
                if (await read_runtime_state(state_path))['pid']!=pid:raise RuntimeError('Watchdog PID changed')
            row['selection_scene']=await c.call('get_scene_state');row['requested_frames']=bounded_tail_count(row['scene_before']['frame'],row['selection_scene']['frame'],3600)
            row['statistics_collection']={};row['statistics'],_=await bounded_statistics(c,row['requested_frames'],row['statistics_collection'])
            split=chars(row['statistics']);selected=function(row['statistics']);validate_nav_diagnostics(row['statistics'])
            if not selected['cpu_enabled'] or selected['cpu_unavailable_calls'] or selected['cpu_available_calls']!=selected['calls_total']:raise RuntimeError('Incomplete Root CPU counters')
            if selected['function']!='Ogre::Root::renderOneFrame' or selected['hook_source']!='loaded_ogre_export' or selected['leading_service_excluded']:raise RuntimeError('Selected service scope differs')
            row['scene_after']=await c.call('get_scene_state');validate_phase_state(data['camera_reference'],row['scene_after'],paused,5)
            row['roles_after']=await c.call('heartbeat');row['process_resources']=resources.finish();row['simulation_progress']=simulation_progress(row['scene_before'],row['scene_after'])
            if paused and row['simulation_progress']['game_hours']!=0 or not paused and row['simulation_progress']['game_hours']<=0:raise RuntimeError('Phase clock differs')
            if not row['scene_before']['frame']<row['statistics']['first_frame']<=row['statistics']['last_frame']<=row['scene_after']['frame']:raise RuntimeError('Statistics outside phase')
            row['environment_after']=await environment(c,500)
            if not row['environment_after']['summary']['complete']:raise RuntimeError('Incomplete city inventory after phase')
            row['completed']=True;publish()
            print(json.dumps(dict(phase=label,frames=row['statistics']['count'],selected_calls=selected['calls_total'],original_mean_ms=selected['mean_ms'],frame_mean_ms=row['statistics']['mean_ms'],chars_calls=split['calls_total'])),flush=True)
        data['sdk_roles_after']=await c.call('get_scene_state',thread_details=True);roles(data['sdk_roles_after'],pid);data['measurement_valid']=True
    except Exception as exc:data['error']=dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mutations:
            try:
                identity();data['restored']=await restore_test(c,False,reference,lock_edge=True)
                if reference is not None and data['restored']['game_total_hours']!=reference['game_total_hours']:raise RuntimeError('Restored game hour differs')
            except Exception as exc:data['restoration_error']=str(exc)
            try:
                identity();await c.call('pause',paused=True);data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as exc:data['camera_release_error']=str(exc)
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before;data['final_scene']=await c.call('get_scene_state')
        data['completed']=bool(data.get('measurement_valid') and not any(data.get(k) for k in ('error','restoration_error','camera_release_error')) and data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and not data['final_scene']['scene_camera_control_owned'])
        publish();print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),restoration_error=data.get('restoration_error'))),flush=True)


if __name__=='__main__':os.chdir(ROOT);asyncio.run(run(main))
