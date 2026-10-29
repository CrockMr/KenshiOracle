"""Replay the two paused-scene service experiment from a hashed raw capture."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json
from pathlib import Path
from command_service import summarize,validate
from benchmark import validate_camera_stability
from sdk_thread_roles import validate as roles


def analyze(data):
    if not data['completed'] or not data['measurement_valid'] or not data['protected_files_unchanged'] or not data['settings_unchanged']:
        raise ValueError('Incomplete or unrestored experiment')
    if data['transport']!='mcp-stdio' or data['repetitions']!=12:raise ValueError('Unexpected measurement plan')
    ping=data['initial_ping'];validate(ping,'ping')
    if ping['plugin_version']!='0.8.11' or ping['system_hook_count']!=3 or not ping['command_service_timing_enabled']:raise ValueError('Probe configuration differs')
    plan=[('copy_no_battle',0),('mongrel_40_paused',40)]
    if [(p['label'],p['actor_count']) for p in data['phases']]!=plan:raise ValueError('Unexpected phase plan')
    result=[];definitions=[('ping','ping',{}),('scene','get_scene_state',{}),('scene_roles','get_scene_state',dict(thread_details=True)),('statistics_60','get_frame_stats',dict(n=60))]
    for phase in data['phases']:
        a,b=phase['before'],phase['after'];count=phase['actor_count']
        if not phase['completed'] or a['game_total_hours']!=b['game_total_hours'] or b['frame']<a['frame']:raise ValueError('Paused phase invalid')
        for scene in (a,b):
            roles(scene,data['pid'])
            if scene['battle']['matched_loaded']!=count or len(scene['battle']['members'])!=count:raise ValueError('Incomplete phase cohort')
        validate_camera_stability(a,b)
        if len(phase['requests'])!=48:raise ValueError('Missing command reads')
        previous=0;keys=set();sizes={}
        for index,item in enumerate(phase['requests']):
            rep,offset=divmod(index,4);label,cmd,params=definitions[(rep+offset)%4]
            if (item['repetition'],item['label'],item['command'],item['params'])!=(rep,label,cmd,params):raise ValueError('Request order differs')
            value=item['result'];timing=validate(value,cmd)
            if timing['queued_qpc_ms']<previous or not a['frame']<=timing['frame']<=b['frame']:raise ValueError('Command outside own phase')
            previous=timing['finished_qpc_ms'];keys.add((timing['thread_id'],timing['created_filetime']))
            actual=len(json.dumps(value,separators=(',',':')).encode())
            if item['compact_result_bytes']!=actual:raise ValueError('Response size differs')
            sizes.setdefault(label,[]).append(actual)
            if cmd=='get_scene_state':
                if not value['paused'] or value['game_total_hours']!=a['game_total_hours'] or value['battle']['matched_loaded']!=count or len(value['battle']['members'])!=count:raise ValueError('Phase scene changed')
                validate_camera_stability(a,value)
            if cmd=='get_frame_stats' and value['count']!=60:raise ValueError('Statistics count differs')
        for snapshot in (phase['thread_before'],phase['thread_after']):
            known={(t['tid'],t.get('created_filetime')) for t in snapshot['threads'] if not t.get('error')}
            if not keys<=known:raise ValueError('Service identity not independently verified')
        summary=summarize(phase['requests'])
        if json.loads(json.dumps(summary))!=phase['summary']:raise ValueError('Saved phase summary differs')
        result.append(dict(label=phase['label'],actor_count=count,summary=summary,
            compact_result_bytes={k:dict(minimum=min(v),maximum=max(v)) for k,v in sizes.items()}))
    final=data['final_scene'];reference=data['source_reference']
    if not final['paused'] or final['frame_speed_multiplier']!=0 or final['battle']['active'] or final['free_camera'] or final['scene_camera_control_owned'] or final['game_total_hours']!=reference['game_total_hours']:raise ValueError('Restoration differs')
    validate_camera_stability(reference,final)
    return dict(phases=result,scope='Paused local scenes, 12 reads/command including first read, wall service/queue/MCP clocks separate; no exclusive CPU, transport attribution, combat p99 explanation or causal per-actor cost.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--expected-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw=args.input.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise SystemExit('Source SHA256 mismatch')
    out=dict(source=str(args.input),source_sha256=digest,result=analyze(json.loads(raw)))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=digest)))
