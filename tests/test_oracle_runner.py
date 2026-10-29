"""Scenario integration and failure tests against an in-process synthetic probe."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_probe import FakeProbe, sample_state
from oracle_runner import (OracleSession, ScenarioError, check_controls, execute_scenario,
                           control_params,
                           restore_interrupted_scenario, run_scenario_file,
                           scenario_lock, variability, wait_stable_controls)
from oracle_schema import canonical_bytes, load_state
from probe import ProbeError


def config(tmp_path):
    return dict(runtime=str(tmp_path / 'runtime'), runs=str(tmp_path / 'runs'),
                oracle_output=str(tmp_path / 'probe-output'), load_timeout=.5,
                run_until_timeout=.5, scenario_timeout=10)


def scenario():
    return dict(schema_version='0.1', name='synthetic-run', save='Synthetic save',
                speed=1, repeat=3, actions=[],
                checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])


def test_variability_distinguishes_relation_pairs_with_separator_in_opaque_ids(tmp_path):
    executions = []
    for index, value in enumerate((1, 9), 1):
        state = sample_state()
        state['relations'] = [dict(source_id='a->b', target_id='c', value=value),
                              dict(source_id='a', target_id='b->c', value=2)]
        path = tmp_path / (str(index) + '.json')
        path.write_bytes(canonical_bytes(state))
        executions.append(dict(execution=index, status='completed',
                               checkpoints=[dict(name='relations', path=str(path))]))
    result = variability(executions)['relations']
    assert result['repeatability_evaluated'] and result['variable_field_count'] == 1
    variation = result['variable_fields'][0]
    assert variation['path'].endswith('/value')
    assert [row['value'] for row in variation['observations']] == [1, 9]


def report_for(cfg):
    reports = list(Path(cfg['runs']).glob('*/*/report.json'))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding='utf-8'))


def guard_for(cfg):
    return json.loads((Path(cfg['runtime']) / 'oracle-restoration.json').read_text(encoding='utf-8'))


def stability_clock(monkeypatch):
    """Advance only the orchestrator's polling time, without a real-game client."""
    clock = SimpleNamespace(value=0.0)
    original_sleep = asyncio.sleep

    async def advance(seconds):
        clock.value += seconds
        await original_sleep(0)

    monkeypatch.setattr('oracle_runner.time', SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr('oracle_runner.asyncio.sleep', advance)
    return clock


def test_three_repetitions_reload_each_time_and_restore_controls_and_source(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    initial_source = deepcopy(fake.initial_state)
    fake.camera_center = [30, 40, 50]
    fake.camera_zoom = 82
    fake.camera_orientation = [.5, .5, .5, .5]
    fake.free_camera = True
    fake.edge_scrolling = False
    fake.state['clock'].update(speed=0, paused=True)
    fake.selected_speed = 2
    value = scenario()
    source = tmp_path / 'scenario.json'
    source.write_text(json.dumps(value, indent=4) + '\n', encoding='utf-8')
    source_bytes = source.read_bytes()
    result = asyncio.run(run_scenario_file(source, cfg, client=fake))
    report = report_for(cfg)
    assert result['status'] == report['status'] == 'completed'
    assert result['executions'] == 3 and result['restored'] is True
    assert fake.loads == ['Synthetic save'] * 4  # Each repetition, then cleanup.
    assert len(report['executions']) == 3
    for index, execution in enumerate(report['executions'], 1):
        assert execution['execution'] == index and execution['status'] == 'completed'
        assert execution['initial_clock']['elapsed_seconds'] == initial_source['clock']['elapsed_seconds']
        assert len(execution['checkpoints']) == 2
        for capture in execution['checkpoints']:
            target = Path(capture['path'])
            assert target.parent.name == str(index)
            payload = target.read_bytes()
            assert canonical_bytes(load_state(target)) == payload
            assert hashlib.sha256(payload).hexdigest() == capture['sha256']
            assert capture['bytes'] == len(payload)
            assert Path(capture['source_path']).read_bytes() == payload
            assert capture['actual_at'] == capture['requested_at']
    assert source.read_bytes() == source_bytes
    assert fake.initial_state == initial_source
    assert fake.camera_center == [30, 40, 50] and fake.camera_zoom == 82
    assert fake.camera_orientation == [.5, .5, .5, .5]
    assert fake.free_camera is True and fake.edge_scrolling is False
    assert fake.camera_owned is False
    assert fake.state['clock']['speed'] == 0 and fake.state['clock']['paused'] is True
    assert guard_for(cfg)['restore_required'] is False
    assert report['restoration']['verified'] is True
    for point in ('initial', 'later'):
        captures = [Path(execution['checkpoints'][0 if point == 'initial' else 1]['path']).read_bytes()
                    for execution in report['executions']]
        assert len(set(captures)) == 1
        assert report['variability'][point]['variable_field_count'] == 0
        assert report['variability'][point]['repeatability_evaluated'] is True


def test_actions_keep_declared_order_and_precede_same_time_checkpoint(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    value = scenario()
    value['repeat'] = 1
    actor = fake.state['characters'][0]['id']
    value['actions'] = [
        dict(at=0, command='issue_order', params=dict(type='move', character_id=actor, position=[10, 0, 20])),
        dict(at=0, command='issue_order', params=dict(type='move', character_id=actor, position=[30, 0, 40])),
        dict(at=0, command='pause', params=dict(paused=True)),
        dict(at=0, command='pause', params=dict(paused=False)),
        dict(at=2, command='pause', params=dict(paused=True))]
    asyncio.run(execute_scenario(value, cfg, client=fake))
    execution = report_for(cfg)['executions'][0]
    first, later = [load_state(capture['path']) for capture in execution['checkpoints']]
    first_actor = next(row for row in first['characters'] if row['id'] == actor)
    later_actor = next(row for row in later['characters'] if row['id'] == actor)
    assert first_actor['order']['position'] == [30, 0, 40]
    assert first_actor['position'] == [0, 0, 0]
    assert later_actor['position'] == [30, 0, 40]
    assert first['clock']['paused'] is True and later['clock']['paused'] is True
    assert [entry['request'] for entry in execution['actions']] == value['actions']
    first_dump = fake.calls.index('dump_state')
    assert fake.calls[:first_dump].count('issue_order') == 2


def test_variability_reports_changed_value_and_missing_entity_by_stable_id(tmp_path):
    executions = []
    for index in (1, 2, 3):
        state = sample_state()
        state['characters'][0]['health'][0]['current'] = 100 if index == 1 else 90
        if index == 3:
            removed = state['characters'].pop()['id']
            state['squads'][0]['members'].remove(removed)
        path = tmp_path / f'{index}.json'
        path.write_bytes(canonical_bytes(state))
        executions.append(dict(execution=index, status='completed',
                               checkpoints=[dict(name='same', path=str(path))]))
    executions.append(dict(execution=4, status='failed', checkpoints=[]))
    result = variability(executions)['same']
    assert result['executions'] == 3 and result['repeatability_evaluated'] is True
    fields = {row['path']: row['observations'] for row in result['variable_fields']}
    first, second = [row['id'] for row in sample_state()['characters']]
    changed = fields[f'/characters/{first}/health/fixture-head:neither/current']
    assert [row['value'] for row in changed] == [100, 90, 90]
    missing = fields[f'/characters/{second}/name']
    assert [row['present'] for row in missing] == [True, True, False]
    assert 'value' not in missing[-1]
    assert '/schema_version' in result['stable_paths']


@pytest.mark.parametrize('mode', ['run_timeout', 'run_stalled'])
def test_native_or_client_timeout_cancels_operation_and_restores(tmp_path, mode):
    cfg = config(tmp_path)
    cfg['run_until_timeout'] = .1
    fake = FakeProbe(cfg['oracle_output'], mode=mode)
    value = scenario()
    value['repeat'] = 1
    with pytest.raises(ScenarioError, match='timed_out|deadline'):
        asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['status'] == report['executions'][0]['status'] == 'failed'
    assert 'cancel_run_until' in fake.calls
    assert all(operation['status'] != 'running' for operation in fake.operations.values())
    assert fake.loads == ['Synthetic save', 'Synthetic save']
    assert fake.state['clock']['paused'] is True and fake.camera_owned is False
    assert report['restoration']['verified'] is True
    assert guard_for(cfg)['restore_required'] is False


def test_invalid_snapshot_never_creates_successful_checkpoint(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'], mode='invalid_state')
    with pytest.raises(ScenarioError, match='required property'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    report = report_for(cfg)
    assert report['status'] == 'failed' and report['variability'] == {}
    assert report['executions'][0]['checkpoints'] == []
    assert not list(Path(cfg['runs']).glob('*/*/1/initial.json'))
    assert report['restoration']['verified'] is True
    assert guard_for(cfg)['restore_required'] is False


class RestartingProbe(FakeProbe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.restarted = False
        self.after_restart = []

    async def call(self, command, **params):
        if self.restarted:
            self.after_restart.append(command)
        result = await super().call(command, **params)
        if command == 'run_until':
            self.restarted = True
        if command == 'ping' and self.restarted:
            result['instance_id'] = 'another-game-instance'
        return result


def test_game_restart_rejects_execution_and_leaves_restoration_guard(tmp_path):
    cfg = config(tmp_path)
    fake = RestartingProbe(cfg['oracle_output'])
    value = scenario()
    value['repeat'] = 1
    with pytest.raises(ScenarioError, match='restarted'):
        asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['status'] == 'failed'
    assert report['executions'][0]['status'] == 'failed'
    assert 'restarted' in report['restoration_error']
    assert guard_for(cfg)['restore_required'] is True
    assert len(fake.loads) == 1
    assert 'commit_scene_control' not in fake.after_restart


def test_restart_never_cancels_old_operation_on_new_game_instance(tmp_path):
    cfg = config(tmp_path)
    fake = RestartingProbe(cfg['oracle_output'])
    session = OracleSession(cfg, fake)
    async def run():
        await session.ping()
        with pytest.raises(ScenarioError, match='restarted'):
            await session.until(fake.state['clock']['elapsed_seconds'] + 2)
    asyncio.run(run())
    assert 'cancel_run_until' not in fake.after_restart


def test_pending_guard_refuses_next_scenario_before_any_probe_call(tmp_path):
    cfg = config(tmp_path)
    Path(cfg['runtime']).mkdir()
    (Path(cfg['runtime']) / 'oracle-restoration.json').write_text('{"restore_required":true}', encoding='utf-8')
    fake = FakeProbe(cfg['oracle_output'])
    with pytest.raises(ScenarioError, match='requires restoration'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert fake.calls == [] and not Path(cfg['runs']).exists()


def test_os_lock_excludes_concurrent_scenarios_and_releases_after_exit(tmp_path):
    cfg = config(tmp_path)
    with scenario_lock(cfg['runtime']):
        with pytest.raises(ScenarioError, match='Another scenario'):
            with scenario_lock(cfg['runtime']):
                pytest.fail('Lock unexpectedly acquired twice')
    with scenario_lock(cfg['runtime']):
        pass


def test_concurrent_execute_is_rejected_without_reaching_second_probe(tmp_path):
    cfg = config(tmp_path)
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        class BlockingProbe(FakeProbe):
            async def call(self, command, **params):
                if command == 'load_save' and not self.loads:
                    entered.set()
                    await release.wait()
                return await super().call(command, **params)
        first = BlockingProbe(cfg['oracle_output'])
        second = FakeProbe(cfg['oracle_output'])
        value = scenario()
        value['repeat'] = 1
        pending = asyncio.create_task(execute_scenario(value, cfg, client=first))
        await asyncio.wait_for(entered.wait(), 1)
        try:
            with pytest.raises(ScenarioError, match='Another scenario'):
                await execute_scenario(value, cfg, client=second)
            assert second.calls == []
        finally:
            release.set()
            result = await pending
        assert result['status'] == 'completed'
    asyncio.run(run())


def test_snapshot_path_escape_is_rejected_before_reading_external_file(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    class OutsideProbe(FakeProbe):
        async def call(self, command, **params):
            if command == 'dump_state':
                return dict(path=str(tmp_path / 'outside' / params['filename']))
            return await super().call(command, **params)
    fake = OutsideProbe(cfg['oracle_output'])
    def forbidden_read(path):
        pytest.fail('Snapshot reader was called outside configured output directory')
    monkeypatch.setattr('oracle_runner.load_state', forbidden_read)
    with pytest.raises(ScenarioError, match='outside the configured'):
        asyncio.run(OracleSession(cfg, fake).dump())
    assert not Path(cfg['runs']).exists()


def test_snapshot_wrong_filename_is_rejected_without_reading(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    existing = Path(cfg['oracle_output']) / 'existing.json'
    existing.write_bytes(canonical_bytes(sample_state()))
    original = existing.read_bytes()
    class WrongName:
        async def call(self, command, **params):
            return dict(path=str(existing))
    monkeypatch.setattr('oracle_runner.load_state', lambda _: pytest.fail('Unexpected filename was read'))
    with pytest.raises(ScenarioError, match='unexpected name'):
        asyncio.run(OracleSession(cfg, WrongName()).dump())
    assert existing.read_bytes() == original


def test_initial_zero_speed_with_immediate_resume_is_valid_for_native_contract(tmp_path):
    cfg = config(tmp_path)
    class NativeSpeedProbe(FakeProbe):
        async def call(self, command, **params):
            if command == 'set_game_speed' and params.get('preserve_pause') and params.get('speed') == 0:
                raise ProbeError('invalid_request: preserve_pause requires positive speed')
            return await super().call(command, **params)
    fake = NativeSpeedProbe(cfg['oracle_output'])
    value = scenario()
    value.update(speed=0, repeat=1,
                 actions=[dict(at=0, command='set_game_speed', params=dict(speed=1))])
    result = asyncio.run(execute_scenario(value, cfg, client=fake))
    assert result['status'] == 'completed'


def test_restoration_verification_rejects_changed_zoom():
    original = dict(free_camera=False, edge_scrolling=True, paused=True,
                    camera_center=[0, 0, 0], camera_position=[0, 0, 0],
                    camera_orientation=[1, 0, 0, 0], camera_zoom=-20,
                    selected_game_speed=1, scene_camera_control_owned=False)
    changed = dict(original, camera_zoom=-80)
    with pytest.raises(ScenarioError, match='zoom'):
        check_controls(original, changed)


@pytest.mark.parametrize('field,value', [
    ('camera_center', [float('nan'), 0, 0]),
    ('camera_center', None),
    ('camera_center', 0),
    ('camera_position', [0, 0]),
    ('camera_position', [0, None, 0]),
    ('camera_orientation', [1, 0, 0]),
    ('camera_orientation', [1, 0, float('inf'), 0]),
    ('selected_game_speed', None),
    ('selected_game_speed', float('nan')),
    ('selected_game_speed', True),
    ('camera_zoom', None),
    ('camera_zoom', float('inf')),
])
def test_restoration_verification_rejects_unverifiable_numeric_controls(field, value):
    original = dict(free_camera=False, edge_scrolling=True, paused=True,
                    camera_center=[0, 0, 0], camera_position=[0, 0, 0],
                    camera_orientation=[1, 0, 0, 0], camera_zoom=-20,
                    selected_game_speed=1, scene_camera_control_owned=False)
    changed = dict(original, **{field: value})
    with pytest.raises(ScenarioError, match=field if field != 'selected_game_speed' else 'selected game speed'):
        check_controls(original, changed)


@pytest.mark.parametrize('recovery_save', [None, 'Original controls save'])
def test_explicit_recovery_restores_guard_controls_after_game_restart(tmp_path, recovery_save):
    cfg = config(tmp_path)
    guard_path = Path(cfg['runtime']) / 'oracle-restoration.json'
    before = None
    class GuardCheckingProbe(FakeProbe):
        async def call(self, command, **params):
            if before is not None:
                assert guard_path.read_bytes() == before
            return await super().call(command, **params)
    fake = GuardCheckingProbe(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    original.update(camera_center=[10, 20, 30], camera_position=[10, 20, 30],
                    camera_zoom=80, selected_game_speed=2,
                    free_camera=True, edge_scrolling=False, paused=True)
    Path(cfg['runtime']).mkdir()
    guard = dict(restore_required=True, save='Synthetic save', controls=original,
                 instance_id='old-crashed-instance', run='historical-invalid-run')
    guard_path.write_text(json.dumps(guard), encoding='utf-8')
    before = guard_path.read_bytes()
    result = asyncio.run(restore_interrupted_scenario(cfg, client=fake, save=recovery_save))
    expected_save = recovery_save or 'Synthetic save'
    assert result['restored'] is True and fake.loads == [expected_save]
    assert result['save'] == result['recovery_save'] == expected_save
    assert fake.camera_center == [10, 20, 30] and fake.camera_zoom == 80
    assert fake.free_camera is True and fake.edge_scrolling is False
    assert fake.state['clock']['paused'] is True and fake.state['clock']['speed'] == 0
    assert fake.selected_speed == 2
    recovered = guard_for(cfg)
    assert recovered['restore_required'] is False
    assert recovered['instance_id'] == 'old-crashed-instance'
    assert recovered['recovery_instance_id'] == 'fake-instance'
    assert recovered['save'] == 'Synthetic save'
    assert recovered['recovery_save'] == expected_save
    assert recovered['controls'] == original
    assert recovered['recovered_at']
    assert recovered['run'] == 'historical-invalid-run'
    assert 'run_until' not in fake.calls and 'issue_order' not in fake.calls


@pytest.mark.parametrize('record,reason', [(None, 'no_restoration_record'),
                                         ({'restore_required': False}, 'already_restored')])
def test_explicit_recovery_noop_does_not_contact_probe(tmp_path, record, reason):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    if record is not None:
        Path(cfg['runtime']).mkdir()
        (Path(cfg['runtime']) / 'oracle-restoration.json').write_text(json.dumps(record), encoding='utf-8')
    assert asyncio.run(restore_interrupted_scenario(cfg, client=fake)) == dict(restored=False, reason=reason)
    assert fake.calls == []


@pytest.mark.parametrize('recovery_save', [None, 'Original controls save'])
def test_failed_explicit_recovery_preserves_pending_guard(tmp_path, recovery_save, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    class WrongRestoreProbe(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'commit_scene_control':
                self.camera_zoom += 10
            return result
    fake = WrongRestoreProbe(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    Path(cfg['runtime']).mkdir()
    guard = dict(restore_required=True, save='Synthetic save', controls=original,
                 instance_id='old-instance')
    path = Path(cfg['runtime']) / 'oracle-restoration.json'
    path.write_text(json.dumps(guard), encoding='utf-8')
    with pytest.raises(ScenarioError, match='zoom'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake, save=recovery_save))
    pending = guard_for(cfg)
    assert pending['restore_required'] is True
    assert all(pending[key] == value for key, value in guard.items())
    assert pending['recovery_attempt']['error']
    assert pending['recovery_attempt']['observations']
    assert fake.loads == [recovery_save or 'Synthetic save']
    assert fake.calls.count('commit_scene_control') == 1


@pytest.mark.parametrize('invalid_save', ['', '../source', 'a\\b', 'a:b', 'a\n',
                                         'a\0', 'é' * 65, 123, False])
def test_explicit_recovery_rejects_invalid_override_before_probe_or_record_change(tmp_path, invalid_save):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    Path(cfg['runtime']).mkdir()
    path = Path(cfg['runtime']) / 'oracle-restoration.json'
    before = b'{"restore_required":true,"save":"Original save","controls":{}}'
    path.write_bytes(before)
    with pytest.raises(ValueError, match='Invalid save name'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake, save=invalid_save))
    assert fake.calls == []
    assert path.read_bytes() == before


@pytest.mark.parametrize('slow_command', ['dump_state', 'issue_order'])
def test_global_deadline_interrupts_last_group_and_still_restores(tmp_path, slow_command):
    cfg = config(tmp_path)
    cfg['scenario_timeout'] = .1
    class SlowLastGroupProbe(FakeProbe):
        started_slow_call = False
        cancelled_slow_call = False

        async def call(self, command, **params):
            if command == slow_command:
                self.started_slow_call = True
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    self.cancelled_slow_call = True
                    raise
            return await super().call(command, **params)
    fake = SlowLastGroupProbe(cfg['oracle_output'])
    value = scenario()
    value.update(repeat=1, checkpoints=[dict(at=0, name='only')])
    if slow_command == 'issue_order':
        value['actions'] = [dict(at=0, command='issue_order', params=dict(
            type='move', character_id=fake.state['characters'][0]['id'], position=[10, 0, 20]))]
    with pytest.raises(ScenarioError, match='scenario_timeout during ' + slow_command):
        asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert fake.started_slow_call and fake.cancelled_slow_call
    assert report['status'] == report['executions'][0]['status'] == 'failed'
    assert report['executions'][0]['checkpoints'] == []
    assert report['restoration']['verified'] is True
    assert guard_for(cfg)['restore_required'] is False
    assert fake.loads == ['Synthetic save', 'Synthetic save']
    assert fake.camera_owned is False and fake.state['clock']['paused'] is True


def test_timeout_error_survives_failed_cancellation_and_cleanup_is_attempted(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'], mode='run_timeout')
    fake.failures['cancel_run_until'] = 'synthetic cancellation transport failure'
    value = scenario()
    value['repeat'] = 1
    with pytest.raises(ScenarioError, match='run_until ended with status timed_out') as caught:
        asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['error'] == 'ScenarioError: run_until ended with status timed_out'
    assert report['cancellation_error'] == 'synthetic cancellation transport failure'
    assert any('Cancellation also failed: synthetic cancellation transport failure' in note
               for note in caught.value.__cause__.__notes__)
    assert report['status'] == 'failed' and report['restoration']['verified'] is True
    assert fake.calls.count('cancel_run_until') == 2
    assert fake.loads == ['Synthetic save', 'Synthetic save']
    assert guard_for(cfg)['restore_required'] is False


def test_unknown_selected_speed_refuses_scenario_before_mutation_or_guard(tmp_path):
    cfg = config(tmp_path)
    class UnknownSelectionProbe(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state':
                result['selected_game_speed'] = None
            return result
    fake = UnknownSelectionProbe(cfg['oracle_output'])
    with pytest.raises(ScenarioError, match='complete camera/time controls'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert set(fake.calls) <= {'ping', 'get_scene_state'}
    assert fake.calls.count('get_scene_state') == 1
    assert fake.loads == []
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()
    assert report_for(cfg)['status'] == 'failed'


def test_unpaused_reference_is_rejected_before_any_mutation_or_guard(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    fake.state['clock'].update(paused=False, speed=1)
    with pytest.raises(ScenarioError, match='pause'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert set(fake.calls) <= {'ping', 'get_scene_state'}
    assert not fake.loads
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()


def test_stable_capture_requires_elapsed_time_and_distinct_scene_frames(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    observations = []
    result = asyncio.run(wait_stable_controls(OracleSession(cfg, fake), observations=observations))
    scenes = [row['scene'] for row in observations if 'scene' in row]
    assert clock.value >= .5
    assert len({row['frame'] for row in scenes}) >= 3
    assert result == scenes[-1]
    assert set(fake.calls) == {'ping', 'get_scene_state'}


def test_stable_capture_cannot_count_repeated_reads_of_one_frame(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class FrozenFrameProbe(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state':
                result['frame'] = 7
            return result

    fake = FrozenFrameProbe(cfg['oracle_output'])
    with pytest.raises(ScenarioError):
        asyncio.run(wait_stable_controls(OracleSession(cfg, fake), timeout=.8))
    assert .8 <= clock.value < 1.0
    assert fake.calls.count('get_scene_state') >= 3
    assert set(fake.calls) == {'ping', 'get_scene_state'}


def test_world_unavailable_resets_the_stability_interval(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class TransientUnavailableProbe(FakeProbe):
        scene_reads = 0
        unavailable_at = None

        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state':
                self.scene_reads += 1
                if self.scene_reads == 3:
                    self.unavailable_at = clock.value
                    raise ProbeError('invalid_request: world not ready')
            return result

    fake = TransientUnavailableProbe(cfg['oracle_output'])
    observations = []
    asyncio.run(wait_stable_controls(OracleSession(cfg, fake), observations=observations, timeout=2))
    assert clock.value - fake.unavailable_at >= .5
    assert any('world not ready' in row.get('error', '') for row in observations)
    assert set(fake.calls) == {'ping', 'get_scene_state'}


def test_initial_capture_tracks_the_last_stable_pose_before_arming_guard(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    guard_path = Path(cfg['runtime']) / 'oracle-restoration.json'

    class MovingReferenceProbe(FakeProbe):
        scene_reads = 0

        async def call(self, command, **params):
            if command == 'get_scene_state' and not self.loads:
                assert not guard_path.exists()
                self.scene_reads += 1
                self.camera_center = [min(self.scene_reads, 3), 0, 0]
            return await super().call(command, **params)

    fake = MovingReferenceProbe(cfg['oracle_output'])
    value = scenario()
    value.update(repeat=1, checkpoints=[dict(at=0, name='only')])
    asyncio.run(execute_scenario(value, cfg, client=fake))
    guard = guard_for(cfg)
    report = report_for(cfg)
    assert guard['controls']['camera_center'] == [3, 0, 0]
    assert report['control_capture_observations']
    assert fake.scene_reads >= 3
    assert report['restoration']['verified'] is True


def test_instance_change_during_initial_capture_never_arms_guard_or_mutates(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class RestartDuringCaptureProbe(FakeProbe):
        pings = 0

        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'ping':
                self.pings += 1
                if self.pings >= 3:
                    result['instance_id'] = 'replacement-instance'
            return result

    fake = RestartDuringCaptureProbe(cfg['oracle_output'])
    with pytest.raises(ScenarioError, match='restarted'):
        asyncio.run(execute_scenario(scenario(), cfg, client=fake))
    assert set(fake.calls) <= {'ping', 'get_scene_state'}
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()


def test_restoration_waits_out_transient_pose_and_readiness_without_mutation_retry(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class SettlingRestoreProbe(FakeProbe):
        restoring = False
        restored_reads = 0
        last_unstable_at = None

        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'commit_scene_control':
                self.restoring = True
            if command == 'get_scene_state' and self.restoring:
                self.restored_reads += 1
                if self.restored_reads <= 2:
                    result['camera_center'][1] -= 4.8
                    result['camera_position'][1] -= 4.8
                    self.last_unstable_at = clock.value
                elif self.restored_reads == 3:
                    self.last_unstable_at = clock.value
                    raise ProbeError('invalid_request: world not ready')
            return result

    fake = SettlingRestoreProbe(cfg['oracle_output'])
    value = scenario()
    value.update(repeat=1, checkpoints=[dict(at=0, name='only')])
    asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['restoration']['verified'] is True
    assert clock.value - fake.last_unstable_at >= .5
    assert fake.calls.count('commit_scene_control') == 1
    assert fake.loads == ['Synthetic save', 'Synthetic save']
    rows = report['restoration']['observations']
    assert any('world not ready' in row.get('error', '') for row in rows)
    assert any(row.get('scene', {}).get('camera_center', [0, 0, 0])[1] == -4.8 for row in rows)
    assert guard_for(cfg)['restore_required'] is False


def test_stable_but_wrong_restoration_times_out_and_keeps_guard(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class WrongRestoreProbe(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'commit_scene_control':
                self.camera_center[0] += .2
            return result

    fake = WrongRestoreProbe(cfg['oracle_output'])
    value = scenario()
    value.update(repeat=1, checkpoints=[dict(at=0, name='only')])
    with pytest.raises(ScenarioError, match='camera_center'):
        asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['status'] == 'failed'
    assert report['restoration']['verified'] is False
    assert report['restoration']['observations']
    assert guard_for(cfg)['restore_required'] is True
    assert fake.calls.count('commit_scene_control') == 1
    assert fake.loads == ['Synthetic save', 'Synthetic save']


def test_stability_poll_does_not_retry_transport_failure(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    fake.failures['get_scene_state'] = 'synthetic transport failure'
    with pytest.raises(ProbeError, match='transport failure'):
        asyncio.run(wait_stable_controls(OracleSession(cfg, fake)))
    assert fake.calls.count('get_scene_state') == 1


def test_two_phase_restore_measures_settled_tracking_baseline_without_moving_actor(tmp_path, monkeypatch):
    clock = stability_clock(monkeypatch)
    monkeypatch.setattr('fake_probe.time', SimpleNamespace(monotonic=lambda: clock.value))
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'], camera_tracking_base_offset=[0, 9.8, 0],
                     camera_move_duration=.2)
    fake.camera_follow_id = fake.state['characters'][0]['id']
    fake._camera_tracking_active = True
    original = asyncio.run(fake.call('get_scene_state'))
    unchanged = deepcopy(original)
    fake.state['characters'][0]['position'][1] = .936
    baseline, post = [], []
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(
        original, baseline_observations=baseline, observations=post))
    assert original == unchanged
    assert fake.state['characters'][0]['position'][1] == .936
    assert fake.camera_follow_offset[1] == pytest.approx(-.936)
    assert result['scene']['camera_center'] == pytest.approx(original['camera_center'])
    assert result['pose_verified_in_pause'] and not result['unpaused_after_verification']
    assert baseline[-1]['stable_seconds'] >= .5 and baseline[-1]['distinct_frames'] >= 3
    assert post[-1]['stable_seconds'] >= .5 and post[-1]['distinct_frames'] >= 3
    assert all(row['scene']['scene_camera_control_owned'] for row in baseline if row.get('accepted'))
    assert all(not row['scene']['scene_camera_control_owned'] for row in post if row.get('accepted'))
    assert fake.calls.count('prepare_scene_control') == fake.calls.count('commit_scene_control') == 1
    assert 'restore_scene_control' not in fake.calls


@pytest.mark.parametrize('key,value', [('scene_camera_control_owned', False),
                                     ('edge_scrolling', True),
                                     ('camera_restore_token', 'another-token'),
                                     ('paused', False)])
def test_lost_held_baseline_never_commits_or_retries_preparation(tmp_path, monkeypatch, key, value):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class LostHold(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state' and self._camera_pending is not None:
                result[key] = value
            return result

    fake = LostHold(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    with pytest.raises(ScenarioError, match='hold|pause'):
        asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert fake.calls.count('prepare_scene_control') == 1
    assert 'commit_scene_control' not in fake.calls
    assert fake._camera_pending is not None


@pytest.mark.parametrize('key,value', [('camera_orientation', [0, 1, 0, 0]),
                                     ('camera_zoom', -25), ('free_camera', True),
                                     ('camera_follow_id', None), ('selected_game_speed', 2)])
def test_stable_but_wrong_held_settings_cannot_be_committed(tmp_path, monkeypatch, key, value):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class WrongHeldSetting(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state' and self._camera_pending is not None:
                result[key] = value
            return result

    fake = WrongHeldSetting(cfg['oracle_output'])
    fake.camera_follow_id = fake.state['characters'][0]['id']
    original = asyncio.run(fake.call('get_scene_state'))
    with pytest.raises(ScenarioError, match='Restoration mismatch'):
        asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert fake.calls.count('prepare_scene_control') == 1
    assert 'commit_scene_control' not in fake.calls


def test_direct_restore_derives_eye_from_observed_rig_without_guessing_height(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class BoomProbe(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'get_scene_state':
                result['camera_position'] = [result['camera_center'][0]+3,
                                             result['camera_center'][1]+4,
                                             result['camera_center'][2]+12]
            return result

    fake = BoomProbe(cfg['oracle_output'])
    requested = control_params(asyncio.run(fake.call('get_scene_state')))
    requested['camera_center'] = [20, 30, 40]
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(params=requested))
    assert result['scene']['camera_position'] == [23, 34, 52]
    assert result['scene']['camera_center'] == [20, 30, 40]
    assert result['pose_verified_in_pause']


def test_restore_verifies_pose_in_pause_then_resumes_without_claiming_frozen_pose(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class ResumeMovesCamera(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'pause' and params['paused'] is False:
                self.camera_center[0] += 100
            return result

    fake = ResumeMovesCamera(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    original['paused'] = False
    fake.state['clock']['paused'] = False
    result = asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert result['pose_verified_in_pause'] and result['unpaused_after_verification']
    assert result['verified_paused_scene']['camera_center'] == original['camera_center']
    assert result['scene']['camera_center'][0] == original['camera_center'][0]+100
    assert result['scene']['paused'] is False and not fake.camera_owned
    pauses = [row['params']['paused'] for row in fake.requests if row['command'] == 'pause']
    assert pauses == [True, False]
    prepared = next(row for row in fake.requests if row['command'] == 'prepare_scene_control')
    assert prepared['params']['paused'] is True
    commit = fake.calls.index('commit_scene_control')
    resume = next(i for i, row in enumerate(fake.requests)
                  if row['command'] == 'pause' and row['params']['paused'] is False)
    assert fake.calls[commit:resume].count('get_scene_state') >= 3


def test_restart_during_held_baseline_cannot_commit_to_replacement_process(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class RestartInHold(FakeProbe):
        async def call(self, command, **params):
            if command == 'ping' and self._camera_pending is not None:
                self.instance_id = 'replacement-game'
            return await super().call(command, **params)

    fake = RestartInHold(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    with pytest.raises(ScenarioError, match='restarted'):
        asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert fake.calls.count('prepare_scene_control') == 1
    assert 'commit_scene_control' not in fake.calls


def test_uncertain_commit_is_not_retried(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class LostCommitResponse(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'commit_scene_control':
                raise ProbeError('commit response lost after application')
            return result

    fake = LostCommitResponse(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    with pytest.raises(ProbeError, match='response lost'):
        asyncio.run(OracleSession(cfg, fake).restore_controls(original))
    assert fake.calls.count('prepare_scene_control') == fake.calls.count('commit_scene_control') == 1


def test_failed_discrete_check_after_resume_preserves_recovery_guard(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)

    class ResumeChangesZoom(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'pause' and params['paused'] is False:
                self.camera_zoom -= 1
            return result

    fake = ResumeChangesZoom(cfg['oracle_output'])
    original = asyncio.run(fake.call('get_scene_state'))
    original['paused'] = False
    Path(cfg['runtime']).mkdir()
    path = Path(cfg['runtime'])/'oracle-restoration.json'
    path.write_text(json.dumps(dict(restore_required=True, save='Synthetic save',
                                   controls=original, instance_id='old-instance')))
    with pytest.raises(ScenarioError, match='camera_zoom'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert guard_for(cfg)['restore_required'] is True
    attempt = guard_for(cfg)['recovery_attempt']
    assert attempt['baseline_observations'] and attempt['observations']
    assert 'camera_zoom' in attempt['error']
    assert fake.calls.count('prepare_scene_control') == fake.calls.count('commit_scene_control') == 1
