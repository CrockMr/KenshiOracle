"""MCP service wall time in two paused scenes; raw requests and restoration."""
import asyncio,hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from command_service import summarize,validate
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready,wait_loaded
from probe import config,read_runtime_state
from thread_resources import WindowsThreadSampler
from benchmark import validate_camera_stability


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid'];proc=psutil.Process(pid)
    created=proc.create_time();exe=proc.exe();cmdline=proc.cmdline()
    def identity():
        p=psutil.Process(pid)
        if p.create_time()!=created or p.exe()!=exe or p.cmdline()!=cmdline or Path(exe).resolve()!=Path(cfg['executable']).resolve() or cmdline!=[exe,'--norestart']:
            raise RuntimeError('Unexpected game identity')
    identity()
    proof=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():return all(manifest(save_root/k)==v['files'] for k,v in proof['save_manifests'].items()) and manifest(snapshot_path)==snapshot['snapshot_manifest']
    if not protected():raise RuntimeError('Protected save manifests differ')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    initial=await c.call('get_scene_state')
    if not initial['paused'] or initial['free_camera'] or initial['battle']['active'] or initial['scene_camera_control_owned']:raise RuntimeError('Requires restored paused copy')
    ping=await c.call('ping');validate(ping,'ping')
    if ping['plugin_version']!='0.8.11' or not ping['command_service_timing_enabled'] or ping['system_hook_count']!=3:raise RuntimeError('Native service probe unavailable')
    output=ROOT/'runtime/scenarios'/('command-service-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data=dict(pid=pid,created_at=created,executable=exe,cmdline=cmdline,transport=c.transport,initial_ping=ping,
        repetitions=12,phases=[],completed=False)
    reference=None;mutations=False
    def publish():output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    async def phase(label,actors):
        identity();before=await c.call('get_scene_state',thread_details=True)
        if not before['paused'] or before['frame_speed_multiplier']!=0 or before['battle']['matched_loaded']!=actors or len(before['battle']['members'])!=actors:raise RuntimeError('Unexpected paused cohort')
        row=dict(label=label,actor_count=actors,before=before,requests=[],thread_before=WindowsThreadSampler(pid)())
        data['phases'].append(row);publish()
        # Rotating order avoids always putting one command first; no warmup discarded.
        commands=[('ping','ping',{}),('scene','get_scene_state',{}),('scene_roles','get_scene_state',dict(thread_details=True)),('statistics_60','get_frame_stats',dict(n=60,detail='full'))]
        for repetition in range(12):
            identity()
            for offset in range(4):
                name,command,params=commands[(repetition+offset)%4]
                start=time.perf_counter();result=await c.call(command,**params);wall=(time.perf_counter()-start)*1000
                row['requests'].append(dict(repetition=repetition,label=name,command=command,params=params,client_ms=wall,
                    compact_result_bytes=len(json.dumps(result,separators=(',',':')).encode()),result=result))
                timing=validate(result,command)
                if timing['menu_service'] and command!='ping':raise RuntimeError('Unexpected Renderer command')
                if command=='get_scene_state':
                    if not result['paused'] or result['battle']['matched_loaded']!=actors or len(result['battle']['members'])!=actors or result['game_total_hours']!=before['game_total_hours']:raise RuntimeError('Paused scene changed')
                    validate_camera_stability(before,result)
                await asyncio.sleep(.1)
        row['thread_after']=WindowsThreadSampler(pid)();row['after']=await c.call('get_scene_state',thread_details=True)
        if not row['after']['paused'] or row['after']['game_total_hours']!=before['game_total_hours']:raise RuntimeError('Paused phase clock advanced')
        validate_camera_stability(before,row['after'])
        keys={(validate(item['result'],item['command'])['thread_id'],item['result']['_probe_service']['created_filetime']) for item in row['requests']}
        for sample in (row['thread_before'],row['thread_after']):
            known={(t['tid'],t.get('created_filetime')) for t in sample['threads'] if not t.get('error')}
            if not keys<=known:raise RuntimeError('Service thread creation not verified at both endpoints')
        row['summary']=summarize(row['requests']);row['completed']=True;publish()
        print(json.dumps(dict(phase=label,requests=len(row['requests']),service=row['summary'])),flush=True)
    try:
        mutations=True;publish();reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        await phase('copy_no_battle',0)
        data['town_preparation']=await c.call('prepare_town_scene',name='Mongrel')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3);await pause_ready(c,True)
        data['focused']=await c.call('focus_town',name='Mongrel');await asyncio.sleep(2)
        data['prepared']=await c.call('prepare_battle_scene',template_id='16863-gamedata.base',pairs=20,faction_name='Bloodraiders',
            opponent_template_id='1227-gamedata.base',opponent_faction_name='Mercenary Guild')
        if not data['prepared']['prepared'] or not data['prepared']['mutual_enemies_verified']:raise RuntimeError('Partial setup; restore without retry')
        await phase('mongrel_40_paused',40)
        data['measurement_valid']=True
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
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before
        data['final_scene']=await c.call('get_scene_state')
        data['completed']=bool(data.get('measurement_valid') and not any(data.get(k) for k in ('error','restoration_error','camera_release_error')) and
            data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and not data['final_scene']['scene_camera_control_owned'])
        publish();print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),restoration_error=data.get('restoration_error'))),flush=True)


if __name__=='__main__':os.chdir(ROOT);asyncio.run(run(main))
