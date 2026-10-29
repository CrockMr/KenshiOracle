"""Read-only native wire error/escaping checks after a serializer change."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,asyncio,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from probe import Client,config,read_runtime_state
from command_service import validate


async def main(version='0.8.12'):
    cfg=config();c=Client();state=await read_runtime_state(Path(cfg['runtime'])/'state.json');proc=psutil.Process(state['pid'])
    if Path(proc.exe()).resolve()!=Path(cfg['executable']).resolve() or proc.cmdline()!=[proc.exe(),'--norestart']:raise RuntimeError('Unexpected game process')
    initial=await c.call('get_scene_state')
    if not initial['paused'] or initial['battle']['active'] or initial['scene_camera_control_owned']:raise RuntimeError('Requires restored paused copy')
    cases=[('malformed',b'{\n',None,'truncated JSON'),
        ('duplicate',b'{"id":"a","id":"b","command":"ping","params":{}}\n',None,'duplicate key'),
        ('invalid_utf8',b'\xff\n',None,'invalid UTF-8'),
        ('unknown',json.dumps(dict(id='synthetic-\u00e9-\U0001f600-"-\\-\n',command='synthetic-unknown',params={})).encode()+b'\n','synthetic-\u00e9-\U0001f600-"-\\-\n','unknown command')]
    data=dict(pid=proc.pid,created_at=proc.create_time(),executable=proc.exe(),cmdline=proc.cmdline(),before=initial,rows=[],completed=False)
    try:
        for label,request,identifier,expected in cases:
            reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',cfg.get('port',47800),limit=65536),10)
            try:
                writer.write(request);await writer.drain();raw=await asyncio.wait_for(reader.readline(),10)
                reply=json.loads(raw);data['rows'].append(dict(label=label,request_hex=request.hex(),response_hex=raw.hex(),response=reply))
                if len(raw)>65536 or not raw.endswith(b'\n') or reply.get('id')!=identifier or reply.get('error')!={'code':'invalid_request','message':expected} or 'result' in reply:raise RuntimeError('Unexpected native error response')
            finally:writer.close();await writer.wait_closed()
        ping=await c.call('ping');validate(ping,'ping');data['ping_after']=ping
        if ping['plugin_version']!=version or ping['system_hook_count']!=3:raise RuntimeError('Unexpected native version/hooks')
        after=await c.call('get_scene_state');data['after']=after
        if not after['paused'] or after['game_total_hours']!=initial['game_total_hours'] or proc.create_time()!=data['created_at']:raise RuntimeError('Game state/process changed')
        data['completed']=True
    except Exception as exc:data['error']=str(exc)
    finally:
        prefix='json-serializer-0812' if version=='0.8.12' else 'json-ownership-0813'
        data['observed_at']=time.time();output=ROOT/('runtime/'+prefix+'-wire-'+str(time.time_ns())+'.json')
        with output.open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2)
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),cases=len(data['rows']))))
    if not data['completed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=['0.8.12','0.8.13'],default='0.8.12');args=parser.parse_args()
    os.chdir(ROOT);asyncio.run(main(args.version))
