"""Validate campaigns and write a local, descriptive comparison and issue drafts."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path

from oracle_compare import classify_metric, saved_metrics
from oracle_identity import validate_origin_fingerprint
from oracle_schema import canonical_bytes, validate_scenario
from oracle_traces import trace_metrics
from original_reference import SUPPORTED_REK_HASH
from rekenshi_profile import REQUESTED_SETTINGS, validate_runtime_evidence


CLASSES = ('stable_divergent', 'stable_identical', 'variable_outside_range',
           'known_deviation', 'variable_compatible', 'not_comparable')


def read_json(path, maximum=256 * 1024 * 1024):
    def invalid_constant(_value):
        raise ValueError('Non-finite comparison metadata')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Comparison input contains a duplicate JSON key')
            result[key] = value
        return result
    with Path(path).open('rb') as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('Comparison input exceeds its size limit')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def canonical_seed(value):
    if (type(value) is not str or len(value) > 20 or not value.isascii() or not value.isdecimal()
            or not 0 <= int(value) < 2**64):
        raise ValueError('Campaign seed must be a known unsigned 64-bit decimal integer')
    return str(int(value))


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e9


def relative(path, output):
    try:
        return Path(os.path.relpath(Path(path).resolve(), Path(output).resolve())).as_posix()
    except ValueError as exc:
        raise ValueError('Comparison output and snapshots must share a filesystem drive for relative links') from exc


def reference_proof(provenance, *, restored=False):
    if type(provenance) is not dict:
        raise ValueError('The original campaign lacks verified reference-profile provenance')
    metadata = provenance.get('metadata', {})
    if (metadata.get('kenshi_version') != '1.0.65' or metadata.get('rekenshi_version') != '0.3.5'
            or metadata.get('rekenshi_sha256') != SUPPORTED_REK_HASH):
        raise ValueError('The original campaign does not identify the audited reference build')
    effective = provenance.get('effective') or {}
    process = effective.get('process', {})
    validate_runtime_evidence(effective.get('evidence'), dict(pid=process.get('pid'),
        instance_id=process.get('instance_id'), settings=REQUESTED_SETTINGS, metadata=metadata))
    if restored:
        restoration = provenance.get('restoration', {})
        if (provenance.get('restore_required') is not False or restoration.get('file_verified') is not True
                or restoration.get('runtime_verified') is not True):
            raise ValueError('The original campaign did not verify player-profile restoration')


def load_campaign(path, target, output, *, minimum_repetitions=5):
    path = Path(path).resolve()
    if path.is_dir():
        path /= 'report.json'
    report = read_json(path)
    report.pop('variability', None)  # Recomputed across targets; release a large legacy summary.
    if report.get('target') != target or report.get('status') != 'completed':
        raise ValueError('Comparison requires a completed campaign for the declared target')
    if report.get('restoration', {}).get('verified') is not True:
        raise ValueError('Campaign controls were not verifiably restored')
    scenario = report['scenario']
    validate_scenario(scenario)
    executions = report.get('executions')
    if (type(executions) is not list or len(executions) < minimum_repetitions
            or len(executions) != report.get('repeat')):
        raise ValueError('Campaign repetition count is incomplete or below the required minimum')
    if target == 'original':
        reference_proof(report.get('reference_profile'), restored=True)
    fingerprint = validate_origin_fingerprint(report.get('source_fingerprint'))
    checkpoints = {point['name']: point['at'] for point in scenario['checkpoints']}
    grouped = defaultdict(list)
    seeds, identities = [], set()
    for execution in executions:
        repetition = execution.get('execution')
        if type(repetition) is not int or repetition < 1 or repetition in identities or execution.get('status') != 'completed':
            raise ValueError('Campaign has duplicate, invalid or incomplete repetitions')
        identities.add(repetition)
        loaded = execution.get('load', {})
        origin = execution.get('initial_clock', {}).get('elapsed_seconds')
        if not finite_number(origin) or origin < 0:
            raise ValueError('A repetition requires its observed initial clock')
        manifest = loaded.get('saved_origins') or loaded.get('source_manifest') or {}
        if manifest.get('source_fingerprint') != fingerprint or manifest.get('save_name') != scenario['save']:
            raise ValueError('A repetition used a different or unverified starting save')
        if target == 'original':
            reference_proof(execution.get('reference_profile'))
        else:
            provenance = execution.get('provenance', {})
            seed = canonical_seed(provenance.get('seed'))
            ready = loaded.get('ready', {})
            if (provenance.get('target') != 'meitou' or provenance.get('seed_applied_before_load') is not True
                    or ready.get('target') != 'meitou' or ready.get('seed_applied_before_load') is not True
                    or canonical_seed(ready.get('seed')) != seed or not provenance.get('seed_source')
                    or ready.get('seed_source') != provenance['seed_source']):
                raise ValueError('Each Meitou repetition requires a verified seed applied before loading')
            seeds.append(seed)
        captures = execution.get('checkpoints', [])
        if len(captures) != len(checkpoints) or {row.get('name') for row in captures} != set(checkpoints):
            raise ValueError('A repetition lacks the complete checkpoint set')
        for capture in captures:
            source = Path(capture['path'])
            if not source.is_absolute():
                source = path.parent / source
            source = source.resolve()
            if not source.is_relative_to(path.parent):
                raise ValueError('A snapshot lies outside its campaign directory')
            if source.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('Snapshot exceeds the shared state size limit')
            with source.open('rb') as handle:
                payload = handle.read(64 * 1024 * 1024 + 1)
            if len(payload) > 64 * 1024 * 1024:
                raise ValueError('Snapshot exceeds the shared state size limit')
            state = json.loads(payload)
            if (state['schema_version'] != '0.2' or payload != canonical_bytes(state)
                    or hashlib.sha256(payload).hexdigest() != capture.get('sha256')):
                raise ValueError('Snapshot schema, canonical bytes or hash does not match its campaign')
            if capture.get('requested_at') != checkpoints[capture['name']] or state['clock']['paused'] is not True:
                raise ValueError('Checkpoint time or paused-state evidence does not match the scenario')
            actual = state['clock']['elapsed_seconds'] - origin
            requested = checkpoints[capture['name']]
            if (actual < requested - 0.000001 or not finite_number(capture.get('actual_at'))
                    or not finite_number(capture.get('overshoot_seconds'))
                    or abs(capture['actual_at'] - actual) > 0.00001
                    or abs(capture['overshoot_seconds'] - (actual - requested)) > 0.00001
                    or capture.get('clock') != state['clock']):
                raise ValueError('Checkpoint actual time, overshoot and snapshot clock are inconsistent')
            if target == 'original':
                reference_proof(capture.get('reference_profile'))
            else:
                proof = capture.get('provenance', {})
                if (proof.get('target') != 'meitou' or proof.get('seed_applied_before_load') is not True
                        or canonical_seed(proof.get('seed')) != seed or proof.get('seed_source') != provenance['seed_source']):
                    raise ValueError('Checkpoint seed evidence differs from its verified repetition')
            grouped[capture['name']].append(dict(repetition=repetition,
                snapshot=relative(source, output), state=state, capture=capture))
    if target == 'meitou' and len(set(seeds)) != len(seeds):
        raise ValueError('Meitou repetitions must use distinct seeds')
    return dict(report=report, path=relative(path, output), scenario=scenario, n=len(executions),
                fingerprint=fingerprint, checkpoints=dict(grouped), seeds=seeds)


def escaped(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def snapshot_metrics(state, baseline):
    """Loaded populations and fixed starting cohorts; absence never means death."""
    values = {'/population/loaded/total': len(state['characters'])}
    for field, value in state['clock'].items():
        values['/clock/' + field] = value
    faction_ids = {row['id'] for row in state['factions']}
    by_faction = defaultdict(list)
    for character in state['characters']:
        by_faction[character['faction_id']].append(character)
    faction_ids.update(faction for faction in by_faction if faction is not None)
    faction_coverage = not by_faction[None]
    for faction in faction_ids:
        prefix = '/population/by_faction/' + escaped(faction)
        members = by_faction[faction]
        values[prefix + '/loaded'] = len(members) if faction_coverage else None
        for status in ('alive', 'unconscious', 'dead'):
            values[prefix + '/' + status] = (sum(row['state'] == status for row in members)
                                              if faction_coverage and all(row['state'] is not None for row in members) else None)
        values[prefix + '/unpaired'] = (sum(row['identity_origin'] != 'saved' for row in members)
                                        if faction_coverage else None)
    values['/population/unknown_faction'] = len(by_faction[None])
    known_towns = {row['current_town_id'] for row in state['characters'] if row['current_town_id'] is not None}
    town_coverage = all(row['town_assignment'] is not None for row in state['characters'])
    values['/population/by_town/coverage'] = True if town_coverage else None
    for town in known_towns:
        values['/population/by_town/' + escaped(town) + '/loaded'] = (
            sum(row['current_town_id'] == town for row in state['characters']) if town_coverage else None)
    templates = defaultdict(list)
    template_coverage = all(row['faction_id'] is not None and row['template_id'] is not None for row in state['squads'])
    values['/population/by_squad_template/coverage'] = True if template_coverage else None
    values['/population/by_faction/coverage'] = True if faction_coverage else None
    for squad in state['squads']:
        if squad['faction_id'] is not None and squad['template_id'] is not None:
            templates[(squad['faction_id'], squad['template_id'])].append(squad)
    for (faction, template), squads in templates.items():
        prefix = '/population/by_squad_template/' + escaped(faction) + '/' + escaped(template)
        values[prefix + '/squads'] = len(squads) if template_coverage else None
        # Loaded membership, not the count of an entire unloaded platoon.
        ids = {row['id'] for row in state['characters']}
        values[prefix + '/loaded_members'] = (len({member for squad in squads for member in squad['members']} & ids)
                                               if template_coverage else None)
    now = {row['id']: row for row in state['characters']}
    cohort = defaultdict(list)
    for row in baseline['characters']:
        if row['faction_id'] is not None:
            cohort[row['faction_id']].append(row['id'])
    for faction, members in cohort.items():
        prefix = '/combat/starting_cohort/' + escaped(faction)
        rows = [now.get(identity) for identity in members]
        complete = all(row is not None and row['state'] is not None for row in rows)
        values[prefix + '/size_at_start'] = len(members)
        values[prefix + '/missing'] = sum(row is None for row in rows)
        values[prefix + '/survivors'] = sum(row['state'] != 'dead' for row in rows) if complete else None
        values[prefix + '/dead'] = sum(row['state'] == 'dead' for row in rows) if complete else None
        values[prefix + '/unconscious'] = sum(row['state'] == 'unconscious' for row in rows) if complete else None
    initial_relations = {(row['source_id'], row['target_id']): row['value'] for row in baseline['relations']}
    for row in state['relations']:
        key = row['source_id'], row['target_id']
        prefix = '/relations/' + escaped(key[0]) + '/' + escaped(key[1])
        values[prefix + '/value'] = row['value']
        initial = initial_relations.get(key)
        values[prefix + '/change_from_first_checkpoint'] = (
            row['value'] - initial if row['value'] is not None and initial is not None else None)
    return values


def observations_for(metric, states, indexed):
    if metric.startswith('/population/by_squad_template/'):
        coverage = '/population/by_squad_template/coverage'
    elif metric.startswith('/population/by_faction/'):
        coverage = '/population/by_faction/coverage'
    elif metric.startswith('/population/by_town/'):
        coverage = '/population/by_town/coverage'
    else:
        coverage = None
    if coverage and metric != coverage:
        for values in indexed.values():
            if metric not in values and values.get(coverage) is True:
                values[metric] = 0
    return [dict(repetition=row['repetition'], snapshot=row['snapshot'],
                 present=metric in indexed[row['repetition']], value=indexed[row['repetition']].get(metric))
            for row in states]


def aggregate_metrics(original, meitou, original_baselines, meitou_baselines, tolerances=None, known_deviations=None):
    left = {row['repetition']: snapshot_metrics(row['state'], original_baselines[row['repetition']]) for row in original}
    right = {row['repetition']: snapshot_metrics(row['state'], meitou_baselines[row['repetition']]) for row in meitou}
    keys = set().union(*(set(row) for row in [*left.values(), *right.values()]))
    findings = []
    for key in sorted(keys):
        tolerance = (tolerances or {}).get(key, (tolerances or {}).get('number', 0.0))
        findings.append(classify_metric(key, observations_for(key, original, left),
            observations_for(key, meitou, right), tolerance=tolerance,
            known_deviation=(known_deviations or {}).get(key)))
    return findings


def temporal_findings(original, meitou, tolerances=None, known_deviations=None, arrival_radius=5.0):
    left = trace_metrics(original, arrival_radius=arrival_radius)
    right = trace_metrics(meitou, arrival_radius=arrival_radius)
    last = max(original['scenario']['checkpoints'], key=lambda point: point['at'])['name']
    keys = set().union(*(set(values) for values in [*left.values(), *right.values()]))
    paths = sorted({row['snapshot'] for campaign in (original, meitou)
                    for rows in campaign['checkpoints'].values() for row in rows})
    result = []
    for key in sorted(keys):
        spatial = any(part in key for part in ('/final_position/', 'distance', 'displacement'))
        tolerance = (tolerances or {}).get(key, (tolerances or {}).get('position' if spatial else 'number',
                                                                                    0.000001 if spatial else 0.0))
        finding = classify_metric(key,
            observations_for(key, original['checkpoints'][last], left),
            observations_for(key, meitou['checkpoints'][last], right), tolerance=tolerance,
            units='world units' if spatial else None, known_deviation=(known_deviations or {}).get(key))
        finding.update(checkpoint='whole_scenario', additional_snapshots=paths)
        result.append(finding)
    return result


def write_reports(report, output, rewrite=False):
    """Render a computed report, optionally reformatting its existing local artifact."""
    from oracle_report import render_reports
    return render_reports(report, output, rewrite=rewrite)


def compare_campaigns(original_path, meitou_path, output, *, minimum_repetitions=5, tolerances=None,
                      known_deviations=None, arrival_radius=5.0):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new empty comparison output directory')
    if type(minimum_repetitions) is not int or not 1 <= minimum_repetitions <= 100:
        raise ValueError('minimum_repetitions must be an integer from 1 to 100')
    tolerances = {'position': 0.000001, 'number': 0.0, **(tolerances or {})}
    for value in [*(tolerances or {}).values(), arrival_radius]:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Numerical tolerances must be finite and nonnegative')
    original = load_campaign(original_path, 'original', output, minimum_repetitions=minimum_repetitions)
    meitou = load_campaign(meitou_path, 'meitou', output, minimum_repetitions=minimum_repetitions)
    scenario = deepcopy(original['scenario'])
    other = deepcopy(meitou['scenario'])
    scenario.pop('repeat', None)
    other.pop('repeat', None)
    if scenario != other or original['fingerprint'] != meitou['fingerprint']:
        raise ValueError('Campaigns must use the same scenario and unchanged starting-save fingerprint')
    first = min(scenario['checkpoints'], key=lambda row: row['at'])['name']
    left_baselines = {row['repetition']: row['state'] for row in original['checkpoints'][first]}
    right_baselines = {row['repetition']: row['state'] for row in meitou['checkpoints'][first]}
    findings = []
    for point in scenario['checkpoints']:
        name = point['name']
        left, right = original['checkpoints'][name], meitou['checkpoints'][name]
        group = saved_metrics(left, right, tolerances=tolerances, known_deviations=known_deviations)
        group += aggregate_metrics(left, right, left_baselines, right_baselines, tolerances, known_deviations)
        for finding in group:
            finding['checkpoint'] = name
        findings.extend(group)
    findings.extend(temporal_findings(original, meitou, tolerances, known_deviations, arrival_radius))
    findings.sort(key=lambda row: (CLASSES.index(row['classification']), row['checkpoint'], row['metric']))
    report = dict(format_version='0.2', scenario=scenario,
        original=dict(n=original['n'], report=original['path']),
        meitou=dict(n=meitou['n'], report=meitou['path'], seeds=meitou['seeds']),
        source_fingerprint=original['fingerprint'], findings=findings,
        reference_deviations=original['report']['reference_profile'].get('known_deviations', []),
        tolerances=tolerances or {}, arrival_radius_world_units=arrival_radius, limitations=[
            'Ranges observed in five repetitions do not characterize the engine’s full distribution.',
            'The number of identical fields is not an overall parity score: the many relations carry substantial weight in that total.',
            'A missing or null value in any repetition retains not-comparable coverage.',
            'Loaded population depends on each engine’s loading rules; its scope is described in state-coverage.',
            'Times are calendar times; the instants actually reached may overshoot the requested checkpoints.',
            'The starting fingerprint covers quick.save and indexed platoons; it alone does not prove identical assets, mods or load order.',
            'Builds are identified by local validation evidence; a save fingerprint does not replace a build manifest.',
            'Observed polyline distances are lower bounds, distinct from net displacement; a missing position censors the cohort.',
            'Arrival is observed within an X/Z radius for all initial members; its exact time remains unknown.',
            'Positive snapshots measure an observed engagement span; they prove neither continuous combat nor cumulative duration.',
            'Duration bounds apply only to the sampled window; duration_seconds remains not comparable without a temporal log.'])
    write_reports(report, output)
    return dict(report=str(output / 'report.json'), summary=str(output / 'report.md'),
                issues=str(output / 'issues'), original_n=original['n'], meitou_n=meitou['n'],
                classifications=dict(Counter(row['classification'] for row in findings)))
