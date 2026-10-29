from copy import deepcopy
import pytest
from live_snapshot_horizon import validate_baseline


def scene():
    return dict(paused=True,game_total_hours=404,free_camera=True,
        camera_center=[1,2,3],camera_position=[4,5,6],
        battle=dict(active=True,matched_loaded=1,members=[dict(name='actor',
            blood=100,position=[1,2,3],dead=False,unconscious=False,is_player=False,
            health=dict(complete=True,part_count=1,sampled_count=1,
                        parts_flesh_stun_max=[[100,0,100]]))]))


def test_accepts_equal_visible_snapshot_without_claiming_handle_identity():
    before,after=scene(),scene()
    after['battle']['members'][0]['attack_target']={'handle':[7,8,9]}
    assert validate_baseline(before,after)['matches']


@pytest.mark.parametrize('change',['clock','pose','medical'])
def test_rejects_changed_visible_baseline(change):
    before,after=scene(),scene()
    if change=='clock': after['game_total_hours']+=.00001
    elif change=='pose': after['battle']['members'][0]['position'][1]+=1.897339
    else: after['battle']['members'][0]['blood']-=.01
    assert not validate_baseline(before,after)['matches']


@pytest.mark.parametrize('change',['duplicate','nan','shape','sampled','paused','missing','camera'])
def test_refuses_invalid_baseline(change):
    before,after=scene(),scene()
    row=after['battle']['members'][0]
    if change=='duplicate': after['battle']['members'].append(deepcopy(row))
    elif change=='nan': row['position'][0]=float('nan')
    elif change=='shape': row['health']['parts_flesh_stun_max'][0].pop()
    elif change=='sampled': row['health']['sampled_count']=0
    elif change=='paused': after['paused']=False
    elif change=='missing': after['battle']['matched_loaded']=0
    else: after['camera_center'][0]+=10
    with pytest.raises((ValueError,RuntimeError)):
        validate_baseline(before,after)
