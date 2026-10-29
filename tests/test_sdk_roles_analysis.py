import pytest
from analyze_sdk_thread_roles import analyze
from sdk_thread_roles import join_cpu
from test_sdk_thread_roles import scene,resources
from test_pause_cpu_analysis import phase


def data():
    r=resources();p=phase('running_x1',False);first,last=scene(),scene()
    r['thread_cpu'].update(residual_cpu_seconds=0,omitted_reasons={})
    last['frame']=last['sdk_threads']['frame']=1300
    return dict(pid=1,completed=True,initial_ping=dict(plugin_version='0.7.7'),
        roles_before=first,roles_after=last,process_resources=r,role_cpu_join=join_cpu(first,last,r,1),
        scene_before=p['scene_before'],scene_after=p['scene_after'],observations=p['observations'],
        simulation_progress=p['simulation_progress'],statistics_tail=p['statistics_tail'],
        heartbeat_before=dict(game_thread=9,service_thread=9),heartbeat_after=dict(game_thread=9,service_thread=9),
        running_details_rejected=True,source_and_copy_unchanged=True,settings_unchanged=True)


def test_offline_join_is_recomputed_and_cached_disagreement_rejected():
    d=data();assert analyze(d)['joined']['unique_matched_threads']==1
    d['role_cpu_join']['roles'][0]['cpu_seconds']=999
    with pytest.raises(ValueError,match='Cached'):analyze(d)


def test_sdk_snapshots_must_bracket_simulation_interval():
    d=data();d['roles_after']['frame']=d['roles_after']['sdk_threads']['frame']=100
    with pytest.raises(ValueError,match='bracket'):analyze(d)


def test_regressed_role_frame_is_not_joined():
    a,b=scene(),scene();b['frame']=b['sdk_threads']['frame']=9
    with pytest.raises(ValueError,match='regressed'):join_cpu(a,b,resources(),1)


def test_sdk_cpu_coverage_counts_aliased_thread_once():
    summary=analyze(data())['known_sdk_thread_cpu']
    assert summary['matched_role_count']==3 and summary['unique_threads']==1
    assert summary['cpu_seconds']==1 and summary['logical_cpu_equivalents']==.5
    assert summary['fraction_of_process_cpu']==1 and summary['unknown_roles']==[]


def test_unverified_optional_role_is_listed_without_inventing_cpu():
    d=data()
    for s in [d['roles_before'],d['roles_after']]:
        s['sdk_threads']['roles'].append(dict(role='save_file_system',available=True,identity_verified=False,sdk_thread_id=0))
    d['role_cpu_join']=join_cpu(d['roles_before'],d['roles_after'],d['process_resources'],1)
    summary=analyze(d)['known_sdk_thread_cpu']
    assert summary['unique_threads']==1 and summary['cpu_seconds']==1
    assert summary['unknown_roles']==['save_file_system']
