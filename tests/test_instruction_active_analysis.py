from copy import deepcopy
import pytest
from analyze_instruction_active import analyze
from benchmark import simulation_progress
from instruction_diagnostics import summarize
from thread_resources import thread_deltas
from test_instruction_diagnostics import sample


def scene(frame, qpc, hours, paused=False):
    return dict(frame=frame, observed_qpc_ms=qpc, game_total_hours=hours,
        paused=paused, frame_speed_multiplier=0 if paused else 1, free_camera=False,
        scene_camera_control_owned=not paused, camera_center=[0,0,0], camera_position=[0,1,0], battle=dict(active=False))


def capture():
    a, b = scene(10,1000,2), scene(30,3000,2.01)
    cpu_a = dict(created_at=1, monotonic_seconds=1, user_seconds=2, system_seconds=3,
        thread_snapshot=dict(threads=[dict(tid=42, created_filetime='123', user_100ns=10000000, kernel_100ns=10000000, observed_monotonic_seconds=1)]))
    cpu_b = dict(created_at=1, monotonic_seconds=3, user_seconds=3, system_seconds=3.5,
        thread_snapshot=dict(threads=[dict(tid=42, created_filetime='123', user_100ns=20000000, kernel_100ns=15000000, observed_monotonic_seconds=3)]))
    resources = dict(pid=7, executable='game.exe', before=cpu_a, after=cpu_b, elapsed_seconds=2,
        user_seconds=1, system_seconds=.5, thread_cpu=thread_deltas(cpu_a['thread_snapshot'], cpu_b['thread_snapshot'],2,1.5))
    return dict(completed=True, capture_valid=True, protected_files_unchanged=True, settings_unchanged=True,
        pid=7, executable='game.exe', created_at=1, process_created_filetime='100', selected_lifetimes=[dict(tid=42, created_filetime='123')],
        samples=[sample()], requested_count=1, observations=[dict(index=0, scene=scene(20,2000,2.005),caller_seconds=.03)],
        summary=summarize([sample()],7,'game.exe','100',[(42,'123')]), scene_before=a, scene_after=b,
        simulation_progress=simulation_progress(a,b), capture_budget_seconds_per_call=.25,
        source_reference=dict(game_total_hours=1),restored=scene(40,4000,1,True), final_scene=scene(50,5000,1,True),
        process_resources=resources)


def test_replay_counts_and_recompute_whole_thread_cpu():
    d = capture(); result = analyze(d)
    assert result['process_cpu_seconds'] == 1.5
    assert result['threads'][0]['whole_thread_cpu']['cpu_seconds'] == 1.5
    assert result['caller_seconds_max'] == .03
    assert d['summary'].get('pid') is None  # Replay does not mutate the retained summary.


@pytest.mark.parametrize('key,value', [('completed',False),('capture_valid',False),('protected_files_unchanged',False),
    ('settings_unchanged',False),('requested_count',2),('restoration_error','failed')])
def test_failed_or_incomplete_controller_rejected(key,value):
    d = capture(); d[key] = value
    with pytest.raises(ValueError): analyze(d)


def test_poisoned_counts_rejected():
    d = capture(); d['summary']['observations'] = 999
    with pytest.raises(ValueError,match='Cached address'): analyze(d)


@pytest.mark.parametrize('key,value', [('paused',True),('frame_speed_multiplier',5),('scene_camera_control_owned',False),
    ('camera_position',[100,0,0]),('frame',31),('observed_qpc_ms',999)])
def test_scene_contradictions_rejected(key,value):
    d = capture(); d['observations'][0]['scene'][key] = value
    with pytest.raises((ValueError,RuntimeError)): analyze(d)


def test_nonmonotonic_scene_observations_rejected():
    d = capture(); second = deepcopy(d['samples'][0]); second['threads'][0]['capture_filetime']='501'
    d['samples'].append(second); d['requested_count']=2
    d['summary']=summarize(d['samples'],7,'game.exe','100',[(42,'123')])
    d['observations'].append(dict(index=1,scene=scene(19,1900,2.004),caller_seconds=.03))
    with pytest.raises(ValueError,match='order'): analyze(d)


@pytest.mark.parametrize('target,key,value', [('restored','game_total_hours',1.01),('final_scene','scene_camera_control_owned',True),
    ('final_scene','paused',False),('final_scene','frame_speed_multiplier',1)])
def test_restoration_contradictions_rejected(target,key,value):
    d = capture(); d[target][key] = value
    with pytest.raises(ValueError): analyze(d)


def test_cpu_cache_poison_and_identity_rejected():
    d = capture(); d['process_resources']['thread_cpu']['threads'][0]['cpu_seconds']=2
    with pytest.raises(ValueError,match='CPU thread'): analyze(d)
    d = capture(); d['process_resources']['after']['created_at']=2
    with pytest.raises(ValueError,match='identity'): analyze(d)


def test_invalid_caller_cost_rejected():
    for cost in (.001,.3,float('nan')):
        d = capture(); d['observations'][0]['caller_seconds']=cost
        with pytest.raises(ValueError): analyze(d)


def separated_capture():
    d = capture(); d['capture_schedule']='scene_then_jitter_then_pss'
    d['samples'][0]['started_at']=1001
    d['observations'][0].update(scene_observed_at=1000,jitter_seconds=1,capture_delay_after_scene_seconds=1)
    return d


def test_retained_capture_separation_replayed():
    result=analyze(separated_capture())
    assert result['capture_delay_after_scene_min']==result['capture_delay_after_scene_max']==1


@pytest.mark.parametrize('key,value',[('scene_observed_at',1000.9),('jitter_seconds',.01),('capture_delay_after_scene_seconds',2)])
def test_false_capture_separation_rejected(key,value):
    d=separated_capture();d['observations'][0][key]=value
    with pytest.raises(ValueError,match='separation'):analyze(d)
