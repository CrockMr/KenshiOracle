"""Coarse GetThreadTimes counters surrounding Root calls; never per-frame precision."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json,math
from pathlib import Path
from analyze_root_frame import analyze as root_analysis

def analyze(data):
    if data.get('expected_function_cpu_enabled') is not True:raise ValueError('CPU-on cohort must declare its measurement mode')
    result=root_analysis(data,expected_cpu=True);cost=data['initial_ping'].get('function_thread_cpu_startup_read_mean_us')
    if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<=0:raise ValueError('CPU read cost unavailable')
    for row in result['phases']:
        f=row['selected_function']
        if f['cpu_available_calls']!=f['calls_total'] or f['cpu_unavailable_calls']!=0:raise ValueError('Root CPU counter coverage incomplete')
        total=f['cpu_user_total_ms']+f['cpu_kernel_total_ms']
        row['root_cpu_counter_total_ms']=total;row['root_cpu_counter_mean_ms_per_retained_frame']=total/row['statistics_count']
    result['cpu_startup_read_mean_us']=cost
    result['cpu_counter_scope']='GetThreadTimes deltas surround original Root plus intervening measurement code; inclusive callbacks/probes/waits. Counter unit100ns is not precision. Individual zeros or deltas greater than call wall can reflect quantification; retain without clamping. Aggregates remain distinct from wider OS CPU and are not exclusive engine/GPU costs or an A/B gain.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.input.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=args.expected_sha256:raise ValueError('Capture SHA differs')
    with args.output.open('x',encoding='utf-8') as stream:json.dump(dict(source_sha256=sha,result=analyze(json.loads(raw))),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=sha)))
