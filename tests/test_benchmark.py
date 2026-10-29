import asyncio
import pytest
from benchmark import collect, validate_nav_diagnostics, validate_camera_stability, simulation_progress
from fake_plugin import FakePlugin
from probe import Client


def test_collect_real_stream_separates_windows():
    async def run():
        async with FakePlugin() as fake:
            data = await collect(Client(fake.port), 2, 3, 'fixture', {'scene': 'fake'}, wait_timeout=2)
            first, second = data['windows']
            assert first['statistics']['count'] == second['statistics']['count'] == 3
            assert second['observed_before']['frame'] - first['observed_after']['frame'] >= 5
    asyncio.run(run())


def test_collect_rejects_speed_change_during_stats_read():
    class ChangingClient:
        frame = 0
        speed = 1
        async def call(self, command, **params):
            if command == 'get_frame_stats':
                self.speed = 5
                return {'count': params['n']}
            self.frame += 10
            return dict(frame=self.frame, world_ready=True, paused=False, frame_speed_multiplier=self.speed)
    with pytest.raises(RuntimeError, match='while reading statistics'):
        asyncio.run(collect(ChangingClient(), 1, 3, 'fixture', {}))


def test_collect_rejects_overlapping_native_frame_windows():
    class OverlapClient:
        frame = 0
        async def call(self, command, **params):
            if command == 'get_frame_stats':
                return dict(count=3, first_frame=10, last_frame=12)
            self.frame += 10
            return dict(frame=self.frame, world_ready=True, paused=False, frame_speed_multiplier=1)
    with pytest.raises(RuntimeError, match='Overlapping'):
        asyncio.run(collect(OverlapClient(), 2, 3, 'fixture', {}))


def nav_stats():
    return dict(first_frame=10, last_frame=12,
        systems=dict(navmesh_findPath_calls_total=2, navmesh_findPath_mean_ms=4,
            navmesh_findPath_max_call_ms=12, navmesh_findPath_threads=dict(
                game_thread=dict(calls_total=0, mean_ms=0, max_call_ms=0),
                other_threads=dict(calls_total=2, mean_ms=4, max_call_ms=12),
                unclassified=dict(calls_total=0, mean_ms=0, max_call_ms=0))),
        navmesh_slow_calls=[dict(start_frame=9, completion_frame=10, elapsed_ms=12,
            thread_id=3, game_thread_id_at_start=2, thread_kind='other_threads')],
        navmesh_slow_calls_total=1, navmesh_slow_calls_capacity=32,
        navmesh_slow_calls_threshold_ms=10, navmesh_slow_calls_retention_truncated=False)


def test_navigation_call_may_start_before_window():
    validate_nav_diagnostics(nav_stats())


@pytest.mark.parametrize('field,value,error', [
    ('completion_frame', 13, 'outside frame window'),
    ('thread_kind', 'game_thread', 'identity mismatch'),
    ('elapsed_ms', 9, 'below threshold'),
])
def test_navigation_diagnostics_reject_inconsistent_call(field, value, error):
    stats = nav_stats()
    stats['navmesh_slow_calls'][0][field] = value
    with pytest.raises(RuntimeError, match=error):
        validate_nav_diagnostics(stats)


def test_navigation_diagnostics_reject_non_partitioned_counts():
    stats = nav_stats()
    stats['systems']['navmesh_findPath_threads']['game_thread']['calls_total'] = 1
    with pytest.raises(RuntimeError, match='counts do not match'):
        validate_nav_diagnostics(stats)


@pytest.mark.parametrize('user,kernel', [(None, 1), (-1, 0), (float('nan'), 0)])
def test_navigation_cpu_rejects_invalid_counter_pairs(user, kernel):
    stats = nav_stats()
    stats['navmesh_slow_calls'][0].update(thread_cpu_user_ms=user, thread_cpu_kernel_ms=kernel)
    with pytest.raises(RuntimeError, match='CPU counters'):
        validate_nav_diagnostics(stats)


@pytest.mark.parametrize('user,kernel', [(None, None), (0, 0), (15.625, 0)])
def test_navigation_cpu_preserves_unavailable_and_quantized_samples(user, kernel):
    stats = nav_stats()
    stats['navmesh_slow_calls'][0].update(thread_cpu_user_ms=user, thread_cpu_kernel_ms=kernel)
    # A rounded CPU sample may exceed a short wall interval; do not clamp it.
    validate_nav_diagnostics(stats)


def test_navigation_argument_vector_requires_all_four_components():
    stats = nav_stats()
    stats['navmesh_slow_calls'][0]['start_vector'] = [1, 2, 3]
    with pytest.raises(RuntimeError, match='argument vector'):
        validate_nav_diagnostics(stats)


@pytest.mark.parametrize('field', ['camera_center', 'camera_position'])
def test_camera_motion_invalidates_measurements(field):
    reference = dict(camera_center=[0,0,0], camera_position=[0,100,0], free_camera=False)
    observed = dict(reference)
    observed[field] = [1000,0,0]
    with pytest.raises(RuntimeError, match='Camera moved'):
        validate_camera_stability(reference, observed)


def test_camera_mode_change_invalidates_measurements():
    reference = dict(camera_center=[0,0,0], camera_position=[0,100,0], free_camera=False)
    with pytest.raises(RuntimeError, match='Camera mode changed'):
        validate_camera_stability(reference, dict(reference, free_camera=True))


def test_simulation_progress_uses_game_clock_and_wall_time():
    before = dict(game_total_hours=10, observed_qpc_ms=1000, frame=1)
    after = dict(game_total_hours=10.1, observed_qpc_ms=3000, frame=200)
    assert simulation_progress(before, after)['game_hours_per_wall_second'] == pytest.approx(.05)


@pytest.mark.parametrize('hours,qpc', [(9, 3000), (11, 1000), (None, 3000)])
def test_simulation_clock_regression_or_zero_interval_is_rejected(hours, qpc):
    with pytest.raises(RuntimeError, match='simulation clock'):
        simulation_progress(dict(game_total_hours=10, observed_qpc_ms=1000, frame=1),
                            dict(game_total_hours=hours, observed_qpc_ms=qpc, frame=2))


def test_simulation_progress_remains_optional_for_old_plugins():
    assert simulation_progress({}, {}) is None


def test_navigation_result_partition_rejects_missing_false_calls():
    stats = nav_stats()
    stats['systems']['navmesh_findPath_results'] = {
        'true': dict(calls_total=1, mean_ms=4, max_call_ms=12, hierarchical_calls_total=1),
        'false': dict(calls_total=0, mean_ms=0, max_call_ms=0, hierarchical_calls_total=0)}
    with pytest.raises(RuntimeError, match='result counts'):
        validate_nav_diagnostics(stats)


def test_navigation_output_size_cannot_be_negative():
    stats = nav_stats()
    stats['navmesh_slow_calls'][0]['output_size_after'] = -1
    with pytest.raises(RuntimeError, match='output size'):
        validate_nav_diagnostics(stats)
