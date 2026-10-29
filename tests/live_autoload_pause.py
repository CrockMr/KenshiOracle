"""Observe the first ready copy after startup or a requested real restart.

Start before the watchdog for --previous-pid; --restart issues one MCP restart.
No manual input/WPR is used. Never unpauses or saves the disposable world.
"""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from benchmark import simulation_progress
from live_mcp_battle import run
from live_scene_snapshot import manifest
from probe import ProbeError,config,read_runtime_state


async def observe(previous_pid,restart,client=None):
    c=client;cfg=config()
    if cfg['startup_save']!='KenshiProbe_test' or time.time()+1800>=cfg['session_until']:
        raise RuntimeError('Requires disposable startup save and time before closure')
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():
        return (all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items()) and
            manifest(snapshot_path)==snapshot['snapshot_manifest'])
    if not protected():raise RuntimeError('Protected files differ before observation')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    output=ROOT/'runtime/scenarios'/('autoload-pause-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data=dict(previous_pid=previous_pid,requested_restart=restart,transport=c.transport,observations=[],completed=False)
    state_path=Path(cfg['runtime'])/'state.json';restart_task=None
    archives_before=set(Path(cfg['crashes']).iterdir())
    def publish():output.write_text(json.dumps(data,indent=2),encoding='utf-8')
    def identity(pid):
        p=psutil.Process(pid)
        if Path(p.exe()).resolve()!=Path(cfg['executable']).resolve() or p.cmdline()!=[p.exe(),'--norestart']:
            raise RuntimeError('Wrong project game identity')
        return dict(pid=pid,executable=p.exe(),created_at=p.create_time(),cmdline=p.cmdline())
    print(json.dumps(dict(stage='waiting_for_new_game',output=str(output))),flush=True);publish()
    try:
        if restart:
            state=await read_runtime_state(state_path);previous_pid=state['pid'];data['previous_pid']=previous_pid
            data['before_identity']=identity(previous_pid)
            before=await c.call('ping')
            if before['plugin_version']!='0.8.4' or not before['paused']:raise RuntimeError('Restart requires paused 0.8.4 copy')
            if identity(previous_pid)!=data['before_identity']:raise RuntimeError('Game identity changed before request')
            restart_task=asyncio.create_task(c.call('restart_game'))
        end=time.monotonic()+180
        while time.monotonic()<end:
            try:
                state=await read_runtime_state(state_path)
                p=await c.call('ping')
            except (ProbeError,FileNotFoundError):
                await asyncio.sleep(.1);continue
            row=dict(observed_at=time.time(),pid=state.get('pid'),autoload_requested=state.get('autoload_requested'),
                loading=state.get('loading'),ping=p)
            data['observations'].append(row)
            if state.get('pid')==previous_pid or not state.get('autoload_requested'):
                await asyncio.sleep(.1);continue
            if p['plugin_version']!='0.8.4' or not p.get('test_save_pause_on_ready_available'):
                raise RuntimeError('New game lacks copy pause capability')
            if p.get('world_ready'):
                if not p['paused'] or p['frame_speed_multiplier']!=0 or p['load_pause_pending']:
                    raise RuntimeError('First ready copy was not paused')
                data['first_ready']=row;data['identity']=identity(state['pid']);break
            await asyncio.sleep(.1)
        else:raise TimeoutError('New autoload did not become ready')
        data['stable_scenes']=[]
        for _ in range(4):
            scene=await c.call('get_scene_state',thread_details=True)
            if not scene['paused'] or scene['frame_speed_multiplier']!=0 or scene['free_camera'] or scene['battle']['active']:
                raise RuntimeError('Paused copy state changed')
            if scene['sdk_threads']['process_id']!=data['identity']['pid']:raise RuntimeError('SDK process differs')
            if data['stable_scenes'] and simulation_progress(data['stable_scenes'][0],scene)['game_hours']!=0:
                raise RuntimeError('Paused clock advanced')
            data['stable_scenes'].append(scene);await asyncio.sleep(1)
        if identity(data['identity']['pid'])!=data['identity']:raise RuntimeError('Game lifetime changed')
        if restart_task:
            data['restart_result']=await restart_task
            after=await read_runtime_state(state_path)
            if not after.get('restart_ack') or after['pid']!=data['identity']['pid'] or after['pid']==previous_pid:
                raise RuntimeError('Restart acknowledgement missing')
            candidates=[p for p in set(Path(cfg['crashes']).iterdir())-archives_before if p.is_dir() and
                (p/'reason.txt').is_file() and (p/'reason.txt').read_text()=='requested']
            if len(candidates)!=1 or not (candidates[0]/Path(cfg['log']).name).is_file():
                raise RuntimeError('Requested restart archive missing/ambiguous')
            data['restart_archive']=str(candidates[0]);data['restart_ack']=after['restart_ack']
        data['pause_observation_valid']=True
    except Exception as e:
        data['error']=dict(type=type(e).__name__,message=str(e))
        # Preserve the failed observation; best effort protects only the known copy.
        try:
            state=await read_runtime_state(state_path)
            if state.get('autoload_requested') and (await c.call('ping'))['plugin_version']=='0.8.4':
                data['fallback_pause']=await c.call('pause',paused=True)
        except Exception as cleanup:data['fallback_pause_error']=str(cleanup)
    finally:
        if restart_task and not restart_task.done():
            try:data['restart_result']=await restart_task
            except Exception as e:data['restart_error']=str(e)
        try:
            data['protected_files_unchanged']=protected()
            data['settings_unchanged']=settings.read_bytes()==settings_before
            data['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            data['watchdog']=await read_runtime_state(state_path)
            data['completed']=bool(data.get('pause_observation_valid') and not data.get('error') and
                data['protected_files_unchanged'] and data['settings_unchanged'])
        except Exception as e:data['verification_error']=str(e)
        publish()
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),
            first_ready_paused=data.get('first_ready',{}).get('ping',{}).get('paused'),identity=data.get('identity'),
            restart_archive=data.get('restart_archive'),protected_files_unchanged=data.get('protected_files_unchanged'))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--previous-pid',type=int);p.add_argument('--restart',action='store_true')
    args=p.parse_args()
    if not args.restart and args.previous_pid is None:p.error('Use --previous-pid before startup or --restart')
    os.chdir(ROOT);asyncio.run(run(observe,args.previous_pid,args.restart))
