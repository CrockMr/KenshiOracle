"""Retained slow-navigation observations, frame quartiles and separate CPU windows."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
from analyze_profiled_function import analyze as profile_analysis
from benchmark import validate_nav_diagnostics
from statistics_detail import validate as detail_mode
from thread_resources import thread_deltas

SOURCES=('statistics_tail','thread_attribution_statistics')


def number(v,label):
    if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid '+label)
    return v


def count(v,label):
    if type(v) is not int or not 0<=v<=2**53:raise ValueError('Invalid '+label)
    return v


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)


def resources(row,pid):
    r=row['process_resources'];a,b=r['before'],r['after']
    created=number(a['created_at'],'process creation')
    if not created or r['pid']!=pid or b['created_at']!=created:raise ValueError('CPU process lifetime differs')
    wall=number(b['monotonic_seconds']-a['monotonic_seconds'],'CPU elapsed')
    user=number(b['user_seconds']-a['user_seconds'],'CPU user delta');kernel=number(b['system_seconds']-a['system_seconds'],'CPU kernel delta')
    if wall<=0:raise ValueError('Empty CPU window')
    for observed,expected in [(r['elapsed_seconds'],wall),(r['user_seconds'],user),(r['system_seconds'],kernel)]:
        if not math.isclose(number(observed,'cached CPU delta'),expected,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Cached CPU counters differ')
    actual=thread_deltas(a['thread_snapshot'],b['thread_snapshot'],wall,user+kernel);saved=r['thread_cpu']
    for key in ('omitted','omitted_reasons','covered_cpu_seconds','residual_cpu_seconds'):
        if actual[key]!=saved[key]:raise ValueError('Cached CPU accounting differs')
    indexed={(t['tid'],t['created_filetime']):t for t in saved['threads']}
    if len(indexed)!=len(saved['threads']) or len(indexed)!=len(actual['threads']):raise ValueError('CPU identity inventory differs')
    for t in actual['threads']:
        cached=indexed.get((t['tid'],t['created_filetime']))
        if cached is None or any(cached.get(k)!=v for k,v in t.items()):raise ValueError('Cached CPU thread differs')
    return dict(pid=pid,created_at=created,executable=r['executable']),actual


def validate_source(stats):
    if detail_mode(stats)!='full':raise ValueError('Navigation timeline requires individual details; aggregates are unavailable, not zero calls')
    n=count(stats['count'],'statistics count');first=count(stats['first_frame'],'first frame');last=count(stats['last_frame'],'last frame')
    if not 1<=n<=3600 or last-first+1!=n:raise ValueError('Noncontiguous statistics window')
    validate_nav_diagnostics(stats)
    if stats['systems'].get('navmesh_findPath_threads') is None:raise ValueError('Navigation thread aggregate unavailable')
    calls=stats.get('navmesh_slow_calls')
    if not isinstance(calls,list):raise ValueError('Slow-call detail unavailable')
    total=count(stats['navmesh_slow_calls_total'],'slow total');capacity=count(stats['navmesh_slow_calls_capacity'],'slow capacity')
    aggregate=count(stats['systems']['navmesh_findPath_calls_total'],'all navigation calls')
    if total>aggregate or not capacity or len(calls)>min(total,capacity):raise ValueError('Slow retention contradicts aggregate')
    truncated=stats['navmesh_slow_calls_retention_truncated']
    if type(truncated) is not bool or truncated!=(len(calls)<total):raise ValueError('Slow-call truncation differs')
    return dict(first_frame=first,last_frame=last,retained_frames=n,all_navigation_calls=aggregate,
                slow_calls_total=total,slow_rows_retained=len(calls),slow_rows_capacity=capacity,
                slow_retention_truncated=truncated,individual_detail_available=True)


def validate_call(call):
    count(call['start_frame'],'start frame');count(call['completion_frame'],'completion frame')
    tid=count(call['thread_id'],'thread ID')
    if not 0<tid<=0xffffffff:raise ValueError('Invalid navigation thread ID')
    start=number(call['started_qpc_ms'],'start QPC');elapsed=number(call['elapsed_ms'],'call wall')
    if not elapsed or not math.isfinite(start+elapsed):raise ValueError('Invalid reconstructed call end')
    for key in ('start_vector','goal_vector'):
        vector=call[key]
        if not isinstance(vector,list) or len(vector)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):
            raise ValueError('Navigation vector unavailable')
    for key in ('radius','water'):number(call[key],key)
    for key in ('hierarchical','result'):
        if type(call[key]) is not bool:raise ValueError('Invalid navigation bool')
    for key in ('output_size_before','output_size_after','start_key','goal_key'):count(call[key],key)
    return start+elapsed


def argument_projection(call):
    return dict(start_xyz=call['start_vector'][:3],goal_xyz=call['goal_vector'][:3],radius=call['radius'],
                water=call['water'],hierarchical=call['hierarchical'],output_size_before=call['output_size_before'])


def analyze(data):
    if (data.get('completed') is not True or any(data.get(k) for k in ('error','restoration_error','camera_release_error')) or
            not data.get('restored') or data.get('source_and_copy_unchanged') is not True or data.get('settings_unchanged') is not True):
        raise ValueError('Incomplete or unrestored navigation campaign')
    p=data['initial_ping']
    if p.get('plugin_version') not in ('0.8.9','0.8.10') or p.get('system_hook_count')!=3 or p.get('navmesh_profiling') is not True:
        raise ValueError('Unexpected historical navigation build/configuration')
    for row in data['phases']:
        for name in SOURCES:
            if detail_mode(row[name])!='full':raise ValueError('Navigation timeline requires individual details; aggregate mode is unavailable')
    profile=profile_analysis(data)
    if not profile['completed'] or len(profile['phases'])!=3 or not all(r['completed'] for r in profile['phases']):raise ValueError('Incomplete phase audit')
    registry={};phase_records=[];process=None
    for row in data['phases']:
        identity,cpu=resources(row,data['pid'])
        normalized=(identity['pid'],identity['created_at'],PureWindowsPath(identity['executable']).as_posix().casefold())
        if process is not None and normalized!=process:raise ValueError('Process identity changes across navigation phases')
        process=normalized;source_reports={};keys=set()
        for name in SOURCES:
            stats=row[name];source_reports[name]=validate_source(stats);seen=set()
            for index,call in enumerate(stats['navmesh_slow_calls']):
                finish=validate_call(call);key=(identity['pid'],identity['created_at'],call['thread_id'],call['started_qpc_ms'])
                if key in seen:raise ValueError('Duplicate call identity within one detail source')
                seen.add(key);keys.add(key)
                if key in registry and registry[key]['native_call']!=call:raise ValueError('Conflicting repeated navigation call')
                if key not in registry:
                    registry[key]=dict(key=list(key),native_call=dict(call),finished_qpc_ms_reconstructed=finish,
                        argument_projection=argument_projection(call),provenances=[])
                registry[key]['provenances'].append(dict(phase=row['label'],source=name,row=index))
        phase_records.append((row,identity,cpu,source_reports,keys))
    ordered=sorted(registry,key=lambda k:(k[0],k[1],k[3],k[2]));indices={k:i for i,k in enumerate(ordered)}
    calls=[]
    for k in ordered:
        item=registry[k];item['provenances'].sort(key=lambda x:(x['phase'],x['source'],x['row']));calls.append(dict(id=indices[k],**item))
    phases=[]
    for row,identity,cpu,sources,keys in phase_records:
        tail=sources['statistics_tail'];first,last,n=tail['first_frame'],tail['last_frame'],tail['retained_frames']
        bins=[dict(quartile=q+1,first_frame=first+(q*n+3)//4,last_frame=first+((q+1)*n+3)//4-1,call_ids=[],false_results=0) for q in range(4)]
        outside=[];selected=[];joins=[];cpu_by_tid={t['tid']:t for t in cpu['threads']}
        for key in sorted(keys,key=lambda k:indices[k]):
            call=registry[key]['native_call'];index=indices[key];frame=call['completion_frame'];matched=cpu_by_tid.get(call['thread_id'])
            if first<=frame<=last:
                bucket=bins[min(3,(frame-first)*4//n)];bucket['call_ids'].append(index);bucket['false_results']+=int(not call['result']);selected.append(index)
            else:outside.append(index)
            joins.append(dict(call_id=index,thread_id=call['thread_id'],call_thread_creation_available=False,
                os_endpoint_candidate_status='same_tid_stable_os_endpoints' if matched else 'no_stable_os_candidate',
                candidate_created_filetime=matched['created_filetime'] if matched else None,
                whole_thread_cpu_seconds=matched['cpu_seconds'] if matched else None,
                completion_in_cpu_heartbeat_frame_bounds=row['roles_before']['frame']<=frame<=row['roles_after']['frame'],
                scope='Candidate by TID in the same process with stable creation at both OS endpoints. The call has no creation FILETIME: this is not an exact call-to-lifetime attribution or exclusive CPU.'))
        groups={}
        for index in selected:
            item=calls[index];signature=canonical(item['argument_projection']);groups.setdefault(signature,[]).append(index)
        projected=[dict(arguments=json.loads(k),call_ids=v,count=len(v)) for k,v in sorted(groups.items())]
        start=min((calls[i]['native_call']['started_qpc_ms'] for i in selected),default=None)
        finish=max((calls[i]['finished_qpc_ms_reconstructed'] for i in selected),default=None)
        r=row['process_resources'];a,b=r['before'],r['after']
        phases.append(dict(label=row['label'],scene_bounds=dict(first_frame=row['scene_before']['frame'],last_frame=row['scene_after']['frame'],
            before_observed_qpc_ms=row['scene_before']['observed_qpc_ms'],after_observed_qpc_ms=row['scene_after']['observed_qpc_ms']),
            os_cpu_bounds=dict(start_monotonic_seconds=a['monotonic_seconds'],end_monotonic_seconds=b['monotonic_seconds'],
                elapsed_seconds=r['elapsed_seconds'],process_cpu_seconds=r['user_seconds']+r['system_seconds'],
                omitted=cpu['omitted'],residual_cpu_seconds=cpu['residual_cpu_seconds']),sources=sources,
            unique_retained_call_ids=sorted(indices[k] for k in keys),quartiles_of_tail_frames=bins,
            retained_calls_with_completion_in_tail=len(selected),retained_call_ids_outside_tail=outside,
            retained_qpc_envelope=dict(first_start_qpc_ms=start,last_finish_qpc_ms_reconstructed=finish,
                span_ms=finish-start if start is not None else None,
                scope='Envelope of the retained unique calls completing inside tail frames, on native QPC milliseconds. End=start+elapsed; not summed CPU, not all navigation activity, and not a conversion from OS monotonic time.'),
            exact_xyz_parameter_groups=projected,repeated_xyz_parameter_groups=[x for x in projected if x['count']>1],cpu_thread_candidates=joins))
    return dict(schema_version=1,plugin_version=p['plugin_version'],profiled_function=profile['profiled_function'],process_identity=identity,
        completed=True,phase_count=len(phases),unique_retained_call_count=len(calls),calls=calls,phases=phases,
        scope='Retained slow navigation calls only. Tail and context overlap: unique calls are deduplicated, never summed as independent windows. Quartiles divide retained FRAME indices, not time or CPU. Exact XYZ/known parameters are descriptive groups, not cache keys or proof of equivalent routing state. The fourth vector component and all native arguments remain in each call. Missing detail is unavailable, never zero activity. No causal version comparison, exclusive attribution or optimization gain.',
        clock_scope='Native call start and elapsed use QPC milliseconds; reconstructed ends and retained envelopes stay on that clock. Scene QPC anchors are reported separately without relative offsets; OS monotonic timestamps are not converted.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();raw=args.source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=args.expected_sha256:raise ValueError('Navigation capture SHA differs')
    report=dict(source=str(args.source),source_sha256=sha,result=analyze(json.loads(raw)))
    with args.output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=sha,unique_retained_calls=report['result']['unique_retained_call_count'])))


if __name__=='__main__':main()
