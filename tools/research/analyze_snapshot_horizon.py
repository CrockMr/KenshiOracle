"""Describe observed clock horizons and medical outcomes, without causal claims."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def summarize_run(run, target):
    result = dict(speed=run['speed'],completed=run.get('completed',False),
        baseline_comparison=run.get('baseline_comparison'),excluded=run.get('excluded'))
    if not result['completed']:
        return result
    if not run['baseline_comparison']['matches']:
        raise ValueError('Completed run has a rejected baseline')
    resources=run['process_resources']
    if resources['before']['created_at'] != resources['after']['created_at']:
        raise ValueError('Game lifetime changed')
    progress=run['progress']
    hours,wall=progress['game_hours'],progress['wall_seconds']
    if not all(math.isfinite(x) for x in [hours,wall]) or hours < target or wall<=0:
        raise ValueError('Invalid completed horizon')
    cpu=resources['user_seconds']+resources['system_seconds']
    if not math.isfinite(cpu) or cpu < 0 or resources['elapsed_seconds'] <= 0:
        raise ValueError('Invalid CPU interval')
    initial={r['name']:r for r in run['initial']['battle']['members']}
    final={r['name']:r for r in run['final']['battle']['members']}
    if (len(initial)!=len(run['initial']['battle']['members']) or
        len(final)!=len(run['final']['battle']['members']) or initial.keys()!=final.keys()):
        raise ValueError('Missing or duplicate final cohort')
    actors={}
    for name,a in initial.items():
        b=final[name]
        if not (a['health']['complete'] and b['health']['complete'] and
                a['health']['part_count']==b['health']['part_count']):
            raise ValueError('Incomplete final medical state')
        actors[name]=dict(blood_delta=b['blood']-a['blood'],
            flesh_delta=b['health']['flesh_sum']-a['health']['flesh_sum'],
            flesh_stun_delta=b['health']['flesh_stun_sum']-a['health']['flesh_stun_sum'],
            unconscious=b['unconscious'],dead=b['dead'])
        if any(not math.isfinite(actors[name][key]) for key in ('blood_delta','flesh_delta','flesh_stun_delta')):
            raise ValueError('Nonfinite medical delta')
        first_ko = next((obs for obs in run['observations'] if any(
            actor['name']==name and actor['unconscious'] for actor in obs['scene']['battle']['members'])),None)
        actors[name]['first_unconscious_observation'] = dict(
            elapsed_seconds=first_ko['elapsed'],
            game_hours_since_start=first_ko['scene']['game_total_hours']-run['clock_start']['game_total_hours']
        ) if first_ko else None
    outside=0
    for observation in run['observations']:
        for actor in observation['scene']['battle']['members']:
            t=actor.get('attack_target') or {}
            outside+=bool(t.get('resolved') and t.get('name') not in initial)
    result.update(progress=progress,horizon_overshoot_hours=hours-target,
        process_cpu_seconds=cpu,cpu_seconds_per_observed_game_hour=cpu/hours,
        wall_seconds_per_observed_game_hour=wall/hours,
        cpu_enclosing_wall_seconds=resources['elapsed_seconds'],
        groups=resources['thread_cpu']['accounting_group_cpu_seconds'],
        omitted_reasons=resources['thread_cpu']['omitted_reasons'],
        residual_cpu_seconds=resources['thread_cpu']['residual_cpu_seconds'],
        actors=actors,outside_cohort_target_observations=outside,
        initial_population=run['initial'].get('loaded_character_count'),
        population_range=[min(x['scene']['loaded_character_count'] for x in run['observations']),
                          max(x['scene']['loaded_character_count'] for x in run['observations'])])
    return result


def analyze(data):
    runs=[summarize_run(row,data['target_game_hours']) for row in data['runs']]
    groups=[]
    for speed in sorted({row['speed'] for row in runs}):
        rows=[r for r in runs if r['speed']==speed and r['completed']]
        group=dict(speed=speed,completed_runs=len(rows))
        for key in ('wall_seconds_per_observed_game_hour','cpu_seconds_per_observed_game_hour'):
            values=[r[key] for r in rows]
            group[key]=dict(median=median(values),minimum=min(values),maximum=max(values)) if values else None
        groups.append(group)
    return dict(pid=data['pid'],snapshot=data['snapshot'],completed=data.get('completed',False),
        error=data.get('error'),runs=runs,groups=groups,
        restored=bool(data.get('restored')) and not data.get('restoration_error'),
        snapshot_files_unchanged=data.get('snapshot_files_unchanged'),
        source_and_copy_unchanged=data.get('source_and_copy_unchanged'),settings_unchanged=data.get('settings_unchanged'),
        interpretation='Descriptive runs from guarded visible baselines; sampled horizon overshoot, AI and reinforcements prevent a deterministic task-cost or optimization claim.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,default=Path('runtime/snapshot-horizon-analysis.json'))
    args=p.parse_args();raw=args.source.read_bytes()
    report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),result=report['result']),ensure_ascii=False))
