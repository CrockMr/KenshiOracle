"""Audit raw battle observations without equating combat mode with landed hits."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def analyze(data):
    initial = {row['name']: row for row in data['initial']['battle']['members']}
    order = [row['name'] for row in data['prepared']['members']]
    partners = {name: order[i ^ 1] for i, name in enumerate(order)} if len(order) % 2 == 0 else {}
    actors = {}
    for name, baseline in initial.items():
        readings = []
        missing = 0
        for observation in data['observations']:
            rows = [row for row in observation['scene']['battle']['members'] if row['name'] == name]
            if len(rows) != 1:
                missing += 1
                continue
            readings.append((observation['elapsed'], rows[0]))
        targets = Counter()
        states = Counter()
        target_names = Counter()
        for elapsed, row in readings:
            target = row.get('attack_target') or {}
            if number(target.get('sword_state')):
                states[str(target['sword_state'])] += 1
            if not target.get('resolved'):
                targets['unresolved'] += 1
            elif target.get('name') == partners.get(name):
                targets['paired_opponent'] += 1
            elif target.get('name') in initial:
                targets['other_cohort_member'] += 1
            else:
                targets['outside_cohort'] += 1
            if target.get('resolved'):
                target_names[target.get('name', '')] += 1
        deltas = {}
        for key in ('blood', 'flesh_sum', 'flesh_stun_sum'):
            old = baseline.get(key) if key == 'blood' else baseline.get('health', {}).get(key)
            values = []
            for elapsed, row in readings:
                if key == 'blood':
                    new = row.get(key)
                else:
                    before = baseline.get('health', {})
                    after = row.get('health', {})
                    if not (before.get('complete') and after.get('complete') and
                            before.get('part_count') == after.get('part_count')):
                        continue
                    new = after.get(key)
                if number(old) and number(new):
                    values.append((elapsed, new-old))
            changed = [(elapsed, delta) for elapsed, delta in values if abs(delta) > 1e-5]
            decreases = [elapsed for elapsed, delta in values if delta < -1e-5]
            increases = [elapsed for elapsed, delta in values if delta > 1e-5]
            deltas[key] = dict(comparable_observations=len(values),
                minimum_delta=min((value for _, value in values), default=None),
                maximum_delta=max((value for _, value in values), default=None),
                first_change_observed_seconds=changed[0][0] if changed else None,
                first_decrease_observed_seconds=decreases[0] if decreases else None,
                first_increase_observed_seconds=increases[0] if increases else None)
        actors[name] = dict(observations=len(readings), missing_or_duplicate_observations=missing,
            target_observations=dict(targets), target_names=dict(target_names),
            sword_state_observations=dict(states), raw_deltas=deltas,
            first_unconscious_observed_seconds=next((elapsed for elapsed, row in readings if row.get('unconscious')), None),
            under_melee_attack_observations=sum(bool(row.get('under_melee_attack')) for _, row in readings))
    return dict(plugin_version=data.get('initial_ping', {}).get('plugin_version'),
        pid=data.get('pid'), completed=data.get('completed', False), error=data.get('error'),
        sampling_interval_seconds=data.get('sampling_interval_seconds'),
        elapsed_seconds=data['observations'][-1]['elapsed'] if data['observations'] else 0,
        source_unchanged=data.get('source_sha256_before') == data.get('source_sha256_after')
            if data.get('source_sha256_after') else None,
        restoration_confirmed=bool(data.get('restored')) and not data.get('restoration_error'),
        actor_inventory_matches_requested=set(initial) == set(order) and len(initial) == len(order),
        actors=actors,
        interpretation='Raw sample changes only; no hit count, attacker attribution or task completion inferred. Missing samples do not imply death.')


def main(paths, output):
    reports = []
    for path in paths:
        raw = path.read_bytes()
        data = json.loads(raw)
        if 'initial' not in data:
            reports.append(dict(source=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                                excluded='No post-creation initial state', error=data.get('error')))
            continue
        reports.append(dict(source=str(path), sha256=hashlib.sha256(raw).hexdigest(), result=analyze(data)))
    result = dict(reports=reports)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, default=Path('runtime/battle-analysis.json'))
    args = parser.parse_args()
    main(args.paths, args.output)
