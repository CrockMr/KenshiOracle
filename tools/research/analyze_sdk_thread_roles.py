"""Recompute SDK-role/CPU joins with source hashes and scoped interpretation."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
from pathlib import Path
from sdk_thread_roles import join_cpu
from benchmark import simulation_progress
from analyze_pause_cpu import validate_phase_state
from physics_diagnostics import validate as validate_physics
from ai_diagnostics import validate as validate_ai,match_cpu as match_ai_cpu,function_name as ai_function_name


def analyze(data):
    if not data.get('completed'):
        return dict(completed=False,error=data.get('error'),restored=bool(data.get('restored')))
    cpu=data['process_resources'];joined=join_cpu(data['roles_before'],data['roles_after'],cpu,data['pid'])
    if not data['roles_before']['frame']<=data['scene_before']['frame']<=data['scene_after']['frame']<=data['roles_after']['frame']:
        raise ValueError('SDK roles do not bracket the CPU scene interval')
    if joined!=data['role_cpu_join']: raise ValueError('Cached role join disagrees with raw identities')
    for scene in [data['scene_before'],data['scene_after']]+[x['scene'] for x in data['observations']]:
        validate_phase_state(data['scene_before'],scene,False)
    progress=simulation_progress(data['scene_before'],data['scene_after'])
    if not progress or progress['game_hours']<=0 or progress!=data['simulation_progress']:
        raise ValueError('Invalid or inconsistent simulation progress')
    validate_physics(data['statistics_tail'])
    ai=validate_ai(data['statistics_tail'])
    ai_name=ai_function_name(data['statistics_tail'])
    known={(r['thread_id'],r['created_filetime']) for r in joined['roles'] if r['status']=='matched'}
    unique_roles={(r['thread_id'],r['created_filetime']):r for r in joined['roles'] if r['status']=='matched'}
    sdk_cpu=sum(r['cpu_seconds'] for r in unique_roles.values())
    process_cpu=cpu['user_seconds']+cpu['system_seconds']
    sdk_coverage=dict(unique_threads=len(unique_roles),matched_role_count=sum(r['status']=='matched' for r in joined['roles']),
        cpu_seconds=sdk_cpu,logical_cpu_equivalents=sdk_cpu/cpu['elapsed_seconds'],
        fraction_of_process_cpu=sdk_cpu/process_cpu if process_cpu else None,
        unknown_roles=[r['role'] for r in joined['roles'] if r['status']!='matched'],
        scope='Whole-thread CPU for unique verified SDK identities, not exclusive function costs')
    a,b=data['heartbeat_before'],data['heartbeat_after'];service_ids=set()
    for field in ('game_thread','service_thread'):
        if a[field]==b[field]:service_ids.add(a[field])
    remaining=[dict(tid=r['tid'],created_filetime=r['created_filetime'],cpu_seconds=r['cpu_seconds'],
                    logical_cpu_equivalents=r['cpu_seconds']/cpu['elapsed_seconds'])
               for r in cpu['thread_cpu']['threads'] if (r['tid'],r['created_filetime']) not in known and r['tid'] not in service_ids]
    remaining.sort(key=lambda r:r['cpu_seconds'],reverse=True)
    scenes=[data['scene_before'],data['scene_after']]+[x['scene'] for x in data['observations']]
    return dict(pid=data['pid'],plugin_version=data['initial_ping']['plugin_version'],completed=True,
        joined=joined,known_sdk_thread_cpu=sdk_coverage,ai_function=ai_name,ai_function_tail=ai,
        ai_periodic_tail=ai if ai_name=='AI::periodicUpdate' else None,
        ai_thread_cpu_identity_matches=match_ai_cpu(ai,cpu),process_cpu_seconds=process_cpu,elapsed_seconds=cpu['elapsed_seconds'],
        process_logical_cpu_equivalents=(cpu['user_seconds']+cpu['system_seconds'])/cpu['elapsed_seconds'],
        simulation_progress=progress,population_range=[min(s['loaded_character_count'] for s in scenes),max(s['loaded_character_count'] for s in scenes)],
        unmatched_role_threads_top=remaining[:10],residual_cpu_seconds=cpu['thread_cpu']['residual_cpu_seconds'],
        omitted_reasons=cpu['thread_cpu']['omitted_reasons'],running_details_rejected=data['running_details_rejected'],
        restored=bool(data.get('restored')) and not data.get('restoration_error'),
        source_and_copy_unchanged=data['source_and_copy_unchanged'],settings_unchanged=data['settings_unchanged'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,default=Path('runtime/sdk-roles-analysis.json'))
    args=p.parse_args();raw=args.source.read_bytes();report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),completed=report['result']['completed'],joined=report['result'].get('joined')),ensure_ascii=False))
