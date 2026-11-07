"""Live comparison of one original snapshot and one MeitouClient snapshot.

This module is pure: it reads no files and never contacts either game. It pairs
characters by complete saved handle only, with the same projection as the
campaign comparator (``oracle_compare.character_fields``), so a live
difference names the same field as a campaign metric. A single pair of
snapshots is one observation: it shows where two runs stand, not whether a
difference is stable, variable or a known deviation. Campaigns classify.
"""
from __future__ import annotations

from collections import Counter
import math

from oracle_compare import DEFAULT_TOLERANCES, _saved_id, character_fields
from oracle_schema import validate_state

TARGETS = ('original', 'meitou')
MAX_LIMIT = 500


def _is_position(key):
    return key.startswith('position/') or key.startswith('order/position/')


def _equal(key, left, right, position_tolerance):
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if _is_position(key):
            return math.isclose(left, right, rel_tol=0.0, abs_tol=position_tolerance)
        return left == right
    return left == right


def _selected(key, fields):
    return not fields or any(key == prefix or key.startswith(prefix + '/') for prefix in fields)


def _check_options(fields, limit, position_tolerance):
    if fields is not None and (not isinstance(fields, list) or not all(isinstance(f, str) and f for f in fields)):
        raise ValueError('fields must be a list of non-empty field prefixes, such as ["goal", "order/type"]')
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f'limit must be an integer from 1 to {MAX_LIMIT}')
    if (type(position_tolerance) not in (int, float) or not math.isfinite(position_tolerance)
            or position_tolerance < 0):
        raise ValueError('position_tolerance must be a nonnegative finite number')


def _saved_rows(state):
    return {row['id']: row for row in state['characters'] if _saved_id(row, 1)}


def _clocks(original, meitou):
    left = original['clock']['elapsed_seconds']
    right = meitou['clock']['elapsed_seconds']
    return dict(original=original['clock'], meitou=meitou['clock'], meitou_minus_original_seconds=right - left)


def _validated_pair(original, meitou):
    validate_state(original)
    validate_state(meitou)
    if original['schema_version'] != meitou['schema_version']:
        raise ValueError('The two snapshots use different state schemas: %s and %s'
                         % (original['schema_version'], meitou['schema_version']))


def compare_states(original, meitou, *, fields=None, limit=20, position_tolerance=None):
    """Differences of saved characters present in both snapshots.

    A null on one side is unknown, never a value: such a field is counted under
    ``not_comparable`` and never listed as a difference.
    """
    tolerance = DEFAULT_TOLERANCES['position'] if position_tolerance is None else position_tolerance
    _check_options(fields, limit, tolerance)
    _validated_pair(original, meitou)
    left, right = _saved_rows(original), _saved_rows(meitou)
    paired = sorted(left.keys() & right.keys())
    divergent, unknown, differences = Counter(), Counter(), []
    for identity in paired:
        a = character_fields(original, left[identity])
        b = character_fields(meitou, right[identity])
        changed = {}
        for key in sorted(a.keys() | b.keys()):
            if not _selected(key, fields):
                continue
            if key not in a or key not in b or a[key] is None or b[key] is None:
                if not (key in a and key in b and a[key] is None and b[key] is None):
                    unknown[key] += 1
                continue
            if not _equal(key, a[key], b[key], tolerance):
                changed[key] = dict(original=a[key], meitou=b[key])
        divergent.update(changed.keys())
        if changed:
            differences.append(dict(id=identity, name=left[identity].get('name'), fields=changed))
    only_original = sorted(left.keys() - right.keys())
    only_meitou = sorted(right.keys() - left.keys())
    return dict(
        schema_version=original['schema_version'],
        clock=_clocks(original, meitou),
        filter=fields,
        position_tolerance=tolerance,
        counts=dict(original_characters=len(original['characters']), meitou_characters=len(meitou['characters']),
                    saved_original=len(left), saved_meitou=len(right), paired=len(paired),
                    paired_with_differences=len(differences), only_original=len(only_original),
                    only_meitou=len(only_meitou)),
        divergent_fields=[dict(field=key, pairs=count) for key, count in
                          sorted(divergent.items(), key=lambda item: (-item[1], item[0]))],
        not_comparable_fields=[dict(field=key, pairs=count) for key, count in
                               sorted(unknown.items(), key=lambda item: (-item[1], item[0]))],
        differences=differences[:limit],
        differences_truncated=len(differences) > limit,
        only_original=[dict(id=i, name=left[i].get('name')) for i in only_original[:limit]],
        only_meitou=[dict(id=i, name=right[i].get('name')) for i in only_meitou[:limit]],
        note='One pair of snapshots is one observation; campaigns classify stability.')


def inspect_states(original, meitou, saved_id):
    """One saved character or squad from both snapshots, raw rows side by side."""
    if not isinstance(saved_id, str) or not saved_id.startswith('hand:'):
        raise ValueError('saved_id must be a complete saved handle, such as hand:1:...')
    _validated_pair(original, meitou)
    kind, collection = (1, 'characters') if saved_id.startswith('hand:1:') else (34, 'squads')
    rows = {}
    for target, state in zip(TARGETS, (original, meitou)):
        rows[target] = next((row for row in state[collection]
                             if row.get('id') == saved_id and _saved_id(row, kind)), None)
    result = dict(saved_id=saved_id, collection=collection, clock=_clocks(original, meitou),
                  original=rows['original'], meitou=rows['meitou'])
    if collection == 'characters' and rows['original'] is not None and rows['meitou'] is not None:
        a, b = character_fields(original, rows['original']), character_fields(meitou, rows['meitou'])
        result['differing_fields'] = sorted(
            key for key in a.keys() | b.keys()
            if a.get(key) is not None and b.get(key) is not None
            and not _equal(key, a[key], b[key], DEFAULT_TOLERANCES['position']))
    return result
