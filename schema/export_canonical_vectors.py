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
from oracle_schema import _check_json_values, _encode, canonical_bytes


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
    return cases


def main():
    rows, legacy = [], bytearray()
    for index, (name, kind, value) in enumerate(vectors()):
        _check_json_values(value)
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
    print(json.dumps(dict(cases=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
