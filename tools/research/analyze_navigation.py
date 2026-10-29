"""Offline audit of retained slow calls; never contacts or controls the game."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from benchmark import validate_camera_stability, validate_nav_diagnostics


def scene_quality(data):
    try:
        reference = data['context']['population_before']['scene']
        validate_camera_stability(reference, data['population_after']['scene'])
        checked = 0
        for window in data['windows']:
            if 'observed_scene' in window:
                validate_camera_stability(reference, window['observed_scene'])
                checked += 1
        return 'per_window' if checked == len(data['windows']) and checked else 'endpoints_only'
    except RuntimeError:
        return 'invalid'
    except (KeyError, TypeError):
        return 'unverified'


def cpu_ms(call):
    values = (call.get('thread_cpu_user_ms'), call.get('thread_cpu_kernel_ms'))
    return sum(values) if all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in values) else None


def battle_quality(data):
    """Sampling checks cannot certify continuously fixed camera or steady combat."""
    try:
        reference = data['initial']
        observations = data['observations']
        if not observations:
            return 'unverified'
        for observation in observations:
            validate_camera_stability(reference, observation['scene'])
        return 'per_observation'
    except RuntimeError:
        return 'invalid'
    except (KeyError, TypeError):
        return 'unverified'


def observation_span(data, stats):
    try:
        first = data['initial']['frame']
        last = data['observations'][-1]['scene']['frame']
        flags = []
        if stats['first_frame'] < first:
            flags.append('starts_before_initial_observation')
        if stats['last_frame'] > last:
            flags.append('ends_after_last_observation')
        return '+'.join(flags) if flags else 'within_observation_span'
    except (KeyError, IndexError, TypeError):
        return 'unknown'


def captures(root, battle_root):
    for path in sorted(Path(root).glob('city-paired-*/x*.json')):
        raw = path.read_bytes()
        data = json.loads(raw)
        manifest_path = path.parent/'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig')) if manifest_path.exists() else {}
        resources = data.get('process_resources', {})
        pid = resources.get('pid', manifest.get('pid'))
        created = resources.get('before', {}).get('created_at')
        quality = scene_quality(data)
        note_path = path.parent/'quality.json'
        if note_path.exists():
            note = json.loads(note_path.read_text(encoding='utf-8-sig')).get(path.stem, {})
            if note.get('controlled_comparison_usable') is False:
                quality = 'invalid'
        metadata = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), kind='city',
            manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest() if manifest_path.exists() else None,
            quality_sha256=hashlib.sha256(note_path.read_bytes()).hexdigest() if note_path.exists() else None,
            camera_quality=quality, original_run_restored=bool(manifest.get('restored')),
            pid=pid, created_at=created, plugin_version=data['initial']['plugin_version'])
        sources = [('steady', index, window['statistics']) for index, window in enumerate(data['windows'], 1)]
        transition = data.get('context', {}).get('scene_transition_statistics')
        if transition:
            sources.append(('transition', None, transition))
        yield dict(path=path, metadata=metadata, sources=sources,
            prepare_frame=data.get('context', {}).get('prepared', {}).get('after', {}).get('frame'),
            prepare_frame_source='town_preparation_after', window_observation_span=None)
    if battle_root is None:
        return
    for path in sorted(Path(battle_root).glob('battle-20*.json')):
        raw = path.read_bytes()
        data = json.loads(raw)
        resources = data.get('process_resources', {})
        pid = resources.get('pid', data.get('pid'))
        if resources.get('pid') is not None and data.get('pid') != resources['pid']:
            raise ValueError('Conflicting battle process identities in '+str(path))
        metadata = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), kind='battle',
            pid=pid, created_at=resources.get('before', {}).get('created_at'),
            plugin_version=data.get('initial_ping', {}).get('plugin_version'),
            camera_quality=battle_quality(data), original_run_restored=bool(data.get('restored'))
                and not data.get('restoration_error'),
            completed=data.get('completed', False), error=data.get('error'),
            transport=data.get('transport', 'unrecorded'),
            requested_cohort_size=data.get('prepared', {}).get('requested_entities'),
            configuration_fingerprints=data.get('configuration_fingerprints'),
            source_save_unchanged=data.get('source_sha256_before') == data.get('source_sha256_after')
                if data.get('source_sha256_after') else None)
        stats = data.get('statistics')
        context = data.get('thread_attribution_statistics')
        if stats is None:
            metadata['excluded_reason'] = 'No measured trailing window; preparation or observation may have failed'
        sources = [('battle_tail', 1, stats)] if stats is not None else []
        if context is not None:
            sources.append(('battle_diagnostic_context', None, context))
            metadata.pop('excluded_reason', None)
        spans = {phase: observation_span(data, values) for phase, _, values in sources}
        yield dict(path=path, metadata=metadata,
            sources=sources, observation_spans=spans,
            prepare_frame=data.get('initial', {}).get('frame'),
            prepare_frame_source='post_creation_initial_scene',
            window_observation_span=observation_span(data, stats) if stats is not None else None)


def analyze(root, battle_root=None):
    events, files = {}, []
    observation_count = 0
    for capture in captures(root, battle_root):
        path, metadata = capture['path'], capture['metadata']
        files.append(metadata)
        pid, created = metadata['pid'], metadata['created_at']
        quality = metadata['camera_quality']
        for phase, index, stats in capture['sources']:
            validate_nav_diagnostics(stats)
            for call in stats.get('navmesh_slow_calls', []):
                if pid is None or created is None:
                    raise ValueError('Missing process identity for slow call in '+str(path))
                identity = (pid, created, call['thread_id'], call['started_qpc_ms'])
                observation_count += 1
                if identity not in events:
                    events[identity] = dict(pid=pid, created_at=created,
                        plugin_version=metadata['plugin_version'], call=call, seen_in=[])
                elif events[identity]['call'] != call:
                    raise ValueError('Conflicting observations of the same call in '+str(path))
                prepare_frame = capture['prepare_frame']
                relation = 'unknown'
                if prepare_frame is not None:
                    relation = ('before_prepare' if call['completion_frame'] < prepare_frame else
                                'spans_prepare' if call['start_frame'] < prepare_frame else 'after_prepare')
                events[identity]['seen_in'].append(dict(file=str(path), phase=phase,
                    window=index, kind=metadata['kind'], camera_quality=quality, relation_to_prepare=relation,
                    prepare_frame_source=capture['prepare_frame_source'],
                    window_observation_span=capture.get('observation_spans', {}).get(phase, capture['window_observation_span']),
                    retention_truncated=stats.get('navmesh_slow_calls_retention_truncated')))

    rows = sorted(events.values(), key=lambda row: row['call']['started_qpc_ms'])
    checked, endpoint_only, transition_only, battle_calls = [], [], [], []
    for row in rows:
        row['cpu_ms'] = cpu_ms(row['call'])
        steady = [source for source in row['seen_in'] if source['phase']=='steady']
        if any(source['camera_quality']=='per_window' for source in steady):
            checked.append(row)
        elif any(source['camera_quality']=='endpoints_only' for source in steady):
            endpoint_only.append(row)
        battle = [source for source in row['seen_in'] if source['phase'].startswith('battle_')]
        if battle:
            battle_calls.append(row)
        if not steady and not battle:
            transition_only.append(row)

    keys = defaultdict(list)
    for row in rows:
        c = row['call']
        vectors = (c.get('start_vector'), c.get('goal_vector'))
        if any(v is None or len(v)!=4 or any(x is None for x in v[:3]) for v in vectors):
            continue
        key = (row['pid'], row['created_at'], c['start_key'], c['goal_key'], c['radius'], c['water'], c['hierarchical'])
        keys[key].append(row)
    changed_xyz = []
    for key, group in keys.items():
        xyz = {(tuple(row['call']['start_vector'][:3]), tuple(row['call']['goal_vector'][:3])) for row in group}
        if len(xyz)>1:
            changed_xyz.append(dict(pid=key[0], created_at=key[1], start_key=key[2], goal_key=key[3],
                radius=key[4], water=key[5], hierarchical=key[6], unique_calls=len(group), distinct_xyz=len(xyz)))

    false_cpu = [row for row in checked if row['call']['result'] is False and row['cpu_ms'] is not None]
    battle_false_cpu = [row for row in battle_calls if row['call']['result'] is False and row['cpu_ms'] is not None]
    nonempty_false = [row for row in rows if row['call']['result'] is False and (row['call'].get('output_size_after') or 0)>0]
    bounds = lambda values: [min(values), max(values)] if values else None
    return dict(generated_at=datetime.now(timezone.utc).isoformat(), files=files,
        summary=dict(observations_in_files=observation_count, unique_retained_calls=len(rows),
            repeated_observations_removed=observation_count-len(rows),
            retained_results=dict(Counter('true' if row['call']['result'] else 'false' for row in rows)),
            per_window_checked_steady_calls=len(checked), endpoint_checked_steady_calls=len(endpoint_only),
            transition_only_calls=len(transition_only), cpu_available_calls=sum(row['cpu_ms'] is not None for row in rows),
            checked_steady_false_cpu_calls=len(false_cpu),
            checked_steady_false_cpu_ms_range=bounds([row['cpu_ms'] for row in false_cpu]),
            checked_steady_false_wall_ms_range=bounds([row['call']['elapsed_ms'] for row in false_cpu]),
            battle_capture_files=sum(file['kind']=='battle' for file in files),
            excluded_capture_files=sum('excluded_reason' in file for file in files),
            battle_tail_retained_calls=sum(any(source['phase']=='battle_tail' for source in row['seen_in']) for row in battle_calls),
            battle_diagnostic_context_calls=sum(any(source['phase']=='battle_diagnostic_context' for source in row['seen_in']) for row in battle_calls),
            battle_retained_calls_all_phases=len(battle_calls),
            battle_sampled_camera_calls=sum(any(source['camera_quality']=='per_observation' for source in row['seen_in'] if source['phase']=='battle_tail') for row in battle_calls),
            battle_false_cpu_calls=len(battle_false_cpu),
            battle_false_cpu_ms_range=bounds([row['cpu_ms'] for row in battle_false_cpu]),
            retained_false_with_nonempty_output_calls=len(nonempty_false),
            same_keys_with_different_xyz_groups=len(changed_xyz)),
        key_groups_with_different_xyz=changed_xyz, events=rows,
        limits=[
            'Only retained calls above the configured slow threshold are represented; no overall failure rate can be inferred.',
            'Transition reads can overlap steady windows and other transition reads; identities use process, creation time, thread and QPC start.',
            'A contextual call completed before the preparation frame is not attributed to the newly prepared town scene.',
            'Endpoint-only camera checks do not prove stability inside a window.',
            'Identical keys or captured arguments do not prove identical mesh/door/streaming state or safe cache reuse.',
            'The four-component vectors are raw SDK arguments; their world transform and fourth-component meaning are not established.',
            'A failed later restoration does not erase completed measurements; recovery evidence is separate.',
            'Battle trailing windows are not steady city windows; camera observations are sampled and can end before the statistics window.',
            'Battle calls are global navigation calls, without cohort character identity or attacker attribution.',
            'False can coexist with nonempty partial output; the API does not expose a detailed reason.',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='runtime/measurements')
    parser.add_argument('--output', default='runtime/navigation-analysis.json')
    parser.add_argument('--battle-root', default=None, help='Optional directory containing battle-20*.json captures')
    args = parser.parse_args()
    report = analyze(args.root, args.battle_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output.resolve()), summary=report['summary']), ensure_ascii=False))
