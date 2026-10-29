"""Sparse observations must not invent travelled paths, exact arrivals or fight durations."""
from copy import deepcopy
import json
import math

import pytest

from oracle_traces import trace_metrics
from test_oracle_compare import FIRST, SECOND, state


SQUAD = 'hand:34:7:101:0:0'
TRAJECTORY = '/trajectory/saved_squad/' + SQUAD
ARRIVAL = '/trajectory/move_action/0'
COMBAT = '/combat/engagement_by_faction/fixture-faction'


def campaign(positions=None, *, actions=None):
    if positions is None:
        positions = [[0, 0, 0], [10, 0, 0], [20, 0, 0]]
    times = [index*10 for index in range(len(positions))]
    scenario = dict(schema_version='0.1', name='synthetic-traces', save='Synthetic save', speed=1,
                    actions=actions or [], checkpoints=[dict(at=instant, name=f'point-{index}')
                      for index, instant in enumerate(times)])
    checkpoints = {}
    for index, (position, instant) in enumerate(zip(positions, times)):
        snapshot = state()
        for character in snapshot['characters']:
            character['position'] = deepcopy(position)
        checkpoints[f'point-{index}'] = [dict(repetition=1, snapshot=f'original/1/point-{index}.json',
            state=snapshot, capture=dict(actual_at=instant, requested_at=instant, overshoot_seconds=0))]
    return dict(scenario=scenario, checkpoints=checkpoints)


def move(*, target=None, at=0):
    return dict(at=at, command='issue_order', params=dict(type='move', squad_id=SQUAD,
                                                        position=target or [10, 0, 0]))


def test_observed_loop_has_nonzero_polyline_length_and_zero_net_displacement():
    result = trace_metrics(campaign([[0, 0, 0], [3, 0, 4], [0, 0, 0]]))[1]
    assert result[TRAJECTORY+'/observed_polyline_distance_mean_lower_bound'] == 10
    assert result[TRAJECTORY+'/net_displacement_mean'] == 0
    assert [result[TRAJECTORY+'/final_position/'+axis] for axis in ('x', 'y', 'z')] == [0, 0, 0]


def test_polyline_distance_is_mean_of_each_members_3d_path_not_centroid_distance():
    value = campaign()
    paths = {FIRST: [[0, 0, 0], [10, 0, 0], [0, 0, 0]],
             SECOND: [[0, 0, 0], [0, 0, 0], [10, 0, 0]]}
    for index, point in enumerate(value['checkpoints'].values()):
        for character in point[0]['state']['characters']:
            character['position'] = paths[character['id']][index]
    result = trace_metrics(value)[1]
    assert result[TRAJECTORY+'/observed_polyline_distance_mean_lower_bound'] == 15
    assert result[TRAJECTORY+'/net_displacement_mean'] == 5
    assert result[TRAJECTORY+'/final_position/x'] == 5
    result = trace_metrics(campaign([[0, 0, 0], [4, 3, 0]]))[1]
    assert result[TRAJECTORY+'/observed_polyline_distance_mean_lower_bound'] == 5


def test_arrival_is_observed_with_conservative_interval_not_an_exact_time():
    result = trace_metrics(campaign(actions=[move()]), arrival_radius=0)[1]
    assert result[ARRIVAL+'/arrival_observed'] is True
    assert result[ARRIVAL+'/first_observed_at'] == 10
    assert result[ARRIVAL+'/arrival_time_lower_bound'] == 0
    assert result[ARRIVAL+'/arrival_time_upper_bound'] == 10
    assert result[ARRIVAL+'/exact_arrival_time'] is None


def test_no_sampled_arrival_does_not_claim_never_arrived_between_photos():
    result = trace_metrics(campaign([[0, 0, 0], [20, 0, 0], [0, 0, 0]], actions=[move()]), arrival_radius=1)[1]
    assert result[ARRIVAL+'/arrival_observed'] is False
    assert result[ARRIVAL+'/first_observed_at'] is None
    assert result[ARRIVAL+'/arrival_time_upper_bound'] is None
    assert result[ARRIVAL+'/exact_arrival_time'] is None


def test_arrival_uses_xz_radius_for_all_cohort_members_not_centroid_or_height():
    value = campaign([[0, 0, 0], [10, 500, 0]], actions=[move()])
    result = trace_metrics(value, arrival_radius=0)[1]
    assert result[ARRIVAL+'/arrival_observed'] is True  # Y does not define ground arrival.
    later = value['checkpoints']['point-1'][0]['state']['characters']
    later[0]['position'], later[1]['position'] = [0, 0, 0], [20, 0, 0]
    result = trace_metrics(value, arrival_radius=1)[1]
    assert result[ARRIVAL+'/arrival_observed'] is False  # Centroid lies at 10; neither member does.


def test_move_observations_before_the_order_do_not_count_as_arrival_after_it():
    value = campaign([[10, 0, 0], [20, 0, 0]], actions=[move(at=5)])
    result = trace_metrics(value, arrival_radius=0)[1]
    assert result[ARRIVAL+'/arrival_observed'] is False


@pytest.mark.parametrize('mutation', ['null_position', 'missing_character', 'missing_checkpoint'])
def test_a_missing_cohort_position_censors_all_trajectory_and_arrival_metrics(mutation):
    value = campaign(actions=[move()])
    if mutation == 'null_position':
        value['checkpoints']['point-1'][0]['state']['characters'][0]['position'] = None
    elif mutation == 'missing_character':
        value['checkpoints']['point-1'][0]['state']['characters'].pop(0)
    else:
        value['checkpoints']['point-1'].clear()
    result = trace_metrics(value)[1]
    assert all(value is None for key, value in result.items() if key.startswith((TRAJECTORY+'/', ARRIVAL+'/')))


def test_squad_cohort_is_fixed_at_initial_loaded_membership_not_later_recruits():
    value = campaign([[0, 0, 0], [10, 0, 0]])
    later = value['checkpoints']['point-1'][0]['state']
    recruit = deepcopy(later['characters'][0])
    recruit.update(id='local:new-member', identity_origin=None, position=[1000, 0, 0])
    later['characters'].append(recruit)
    later['squads'][0]['members'].append(recruit['id'])
    result = trace_metrics(value)[1]
    assert result[TRAJECTORY+'/final_position/x'] == 10
    assert result[TRAJECTORY+'/observed_polyline_distance_mean_lower_bound'] == 10


@pytest.mark.parametrize('origin,identity', [(None, SQUAD), ('generated', SQUAD),
    ('saved', 'hand:34:7:101:0'), ('saved', 'hand:34:7:101:0:4294967296')])
def test_squad_trajectory_requires_proven_saved_full_uint32_hand(origin, identity):
    value = campaign()
    value['checkpoints']['point-0'][0]['state']['squads'][0].update(id=identity, identity_origin=origin)
    result = trace_metrics(value)[1]
    assert not any(key.startswith('/trajectory/saved_squad/') for key in result)


def test_character_move_requires_saved_identity_and_does_not_relabel_unknown_as_generated():
    action = dict(at=0, command='issue_order', params=dict(type='move', character_id=FIRST, position=[10, 0, 0]))
    value = campaign(actions=[action])
    assert trace_metrics(value, arrival_radius=0)[1][ARRIVAL+'/arrival_observed'] is True
    value['checkpoints']['point-0'][0]['state']['characters'][0]['identity_origin'] = None
    assert trace_metrics(value)[1][ARRIVAL+'/arrival_observed'] is None


def test_disjoint_observed_combat_bouts_do_not_invent_continuous_or_cumulative_duration():
    value = campaign()
    for index, flag in enumerate((True, False, True)):
        for character in value['checkpoints'][f'point-{index}'][0]['state']['characters']:
            character['in_combat'] = flag
    result = trace_metrics(value)[1]
    assert result[COMBAT+'/engagement_observed'] is True
    assert result[COMBAT+'/first_observed_at'] == 0
    assert result[COMBAT+'/last_observed_at'] == 20
    assert result[COMBAT+'/observed_span_seconds'] == 20
    assert result[COMBAT+'/duration_seconds'] is None
    assert result[COMBAT+'/window_duration_lower_bound'] == 0
    assert result[COMBAT+'/window_duration_upper_bound'] == 20


def test_single_combat_photo_has_zero_observed_span_without_zero_duration_claim():
    value = campaign()
    value['checkpoints']['point-1'][0]['state']['characters'][0]['in_combat'] = True
    result = trace_metrics(value)[1]
    assert result[COMBAT+'/first_observed_at'] == result[COMBAT+'/last_observed_at'] == 10
    assert result[COMBAT+'/observed_span_seconds'] == 0
    assert result[COMBAT+'/duration_seconds'] is None


def test_unknown_combat_is_not_false_and_one_known_true_still_proves_observed_engagement():
    value = campaign()
    assert trace_metrics(value)[1][COMBAT+'/engagement_observed'] is False
    value['checkpoints']['point-1'][0]['state']['characters'][0]['in_combat'] = None
    result = trace_metrics(value)[1]
    assert result[COMBAT+'/engagement_observed'] is None
    assert result[COMBAT+'/duration_seconds'] is None
    value['checkpoints']['point-2'][0]['state']['characters'][1]['in_combat'] = True
    result = trace_metrics(value)[1]
    assert result[COMBAT+'/engagement_observed'] is True
    assert result[COMBAT+'/first_observed_at'] == 20


def test_lost_combat_cohort_member_is_unknown_not_dead_or_disengaged():
    value = campaign()
    value['checkpoints']['point-1'][0]['state']['characters'].pop(0)
    result = trace_metrics(value)[1]
    assert result[COMBAT+'/engagement_observed'] is None
    assert result[COMBAT+'/duration_seconds'] is None


def test_repetitions_are_separate_and_input_is_not_mutated():
    value = campaign()
    for rows in value['checkpoints'].values():
        other = deepcopy(rows[0]); other['repetition'] = 2
        other['snapshot'] = other['snapshot'].replace('/1/', '/2/')
        rows.append(other)
    before = deepcopy(value)
    result = trace_metrics(value)
    assert set(result) == {1, 2} and result[1] == result[2]
    assert value == before
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('radius', [-1, True, math.nan, math.inf, '5', 1e9+1])
def test_invalid_arrival_radius_is_rejected(radius):
    with pytest.raises(ValueError, match='arrival_radius'):
        trace_metrics(campaign(), arrival_radius=radius)


def test_nonchronological_observed_times_and_duplicate_repetitions_are_rejected():
    value = campaign()
    value['checkpoints']['point-2'][0]['capture']['actual_at'] = 1
    with pytest.raises(ValueError, match='nondecreasing'):
        trace_metrics(value)
    value = campaign()
    value['checkpoints']['point-0'].append(deepcopy(value['checkpoints']['point-0'][0]))
    with pytest.raises(ValueError, match='unique'):
        trace_metrics(value)
