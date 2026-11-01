"""Restoration to a followed reference waits for the engine's settled follow pivot.

After a follow is (re)attached the engine's pivot (center - follow position -
offset) is provisionally Y=10 and settles to the reference's +10.9 after an
unpredictable number of frames. Committing on the provisional pivot calibrates
a 0.9 offset and leaves the center 0.9 too high once the pivot settles.
"""
import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_probe import FakeProbe
from oracle_runner import (OracleSession, ScenarioError, check_controls, execute_scenario,
                           follow_pivot, restore_interrupted_scenario, wait_stable_controls)

ACTOR = [66484, 781.2881469726562, -90000]
PIVOT = [0, 10.9, 0]
LATE = 90  # Frames: later than a stable baseline window of the old runner (~35 frames).
NEVER = 10**9


def config(tmp_path):
    return dict(runtime=str(tmp_path / 'runtime'), runs=str(tmp_path / 'runs'),
                oracle_output=str(tmp_path / 'probe-output'), load_timeout=.5,
                run_until_timeout=.5, scenario_timeout=10)


def stability_clock(monkeypatch):
    clock = SimpleNamespace(value=0.0)
    original_sleep = asyncio.sleep

    async def advance(seconds):
        clock.value += seconds
        await original_sleep(0)

    monkeypatch.setattr('oracle_runner.time', SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr('oracle_runner.asyncio.sleep', advance)
    return clock


def followed(cfg, settle, pivot=PIVOT):
    """A fake following its first actor with a settled pivot, and that captured reference."""
    fake = FakeProbe(cfg['oracle_output'], camera_tracking_base_offset=pivot,
                     camera_pivot_settle_frames=settle)
    for state in (fake.state, fake.initial_state):
        state['characters'][0]['position'] = list(ACTOR)
    fake.camera_follow_id = fake.state['characters'][0]['id']
    fake._camera_tracking_active = True
    original = asyncio.run(fake.call('get_scene_state'))
    assert follow_pivot(original) == pytest.approx(PIVOT)
    return fake, original


def pivots(rows):
    return [follow_pivot(row['scene'])[1] for row in rows if 'scene' in row]


def write_guard(cfg, original):
    Path(cfg['runtime']).mkdir()
    path = Path(cfg['runtime']) / 'oracle-restoration.json'
    path.write_text(json.dumps(dict(restore_required=True, save='Synthetic save', controls=original,
                                    instance_id='old-instance')), encoding='utf-8')
    return path


def test_late_settle_after_a_stable_provisional_baseline_restores_with_zero_offset(tmp_path, monkeypatch):
    # Failed-run shape (report 20261101T122316.049858Z-59edbec4): the held pivot
    # stays provisional for longer than a stable window, the commit's re-follow
    # settles at once. Before the fix this committed offset 0.9 (center +0.9).
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, (LATE, 0))
    baseline, post = [], []
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(
        original, baseline_observations=baseline, observations=post))
    provisional = [row for row in baseline if 'scene' in row and follow_pivot(row['scene'])[1] == 10]
    # The provisional pivot alone would have met the stability rule.
    assert len({row['scene']['frame'] for row in provisional}) >= 3
    assert provisional[-1]['elapsed_seconds'] - provisional[0]['elapsed_seconds'] >= .5
    assert all('camera follow pivot' in row['error'] for row in provisional)
    assert not any(row['accepted'] for row in provisional)
    accepted = [row for row in baseline if row['accepted']]
    assert accepted and all(follow_pivot(row['scene']) == pytest.approx(PIVOT) for row in accepted)
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    assert result['reference_follow_pivot'] == pytest.approx(PIVOT)
    assert fake.calls.count('prepare_scene_control') == fake.calls.count('commit_scene_control') == 1
    # The settled pose stays put: no correction is still pending in the pivot.
    assert asyncio.run(fake.call('get_scene_state'))['camera_center'] == pytest.approx(original['camera_center'])


@pytest.mark.parametrize('settle', [0, 2, 12, (12, 0), (0, 12), (2, 14), (LATE, LATE)])
def test_settle_inside_the_window_or_immediately_restores_with_zero_offset(tmp_path, monkeypatch, settle):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, settle)
    baseline, post = [], []
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(
        original, baseline_observations=baseline, observations=post))
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    assert all(follow_pivot(row['scene']) == pytest.approx(PIVOT) for row in baseline if row['accepted'])
    assert baseline[-1]['distinct_frames'] >= 3 and baseline[-1]['stable_seconds'] >= .5
    assert post[-1]['distinct_frames'] >= 3 and post[-1]['stable_seconds'] >= .5
    assert fake.calls.count('commit_scene_control') == 1


def test_never_settling_pivot_fails_at_the_deadline_without_commit_and_keeps_journal(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, (NEVER, 0))
    path = write_guard(cfg, original)
    with pytest.raises(ScenarioError, match='did not stabilize.*camera follow pivot'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert 'commit_scene_control' not in fake.calls
    assert fake.calls.count('prepare_scene_control') == 1
    assert fake._camera_pending is not None
    assert fake.camera_follow_offset == [0, 0, 0]
    pending = json.loads(path.read_text(encoding='utf-8'))
    assert pending['restore_required'] is True
    attempt = pending['recovery_attempt']
    assert 'camera follow pivot' in attempt['error']
    assert set(pivots(attempt['baseline_observations'])) == {10}
    assert attempt['observations'] == []
    # The existing 10 s stability deadline, not a longer one.
    assert 9.9 <= attempt['baseline_observations'][-1]['elapsed_seconds'] < 10
    assert clock.value < 10.2


def test_moved_actor_with_settled_pivot_calibrates_only_the_move(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, (LATE, 0))
    move = [3, -.936, 5]
    fake.initial_state['characters'][0]['position'] = [a+b for a, b in zip(ACTOR, move)]
    path = write_guard(cfg, original)
    result = asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert result['restored'] is True
    assert fake.state['characters'][0]['position'] == [a+b for a, b in zip(ACTOR, move)]
    assert fake.camera_follow_offset == pytest.approx([-value for value in move])
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    assert follow_pivot(result['scene']) == pytest.approx(PIVOT)
    assert json.loads(path.read_text(encoding='utf-8'))['restore_required'] is False


@pytest.mark.parametrize('settle', [(LATE, 0), (LATE, LATE)])
def test_delayed_settle_through_interrupted_recovery(tmp_path, monkeypatch, settle):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, settle)
    path = write_guard(cfg, original)
    result = asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert result['restored'] is True and fake.loads == ['Synthetic save']
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    recovered = json.loads(path.read_text(encoding='utf-8'))
    assert recovered['restore_required'] is False
    assert 10 in pivots(recovered['recovery_attempt']['baseline_observations'])
    assert fake.calls.count('commit_scene_control') == 1


@pytest.mark.parametrize('settle', [(LATE, 0), (LATE, LATE)])
def test_delayed_settle_through_scenario_cleanup(tmp_path, monkeypatch, settle):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, settle)
    scenario = dict(schema_version='0.1', name='synthetic-run', save='Synthetic save',
                    speed=1, repeat=1, actions=[], checkpoints=[dict(at=0, name='only')])
    result = asyncio.run(execute_scenario(scenario, cfg, client=fake))
    assert result['restored'] is True
    report = json.loads(Path(result['report']).read_text(encoding='utf-8'))
    restoration = report['restoration']
    assert restoration['verified'] is True
    assert 10 in pivots(restoration['baseline_observations'])
    assert restoration['reference_follow_pivot'] == pytest.approx(PIVOT)
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert restoration['scene']['camera_center'] == pytest.approx(original['camera_center'])
    guard = json.loads((Path(cfg['runtime']) / 'oracle-restoration.json').read_text(encoding='utf-8'))
    assert guard['restore_required'] is False
    assert fake.calls.count('commit_scene_control') == 1


def test_scene_request_path_is_unchanged_and_has_no_pivot_gate(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, (LATE, 0))
    params = dict(camera_center=original['camera_center'], camera_orientation=original['camera_orientation'],
                  camera_zoom=original['camera_zoom'], free_camera=False, edge_scrolling=True,
                  speed=1, paused=True, camera_follow_id=original['camera_follow_id'])
    baseline = []
    session = OracleSession(cfg, fake)
    with pytest.raises(ScenarioError, match='camera_center'):
        asyncio.run(session.restore_controls(params=params, baseline_observations=baseline))
    # Unchanged behavior: the provisional held pivot is accepted as the baseline
    # and committed; a scene request has no reference pivot to wait for.
    accepted = [row for row in baseline if row['accepted']]
    assert accepted and all(follow_pivot(row['scene'])[1] == 10 for row in accepted)
    assert not any('camera follow pivot' in row.get('error', '') for row in baseline)
    assert fake.calls.count('commit_scene_control') == 1


def test_followed_reference_without_pivot_is_refused_before_any_mutation(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, None)
    original['camera_follow_center_delta'] = None
    with pytest.raises(ScenarioError, match='follow pivot of the reference controls'):
        asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert not {'pause', 'prepare_scene_control', 'commit_scene_control'} & set(fake.calls)


def test_restoration_limits_are_unchanged(tmp_path, monkeypatch):
    defaults = inspect.signature(wait_stable_controls).parameters
    assert defaults['timeout'].default == 10.0
    assert defaults['stable_seconds'].default == .5
    reference = dict(camera_center=[0, 0, 0], camera_position=[0, 0, 0])
    settings = dict(free_camera=False, edge_scrolling=True, paused=True, camera_follow_id=None,
                    camera_orientation=[1, 0, 0, 0], selected_game_speed=1, camera_zoom=-20)
    reference.update(settings)
    check_controls(reference, dict(reference, camera_center=[.05, 0, 0]))
    with pytest.raises(ScenarioError, match='camera_center'):
        check_controls(reference, dict(reference, camera_center=[.0501, 0, 0]))
    # The pivot uses the same 0.05 limit.
    for drift, accepted in ((.04, True), (.06, False)):
        stability_clock(monkeypatch)
        run_cfg = config(tmp_path / str(drift))
        fake, original = followed(run_cfg, None)
        fake.camera_tracking_base_offset = [0, PIVOT[1]+drift, 0]
        if accepted:
            result = asyncio.run(OracleSession(run_cfg, fake).restore_controls(original))
            assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
        else:
            with pytest.raises(ScenarioError, match='camera follow pivot'):
                asyncio.run(OracleSession(run_cfg, fake).restore_controls(original))
            assert 'commit_scene_control' not in fake.calls
    # Larger requests are still clamped to 10 s and no window is shorter than 0.5 s or 3 frames.
    stability_clock(monkeypatch)
    run_cfg = config(tmp_path / 'clamp')
    fake = FakeProbe(run_cfg['oracle_output'])
    rows = []
    asyncio.run(wait_stable_controls(OracleSession(run_cfg, fake), observations=rows,
                                     timeout=100, stable_seconds=.01))
    assert rows[-1]['stable_seconds'] >= .5 and rows[-1]['distinct_frames'] >= 3
    clock = stability_clock(monkeypatch)
    fake, original = followed(config(tmp_path / 'deadline'), (NEVER, 0))
    rows = []
    with pytest.raises(ScenarioError, match='did not stabilize'):
        asyncio.run(wait_stable_controls(OracleSession(config(tmp_path / 'deadline'), fake),
                                         observations=rows, timeout=100,
                                         pivot=[0, 0, 0]))
    assert 10 <= clock.value < 10.2


def scenario():
    return dict(schema_version='0.1', name='synthetic-run', save='Synthetic save',
                speed=1, repeat=1, actions=[], checkpoints=[dict(at=0, name='only')])


def followed_without_settle(cfg, offset=(0, 0, 0), pivot=PIVOT, settle=None):
    """Like followed(), with a chosen additional follow offset at capture."""
    fake = FakeProbe(cfg['oracle_output'], camera_tracking_base_offset=pivot,
                     camera_pivot_settle_frames=settle)
    for state in (fake.state, fake.initial_state):
        state['characters'][0]['position'] = list(ACTOR)
    fake.camera_follow_id = fake.state['characters'][0]['id']
    fake.camera_follow_offset = list(offset)
    fake._camera_tracking_active = True
    return fake, asyncio.run(fake.call('get_scene_state'))


@pytest.mark.parametrize('settle', [12, LATE])
def test_capture_waits_for_the_settled_pivot_before_arming(tmp_path, monkeypatch, settle):
    # The load before the run has just attached the follow: the capture window
    # must not record the provisional pivot, or no restoration could match it.
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, None)
    fake._camera_pivot_settles_at = fake.frame + settle
    result = asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert result['restored'] is True
    report = json.loads(Path(result['report']).read_text(encoding='utf-8'))
    capture = report['control_capture_observations']
    provisional = [row for row in capture if 'scene' in row and follow_pivot(row['scene'])[1] == 10]
    assert provisional and not any(row['accepted'] for row in provisional)
    assert all('provisional camera follow pivot' in row['error'] for row in provisional)
    accepted = [row for row in capture if row['accepted']]
    assert accepted and all(follow_pivot(row['scene']) == pytest.approx(PIVOT) for row in accepted)
    assert report['restoration']['reference_follow_pivot'] == pytest.approx(PIVOT)
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert report['restoration']['scene']['camera_center'] == pytest.approx(original['camera_center'])


def test_capture_on_a_never_settling_pivot_is_refused_before_arming(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, _ = followed(cfg, None)
    fake._camera_pivot_settles_at = NEVER
    with pytest.raises(ScenarioError, match='did not stabilize.*provisional camera follow pivot'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()
    assert fake.loads == []
    assert not {'pause', 'prepare_scene_control', 'commit_scene_control'} & set(fake.calls)


def test_capture_without_a_follow_pivot_is_refused_before_arming(tmp_path, monkeypatch):
    # The native omits the pivot when the followed character is not loaded, and
    # probes older than 0.9.5 never report it: no restorable reference exists.
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, _ = followed(cfg, None)
    monkeypatch.setattr(fake, '_camera_follow_diagnostics', lambda: dict(
        camera_follow_offset=[0, 0, 0], camera_follow_position=None, camera_follow_center_delta=None))
    with pytest.raises(ScenarioError, match='follow pivot of the captured controls'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()
    assert fake.loads == []
    assert not {'pause', 'prepare_scene_control', 'commit_scene_control'} & set(fake.calls)


@pytest.mark.parametrize('axis', [0, 2])
def test_held_pivot_off_on_x_or_z_is_rejected(tmp_path, monkeypatch, axis):
    for drift, accepted in ((.04, True), (.06, False)):
        stability_clock(monkeypatch)
        cfg = config(tmp_path / str(drift))
        fake, original = followed(cfg, None)
        fake.camera_tracking_base_offset[axis] += drift
        if accepted:
            result = asyncio.run(OracleSession(cfg, fake).restore_controls(original))
            assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
        else:
            with pytest.raises(ScenarioError, match='camera follow pivot'):
                asyncio.run(OracleSession(cfg, fake).restore_controls(original))
            assert 'commit_scene_control' not in fake.calls


@pytest.mark.parametrize('axis', [0, 1, 2])
def test_pivot_limit_is_exactly_005(tmp_path, monkeypatch, axis):
    # Engine pivot exactly zero; only the reference's recorded pivot differs, so
    # the comparison sees exactly 0.05 (accepted) or 0.0501 (rejected).
    for drift, accepted in ((.05, True), (.0501, False)):
        stability_clock(monkeypatch)
        cfg = config(tmp_path / str(drift))
        fake, original = followed_without_settle(cfg, pivot=[0, 0, 0])
        assert follow_pivot(original) == [0, 0, 0]
        original['camera_follow_center_delta'][axis] = drift
        if accepted:
            result = asyncio.run(OracleSession(cfg, fake).restore_controls(original))
            assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
        else:
            with pytest.raises(ScenarioError, match='camera follow pivot'):
                asyncio.run(OracleSession(cfg, fake).restore_controls(original))
            assert 'commit_scene_control' not in fake.calls


def test_pivot_that_settles_then_goes_provisional_again_restarts_the_window(tmp_path, monkeypatch):
    # Not monotonic: settled for 4 frames after the prepare, provisional for the
    # next 6, then settled. No provisional sample may enter the accepted window.
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, None)
    attached = {}

    def attach(phase):
        attached.setdefault(phase, fake.frame)

    def pivot():
        value = list(fake.camera_tracking_base_offset)
        if 0 in attached and 1 not in attached and attached[0] + 4 <= fake.frame < attached[0] + 10:
            value[1] = 10
        return value

    monkeypatch.setattr(fake, '_attach_camera_follow', attach)
    monkeypatch.setattr(fake, '_camera_pivot', pivot)
    baseline = []
    asyncio.run(OracleSession(cfg, fake).restore_controls(original, baseline_observations=baseline))
    provisional = [row for row in baseline if 'scene' in row and follow_pivot(row['scene'])[1] == 10]
    assert provisional and not any(row['accepted'] for row in provisional)
    assert all(row['error'].startswith('Restoration mismatch: camera') for row in provisional)
    first = baseline.index(provisional[0])
    assert any(row['accepted'] for row in baseline[:first])
    assert fake.camera_follow_offset == pytest.approx([0, 0, 0])
    assert fake.calls.count('commit_scene_control') == 1


def test_reference_with_a_nonzero_follow_offset_gates_on_delta_minus_offset(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed_without_settle(cfg, offset=[0, .4, 0], settle=(LATE, 0))
    assert original['camera_follow_center_delta'] == pytest.approx([0, 11.3, 0])
    assert follow_pivot(original) == pytest.approx(PIVOT)
    baseline = []
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(original, baseline_observations=baseline))
    accepted = [row for row in baseline if row['accepted']]
    assert accepted and all(follow_pivot(row['scene']) == pytest.approx(PIVOT) for row in accepted)
    assert any('camera follow pivot' in row.get('error', '') for row in baseline)
    assert result['reference_follow_pivot'] == pytest.approx(PIVOT)
    assert fake.camera_follow_offset == pytest.approx([0, .4, 0])
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    assert fake.calls.count('commit_scene_control') == 1


def test_old_journal_without_a_pivot_stays_pending(tmp_path, monkeypatch):
    # A journal armed before probe 0.9.5 has no pivot: it is refused before any
    # camera mutation and stays pending for a manual decision.
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake, original = followed(cfg, None)
    for key in ('camera_follow_offset', 'camera_follow_position', 'camera_follow_center_delta'):
        del original[key]
    path = write_guard(cfg, original)
    with pytest.raises(ScenarioError, match='follow pivot of the reference controls'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert not {'prepare_scene_control', 'commit_scene_control'} & set(fake.calls)
    pending = json.loads(path.read_text(encoding='utf-8'))
    assert pending['restore_required'] is True
    assert 'follow pivot of the reference controls' in pending['recovery_attempt']['error']
