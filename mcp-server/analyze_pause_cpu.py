"""Audit a sequential pause/active/pause CPU observation, without causal labels."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from benchmark import simulation_progress,validate_camera_stability
from environment_diagnostics import summarize as environment_summary,compare as environment_compare
from physics_diagnostics import validate as validate_physics_diagnostics
from ai_diagnostics import validate as validate_ai,match_cpu as match_ai_cpu,function_name as ai_function_name
from function_diagnostics import validate as validate_function,match_cpu as match_function_cpu,function_name as selected_function_name


def validate_active_speed(speed):
    if isinstance(speed,bool) or not isinstance(speed,int) or speed not in (1,5):
        raise ValueError('Active speed must be integer 1 or 5')
    return speed


def bounded_tail_count(first_frame,observed_frame,maximum=600):
    if any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in (first_frame,observed_frame)):
        raise ValueError('Invalid scene frame bounds')
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=3600:
        raise ValueError('Invalid maximum tail count')
    # Leave the frame observed at phase entry outside the completed tail.
    available=observed_frame-first_frame-1
    if available<1:raise ValueError('No completed frames strictly after phase entry')
    return min(maximum,available)


def validate_phase_state(reference,scene,paused,speed=1):
    validate_active_speed(speed)
    validate_camera_stability(reference,scene)
    if scene['paused'] is not paused or scene['frame_speed_multiplier']!=(0 if paused else speed):
        raise ValueError('Phase pause/speed disagrees with requested state')


def summarize_phase(row,pid):
    result=dict(label=row['label'],completed=row.get('completed',False))
    if not result['completed']: return result
    paused=row['expected_paused'];before,after=row['scene_before'],row['scene_after']
    speed=validate_active_speed(row.get('active_speed',1))
    for scene in [before,after]+[x['scene'] for x in row['observations']]:
        validate_phase_state(before,scene,paused,speed)
    progress=simulation_progress(before,after)
    if progress is None or (paused and progress['game_hours']>1e-7) or (not paused and progress['game_hours']<=0):
        raise ValueError('Phase simulation clock disagrees with requested state')
    if row['simulation_progress']!=progress:
        raise ValueError('Cached simulation progress disagrees with raw scenes')
    resources=row['process_resources'];wall=resources['elapsed_seconds']
    if resources['pid']!=pid or resources['before']['created_at']!=resources['after']['created_at']:
        raise ValueError('Phase process identity changed')
    counters=[resources['user_seconds'],resources['system_seconds']]
    if not math.isfinite(wall) or wall<=0 or any(not math.isfinite(x) or x<0 for x in counters):
        raise ValueError('Invalid phase CPU interval')
    cpu=sum(counters);threads=resources['thread_cpu']
    groups=threads['accounting_group_cpu_seconds']
    if any(not math.isfinite(x) or x<0 for x in groups.values()):
        raise ValueError('Invalid thread accounting group')
    env_a,env_b=(environment_summary(row[k]) for k in ('environment_before','environment_after'))
    stats=row['statistics_tail'];roles_a,roles_b=row['roles_before'],row['roles_after']
    selection=row.get('statistics_tail_selection')
    if selection is not None:
        if not env_a['complete'] or not env_b['complete']:raise ValueError('Adaptive campaign inventory incomplete')
        for environment in (row['environment_before'],row['environment_after']):
            for scene in (environment['scene_before'],environment['scene_after']):
                validate_phase_state(before,scene,paused,speed)
        if selection['policy']!='bounded_since_phase_start':raise ValueError('Unknown tail selection policy')
        observed=selection['observed_scene']
        validate_phase_state(before,observed,paused,speed)
        if not before['frame']<=observed['frame']<=after['frame']:raise ValueError('Tail selection scene outside phase')
        requested=bounded_tail_count(before['frame'],observed['frame'],selection['maximum'])
        if requested!=selection['requested_count'] or stats['count']!=requested:
            raise ValueError('Adaptive tail count disagrees with observed frames')
        if not (before['frame']<stats['first_frame']<=stats['last_frame']<=after['frame'] and
                stats['last_frame']-stats['first_frame']+1==requested):
            raise ValueError('Adaptive tail outside phase or noncontiguous')
    retained=[x for x in row['thread_attribution_statistics']['navmesh_slow_calls']
              if roles_a['frame']<=x['completion_frame']<=roles_b['frame']]
    scenes=[before,after]+[x['scene'] for x in row['observations']]
    physics=validate_physics_diagnostics(stats)
    ai=validate_ai(stats)
    ai_name=ai_function_name(stats)
    selected=validate_function(stats);selected_name=selected_function_name(stats)
    physics_matches=[]
    if physics is not None:
        cpu_threads={(r['tid'],r['created_filetime']):r for r in threads['threads']}
        for r in physics['threads']:
            matched=cpu_threads.get((r['thread_id'],r.get('created_filetime')))
            physics_matches.append(dict(thread_id=r['thread_id'],created_filetime=r.get('created_filetime'),
                matched_cpu_identity=matched is not None,
                whole_thread_cpu_seconds=matched['cpu_seconds'] if matched else None,
                whole_thread_logical_cpu_equivalents=matched['cpu_seconds']/wall if matched else None))
    result.update(expected_paused=paused,created_at=resources['before']['created_at'],executable=resources['executable'],
        process_cpu_seconds=cpu,cpu_elapsed_seconds=wall,logical_cpu_equivalents=cpu/wall,
        simulation_progress=progress,group_cpu_seconds=groups,
        group_logical_cpu_equivalents={k:v/wall for k,v in groups.items()},
        matched_threads=len(threads['threads']),omitted_reasons=threads['omitted_reasons'],
        residual_cpu_seconds=threads['residual_cpu_seconds'],
        endpoint_collection_ms={k:resources[k]['thread_snapshot']['collection_seconds']*1000 for k in ('before','after')},
        top_threads=threads['threads'][:5],role_evidence=threads['role_evidence'],
        population_range=[min(s['loaded_character_count'] for s in scenes),max(s['loaded_character_count'] for s in scenes)],
        inventory_complete_at_bounds=[env_a['complete'],env_b['complete']],environment_comparison=environment_compare(env_a,env_b),
        retained_navigation_calls_in_cpu_frame_bounds=len(retained),
        context_retention_truncated=row['thread_attribution_statistics']['navmesh_slow_calls_retention_truncated'],
        tail=dict(first_frame=stats['first_frame'],last_frame=stats['last_frame'],count=stats['count'],
            mean_frame_ms=stats['mean_ms'],p99_frame_ms=stats['p99_ms'],
            navigation_calls=stats['systems']['navmesh_findPath_calls_total'],
            inside_scene_bounds=before['frame']<=stats['first_frame']<=stats['last_frame']<=row['environment_after']['scene_after']['frame'],
            ends_after_cpu_heartbeat=stats['last_frame']>roles_b['frame']),
        physics_tail=physics,physics_thread_cpu_identity_matches=physics_matches,
        profiled_function=selected_name,profiled_function_tail=selected,
        function_thread_cpu_identity_matches=match_function_cpu(selected,resources),
        ai_function=ai_name,ai_function_tail=ai,ai_periodic_tail=ai if ai_name=='AI::periodicUpdate' else None,
        ai_thread_cpu_identity_matches=match_ai_cpu(ai,resources))
    if 'active_speed' in row:result['active_speed']=speed
    if selection is not None:result['tail']['selection']=selection
    return result


def common_threads(rows):
    maps=[]
    for row in rows:
        threads=row['process_resources']['thread_cpu']['threads']
        mapped={(x['tid'],x['created_filetime']):x for x in threads}
        if len(mapped)!=len(threads): raise ValueError('Duplicate thread lifetime in one phase')
        maps.append(mapped)
    identities=set.intersection(*(set(m) for m in maps)) if maps else set()
    result=[]
    for identity in identities:
        samples=[m[identity] for m in maps]
        result.append(dict(tid=identity[0],created_filetime=identity[1],
            observed_roles_union=sorted({role for sample in samples for role in sample.get('observed_roles',[])}),
            logical_cpu_equivalents_by_phase={row['label']:sample['cpu_seconds']/row['process_resources']['elapsed_seconds']
                                            for row,sample in zip(rows,samples)}))
    # A set intersection has hash-dependent iteration order. Quantized equal
    # CPU maxima need a lifetime tie-breaker, including at the top-12 boundary.
    result.sort(key=lambda x:(-max(x['logical_cpu_equivalents_by_phase'].values()),x['tid'],x['created_filetime']))
    return dict(common_thread_count=len(result),top_threads=result[:12],
        scope='Same TID and creation FILETIME across completed phases; whole-thread CPU divided by enclosing process interval. Role union does not establish exclusive work.')


def analyze(data):
    speed=validate_active_speed(data.get('active_speed',1))
    if any(row.get('active_speed',1)!=speed for row in data['phases']):
        raise ValueError('Active speed differs across phases or campaign')
    phases=[summarize_phase(row,data['pid']) for row in data['phases']]
    completed=[x for x in phases if x['completed']]
    if len({(x['created_at'],x['executable']) for x in completed})>1:
        raise ValueError('Game lifetime or executable changed across phases')
    contrast=None
    if len(completed)==3:
        if [x['label'] for x in completed]!=['paused_before','running_x'+str(speed),'paused_after']:
            raise ValueError('Unexpected phase order')
        a,b,c=[x['logical_cpu_equivalents'] for x in completed]
        contrast=dict(running_minus_mean_paused_logical_cpus=b-(a+c)/2,
            paused_after_minus_before_logical_cpus=c-a,
            mean_paused_fraction_of_running=(a+c)/2/b if b else None,
            scope='Descriptive sequential contrast; not exclusive simulation, render, navigation or optimization cost.')
    return dict(pid=data['pid'],completed=data.get('completed',False),error=data.get('error'),phases=phases,
        contrast=contrast,common_threads=common_threads([row for row in data['phases'] if row.get('completed')]),
        restored=bool(data.get('restored')) and not data.get('restoration_error'),
        source_and_copy_unchanged=data.get('source_and_copy_unchanged'),settings_unchanged=data.get('settings_unchanged'),
        limits=data.get('limits',[]))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,default=Path('runtime/pause-cpu-analysis.json'))
    args=p.parse_args();raw=args.source.read_bytes()
    report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),completed=report['result']['completed'],contrast=report['result']['contrast']),ensure_ascii=False))
