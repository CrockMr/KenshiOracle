"""Audit the selected AI function and SDK roles over a pause/x1/pause scenario."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
from pathlib import Path
from analyze_pause_cpu import analyze as analyze_base
from sdk_thread_roles import join_cpu


def analyze(data):
    result=analyze_base(data)
    if not result['completed']:return result
    functions={p['ai_function'] for p in result['phases']}
    if len(functions)!=1 or None in functions:raise ValueError('AI function changed or probe unavailable')
    result['ai_function']=next(iter(functions))
    declared=data.get('initial_ping',{}).get('ai_profiled_function')
    if declared is not None and declared!=result['ai_function']:raise ValueError('Initial AI selection disagrees with measured function')
    first=data['phases'][0]['sdk_roles_before'];last=data['phases'][-1]['sdk_roles_after']
    for raw,phase in zip(data['phases'],result['phases']):
        if not first['frame']<=raw['scene_before']['frame']<=raw['scene_after']['frame']<=last['frame']:
            raise ValueError('SDK identities do not bracket the CPU phase')
        joined=join_cpu(first,last,raw['process_resources'],data['pid'])
        phase['sdk_role_cpu_join']=joined
        tail=phase['ai_function_tail'];matches=phase['ai_thread_cpu_identity_matches']
        if tail is None:raise ValueError('AI function probe unavailable')
        identities={}
        for role in joined['roles']:
            if role['status']=='matched':
                identities.setdefault((role['thread_id'],role['created_filetime']),[]).append(role['role'])
        phase['ai_function_threads']=[]
        for call in tail['threads']:
            key=(call['thread_id'],call.get('created_filetime'))
            cpu=next(r for r in matches['threads'] if (r['thread_id'],r['created_filetime'])==key)
            phase['ai_function_threads'].append(dict(thread_id=key[0],created_filetime=key[1],sdk_roles=identities.get(key,[]),
                calls=call['calls_total'],mean_inclusive_ms_per_frame=call['mean_ms'],max_inclusive_call_ms=call['max_call_ms'],
                measured_call_cpu_ms=(call['cpu_user_total_ms']+call['cpu_kernel_total_ms']) if tail['cpu_enabled'] else None,
                cpu_available_calls=call['cpu_available_calls'],cpu_unavailable_calls=call['cpu_unavailable_calls'],
                whole_thread_cpu=cpu))
    result['scope']='Completed outermost AI function calls, inclusive; function-tail and OS CPU windows differ. No exclusive coverage or optimization claim.'
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,default=None)
    args=p.parse_args();args.output=args.output or args.source.with_suffix('.ai-analysis.json');raw=args.source.read_bytes();report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),completed=report['result']['completed'],function=report['result'].get('ai_function'),ai_threads=[dict(label=r['label'],threads=r.get('ai_function_threads')) for r in report['result']['phases']])))


if __name__=='__main__':main()
