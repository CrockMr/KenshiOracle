from copy import deepcopy
import pytest
from analyze_profiled_function import analyze
from test_ai_periodic_analysis import data as historical
from test_function_diagnostics import stats


def data():
    d=historical();d['initial_ping']=dict(profiled_function='GameWorld::charsUpdateUT')
    for row in d['phases']:
        row['statistics_tail']['systems'].update(deepcopy(stats()['systems']))
    return d


def test_world_entrypoint_keeps_truthful_name_and_exact_os_sdk_join():
    result=analyze(data());r=result['phases'][1]['function_threads'][0]
    assert result['profiled_function']=='GameWorld::charsUpdateUT' and r['calls']==2
    assert r['sdk_roles']==['physics_backthread','world_ai_non_render','world_navmesh']
    assert r['whole_thread_cpu']['matched_cpu_identity']
    assert 'fraction_of_process_cpu' not in r
    assert result['phases'][1]['ai_function_tail'] is None


def test_historical_ai_data_stays_readable():
    assert analyze(historical())['profiled_function']=='AI::periodicUpdate'


def test_observed_main_role_requires_matching_cpu_creation_not_just_tid():
    d=data();thread=d['phases'][1]['process_resources']['thread_cpu']['threads'][0]
    thread['observed_roles']=['game_thread','renderer_service_thread']
    assert analyze(d)['phases'][1]['function_threads'][0]['observed_thread_roles']==thread['observed_roles']
    thread['created_filetime']='999'
    row=analyze(d)['phases'][1]['function_threads'][0]
    assert row['observed_thread_roles']==[] and not row['whole_thread_cpu']['matched_cpu_identity']


@pytest.mark.parametrize('change',['mixed','initial','bracket'])
def test_function_selection_and_sdk_bounds_cannot_be_silently_mixed(change):
    d=data()
    if change=='mixed':d['phases'][1]['statistics_tail']['systems']['profiled_function']['function']='AI::periodicUpdate'
    elif change=='initial':d['initial_ping']['profiled_function']='AI::update4Frame'
    else:
        s=d['phases'][-1]['sdk_roles_after'];s['frame']=s['sdk_threads']['frame']=100
    with pytest.raises(ValueError):analyze(d)
