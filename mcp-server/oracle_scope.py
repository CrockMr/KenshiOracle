"""Scene scope for scenario-0.2 campaigns (docs/scene-setup.md, comparator).

This module is pure: it reads no files and never contacts either game. The
campaign loader certifies each setup receipt before these helpers run.

Characters in scope at a checkpoint are the alias ids, the player ids and every
character whose X/Z distance to ``scene_center`` is at most ``scene_radius``.
Only ``/scene/`` metrics are classified: alias presence and missing counts,
``/scene/intruders/count`` and the declared relation pairs in both directions.
``/scene/outcome/`` metrics (cohort survivors, dead, unconscious, health and
engagement) are reported per repetition and never classified. Everything else
is background, recorded and never classified. Spawned members are interchangeable:
they enter metrics only as (spawn alias, template) aggregates, never by id or by
their index in a reply.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from oracle_compare import character_fields


RECEIPT_FORMAT = 'scene-setup-0.1'
SCENE_PREFIX = '/scene/'
OUTCOME_PREFIX = '/scene/outcome/'
BACKGROUND_PREFIX = '/background'
PLAYER_COHORT = 'player'
_PLAYER_ALIAS = re.compile(r'player(?:/([1-9][0-9]*))?')
_MEMBER_ALIAS = re.compile(r'([a-z][a-z0-9-]{0,31})/([A-Za-z0-9][A-Za-z0-9._-]{0,127})/([1-9][0-9]*)')
_MAX_PLAYER_CHARACTERS = 64


def escaped(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def setup_hash(setup):
    """The receipt's ``setup_hash`` rule, recomputed from ``scenario['setup']``."""
    text = json.dumps(setup, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def metric_scope(metric):
    """Return 'scene' (classified), 'outcome' or 'background' (never classified)."""
    if metric.startswith(OUTCOME_PREFIX):
        return 'outcome'
    if metric.startswith(SCENE_PREFIX):
        return 'scene'
    return 'background'


def scene_scope(scenario):
    """Static scope of a scenario, or None when it has no setup block."""
    setup = scenario.get('setup')
    if setup is None:
        return None
    preflight = setup['preflight']
    spawns = {spawn['alias']: dict(spawn['expected_templates']) for spawn in setup['spawns']}
    members = {f'{alias}/{template}/{index}'
               for alias, templates in spawns.items()
               for template, count in templates.items() for index in range(1, count + 1)}
    pairs = []
    for relation in setup['relations']:
        for cell in ((relation['a'], relation['b']), (relation['b'], relation['a'])):
            if cell not in pairs:
                pairs.append(cell)
    return dict(center=tuple(preflight['scene_center']), radius=preflight['scene_radius'],
                spawns=spawns, declared=frozenset(spawns) | frozenset(members), pairs=tuple(pairs))


def player_aliases(keys):
    """Player alias keys of an alias map: exactly ``player`` or ``player/1..n`` (n >= 2)."""
    players = sorted((key for key in keys if _PLAYER_ALIAS.fullmatch(key)),
                     key=lambda key: 0 if key == 'player' else int(key.split('/')[1]))
    if players == ['player']:
        return players
    expected = [f'player/{index}' for index in range(1, len(players) + 1)]
    if len(players) < 2 or len(players) > _MAX_PLAYER_CHARACTERS or players != expected:
        raise ValueError('Setup alias map must bind player or player/1..n')
    return players


def validate_alias_map(alias_map, scope):
    """Check an execution's alias map against the declared alias set."""
    if (type(alias_map) is not dict or not alias_map
            or any(type(key) is not str or type(value) is not str or not value
                   for key, value in alias_map.items())):
        raise ValueError('Setup alias map must map alias names to ids')
    players = player_aliases(alias_map)
    if set(alias_map) - set(players) != scope['declared']:
        raise ValueError('Setup alias map differs from the declared alias set')
    characters = [alias_map[key] for key in alias_map if key not in scope['spawns']]
    if len(set(characters)) != len(characters):
        raise ValueError('Setup alias map binds one character to several aliases')
    return players


def cohorts(alias_map, scope):
    """Return {cohort path: [ids]}: ``player`` and ``<spawn>/<template>`` aggregates."""
    result = {PLAYER_COHORT: [alias_map[key] for key in player_aliases(alias_map)]}
    for alias, templates in scope['spawns'].items():
        for template, count in templates.items():
            result[escaped(alias) + '/' + escaped(template)] = [
                alias_map[f'{alias}/{template}/{index}'] for index in range(1, count + 1)]
    return result


def labels(alias_map, scope):
    """Map ids to the label used in values: players by alias, members by aggregate."""
    result = {}
    for key, identity in alias_map.items():
        member = _MEMBER_ALIAS.fullmatch(key)
        if member is not None and member.group(1) in scope['spawns']:
            result[identity] = 'alias:' + member.group(1) + '/' + member.group(2)
        else:
            result[identity] = 'alias:' + key
    return result


def _distance_xz(position, center):
    if (type(position) is not list or len(position) != 3
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in position)):
        return None
    return math.hypot(position[0] - center[0], position[2] - center[1])


def scene_metrics(state, alias_map, scope):
    """Per-checkpoint ``/scene/`` and ``/scene/outcome/`` metrics of one repetition."""
    characters = {row['id']: row for row in state['characters']}
    squads = {row['id'] for row in state['squads']}
    groups = cohorts(alias_map, scope)
    in_cohort = {identity for members in groups.values() for identity in members}
    values = {}
    for alias in sorted(scope['spawns']):
        values[f'/scene/squads/{escaped(alias)}/present'] = alias_map[alias] in squads
    for name, members in sorted(groups.items()):
        rows = [characters.get(identity) for identity in members]
        prefix = '/scene/cohort/' + name
        values[prefix + '/size'] = len(members)
        values[prefix + '/present'] = sum(row is not None for row in rows)
        values[prefix + '/missing'] = sum(row is None for row in rows)
        outcome = '/scene/outcome/cohort/' + name
        complete = all(row is not None and row['state'] is not None for row in rows)
        values[outcome + '/survivors'] = sum(row['state'] != 'dead' for row in rows) if complete else None
        values[outcome + '/dead'] = sum(row['state'] == 'dead' for row in rows) if complete else None
        values[outcome + '/unconscious'] = sum(row['state'] == 'unconscious' for row in rows) if complete else None
        healthy = all(row is not None and row.get('health') is not None for row in rows)
        for field in ('current', 'stun', 'maximum'):
            parts = [part[field] for row in rows for part in row['health']] if healthy else [None]
            values[outcome + '/health/' + field + '_total'] = (
                sum(parts) if all(value is not None for value in parts) else None)
    intruders, known = 0, True
    for identity, row in characters.items():
        if identity in in_cohort:
            continue
        distance = _distance_xz(row.get('position'), scope['center'])
        if distance is None:
            known = False
        elif distance <= scope['radius']:
            intruders += 1
    values['/scene/intruders/count'] = intruders if known else None
    names = labels(alias_map, scope)
    for alias in player_aliases(alias_map):
        row = characters.get(alias_map[alias])
        if row is not None:
            for field, value in character_fields(state, row, names).items():
                values['/scene/outcome/characters/' + escaped('alias:' + alias) + '/' + field] = value
    relations = {(row['source_id'], row['target_id']): row['value'] for row in state['relations']}
    for source, target in scope['pairs']:
        if (source, target) in relations:
            values[f'/scene/relations/{escaped(source)}/{escaped(target)}/value'] = relations[(source, target)]
    return values


def background_baseline(baseline, alias_map, scope):
    """The first checkpoint without the alias and player cohorts (faction cohorts outside them)."""
    excluded = {identity for members in cohorts(alias_map, scope).values() for identity in members}
    return dict(baseline, characters=[row for row in baseline['characters'] if row['id'] not in excluded])


def is_pair_relation_metric(metric, scope):
    """True for an unscoped ``/relations/<a>/<b>/...`` metric on a declared pair."""
    return any(metric.startswith(f'/relations/{escaped(source)}/{escaped(target)}/')
               for source, target in scope['pairs'])


def limitations():
    return [
        'Scene scope: only /scene/ metrics (alias presence and missing counts, /scene/intruders/count and the '
        'declared relation pairs in both directions) are classified; /scene/outcome/ metrics (cohort survivors, dead, '
        'unconscious, health and engagement) are reported per repetition in scene_outcome, and background metrics '
        '(population, clock, every other relation, saved characters and traces outside the alias and player cohorts) '
        'are recorded in background_metrics; outcome and background metrics are not classified.',
        'Spawned members are compared only as (spawn alias, template) aggregates; setup member maxima are reported '
        'per repetition in setup_members as facts, with no verdict on the fight outcome.']
