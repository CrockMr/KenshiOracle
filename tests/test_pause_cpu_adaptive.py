from copy import deepcopy
import pytest
from analyze_pause_cpu import analyze,bounded_tail_count,summarize_phase,validate_phase_state
from test_pause_cpu_analysis import phase


def with_speed(row,speed):
    row['active_speed']=speed
    for scene in [row['scene_before'],row['scene_after']]+[x['scene'] for x in row['observations']]:
        scene['frame_speed_multiplier']=0 if row['expected_paused'] else speed
    for key in ('environment_before','environment_after'):
        for scene in (row[key]['scene_before'],row[key]['scene_after']):
            scene['frame_speed_multiplier']=0 if row['expected_paused'] else speed
    return row


def adaptive_phase():
    row=with_speed(phase('running_x5',False),5)
    row['statistics_tail_selection']=dict(policy='bounded_since_phase_start',maximum=3600,
        observed_scene=deepcopy(row['scene_after']),requested_count=1186)
    # 1200 - 13 - 1 = 1186 completed frames available strictly after entry.
    row['statistics_tail'].update(first_frame=15,last_frame=1200,count=1186)
    return row


@pytest.mark.parametrize('first,observed,maximum,expected',[(10,15,600,4),(10,1000,600,600),
    (10,1000,3600,989),(10,12,1,1),(0,2,3600,1)])
def test_tail_uses_only_completed_frames_after_entry(first,observed,maximum,expected):
    assert bounded_tail_count(first,observed,maximum)==expected


@pytest.mark.parametrize('first,observed,maximum',[(10,11,600),(10,10,600),(10,9,600),
    (True,20,600),(-1,20,600),(1,20.5,600),(1,20,True),(1,20,0),(1,20,3601)])
def test_invalid_or_empty_tail_not_replaced_with_old_frames(first,observed,maximum):
    with pytest.raises(ValueError):bounded_tail_count(first,observed,maximum)


def test_explicit_x5_and_adaptive_tail_are_reported():
    row=adaptive_phase();result=summarize_phase(row,1)
    assert result['active_speed']==5
    assert result['tail']['count']==1186 and result['tail']['inside_scene_bounds']
    assert result['tail']['selection']['maximum']==3600


def test_x5_campaign_contrast_keeps_actual_label():
    rows=[with_speed(phase(),5),adaptive_phase(),with_speed(phase('paused_after'),5)]
    result=analyze(dict(pid=1,active_speed=5,phases=rows))
    assert result['contrast'] is not None
    assert result['phases'][1]['label']=='running_x5'


@pytest.mark.parametrize('change',['speed','label','campaign','bool','unsupported','unannounced'])
def test_x5_not_silently_reinterpreted_as_x1(change):
    rows=[with_speed(phase(),5),adaptive_phase(),with_speed(phase('paused_after'),5)]
    data=dict(pid=1,active_speed=5,phases=rows)
    if change=='speed':rows[1]['observations'][0]['scene']['frame_speed_multiplier']=1
    elif change=='label':rows[1]['label']='running_x1'
    elif change=='campaign':data['active_speed']=1
    elif change=='bool':data['active_speed']=True
    elif change=='unsupported':data['active_speed']=2
    else:rows[1].pop('active_speed')
    with pytest.raises(ValueError):analyze(data)


@pytest.mark.parametrize('change',['count','requested','maximum','before','after','noncontiguous','selection_scene','env_speed'])
def test_adaptive_window_contradictions_rejected(change):
    row=adaptive_phase()
    if change=='count':row['statistics_tail']['count']-=1
    elif change=='requested':row['statistics_tail_selection']['requested_count']-=1
    elif change=='maximum':row['statistics_tail_selection']['maximum']=600
    elif change=='before':row['statistics_tail'].update(first_frame=13,last_frame=1198)
    elif change=='after':row['statistics_tail'].update(first_frame=16,last_frame=1201)
    elif change=='noncontiguous':row['statistics_tail']['first_frame']+=1
    elif change=='selection_scene':row['statistics_tail_selection']['observed_scene']['frame']=1201
    else:row['environment_after']['scene_after']['frame_speed_multiplier']=1
    with pytest.raises(ValueError):summarize_phase(row,1)


def test_old_x1_output_has_no_new_fields_or_relaxed_speed():
    row=phase('running_x1',False);result=summarize_phase(row,1)
    assert 'active_speed' not in result and 'selection' not in result['tail']
    scene=deepcopy(row['scene_after']);scene['frame_speed_multiplier']=5
    with pytest.raises(ValueError):validate_phase_state(row['scene_before'],scene,False)
