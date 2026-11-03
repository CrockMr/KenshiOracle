"""Additive 0.5 AI goal contract, its comparison, and unchanged 0.4 rules."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from oracle_compare import saved_metrics
from oracle_comparison import compare_campaigns
from oracle_schema import (COMPARABLE_STATE_SCHEMA_VERSIONS, GOAL_PRIORITIES, LATEST_STATE_SCHEMA_VERSION,
                           STATE_SCHEMA_VERSIONS, OracleSchemaError, canonical_bytes, load_state, validate_state)
from oracle_triage import field_pattern, triage
from test_oracle_compare import FIRST, SECOND, by_metric, state as compare_state, states
from test_oracle_comparison import (BYSTANDER, alias_map, by_alias, campaign, rows_by_metric, scene_campaigns,
                                    scene_report, values)
from test_oracle_schema_04 import add_04, state_04
from test_oracle_triage import finding, report as triage_report


ROOT = Path(__file__).resolve().parents[1] / 'schema'
GOAL_METRICS = ('goal/type', 'goal/priority', 'goal/target_id')


def add_05(value):
    """Turn a valid 0.4 state into 0.5 with every goal unknown."""
    value['schema_version'] = '0.5'
    for row in value['characters']:
        row.update(goal=None)
    return value


def state_05():
    return add_05(state_04())


def goal(kind='wander_town', priority='fluff', target_id=None):
    return dict(type=kind, priority=priority, target_id=target_id)


def filled():
    value = state_05()
    value['characters'][0]['goal'] = goal('melee_attack', 'urgent', SECOND)
    value['characters'][1]['goal'] = goal()
    return value


def schema(filename):
    return json.loads((ROOT / filename).read_text(encoding='utf-8'))


def test_schema_05_is_self_contained_valid_and_only_adds_the_goal_to_04():
    old, new = schema('state-0.4.schema.json'), schema('state-0.5.schema.json')
    Draft202012Validator.check_schema(new)
    assert new['properties']['schema_version']['const'] == '0.5'
    assert new['$id'] == 'urn:kenshi-oracle:state:0.5'
    assert old['required'] == new['required']
    assert old['additionalProperties'] is new['additionalProperties'] is False
    for key, value in old['properties'].items():
        if key != 'schema_version':
            assert new['properties'][key] == value
    for key, value in old['$defs'].items():
        if key != 'character':
            assert new['$defs'][key] == value
    assert set(new['$defs']) - set(old['$defs']) == {'goal'}
    before, after = old['$defs']['character'], new['$defs']['character']
    assert set(after['properties']) - set(before['properties']) == {'goal'}
    assert after['required'] == before['required'] + ['goal']
    for key, value in before['properties'].items():
        assert after['properties'][key] == value
    assert after['allOf'] == before['allOf'] and after['additionalProperties'] is False
    definition = new['$defs']['goal']
    assert definition['required'] == ['type', 'priority', 'target_id'] and definition['additionalProperties'] is False
    order = new['$defs']['order']['properties']
    # type and target_id are constrained exactly like order.type and order.target_id.
    assert {key: value for key, value in definition['properties']['type'].items() if key != 'description'} == {
        key: value for key, value in order['type'].items() if key != 'description'}
    assert definition['properties']['target_id'] == order['target_id']
    assert definition['properties']['priority']['enum'] == list(GOAL_PRIORITIES) + [None]
    assert GOAL_PRIORITIES == ('just_action', 'fluff', 'non_urgent', 'urgent', 'obedience')
    assert Draft202012Validator(new).is_valid(state_05()) and Draft202012Validator(new).is_valid(filled())


def test_versions_and_comparable_versions():
    assert STATE_SCHEMA_VERSIONS == ('0.1', '0.2', '0.3', '0.4', '0.5')
    assert LATEST_STATE_SCHEMA_VERSION == '0.5'
    assert COMPARABLE_STATE_SCHEMA_VERSIONS == ('0.2', '0.3', '0.4', '0.5')
    assert validate_state(state_05())['schema_version'] == '0.5'
    assert validate_state(filled())['schema_version'] == '0.5'
    assert validate_state(state_04())['schema_version'] == '0.4'


def test_version_switch_without_the_goal_is_rejected():
    value = state_04()
    value['schema_version'] = '0.5'
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('value', [None, goal()])
def test_04_states_cannot_carry_the_goal(value):
    state = state_04()
    state['characters'][0]['goal'] = value
    with pytest.raises(OracleSchemaError):
        validate_state(state)


def test_the_goal_is_required_even_when_unknown():
    value = state_05()
    del value['characters'][0]['goal']
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('name', ['type', 'priority', 'target_id'])
def test_every_goal_key_is_required(name):
    value = filled()
    del value['characters'][0]['goal'][name]
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('bad', [{}, [], 0, False, '', 'none', 'wander_town', dict(goal(), extra=1),
                                 dict(goal(), position=None)])
def test_goal_is_an_object_with_three_keys_or_null(bad):
    value = filled()
    value['characters'][0]['goal'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('priority', list(GOAL_PRIORITIES) + [None])
def test_every_priority_and_null_are_accepted(priority):
    value = filled()
    value['characters'][0]['goal']['priority'] = priority
    assert validate_state(value) is value


@pytest.mark.parametrize('bad', [0, 4, 5, True, '', 'URGENT', 'Urgent', 'tp_urgent', 'TP_URGENT', 'max_size',
                                 'nonurgent', 'non-urgent', [], {}])
def test_priority_rejects_raw_values_and_other_spellings(bad):
    value = filled()
    value['characters'][0]['goal']['priority'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


@pytest.mark.parametrize('kind', ['wander_town', 'idle', 'man_the_gate', 'job_medic', 'null_task', 'a' * 128])
def test_type_accepts_symbolic_row_names(kind):
    value = filled()
    value['characters'][0]['goal']['type'] = kind
    assert validate_state(value) is value


@pytest.mark.parametrize('bad', [None, '', 'WANDER_TOWN', 'Wander_town', '9idle', 'wander-town', 'wander town',
                                 37, 'a' * 129, True])
def test_type_follows_the_order_type_rule(bad):
    value = filled()
    value['characters'][0]['goal']['type'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)
    order = filled()
    order['characters'][0]['order'] = dict(type=bad, target_id=None, position=None)
    with pytest.raises(OracleSchemaError):
        validate_state(order)


@pytest.mark.parametrize('bad', ['', 42, 'bad\nid', False])
def test_target_id_follows_the_order_target_id_rule(bad):
    value = filled()
    value['characters'][0]['goal']['target_id'] = bad
    with pytest.raises(OracleSchemaError):
        validate_state(value)


def test_unknowns_stay_explicit_null_in_canonical_bytes():
    assert b'"goal":null' in canonical_bytes(state_05())
    value = filled()
    value['characters'][1]['goal'].update(priority=None)
    encoded = canonical_bytes(value)
    assert b'"goal":{"priority":null,"target_id":null,"type":"wander_town"}' in encoded


def test_projecting_the_goal_away_preserves_exact_04_bytes():
    value = filled()
    value['schema_version'] = '0.4'
    for row in value['characters']:
        del row['goal']
    assert canonical_bytes(value) == canonical_bytes(state_04())


def test_permutations_do_not_affect_bytes_or_mutate_input():
    value = filled()
    original = deepcopy(value)
    permuted = deepcopy(value)
    for collection in ('characters', 'squads', 'factions', 'relations'):
        permuted[collection].reverse()
    for row in permuted['characters']:
        row['goal'] = dict(reversed(list(row['goal'].items())))
    expected = canonical_bytes(value)
    assert canonical_bytes(permuted) == expected and value == original
    assert canonical_bytes(json.loads(expected)) == expected


def test_05_file_load_round_trips_and_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / 'state-05.json'
    raw = canonical_bytes(state_05())
    path.write_bytes(raw)
    assert canonical_bytes(load_state(path)) == raw
    path.write_bytes(raw.replace(b'"goal":null', b'"goal":null,"goal":null', 1))
    with pytest.raises(OracleSchemaError, match='Duplicate'):
        load_state(path)


# Comparison: goal/type, goal/priority and goal/target_id are ordinary character metrics in 0.5 only.

def compare_state_05(**first):
    value = compare_state()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    add_05(add_04(value))
    value['characters'][0].update(first)
    return value


def findings(left, right):
    return by_metric(saved_metrics(states(left), states(right, 'meitou')))


def classes(result, prefix=f'/characters/{FIRST}/'):
    return {key[len(prefix):]: row['classification'] for key, row in result.items() if key.startswith(prefix)}


def test_05_comparison_emits_the_three_goal_metrics_even_when_null():
    result = classes(findings(compare_state_05(), compare_state_05()))
    for key in GOAL_METRICS:
        assert result[key] == 'not_comparable'


def test_05_comparison_classifies_known_goals():
    known = compare_state_05(goal=goal('man_the_gate', 'non_urgent', SECOND))
    same = classes(findings(known, known))
    assert {same[key] for key in GOAL_METRICS} == {'stable_identical'}
    other = compare_state_05(goal=goal('wander_town', 'fluff', SECOND))
    result = classes(findings(known, other))
    assert result['goal/type'] == result['goal/priority'] == 'stable_divergent'
    assert result['goal/target_id'] == 'stable_identical'
    # The 0.4 metrics are unchanged next to the goal.
    assert result['medical/blood'] == 'not_comparable' and result['order/type'] == same['order/type']


def test_null_on_one_side_is_never_a_divergence():
    known = compare_state_05(goal=goal('idle', 'just_action', SECOND))
    result = classes(findings(known, compare_state_05()))
    assert {result[key] for key in GOAL_METRICS} == {'not_comparable'}
    partial = compare_state_05(goal=goal('idle', None, None))
    result = classes(findings(known, partial))
    assert result['goal/priority'] == result['goal/target_id'] == 'not_comparable'
    assert result['goal/type'] == 'stable_identical'


def test_goal_target_id_uses_the_order_target_reference_rule():
    # A proven saved HAND is kept; any other identity (generated, unknown) becomes null.
    proven = compare_state_05(goal=goal('melee_attack', 'urgent', SECOND))
    row = findings(proven, proven)[f'/characters/{FIRST}/goal/target_id']
    assert row['classification'] == 'stable_identical' and row['original']['values'] == [SECOND] * 5
    loose = compare_state_05(goal=goal('melee_attack', 'urgent', 'local:target-7'))
    row = findings(loose, loose)[f'/characters/{FIRST}/goal/target_id']
    assert row['classification'] == 'not_comparable' and row['original']['values'] == [None] * 5
    assert classes(findings(loose, loose))['goal/type'] == 'stable_identical'


def test_04_comparison_gains_no_goal_metric():
    value = compare_state()
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    add_04(value)
    metrics = [row['metric'] for row in saved_metrics(states(value), states(value, 'meitou'))]
    assert not [metric for metric in metrics if '/goal/' in metric]
    assert [metric for metric in metrics if metric.endswith('/medical/blood')]


def snapshot_05(target, index, point):
    return compare_state_05(goal=goal('wander_town', 'fluff' if target == 'original' else 'non_urgent'))


def test_05_campaigns_compare_and_report_the_goal(tmp_path):
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_05)
    campaign(meitou, 'meitou', snapshot=snapshot_05)
    compare_campaigns(original, meitou, tmp_path / 'out')
    report = json.loads((tmp_path / 'out' / 'report.json').read_text(encoding='utf-8'))
    found = {(row['checkpoint'], row['metric']): row['classification'] for row in report['findings']}
    for point in ('initial', 'later'):
        assert found[(point, f'/characters/{FIRST}/goal/type')] == 'stable_identical'
        assert found[(point, f'/characters/{FIRST}/goal/priority')] == 'stable_divergent'
        assert found[(point, f'/characters/{FIRST}/goal/target_id')] == 'not_comparable'
        assert found[(point, f'/characters/{SECOND}/goal/type')] == 'not_comparable'


@pytest.mark.parametrize('other', ['0.4', '0.3'])
def test_mixed_state_schema_versions_are_refused_between_campaigns(tmp_path, other):
    def earlier(target, index, point):
        value = compare_state()
        value['schema_version'] = '0.3'
        for row in value['characters']:
            row.update(slave_state=None, slave_owner_faction_id=None)
        return add_04(value) if other == '0.4' else value
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=snapshot_05)
    campaign(meitou, 'meitou', snapshot=earlier)
    with pytest.raises(ValueError, match='same state schema version'):
        compare_campaigns(original, meitou, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_mixed_04_and_05_snapshots_are_refused_within_a_campaign(tmp_path):
    def mixed(target, index, point):
        value = snapshot_05(target, index, point)
        if index == 2:
            value['schema_version'] = '0.4'
            for row in value['characters']:
                del row['goal']
        return value
    original = tmp_path / 'original'
    meitou = tmp_path / 'meitou'
    campaign(original, 'original', snapshot=mixed)
    campaign(meitou, 'meitou', snapshot=snapshot_05)
    with pytest.raises(ValueError, match='recorded state schema'):
        compare_campaigns(original, meitou, tmp_path / 'out')


def scene_05(target, index, point, value):
    value['schema_version'] = '0.3'
    for row in value['characters']:
        row.update(slave_state=None, slave_owner_faction_id=None)
    add_05(add_04(value))
    player = by_alias(value, target, index, 'player')
    leader = alias_map(target, index)['raiders/leader.base/1']
    player['goal'] = goal('melee_attack', 'urgent', leader)
    for row in value['characters']:
        if row['id'] == BYSTANDER:
            row['goal'] = goal()


def test_05_scene_scope_records_the_goal_in_outcome_and_background(tmp_path, monkeypatch):
    # The scene fixture records state_schema "0.2" in its reports; record 0.5 instead.
    import test_oracle_comparison as fixtures
    original_campaign = fixtures.campaign

    def campaign_05(*args, **kwargs):
        report = original_campaign(*args, **kwargs)
        report['state_schema'] = '0.5'
        fixtures.save_report(args[0], report)
        return report
    monkeypatch.setattr(fixtures, 'campaign', campaign_05)
    original, meitou, _, _, output = scene_campaigns(tmp_path, scene_05)
    report = scene_report(original, meitou, output)
    assert all(row['metric'].startswith('/scene/') and not row['metric'].startswith('/scene/outcome/')
               for row in report['findings'])
    outcome = rows_by_metric(report['scene_outcome'])
    kind = outcome['/scene/outcome/characters/alias:player/goal/type']
    assert values(kind, 'original') == values(kind, 'meitou') == ['melee_attack'] * 5
    target = outcome['/scene/outcome/characters/alias:player/goal/target_id']
    assert values(target, 'original') == values(target, 'meitou') == ['alias:raiders/leader.base'] * 5
    background = rows_by_metric(report['background_metrics'])
    priority = background['/background/characters/' + BYSTANDER + '/goal/priority']
    assert values(priority, 'original') == ['fluff'] * 5


def test_triage_rule_7_merges_one_goal_field_across_squads():
    # The generic character field pattern covers the goal: no new triage rule.
    assert field_pattern(f'/characters/{FIRST}/goal/type') == '/characters/*/goal/type'
    assert field_pattern(f'/characters/{FIRST}/goal/target_id') == '/characters/*/goal/target_id'
    rows = [finding(f'/characters/hand:1:{c}:101:1:{c}00{i}/goal/type', 'zero', ['idle'] * 5, ['wander_town'] * 5)
            for c in (7, 8) for i in (1, 2)]
    value = triage_report(rows)
    groups = triage(value)
    assert [group['entity'] for group in groups] == ['field:/characters/*/goal/type']
    assert groups[0]['size'] == 4 and groups[0]['onset'] == 'load'


def test_meitou_target_defaults_to_05_and_keeps_an_explicit_04(tmp_path):
    from test_meitou_targets import target_files
    from oracle_targets import target_config
    assert target_config(target_files(tmp_path), 'meitou')['state_schema'] == '0.5'
    pinned = tmp_path / 'pinned'
    pinned.mkdir()
    assert target_config(target_files(pinned, state_schema='0.4'), 'meitou')['state_schema'] == '0.4'
