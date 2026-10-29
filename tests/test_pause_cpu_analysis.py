from copy import deepcopy
import pytest
from analyze_pause_cpu import analyze,summarize_phase,common_threads
from benchmark import simulation_progress
from test_environment_diagnostics import capture


def phase(label='paused_before',paused=True,cpu=40):
    env=capture()
    for s in (env['scene_before'],env['scene_after']):
        s.update(paused=paused,frame_speed_multiplier=0 if paused else 1,observed_qpc_ms=1000)
    before=deepcopy(env['scene_after']);before['frame']=13
    after=dict(before,frame=1200,observed_qpc_ms=21000,game_total_hours=404 if paused else 404.18)
    final_env=deepcopy(env)
    final_env['scene_before']=dict(after,frame=1207)
    final_env['scene_after']=dict(after,frame=1210)
    endpoint=dict(created_at=10,thread_snapshot=dict(collection_seconds=.01))
    return dict(label=label,completed=True,expected_paused=paused,scene_before=before,scene_after=after,
        observations=[dict(scene=deepcopy(after),elapsed=20)],simulation_progress=simulation_progress(before,after),
        roles_before=dict(frame=13),roles_after=dict(frame=1200),environment_before=env,environment_after=final_env,
        process_resources=dict(pid=1,executable='game.exe',before=deepcopy(endpoint),after=deepcopy(endpoint),
            elapsed_seconds=20.1,user_seconds=cpu,system_seconds=0,
            thread_cpu=dict(accounting_group_cpu_seconds=dict(game_thread=cpu/2,other_threads=cpu/2),
                threads=[],omitted_reasons={},residual_cpu_seconds=-.015625,role_evidence={})),
        statistics_tail=dict(first_frame=603,last_frame=1202,count=600,mean_ms=16,p99_ms=20,
            systems=dict(navmesh_findPath_calls_total=0)),
        thread_attribution_statistics=dict(navmesh_slow_calls=[],navmesh_slow_calls_retention_truncated=False))


def test_preserves_distinct_cpu_clock_and_tail_bounds():
    result=summarize_phase(phase(),1)
    assert result['cpu_elapsed_seconds']==20.1
    assert result['simulation_progress']['wall_seconds']==20
    assert result['residual_cpu_seconds']==-.015625
    assert result['tail']['ends_after_cpu_heartbeat'] and result['tail']['inside_scene_bounds']
    assert result['environment_comparison']['labels_equal']


@pytest.mark.parametrize('change',['pause','clock','frozen_run','camera','identity','counter','cached'])
def test_invalid_phase_not_treated_as_valid_measurement(change):
    row=phase()
    if change=='pause': row['observations'][0]['scene']['paused']=False
    elif change=='clock': row['scene_after']['game_total_hours']+=.1
    elif change=='frozen_run': row=phase('running_x1',False);row['scene_after']['game_total_hours']=404
    elif change=='camera': row['scene_after']['camera_center']=[100,0,0]
    elif change=='identity': row['process_resources']['after']['created_at']=11
    elif change=='counter': row['process_resources']['user_seconds']=-1
    else: row['simulation_progress']['game_hours']=10
    with pytest.raises((ValueError,RuntimeError)): summarize_phase(row,1)


def test_signed_contrast_is_not_normalized_into_simulation_cost():
    data=dict(pid=1,phases=[phase(),phase('running_x1',False,20),phase('paused_after')])
    result=analyze(data)
    assert result['contrast']['running_minus_mean_paused_logical_cpus']<0
    assert result['contrast']['mean_paused_fraction_of_running']==pytest.approx(2)
    assert not result['completed']


def test_lifetime_change_between_valid_phases_is_rejected():
    a,b=phase(),phase('running_x1',False)
    b['process_resources']['before']['created_at']=b['process_resources']['after']['created_at']=11
    with pytest.raises(ValueError,match='across phases'): analyze(dict(pid=1,phases=[a,b]))


def test_partial_phase_is_retained_without_contrast():
    result=analyze(dict(pid=1,phases=[dict(label='paused_before',completed=False)]))
    assert result['contrast'] is None and not result['phases'][0]['completed']


def test_common_thread_rates_require_same_creation_and_keep_role_union():
    rows=[phase(),phase('running_x1',False),phase('paused_after')]
    for i,row in enumerate(rows):
        row['process_resources']['thread_cpu']['threads']=[dict(tid=7,created_filetime='123456789012345678',
            cpu_seconds=10+i,observed_roles=['observed_navigation_thread'] if i==1 else [])]
    result=common_threads(rows)
    assert result['common_thread_count']==1
    assert result['top_threads'][0]['observed_roles_union']==['observed_navigation_thread']
    assert result['top_threads'][0]['logical_cpu_equivalents_by_phase']['running_x1']==pytest.approx(11/20.1)
    rows[-1]['process_resources']['thread_cpu']['threads'][0]['created_filetime']='different'
    assert common_threads(rows)['common_thread_count']==0


def test_common_thread_does_not_fill_missing_phase_with_zero():
    a,b=phase(),phase('running_x1',False)
    a['process_resources']['thread_cpu']['threads']=[dict(tid=7,created_filetime='1',cpu_seconds=2)]
    assert common_threads([a,b])['common_thread_count']==0


def test_common_thread_duplicate_is_not_summed_twice():
    row=phase();thread=dict(tid=7,created_filetime='1',cpu_seconds=2)
    row['process_resources']['thread_cpu']['threads']=[thread,dict(thread)]
    with pytest.raises(ValueError,match='Duplicate'): common_threads([row])


def test_common_thread_equal_rates_have_deterministic_top_boundary():
    row=phase()
    row['process_resources']['thread_cpu']['threads']=[dict(tid=t,created_filetime=str(t),cpu_seconds=1) for t in range(20,0,-1)]
    result=common_threads([row])
    assert result['common_thread_count']==20
    assert [t['tid'] for t in result['top_threads']]==list(range(1,13))


def test_common_thread_equal_rates_are_stable_across_hash_seeds():
    import json,os,subprocess,sys
    from pathlib import Path
    module=str(Path(__file__).resolve().parents[1]/'mcp-server')
    code=('import json,sys;sys.path.insert(0,'+repr(module)+');from analyze_pause_cpu import common_threads;'
          'rows=[dict(label="running_x5",process_resources=dict(elapsed_seconds=20,thread_cpu=dict(threads=['
          'dict(tid=t,created_filetime=str(100+t),cpu_seconds=1) for t in range(20)])))];'
          'print(json.dumps(common_threads(rows),sort_keys=True))')
    results=[]
    for seed in ('1','77'):
        env=dict(os.environ,PYTHONHASHSEED=seed)
        results.append(subprocess.check_output([sys.executable,'-c',code],env=env,text=True))
    assert results[0]==results[1]


@pytest.mark.parametrize('creation,matched',[('100',True),('different',False)])
def test_physics_role_joins_only_matching_cpu_creation(creation,matched):
    from test_physics_diagnostics import stats
    row=phase();row['statistics_tail']['systems'].update(stats()['systems'])
    row['process_resources']['thread_cpu']['threads']=[dict(tid=7,created_filetime=creation,cpu_seconds=10)]
    result=summarize_phase(row,1)
    first=result['physics_thread_cpu_identity_matches'][0]
    assert first['matched_cpu_identity'] is matched
    assert first['whole_thread_cpu_seconds']==(10 if matched else None)
