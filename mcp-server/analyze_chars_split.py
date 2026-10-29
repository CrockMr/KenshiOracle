"""Replay disjoint chars wall intervals; OS CPU remains a separate wider window."""
import argparse,hashlib,json,math
from pathlib import Path
from chars_diagnostics import validate as chars
from analyze_pause_cpu import validate_phase_state,bounded_tail_count
from benchmark import simulation_progress,validate_camera_stability
from environment_diagnostics import summarize as environment
from sdk_thread_roles import validate as sdk_roles
from statistics_budget import validate_plan
from thread_resources import thread_deltas


def analyze(data,expected_version='0.8.15'):
    if data['completed'] is not True or any(data.get(k) for k in ('error','restoration_error','camera_release_error')) or data['protected_files_unchanged'] is not True or data['settings_unchanged'] is not True:raise ValueError('Incomplete or unrestored chars campaign')
    ping=data['initial_ping']
    if ping['plugin_version']!=expected_version or ping['system_hook_count']!=3 or not ping['chars_update_split_profiling'] or ping['chars_update_bucket_bytes']!=696 or ping['telemetry_sample_bytes']!=696 or ping['chars_update_history_bytes']!=2523600:raise ValueError('Native chars config differs')
    if data['transport']!='mcp-stdio' or data['active_speed']!=5 or data['seconds_requested']!=12:raise ValueError('Campaign plan differs')
    plan=[('paused_before',True),('running_x5',False),('paused_after',True)]
    if [(r['label'],r['expected_paused']) for r in data['phases']]!=plan:raise ValueError('Phase order differs')
    a,b=sdk_roles(data['sdk_roles_before'],data['pid']),sdk_roles(data['sdk_roles_after'],data['pid']);results=[]
    for row in data['phases']:
        if row['completed'] is not True:raise ValueError('Incomplete phase')
        before,after=row['scene_before'],row['scene_after'];paused=row['expected_paused']
        scenes=[before,after,row['selection_scene']]+[x['scene'] for x in row['observations']]
        if not row['observations'] or row['observations'][-1]['elapsed']<12:raise ValueError('Short phase')
        for scene in scenes:validate_phase_state(data['camera_reference'],scene,paused,5)
        progress=simulation_progress(before,after)
        if progress!=row['simulation_progress'] or paused and progress['game_hours']!=0 or not paused and progress['game_hours']<=0:raise ValueError('Simulation progress differs')
        for key in ('environment_before','environment_after'):
            actual=environment(row[key])
            if actual!=row[key]['summary'] or not actual['complete']:raise ValueError('Environment incomplete or changed')
            for scene in (row[key]['scene_before'],row[key]['scene_after']):validate_phase_state(data['camera_reference'],scene,paused,5)
        requested=bounded_tail_count(before['frame'],row['selection_scene']['frame'],3600)
        if requested!=row['requested_frames']:raise ValueError('Requested frame bound differs')
        stats=row['statistics'];split=chars(stats)
        if split is None or validate_plan(row['statistics_collection'],requested)!=stats['count']:raise ValueError('Split/size plan differs')
        if row['statistics_collection']['attempts'][-1]['compact_bytes']!=len(json.dumps(stats,separators=(',',':')).encode()):raise ValueError('Stats compact byte count differs')
        if not before['frame']<stats['first_frame']<=stats['last_frame']<=after['frame']:raise ValueError('Chars bucket frames outside phase')
        r=row['process_resources'];first,last=r['before'],r['after'];wall=last['monotonic_seconds']-first['monotonic_seconds']
        user=last['user_seconds']-first['user_seconds'];kernel=last['system_seconds']-first['system_seconds'];cpu=user+kernel
        if r['pid']!=data['pid'] or r['executable'].casefold()!=data['executable'].casefold() or first['created_at']!=data['created_at'] or last['created_at']!=data['created_at'] or any(not math.isfinite(x) for x in (wall,user,kernel)) or wall<=0 or min(user,kernel)<0:raise ValueError('CPU interval/process differs')
        for value,expected in [(r['elapsed_seconds'],wall),(r['user_seconds'],user),(r['system_seconds'],kernel),(r['logical_cpu_equivalents'],cpu/wall)]:
            if not math.isclose(value,expected,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('CPU counters differ')
        recomputed=thread_deltas(first['thread_snapshot'],last['thread_snapshot'],wall,cpu)
        if recomputed!=r['thread_cpu']:raise ValueError('Cached thread CPU differs')
        cpu_threads={(t['tid'],t['created_filetime']):t for t in recomputed['threads']};joined=[]
        for thread in split['threads']:
            key=(thread['thread_id'],thread['created_filetime']);matched=cpu_threads.get(key) if thread['identity_verified'] else None
            names=[name for name in a.keys()&b.keys() if a[name]['identity_verified'] and b[name]['identity_verified'] and (a[name]['kernel_thread_id'],a[name]['created_filetime'])==key==(b[name]['kernel_thread_id'],b[name]['created_filetime'])]
            beats=row['roles_before'],row['roles_after']
            joined.append(dict(thread_id=key[0],created_filetime=key[1],calls_total=thread['calls_total'],sdk_roles=sorted(names),
                matches_game_thread_at_bounds=bool(matched and beats[0]['game_thread']==beats[1]['game_thread']==key[0]),
                matches_renderer_thread_at_bounds=bool(matched and beats[0]['service_thread']==beats[1]['service_thread']==key[0]),
                matched_cpu_identity=matched is not None,whole_thread_cpu_seconds=matched['cpu_seconds'] if matched else None,
                call_wall_total_ms=thread['call_wall_total_ms'],post_call_to_lock_total_ms=thread['post_call_to_lock_total_ms']))
        results.append(dict(label=row['label'],simulation_progress=progress,statistics_count=stats['count'],first_frame=stats['first_frame'],last_frame=stats['last_frame'],
            frame_interval_mean_ms=stats['mean_ms'],p99_frame_interval_ms=stats['p99_ms'],chars=split,thread_identity_matches=joined,
            post_fraction_of_legacy_wall=split['post_call_to_lock_total_ms']/split['legacy_total_ms'] if split['legacy_total_ms'] else None,
            cpu_elapsed_seconds=wall,process_cpu_seconds=cpu,logical_cpu_equivalents=cpu/wall,residual_cpu_seconds=recomputed['residual_cpu_seconds'],omitted_threads=len(recomputed['omitted']),
            population_range=[min(s['loaded_character_count'] for s in scenes),max(s['loaded_character_count'] for s in scenes)]))
    final=data['final_scene'];ref=data['source_reference']
    if not final['paused'] or final['frame_speed_multiplier']!=0 or final['free_camera'] or final['scene_camera_control_owned'] or final['battle']['active'] or final['game_total_hours']!=ref['game_total_hours']:raise ValueError('Final restored state differs')
    validate_camera_stability(ref,final)
    return dict(phases=results,scope='Sequential city phases, not causal comparisons. Chars wall intervals by telemetry-lock bucket admission; original spans may cross boundaries. Post includes timer/scheduling, not pure contention. CPU covers a distinct enclosing OS window and whole threads, not exclusive functions; do not subtract wall probes from frame time.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--expected-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw=args.input.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise SystemExit('Source SHA256 mismatch')
    out=dict(source_sha256=digest,result=analyze(json.loads(raw)))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=digest)))
