"""Additive 0.3 slave-state contract, its comparison, and unchanged 0.2 rules."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from oracle_compare import saved_metrics
from oracle_comparison import compare_campaigns
from oracle_schema import (COMPARABLE_STATE_SCHEMA_VERSIONS, LATEST_STATE_SCHEMA_VERSION,
                           STATE_SCHEMA_VERSIONS, OracleSchemaError, canonical_bytes, load_state,
                           validate_state)
from test_oracle_compare import FIRST, SECOND, by_metric, state as compare_state, states
from test_oracle_comparison import campaign
from test_oracle_schema_02 import state_02


ADDED = {'slave_state', 'slave_owner_faction_id'}
SLAVE_STATES = ('not_slave', 'slave', 'escaping_slave', 'ex_slave')
ROOT = Path(__file__).resolve().parents[1] / 'schema'


def state_03():
    state = state_02()
    state['schema_version'] = '0.3'
    for row in state['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    return state


def schema(filename):
    return json.loads((ROOT / filename).read_text(encoding='utf-8'))


def test_schema_03_is_self_contained_valid_and_only_adds_two_character_fields_to_02():
    old, new = schema('state-0.2.schema.json'), schema('state-0.3.schema.json')
    Draft202012Validator.check_schema(new)
    assert new['properties']['schema_version']['const'] == '0.3'
    assert new['$id'] == 'urn:kenshi-oracle:state:0.3'
    assert old['required'] == new['required']
    assert old['additionalProperties'] is new['additionalProperties'] is False
    for key, value in old['properties'].items():
        if key != 'schema_version':
            assert new['properties'][key] == value
    for key, value in old['$defs'].items():
        if key != 'character':
            assert new['$defs'][key] == value
    before, after = old['$defs']['character'], new['$defs']['character']
    assert set(after['properties']) - set(before['properties']) == ADDED
    assert set(after['required']) - set(before['required']) == ADDED
    assert after['required'][:len(before['required'])] == before['required']
    for name, value in before['properties'].items():
        assert after['properties'][name] == value
    assert after['allOf'] == before['allOf']
    assert after['properties']['slave_state']['enum'] == [*SLAVE_STATES, None]
    assert after['properties']['slave_owner_faction_id']['$ref'] == '#/$defs/nullable_id'
    for name in ADDED:
        assert 'never' in after['properties'][name]['description'] or 'not prove' in after['properties'][name]['description']
    assert Draft202012Validator(new).is_valid(state_03())


def test_versions_and_comparable_versions():
    assert STATE_SCHEMA_VERSIONS == ('0.1', '0.2', '0.3', '0.4', '0.5')
    assert LATEST_STATE_SCHEMA_VERSION == '0.5'
    assert COMPARABLE_STATE_SCHEMA_VERSIONS == ('0.2', '0.3', '0.4', '0.5')
    assert validate_state(state_03())['schema_version'] == '0.3'
    assert validate_state(state_02())['schema_version'] == '0.2'


def test_02_states_cannot_carry_the_03_fields():
    state = state_02()
    state['characters'][0].update(slave_state=None, slave_owner_faction_id=None)
    with pytest.raises(OracleSchemaError):
        validate_state(state)


def test_version_switch_without_additions_is_rejected():
    state = state_02()
    state['schema_version'] = '0.3'
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('name', sorted(ADDED))
def test_every_added_field_is_required_even_when_unknown(name):
    state = state_03()
    del state['characters'][0][name]
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('version', ['0.6', '0.30', ' 0.3', 0.3, None])
def test_unknown_versions_fail_the_01_constant(version):
    state = state_03()
    state['schema_version'] = version
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('value', [*SLAVE_STATES, None])
def test_each_slave_state_name_and_unknown_are_accepted(value):
    state = state_03()
    state['characters'][0]['slave_state'] = value
    assert validate_state(state) is state


@pytest.mark.parametrize('value', [0, 1, 2, 3, 4, -1, 'NOT_SLAVE', 'IS_SLAVE', 'is_slave', 'escaped',
                                   'unknown', '', False, True, [], {}])
def test_raw_integers_enum_spellings_and_substitutes_are_rejected(value):
    state = state_03()
    state['characters'][0]['slave_state'] = value
    with pytest.raises(OracleSchemaError):
        validate_state(state)


@pytest.mark.parametrize('value', ['', 'bad\nidentifier', 'bad\x00id', 42, False, [], 'x' * 513])
def test_owner_faction_is_a_nullable_opaque_id(value):
    state = state_03()
    state['characters'][0]['slave_owner_faction_id'] = '1083-gamedata.base'
    assert validate_state(state) is state
    state['characters'][0]['slave_owner_faction_id'] = value
    with pytest.raises(OracleSchemaError):
        validate_state(state)


def test_owner_and_state_are_independent_unknowns():
    # The contract never infers one field from the other: an owner without a
    # known state, and a known escaping slave without a readable owner, are valid.
    state = state_03()
    state['characters'][0].update(slave_state=None, slave_owner_faction_id='f1')
    state['characters'][1].update(slave_state='escaping_slave', slave_owner_faction_id=None)
    assert validate_state(state) is state


def test_unknowns_stay_explicit_null_in_canonical_bytes():
    encoded = canonical_bytes(state_03())
    decoded = json.loads(encoded)
    for row in decoded['characters']:
        assert row['slave_state'] is None and row['slave_owner_faction_id'] is None
    assert b'"slave_state":null' in encoded
    assert b'"slave_owner_faction_id":null' in encoded
    assert b'not_slave' not in encoded


def test_projecting_03_fields_away_preserves_exact_02_bytes():
    state = state_03()
    state['characters'][0].update(slave_state='slave', slave_owner_faction_id='f1')
    state['schema_version'] = '0.2'
    for row in state['characters']:
        for name in ADDED:
            del row[name]
    assert canonical_bytes(state) == canonical_bytes(state_02())


def test_permutations_do_not_affect_bytes_or_mutate_input():
    state = state_03()
    state['characters'][0].update(slave_state='escaping_slave', slave_owner_faction_id='城-faction')
    original = deepcopy(state)
    permuted = {key: value for key, value in reversed(list(deepcopy(state).items()))}
    for collection in ('characters', 'squads', 'factions', 'relations'):
        permuted[collection].reverse()
        permuted[collection] = [{key: value for key, value in reversed(list(row.items()))}
                                for row in permuted[collection]]
    expected = canonical_bytes(state)
    assert canonical_bytes(permuted) == expected
    assert state == original
    assert b'"slave_state":"escaping_slave"' in expected
    assert '城-faction'.encode('utf-8') in expected
    assert expected.endswith(b'\n') and b'\r\n' not in expected
    assert canonical_bytes(json.loads(expected)) == expected


def test_03_file_load_round_trips_and_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / 'state-03.json'
    raw = canonical_bytes(state_03())
    path.write_bytes(raw)
    assert canonical_bytes(load_state(path)) == raw
    path.write_bytes(raw.replace(b'"slave_state":null', b'"slave_state":null,"slave_state":"not_slave"', 1))
    with pytest.raises(OracleSchemaError, match='Duplicate'):
        load_state(path)


# Comparison: the new fields are ordinary character fields of saved characters.

def compare_state_03(slave_state=None, owner=None):
    value = compare_state()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    value['characters'][0].update(slave_state=slave_state, slave_owner_faction_id=owner)
    return value


def slave_findings(left, right):
    findings = by_metric(saved_metrics(states(left), states(right, 'meitou')))
    return {key: findings[f'/characters/{FIRST}/{key}']['classification'] for key in sorted(ADDED)}


def test_03_comparison_classifies_the_slave_fields_as_character_fields():
    same = compare_state_03('escaping_slave', 'f-owner')
    assert slave_findings(same, same) == dict(slave_owner_faction_id='stable_identical',
                                              slave_state='stable_identical')
    other = compare_state_03('slave', 'f-other')
    assert slave_findings(same, other) == dict(slave_owner_faction_id='stable_divergent',
                                               slave_state='stable_divergent')


def test_null_slave_state_never_equals_not_slave():
    known = compare_state_03('not_slave', None)
    unknown = compare_state_03(None, None)
    result = slave_findings(known, unknown)
    assert result['slave_state'] == 'not_comparable'
    # Null on both sides is still unknown coverage, not agreement.
    assert slave_findings(unknown, unknown)['slave_state'] == 'not_comparable'
    assert slave_findings(unknown, unknown)['slave_owner_faction_id'] == 'not_comparable'
    assert slave_findings(known, known)['slave_state'] == 'stable_identical'


def test_02_comparison_gains_no_slave_metric():
    findings = saved_metrics(states(compare_state()), states(compare_state(), 'meitou'))
    assert not [row for row in findings if 'slave' in row['metric']]


def snapshot_03(target, index, point):
    return compare_state_03('escaping_slave', None)


def test_03_campaigns_compare_and_report_the_new_fields(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_03)
    campaign(meitou, 'meitou', snapshot=snapshot_03)
    compare_campaigns(original, meitou, tmp_path / 'out')
    report = json.loads((tmp_path / 'out' / 'report.json').read_text(encoding='utf-8'))
    found = {(row['checkpoint'], row['metric']): row['classification'] for row in report['findings']}
    for point in ('initial', 'later'):
        assert found[(point, f'/characters/{FIRST}/slave_state')] == 'stable_identical'
        assert found[(point, f'/characters/{FIRST}/slave_owner_faction_id')] == 'not_comparable'
        assert found[(point, f'/characters/{SECOND}/slave_state')] == 'not_comparable'


def test_mixed_state_schema_versions_are_refused_between_campaigns(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_03)
    campaign(meitou, 'meitou')
    with pytest.raises(ValueError, match='same state schema version'):
        compare_campaigns(original, meitou, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_mixed_state_schema_versions_are_refused_within_a_campaign(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'

    def mixed(target, index, point):
        return compare_state_03() if index == 3 else compare_state()
    campaign(original, 'original', snapshot=mixed)
    campaign(meitou, 'meitou')
    with pytest.raises(ValueError, match='recorded state schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def test_snapshot_must_match_the_reports_recorded_state_schema(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    # commit= makes the fixture record state_schema "0.2" in both reports.
    commit = '0123456789abcdef0123456789abcdef01234567'
    campaign(original, 'original', snapshot=snapshot_03, commit=commit)
    campaign(meitou, 'meitou', snapshot=snapshot_03, commit=commit)
    with pytest.raises(ValueError, match='recorded state schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def test_01_snapshots_are_still_refused_by_the_comparator(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'

    def legacy(target, index, point):
        from fake_probe import sample_state
        return sample_state()
    campaign(original, 'original', snapshot=legacy)
    campaign(meitou, 'meitou', snapshot=legacy)
    with pytest.raises(ValueError, match='Snapshot schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def test_meitou_target_keeps_an_explicit_03_or_02(tmp_path):
    from test_meitou_targets import target_files
    from oracle_targets import target_config
    assert target_config(target_files(tmp_path, state_schema='0.3'), 'meitou')['state_schema'] == '0.3'
    pinned = tmp_path / 'pinned'
    pinned.mkdir()
    assert target_config(target_files(pinned, state_schema='0.2'), 'meitou')['state_schema'] == '0.2'
