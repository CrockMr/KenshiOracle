"""Virtual-clock checks of no-command controls and non-bursting request slots."""
import asyncio
import pytest
import live_observer_overhead as pilot


class Clock:
    def __init__(self, first_delay=0):
        self.now = 100.0
        self.first_delay = first_delay

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        assert seconds > 0
        self.now += seconds + self.first_delay
        self.first_delay = 0


class Client:
    def __init__(self, clock, duration=.02, fail=False):
        self.clock, self.duration, self.fail = clock, duration, fail
        self.calls = []

    async def call(self, command, **params):
        self.calls.append((self.clock.now, command, params))
        self.clock.now += self.duration
        if self.fail:
            raise RuntimeError('synthetic request failure')
        return dict(index=len(self.calls))


def setup(monkeypatch, condition, frequency, **clock_args):
    clock = Clock(**clock_args)
    monkeypatch.setattr(pilot, 'clock', clock.monotonic)
    monkeypatch.setattr(pilot.asyncio, 'sleep', clock.sleep)
    return clock, dict(plan=dict(condition=condition, frequency_hz=frequency))


@pytest.mark.parametrize('frequency,expected', [(1, 5), (10, 50)])
def test_baseline_has_matched_timer_wakes_and_no_commands(monkeypatch, frequency, expected):
    clock, row = setup(monkeypatch, 'baseline', frequency)
    client = Client(clock)
    asyncio.run(pilot.collect_slots(client, row))
    assert not client.calls and not row['requests'] and not row['skipped_slots']
    assert len(row['baseline_wakes']) == expected and row['expected_requests'] == 0
    assert [w['slot'] for w in row['baseline_wakes']] == list(range(expected))
    assert row['measured_end_monotonic_seconds'] - row['measured_start_monotonic_seconds'] == 5


@pytest.mark.parametrize('condition', ['full', 'aggregates'])
def test_requests_keep_absolute_schedule_and_raw_results(monkeypatch, condition):
    clock, row = setup(monkeypatch, condition, 1)
    client = Client(clock)
    asyncio.run(pilot.collect_slots(client, row))
    assert len(client.calls) == 5 and not row['baseline_wakes'] and not row['skipped_slots']
    for slot, request in enumerate(row['requests']):
        assert client.calls[slot] == (100 + slot, 'get_frame_stats', dict(n=60, detail=condition))
        assert request['result'] == dict(index=slot + 1)
        assert request['scheduled_offset_seconds'] == slot and request['lateness_seconds'] == 0
        assert request['client_ms'] == pytest.approx(20) and request['overrun_seconds'] == 0
        assert 'compact_result_bytes' not in request  # Encoding belongs after CPU finish.


def test_overruns_skip_expired_slots_without_immediate_catchup(monkeypatch):
    clock, row = setup(monkeypatch, 'aggregates', 10)
    client = Client(clock, duration=.25)
    asyncio.run(pilot.collect_slots(client, row))
    assert len(row['requests']) == 17 and len(row['skipped_slots']) == 33
    assert sorted([r['slot'] for r in row['requests']] + [r['slot'] for r in row['skipped_slots']]) == list(range(50))
    assert all(s['reason'] == 'previous_request_overrun' and s['lateness_seconds'] > 0 for s in row['skipped_slots'])
    assert all(b['started_monotonic_seconds'] > a['finished_monotonic_seconds'] for a, b in zip(row['requests'], row['requests'][1:]))
    assert row['requests'][-1]['overrun_seconds'] == pytest.approx(.05)
    assert row['measured_end_monotonic_seconds'] == pytest.approx(105.05)


def test_late_baseline_wake_is_explicit_and_not_counted_as_command(monkeypatch):
    clock, row = setup(monkeypatch, 'baseline', 1, first_delay=2)
    client = Client(clock)
    asyncio.run(pilot.collect_slots(client, row))
    assert [w['slot'] for w in row['baseline_wakes']] == [0, 3, 4]
    assert [s['slot'] for s in row['skipped_slots']] == [1, 2]
    assert all(s['reason'] == 'wake_late' and s['lateness_seconds'] >= 1 for s in row['skipped_slots'])
    assert not client.calls and row['measured_end_monotonic_seconds'] == 105


def test_failed_request_preserves_timings_and_stops_collection(monkeypatch):
    clock, row = setup(monkeypatch, 'full', 10)
    client = Client(clock, duration=.2, fail=True)
    with pytest.raises(RuntimeError, match='synthetic'):
        asyncio.run(pilot.collect_slots(client, row))
    assert len(row['requests']) == 1 and row['requests'][0]['error']['type'] == 'RuntimeError'
    assert row['requests'][0]['client_ms'] == pytest.approx(200)
    assert row['measured_end_monotonic_seconds'] == pytest.approx(100.2)


def locked_scene(position, hours=404, owned=True):
    return dict(paused=True, game_total_hours=hours, scene_camera_control_owned=owned,
                edge_scrolling=False, free_camera=False, camera_position=[position, 0, 0],
                camera_center=[position, 1, 0])


def check_locked(scene):
    if (not scene['paused'] or scene['game_total_hours'] != 404 or
        not scene['scene_camera_control_owned'] or scene['edge_scrolling']):
        raise RuntimeError('synthetic paused/clock/ownership rejection')


class SceneClient:
    def __init__(self, scenes):
        self.scenes = iter(scenes)
        self.commands = []

    async def call(self, command):
        self.commands.append(command)
        assert command == 'get_scene_state'
        return next(self.scenes)


def test_camera_reference_is_taken_after_initial_drift_settles(monkeypatch):
    clock, _ = setup(monkeypatch, 'baseline', 1)
    client = SceneClient([locked_scene(0), locked_scene(100), locked_scene(100)])
    records = []
    reference = asyncio.run(pilot.stabilize_camera(client, check_locked, records))
    assert reference is records[-1]['scene'] and reference['camera_position'] == [100, 0, 0]
    assert [r['observed_monotonic_seconds'] for r in records] == [100, 101, 102]
    assert client.commands == ['get_scene_state'] * 3 and clock.now == 102
    assert pilot.camera_delta(records[0]['scene'], reference) == dict(camera_position_distance=100, camera_center_distance=100)


def test_persistent_camera_drift_times_out_without_statistics_capture(monkeypatch):
    clock, _ = setup(monkeypatch, 'baseline', 1)
    client = SceneClient([locked_scene(10 * i) for i in range(20)])
    records = []
    with pytest.raises(RuntimeError, match='did not stabilize'):
        asyncio.run(pilot.stabilize_camera(client, check_locked, records, timeout=10))
    assert clock.now == 110 and len(records) == 10
    assert client.commands == ['get_scene_state'] * 10


@pytest.mark.parametrize('change', ['clock', 'ownership'])
def test_stabilization_rejects_clock_or_ownership_before_any_measurement(monkeypatch, change):
    clock, _ = setup(monkeypatch, 'baseline', 1)
    scene = locked_scene(0, hours=405 if change == 'clock' else 404, owned=change != 'ownership')
    client = SceneClient([scene])
    records = []
    with pytest.raises(RuntimeError, match='paused/clock/ownership'):
        asyncio.run(pilot.stabilize_camera(client, check_locked, records))
    assert len(records) == 1 and clock.now == 100
    assert client.commands == ['get_scene_state']


class EarlyClock(Clock):
    """Every first sleep wakes 13 ms early; the corrective sleep advances normally."""
    def __init__(self):
        super().__init__()
        self.sleep_calls = 0

    async def sleep(self, seconds):
        assert seconds >= .001
        self.sleep_calls += 1
        self.now += max(0, seconds - .013) if self.sleep_calls % 2 else seconds


@pytest.mark.parametrize('condition', ['baseline', 'full', 'aggregates'])
def test_early_windows_wakes_cannot_start_slots_or_finish_block_early(monkeypatch, condition):
    clock = EarlyClock()
    monkeypatch.setattr(pilot, 'clock', clock.monotonic)
    monkeypatch.setattr(pilot.asyncio, 'sleep', clock.sleep)
    row = dict(plan=dict(condition=condition, frequency_hz=1))
    client = Client(clock)
    asyncio.run(pilot.collect_slots(client, row))
    observed = row['baseline_wakes'] if condition == 'baseline' else row['requests']
    assert len(observed) == 5 and not row['skipped_slots']
    assert all(r['started_monotonic_seconds'] >= 100 + r['scheduled_offset_seconds'] for r in observed)
    assert all(r['lateness_seconds'] >= 0 for r in observed)
    assert row['measured_end_monotonic_seconds'] >= 105
    assert clock.sleep_calls >= 10  # Four inter-slot waits plus the block-end wait were rechecked.
    assert len(client.calls) == (0 if condition == 'baseline' else 5)


def test_early_wakes_do_not_shorten_camera_stabilization_interval(monkeypatch):
    clock = EarlyClock()
    monkeypatch.setattr(pilot, 'clock', clock.monotonic)
    monkeypatch.setattr(pilot.asyncio, 'sleep', clock.sleep)
    client = SceneClient([locked_scene(0), locked_scene(0)])
    records = []
    asyncio.run(pilot.stabilize_camera(client, check_locked, records))
    assert len(records) == 2 and records[1]['observed_monotonic_seconds'] - records[0]['observed_monotonic_seconds'] >= 1
    assert clock.sleep_calls >= 2
