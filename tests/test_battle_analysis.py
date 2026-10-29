from copy import deepcopy
from analyze_battle import analyze


def sample():
    a = dict(name='fight_0', blood=100, health=dict(complete=True, part_count=7, flesh_sum=0, flesh_stun_sum=0))
    b = dict(name='fight_1', blood=100, health=dict(complete=True, part_count=7, flesh_sum=0, flesh_stun_sum=0))
    return dict(initial=dict(battle=dict(members=[a, b])), prepared=dict(members=[a, b]),
        observations=[dict(elapsed=.25, scene=dict(battle=dict(members=deepcopy([a, b]))))])


def test_bruise_signal_is_retained_when_blood_does_not_change():
    data = sample()
    data['observations'][0]['scene']['battle']['members'][0]['health']['flesh_stun_sum'] = 12
    result = analyze(data)['actors']['fight_0']['raw_deltas']
    assert result['blood']['maximum_delta'] == 0
    assert result['flesh_stun_sum']['maximum_delta'] == 12
    assert result['flesh_stun_sum']['first_change_observed_seconds'] == .25


def test_foreign_target_is_not_counted_as_paired_fight():
    data = sample()
    data['observations'][0]['scene']['battle']['members'][0]['attack_target'] = dict(resolved=True, name='guard')
    result = analyze(data)['actors']['fight_0']['target_observations']
    assert result == {'outside_cohort': 1}


def test_missing_actor_and_truncated_health_do_not_imply_zero_damage():
    data = sample()
    rows = data['observations'][0]['scene']['battle']['members']
    rows.pop()
    rows[0]['health']['complete'] = False
    result = analyze(data)['actors']
    assert result['fight_1']['missing_or_duplicate_observations'] == 1
    assert result['fight_0']['raw_deltas']['flesh_sum']['maximum_delta'] is None


def test_legacy_blood_only_capture_does_not_invent_health():
    data = sample()
    for row in data['initial']['battle']['members'] + data['observations'][0]['scene']['battle']['members']:
        row.pop('health')
    result = analyze(data)['actors']['fight_0']['raw_deltas']
    assert result['flesh_sum']['comparable_observations'] == 0
    assert result['flesh_sum']['first_change_observed_seconds'] is None


def test_regeneration_does_not_count_as_first_decrease():
    data = sample()
    data['observations'][0]['scene']['battle']['members'][0]['blood'] = 100.01
    later = deepcopy(data['observations'][0])
    later['elapsed'] = 2
    later['scene']['battle']['members'][0]['blood'] = 90
    data['observations'].append(later)
    result = analyze(data)['actors']['fight_0']['raw_deltas']['blood']
    assert result['first_change_observed_seconds'] == .25
    assert result['first_decrease_observed_seconds'] == 2
