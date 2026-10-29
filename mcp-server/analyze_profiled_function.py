"""Audit the selected function and SDK roles over a pause/active/pause scenario."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_pause_cpu import analyze as analyze_base
from sdk_thread_roles import join_cpu


def analyze(data):
    result=analyze_base(data)
    if not result['completed']:return result
    functions={p['profiled_function'] for p in result['phases']}
    if len(functions)!=1 or None in functions:raise ValueError('Selected function changed or probe unavailable')
    result['profiled_function']=next(iter(functions))
    declared=data.get('initial_ping',{}).get('profiled_function',data.get('initial_ping',{}).get('ai_profiled_function'))
    if declared is not None and declared!=result['profiled_function']:raise ValueError('Initial function selection disagrees with measured function')
    first=data['phases'][0]['sdk_roles_before'];last=data['phases'][-1]['sdk_roles_after']
    for raw,phase in zip(data['phases'],result['phases']):
        if not first['frame']<=raw['scene_before']['frame']<=raw['scene_after']['frame']<=last['frame']:
            raise ValueError('SDK identities do not bracket the CPU phase')
        joined=join_cpu(first,last,raw['process_resources'],data['pid'])
        phase['sdk_role_cpu_join']=joined
        tail=phase['profiled_function_tail'];matches=phase['function_thread_cpu_identity_matches']
        if tail is None:raise ValueError('Selected function probe unavailable')
        identities={}
        for role in joined['roles']:
            if role['status']=='matched':
                identities.setdefault((role['thread_id'],role['created_filetime']),[]).append(role['role'])
        phase['function_threads']=[]
        observed={(r['tid'],r['created_filetime']):r.get('observed_roles',[]) for r in raw['process_resources']['thread_cpu']['threads']}
        for call in tail['threads']:
            key=(call['thread_id'],call.get('created_filetime'))
            cpu=next(r for r in matches['threads'] if (r['thread_id'],r['created_filetime'])==key)
            phase['function_threads'].append(dict(thread_id=key[0],created_filetime=key[1],sdk_roles=identities.get(key,[]),
                observed_thread_roles=observed.get(key,[]) if cpu['matched_cpu_identity'] else [],
                calls=call['calls_total'],mean_inclusive_ms_per_frame=call['mean_ms'],max_inclusive_call_ms=call['max_call_ms'],
                measured_call_cpu_ms=(call['cpu_user_total_ms']+call['cpu_kernel_total_ms']) if tail['cpu_enabled'] else None,
                cpu_available_calls=call['cpu_available_calls'],cpu_unavailable_calls=call['cpu_unavailable_calls'],
                whole_thread_cpu=cpu))
    result['scope']='Completed outermost selected function calls, inclusive; function-tail and OS CPU windows differ. No exclusive coverage or optimization claim.'
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,default=None)
    args=p.parse_args();args.output=args.output or args.source.with_suffix('.function-analysis.json');raw=args.source.read_bytes();report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),completed=report['result']['completed'],function=report['result'].get('profiled_function'),function_threads=[dict(label=r['label'],threads=r.get('function_threads')) for r in report['result']['phases']])))


if __name__=='__main__':main()
