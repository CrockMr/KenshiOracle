"""One external PSS instruction-pointer observation of a paused, identified test copy.

Selects the top three CPU lifetimes from an existing same-process phase capture.
No target mutation, VA clone, stack unwind, WPR or administrator token is requested.
"""
import argparse
import asyncio
import ctypes
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
from probe import config,read_runtime_state
from instruction_snapshot import WindowsInstructionSnapshot


async def pilot(source,client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    source=Path(source).resolve();raw=source.read_bytes();baseline=json.loads(raw)
    if baseline.get('completed') is not True:raise RuntimeError('Requires a completed CPU capture')
    phase=next(r for r in baseline['phases'] if r['label']=='running_x1' and r['completed'])
    before=phase['process_resources']['before'];created=before['created_at'];pid=baseline['pid']
    state=await read_runtime_state(Path(cfg['runtime'])/'state.json')
    if state['pid']!=pid:raise RuntimeError('CPU capture belongs to an older process')
    def identity():
        p=psutil.Process(pid)
        if p.create_time()!=created or Path(p.exe()).resolve()!=Path(cfg['executable']).resolve():
            raise RuntimeError('Game identity changed')
        return dict(pid=pid,created_at=p.create_time(),executable=p.exe(),cmdline=p.cmdline())
    selected=sorted(phase['process_resources']['thread_cpu']['threads'],key=lambda r:r['cpu_seconds'],reverse=True)[:3]
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():
        return all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items()) and manifest(snapshot_path)==snapshot['snapshot_manifest']
    if not protected():raise RuntimeError('Protected save differs before capture')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    scene=await c.call('get_scene_state')
    if not scene['paused'] or scene['frame_speed_multiplier']!=0 or scene['battle']['active']:raise RuntimeError('Requires paused test copy')
    data=dict(identity(),source=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),selected_lifetimes=selected,
        admin=bool(ctypes.windll.shell32.IsUserAnAdmin()),transport=c.transport,scene_before=scene,completed=False)
    output=ROOT/'runtime/scenarios'/('instruction-pilot-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    try:
        data['snapshot']=WindowsInstructionSnapshot().capture(pid,cfg['executable'],[(r['tid'],r['created_filetime']) for r in selected])
        if not data['snapshot'].get('completed') or not data['snapshot']['cleanup_verified']:
            raise RuntimeError('Snapshot capture or cleanup incomplete')
        if data['snapshot']['missing_requested_lifetimes']:raise RuntimeError('Requested thread lifetime unavailable')
        if data['snapshot']['process_created_filetime']!=str(int(created*10000000)+116444736000000000):
            # psutil float conversion can lose sub-microsecond bits: compare the
            # exact baseline thread snapshots' process FILETIME when available
            # separately; the durable OS process identity is rechecked below.
            data['process_filetime_float_roundtrip_exact']=False
        else:data['process_filetime_float_roundtrip_exact']=True
        if identity()!=dict(pid=data['pid'],created_at=data['created_at'],executable=data['executable'],cmdline=data['cmdline']):
            raise RuntimeError('Game identity changed after capture')
        data['capture_valid']=True
    except Exception as e:data['error']=dict(type=type(e).__name__,message=str(e))
    finally:
        data['scene_after']=await c.call('get_scene_state')
        data['simulation_progress']=simulation_progress(data['scene_before'],data['scene_after'])
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before
        data['watchdog']=await read_runtime_state(Path(cfg['runtime'])/'state.json')
        data['completed']=bool(data.get('capture_valid') and data['protected_files_unchanged'] and data['settings_unchanged'] and
            data['scene_after']['paused'] and data['simulation_progress']['game_hours']==0 and data['watchdog']['pid']==pid)
        output.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),admin=data['admin'],
            elapsed=data.get('snapshot',{}).get('elapsed_seconds'),cleanup=data.get('snapshot',{}).get('cleanup'),
            threads=[dict(tid=t['tid'],rip=t.get('rip'),module=t.get('module')) for t in data.get('snapshot',{}).get('threads',[])])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);args=p.parse_args()
    os.chdir(ROOT);asyncio.run(run(pilot,args.source))
