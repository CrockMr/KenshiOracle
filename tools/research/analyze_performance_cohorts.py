"""Offline, hash-bound independent cohorts; never merge function/CPU windows."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from analyze_chars_split import analyze as chars_analysis
from analyze_main_loop import analyze as main_analysis
from analyze_renderer import analyze as renderer_analysis
from analyze_root_frame import analyze as root_analysis
from analyze_root_cpu import analyze as root_cpu_analysis
from analyze_root_battle import analyze as root_battle_analysis
from analyze_aggregate_battle import analyze as aggregate_battle_analysis
from analyze_profiled_function import analyze as function_analysis
from analyze_heavy_battle import analyze as battle_analysis
from chars_diagnostics import validate as chars
from function_diagnostics import validate as function, match_cpu
from benchmark import validate_nav_diagnostics
from thread_resources import thread_deltas
from sdk_thread_roles import join_cpu

ANALYZERS={'chars_split':chars_analysis,'main_loop':main_analysis,
           'renderer':renderer_analysis,'root_frame':root_analysis,'root_cpu':root_cpu_analysis,'root_battle':root_battle_analysis,'aggregate_battle':aggregate_battle_analysis,'profiled_function':function_analysis,'heavy_battle':battle_analysis}
LIMITATIONS=[
    'Independent sequential cohorts; no causal version/speed comparison, pooled average or optimization gain.',
    'Callback intervals are not displayed FPS. Function wall scopes are inclusive and can overlap.',
    'Function buckets, scene-clock bounds and enclosing OS CPU windows differ; no subtraction or exclusive coverage fraction.',
    'Whole-thread CPU is not CPU of a selected function; creation identities are local to each cohort/process.',
    'SDK object roles can alias the same OS thread; their whole-thread CPU must not be summed.',
    'Missing endpoints remain omitted; signed CPU residuals are preserved without clamping.',
    'Population ranges contain observations only. Save reload does not determinize all NPC state.',
    'Replay verifies recorded data, not the current game, hardware or live preservation of saves.',
]

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def number(value,minimum=0):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum:
        raise ValueError('Invalid finite timing/counter')
    return value

def _json(raw):
    def invalid(value):raise ValueError('Non-finite JSON constant: '+value)
    return json.loads(raw,parse_constant=invalid)

def process_identity(data,phases):
    anchor=phases[0]['process_resources']
    created=data.get('created_at',anchor['before']['created_at'])
    executable=data.get('executable',anchor['executable']);number(created)
    if not isinstance(executable,str) or not executable:raise ValueError('Missing CPU executable identity')
    for phase in phases:
        resources=phase['process_resources']
        if (resources['pid']!=data['pid'] or resources['before']['created_at']!=created or resources['after']['created_at']!=created or
                str(Path(resources['executable']).resolve()).casefold()!=str(Path(executable).resolve()).casefold()):
            raise ValueError('CPU data belongs to another process lifetime/executable')
    return dict(pid=data['pid'],created_at=created,executable=executable,
                creation_source='capture_root' if 'created_at' in data else 'first_cpu_endpoint_checked_across_all_phases',
                executable_source='capture_root' if 'executable' in data else 'first_cpu_interval_checked_across_all_phases')

def phase_summary(row):
    stats=row['statistics'] if 'statistics' in row else row['statistics_tail']
    n=stats['count'];first,last=stats['first_frame'],stats['last_frame']
    if any(type(v) is not int for v in (n,first,last)) or not 1<=n<=3600 or last-first+1!=n:
        raise ValueError('Invalid selected frame interval')
    resources=row['process_resources'];a,b=resources['before'],resources['after']
    wall=number(b['monotonic_seconds']-a['monotonic_seconds'])
    user=number(b['user_seconds']-a['user_seconds']);kernel=number(b['system_seconds']-a['system_seconds'])
    if wall<=0 or a['created_at']!=b['created_at']:raise ValueError('CPU interval/lifetime differs')
    for observed,expected in [(resources['elapsed_seconds'],wall),(resources['user_seconds'],user),(resources['system_seconds'],kernel),(resources['logical_cpu_equivalents'],(user+kernel)/wall)]:
        if not math.isclose(number(observed),expected,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Cached CPU interval differs')
    cpu=thread_deltas(a['thread_snapshot'],b['thread_snapshot'],wall,user+kernel)
    selected=function(stats);split=chars(stats) if 'charsUpdate_split' in stats['systems'] else None
    if selected is not None:
        selected=dict(selected,whole_thread_identity_join=match_cpu(selected,dict(resources,thread_cpu=cpu)))
    systems=stats['systems'];nav=None
    if 'navmesh_findPath_threads' in systems:
        validate_nav_diagnostics(stats)
        nav=dict(calls_total=systems['navmesh_findPath_calls_total'],inclusive_wall_mean_ms=systems['navmesh_findPath_mean_ms'],
                 max_call_ms=systems['navmesh_findPath_max_call_ms'],results=systems.get('navmesh_findPath_results'))
    observations=[row['scene_before'],row['scene_after']]+[r['scene'] for r in row['observations']]
    population=[r['loaded_character_count'] for r in observations]
    if any(type(v) is not int or v<0 for v in population):raise ValueError('Invalid observed population')
    paused=row['scene_before']['paused'];speed=row['scene_before']['frame_speed_multiplier']
    return dict(label=row['label'],paused=paused,frame_speed_multiplier=speed,
        frame_statistics=dict(count=n,first_frame=first,last_frame=last,callback_interval_mean_ms=number(stats['mean_ms']),p99_callback_interval_ms=number(stats['p99_ms']),collection=row.get('statistics_collection')),
        observed_population_range=[min(population),max(population)],simulation_progress=row['simulation_progress'],
        os_cpu=dict(start_monotonic=a['monotonic_seconds'],end_monotonic=b['monotonic_seconds'],elapsed_seconds=wall,
                    user_seconds=user,kernel_seconds=kernel,process_cpu_seconds=user+kernel,logical_cpu_equivalents=(user+kernel)/wall,
                    threads=sorted(cpu['threads'],key=lambda t:(-t['cpu_seconds'],t['tid'],t['created_filetime'])),
                    omitted=cpu['omitted'],residual_cpu_seconds=cpu['residual_cpu_seconds']),
        selected_function=selected,chars_split=split,
        legacy_chars_mean_ms=systems.get('charsUpdate_mean_ms'),
        legacy_chars_scope='Historical chars wall through telemetry-lock acquisition; not the pure original call.',navigation=nav)

def analyze_manifest(raw,root):
    manifest=_json(raw);root=Path(root).resolve()
    if type(manifest.get('schema_version')) is not int or manifest['schema_version']!=1:raise ValueError('Unknown cohort manifest schema')
    rows=manifest.get('cohorts')
    if not isinstance(rows,list) or not 1<=len(rows)<=32:raise ValueError('Requires 1..32 independent cohorts')
    ids=set();paths=set();hashes=set();cohorts=[]
    for entry in rows:
        key=entry['id'];kind=entry['analyzer'];path=Path(entry['source']);expected=entry['sha256']
        if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',key) or key in ids:raise ValueError('Invalid/duplicate cohort ID')
        if kind not in ANALYZERS:raise ValueError('Unknown specialized analyzer')
        if not isinstance(entry['scenario'],str) or not 1<=len(entry['scenario'])<=200:raise ValueError('Invalid declared scenario label')
        if path.is_absolute() or '..' in path.parts:raise ValueError('Capture path must be relative to the explicit root')
        source=(root/path).resolve()
        if not source.is_relative_to(root) or source in paths:raise ValueError('Escaped/duplicate capture path')
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or expected in hashes:raise ValueError('Invalid/duplicate source SHA256')
        if not 0<source.stat().st_size<=128*1024*1024:raise ValueError('Capture size outside bound')
        content=source.read_bytes()
        if digest(content)!=expected:raise ValueError('Capture SHA256 mismatch: '+key)
        data=_json(content)
        if data.get('completed') is not True:raise ValueError('Incomplete capture: '+key)
        ping=data['initial_ping']
        if ping.get('plugin_version')!=entry['plugin_version'] or ping.get('system_hook_count')!=3:raise ValueError('Declared native version/hooks differ')
        if ping.get('profiled_function')!=entry['selected_function']:raise ValueError('Declared function selection differs')
        result=ANALYZERS[kind](data)
        if result.get('completed') is False:raise ValueError('Specialized replay did not complete')
        phases=data['windows'] if kind in ('heavy_battle','root_battle','aggregate_battle') else data['phases']
        if not phases or len({r['label'] for r in phases})!=len(phases):raise ValueError('Missing/duplicate phase labels')
        summaries=[phase_summary(r) for r in phases]
        if any((r['selected_function'] is None)!=(entry['selected_function'] is None) or
               r['selected_function'] is not None and r['selected_function']['function']!=entry['selected_function'] for r in summaries):
            raise ValueError('Measured function differs from declared native selection')
        # Never pool rows or join thread identities between captures, even for equal TIDs.
        identity=process_identity(data,phases)
        sdk_before=data.get('sdk_roles_before',phases[0].get('sdk_roles_before'))
        sdk_after=data.get('sdk_roles_after',phases[-1].get('sdk_roles_after'))
        for original,summary in zip(phases,summaries):
            summary['sdk_role_cpu_join']=None
            if sdk_before is not None and sdk_after is not None:
                if not sdk_before['frame']<=original['scene_before']['frame']<=original['scene_after']['frame']<=sdk_after['frame']:
                    raise ValueError('SDK roles do not bracket cohort phase')
                resources=dict(original['process_resources'],thread_cpu=dict(threads=summary['os_cpu']['threads']))
                summary['sdk_role_cpu_join']=join_cpu(sdk_before,sdk_after,resources,data['pid'])
        analyzer=Path(ANALYZERS[kind].__code__.co_filename)
        cohort=dict(id=key,analyzer=kind,source=str(path).replace('\\','/'),source_sha256=expected,
                    plugin_version=ping['plugin_version'],selected_function=ping.get('profiled_function'),
                    declared_scenario=entry['scenario'],captured_town=data.get('town'),
                    process_identity=identity,
                    specialized_analysis_sha256=digest(canonical(result)),specialized_analysis_scope=result.get('scope'),
                    analyzer_source_sha256=digest(analyzer.read_bytes()),phases=summaries)
        if kind in ('heavy_battle','root_battle','aggregate_battle'):cohort['battle_observations']=dict(requested_pairs=data['pairs'],tracked_actors=len(result['actors']),
            actors_with_damage_signal=len(result['actors_with_damage_signal']),outside_cohort_target_observations=result['outside_cohort_target_observations'])
        cohorts.append(cohort);ids.add(key);paths.add(source);hashes.add(expected)
    return dict(schema_version=1,manifest_sha256=digest(raw),cohort_count=len(cohorts),cohorts=cohorts,limitations=LIMITATIONS)

def markdown(report):
    lines=['# Diagnostic des cohortes de performances','',
           'Rejeu hors jeu de captures indépendantes. Aucune moyenne regroupée, comparaison causale entre versions, fraction CPU exclusive ou amélioration moteur déduite.','',
           '| Cohorte/version | Phase | Pause/vitesse | Frames retenues | Intervalle moyen ms | p99 ms | Fenêtre CPU s | CPU logiques | Population observée |',
           '|---|---|---|---:|---:|---:|---:|---:|---|']
    for cohort in report['cohorts']:
        for row in cohort['phases']:
            frame=row['frame_statistics'];cpu=row['os_cpu'];population=row['observed_population_range']
            lines.append(f"| {cohort['id']} / {cohort['plugin_version']} | {row['label']} | {'pause' if row['paused'] else 'x'+str(row['frame_speed_multiplier'])} | {frame['count']} | {frame['callback_interval_mean_ms']:.6f} | {frame['p99_callback_interval_ms']:.6f} | {cpu['elapsed_seconds']:.3f} | {cpu['logical_cpu_equivalents']:.6f} | {population[0]}..{population[1]} |")
    lines+=['','## Portées des appels sélectionnés','','Temps muraux inclusifs en **millisecondes** ; jamais le CPU du thread entier ni un temps GPU.','',
            '| Cohorte/phase | Fonction | Appels terminés | Mur moyen ms/frame | Max appel ms | Identités CPU jointes |',
            '|---|---|---:|---:|---:|---:|']
    for c in report['cohorts']:
        for r in c['phases']:
            f=r['selected_function']
            if f is not None:
                matched=sum(t['matched_cpu_identity'] for t in f['whole_thread_identity_join']['threads'])
                lines.append(f"| {c['id']}/{r['label']} | {f['function']} | {f['calls_total']} | {f['mean_ms']:.9f} | {f['max_call_ms']:.6f} | {matched}/{len(f['threads'])} |")
    lines+=['','## Provenance','','Manifest SHA256 : `'+report['manifest_sha256']+'`. Labels de scénario déclaratifs ; villes capturées et scènes restent dans le JSON. Les créations FILETIME sont conservées comme chaînes exactes.','']
    for c in report['cohorts']:lines+=['- '+c['id']+' : `'+c['source']+'`, SHA256 `'+c['source_sha256']+'`. Analyse spécialisée canonique : `'+c['specialized_analysis_sha256']+'`.']
    lines+=['','## Limites','']+['- '+item for item in report['limitations']]
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('--expected-manifest-sha256',required=True)
    p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--output',type=Path,required=True);p.add_argument('--markdown',type=Path)
    args=p.parse_args();raw=args.manifest.read_bytes()
    if digest(raw)!=args.expected_manifest_sha256:raise ValueError('Manifest SHA256 mismatch')
    if args.output.exists() or args.markdown is not None and args.markdown.exists():raise FileExistsError('Choose new output paths')
    if args.markdown is not None and args.markdown.resolve()==args.output.resolve():raise ValueError('JSON and Markdown outputs must differ')
    report=analyze_manifest(raw,args.root);payload=json.dumps(report,indent=2,ensure_ascii=True,allow_nan=False)+'\n'
    with args.output.open('x',encoding='utf-8') as stream:stream.write(payload)
    if args.markdown is not None:
        with args.markdown.open('x',encoding='utf-8') as stream:stream.write(markdown(report))
    print(json.dumps(dict(output=str(args.output),cohorts=report['cohort_count'],phases=sum(len(c['phases']) for c in report['cohorts']),manifest_sha256=report['manifest_sha256'])))

if __name__=='__main__':main()
