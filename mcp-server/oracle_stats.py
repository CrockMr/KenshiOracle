"""Exact two-sample tests for comparator findings (standard library only, deterministic).

A two-sided permutation test over every split of the pooled repetitions into
groups of the original's and Meitou's sizes: |difference of means| for numbers,
total variation distance between the two value distributions for booleans and
strings. With binary values the second is a conditional test on the 2x2 table,
like Fisher's exact test. Splits are enumerated exactly up to EXACT_SPLITS;
beyond that a fixed-seed sample of SAMPLED_SPLITS splits keeps reports
reproducible. With five repetitions per engine the smallest attainable p-value
is 2/252 (about 0.0079): only a complete separation reaches it.

These tests treat repetitions as exchangeable and metrics as independent; they
qualify one finding or one group's headline metric, not a whole report.
"""
from collections import Counter
from itertools import combinations
import json
from math import comb, isfinite
import random

EXACT_SPLITS = 200_000
SAMPLED_SPLITS = 100_000
SAMPLE_SEED = 20261102
STRONG_ALPHA = 0.01
# Pooled statistics are compared with this relative slack so that rounding in
# the sums never drops the observed split itself from the tail.
_SLACK = 1e-9


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _statistic(kind):
    if kind == 'number':
        def statistic(left, right):
            return abs(sum(left) / len(left) - sum(right) / len(right))
    else:
        def statistic(left, right):
            a, b = Counter(map(_key, left)), Counter(map(_key, right))
            return sum(abs(a[k] / len(left) - b[k] / len(right)) for k in a.keys() | b.keys()) / 2
    return statistic


def kind_of(values):
    """'number', 'category' or None when the values cannot be tested together."""
    if not values or any(value is None for value in values):
        return None
    if all(type(value) in (int, float) and isfinite(value) for value in values):
        return 'number'
    if all(type(value) is bool for value in values) or all(type(value) is str for value in values):
        return 'category'
    return None


def permutation_test(original, meitou, kind=None):
    """Two-sided permutation p-value for "both samples come from one distribution".

    Returns dict(test, kind, statistic, p_value, splits, exact, minimum_p_value),
    or dict(test=None, ..., p_value=None) when either side is empty, a value is
    null or unsupported, or the two sides mix kinds. Never raises on data.
    """
    original, meitou = list(original), list(meitou)
    kind = kind or kind_of(original + meitou)
    if not original or not meitou or kind not in ('number', 'category') or kind_of(original + meitou) != kind:
        return dict(test=None, kind=kind, statistic=None, p_value=None, splits=0, exact=False, minimum_p_value=None)
    statistic = _statistic(kind)
    pooled, size = original + meitou, len(original)
    observed = statistic(original, meitou)
    threshold = observed - _SLACK * max(1.0, abs(observed))
    total = comb(len(pooled), size)
    indices = range(len(pooled))

    def split(chosen):
        chosen = set(chosen)
        return [pooled[i] for i in indices if i in chosen], [pooled[i] for i in indices if i not in chosen]

    if total <= EXACT_SPLITS:
        hits = sum(statistic(*split(chosen)) >= threshold for chosen in combinations(indices, size))
        splits, exact, p_value = total, True, hits / total
    else:
        rng = random.Random(SAMPLE_SEED)
        hits = sum(statistic(*split(rng.sample(indices, size))) >= threshold for _ in range(SAMPLED_SPLITS))
        # The observed split counts once, so a sampled p-value is never zero.
        splits, exact, p_value = SAMPLED_SPLITS, False, (hits + 1) / (SAMPLED_SPLITS + 1)
    return dict(test='permutation', kind=kind, statistic=observed, p_value=p_value, splits=splits, exact=exact,
                minimum_p_value=2 / total if size == len(meitou) else 1 / total)


def strength(p_value, alpha=STRONG_ALPHA):
    """'strong' below alpha, 'weak' otherwise, None without a test."""
    if p_value is None:
        return None
    return 'strong' if p_value < alpha else 'weak'
