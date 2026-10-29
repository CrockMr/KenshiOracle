from copy import deepcopy
import pytest
from live_scene_snapshot import visible_comparison


def scene():
    return dict(battle=dict(members=[dict(name='fight_0', blood=100,
        health=dict(complete=True, parts_flesh_stun_max=[[100,0,100]]),
        position=[0,1,2], dead=False, unconscious=False, is_player=False)]))


def test_snapshot_visible_comparison_ignores_recreated_handles():
    before, after = scene(), scene()
    before['battle']['members'][0]['attack_target'] = {'handle': [1,2,3,4,5]}
    after['battle']['members'][0]['attack_target'] = {'handle': None}
    assert visible_comparison(before, after)['matches']


@pytest.mark.parametrize('change', ['blood', 'injury', 'position', 'missing', 'incomplete', 'unconscious'])
def test_snapshot_comparison_detects_changed_visible_baseline(change):
    before = scene()
    after = deepcopy(before)
    row = after['battle']['members'][0]
    if change == 'blood':
        row['blood'] += .01
    elif change == 'injury':
        row['health']['parts_flesh_stun_max'][0][0] -= 5
    elif change == 'position':
        row['position'][0] += 2
    elif change == 'missing':
        after['battle']['members'] = []
    elif change == 'incomplete':
        row['health']['complete'] = False
    else:
        row['unconscious'] = True
    assert not visible_comparison(before, after)['matches']
