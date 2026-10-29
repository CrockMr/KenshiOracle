"""Contract tests use synthetic states only; no game files or live game access."""
from copy import deepcopy
import json

import pytest

from oracle_schema import (OracleSchemaError, canonical_bytes, load_scenario,
                           load_state, validate_scenario, validate_state)


def minimal_state():
    return dict(schema_version='0.1',
                clock=dict(day=2, hour=3.5, elapsed_seconds=185400, speed=0, paused=True),
                characters=[], squads=[], factions=[], relations=[])


def populated_state():
    state = minimal_state()
    state['characters'] = [
        dict(id=identity, name='Éclaireur', race_id='human', faction_id='f2',
             squad_id='s1', position=[1.2345675, -0.0, -0.0000005], state='alive',
             health=[dict(id='head:neither', current=98.75, stun=-2.0, maximum=100),
                     dict(id='arm:left', current=-5, stun=0, maximum=100)],
             order=dict(type='move_cus_ordered', target_id=None, position=[1, 2, 3]))
        for identity in ('c2', 'c1')]
    state['squads'] = [dict(id='s1', faction_id='f2', members=['c2', 'c1'], leader_id='c1')]
    state['factions'] = [dict(id='f2', name='Two'), dict(id='f1', name='One')]
    state['relations'] = [dict(source_id='f2', target_id='f1', value=-50),
                          dict(source_id='f1', target_id='f2', value=25)]
    return state


def scenario():
    return dict(schema_version='0.1', name='synthetic-town', save='Synthetic save',
                speed=1, repeat=3, actions=[],
                checkpoints=[dict(at=0, name='start'), dict(at=30, name='finish')])


def test_minimal_canonical_golden_bytes():
    assert canonical_bytes(minimal_state()) == (
        b'{"characters":[],"clock":{"day":2,"elapsed_seconds":185400,"hour":3.5,'
        b'"paused":true,"speed":0},"factions":[],"relations":[],"schema_version":"0.1",'
        b'"squads":[]}\n')


def test_canonical_state_is_permutation_independent_without_mutating_input():
    state = populated_state()
    original = deepcopy(state)
    reordered = {key: value for key, value in reversed(list(deepcopy(state).items()))}
    for key in ('characters', 'squads', 'factions', 'relations'):
        reordered[key].reverse()
    for character in reordered['characters']:
        character['health'].reverse()
    reordered['squads'][0]['members'].reverse()
    assert canonical_bytes(state) == canonical_bytes(reordered)
    assert state == original
    decoded = json.loads(canonical_bytes(state))
    assert [row['id'] for row in decoded['characters']] == ['c1', 'c2']
    assert decoded['squads'][0]['members'] == ['c1', 'c2']
    assert [row['id'] for row in decoded['characters'][0]['health']] == ['arm:left', 'head:neither']
    assert [row['source_id'] for row in decoded['relations']] == ['f1', 'f2']
    assert decoded['relations'][0]['value'] == 25
    assert decoded['relations'][1]['value'] == -50
    assert validate_state(decoded) is decoded


@pytest.mark.parametrize('value,text', [
    (1.0, '1'), (0.0, '0'), (-0.0, '0'),
    (0.00000049, '0'), (-0.00000049, '0'),
    (0.0000005, '0.000001'), (-0.0000005, '-0.000001'),
    (1.2345675, '1.234568'), (-1.2345675, '-1.234568'),
    (1000000000.0, '1000000000'), (123.4, '123.4')])
def test_numeric_canonicalization_matches_shared_binary64_rule(value, text):
    state = populated_state()
    state['characters'][0]['position'] = [value, value, value]
    encoded = canonical_bytes(state)
    assert f'"position":[{text},{text},{text}]'.encode() in encoded
    assert canonical_bytes(json.loads(encoded)) == encoded


def test_canonical_unicode_and_escaping():
    state = populated_state()
    state['characters'][0]['name'] = 'Éclaireur "雪"\n\t\\'
    encoded = canonical_bytes(state)
    assert 'Éclaireur'.encode() in encoded
    assert b'\\"' in encoded and b'\\n' in encoded and b'\\t' in encoded
    assert not encoded.startswith(b'\xef\xbb\xbf')
    assert encoded.endswith(b'\n') and b'\r\n' not in encoded
    assert json.loads(encoded)['characters'][1]['name'] == state['characters'][0]['name']


def test_unknown_fields_stay_null_and_do_not_become_empty_or_zero():
    state = populated_state()
    character = state['characters'][0]
    for key in ('race_id', 'faction_id', 'squad_id', 'position', 'state', 'health', 'order'):
        character[key] = None
    state['relations'][0]['value'] = None
    decoded = json.loads(canonical_bytes(state))
    assert decoded['characters'][1]['health'] is None
    assert decoded['characters'][1]['state'] is None
    assert decoded['relations'][1]['value'] is None


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), 1000000001, 10 ** 5000],
                         ids=['nan', 'inf', 'negative-inf', 'over-limit', 'huge-integer'])
def test_nonfinite_and_out_of_range_numbers_are_rejected(value):
    state = populated_state()
    state['characters'][0]['position'][0] = value
    with pytest.raises(OracleSchemaError, match='finite'):
        canonical_bytes(state)


@pytest.mark.parametrize('mutate', [
    lambda s: s.update(schema_version='0.2'),
    lambda s: s.update(captured_at='machine time'),
    lambda s: s['clock'].update(day=True),
    lambda s: s['characters'][0].update(id=''),
    lambda s: s['characters'][0].update(id='bad\x00id'),
    lambda s: s['characters'][0].update(position=[1, 2]),
    lambda s: s['characters'][0].update(state='sleeping'),
    lambda s: s['characters'][0]['order'].update(type=42),
    lambda s: s['characters'][0]['order'].update(type='MOVE_TO'),
    lambda s: s['characters'][0]['health'][0].update(maximum=-1),
    lambda s: s['squads'][0].update(members=['c1', 'c1']),
    lambda s: s['characters'][0].update(name='\ud800'),
    lambda s: s['characters'][0].update(name=b'not a JSON string')])
def test_invalid_state_contracts_are_rejected(mutate):
    state = populated_state()
    mutate(state)
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('collection', ['characters', 'squads', 'factions', 'relations'])
def test_duplicate_collection_identity_is_rejected(collection):
    state = populated_state()
    state[collection].append(deepcopy(state[collection][0]))
    with pytest.raises(OracleSchemaError, match='duplicate identity'):
        validate_state(state)


def test_duplicate_health_identity_is_rejected():
    state = populated_state()
    state['characters'][0]['health'].append(deepcopy(state['characters'][0]['health'][0]))
    with pytest.raises(OracleSchemaError, match='duplicate identity'):
        validate_state(state)


def test_public_task_name_can_have_a_leading_underscore():
    state = populated_state()
    state['characters'][0]['order']['type'] = '_slave_obedience'
    assert validate_state(state) is state


def test_load_state_validates_and_preserves_bytes_on_canonical_reencoding(tmp_path):
    path = tmp_path / 'state.json'
    expected = canonical_bytes(populated_state())
    path.write_bytes(expected)
    assert canonical_bytes(load_state(path)) == expected


@pytest.mark.parametrize('data', [b'{"schema_version":"0.1","schema_version":"0.1"}',
                                b'{"value":NaN}', b'{} trailing', b'\xff'])
def test_load_rejects_ambiguous_or_invalid_json(tmp_path, data):
    path = tmp_path / 'bad.json'
    path.write_bytes(data)
    with pytest.raises(OracleSchemaError):
        load_state(path)


def test_load_size_limit_and_missing_file(tmp_path, monkeypatch):
    import oracle_schema
    path = tmp_path / 'large.json'
    path.write_bytes(b' ' * 11)
    monkeypatch.setattr(oracle_schema, 'MAX_DOCUMENT_BYTES', 10)
    with pytest.raises(OracleSchemaError, match='exceeds'):
        load_state(path)
    with pytest.raises(OracleSchemaError, match='Cannot read'):
        load_state(tmp_path / 'absent.json')


def test_scenario_load_and_validation_are_nonmutating(tmp_path):
    value = scenario()
    original = deepcopy(value)
    assert validate_scenario(value) is value
    assert value == original
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    assert load_scenario(path) == value


@pytest.mark.parametrize('actor', ['character_id', 'squad_id'])
@pytest.mark.parametrize('kind', ['move', 'attack'])
def test_both_order_kinds_accept_each_actor_scope(actor, kind):
    value = scenario()
    params = dict(type=kind, **{actor: 'persistent-id'})
    params.update(position=[1, 2, 3]) if kind == 'move' else params.update(target_id='target-id')
    value['actions'] = [dict(at=0, command='issue_order', params=params)]
    assert validate_scenario(value) is value


@pytest.mark.parametrize('params', [
    dict(type='move', position=[1, 2, 3]),
    dict(type='move', character_id='c', squad_id='s', position=[1, 2, 3]),
    dict(type='move', character_id='c', target_id='target'),
    dict(type='attack', squad_id='s', position=[1, 2, 3]),
    dict(type='attack', squad_id='s', target_id='target', position=[1, 2, 3]),
    dict(type='invented', character_id='c')])
def test_orders_reject_ambiguous_actors_and_wrong_parameters(params):
    value = scenario()
    value['actions'] = [dict(at=0, command='issue_order', params=params)]
    with pytest.raises(OracleSchemaError):
        validate_scenario(value)


@pytest.mark.parametrize('mutate', [
    lambda s: s.update(repeat=0),
    lambda s: s.update(repeat=101),
    lambda s: s.update(repeat=True),
    lambda s: s.update(speed=True),
    lambda s: s.update(speed=5.01),
    lambda s: s.update(checkpoints=[]),
    lambda s: s.update(name='../escape'),
    lambda s: s.update(name='CON'),
    lambda s: s.update(save='..'),
    lambda s: s.update(save='save/path'),
    lambda s: s.update(save='save\\path'),
    lambda s: s.update(save='save.'),
    lambda s: s.update(save=' save'),
    lambda s: s.update(save='NUL.txt'),
    lambda s: s['checkpoints'][1].update(name='START'),
    lambda s: s['checkpoints'][1].update(at=-1),
    lambda s: s['checkpoints'][1].update(at=float('nan')),
    lambda s: s['checkpoints'][1].update(at=True),
    lambda s: s['checkpoints'][1].update(name='AUX'),
    lambda s: s['checkpoints'].reverse(),
    lambda s: s.update(actions=[dict(at=0, command='load_save', params=dict(name='wrong'))])])
def test_invalid_scenarios_are_rejected_before_game_access(mutate):
    value = scenario()
    mutate(value)
    with pytest.raises(OracleSchemaError):
        validate_scenario(value)


@pytest.mark.parametrize('pause_action', [
    dict(at=5, command='pause', params=dict(paused=True)),
    dict(at=5, command='set_game_speed', params=dict(speed=0))])
def test_pause_that_prevents_next_event_is_rejected(pause_action):
    value = scenario()
    value['actions'] = [pause_action]
    with pytest.raises(OracleSchemaError, match='resume at 5'):
        validate_scenario(value)


def test_pause_and_resume_at_same_instant_preserve_declared_order():
    value = scenario()
    value['actions'] = [dict(at=5, command='pause', params=dict(paused=True)),
                        dict(at=5, command='pause', params=dict(paused=False))]
    assert validate_scenario(value) is value
    value['actions'].reverse()
    with pytest.raises(OracleSchemaError, match='resume at 5'):
        validate_scenario(value)


def test_initial_pause_and_terminal_pause_have_explicit_timeline_rules():
    value = scenario()
    value['speed'] = 0
    with pytest.raises(OracleSchemaError, match='resume at 0'):
        validate_scenario(value)
    value['actions'] = [dict(at=0, command='set_game_speed', params=dict(speed=1)),
                        dict(at=30, command='pause', params=dict(paused=True))]
    assert validate_scenario(value) is value
    value['actions'].reverse()
    with pytest.raises(OracleSchemaError, match='nondecreasing'):
        validate_scenario(value)


def test_initial_zero_speed_requires_explicit_positive_selection_before_advancing():
    value = scenario()
    value['speed'] = 0
    value['actions'] = [dict(at=0, command='pause', params=dict(paused=False))]
    with pytest.raises(OracleSchemaError, match='positive game speed explicitly'):
        validate_scenario(value)
    value['actions'].insert(0, dict(at=0, command='set_game_speed', params=dict(speed=2)))
    assert validate_scenario(value) is value


def test_zero_speed_action_retains_previously_known_positive_selection():
    value = scenario()
    value['actions'] = [dict(at=0, command='set_game_speed', params=dict(speed=0)),
                        dict(at=0, command='pause', params=dict(paused=False))]
    assert validate_scenario(value) is value
