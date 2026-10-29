"""Read-only MCP timing before/after ownership changes; no save or scene mutation."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,asyncio,hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from command_service import summarize,validate
from live_mcp_battle import run
from probe import config,read_runtime_state
from thread_resources import WindowsThreadSampler
from benchmark import validate_camera_stability


async def main(version,client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    state=await read_runtime_state(Path(cfg['runtime'])/'state.json');proc=psutil.Process(state['pid']);created=proc.create_time();exe=proc.exe();cmdline=proc.cmdline()
    def identity():
        p=psutil.Process(proc.pid)
        if p.create_time()!=created or p.exe()!=exe or p.cmdline()!=cmdline or Path(exe).resolve()!=Path(cfg['executable']).resolve() or cmdline!=[exe,'--norestart']:raise RuntimeError('Game identity changed')
    identity();ping=await c.call('ping');initial=await c.call('get_scene_state')
    if ping['plugin_version']!=version or ping['system_hook_count']!=3 or not ping['command_service_timing_enabled']:raise RuntimeError('Probe/version differs')
    if not initial['paused'] or initial['frame_speed_multiplier']!=0 or initial['battle']['active'] or initial['free_camera'] or initial['scene_camera_control_owned']:raise RuntimeError('Requires restored paused copy')
    symbol_path=ROOT/'runtime/symbols'/version/'manifest.json';symbols=json.loads(symbol_path.read_text(encoding='utf-8'))
    dll_sha=hashlib.sha256((ROOT/'Re_Kenshi/mods/KenshiProbe/KenshiProbe.dll').read_bytes()).hexdigest()
    if dll_sha!=symbols['files']['KenshiProbe.dll']['sha256']:raise RuntimeError('Own installed DLL differs')
    output=ROOT/'runtime/json-copy-probe'/(version+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json');output.parent.mkdir(exist_ok=True)
    data=dict(version=version,pid=proc.pid,created_at=created,executable=exe,cmdline=cmdline,transport=c.transport,
        installed_dll_sha256=dll_sha,initial_ping=ping,source_reference=initial,requests=[],completed=False)
    try:
        # Admit only tails newer than the initial paused snapshot; warmup retained separately.
        data['warmup']=[];deadline=time.monotonic()+10
        while True:
            await asyncio.sleep(.5);warm=await c.call('get_frame_stats',n=60,detail='full');data['warmup'].append(warm)
            if warm['count']==60 and warm['first_frame']>initial['frame']:break
            if time.monotonic()>=deadline:raise RuntimeError('No own 60-frame paused tail')
        data['thread_before']=WindowsThreadSampler(proc.pid)()
        definitions=[('ping','ping',{}),('scene','get_scene_state',{}),('statistics_60','get_frame_stats',dict(n=60,detail='full'))]
        for rep in range(12):
            identity()
            for offset in range(3):
                label,command,params=definitions[(rep+offset)%3];started=time.perf_counter();result=await c.call(command,**params);wall=(time.perf_counter()-started)*1000
                data['requests'].append(dict(repetition=rep,label=label,command=command,params=params,client_ms=wall,
                    compact_result_bytes=len(json.dumps(result,separators=(',',':')).encode()),result=result))
                timing=validate(result,command)
                if timing['menu_service'] and command!='ping':raise RuntimeError('Unexpected Renderer command')
                if command=='get_scene_state':
                    if not result['paused'] or result['game_total_hours']!=initial['game_total_hours'] or result['battle']['active']:raise RuntimeError('Paused scene changed')
                    validate_camera_stability(initial,result)
                if command=='get_frame_stats' and (result['count']!=60 or result['first_frame']<=initial['frame']):raise RuntimeError('Statistics outside own paused phase')
                await asyncio.sleep(.1)
        data['thread_after']=WindowsThreadSampler(proc.pid)();data['final_scene']=await c.call('get_scene_state')
        final=data['final_scene'];identity();validate_camera_stability(initial,final)
        if not final['paused'] or final['game_total_hours']!=initial['game_total_hours'] or final['scene_camera_control_owned'] or final['battle']['active']:raise RuntimeError('Final paused state differs')
        keys={(r['result']['_probe_service']['thread_id'],r['result']['_probe_service']['created_filetime']) for r in data['requests']}
        for sample in (data['thread_before'],data['thread_after']):
            known={(t['tid'],t.get('created_filetime')) for t in sample['threads'] if not t.get('error')}
            if not keys<=known:raise RuntimeError('Service identity not verified at both endpoints')
        data['summary']=summarize(data['requests']);data['completed']=True
    except Exception as exc:data['error']=dict(type=type(exc).__name__,message=str(exc))
    finally:
        data['observed_at']=time.time()
        with output.open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2)
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),summary=data.get('summary'))),flush=True)
    if not data['completed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',required=True,choices=['0.8.12','0.8.13']);args=parser.parse_args()
    os.chdir(ROOT);asyncio.run(run(main,args.version))
