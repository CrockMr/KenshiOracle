"""Validate read-only paused MCP probes; differences across launches descriptive."""
import argparse,hashlib,json,math
from pathlib import Path
from command_service import summarize,validate
from benchmark import validate_camera_stability


def camera(reference,observed):
    try:validate_camera_stability(reference,observed)
    except RuntimeError as exc:raise ValueError(str(exc)) from exc


def analyze(data):
    if data['completed'] is not True or data.get('error') or data['transport']!='mcp-stdio' or data['version'] not in ('0.8.12','0.8.13'):raise ValueError('Incomplete paused copy probe')
    ping=data['initial_ping'];initial=data['source_reference'];final=data['final_scene']
    if ping['plugin_version']!=data['version'] or ping['system_hook_count']!=3 or not ping['command_service_timing_enabled']:raise ValueError('Native config differs')
    digest=data['installed_dll_sha256']
    if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid own DLL hash')
    for scene in (initial,final):
        if not scene['paused'] or scene['frame_speed_multiplier']!=0 or scene['battle']['active'] or scene['free_camera'] or scene['scene_camera_control_owned']:raise ValueError('Probe scene not restored and paused')
    if final['game_total_hours']!=initial['game_total_hours'] or final['frame']<initial['frame']:raise ValueError('Paused state progressed')
    camera(initial,final)
    if len(data['requests'])!=36:raise ValueError('Missing read-only requests')
    definitions=[('ping','ping',{}),('scene','get_scene_state',{}),('statistics_60','get_frame_stats',dict(n=60))]
    previous=0;keys=set()
    for index,row in enumerate(data['requests']):
        rep,offset=divmod(index,3);label,cmd,params=definitions[(rep+offset)%3]
        if (row['repetition'],row['label'],row['command'],row['params'])!=(rep,label,cmd,params):raise ValueError('Probe request order differs')
        result=row['result'];timing=validate(result,cmd);keys.add((timing['thread_id'],timing['created_filetime']))
        if timing['queued_qpc_ms']<previous or not initial['frame']<=timing['frame']<=final['frame']:raise ValueError('Request outside own phase')
        previous=timing['finished_qpc_ms']
        if row['compact_result_bytes']!=len(json.dumps(result,separators=(',',':')).encode()):raise ValueError('Response size differs')
        if cmd=='get_scene_state':
            if not result['paused'] or result['game_total_hours']!=initial['game_total_hours'] or result['battle']['active']:raise ValueError('Read scene changed')
            camera(initial,result)
        if cmd=='get_frame_stats' and (result['count']!=60 or not initial['frame']<result['first_frame']<=result['last_frame']<timing['frame'] or result['last_frame']-result['first_frame']+1!=60):raise ValueError('Statistics outside own paused phase')
    for snapshot in (data['thread_before'],data['thread_after']):
        known={(r['tid'],r.get('created_filetime')) for r in snapshot['threads'] if not r.get('error')}
        if not keys<=known:raise ValueError('Unverified native service identity')
    summary=summarize(data['requests'])
    if json.loads(json.dumps(summary))!=data['summary']:raise ValueError('Saved probe summary differs')
    return dict(version=data['version'],pid=data['pid'],created_at=data['created_at'],summary=summary,
        scope='12 rotating reads per command in one paused process, exact service thread creation verified at both endpoints; wall service/queue/MCP clocks separate.')


def compare(before,after):
    if (before['version'],after['version'])!=('0.8.12','0.8.13'):raise ValueError('Unexpected versions')
    a,b=analyze(before),analyze(after)
    if before['source_reference']['game_total_hours']!=after['source_reference']['game_total_hours']:raise ValueError('Different saved game hour')
    camera(before['source_reference'],after['source_reference'])
    differences={label:{key:b['summary'][label][key]['mean']-a['summary'][label][key]['mean'] for key in ('service_ms','queue_wait_ms','client_ms')} for label in a['summary']}
    return dict(before=a,after=b,after_minus_before_mean_ms=differences,
        scope='Different game process launches, recent frame payloads and ambient scheduling; descriptive means, no paired causal game/FPS or exclusive CPU claim. No cross-process TID join.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('before',type=Path);parser.add_argument('after',type=Path);parser.add_argument('--before-sha256',required=True);parser.add_argument('--after-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    inputs=[]
    for path,expected in [(args.before,args.before_sha256),(args.after,args.after_sha256)]:
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('Probe SHA256 mismatch')
        inputs.append(json.loads(raw))
    result=dict(before_source_sha256=args.before_sha256,after_source_sha256=args.after_sha256,result=compare(*inputs))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output))))
