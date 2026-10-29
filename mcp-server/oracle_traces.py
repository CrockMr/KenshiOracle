"""Conservative trajectory and engagement observations from sparse checkpoints.

No interpolation, extra game ticks or wall-clock timing is introduced. Polyline
length is an observed lower bound, displacement is a distinct measure, and a
first sampled arrival never establishes its exact time. Engagement span does
not establish continuous or cumulative combat duration.
"""
from __future__ import annotations

from collections import defaultdict
import math

from oracle_identity import validate_saved_handles


def _saved(row, kind):
    if row.get('identity_origin') != 'saved':
        return False
    try:
        validate_saved_handles([row.get('id')])
    except ValueError:
        return False
    return row['id'].startswith(f'hand:{kind}:')


def _escape(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def _position(row):
    value = row.get('position') if row is not None else None
    if (type(value) is not list or len(value) != 3
            or any(type(component) not in (int, float) or not math.isfinite(component)
                   or abs(component) > 1e9 for component in value)):
        return None
    return tuple(value)


def _time(row):
    value = row.get('capture', {}).get('actual_at') if row is not None else None
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _characters(row):
    return {character['id']: character for character in row['state']['characters']} if row is not None else {}


def _paths(timeline, cohort):
    if not cohort:
        return None
    result = {identity: [] for identity in cohort}
    for row in timeline:
        characters = _characters(row)
        for identity in cohort:
            position = _position(characters.get(identity))
            if position is None:
                return None
            result[identity].append(position)
    return result


def _trajectory(values, prefix, timeline, cohort):
    fields = ('final_position/x', 'final_position/y', 'final_position/z',
              'observed_polyline_distance_mean_lower_bound', 'net_displacement_mean')
    paths = _paths(timeline, cohort)
    for field in fields:
        values[prefix + '/' + field] = None
    if paths is None:
        return
    for index, axis in enumerate(('x', 'y', 'z')):
        values[prefix + '/final_position/' + axis] = sum(path[-1][index] for path in paths.values()) / len(paths)
    values[prefix + '/observed_polyline_distance_mean_lower_bound'] = sum(
        sum(math.dist(first, second) for first, second in zip(path, path[1:])) for path in paths.values()) / len(paths)
    values[prefix + '/net_displacement_mean'] = sum(
        math.dist(path[0], path[-1]) for path in paths.values()) / len(paths)


def _arrival(values, prefix, timeline, cohort, action, radius):
    values.update({prefix + '/' + field: None for field in ('arrival_observed', 'first_observed_at',
        'arrival_time_lower_bound', 'arrival_time_upper_bound', 'exact_arrival_time')})
    destination = _position({'position': action.get('params', {}).get('position')})
    if destination is None or _paths(timeline, cohort) is None or any(_time(row) is None for row in timeline):
        return
    eligible = [row for row in timeline if _time(row) >= action['at']]
    if not eligible:
        return
    # A centroid alone could lie at the destination while every member is far away.
    observed = [row for row in eligible if all(
        math.hypot(_position(_characters(row)[identity])[0] - destination[0],
                   _position(_characters(row)[identity])[2] - destination[2]) <= radius for identity in cohort)]
    values[prefix + '/arrival_observed'] = bool(observed)
    if observed:
        first = _time(observed[0])
        values[prefix + '/first_observed_at'] = first
        # Scenario-relative bounds: no assertion that the previous photo excluded
        # an earlier arrival/departure/rearrival between observations.
        values[prefix + '/arrival_time_lower_bound'] = 0
        values[prefix + '/arrival_time_upper_bound'] = first


def _engagement(values, prefix, timeline, cohort):
    known_true, complete = [], bool(cohort)
    times = [_time(row) for row in timeline]
    for row, instant in zip(timeline, times):
        characters = _characters(row)
        flags = [characters.get(identity, {}).get('in_combat') for identity in cohort]
        if instant is not None and any(flag is True for flag in flags):
            known_true.append(instant)
        if instant is None or any(type(flag) is not bool for flag in flags):
            complete = False
    values[prefix + '/engagement_observed'] = True if known_true else False if complete else None
    values[prefix + '/first_observed_at'] = min(known_true) if known_true else None
    values[prefix + '/last_observed_at'] = max(known_true) if known_true else None
    values[prefix + '/observed_span_seconds'] = max(known_true) - min(known_true) if known_true else None
    values[prefix + '/duration_seconds'] = None
    # These bounds concern engagement inside the sampled window only. Total fight
    # duration may begin before it or end after it, and has no finite upper bound.
    values[prefix + '/window_duration_lower_bound'] = 0 if all(t is not None for t in times) else None
    values[prefix + '/window_duration_upper_bound'] = times[-1] - times[0] if all(t is not None for t in times) else None


def trace_metrics(campaign, arrival_radius=5.0):
    """Return {repetition: {metric: scalar|null}} for a validated campaign.

    Saved squads use full type-34 HANDs and the fixed loaded membership of the
    first checkpoint. Move arrivals require the entire initial actor cohort in
    the destination's X/Z radius; no observation means only "not observed".
    Missing positions censor every trajectory/arrival metric for that cohort.
    Faction engagement tracks each repetition's own initial loaded cohort, never
    matches generated individuals across games, and preserves unknown booleans.
    """
    if (type(arrival_radius) not in (int, float) or not math.isfinite(arrival_radius)
            or arrival_radius < 0 or arrival_radius > 1e9):
        raise ValueError('arrival_radius must be a finite nonnegative world-space distance <= 1e9')
    points = sorted(campaign['scenario']['checkpoints'], key=lambda point: point['at'])
    if not points:
        return {}
    indexed, repetitions = {}, set()
    for point in points:
        rows = {}
        for row in campaign['checkpoints'].get(point['name'], []):
            repetition = row['repetition']
            if type(repetition) is not int or repetition < 1 or repetition in rows:
                raise ValueError('Trace checkpoints require unique positive integer repetitions')
            rows[repetition] = row
            repetitions.add(repetition)
        indexed[point['name']] = rows
    output = {}
    for repetition in sorted(repetitions):
        timeline = [indexed[point['name']].get(repetition) for point in points]
        times = [_time(row) for row in timeline]
        known_times = [instant for instant in times if instant is not None]
        if known_times != sorted(known_times):
            raise ValueError('Trace checkpoint observations must have nondecreasing actual times')
        values = {}
        output[repetition] = values
        baseline = timeline[0]
        if baseline is None:
            values['/trace/initial_cohort_coverage'] = None
            continue
        squads = {row['id']: row for row in baseline['state']['squads'] if _saved(row, 34)}
        saved_characters = {row['id'] for row in baseline['state']['characters'] if _saved(row, 1)}
        for identity, squad in sorted(squads.items()):
            _trajectory(values, '/trajectory/saved_squad/' + _escape(identity), timeline, squad['members'])
        for index, action in enumerate(campaign['scenario'].get('actions', [])):
            params = action.get('params', {})
            if action.get('command') != 'issue_order' or params.get('type') != 'move':
                continue
            cohort = (squads.get(params.get('squad_id'), {}).get('members', []) if 'squad_id' in params
                      else [params['character_id']] if params.get('character_id') in saved_characters else [])
            _arrival(values, '/trajectory/move_action/' + str(index), timeline, cohort, action, arrival_radius)
        factions = defaultdict(list)
        for character in baseline['state']['characters']:
            if character.get('faction_id') is not None:
                factions[character['faction_id']].append(character['id'])
        for faction, cohort in sorted(factions.items()):
            _engagement(values, '/combat/engagement_by_faction/' + _escape(faction), timeline, cohort)
    return output
