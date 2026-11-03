"""Export owned synthetic cross-language oracle canonical fixtures (no game data).

The first 59 cases reproduce runtime/oracle-phase1/check-native-canonical.py
exactly. Their concatenated expected UTF-8 hash is retained as a regression pin.
Run with the project's Python environment; no game or native build is launched.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'mcp-server'), str(ROOT / 'tests')]
from fake_probe import sample_state
from oracle_schema import STATS_KEYS, _check_json_values, _encode, canonical_bytes, validate_state


def vectors():
    numbers = [0.0, -0.0, .00000049, -.00000049, .0000005, -.0000005,
               .0000015, -.0000015, 1.2345675, -1.2345675, 1, 1.23,
               999999999.999999, -999999999.999999, 1e9, -1e9,
               216000.1234565, -216000.1234565]
    cases = []
    for number in numbers:
        for label, value in [('exact', number), ('next-down', math.nextafter(number, -math.inf)),
                             ('next-up', math.nextafter(number, math.inf))]:
            if abs(value) > 1e9:
                continue
            state = sample_state()
            state['characters'][0]['position'] = [value, value, value]
            cases.append((f'number-{number!r}-{label}', 'state', state))
    for index, value in enumerate([''.join(map(chr, range(32))), '"\\/',
                                    'Éclaireur 雪 🚀', '\u2028\u2029', 'a\x7fb', '']):
        state = sample_state()
        state['characters'][0]['name'] = value
        cases.append((f'string-{index}', 'state', state))
    state = sample_state()
    for character in state['characters']:
        character.update(health=None, order=None, race_id=None, state=None)
    cases.append(('nullable-state', 'state', state))
    assert len(cases) == 59
    # Astral U+10000 sorts after BMP U+E000 in Python/UTF-8, unlike UTF-16 ordinal.
    cases.append(('unicode-scalar-object-key-order', 'json', {'\U00010000': 'astral', '\ue000': 'bmp'}))
    state = sample_state()
    for row in state['characters']:
        row.update(identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=False)
    for row in state['squads']:
        row.update(identity_origin='saved', template_id='fixture-template', origin_town_id=None)
    state['schema_version'] = '0.2'
    cases.append(('additive-state-02', 'state', state))
    permuted = deepcopy(state)
    for key in ('characters', 'squads', 'factions', 'relations'):
        permuted[key].reverse()
    for row in permuted['squads']:
        row['members'].reverse()
    cases.append(('state-02-permutation', 'state', permuted))
    # State 0.3: the 0.2 case plus the two slave fields; null is unknown coverage.
    state = deepcopy(state)
    state['schema_version'] = '0.3'
    state['characters'][0].update(slave_state='escaping_slave', slave_owner_faction_id='fixture-owner')
    state['characters'][1].update(slave_state=None, slave_owner_faction_id=None)
    cases.append(('additive-state-03', 'state', state))
    permuted = deepcopy(state)
    for key in ('characters', 'squads', 'factions', 'relations'):
        permuted[key].reverse()
    for row in permuted['squads']:
        row['members'].reverse()
    cases.append(('state-03-permutation', 'state', permuted))
    state = deepcopy(state)
    state['characters'][0].update(slave_state='not_slave', slave_owner_faction_id=None)
    state['characters'][1].update(slave_state='ex_slave', slave_owner_faction_id='fixture-faction')
    cases.append(('state-03-not-slave-and-ex-slave', 'state', state))
    # State 0.4: the last 0.3 case plus medical, stats, use-stuff, carrying, part
    # bandage/splint/wear and squad money; null is unknown coverage.
    state = deepcopy(state)
    state['schema_version'] = '0.4'
    first, second = state['characters'][0]['id'], state['characters'][1]['id']
    state['characters'][0].update(
        medical=dict(blood=97.5, bleed_rate=0.125, hunger=2.25, fed=1.5, coma=False, blood_loss_trauma=True),
        stats={key: index + 0.5 for index, key in enumerate(STATS_KEYS)},
        in_something='bed', carrying='character', carrying_id=second, being_carried=False)
    state['characters'][1].update(
        medical=dict(blood=None, bleed_rate=-0.0000005, hunger=0, fed=None, coma=None, blood_loss_trauma=False),
        stats={key: None if index % 2 else -1.2345675 for index, key in enumerate(STATS_KEYS)},
        in_something='prison', carrying='nothing', carrying_id=None, being_carried=True)
    for row in state['characters']:
        for part in row['health']:
            part.update(bandage=12.5, splint=0, wear=3.000001)
    for row in state['squads']:
        row.update(money=123456)
    cases.append(('additive-state-04', 'state', state))
    permuted = deepcopy(state)
    for key in ('characters', 'squads', 'factions', 'relations'):
        permuted[key].reverse()
    for row in permuted['squads']:
        row['members'].reverse()
    for row in permuted['characters']:
        row['stats'] = {key: value for key, value in reversed(list((row['stats'] or {}).items()))}
        row['medical'] = {key: value for key, value in reversed(list(row['medical'].items()))}
    cases.append(('state-04-permutation', 'state', permuted))
    state = deepcopy(state)
    state['characters'][0].update(medical=None, stats=None, in_something=None, carrying='other', carrying_id=None,
                                  being_carried=None)
    state['characters'][1].update(in_something='nothing', carrying=None, carrying_id=None)
    for row in state['characters']:
        for part in row['health']:
            part.update(bandage=None, splint=None, wear=None)
    for row in state['squads']:
        row.update(money=None)
    cases.append(('state-04-nulls-other-and-nothing', 'state', state))
    state = deepcopy(state)
    state['characters'][0].update(health=None, carrying='nothing', in_something='bed')
    state['characters'][1].update(medical=dict(blood=1e9, bleed_rate=-1e9, hunger=None, fed=None, coma=True,
                                               blood_loss_trauma=None),
                                  stats={key: 0 for key in STATS_KEYS}, carrying='character', carrying_id=first)
    for row in state['squads']:
        row.update(money=-1000000000)
    cases.append(('state-04-edges', 'state', state))
    # State 0.5: the last 0.4 case plus the current AI goal; Task_Blank rows such
    # as wander_town are goals, null is unknown coverage or no current goal.
    state = deepcopy(state)
    state['schema_version'] = '0.5'
    state['characters'][0].update(goal=dict(type='melee_attack', priority='urgent', target_id=second))
    state['characters'][1].update(goal=dict(type='wander_town', priority='fluff', target_id=None))
    cases.append(('additive-state-05', 'state', state))
    permuted = deepcopy(state)
    for key in ('characters', 'squads', 'factions', 'relations'):
        permuted[key].reverse()
    for row in permuted['squads']:
        row['members'].reverse()
    for row in permuted['characters']:
        row['goal'] = {key: value for key, value in reversed(list(row['goal'].items()))}
    cases.append(('state-05-permutation', 'state', permuted))
    state = deepcopy(state)
    state['characters'][0].update(goal=dict(type='idle', priority='just_action', target_id=None))
    state['characters'][1].update(goal=dict(type='job_medic', priority='non_urgent', target_id=first))
    cases.append(('state-05-just-action-and-non-urgent', 'state', state))
    state = deepcopy(state)
    state['characters'][0].update(goal=dict(type='man_the_gate', priority='obedience', target_id=second))
    state['characters'][1].update(goal=dict(type='wander_town', priority=None, target_id=None))
    cases.append(('state-05-obedience-and-null-priority', 'state', state))
    state = deepcopy(state)
    state['characters'][0].update(goal=None)
    cases.append(('state-05-null-goal', 'state', state))
    return cases


def main():
    rows, legacy = [], bytearray()
    for index, (name, kind, value) in enumerate(vectors()):
        _check_json_values(value)
        if kind == 'state' and value['schema_version'] in ('0.4', '0.5'):
            validate_state(value)
        encoded = canonical_bytes(value) if kind == 'state' else (_encode(value) + '\n').encode('utf-8')
        if index < 59:
            legacy.extend(encoded)
        rows.append(dict(name=name, kind=kind, input=value,
                         expected_base64=base64.b64encode(encoded).decode('ascii'),
                         expected_sha256=hashlib.sha256(encoded).hexdigest()))
    pinned = '413a593b4b2378ecffdba277942ed6ef0797302667a1f02e39260ff5c7b8fab7'
    assert hashlib.sha256(legacy).hexdigest() == pinned
    document = dict(format='kenshi-oracle-canonical-vectors-1', historical_case_count=59,
                    historical_expected_sha256=pinned, cases=rows)
    path = ROOT / 'schema' / 'canonical-vectors.json'
    path.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    # Report the LF-normalized identity so CRLF and LF checkouts print the same hash.
    normalized = path.read_bytes().replace(b'\r\n', b'\n')
    print(json.dumps(dict(cases=len(rows), sha256=hashlib.sha256(normalized).hexdigest())))


if __name__ == '__main__':
    main()
