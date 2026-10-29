from copy import deepcopy
import pytest
from environment_diagnostics import summarize,compare,admission


def capture(rows=None,total=None,limit=250):
    rows=rows if rows is not None else [dict(name='Guard',faction='Town',position=[1,2,3]),
                                      dict(name='Guard',faction='Town',position=[4,5,6])]
    total=total if total is not None else len(rows)
    scene=dict(frame=10,paused=True,game_total_hours=404,loaded_character_count=total,
        camera_center=[0,1,2],camera_position=[3,4,5],free_camera=True)
    return dict(limit=limit,scene_before=scene,scene_after=dict(scene,frame=12),
        inventory=dict(characters=rows,total_update_list=total))


def test_unordered_duplicate_names_keep_multiplicity():
    first=capture();second=deepcopy(first);second['inventory']['characters'].reverse()
    a,b=summarize(first),summarize(second)
    assert a['repeated_label_groups']==1
    assert compare(a,b)['labels_equal'] and compare(a,b)['exact_positions_equal']
    assert not a['atomic']


def test_same_count_different_labels_are_detected_without_identity_claim():
    first=capture();second=deepcopy(first)
    second['inventory']['characters'][1]['faction']='Other'
    result=compare(summarize(first),summarize(second))
    assert result['total_count_delta']==0 and not result['labels_equal']
    assert result['added_label_occurrences']==result['removed_label_occurrences']==1


def test_positions_can_differ_without_label_churn():
    first=capture();second=deepcopy(first)
    second['inventory']['characters'][0]['position'][1]+=.1
    result=compare(summarize(first),summarize(second))
    assert result['labels_equal'] and not result['exact_positions_equal']


@pytest.mark.parametrize('change',['truncated','population','clock','pause','camera','different_clock'])
def test_incomplete_or_changing_capture_does_not_infer_roster_churn(change):
    first=capture();second=deepcopy(first)
    if change=='truncated': second['inventory']['characters'].pop()
    elif change=='population': second['scene_after']['loaded_character_count']+=1
    elif change=='clock': second['scene_after']['game_total_hours']+=.01
    elif change=='pause': second['scene_after']['paused']=False
    elif change=='camera': second['scene_after']['camera_position']=[10,4,5]
    else:
        second['scene_before']['game_total_hours']+=1
        second['scene_after']['game_total_hours']+=1
    result=compare(summarize(first),summarize(second))
    assert not result['full_label_comparison_allowed'] and 'added_labels' not in result


@pytest.mark.parametrize('change',['nan','oversized','regression'])
def test_malformed_inventory_rejected(change):
    data=capture()
    if change=='nan': data['inventory']['characters'][0]['position'][0]=float('nan')
    elif change=='oversized': data['limit']=1
    else: data['scene_after']['frame']=9
    with pytest.raises(ValueError): summarize(data)


def test_empty_complete_update_lists_are_valid():
    a=summarize(capture([]));assert a['complete'] and a['comparable']
    assert compare(a,a)['labels_equal']


def test_environment_gate_accepts_first_complete_capture_and_equal_reload():
    a=summarize(capture())
    assert admission(None,a)['accepted'] and admission(a,a)['accepted']


def test_environment_gate_rejects_same_labels_with_different_positions():
    a=capture();b=deepcopy(a);b['inventory']['characters'][0]['position'][1]+=.1
    result=admission(summarize(a),summarize(b))
    assert result['labels_equal'] and not result['accepted']


def test_first_partial_environment_is_not_a_reference():
    a=capture(total=3)
    assert not admission(None,summarize(a))['accepted']


def test_inventory_over_250_can_be_complete_with_existing_500_bound():
    rows=[dict(name='Guard',faction='Town',position=[i,2,3]) for i in range(450)]
    full=summarize(capture(rows,total=450,limit=500))
    partial=summarize(capture(rows[:250],total=450,limit=250))
    assert full['complete'] and admission(None,full)['accepted']
    assert not partial['complete'] and not admission(full,partial)['accepted']


def test_existing_maximum_does_not_claim_coverage_over_500():
    rows=[dict(name='Guard',faction='Town',position=[i,2,3]) for i in range(500)]
    result=summarize(capture(rows,total=501,limit=500))
    assert not result['complete'] and not admission(None,result)['accepted']
