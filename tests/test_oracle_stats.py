"""Exact permutation tests that qualify comparator findings (mcp-server/oracle_stats.py)."""
import pytest

import oracle_stats
from oracle_stats import permutation_test, strength


def test_a_complete_separation_of_five_against_five_reaches_the_smallest_p_value():
    result = permutation_test([0, 0, 0, 0, 0], [1, 1, 1, 1, 1])
    assert result['test'] == 'permutation' and result['kind'] == 'number' and result['exact'] is True
    assert result['splits'] == 252 and result['p_value'] == pytest.approx(2 / 252)
    assert result['minimum_p_value'] == pytest.approx(2 / 252) and strength(result['p_value']) == 'strong'


def test_a_single_outlier_against_a_stable_original_is_weak():
    # The nature-bandit intruder count: 0 in 5 of 5 on the original, 11 and 8 in two Meitou repetitions.
    result = permutation_test([0, 0, 0, 0, 0], [0, 0, 11, 0, 8])
    assert result['p_value'] > 0.2 and strength(result['p_value']) == 'weak'
    one = permutation_test([0, 0, 0, 0, 0], [0, 0, 0, 0, 7])
    assert one['p_value'] == pytest.approx(1.0) and strength(one['p_value']) == 'weak'


def test_categories_use_the_distance_between_value_distributions():
    separated = permutation_test(['not_slave'] * 5, ['escaping_slave'] * 5)
    assert separated['kind'] == 'category' and separated['p_value'] == pytest.approx(2 / 252)
    mixed = permutation_test([True, False, True, False, True], [True, True, False, False, True])
    assert mixed['statistic'] == pytest.approx(0.0) and mixed['p_value'] == pytest.approx(1.0)


def test_identical_samples_are_never_significant():
    result = permutation_test([1.5, 2.5, 3.5, 4.5, 5.5], [1.5, 2.5, 3.5, 4.5, 5.5])
    assert result['statistic'] == pytest.approx(0.0) and result['p_value'] == pytest.approx(1.0)


def test_unequal_sizes_have_no_mirror_split():
    result = permutation_test([0, 0, 0], [1, 1, 1, 1, 1])
    # Only the observed split reaches |0 - 1|; three of the five ones against the rest give 0.6.
    assert result['splits'] == 56 and result['p_value'] == pytest.approx(1 / 56)
    assert result['minimum_p_value'] == pytest.approx(1 / 56)


@pytest.mark.parametrize('original, meitou', [
    ([], [1, 2]), ([1, 2], []), ([1, None], [1, 2]), ([1, 2], ['a', 'b']), ([True, False], [1, 0]),
    ([float('nan'), 1], [1, 2]), ([{'a': 1}], [{'a': 1}]),
])
def test_untestable_inputs_give_no_p_value(original, meitou):
    result = permutation_test(original, meitou)
    assert result['test'] is None and result['p_value'] is None and strength(result['p_value']) is None


def test_large_samples_use_a_fixed_seed_sample(monkeypatch):
    monkeypatch.setattr(oracle_stats, 'EXACT_SPLITS', 10)
    monkeypatch.setattr(oracle_stats, 'SAMPLED_SPLITS', 2000)
    first = permutation_test([0, 1, 2, 3, 4, 5], [3, 4, 5, 6, 7, 8])
    second = permutation_test([0, 1, 2, 3, 4, 5], [3, 4, 5, 6, 7, 8])
    assert first['exact'] is False and first['splits'] == 2000 and first == second
    assert 0 < first['p_value'] < 1


def test_strength_threshold():
    assert strength(0.0099) == 'strong' and strength(0.01) == 'weak' and strength(0.5, alpha=0.6) == 'strong'
