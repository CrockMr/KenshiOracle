"""Additive 0.2 contracts, unknown coverage and unchanged canonical rules."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from oracle_schema import (LATEST_STATE_SCHEMA_VERSION, SCHEMA_VERSION,
                           STATE_SCHEMA_VERSIONS, OracleSchemaError,
                           canonical_bytes, load_state, validate_scenario, validate_state)
from test_oracle_schema import populated_state, scenario


CHARACTER_FIELDS = {'identity_origin', 'current_town_id', 'town_assignment', 'in_combat'}
SQUAD_FIELDS = {'identity_origin', 'template_id', 'origin_town_id'}


def state_02():
    state = populated_state()
    state['schema_version'] = '0.2'
    for row in state['characters']:
        row.update(identity_origin=None, current_town_id=None, town_assignment=None, in_combat=None)
    for row in state['squads']:
        row.update(identity_origin=None, template_id=None, origin_town_id=None)
    return state


def schema(version):
    filename = 'state.schema.json' if version == '0.1' else 'state-0.2.schema.json'
    return json.loads((Path(__file__).resolve().parents[1] / 'schema' / filename).read_text(encoding='utf-8'))


def test_schema_02_is_self_contained_valid_and_only_adds_to_01_contract():
    old, new = schema('0.1'), schema('0.2')
    Draft202012Validator.check_schema(new)
    assert old['properties']['schema_version']['const'] == '0.1'
    assert new['properties']['schema_version']['const'] == '0.2'
    assert old['required'] == new['required']
    assert old['additionalProperties'] is new['additionalProperties'] is False
    for key, value in old['properties'].items():
        if key != 'schema_version':
            assert new['properties'][key] == value
    for key, value in old['$defs'].items():
        if key not in ('character', 'squad'):
            assert new['$defs'][key] == value
    for key, added in (('character', CHARACTER_FIELDS), ('squad', SQUAD_FIELDS)):
        before, after = old['$defs'][key], new['$defs'][key]
        assert set(after['properties']) - set(before['properties']) == added
        assert set(after['required']) - set(before['required']) == added
        for name, value in before['properties'].items():
            assert after['properties'][name] == value
    assert Draft202012Validator(new).is_valid(state_02())


def test_both_versions_are_supported_without_upgrading_scenarios():
    assert SCHEMA_VERSION == '0.1'
    assert STATE_SCHEMA_VERSIONS == ('0.1', '0.2')
    assert LATEST_STATE_SCHEMA_VERSION == '0.2'
    assert validate_state(populated_state())['schema_version'] == '0.1'
    assert validate_state(state_02())['schema_version'] == '0.2'
    assert validate_scenario(scenario())['schema_version'] == '0.1'


def test_projecting_additive_fields_preserves_exact_phase1_canonical_bytes():
    state = state_02()
    state['schema_version'] = '0.1'
    for row in state['characters']:
        for name in CHARACTER_FIELDS:
            del row[name]
    for row in state['squads']:
        for name in SQUAD_FIELDS:
            del row[name]
    assert canonical_bytes(state) == canonical_bytes(populated_state())


def test_version_switch_without_additions_is_rejected():
    state = populated_state()
    state['schema_version'] = '0.2'
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('collection,names', [('characters', CHARACTER_FIELDS), ('squads', SQUAD_FIELDS)])
def test_every_additive_field_is_required_even_when_coverage_is_unknown(collection, names):
    for name in names:
        state = state_02()
        del state[collection][0][name]
        with pytest.raises(OracleSchemaError):
            validate_state(state)


def test_unknowns_remain_explicit_null_without_becoming_outside_or_generated():
    state = state_02()
    encoded = canonical_bytes(state)
    decoded = json.loads(encoded)
    for row in decoded['characters']:
        assert all(row[name] is None for name in CHARACTER_FIELDS)
    for row in decoded['squads']:
        assert all(row[name] is None for name in SQUAD_FIELDS)
    assert b'"town_assignment":null' in encoded
    assert b'"in_combat":null' in encoded
    assert b'"identity_origin":null' in encoded


@pytest.mark.parametrize('origin', ['saved', 'generated', None])
def test_producer_asserted_identity_origin_is_engine_neutral(origin):
    state = state_02()
    state['characters'][0]['identity_origin'] = origin
    state['squads'][0]['identity_origin'] = origin
    assert validate_state(state) is state


@pytest.mark.parametrize('origin', ['unknown', 'unresolved', 'loaded', '', 0, False, {}, []])
def test_identity_origin_does_not_accept_inferred_or_ill_typed_labels(origin):
    state = state_02()
    state['characters'][0]['identity_origin'] = origin
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('assignment,town', [('inside', 'placement-uid'), ('outside', None), (None, None)])
def test_known_inside_known_outside_and_unknown_are_distinct(assignment, town):
    state = state_02()
    state['characters'][0].update(town_assignment=assignment, current_town_id=town)
    assert validate_state(state) is state
    assert json.loads(canonical_bytes(state))['characters'][1]['town_assignment'] == assignment


@pytest.mark.parametrize('assignment,town', [
    ('inside', None), ('outside', 'placement-uid'), (None, 'placement-uid'),
    ('unknown', None), (False, None), ('inside', ''), ('inside', 'bad\x00id')])
def test_town_membership_cannot_contradict_its_coverage_or_identity(assignment, town):
    state = state_02()
    state['characters'][0].update(town_assignment=assignment, current_town_id=town)
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('combat', [True, False, None])
def test_combat_mode_can_be_known_true_known_false_or_unknown(combat):
    state = state_02()
    state['characters'][0]['in_combat'] = combat
    assert validate_state(state) is state


@pytest.mark.parametrize('combat', [0, 1, 'false', 'unknown', [], {}])
def test_combat_coverage_rejects_integer_or_string_substitutes(combat):
    state = state_02()
    state['characters'][0]['in_combat'] = combat
    with pytest.raises(OracleSchemaError):
        validate_state(state)


def test_grouping_ids_are_nullable_opaque_data_and_placement_identities():
    state = state_02()
    state['squads'][0].update(template_id='12-squad.mod', origin_town_id='town-placement-uid')
    assert validate_state(state) is state
    for key in ('template_id', 'origin_town_id'):
        for invalid in ('', 'bad\nidentifier', 42, False):
            bad = deepcopy(state)
            bad['squads'][0][key] = invalid
            with pytest.raises(OracleSchemaError):
                validate_state(bad)


def test_permutations_and_new_field_key_order_do_not_affect_bytes_or_mutate_input():
    state = state_02()
    original = deepcopy(state)
    state['characters'][0].update(identity_origin='saved', in_combat=True,
                                   town_assignment='inside', current_town_id='城-placement')
    state['squads'][0].update(template_id='12-squad.mod', origin_town_id='城-placement')
    original = deepcopy(state)
    permuted = {key: value for key, value in reversed(list(deepcopy(state).items()))}
    for collection in ('characters', 'squads', 'factions', 'relations'):
        permuted[collection].reverse()
        permuted[collection] = [{key: value for key, value in reversed(list(row.items()))}
                                for row in permuted[collection]]
    for row in permuted['characters']:
        row['health'].reverse()
    for row in permuted['squads']:
        row['members'].reverse()
    expected = canonical_bytes(state)
    assert canonical_bytes(permuted) == expected
    assert state == original
    assert b'"in_combat":true' in expected
    assert b'"position":[1.234568,0,-0.000001]' in expected
    assert '城-placement'.encode('utf-8') in expected
    assert expected.endswith(b'\n') and b'\r\n' not in expected
    assert canonical_bytes(json.loads(expected)) == expected


def test_02_file_load_round_trips_and_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / 'state-02.json'
    raw = canonical_bytes(state_02())
    path.write_bytes(raw)
    assert canonical_bytes(load_state(path)) == raw
    path.write_bytes(raw.replace(b'"identity_origin":null',
                                b'"identity_origin":null,"identity_origin":"generated"', 1))
    with pytest.raises(OracleSchemaError, match='Duplicate'):
        load_state(path)


def test_02_retains_unique_identity_guards_and_no_producer_metadata():
    state = state_02()
    state['characters'].append(deepcopy(state['characters'][0]))
    with pytest.raises(OracleSchemaError, match='duplicate identity'):
        validate_state(state)
    state = state_02()
    state['process_id'] = 123
    with pytest.raises(OracleSchemaError):
        validate_state(state)
