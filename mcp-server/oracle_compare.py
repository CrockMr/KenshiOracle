"""Small-sample oracle classification and proven saved-character matching.

This module is pure: it reads no files and never contacts either game. The report
loader certifies provenance, source fingerprints and seeds before calling it.
Original stability uses exact observed values. Tolerances affect cross-target
equality and range boundaries only, never the original's variability.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from statistics import median
from urllib.parse import urlsplit

from oracle_identity import validate_saved_handles
from oracle_schema import validate_state


CLASSES = ('stable_identical', 'stable_divergent', 'variable_compatible',
           'variable_outside_range', 'known_deviation', 'not_comparable')
DEFAULT_TOLERANCES = {'position': 0.000001, 'number': 0.0}


def _tolerance(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Tolerance must be a finite nonnegative absolute number')
    return float(value)


def _kind(value):
    if type(value) in (int, float):
        try:
            return 'number' if math.isfinite(value) else None
        except OverflowError:
            return None
    if type(value) is bool:
        return 'boolean'
    if type(value) is str:
        try:
            value.encode('utf-8')
        except UnicodeError:
            return None
        return 'string'
    return None


def _observations(rows):
    if type(rows) is not list:
        raise ValueError('Observations must be a list')
    result, repetitions = [], set()
    for row in rows:
        if type(row) is not dict or type(row.get('repetition')) is not int or row['repetition'] < 1:
            raise ValueError('Every observation requires a positive integer repetition')
        if row['repetition'] in repetitions:
            raise ValueError('A repetition must contribute only one observation to a metric')
        repetitions.add(row['repetition'])
        snapshot = row.get('snapshot')
        if (type(snapshot) is not str or not snapshot or len(snapshot) > 4096
                or '\\' in snapshot or snapshot.startswith('/') or ':' in snapshot
                or any(ord(c) < 32 or ord(c) == 127 for c in snapshot)
                or any(part in ('', '.') for part in snapshot.split('/'))):
            # The loader checks physical containment before computing links from
            # a separate report folder; those relative evidence links can use .. .
            raise ValueError('Snapshot evidence must be a relative POSIX path')
        present = row.get('present', 'value' in row)
        if type(present) is not bool:
            raise ValueError('Observation present must be boolean')
        normalized = dict(repetition=row['repetition'], snapshot=snapshot, present=present,
                          value=deepcopy(row.get('value')) if present else None)
        if row.get('reason'):
            normalized['reason'] = str(row['reason'])
        if normalized['value'] is not None and _kind(normalized['value']) is None:
            # Preserve unavailable coverage without emitting NaN/Infinity or an
            # arbitrary Python object into the equivalent strict JSON report.
            normalized.update(value=None, reason='Unsupported or non-finite scalar observation')
        result.append(normalized)
    return result


def _summary(rows):
    values = [row['value'] for row in rows]
    available = [row['value'] for row in rows if row['present'] and _kind(row['value']) is not None]
    kinds = {_kind(value) for value in available}
    complete = bool(rows) and len(available) == len(rows) and len(kinds) == 1
    numeric = complete and kinds == {'number'}
    middle = median(available) if numeric else None
    if numeric and not math.isfinite(middle):
        ordered = sorted(available)
        halfway = len(ordered) // 2
        middle = ordered[halfway - 1] / 2 + ordered[halfway] / 2
    return dict(n=len(rows), comparable_n=len(available), values=values, observations=rows,
                exact_stable=complete and all(value == available[0] for value in available),
                min=min(available) if numeric else None,
                max=max(available) if numeric else None,
                median=middle,
                frequencies=([dict(value=value, count=count) for value, count in sorted(Counter(available).items())]
                             if complete and not numeric else None)), complete, kinds


def _known_rule(rule, metric):
    if rule is None:
        return None
    if type(rule) is not dict or rule.get('metric') != metric:
        raise ValueError('A known deviation must name this exact metric, without wildcard matching')
    for key in ('id', 'source', 'explanation', 'evidence'):
        if type(rule.get(key)) is not str or not rule[key].strip():
            raise ValueError('Known deviations require explicit id, source, explanation and evidence')
    parsed = urlsplit(rule['source'])
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('A known deviation requires a source URL')
    return deepcopy(rule)


def classify_metric(metric_id, original, meitou, *, tolerance=0.0, units=None, known_deviation=None):
    """Classify one scalar metric; missing/null coverage is never zero or agreement.

    Observations are {repetition, snapshot: relative POSIX path, value, present?}.
    Values must be finite numbers, strings or booleans. With a stable original,
    every Meitou value must equal its reference within the explicit tolerance.
    Such a result is observed parity within tolerance, not bitwise identity;
    comparison_exact and each side's exact_stable retain that distinction.
    """
    if type(metric_id) is not str or not metric_id:
        raise ValueError('A nonempty metric identity is required')
    absolute = _tolerance(tolerance)
    rule = _known_rule(known_deviation, metric_id)
    original_rows, meitou_rows = _observations(original), _observations(meitou)
    left, left_complete, left_kinds = _summary(original_rows)
    right, right_complete, right_kinds = _summary(meitou_rows)
    right['outside_count'] = None
    reasons, warnings = [], []
    for name, summary in (('original', left), ('meitou', right)):
        if summary['n'] < 5:
            warnings.append(f'{name}: N={summary["n"]}; at least five repetitions are recommended')
        if summary['comparable_n'] != summary['n'] or not summary['n']:
            reasons.append(f'{name}: missing, null or unsupported coverage ({summary["comparable_n"]}/{summary["n"]})')
    same_kind = len(left_kinds | right_kinds) == 1
    if not same_kind or not left_complete or not right_complete:
        if not same_kind:
            reasons.append('Observation value types are unavailable or incompatible')
        classification, exact = 'not_comparable', False
    else:
        numeric = left_kinds == {'number'}
        values, candidates = left['values'], right['values']
        exact = left['exact_stable'] and all(value == values[0] for value in candidates)
        if numeric:
            outside = sum(value < left['min'] - absolute or value > left['max'] + absolute for value in candidates)
        else:
            outside = sum(value not in values for value in candidates)
        right['outside_count'] = outside
        if left['exact_stable']:
            agrees = (all(abs(value - values[0]) <= absolute for value in candidates) if numeric
                      else all(value == values[0] for value in candidates))
            classification = 'stable_identical' if agrees else 'stable_divergent'
        else:
            classification = 'variable_outside_range' if outside else 'variable_compatible'
    base = classification
    applied = rule is not None and base in ('stable_divergent', 'variable_outside_range')
    if applied:
        classification = 'known_deviation'
    return dict(metric=metric_id, classification=classification, base_classification=base,
                comparison_exact=exact, original=left, meitou=right,
                tolerance=dict(absolute=absolute, units=units), reasons=reasons, warnings=warnings,
                known_deviation=rule if applied else None)


def _saved_id(row, kind):
    identity = row.get('id')
    if row.get('identity_origin') != 'saved':
        return False
    try:
        validate_saved_handles([identity])
    except ValueError:
        return False
    return identity.startswith(f'hand:{kind}:')


def _escape(value):
    return value.replace('~', '~0').replace('/', '~1')


def _reference(value, proven, labels):
    # A setup alias label replaces its id; otherwise only a proven saved HAND is kept.
    if value is not None and value in labels:
        return labels[value]
    return value if value in proven else None


def _fields(state, row, labels=None):
    """Only proven references enter individual metrics; order semantics are not guessed.

    ``labels`` maps setup alias ids to their ``alias:`` label (scene scope), so a
    reference to an aliased character or squad never shows its raw engine id.
    """
    labels = labels or {}
    saved_characters = {r['id'] for r in state['characters'] if _saved_id(r, 1)}
    saved_squads = {r['id'] for r in state['squads'] if _saved_id(r, 34)}
    fields = {key: row.get(key) for key in ('name', 'race_id', 'faction_id', 'state',
                                         'current_town_id', 'town_assignment', 'in_combat')}
    fields['squad_id'] = _reference(row.get('squad_id'), saved_squads, labels)
    for index in range(3):
        fields[f'position/{index}'] = row['position'][index] if row.get('position') is not None else None
    health = row.get('health')
    fields['health/count'] = len(health) if health is not None else None
    for part in health or []:
        for field in ('current', 'stun', 'maximum'):
            fields[f'health/{_escape(part["id"])}/{field}'] = part[field]
    order = row.get('order')
    fields['order/type'] = order['type'] if order is not None else None
    fields['order/target_id'] = _reference(order['target_id'], saved_characters, labels) if order is not None else None
    for index in range(3):
        fields[f'order/position/{index}'] = (order['position'][index] if order is not None
                                          and order['position'] is not None else None)
    return fields


def character_fields(state, row, labels=None):
    """Individual fields of one character, references labelled as in ``_fields``."""
    return _fields(state, row, labels)


def saved_observations(original_states, meitou_states):
    """Observations of individual saved characters, without classification.

    Input rows are {repetition, snapshot: relative POSIX path, state, aliases?}.
    ``aliases`` (scene scope) maps setup alias ids to labels: those characters are
    left out here (the scene scope reports them) and references to them are
    replaced by their label. Returns [(metric, original rows, meitou rows,
    category)], or the single ``/coverage/saved_characters`` entry when no
    saved identity exists.
    """
    datasets, identities = [], set()
    for rows in (original_states, meitou_states):
        evidence = _observations([{key: row[key] for key in ('repetition', 'snapshot')} for row in rows])
        prepared = []
        for source, observation in zip(rows, evidence):
            state = source.get('state')
            labels = source.get('aliases') or {}
            mapped = {}
            if state is not None:
                validate_state(state)
                for row in state['characters']:
                    if _saved_id(row, 1) and row['id'] not in labels:
                        mapped[row['id']] = _fields(state, row, labels)
                identities.update(mapped)
            prepared.append((observation, mapped))
        datasets.append(prepared)
    if not identities:
        sides = [[dict(row, value=None, present=False, reason='No complete producer-proven saved character identity')
                  for row, _ in dataset] for dataset in datasets]
        return [('/coverage/saved_characters', *sides, 'number')]
    result = []
    for identity in sorted(identities):
        keys = set().union(*(mapping.get(identity, {}) for dataset in datasets for _, mapping in dataset))
        for field in sorted(keys):
            metric = '/characters/' + _escape(identity) + '/' + field
            sides = []
            for dataset in datasets:
                observations = []
                for observation, mapping in dataset:
                    fields = mapping.get(identity, {})
                    observations.append(dict(observation, present=field in fields, value=fields.get(field)))
                sides.append(observations)
            category = 'position' if field.startswith(('position/', 'order/position/')) else 'number'
            result.append((metric, *sides, category))
    return result


def saved_metrics(original_states, meitou_states, *, tolerances=None, known_deviations=None):
    """Compare individual characters only through full, producer-proven saved HANDs.

    Input rows are {repetition, snapshot: relative POSIX path, state}. A missing
    state can be None. Generated/unknown-origin characters are never paired by
    ID coincidence, name, position, faction or enumeration order. The report's
    separate aggregate path handles those populations. A single missing entity
    or field makes that individual metric non-comparable for the whole cohort.
    """
    limits = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    for value in limits.values():
        _tolerance(value)
    rules = known_deviations or {}
    if type(rules) is not dict:
        raise ValueError('known_deviations must map exact metric IDs to explicit evidence rules')
    observed = saved_observations(original_states, meitou_states)
    if len(observed) == 1 and observed[0][0] == '/coverage/saved_characters':
        return [classify_metric('/coverage/saved_characters', observed[0][1], observed[0][2])]
    findings = []
    for metric, left, right, category in observed:
        absolute = limits.get(metric, limits[category])
        findings.append(classify_metric(metric, left, right, tolerance=absolute,
            units='world_units' if category == 'position' else None, known_deviation=rules.get(metric)))
    return findings
