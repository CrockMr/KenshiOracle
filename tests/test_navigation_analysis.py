import copy
import json
import pytest
from analyze_navigation import analyze


def call(start=100, elapsed=12):
    return dict(start_frame=9, completion_frame=10, elapsed_ms=elapsed, started_qpc_ms=start,
        thread_id=3, game_thread_id_at_start=2, thread_kind='other_threads',
        start_key=7, goal_key=8, radius=.4, water=10, hierarchical=True, result=False,
        start_vector=[1,2,3,0], goal_vector=[4,5,6,0],
        thread_cpu_user_ms=15.625, thread_cpu_kernel_ms=0)


def stats(event):
    return dict(count=3, first_frame=10, last_frame=12,
        systems=dict(navmesh_findPath_calls_total=1, navmesh_findPath_mean_ms=event['elapsed_ms']/3,
            navmesh_findPath_max_call_ms=event['elapsed_ms'], navmesh_findPath_threads=dict(
                game_thread=dict(calls_total=0, mean_ms=0, max_call_ms=0),
                other_threads=dict(calls_total=1, mean_ms=event['elapsed_ms']/3, max_call_ms=event['elapsed_ms']),
                unclassified=dict(calls_total=0, mean_ms=0, max_call_ms=0))),
        navmesh_slow_calls=[event], navmesh_slow_calls_total=1, navmesh_slow_calls_capacity=32,
        navmesh_slow_calls_threshold_ms=10, navmesh_slow_calls_retention_truncated=False)


def write(root, folder, event, *, created=10, drift=0, transition=False, restored=True):
    target = root/('city-paired-'+folder)
    target.mkdir()
    scene = dict(camera_center=[0,0,0], camera_position=[0,100,0], free_camera=False)
    after = dict(scene, camera_center=[drift,0,0])
    context = dict(population_before=dict(scene=scene))
    if transition:
        context['scene_transition_statistics'] = stats(event)
    data = dict(initial=dict(plugin_version='0.6.2'), context=context,
        population_after=dict(scene=after), windows=[dict(statistics=stats(event),observed_scene=scene)],
        process_resources=dict(pid=42, before=dict(created_at=created)))
    (target/'x5.json').write_text(json.dumps(data))
    (target/'manifest.json').write_text(json.dumps(dict(pid=42,restored=dict(scene=scene) if restored else None)))


def test_overlapping_transition_and_steady_observations_are_not_double_counted(tmp_path):
    write(tmp_path, 'a', call(), transition=True)
    write(tmp_path, 'b', call())
    report = analyze(tmp_path)
    assert report['summary']['observations_in_files'] == 3
    assert report['summary']['unique_retained_calls'] == 1
    assert report['summary']['repeated_observations_removed'] == 2
    assert len(report['events'][0]['seen_in']) == 3


def test_reused_pid_does_not_merge_different_processes(tmp_path):
    write(tmp_path, 'a', call(), created=10)
    write(tmp_path, 'b', call(), created=11)
    assert analyze(tmp_path)['summary']['unique_retained_calls'] == 2


def test_conflicting_same_call_observations_fail_instead_of_silent_merge(tmp_path):
    write(tmp_path, 'a', call())
    write(tmp_path, 'b', call(elapsed=13))
    with pytest.raises(ValueError, match='Conflicting'):
        analyze(tmp_path)


def test_camera_invalid_data_is_retained_but_excluded_from_controlled_cpu_group(tmp_path):
    write(tmp_path, 'a', call(), drift=1000)
    report = analyze(tmp_path)
    assert report['summary']['cpu_available_calls'] == 1
    assert report['summary']['checked_steady_false_cpu_calls'] == 0
    assert report['files'][0]['camera_quality'] == 'invalid'


def test_same_keys_do_not_hide_different_goal_positions(tmp_path):
    write(tmp_path, 'a', call())
    other = copy.deepcopy(call(start=200))
    other['goal_vector'][0] = 10
    write(tmp_path, 'b', other)
    report = analyze(tmp_path)
    assert report['summary']['same_keys_with_different_xyz_groups'] == 1
    assert report['key_groups_with_different_xyz'][0]['distinct_xyz'] == 2


def test_failed_restoration_does_not_discard_completed_measurement(tmp_path):
    write(tmp_path, 'a', call(), restored=False)
    report = analyze(tmp_path)
    assert not report['files'][0]['original_run_restored']
    assert report['summary']['checked_steady_false_cpu_calls'] == 1


def test_context_before_scene_preparation_is_not_labelled_as_town_work(tmp_path):
    write(tmp_path, 'a', call(), transition=True)
    path = tmp_path/'city-paired-a/x5.json'
    data = json.loads(path.read_text())
    data['context']['prepared'] = dict(after=dict(frame=11))
    path.write_text(json.dumps(data))
    report = analyze(tmp_path)
    assert all(source['relation_to_prepare']=='before_prepare' for source in report['events'][0]['seen_in'])


def write_battle(root, event, *, last_observed=12, drift=0, created=10):
    scene = dict(camera_center=[0,0,0], camera_position=[0,100,0], free_camera=True)
    data = dict(pid=42, initial_ping=dict(plugin_version='0.7.3'),
        initial=dict(scene, frame=9), prepared=dict(requested_entities=10),
        observations=[dict(elapsed=1, scene=dict(scene, frame=last_observed, camera_center=[drift,0,0]))],
        statistics=stats(event), process_resources=dict(pid=42, before=dict(created_at=created)),
        completed=True, restored=dict(paused=True), transport='mcp-stdio')
    path = root/'battle-20261028T000000Z.json'
    path.write_text(json.dumps(data))
    return path


def test_battle_partial_output_is_retained_without_steady_city_classification(tmp_path):
    event = dict(call(), output_size_before=0, output_size_after=6)
    write_battle(tmp_path, event)
    report = analyze(tmp_path, tmp_path)
    assert report['events'][0]['call']['output_size_after'] == 6
    assert report['events'][0]['seen_in'][0]['phase'] == 'battle_tail'
    assert report['summary']['checked_steady_false_cpu_calls'] == 0
    assert report['summary']['battle_tail_retained_calls'] == 1
    assert report['summary']['retained_false_with_nonempty_output_calls'] == 1


def test_battle_window_after_last_camera_read_is_explicit(tmp_path):
    write_battle(tmp_path, call(), last_observed=11)
    report = analyze(tmp_path, tmp_path)
    source = report['events'][0]['seen_in'][0]
    assert source['camera_quality'] == 'per_observation'
    assert source['window_observation_span'] == 'ends_after_last_observation'


def test_missing_creation_time_cannot_merge_slow_calls_by_pid_alone(tmp_path):
    write_battle(tmp_path, call(), created=None)
    with pytest.raises(ValueError, match='Missing process identity'):
        analyze(tmp_path, tmp_path)


def test_same_call_seen_in_city_and_battle_is_still_one_event(tmp_path):
    write(tmp_path, 'a', call())
    write_battle(tmp_path, call())
    report = analyze(tmp_path, tmp_path)
    assert report['summary']['unique_retained_calls'] == 1
    assert report['summary']['repeated_observations_removed'] == 1
    assert {source['kind'] for source in report['events'][0]['seen_in']} == {'city', 'battle'}


def test_failed_battle_has_provenance_without_invented_window(tmp_path):
    (tmp_path/'battle-20261028T000000Z.json').write_text(json.dumps(dict(pid=42, error='setup failed')))
    report = analyze(tmp_path, tmp_path)
    assert report['summary']['unique_retained_calls'] == 0
    assert report['summary']['excluded_capture_files'] == 1
    assert report['files'][0]['sha256'] and report['files'][0]['error'] == 'setup failed'


def test_drifting_battle_is_retained_without_camera_certification(tmp_path):
    write_battle(tmp_path, call(), drift=100)
    report = analyze(tmp_path, tmp_path)
    assert report['files'][0]['camera_quality'] == 'invalid'
    assert report['summary']['battle_tail_retained_calls'] == 1
    assert report['summary']['battle_sampled_camera_calls'] == 0


def test_battle_pid_disagreement_is_rejected(tmp_path):
    path = write_battle(tmp_path, call())
    data = json.loads(path.read_text())
    data['process_resources']['pid'] = 99
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Conflicting battle process'):
        analyze(tmp_path, tmp_path)


def test_thread_context_and_tail_share_identity_but_keep_distinct_provenance(tmp_path):
    path = write_battle(tmp_path, call())
    data = json.loads(path.read_text())
    data['thread_attribution_statistics'] = stats(call())
    path.write_text(json.dumps(data))
    report = analyze(tmp_path, tmp_path)
    assert report['summary']['unique_retained_calls'] == 1
    assert report['summary']['repeated_observations_removed'] == 1
    assert report['summary']['transition_only_calls'] == 0
    assert {source['phase'] for source in report['events'][0]['seen_in']} == {'battle_tail', 'battle_diagnostic_context'}


def test_context_observation_span_is_not_borrowed_from_tail(tmp_path):
    path = write_battle(tmp_path, call())
    data = json.loads(path.read_text())
    context = stats(call())
    context.update(first_frame=8, last_frame=10)
    data['thread_attribution_statistics'] = context
    path.write_text(json.dumps(data))
    sources = analyze(tmp_path, tmp_path)['events'][0]['seen_in']
    assert sources[0]['window_observation_span'] == 'within_observation_span'
    assert sources[1]['window_observation_span'] == 'starts_before_initial_observation'


def test_retained_context_records_expose_their_truncation(tmp_path):
    path = write_battle(tmp_path, call())
    data = json.loads(path.read_text())
    context = stats(call())
    context.update(navmesh_slow_calls_total=2, navmesh_slow_calls_retention_truncated=True)
    data['thread_attribution_statistics'] = context
    path.write_text(json.dumps(data))
    sources = analyze(tmp_path, tmp_path)['events'][0]['seen_in']
    assert sources[1]['retention_truncated']
