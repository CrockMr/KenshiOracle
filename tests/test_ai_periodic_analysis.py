from copy import deepcopy
import pytest
from analyze_ai_periodic import analyze
from test_pause_cpu_analysis import phase
from test_sdk_thread_roles import scene
from test_ai_diagnostics import stats


def data():
    rows=[phase(),phase('running_x1',False),phase('paused_after')]
    for row in rows:
        row['statistics_tail']['systems'].update(deepcopy(stats()['systems']))
        row['process_resources']['thread_cpu']['threads']=[dict(tid=7,created_filetime='100',cpu_seconds=2),dict(tid=8,created_filetime='200',cpu_seconds=1)]
    first,last=scene(),scene();last['frame']=last['sdk_threads']['frame']=1300
    for s in [first,last]:
        for r in s['sdk_threads']['roles']:r['created_filetime']='100'
    rows[0]['sdk_roles_before']=first;rows[-1]['sdk_roles_after']=last
    return dict(pid=1,completed=True,phases=rows)


def test_ai_calls_are_joined_to_sdk_roles_without_exclusive_cpu_ratio():
    d=analyze(data());r=d['phases'][1]['ai_function_threads'][0]
    assert r['calls']==2 and r['sdk_roles']==['physics_backthread','world_ai_non_render','world_navmesh']
    assert r['whole_thread_cpu']['matched_cpu_identity'] and r['measured_call_cpu_ms']==15.625
    assert 'fraction_of_process_cpu' not in r


def test_changed_sdk_lifetime_is_not_used_to_label_function_thread():
    d=data()
    for r in d['phases'][-1]['sdk_roles_after']['sdk_threads']['roles']:r['created_filetime']='999'
    r=analyze(d)['phases'][1]['ai_function_threads'][0]
    assert r['sdk_roles']==[] and r['whole_thread_cpu']['matched_cpu_identity']


def test_sdk_bracket_must_enclose_cpu_scenes():
    d=data();s=d['phases'][-1]['sdk_roles_after'];s['frame']=s['sdk_threads']['frame']=100
    with pytest.raises(ValueError,match='bracket'):analyze(d)


def selected_data():
    d=data();d['initial_ping']=dict(ai_profiled_function='AI::update4Frame')
    for row in d['phases']:
        systems=row['statistics_tail']['systems'];p=systems.pop('ai_periodicUpdate')
        p['function']='AI::update4Frame';systems.update(ai_profiled_function=p,ai_periodicUpdate=None)
    return d


def test_selected_function_retains_its_name_and_retires_periodic_tail():
    d=analyze(selected_data());assert d['ai_function']=='AI::update4Frame'
    assert all(p['ai_periodic_tail'] is None and p['ai_function_tail']['function']=='AI::update4Frame' for p in d['phases'])


@pytest.mark.parametrize('change',['mixed_phases','initial_selection'])
def test_different_function_selections_cannot_be_merged(change):
    d=selected_data()
    if change=='mixed_phases':d['phases'][1]['statistics_tail']['systems']['ai_profiled_function']['function']='AI::periodicUpdate'
    else:d['initial_ping']['ai_profiled_function']='AI::periodicUpdate'
    with pytest.raises(ValueError):analyze(d)
