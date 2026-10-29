"""One 40-NPC x5 urban fight through MCP; bounded windows and full restoration."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio,hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from analyze_heavy_battle import validate_cohort
from analyze_pause_cpu import bounded_tail_count
from benchmark import simulation_progress,validate_nav_diagnostics
from environment_diagnostics import collect as environment
from function_diagnostics import validate as function_stats
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready,wait_loaded
from probe import config,read_runtime_state
from resources import ProcessResources
from sdk_thread_roles import validate as validate_roles
from thread_resources import assign_roles
from statistics_budget import collect as bounded_statistics


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid'];process=psutil.Process(pid)
    created=process.create_time();executable=process.exe();command=process.cmdline()
    if Path(executable).resolve()!=Path(cfg['executable']).resolve() or command!=[executable,'--norestart']:raise RuntimeError('Unexpected game identity')
    def identity():
        p=psutil.Process(pid)
        if p.create_time()!=created or p.exe()!=executable or p.cmdline()!=command:raise RuntimeError('Game identity changed')
    proof=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text(encoding='utf-8'))
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():return all(manifest(save_root/k)==v['files'] for k,v in proof['save_manifests'].items()) and manifest(snapshot_path)==snapshot['snapshot_manifest']
    if not protected():raise RuntimeError('Protected save manifests differ')
    initial=await c.call('get_scene_state')
    if not initial['paused'] or initial['free_camera'] or initial['battle']['active'] or initial['scene_camera_control_owned']:raise RuntimeError('Requires restored paused copy')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    source=save_root/'KenshiProbe_validation/quick.save';source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    output=ROOT/'runtime/scenarios'/('heavy-battle-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data=dict(pid=pid,created_at=created,executable=executable,cmdline=command,transport=c.transport,speed=5,pairs=20,
        town='Mongrel',template_id='16863-gamedata.base',faction_name='Bloodraiders',opponent_template_id='1227-gamedata.base',
        opponent_faction_name='Mercenary Guild',sampling_interval_seconds=.25,source_sha256_before=source_sha,
        random_seed_controlled=False,windows=[],observations=[],completed=False)
    reference=None;mutations=False
    def publish():output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    try:
        data['initial_ping']=await c.call('ping')
        assert data['initial_ping']['plugin_version']=='0.8.10' and data['initial_ping']['system_hook_count']==3
        mutations=True;publish();reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        data['town_preparation']=await c.call('prepare_town_scene',name='Mongrel')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3);await pause_ready(c,True)
        data['focused']=await c.call('focus_town',name='Mongrel');await asyncio.sleep(2)
        data['prepared']=await c.call('prepare_battle_scene',template_id=data['template_id'],pairs=20,faction_name=data['faction_name'],
            opponent_template_id=data['opponent_template_id'],opponent_faction_name=data['opponent_faction_name'])
        if not data['prepared']['prepared'] or not data['prepared']['mutual_enemies_verified']:raise RuntimeError('Partial battle setup; reload, no retry')
        data['initial']=await c.call('get_scene_state');validate_cohort(data['initial'],data['initial'],5,True)
        data['environment_before']=await environment(c,500)
        if not data['environment_before']['summary']['complete']:raise RuntimeError('Incomplete pre-battle city inventory')
        data['sdk_roles_before']=await c.call('get_scene_state',thread_details=True);validate_roles(data['sdk_roles_before'],pid)
        data['activation']=await c.call('set_game_speed',speed=5);campaign_started=time.monotonic()
        for index,seconds in enumerate((5,5,10,10)):
            if time.time()+300>=cfg['session_until']:raise RuntimeError('Restoration time reserved')
            identity();row=dict(label='window_'+str(index+1),requested_seconds=seconds,observations=[],completed=False);data['windows'].append(row)
            row['scene_before']=await c.call('get_scene_state');validate_cohort(data['initial'],row['scene_before'])
            row['roles_before']=await c.call('heartbeat');resources=ProcessResources(pid,cfg['executable'],sample_threads=True);started=time.monotonic()
            while time.monotonic()-started<seconds:
                await asyncio.sleep(.25);scene=await c.call('get_scene_state');validate_cohort(data['initial'],scene)
                observation=dict(elapsed=time.monotonic()-campaign_started,scene=scene)
                data['observations'].append(observation);row['observations'].append(observation)
                if (await read_runtime_state(state_path))['pid']!=pid:raise RuntimeError('Watchdog PID changed')
            row['selection_scene']=await c.call('get_scene_state');validate_cohort(data['initial'],row['selection_scene'])
            row['requested_frames']=bounded_tail_count(row['scene_before']['frame'],row['selection_scene']['frame'],3600)
            row['statistics_collection']={}
            row['statistics'],_=await bounded_statistics(c,row['requested_frames'],row['statistics_collection'])
            validate_nav_diagnostics(row['statistics']);function_stats(row['statistics'])
            row['scene_after']=await c.call('get_scene_state');validate_cohort(data['initial'],row['scene_after'])
            row['roles_after']=await c.call('heartbeat');row['process_resources']=resources.finish()
            row['simulation_progress']=simulation_progress(row['scene_before'],row['scene_after'])
            if row['simulation_progress']['game_hours']<=0:raise RuntimeError('Battle clock did not advance')
            if not row['scene_before']['frame']<row['statistics']['first_frame']<=row['statistics']['last_frame']<=row['scene_after']['frame']:
                raise RuntimeError('Battle statistics outside own window')
            row['context_collection']={}
            context,_=await bounded_statistics(c,3600,row['context_collection']);row['context']=context;validate_nav_diagnostics(context)
            a,b=row['roles_before'],row['roles_after'];game={a['game_thread']} if a['game_thread']==b['game_thread'] else set();renderer={a['service_thread']} if a['service_thread']==b['service_thread'] else set()
            nav={x['thread_id'] for x in context['navmesh_slow_calls'] if a['frame']<=x['completion_frame']<=b['frame']}
            assign_roles(row['process_resources']['thread_cpu'],game,renderer,nav)
            row['completed']=True;publish()
            print(json.dumps(dict(window=row['label'],logical_cpu=row['process_resources']['logical_cpu_equivalents'],
                frames=row['statistics']['count'],unconscious=row['scene_after']['battle']['unconscious_count'])),flush=True)
        await c.call('pause',paused=True)
        data['sdk_roles_after']=await c.call('get_scene_state',thread_details=True);validate_roles(data['sdk_roles_after'],pid)
        data['environment_after']=await environment(c,500)
        if not data['environment_after']['summary']['complete']:raise RuntimeError('Incomplete post-battle city inventory')
        identity();data['measurement_valid']=True
    except Exception as exc:data['error']=dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mutations:
            try:
                identity();data['restored']=await restore_test(c,False,reference,lock_edge=True)
                if reference is not None and data['restored']['game_total_hours']!=reference['game_total_hours']:raise RuntimeError('Restored simulation hour differs')
            except Exception as exc:data['restoration_error']=str(exc)
            try:
                identity();await c.call('pause',paused=True);data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as exc:data['camera_release_error']=str(exc)
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before
        data['source_sha256_after']=hashlib.sha256(source.read_bytes()).hexdigest();data['final_scene']=await c.call('get_scene_state')
        data['completed']=bool(data.get('measurement_valid') and not any(data.get(k) for k in ('error','restoration_error','camera_release_error')) and
            data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and not data['final_scene']['scene_camera_control_owned'])
        publish();print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),restoration_error=data.get('restoration_error'),
            windows=len(data['windows']),protected=data['protected_files_unchanged'],settings=data['settings_unchanged'])),flush=True)


if __name__=='__main__':
    os.chdir(ROOT);asyncio.run(run(main))
