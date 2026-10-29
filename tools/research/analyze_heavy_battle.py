"""Replay a bounded battle with complete sampled cohort and separate CPU windows."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from pathlib import Path
from analyze_battle import analyze as battle_analysis, number
from analyze_pause_cpu import bounded_tail_count, common_threads, validate_phase_state
from benchmark import simulation_progress, validate_nav_diagnostics
from environment_diagnostics import summarize as inventory_summary
from function_diagnostics import validate as function_stats, match_cpu
from sdk_thread_roles import join_cpu
from thread_resources import thread_deltas
from statistics_budget import validate_plan


def validate_cohort(reference, scene, speed=5, paused=False):
    validate_phase_state(reference,scene,paused,speed)
    if not scene['scene_camera_control_owned'] or scene['edge_scrolling']:
        raise ValueError('Battle camera control lost')
    expected={r['name']:r for r in reference['battle']['members']}
    rows=scene['battle']['members'];names=[r['name'] for r in rows]
    if (len(expected)!=len(reference['battle']['members']) or not 2<=len(expected)<=40 or
            len(names)!=len(set(names)) or set(names)!=set(expected)):
        raise ValueError('Missing or duplicate sampled cohort; not inferred dead')
    battle=scene['battle']
    if (battle['active'] is not True or battle['prefix']!=reference['battle']['prefix'] or
            any(battle[k]!=len(expected) for k in ('requested_entities','spawned_entities','matched_loaded'))):
        raise ValueError('Battle tracking/count differs')
    for row in rows:
        health=row['health'];baseline=expected[row['name']]['health']
        if (row['is_player'] or health['complete'] is not True or
                health['part_count']!=baseline['part_count'] or not 1<=health['part_count']<=8 or
                health['sampled_count']!=health['part_count'] or
                any(not number(health[k]) for k in ('flesh_sum','flesh_stun_sum','max_health_sum')) or not number(row['blood'])):
            raise ValueError('Incomplete medical state or player in cohort')
    return True


def window_summary(row,data):
    if row.get('completed') is not True:raise ValueError('Incomplete battle window')
    before,after=row['scene_before'],row['scene_after'];initial=data['initial'];speed=data['speed']
    scenes=[before,after,row['selection_scene']]+[o['scene'] for o in row['observations']]
    for scene in scenes:validate_cohort(initial,scene,speed)
    progress=simulation_progress(before,after)
    if progress['game_hours']<=0 or progress!=row['simulation_progress']:raise ValueError('Battle clock progression differs')
    selected=row['selection_scene'];stats=row['statistics']
    if not before['frame']<=selected['frame']<=after['frame']:raise ValueError('Selection scene outside battle window')
    n=bounded_tail_count(before['frame'],selected['frame'],3600)
    actual_count=validate_plan(row['statistics_collection'],n) if 'statistics_collection' in row else n
    if (row['requested_frames']!=n or stats['count']!=actual_count or
            not before['frame']<stats['first_frame']<=stats['last_frame']<=after['frame'] or
            stats['last_frame']-stats['first_frame']+1!=actual_count):raise ValueError('Battle statistics outside own window')
    if 'context_collection' in row and row['context']['count']!=validate_plan(row['context_collection'],3600):
        raise ValueError('Diagnostic context selected count differs')
    validate_nav_diagnostics(stats);function=function_stats(stats)
    if function is None or function['function']!=data['initial_ping']['profiled_function']:raise ValueError('Selected battle function unavailable or changed')
    resources=row['process_resources'];a,b=resources['before'],resources['after']
    if (resources['pid']!=data['pid'] or a['created_at']!=b['created_at'] or
            a['created_at']!=data['created_at']):raise ValueError('Battle CPU process identity differs')
    if Path(resources['executable']).resolve()!=Path(data['executable']).resolve():raise ValueError('Battle CPU executable differs')
    wall=b['monotonic_seconds']-a['monotonic_seconds'];user=b['user_seconds']-a['user_seconds'];kernel=b['system_seconds']-a['system_seconds']
    if any(not math.isfinite(x) for x in (wall,user,kernel)) or wall<=0 or user<0 or kernel<0:raise ValueError('Invalid battle CPU counters')
    if wall<row['requested_seconds']:raise ValueError('Truncated battle CPU window')
    if (wall,user,kernel)!=(resources['elapsed_seconds'],resources['user_seconds'],resources['system_seconds']):raise ValueError('Cached CPU counters differ')
    # Role labels are added by the controller; raw endpoint deltas remain authoritative.
    actual=thread_deltas(a['thread_snapshot'],b['thread_snapshot'],wall,user+kernel)
    retained=resources['thread_cpu']
    for key in ('omitted','omitted_reasons','covered_cpu_seconds','residual_cpu_seconds'):
        if actual[key]!=retained[key]:raise ValueError('Cached thread CPU accounting differs')
    raw={(r['tid'],r['created_filetime']):r for r in actual['threads']}
    if len(raw)!=len(retained['threads']):raise ValueError('Cached thread inventory differs')
    for thread in retained['threads']:
        if any(thread.get(k)!=v for k,v in raw[(thread['tid'],thread['created_filetime'])].items()):raise ValueError('Cached thread counters differ')
    roles=join_cpu(data['sdk_roles_before'],data['sdk_roles_after'],resources,data['pid'])
    if not data['sdk_roles_before']['frame']<=before['frame']<=after['frame']<=data['sdk_roles_after']['frame']:
        raise ValueError('SDK roles do not bracket window')
    return dict(label=row['label'],requested_seconds=row['requested_seconds'],cpu_elapsed_seconds=wall,
        process_cpu_seconds=user+kernel,logical_cpu_equivalents=(user+kernel)/wall,
        residual_cpu_seconds=actual['residual_cpu_seconds'],omitted_reasons=actual['omitted_reasons'],
        top_threads=actual['threads'][:6],simulation_progress=progress,
        statistics=dict(first_frame=stats['first_frame'],last_frame=stats['last_frame'],count=actual_count,
            requested_maximum=n,collection=row.get('statistics_collection'),context_collection=row.get('context_collection'),
            mean_frame_ms=stats['mean_ms'],p99_frame_ms=stats['p99_ms'],systems=stats['systems']),
        function_cpu_identity=match_cpu(function,resources),sdk_role_cpu_join=roles,
        population_range=[min(s['loaded_character_count'] for s in scenes),max(s['loaded_character_count'] for s in scenes)],
        max_under_attack=max(s['battle']['under_melee_attack_count'] for s in scenes),
        max_unconscious=max(s['battle']['unconscious_count'] for s in scenes),max_dead=max(s['battle']['dead_count'] for s in scenes))


def analyze(data):
    if data.get('completed') is not True or data.get('error') or data.get('restoration_error') or data.get('camera_release_error'):
        raise ValueError('Battle acquisition or restoration incomplete')
    if type(data['speed']) is not int or data['speed']!=5:raise ValueError('Heavy battle requires explicit x5')
    if type(data['pairs']) is not int or not 1<=data['pairs']<=20 or len(data['initial']['battle']['members'])!=2*data['pairs']:
        raise ValueError('Requested battle cohort differs')
    if ([r['label'] for r in data['windows']]!=['window_1','window_2','window_3','window_4'] or
            [r['requested_seconds'] for r in data['windows']]!=[5,5,10,10]):raise ValueError('Unexpected battle window plan')
    if data['prepared']['prepared'] is not True or data['prepared']['mutual_enemies_verified'] is not True:
        raise ValueError('Battle was not prepared with mutual enemies')
    if not data['protected_files_unchanged'] or not data['settings_unchanged']:raise ValueError('Protected file attestation failed')
    validate_cohort(data['initial'],data['initial'],5,True)
    for obs in data['observations']:validate_cohort(data['initial'],obs['scene'],5)
    for env in (data['environment_before'],data['environment_after']):
        if not inventory_summary(env)['complete']:raise ValueError('Incomplete city inventory')
    final=data['final_scene'];reference=data['source_reference']
    if (not final['paused'] or final['frame_speed_multiplier']!=0 or final['battle']['active'] or
            final['scene_camera_control_owned'] or final['free_camera'] or final['game_total_hours']!=reference['game_total_hours']):
        raise ValueError('Final state not restored')
    result=battle_analysis(data);windows=[window_summary(row,data) for row in data['windows']]
    injured=[name for name,row in result['actors'].items() if any(
        row['raw_deltas'][k]['minimum_delta'] is not None and row['raw_deltas'][k]['minimum_delta'] < -1e-5 for k in ('blood','flesh_sum')) or
        (row['raw_deltas']['flesh_stun_sum']['maximum_delta'] is not None and row['raw_deltas']['flesh_stun_sum']['maximum_delta']>1e-5)]
    result.update(speed=5,windows=windows,actors_with_damage_signal=injured,combat_effective_observed=bool(injured),
        outside_cohort_target_observations=sum(r['target_observations'].get('outside_cohort',0) for r in result['actors'].values()),
        common_threads=common_threads([dict(label=r['label'],completed=True,process_resources=r['process_resources']) for r in data['windows']]),
        scope='One generated urban battle, not a deterministic speed comparison. No hit count, attacker attribution, exclusive CPU or optimization gain inferred.')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--expected-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise ValueError('Battle controller SHA differs')
    result=analyze(json.loads(raw))
    with args.output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(dict(source=str(args.source),source_sha256=digest,result=result),indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output),actors=len(result['actors']),damaged=len(result['actors_with_damage_signal']),windows=len(result['windows']))))
