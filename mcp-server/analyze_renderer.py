"""Renderer original selected through its existing service hook; wall != CPU."""
import argparse,hashlib,json
from pathlib import Path
from analyze_chars_split import analyze as analyze_city
from function_diagnostics import validate as function,match_cpu

NAME='Renderer::update'


def analyze(data):
    result=analyze_city(data,expected_version='0.8.17');ping=data['initial_ping']
    if (ping.get('profiled_function')!=NAME or ping.get('function_hook_reuses_service') is not True or ping.get('renderer_update_profiling') is not True or ping.get('main_loop_gpu_sensitive_profiling') is not False or
        ping.get('dedicated_system_hook_count')!=2 or ping.get('service_hook_count')!=2 or ping.get('installed_hook_count')!=4 or ping.get('havok_character_update_profiling') is not False or ping.get('function_thread_cpu_enabled') is not False):raise ValueError('Renderer hook reuse/counts/CPU not explicit')
    for summary,row in zip(result['phases'],data['phases']):
        total=function(row['statistics'])
        if total is None or total['function']!=NAME or total['cpu_enabled']:raise ValueError('Selected renderer wall data unavailable')
        summary['selected_function']=total;summary['selected_function_cpu_identity_matches']=match_cpu(total,row['process_resources'])
    result['scope']='Original renderer-update calls through the existing service hook; leading heartbeat/pause/command/load-state service excluded, internal callbacks and other nested work included. Inclusive wall, not GPU or exclusive CPU. Three profiled boundaries, two dedicated system detours plus two service detours; Havok absent. CPU and bucket windows differ; no frame subtraction or causal phase comparison.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.input.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise SystemExit('Source SHA256 mismatch')
    out=dict(source_sha256=digest,result=analyze(json.loads(raw)))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=digest)))
