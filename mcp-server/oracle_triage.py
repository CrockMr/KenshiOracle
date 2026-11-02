"""Root-cause groups of divergent comparator findings (pure, deterministic).

This module reads no files. It adds to a computed comparison report a
permutation test per divergent finding, the groups those findings form, and
each finding's group id. Classifications are never changed. A divergent finding
is one whose base classification is ``stable_divergent`` or
``variable_outside_range``, known deviations included.

Grouping (docs/comparator.md#root-cause-groups):

1. One metric's divergent findings across checkpoints become one member, its
   checkpoints listed in time order (``whole_scenario`` after every checkpoint).
2. A member's entity is the smallest unit one cause plausibly explains:
   ``faction:<F>`` for ``/population/by_faction/<F>/``,
   ``/population/by_squad_template/<F>/`` and ``/combat/starting_cohort/<F>/``;
   ``squad:<id>`` for saved characters, ``/squads/<id>/`` and
   ``/trajectory/saved_squad/<id>/``; ``scene`` for ``/scene/``; otherwise
   ``family:/<a>/<b>`` (the first two path parts).
3. The disagreeing set is the Meitou repetitions whose value disagrees with the
   original at the member's first divergent checkpoint (stable: beyond the
   tolerance; variable: outside [min, max] widened by the tolerance).
4. The key is (entity, disagreeing set, onset, known-deviation status). Onset is
   ``load`` when the first divergent checkpoint is the scenario's earliest,
   else ``simulation``; the group's first checkpoint is its earliest member's.
5. A key whose disagreeing set is a proper subset of another key's set with the
   same entity, onset and status joins the smallest such superset key.
6. A whole-scenario trace member has no checkpoint of its own: it joins its
   entity's simulation key whose set contains its set, else the key of its
   metric family.

Rules 4 to 6 tune the spec's key (entity, disagreeing set, first divergent
checkpoint): on the real campaigns it split one squad's drift over every
checkpoint, every repetition subset and every trajectory into separate groups.

A character's squad is the most frequent non-null original value of its
``/characters/<id>/squad_id`` finding; without one it is the container part of
its saved handle (``hand:1:C:CS:I:S`` gives ``hand:34:C:CS:0:0``). Verified on
the esclaves-hold, ville-calme and ville-calme-clean-300 campaigns: every
character's recorded saved squad equals that container squad.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math

from oracle_stats import permutation_test, strength

FORMAT_VERSION = '0.3'
DIVERGENT = ('stable_divergent', 'variable_outside_range')
WHOLE_SCENARIO = 'whole_scenario'
_FACTION_PREFIXES = ('/population/by_faction/', '/population/by_squad_template/',
                     '/combat/starting_cohort/')
_SQUAD_PREFIXES = ('/squads/', '/trajectory/saved_squad/')


def is_divergent(finding):
    return finding.get('base_classification', finding['classification']) in DIVERGENT


def checkpoint_times(report, findings=()):
    """{checkpoint name: at}; ``whole_scenario`` and unknown names sort last."""
    times = {point['name']: point['at'] for point in (report.get('scenario') or {}).get('checkpoints', [])}
    for finding in findings:
        times.setdefault(finding['checkpoint'], math.inf)
    return times


def chronological(times):
    """Sort key of a finding or row: checkpoint time, checkpoint name, metric."""
    return lambda row: (times.get(row['checkpoint'], math.inf), row['checkpoint'], row['metric'])


def disagreeing(finding):
    """Meitou repetitions outside the original reference, as classify_metric counts them."""
    left, tolerance = finding['original'], finding['tolerance']['absolute']
    values, numeric = left['values'], left.get('min') is not None
    result = []
    for row in finding['meitou']['observations']:
        value = row['value']
        if left['exact_stable']:
            differs = abs(value - values[0]) > tolerance if numeric else value != values[0]
        else:
            differs = (value < left['min'] - tolerance or value > left['max'] + tolerance) if numeric \
                else value not in values
        if differs:
            result.append(row['repetition'])
    return sorted(result)


def _container_squad(handle):
    parts = handle.split(':')
    if len(parts) == 6 and parts[0] == 'hand' and parts[1] == '1':
        return ':'.join(('hand', '34', parts[2], parts[3], '0', '0'))
    return None


def character_squads(findings):
    """{character id path part: squad id} from the original's recorded squad_id values."""
    counts = defaultdict(Counter)
    for finding in findings:
        parts = finding['metric'].split('/')
        if len(parts) == 4 and parts[1] == 'characters' and parts[3] == 'squad_id':
            counts[parts[2]].update(value for value in finding['original']['values'] if type(value) is str)
    return {character: min(counter.items(), key=lambda item: (-item[1], item[0]))[0]
            for character, counter in counts.items() if counter}


def entity(metric, squads=None):
    """Entity label of a metric (see the module docstring)."""
    parts = metric.split('/')
    if metric.startswith('/scene/'):
        return 'scene'
    for prefix in _FACTION_PREFIXES:
        if metric.startswith(prefix) and len(parts) > 4:
            return 'faction:' + parts[3]
    for prefix in _SQUAD_PREFIXES:
        if metric.startswith(prefix) and len(parts) > prefix.count('/') + 1:
            return 'squad:' + parts[prefix.count('/')]
    if metric.startswith('/characters/') and len(parts) > 3:
        squad = (squads or {}).get(parts[2]) or _container_squad(parts[2].replace('~1', '/').replace('~0', '~'))
        if squad is not None:
            return 'squad:' + squad
    return 'family:' + '/'.join(parts[:3])


def _digest(key):
    return hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).hexdigest()[:8]


def triage(report):
    """Add tests, groups and per-finding group ids to ``report``; return its groups.

    Deterministic: two runs on one report give the same groups, ids and order.
    """
    findings = report['findings']
    times = checkpoint_times(report, findings)
    order = sorted(times, key=lambda name: (times[name], name))
    earliest = order[0] if order else None
    squads = character_squads(findings)
    by_metric = defaultdict(list)
    for finding in findings:
        finding['group'] = None
        if not is_divergent(finding):
            finding.pop('test', None)
            finding.pop('strength', None)
            continue
        finding['test'] = permutation_test(finding['original']['values'], finding['meitou']['values'])
        finding['strength'] = strength(finding['test']['p_value'])
        by_metric[finding['metric']].append(finding)
    grouped, keyed = defaultdict(list), []
    for metric, rows in by_metric.items():
        rows.sort(key=chronological(times))
        first = rows[0]
        tested = min(rows, key=lambda row: (row['test']['p_value'] is None, row['test']['p_value'] or 0,
                                            times[row['checkpoint']], row['checkpoint']))
        known = all(row['classification'] == 'known_deviation' for row in rows)
        member = dict(metric=metric, checkpoints=[row['checkpoint'] for row in rows],
                      first_checkpoint=first['checkpoint'], classification=first['base_classification'],
                      disagreeing_repetitions=disagreeing(first), test_checkpoint=tested['checkpoint'],
                      p_value=tested['test']['p_value'], strength=tested['strength'], known_deviation=known)
        member['entity'] = entity(metric, squads)
        keyed.append((member, rows))
    # Rules 4 to 6 of the module docstring.
    def onset_of(checkpoint):
        return 'load' if checkpoint == earliest and checkpoint != WHOLE_SCENARIO else 'simulation'
    def root(key, keys):
        supersets = [other for other in keys if other[0] == key[0] and other[2:] == key[2:]
                     and set(key[1]) < set(other[1])]
        return min(supersets, key=lambda other: (len(other[1]), other)) if supersets else key
    exact = {}
    for member, rows in keyed:
        if member['first_checkpoint'] != WHOLE_SCENARIO:
            exact[member['metric']] = (member['entity'], tuple(member['disagreeing_repetitions']),
                                       onset_of(member['first_checkpoint']), member['known_deviation'])
    keys = set(exact.values())
    roots = {key: root(key, keys) for key in keys}
    for member, rows in keyed:
        name = member.pop('entity')
        key = exact.get(member['metric'])
        if key is None:
            key = (name, tuple(member['disagreeing_repetitions']), 'simulation', member['known_deviation'])
            if key not in keys:
                found = root(key, keys)
                key = found if found != key else ('family:' + '/'.join(member['metric'].split('/')[:3]),) + key[1:]
        grouped[json.dumps(roots.get(key, key))].append((member, rows))
    groups = []
    for text, entries in grouped.items():
        entity_name, repetitions, onset, known = json.loads(text)
        members = sorted((member for member, _ in entries), key=lambda member: member['metric'])
        checkpoint = min((member['first_checkpoint'] for member in members),
                         key=lambda name: (times[name], name))
        headline = min(members, key=lambda member: (member['p_value'] is None, member['p_value'] or 0,
                                                    times[member['test_checkpoint']], member['metric']))
        groups.append(dict(key=dict(entity=entity_name, disagreeing_repetitions=repetitions, onset=onset),
                           entity=entity_name, disagreeing_repetitions=repetitions,
                           first_checkpoint=dict(name=checkpoint, at=None if times[checkpoint] == math.inf
                                                 else times[checkpoint]),
                           onset=onset, known_deviation=known, strength=headline['strength'] or 'weak',
                           p_value=headline['p_value'], size=len(members),
                           headline=dict(metric=headline['metric'], checkpoint=headline['test_checkpoint'],
                                         p_value=headline['p_value']),
                           members=members, _rows=[row for _, rows in entries for row in rows],
                           _digest=_digest([entity_name, repetitions, onset, known])))
    groups.sort(key=lambda group: (group['known_deviation'], group['strength'] != 'strong',
                                   -group['size'] * len(group['disagreeing_repetitions']),
                                   group['onset'] != 'load', group['entity'],
                                   group['disagreeing_repetitions']))
    for index, group in enumerate(groups, 1):
        group['id'] = f'g{index:03d}-' + group.pop('_digest')
        group['drafted'] = group['strength'] == 'strong' and not group['known_deviation']
        for row in group.pop('_rows'):
            row['group'] = group['id']
    report['groups'] = groups
    report['format_version'] = FORMAT_VERSION
    return groups
