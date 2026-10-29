"""All six statistical classes and strict saved-identity matching, synthetic only."""
from copy import deepcopy
import math
import json

import pytest

from fake_probe import sample_state
from oracle_compare import CLASSES, classify_metric, saved_metrics


def observations(values, target='original'):
    return [dict(repetition=index, snapshot=f'{target}/{index}/state.json', value=value)
            for index, value in enumerate(values, 1)]


def compare(left, right, **kwargs):
    return classify_metric('/metric', observations(left), observations(right, 'meitou'), **kwargs)


@pytest.mark.parametrize('left,right,expected', [
    ([2]*5, [2]*5, 'stable_identical'),
    ([2]*5, [3]*5, 'stable_divergent'),
    ([2]*5, [2, 3, 2, 3, 2], 'stable_divergent'),
    ([1, 2, 3, 4, 5], [2, 3, 4, 3, 2], 'variable_compatible'),
    ([1, 2, 3, 4, 5], [0, 2, 3, 4, 6], 'variable_outside_range'),
    ([2]*5, [None]*5, 'not_comparable'),
])
def test_observed_classes(left, right, expected):
    finding = compare(left, right)
    assert finding['classification'] == expected
    assert finding['original']['n'] == finding['meitou']['n'] == 5
    assert not finding['warnings']
    assert finding['original']['values'] == left
    assert finding['meitou']['observations'][0]['snapshot'] == 'meitou/1/state.json'


def test_known_deviation_requires_explicit_exact_bounded_evidence_and_preserves_base_class():
    rule = dict(metric='/metric', id='rekenshi-speed-callbacks',
                source='https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1442',
                explanation='A separately reproduced callback difference affects this metric only.',
                evidence='evidence/callback-reproduction.json')
    finding = compare([2]*5, [3]*5, known_deviation=rule)
    assert finding['classification'] == 'known_deviation'
    assert finding['base_classification'] == 'stable_divergent'
    assert finding['known_deviation'] == rule
    assert finding['known_deviation'] is not rule
    assert compare([2]*5, [2]*5, known_deviation=rule)['classification'] == 'stable_identical'
    assert set(CLASSES) == {'stable_identical', 'stable_divergent', 'variable_compatible',
                            'variable_outside_range', 'known_deviation', 'not_comparable'}


@pytest.mark.parametrize('patch', [dict(metric='*'), dict(id=''), dict(source=''), dict(source='not-a-url'),
                                  dict(explanation=''), dict(evidence='')])
def test_known_deviation_cannot_be_global_or_unsourced(patch):
    rule = dict(metric='/metric', id='rekenshi-startup-srand', source='https://example.test/source',
                explanation='Explicit metric-specific explanation', evidence='evidence/reproduction.json')
    rule.update(patch)
    with pytest.raises(ValueError):
        compare([1]*5, [9]*5, known_deviation=rule)
    # A broad RNG difference is never automatically attributed to startup srand.
    assert compare([1]*5, [9]*5)['classification'] == 'stable_divergent'


def test_range_median_and_outside_count_are_observations_not_significance_tests():
    finding = compare([1, 2, 3, 4, 100], [0, 1, 3, 100, 101])
    assert finding['original']['min'] == 1
    assert finding['original']['max'] == 100
    assert finding['original']['median'] == 3
    assert finding['meitou']['median'] == 3
    assert finding['meitou']['outside_count'] == 2
    assert 'p_value' not in finding and 'significant' not in finding


def test_large_finite_aggregate_values_do_not_overflow_the_report_median():
    finding = compare([1e308, 1e308], [1e308, 1e308])
    assert finding['original']['median'] == 1e308
    json.dumps(finding, allow_nan=False)


def test_tolerance_does_not_remove_original_variability():
    finding = compare([1, 1.000001, 1, 1.000001, 1], [1.000002]*5, tolerance=0.000002)
    assert finding['original']['exact_stable'] is False
    assert finding['classification'] == 'variable_compatible'
    assert finding['comparison_exact'] is False
    assert finding['tolerance']['absolute'] == 0.000002
    assert finding['meitou']['outside_count'] == 0


def test_tolerated_stable_parity_does_not_claim_exact_meitou_stability():
    finding = compare([1]*5, [1, 1.000001, 1, 1.000001, 1], tolerance=0.000002)
    assert finding['classification'] == 'stable_identical'
    assert finding['original']['exact_stable'] is True
    assert finding['meitou']['exact_stable'] is False
    assert finding['comparison_exact'] is False


def test_range_boundary_tolerance_is_explicit_and_separate_from_classification():
    finding = compare([10, 11, 12, 11, 10], [9.75, 12.25, 10, 11, 12], tolerance=.25, units='world_units')
    assert finding['classification'] == 'variable_compatible'
    assert finding['tolerance'] == dict(absolute=.25, units='world_units')
    assert compare([10, 11, 12], [9.74], tolerance=.25)['classification'] == 'variable_outside_range'


@pytest.mark.parametrize('left,right,expected', [
    (['alive']*5, ['alive']*5, 'stable_identical'),
    (['alive']*5, ['dead']*5, 'stable_divergent'),
    (['alive', 'dead'], ['dead', 'alive'], 'variable_compatible'),
    (['alive', 'dead'], ['unconscious'], 'variable_outside_range'),
    ([True, False], [True, False], 'variable_compatible'),
    ([True]*5, [1]*5, 'not_comparable'),
    ([1, '1'], [1, '1'], 'not_comparable'),
])
def test_categorical_sets_and_boolean_numeric_type_safety(left, right, expected):
    finding = compare(left, right)
    assert finding['classification'] == expected
    if type(left[0]) is str and expected != 'not_comparable':
        assert finding['original']['median'] is None
        assert finding['original']['frequencies']


@pytest.mark.parametrize('unknown', [None, math.nan, math.inf, -math.inf, [], {}])
def test_one_unknown_observation_invalidates_whole_metric_without_silently_dropping_it(unknown):
    finding = compare([1, 1, 1, 1, unknown], [1]*5)
    assert finding['classification'] == 'not_comparable'
    assert finding['original']['n'] == 5 and finding['original']['comparable_n'] == 4
    assert finding['meitou']['outside_count'] is None
    json.dumps(finding, allow_nan=False)


def test_empty_or_missing_observations_do_not_become_zero_or_stable_agreement():
    finding = compare([], [])
    assert finding['classification'] == 'not_comparable'
    assert len(finding['warnings']) == 2
    rows = observations([1]*5)
    rows[2].update(present=False, value=1)
    assert classify_metric('/metric', rows, observations([1]*5, 'meitou'))['classification'] == 'not_comparable'


def test_small_n_is_reported_without_reclassifying_observations():
    finding = compare([1, 2], [1.5])
    assert finding['classification'] == 'variable_compatible'
    assert finding['original']['n'] == 2 and finding['meitou']['n'] == 1
    assert len(finding['warnings']) == 2


@pytest.mark.parametrize('tolerance', [-1, True, math.nan, math.inf, '1'])
def test_invalid_tolerance_is_rejected(tolerance):
    with pytest.raises(ValueError):
        compare([1], [1], tolerance=tolerance)


@pytest.mark.parametrize('snapshot', ['C:/private/state.json', '/private/state.json',
                                     'snapshots\\state.json', 'snapshots//state.json', 'snapshots/./state.json',
                                     'snapshots/line\nbreak.json', 'https://example.test/state.json'])
def test_evidence_paths_must_be_relative_without_machine_paths(snapshot):
    with pytest.raises(ValueError, match='relative'):
        classify_metric('/metric', [dict(repetition=1, snapshot=snapshot, value=1)], observations([1]))


@pytest.mark.parametrize('snapshot', ['../state.json', '../../scenario/run/1/initial.json', 'snapshots/../state.json'])
def test_relative_links_from_report_to_validated_external_campaign_evidence_are_preserved(snapshot):
    result = classify_metric('/metric', [dict(repetition=1, snapshot=snapshot, value=1)], observations([1]))
    assert result['classification'] == 'stable_identical'
    assert result['original']['observations'][0]['snapshot'] == snapshot


def test_duplicate_repetitions_are_rejected_and_inputs_are_not_mutated():
    left, right = observations([1, 2]), observations([2, 3], 'meitou')
    before = deepcopy((left, right))
    classify_metric('/metric', left, right)
    assert (left, right) == before
    left[1]['repetition'] = 1
    with pytest.raises(ValueError, match='one observation'):
        classify_metric('/metric', left, right)


def state():
    result = sample_state()
    result['schema_version'] = '0.2'
    for row in result['characters']:
        row.update(identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=False)
    for row in result['squads']:
        row.update(identity_origin='saved', template_id='fixture-template', origin_town_id=None)
    return result


def states(value, target='original', count=5):
    return [dict(repetition=index, snapshot=f'{target}/{index}/state.json', state=deepcopy(value))
            for index in range(1, count+1)]


def by_metric(findings):
    return {finding['metric']: finding for finding in findings}


FIRST = 'hand:1:7:101:1:1001'
SECOND = 'hand:1:7:101:2:1002'


def test_saved_individuals_pair_by_complete_handle_despite_collection_order_or_name_changes():
    original = state()
    meitou = deepcopy(original)
    meitou['characters'].reverse()
    meitou['characters'][1]['name'] = 'Different display name'
    findings = by_metric(saved_metrics(states(original), states(meitou, 'meitou')))
    assert findings[f'/characters/{FIRST}/name']['classification'] == 'stable_divergent'
    assert findings[f'/characters/{FIRST}/position/0']['classification'] == 'stable_identical'
    assert findings[f'/characters/{SECOND}/state']['classification'] == 'stable_identical'
    assert findings[f'/characters/{FIRST}/current_town_id']['classification'] == 'not_comparable'


@pytest.mark.parametrize('origin', [None, 'generated'])
def test_matching_ids_or_names_without_saved_provenance_never_pair_individuals(origin):
    original, meitou = state(), state()
    for row in original['characters']:
        row['identity_origin'] = origin
    findings = saved_metrics(states(original), states(meitou, 'meitou'))
    assert findings and all(row['classification'] == 'not_comparable' for row in findings)
    for row in meitou['characters']:
        row['identity_origin'] = origin
    coverage = saved_metrics(states(original), states(meitou, 'meitou'))
    assert len(coverage) == 1 and coverage[0]['metric'] == '/coverage/saved_characters'
    assert coverage[0]['classification'] == 'not_comparable'


@pytest.mark.parametrize('bad_id', ['hand:1:7:101:1', 'hand:1:7:101:1:4294967296',
                                  'hand:1:-1:101:1:1', 'hand:01:7:101:1:1', 'hand:34:7:101:1:1'])
def test_claimed_saved_origin_still_requires_full_canonical_uint32_character_handle(bad_id):
    original = state()
    for index, row in enumerate(original['characters']):
        row.update(id=bad_id + (str(index) if index else ''), identity_origin='saved')
    result = saved_metrics(states(original), states(original, 'meitou'))
    assert result[0]['classification'] == 'not_comparable'


def test_serial_or_container_serial_difference_does_not_pair_by_shortened_handle():
    original, meitou = state(), state()
    meitou['characters'][0]['id'] = 'hand:1:7:102:1:1001'
    meitou['characters'][1]['id'] = 'hand:1:7:101:2:1003'
    findings = saved_metrics(states(original), states(meitou, 'meitou'))
    assert findings and all(row['classification'] == 'not_comparable' for row in findings)


def test_one_unloaded_saved_character_or_unknown_health_part_is_not_zero():
    original = states(state())
    meitou = states(state(), 'meitou')
    meitou[-1]['state']['characters'].pop(0)
    findings = by_metric(saved_metrics(original, meitou))
    assert findings[f'/characters/{FIRST}/state']['classification'] == 'not_comparable'
    assert findings[f'/characters/{FIRST}/state']['meitou']['comparable_n'] == 4
    assert findings[f'/characters/{SECOND}/state']['classification'] == 'stable_identical'
    meitou = states(state(), 'meitou')
    meitou[-1]['state']['characters'][0]['health'] = None
    findings = by_metric(saved_metrics(original, meitou))
    assert findings[f'/characters/{FIRST}/health/count']['classification'] == 'not_comparable'
    assert findings[f'/characters/{FIRST}/health/fixture-head:neither/current']['classification'] == 'not_comparable'


def test_reference_to_unknown_origin_target_or_squad_is_not_compared_as_raw_identity():
    original, meitou = state(), state()
    for value in (original, meitou):
        value['characters'][0]['order'] = dict(type='attack', target_id=SECOND, position=None)
    meitou['characters'][1]['identity_origin'] = None
    meitou['squads'][0]['identity_origin'] = None
    findings = by_metric(saved_metrics(states(original), states(meitou, 'meitou')))
    assert findings[f'/characters/{FIRST}/order/type']['classification'] == 'stable_identical'
    assert findings[f'/characters/{FIRST}/order/target_id']['classification'] == 'not_comparable'
    assert findings[f'/characters/{FIRST}/squad_id']['classification'] == 'not_comparable'


def test_positions_use_explicit_default_or_metric_specific_tolerances_without_input_mutation():
    original, meitou = state(), state()
    meitou['characters'][0]['position'][0] = .000001
    before = deepcopy((original, meitou))
    metric = f'/characters/{FIRST}/position/0'
    finding = by_metric(saved_metrics(states(original), states(meitou, 'meitou')))[metric]
    assert finding['classification'] == 'stable_identical' and not finding['comparison_exact']
    finding = by_metric(saved_metrics(states(original), states(meitou, 'meitou'), tolerances={metric: 0}))[metric]
    assert finding['classification'] == 'stable_divergent'
    assert (original, meitou) == before


def test_01_does_not_invent_saved_origin_and_missing_state_remains_unknown():
    legacy = sample_state()
    finding = saved_metrics(states(legacy), states(legacy, 'meitou'))[0]
    assert finding['classification'] == 'not_comparable'
    original, meitou = states(state()), states(state(), 'meitou')
    meitou[0]['state'] = None
    findings = saved_metrics(original, meitou)
    assert all(row['classification'] == 'not_comparable' for row in findings)
