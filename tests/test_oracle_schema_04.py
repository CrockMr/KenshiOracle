"""Additive 0.4 medical, stats, use-stuff, carrying and money contract, its comparison, and unchanged 0.3 rules."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from oracle_compare import saved_metrics
from oracle_comparison import compare_campaigns
from oracle_schema import (COMPARABLE_STATE_SCHEMA_VERSIONS, LATEST_STATE_SCHEMA_VERSION, MEDICAL_KEYS,
                           STATE_SCHEMA_VERSIONS, STATS_KEYS, OracleSchemaError, canonical_bytes, load_state,
                           validate_state)
from test_oracle_compare import FIRST, SECOND, by_metric, state as compare_state, states
from test_oracle_comparison import (BYSTANDER, PLAYER_SQUAD, alias_map, by_alias, campaign, rows_by_metric,
                                    scene_campaigns, scene_report, values)
from test_oracle_schema_03 import state_03


CHARACTER_ADDED = ['medical', 'stats', 'in_something', 'carrying', 'carrying_id', 'being_carried']
PART_ADDED = ['bandage', 'splint', 'wear']
ROOT = Path(__file__).resolve().parents[1] / 'schema'
# The contract's 34 keys (KenshiLib StatsEnumerated without STAT_, lower case).
CONTRACT_STATS = {
    'strength', 'melee_attack', 'labouring', 'science', 'engineering', 'robotics', 'smithing_weapon',
    'smithing_armour', 'medic', 'thieving', 'turrets', 'farming', 'cooking', 'stealth', 'athletics', 'dexterity',
    'melee_defence', 'toughness', 'assassination', 'swimming', 'perception', 'katanas', 'sabres', 'hackers',
    'heavyweapons', 'blunt', 'martialarts', 'masscombat', 'dodge', 'polearms', 'crossbows', 'friendly_fire',
    'lockpicking', 'smithing_bow'}


def add_04(value):
    """Turn a valid 0.3 state into 0.4 with every new field unknown."""
    value['schema_version'] = '0.4'
    for row in value['characters']:
        row.update(medical=None, stats=None, in_something=None, carrying=None, carrying_id=None,
                   being_carried=None)
        for part in row['health'] or []:
            part.update(bandage=None, splint=None, wear=None)
    for row in value['squads']:
        row.update(money=None)
    return value


def state_04():
    return add_04(state_03())


def medical(**updates):
    return dict(dict(blood=97.5, bleed_rate=0.25, hunger=1.5, fed=2.0, coma=False, blood_loss_trauma=False),
                **updates)


def stats(value=10.0):
    return {key: value for key in STATS_KEYS}


def filled():
    value = state_04()
    value['characters'][0].update(medical=medical(), stats=stats(), in_something='bed', carrying='character',
                                  carrying_id=SECOND, being_carried=False)
    value['characters'][1].update(in_something='prison', carrying='nothing', being_carried=True)
    for row in value['characters']:
        for part in row['health']:
            part.update(bandage=20, splint=0, wear=1.5)
    value['squads'][0]['money'] = 4200
    return value


def schema(filename):
    return json.loads((ROOT / filename).read_text(encoding='utf-8'))


def test_schema_04_is_self_contained_valid_and_only_adds_to_03():
    old, new = schema('state-0.3.schema.json'), schema('state-0.4.schema.json')
    Draft202012Validator.check_schema(new)
    assert new['properties']['schema_version']['const'] == '0.4'
    assert new['$id'] == 'urn:kenshi-oracle:state:0.4'
    assert old['required'] == new['required']
    assert old['additionalProperties'] is new['additionalProperties'] is False
    for key, value in old['properties'].items():
        if key != 'schema_version':
            assert new['properties'][key] == value
    changed = {'character', 'squad', 'health_part'}
    for key, value in old['$defs'].items():
        if key not in changed:
            assert new['$defs'][key] == value
    assert set(new['$defs']) - set(old['$defs']) == {'medical', 'stats'}
    for name, added in (('character', CHARACTER_ADDED), ('health_part', PART_ADDED), ('squad', ['money'])):
        before, after = old['$defs'][name], new['$defs'][name]
        assert set(after['properties']) - set(before['properties']) == set(added)
        assert after['required'] == before['required'] + added
        for key, value in before['properties'].items():
            assert after['properties'][key] == value
        assert after['additionalProperties'] is False
    before, after = old['$defs']['character'], new['$defs']['character']
    assert after['allOf'][:len(before['allOf'])] == before['allOf'] and len(after['allOf']) == len(before['allOf']) + 1
    assert after['properties']['in_something']['enum'] == ['nothing', 'bed', 'prison', None]
    assert after['properties']['carrying']['enum'] == ['nothing', 'character', 'other', None]
    assert set(new['$defs']['stats']['required']) == set(new['$defs']['stats']['properties']) == CONTRACT_STATS
    assert tuple(new['$defs']['stats']['required']) == STATS_KEYS and len(STATS_KEYS) == 34
    assert tuple(new['$defs']['medical']['required']) == MEDICAL_KEYS
    assert Draft202012Validator(new).is_valid(state_04()) and Draft202012Validator(new).is_valid(filled())


def test_versions_and_comparable_versions():
    assert STATE_SCHEMA_VERSIONS == ('0.1', '0.2', '0.3', '0.4', '0.5')
    assert LATEST_STATE_SCHEMA_VERSION == '0.5'
    assert COMPARABLE_STATE_SCHEMA_VERSIONS == ('0.2', '0.3', '0.4', '0.5')
    assert validate_state(state_04())['schema_version'] == '0.4'
    assert validate_state(filled())['schema_version'] == '0.4'
    assert validate_state(state_03())['schema_version'] == '0.3'


def test_version_switch_without_additions_is_rejected():
    value = state_03()
    value['schema_version'] = '0.4'
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('where', ['character', 'part', 'squad'])
def test_03_states_cannot_carry_the_04_fields(where):
    value = state_03()
    if where == 'character':
        value['characters'][0].update(medical=None)
    elif where == 'part':
        value['characters'][0]['health'][0].update(bandage=None)
    else:
        value['squads'][0].update(money=None)
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('name', CHARACTER_ADDED)
def test_every_character_field_is_required_even_when_unknown(name):
    value = state_04()
    del value['characters'][0][name]
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('name', PART_ADDED)
def test_every_part_field_is_required_even_when_unknown(name):
    value = state_04()
    del value['characters'][0]['health'][0][name]
    with pytest.raises(OracleSchemaError):
        validate_state(value)


def test_squad_money_is_required_even_when_unknown():
    value = state_04()
    del value['squads'][0]['money']
    with pytest.raises(OracleSchemaError):
        validate_state(value)


def test_health_null_keeps_its_01_rule():
    value = state_04()
    value['characters'][0]['health'] = None
    assert validate_state(value) is value


@pytest.mark.parametrize('name', MEDICAL_KEYS)
def test_every_medical_key_is_required_and_nullable(name):
    value = filled()
    value['characters'][0]['medical'][name] = None
    assert validate_state(value) is value
    del value['characters'][0]['medical'][name]
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('bad', [{}, [], 0, False, 'none', dict(medical(), extra=1)])
def test_medical_is_an_object_with_six_keys_or_null(bad):
    value = filled()
    value['characters'][0]['medical'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('key,bad', [('coma', 0), ('coma', 'false'), ('blood_loss_trauma', 1),
                                     ('blood', True), ('blood', '97'), ('hunger', [])])
def test_medical_value_types(key, bad):
    value = filled()
    value['characters'][0]['medical'][key] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


def test_stats_values_are_nullable_numbers():
    value = filled()
    value['characters'][0]['stats'] = {key: None for key in STATS_KEYS}
    assert validate_state(value) is value
    value['characters'][0]['stats']['strength'] = True
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('change', ['missing', 'extra', 'survival', 'weapons', 'hivemedic', 'vet', 'upper',
                                    'prefixed', 'empty'])
def test_wrong_stats_key_sets_are_rejected(change):
    value = filled()
    row = value['characters'][0]['stats']
    if change == 'missing':
        del row['strength']
    elif change == 'extra':
        row['unknown_stat'] = 1
    elif change in ('survival', 'weapons', 'hivemedic', 'vet'):
        row[change] = 1
    elif change == 'upper':
        row['STRENGTH'] = row.pop('strength')
    elif change == 'prefixed':
        row['stat_strength'] = row.pop('strength')
    else:
        value['characters'][0]['stats'] = {}
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('field', ['in_something', 'carrying'])
@pytest.mark.parametrize('bad', [0, 1, 2, '', 'IN_BED', 'in_bed', 'Bed', 'unknown', False, [], {}])
def test_enumerations_reject_raw_values_and_spellings(field, bad):
    value = filled()
    value['characters'][1][field] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('carrying', ['nothing', 'other', None])
def test_carrying_id_without_carrying_character_is_rejected(carrying):
    value = filled()
    value['characters'][0].update(carrying=carrying, carrying_id=SECOND)
    with pytest.raises(OracleSchemaError):
        validate_state(value)
    value['characters'][0]['carrying_id'] = None
    assert validate_state(value) is value


@pytest.mark.parametrize('bad', [None, '', 42, 'bad\nid'])
def test_carrying_character_requires_an_id(bad):
    value = filled()
    value['characters'][0]['carrying_id'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('bad', [0, 1, 'true', [], {}])
def test_being_carried_is_a_nullable_boolean(bad):
    value = filled()
    value['characters'][0]['being_carried'] = None
    assert validate_state(value) is value
    value['characters'][0]['being_carried'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('where', ['blood', 'stat', 'bandage', 'splint', 'wear', 'money'])
@pytest.mark.parametrize('bad', [1e9 + 1, -1e9 - 1, 2e12])
def test_out_of_range_values_are_rejected(where, bad):
    value = filled()
    row = value['characters'][0]
    if where == 'blood':
        row['medical']['blood'] = bad
    elif where == 'stat':
        row['stats']['katanas'] = bad
    elif where == 'money':
        value['squads'][0]['money'] = int(bad)
    else:
        row['health'][0][where] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('bad', [1.5, '4200', True, []])
def test_money_is_a_nullable_integer(bad):
    value = filled()
    value['squads'][0]['money'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


def test_range_limits_are_accepted():
    value = filled()
    value['characters'][0]['medical'].update(blood=1e9, bleed_rate=-1e9)
    value['characters'][0]['stats']['strength'] = -1e9
    value['squads'][0]['money'] = -1000000000
    assert validate_state(value) is value


def test_unknowns_stay_explicit_null_in_canonical_bytes():
    encoded = canonical_bytes(state_04())
    for key in ('medical', 'stats', 'in_something', 'carrying', 'carrying_id', 'being_carried',
                'bandage', 'splint', 'wear', 'money'):
        assert f'"{key}":null'.encode() in encoded
    assert b'"nothing"' not in encoded and b'{}' not in encoded


def test_projecting_04_fields_away_preserves_exact_03_bytes():
    value = filled()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        for name in CHARACTER_ADDED:
            del row[name]
        for part in row['health']:
            for name in PART_ADDED:
                del part[name]
    for row in value['squads']:
        del row['money']
    assert canonical_bytes(value) == canonical_bytes(state_03())


def test_permutations_do_not_affect_bytes_or_mutate_input():
    value = filled()
    original = deepcopy(value)
    permuted = deepcopy(value)
    for collection in ('characters', 'squads', 'factions', 'relations'):
        permuted[collection].reverse()
    for row in permuted['characters']:
        row['stats'] = None if row['stats'] is None else dict(reversed(list(row['stats'].items())))
    expected = canonical_bytes(value)
    assert canonical_bytes(permuted) == expected and value == original
    assert canonical_bytes(json.loads(expected)) == expected


def test_04_file_load_round_trips_and_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / 'state-04.json'
    raw = canonical_bytes(state_04())
    path.write_bytes(raw)
    assert canonical_bytes(load_state(path)) == raw
    path.write_bytes(raw.replace(b'"money":null', b'"money":null,"money":0', 1))
    with pytest.raises(OracleSchemaError, match='Duplicate'):
        load_state(path)


# Comparison: the new fields are ordinary character, part and squad metrics.

def compare_state_04(**first):
    value = compare_state()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    add_04(value)
    value['characters'][0].update(first)
    return value


def findings(left, right):
    return by_metric(saved_metrics(states(left), states(right, 'meitou')))


def classes(result, prefix=f'/characters/{FIRST}/'):
    return {key[len(prefix):]: row['classification'] for key, row in result.items() if key.startswith(prefix)}


def test_04_comparison_emits_every_medical_and_stats_key_even_when_null():
    result = classes(findings(compare_state_04(), compare_state_04()))
    for key in MEDICAL_KEYS:
        assert result[f'medical/{key}'] == 'not_comparable'
    for key in STATS_KEYS:
        assert result[f'stats/{key}'] == 'not_comparable'
    for key in ('in_something', 'carrying', 'carrying_id', 'being_carried'):
        assert result[key] == 'not_comparable'
    for key in PART_ADDED:
        assert result[f'health/fixture-head:neither/{key}'] == 'not_comparable'


def test_04_comparison_classifies_known_values():
    known = compare_state_04(medical=medical(), stats=stats(), in_something='bed', carrying='character',
                             carrying_id=SECOND, being_carried=False)
    for part in known['characters'][0]['health']:
        part.update(bandage=20, splint=0, wear=1.5)
    same = classes(findings(known, known))
    assert {same[f'medical/{key}'] for key in MEDICAL_KEYS} == {'stable_identical'}
    assert {same[f'stats/{key}'] for key in STATS_KEYS} == {'stable_identical'}
    for key in ('in_something', 'carrying', 'carrying_id', 'being_carried', 'health/fixture-head:neither/bandage',
                'health/fixture-head:neither/splint', 'health/fixture-head:neither/wear'):
        assert same[key] == 'stable_identical'
    other = deepcopy(known)
    other['characters'][0].update(medical=medical(blood=50, coma=True), in_something='prison', carrying='nothing',
                                  carrying_id=None, being_carried=True)
    other['characters'][0]['stats']['katanas'] = 11.0
    other['characters'][0]['health'][0]['wear'] = 2
    result = classes(findings(known, other))
    assert result['medical/blood'] == result['medical/coma'] == 'stable_divergent'
    assert result['medical/fed'] == 'stable_identical'
    assert result['stats/katanas'] == 'stable_divergent' and result['stats/strength'] == 'stable_identical'
    assert result['in_something'] == result['carrying'] == result['being_carried'] == 'stable_divergent'
    assert result['health/fixture-head:neither/wear'] == 'stable_divergent'
    # Known on one side, null on the other: never a divergence.
    assert result['carrying_id'] == 'not_comparable'


def test_null_on_one_side_is_never_a_divergence():
    known = compare_state_04(medical=medical(), stats=stats(0), in_something='nothing', carrying='nothing',
                             being_carried=False)
    unknown = compare_state_04()
    result = classes(findings(known, unknown))
    assert {value for key, value in result.items()
            if key.split('/')[0] in ('medical', 'stats', 'in_something', 'carrying', 'being_carried')} == {
        'not_comparable'}
    partial = deepcopy(known)
    partial['characters'][0]['medical']['blood'] = None
    partial['characters'][0]['stats']['dodge'] = None
    result = classes(findings(known, partial))
    assert result['medical/blood'] == result['stats/dodge'] == 'not_comparable'
    assert result['medical/hunger'] == result['stats/strength'] == 'stable_identical'


def test_carrying_id_uses_the_order_target_reference_rule():
    # A proven saved HAND is kept; any other identity (generated, unknown) becomes null.
    proven = compare_state_04(carrying='character', carrying_id=SECOND)
    assert classes(findings(proven, proven))['carrying_id'] == 'stable_identical'
    assert findings(proven, proven)[f'/characters/{FIRST}/carrying_id']['original']['values'] == [SECOND] * 5
    loose = compare_state_04(carrying='character', carrying_id='local:carried-7')
    row = findings(loose, loose)[f'/characters/{FIRST}/carrying_id']
    assert row['classification'] == 'not_comparable' and row['original']['values'] == [None] * 5
    assert classes(findings(loose, loose))['carrying'] == 'stable_identical'


def test_03_comparison_gains_no_04_metric():
    value = compare_state()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    metrics = [row['metric'] for row in saved_metrics(states(value), states(value, 'meitou'))]
    for word in ('medical', 'stats', 'in_something', 'carrying', 'being_carried', 'bandage', 'splint', 'wear',
                 'money'):
        assert not [metric for metric in metrics if word in metric]


def snapshot_04(target, index, point):
    value = compare_state_04(medical=medical(), carrying='nothing', in_something='nothing')
    value['squads'][0]['money'] = 4200 if target == 'original' else 4100
    return value


def test_04_campaigns_compare_and_report_the_new_fields(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_04)
    campaign(meitou, 'meitou', snapshot=snapshot_04)
    compare_campaigns(original, meitou, tmp_path / 'out')
    report = json.loads((tmp_path / 'out' / 'report.json').read_text(encoding='utf-8'))
    found = {(row['checkpoint'], row['metric']): row['classification'] for row in report['findings']}
    squad = '/squads/' + 'hand:34:7:101:0:0' + '/money'
    for point in ('initial', 'later'):
        assert found[(point, f'/characters/{FIRST}/medical/blood')] == 'stable_identical'
        assert found[(point, f'/characters/{FIRST}/carrying')] == 'stable_identical'
        assert found[(point, f'/characters/{FIRST}/stats/strength')] == 'not_comparable'
        assert found[(point, f'/characters/{SECOND}/medical/blood')] == 'not_comparable'
        assert found[(point, squad)] == 'stable_divergent'


def test_unknown_squad_money_is_not_comparable(tmp_path):
    def snapshot(target, index, point):
        value = snapshot_04(target, index, point)
        if target == 'meitou':
            value['squads'][0]['money'] = None
        return value
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot)
    campaign(meitou, 'meitou', snapshot=snapshot)
    compare_campaigns(original, meitou, tmp_path / 'out')
    report = json.loads((tmp_path / 'out' / 'report.json').read_text(encoding='utf-8'))
    found = {(row['checkpoint'], row['metric']): row['classification'] for row in report['findings']}
    assert found[('later', '/squads/hand:34:7:101:0:0/money')] == 'not_comparable'


@pytest.mark.parametrize('other', ['0.3', '0.2'])
def test_mixed_state_schema_versions_are_refused_between_campaigns(tmp_path, other):
    def earlier(target, index, point):
        value = compare_state()
        if other == '0.3':
            value['schema_version'] = '0.3'
            for row in value['characters']:
                row.update(slave_state=None, slave_owner_faction_id=None)
        return value
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_04)
    campaign(meitou, 'meitou', snapshot=earlier)
    with pytest.raises(ValueError, match='same state schema version'):
        compare_campaigns(original, meitou, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_mixed_03_and_04_snapshots_are_refused_within_a_campaign(tmp_path):
    def mixed(target, index, point):
        if index == 2:
            value = compare_state()
            value['schema_version'] = '0.3'
            for row in value['characters']:
                row.update(slave_state=None, slave_owner_faction_id=None)
            return value
        return snapshot_04(target, index, point)
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=mixed)
    campaign(meitou, 'meitou', snapshot=snapshot_04)
    with pytest.raises(ValueError, match='recorded state schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def test_04_snapshot_must_match_the_reports_recorded_state_schema(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    commit = '0123456789abcdef0123456789abcdef01234567'  # records state_schema "0.2"
    campaign(original, 'original', snapshot=snapshot_04, commit=commit)
    campaign(meitou, 'meitou', snapshot=snapshot_04, commit=commit)
    with pytest.raises(ValueError, match='recorded state schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def scene_04(target, index, point, value):
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    add_04(value)
    player = by_alias(value, target, index, 'player')
    leader = alias_map(target, index)['raiders/leader.base/1']
    player.update(medical=medical(), carrying='character', carrying_id=leader)
    for row in value['squads']:
        row['money'] = 300 if row['identity_origin'] == 'saved' else 999


def test_04_scene_scope_records_new_fields_in_outcome_and_background(tmp_path, monkeypatch):
    # The scene fixture records state_schema "0.2" in its reports; record 0.4 instead.
    import test_oracle_comparison as fixtures
    original_campaign = fixtures.campaign

    def campaign_04(*args, **kwargs):
        report = original_campaign(*args, **kwargs)
        report['state_schema'] = '0.4'
        fixtures.save_report(args[0], report)
        return report
    monkeypatch.setattr(fixtures, 'campaign', campaign_04)
    original, meitou, _, _, output = scene_campaigns(tmp_path, scene_04)
    report = scene_report(original, meitou, output)
    assert all(row['metric'].startswith('/scene/') and not row['metric'].startswith('/scene/outcome/')
               for row in report['findings'])
    outcome = rows_by_metric(report['scene_outcome'])
    blood = outcome['/scene/outcome/characters/alias:player/medical/blood']
    assert values(blood, 'original') == values(blood, 'meitou') == [97.5] * 5
    carried = outcome['/scene/outcome/characters/alias:player/carrying_id']
    assert values(carried, 'original') == values(carried, 'meitou') == ['alias:raiders/leader.base'] * 5
    assert '/scene/outcome/characters/alias:player/stats/strength' in outcome
    background = rows_by_metric(report['background_metrics'])
    money = background['/background/squads/' + PLAYER_SQUAD + '/money']
    assert values(money, 'original') == [300] * 5
    assert '/background/characters/' + BYSTANDER + '/medical/blood' in background
    # Spawn alias squads never get a raw-id money metric.
    assert not [metric for metric in background if metric.endswith('/money') and PLAYER_SQUAD not in metric
                and 'hand:34:7:101:0:1' not in metric]


def test_meitou_target_keeps_an_explicit_04_or_03(tmp_path):
    from test_meitou_targets import target_files
    from oracle_targets import target_config
    assert target_config(target_files(tmp_path, state_schema='0.4'), 'meitou')['state_schema'] == '0.4'
    pinned = tmp_path / 'pinned'
    pinned.mkdir()
    assert target_config(target_files(pinned, state_schema='0.3'), 'meitou')['state_schema'] == '0.3'
