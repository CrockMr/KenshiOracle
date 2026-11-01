"""Scenario format scenario-0.2: setup block, aliases and version dispatch (synthetic only)."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import oracle_schema
from oracle_schema import (SCENARIO_SCHEMA_VERSIONS, SCHEMA_VERSION, OracleSchemaError,
                           validate_scenario, validate_state)
from test_oracle_schema import populated_state, scenario
from test_oracle_schema_02 import state_02


SCHEMA_DIR = Path(__file__).resolve().parents[1] / 'schema'
EXAMPLES = Path(__file__).resolve().parents[1] / 'scenarios'


def setup_block():
    return dict(
        preflight=dict(scene_center=[100, -200], scene_radius=1500, squad_size_multiplier=1,
                       player_faction_id='player-faction', expect_absent_factions_in_scene=['enemy-faction']),
        moves=[],
        spawns=[dict(alias='raiders', squad_template='squad-template.base', count=3,
                     faction_id='enemy-faction', at=dict(offset_from_player=[30, 0]),
                     expected_templates={'leader.base': 1, 'grunt.base': 2})],
        settle=dict(sim_seconds=1),
        heal='all_scene_characters',
        relations=[dict(a='enemy-faction', b='player-faction', a_to_b=-60, b_to_a=-60)])


def scenario_02(**params):
    value = scenario()
    value['schema_version'] = 'scenario-0.2'
    value['setup'] = setup_block()
    order = dict(type='attack', squad_alias='raiders', target_alias='player')
    order.update(params)
    value['actions'] = [dict(at=0, command='issue_order', params=order)]
    return value


def with_order(**params):
    value = scenario_02()
    value['actions'][0]['params'] = params
    return value


def rejects(value, match=None):
    with pytest.raises(OracleSchemaError, match=match):
        validate_scenario(value)


def test_schema_file_is_valid_and_distinct_from_state_02():
    schema = json.loads((SCHEMA_DIR / 'scenario-0.2.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    assert schema['$id'] == 'urn:kenshi-oracle:scenario:0.2'
    assert schema['title'] == 'Kenshi scenario format scenario-0.2'
    assert schema['properties']['schema_version']['const'] == 'scenario-0.2'
    old = json.loads((SCHEMA_DIR / 'scenario.schema.json').read_text(encoding='utf-8'))
    assert old['properties']['schema_version']['const'] == '0.1'


def test_versions_and_valid_documents():
    assert SCENARIO_SCHEMA_VERSIONS == ('0.1', 'scenario-0.2')
    assert SCHEMA_VERSION == '0.1'
    value = scenario_02()
    original = deepcopy(value)
    assert validate_scenario(value) is value
    assert value == original
    assert validate_scenario(scenario())['schema_version'] == '0.1'
    without_setup = scenario()
    without_setup['schema_version'] = 'scenario-0.2'
    assert validate_scenario(without_setup) is without_setup


@pytest.mark.parametrize('path', sorted(EXAMPLES.glob('*.json')), ids=lambda path: path.name)
def test_distributed_examples_still_validate(path):
    assert oracle_schema.load_scenario(path)['name'] == path.stem


def test_validator_cache_holds_the_four_kinds():
    oracle_schema._validator.cache_clear()
    validate_state(populated_state())
    validate_state(state_02())
    validate_scenario(scenario())
    validate_scenario(scenario_02())
    info = oracle_schema._validator.cache_info()
    assert info.maxsize == 4
    assert info.currsize == 4
    assert info.misses == 4


def test_state_and_scenario_versions_do_not_cross():
    rejects(state_02())
    bare = scenario_02()
    bare['schema_version'] = '0.2'
    rejects(bare)
    bare = scenario()
    bare['schema_version'] = '0.2'
    rejects(bare)
    state = populated_state()
    state['schema_version'] = 'scenario-0.2'
    with pytest.raises(OracleSchemaError):
        validate_state(state)
    old = scenario()
    old['setup'] = setup_block()
    rejects(old)


@pytest.mark.parametrize('mutate', [
    lambda s: s['relations'][0].pop('b_to_a'),
    lambda s: s['relations'][0].pop('a_to_b'),
    lambda s: s['relations'][0].pop('b'),
    lambda s: s.update(relations=[]),
    lambda s: s.update(relations=[dict(a=f'f{i}', b=f'g{i}', a_to_b=0, b_to_a=0) for i in range(5)]),
    lambda s: s['relations'][0].update(a_to_b=-60.5),
    lambda s: s['relations'][0].update(b_to_a=101),
    lambda s: s['relations'][0].update(a_to_b=-101),
    lambda s: s['relations'][0].update(a_to_b='-60'),
    lambda s: s['relations'][0].update(a_to_b=True),
    lambda s: s['relations'][0].update(at_war=False),
    lambda s: s['relations'][0].update(war=False),
    lambda s: s.update(war=False),
    lambda s: s['relations'][0].update(b='enemy-faction'),
    lambda s: s['relations'].append(dict(a='player-faction', b='enemy-faction', a_to_b=0, b_to_a=0)),
    lambda s: s['relations'][0].update(a='x' * 129),
    lambda s: s['relations'][0].update(a='é' * 65),
], ids=['one-way-b-to-a', 'one-way-a-to-b', 'missing-b', 'no-relation', 'five-relations',
        'fractional', 'above-100', 'below-minus-100', 'string', 'boolean', 'war-flag-at-war',
        'war-flag-war', 'war-flag-setup', 'a-equals-b', 'duplicate-pair', 'long-id', 'long-utf8-id'])
def test_relation_rules(mutate):
    value = scenario_02()
    mutate(value['setup'])
    rejects(value)


@pytest.mark.parametrize('values', [(-100, 100), (100, -100), (0, -60), (-30, -29)],
                         ids=['bounds', 'reverse-bounds', 'asymmetric', 'no-threshold'])
def test_relations_have_no_symmetry_or_threshold_constraint(values):
    value = scenario_02()
    value['setup']['relations'][0].update(a_to_b=values[0], b_to_a=values[1])
    assert validate_scenario(value) is value


@pytest.mark.parametrize('relation', [
    dict(a='enemy-faction', b='player-faction', a_to_b=-60, b_to_a=-60),
    dict(a='player-faction', b='enemy-faction', a_to_b=-60, b_to_a=-60),
], ids=['repeated', 'reversed'])
def test_repeated_relation_pair_with_the_same_values_is_accepted(relation):
    value = scenario_02()
    value['setup']['relations'].append(relation)
    assert validate_scenario(value) is value


@pytest.mark.parametrize('mutate', [
    lambda s: s['relations'][0].update(a_to_b=-60.0),
    lambda s: s['relations'][0].update(b_to_a=-60.0),
    lambda s: s['spawns'][0].update(count=3.0),
    lambda s: s['spawns'][0]['expected_templates'].update({'grunt.base': 2.0}),
], ids=['a-to-b', 'b-to-a', 'count', 'template-count'])
def test_integral_floats_are_not_integers(mutate):
    value = scenario_02()
    mutate(value['setup'])
    rejects(value, 'must be an integer')
    rejects(json.loads(json.dumps(value)), 'must be an integer')


@pytest.mark.parametrize('mutate', [
    lambda s: s['moves'].append(dict(alias='player', offset=[1, 0])),
    lambda s: s.update(heal='players_only'),
    lambda s: s.update(heal='none'),
    lambda s: s.pop('heal'),
    lambda s: s.update(settle=dict(sim_seconds=2)),
    lambda s: s.update(settle=dict(sim_seconds=0)),
    lambda s: s.update(settle=dict(sim_seconds=1, calendar_seconds=33)),
    lambda s: s.pop('settle'),
    lambda s: s.pop('moves'),
    lambda s: s.update(extra=True),
    lambda s: s['preflight'].update(squad_size_multiplier=2),
    lambda s: s['preflight'].update(scene_radius=0),
    lambda s: s['preflight'].update(scene_radius=20001),
    lambda s: s['preflight'].update(scene_center=[0, 0, 0]),
    lambda s: s['preflight'].update(player_y=736.593),
    lambda s: s['preflight'].pop('expect_absent_factions_in_scene'),
    lambda s: s.update(spawns=[]),
    lambda s: s.update(spawns=[dict(s['spawns'][0], alias=f'a{i}') for i in range(5)]),
    lambda s: s['spawns'][0].update(count=0),
    lambda s: s['spawns'][0].update(count=17),
    lambda s: s['spawns'][0].update(count=4),
    lambda s: s['spawns'][0].update(expected_templates={}),
    lambda s: s['spawns'][0].update(expected_templates={'leader.base': 0, 'grunt.base': 3}),
    lambda s: s['spawns'][0].update(at=dict(position=[0, 0, 0])),
    lambda s: s['spawns'][0].update(at=dict(offset_from_player=[30, 0, 0])),
    lambda s: s['spawns'][0].update(size_multiplier=1),
    lambda s: s['spawns'][0].update(squad_template='t' * 129),
], ids=['move', 'heal-players-only', 'heal-none', 'heal-missing', 'settle-two', 'settle-zero',
        'settle-extra', 'settle-missing', 'moves-missing', 'setup-extra', 'multiplier',
        'radius-zero', 'radius-above-limit', 'center-three', 'pinned-height', 'absent-missing',
        'no-spawn', 'five-spawns', 'count-zero', 'count-17', 'templates-sum', 'templates-empty',
        'template-zero', 'absolute-position', 'offset-three', 'spawn-extra', 'long-template'])
def test_setup_block_rules(mutate):
    value = scenario_02()
    mutate(value['setup'])
    rejects(value)


def test_speed_must_be_positive_with_setup():
    value = scenario_02()
    value['speed'] = 0
    value['actions'].insert(0, dict(at=0, command='set_game_speed', params=dict(speed=1)))
    rejects(value)
    value = scenario_02()
    value.pop('setup')
    value['speed'] = 0
    value['actions'] = [dict(at=0, command='set_game_speed', params=dict(speed=1))]
    assert validate_scenario(value) is value


@pytest.mark.parametrize('alias', ['player', 'raiders/leader.base/1', 'raiders/grunt.base/2'])
def test_character_aliases_resolve(alias):
    value = with_order(type='move', character_alias=alias, position=[1, 2, 3])
    assert validate_scenario(value) is value
    value = with_order(type='attack', squad_alias='raiders', target_alias=alias)
    assert validate_scenario(value) is value


def test_numbered_player_aliases_resolve():
    value = with_order(type='attack', character_alias='player/1', target_alias='player/2')
    assert validate_scenario(value) is value


@pytest.mark.parametrize('params', [
    dict(type='attack', squad_alias='bandits', target_alias='player'),
    dict(type='attack', squad_alias='player', target_alias='raiders/leader.base/1'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders'),
    dict(type='attack', squad_alias='raiders', target_alias='enemy'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/leader.base/2'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/grunt.base/3'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/other.base/1'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/leader.base/0'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/leader.base/01'),
    dict(type='attack', squad_alias='raiders', target_alias='bandits/leader.base/1'),
    dict(type='attack', squad_alias='raiders', target_alias='player/0'),
    dict(type='attack', squad_alias='raiders', target_alias='player/65'),
    dict(type='attack', squad_alias='raiders', target_alias='player/' + '9' * 5000),
    dict(type='attack', squad_alias='raiders', target_alias='player\n'),
    dict(type='attack', squad_alias='raiders\n', target_alias='player'),
    dict(type='attack', squad_alias='raiders', target_alias='Player'),
    dict(type='attack', squad_alias='raiders', target_alias='player/'),
    dict(type='attack', squad_alias='raiders', target_alias='raiders/.base/1'),
    dict(type='attack', character_alias='player', target_alias='player/1'),
], ids=['unknown-squad', 'player-as-squad', 'squad-as-target', 'unknown-character', 'member-k-beyond',
        'member-k-beyond-count', 'member-unknown-template', 'member-k-zero', 'member-k-leading-zero',
        'member-unknown-spawn', 'player-zero', 'player-above-64', 'player-huge', 'trailing-newline',
        'squad-trailing-newline', 'uppercase', 'empty-segment', 'segment-dot-first',
        'player-forms-mixed'])
def test_unknown_or_malformed_aliases_are_rejected(params):
    rejects(with_order(**params))


def test_duplicate_spawn_alias_is_rejected():
    value = scenario_02()
    value['setup']['spawns'].append(deepcopy(value['setup']['spawns'][0]))
    rejects(value, 'duplicate alias')


@pytest.mark.parametrize('alias', ['player', 'Raiders', '1raiders', 'raiders/x', 'r' * 33, 'raiders\n'])
def test_spawn_alias_grammar(alias):
    value = scenario_02()
    value['setup']['spawns'][0]['alias'] = alias
    value['actions'] = []
    rejects(value)


def test_aliases_require_a_setup_block():
    value = scenario_02()
    value.pop('setup')
    rejects(value, 'setup block')


@pytest.mark.parametrize('params', [
    dict(type='attack', target_alias='player'),
    dict(type='attack', character_id='c1', squad_alias='raiders', target_alias='player'),
    dict(type='attack', character_alias='player', squad_alias='raiders', target_id='t1'),
    dict(type='attack', character_id='c1', character_alias='player', target_id='t1'),
    dict(type='attack', squad_id='s1', squad_alias='raiders', target_id='t1'),
    dict(type='attack', squad_alias='raiders'),
    dict(type='attack', squad_alias='raiders', target_id='t1', target_alias='player'),
    dict(type='attack', squad_alias='raiders', target_alias='player', position=[1, 2, 3]),
    dict(type='move', squad_alias='raiders'),
    dict(type='move', squad_alias='raiders', position=[1, 2, 3], target_alias='player'),
    dict(type='move', squad_alias='raiders', position=[1, 2, 3], target_id='t1'),
    dict(type='attack', squad_alias='raiders', target_alias='player', squad_name='raiders'),
], ids=['no-actor', 'id-and-squad-alias', 'two-aliases', 'id-and-alias', 'squad-id-and-alias',
        'attack-no-target', 'attack-two-targets', 'attack-position', 'move-no-position',
        'move-target-alias', 'move-target-id', 'extra-key'])
def test_alias_one_of_combinations_are_rejected(params):
    rejects(with_order(**params))


@pytest.mark.parametrize('params', [
    dict(type='attack', character_id='c1', target_alias='player'),
    dict(type='attack', squad_alias='raiders', target_id='t1'),
    dict(type='move', squad_id='s1', position=[1, 2, 3]),
])
def test_ids_and_aliases_can_be_mixed_across_roles(params):
    value = with_order(**params)
    assert validate_scenario(value) is value
