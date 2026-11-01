"""Scenario integration and failure tests against an in-process synthetic probe."""
import asyncio
from copy import deepcopy
import hashlib
import json
import re
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
    assert report['report_format'] == '0.1' and report['scenario_schema'] == '0.1'
    assert report['state_schema'] == fake.state['schema_version'] and 'schema_version' not in report
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


# Scene setup (docs/scene-setup.md, Runner steps) -------------------------------

SETUP_SAVE = 'oracle-base-nature'  # Pins exist for this save name only (Q5).
PLAYER_POSITION = [100, 7.25, 200]
SETTINGS_LINE = 'Squad size multiplier=1'
MEMBER_ALIASES = ['raiders/fixture-leader/1', 'raiders/fixture-member/1',
                  'raiders/fixture-member/2', 'raiders/fixture-member/3']
SETUP_MUTATIONS = ('setup_spawn_squad', 'setup_heal', 'setup_set_relation')


class SetupProbe(FakeProbe):
    """The W3 fake with per-command hooks that alter the synthetic world or a reply."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hooks = {}
        self.advance_hook = None

    async def call(self, command, **params):
        result = await super().call(command, **params)
        hook = self.hooks.get(command)
        return result if hook is None else (hook(self, params, result) or result)

    def _advance(self, seconds):
        super()._advance(seconds)
        if self.advance_hook is not None:
            self.advance_hook(self)

    def spawned(self):
        return [row for row in self.state['characters'] if row['id'].startswith('local:fake-spawn:')]


def squad_facts(line=SETTINGS_LINE):
    raw = line.encode('utf-8')
    return dict(squad_size=dict(source='engine_facts', multiplier=float(line.partition('=')[2]), line=line,
                                sha256=hashlib.sha256(raw).hexdigest(), path='settings.cfg'))


def setup_fixture(tmp_path, *, y_after=7.25, fingerprint=None, save=SETUP_SAVE):
    from oracle_origins import read_saved_origins
    from test_oracle_origins import handle, record, write_source
    root = tmp_path / 'synthetic-saves'
    root.mkdir()
    records = [record(30, 'collection', instances=[(f'instance-{index}', [f'character-{index}'])
                                                   for index in range(2)])]
    records += [record(36, f'character-{index}', int=handle(slot=index + 1, object_serial=1000 + index))
                for index in range(2)]
    write_source(root, platoons={'synthetic.platoon': records}, name=save)
    manifest = read_saved_origins(root, save)
    saved = [row['saved_id'] for row in manifest['characters'][:2]] + [manifest['squads'][0]['saved_id']]
    raw = ['char:player', 'char:bystander', 'squad:player']
    state = sample_state()
    for index, character in enumerate(state['characters']):
        character.update(id=raw[index], squad_id=raw[2])
    state['characters'][0]['position'] = list(PLAYER_POSITION)
    state['characters'][1].update(faction_id='fixture-bystander', position=[110, 0, 200])
    state['factions'].append(dict(id='fixture-bystander', name='Fixture bystander'))
    state['squads'][0].update(id=raw[2], members=raw[:2], leader_id=raw[0])
    fake = SetupProbe(tmp_path / 'native', state, require_saved_origins=True,
                      save_root=root, origin_aliases=dict(zip(saved, raw)))
    profile = tmp_path / 'engine-profile.json'
    profile.write_text(json.dumps(dict(profile_format='engine-profile-0.1', entries=[dict(
        target='original', save=SETUP_SAVE, source_fingerprint=fingerprint or manifest['fingerprint'],
        seed=None, player=dict(xz=[100, 200], y_before_settle=7.25, y_after_settle=y_after, decimals=3),
        evidence='synthetic')])), encoding='utf-8')
    cfg = dict(runtime=str(tmp_path / 'runtime'), runs=str(tmp_path / 'runs'),
               oracle_output=str(fake.output_directory), timeout=2, load_timeout=3,
               run_until_timeout=2, scenario_timeout=20, engine_profile=str(profile))
    return fake, cfg, saved


def setup_scenario(repeat=1):
    return dict(
        schema_version='scenario-0.2', name='synthetic-setup', save=SETUP_SAVE, speed=1, repeat=repeat,
        setup=dict(
            preflight=dict(scene_center=[100, 200], scene_radius=1500, squad_size_multiplier=1,
                           player_faction_id='fixture-faction', expect_absent_factions_in_scene=['fixture-rival']),
            moves=[],
            spawns=[dict(alias='raiders', squad_template='fixture-squad', count=4, faction_id='fixture-rival',
                         at=dict(offset_from_player=[30, 0]),
                         expected_templates={'fixture-leader': 1, 'fixture-member': 3})],
            settle=dict(sim_seconds=1), heal='all_scene_characters',
            relations=[dict(a='fixture-rival', b='fixture-faction', a_to_b=-60, b_to_a=-60)]),
        actions=[dict(at=0, command='issue_order',
                      params=dict(type='attack', squad_alias='raiders', target_alias='player')),
                 dict(at=2, command='pause', params=dict(paused=True))],
        checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])


def run_setup(fake, cfg, value=None, facts=None):
    async def run():
        scenario_value = setup_scenario() if value is None else value
        await OracleSession(cfg, fake).load(scenario_value['save'], lock_edge=False)
        await fake.call('set_game_speed', speed=1, preserve_pause=True)
        fake.calls.clear()
        fake.requests.clear()
        return await execute_scenario(scenario_value, cfg, client=fake,
                                      engine_facts=squad_facts() if facts is None else facts)
    return asyncio.run(run())


def test_setup_block_runs_between_speed_and_origin_and_records_the_receipt(tmp_path):
    from oracle_setup import setup_hash
    fake, cfg, saved = setup_fixture(tmp_path)
    value = setup_scenario()
    result = run_setup(fake, cfg, value)
    report = report_for(cfg)
    assert result['status'] == report['status'] == 'completed' and result['restored'] is True
    assert report['build_commit'] == fake.build_commit and report['build_commit_known'] is True
    assert report['limitations'] == ['war flag not observable on original']
    execution = report['executions'][0]
    receipt = execution['setup']
    folder = Path(report['output']) / '1'
    assert json.loads((folder / 'setup' / 'setup.json').read_text(encoding='utf-8')) == receipt
    assert receipt['receipt_format'] == 'scene-setup-0.1' and receipt['verdict'] == 'passed'
    assert receipt['failure'] is None and receipt['target'] == 'original'
    assert receipt['setup_hash'] == setup_hash(value['setup'])
    assert receipt['build_commit'] == fake.build_commit and receipt['build_commit_known'] is True
    assert list(receipt['alias_map']) == ['player', 'raiders', *MEMBER_ALIASES]
    assert receipt['alias_map']['player'] == saved[0]
    assert receipt['alias_map']['raiders'].startswith('local:fake-squad:')
    assert receipt['squad_size'] == squad_facts()['squad_size']
    assert [row['alias'] for row in receipt['members']] == ['player', *MEMBER_ALIASES]
    member = receipt['members'][1]
    assert member['part_max'] == {'fixture-head:neither': 100}
    assert (member['blood_before'], member['blood_after'], member['rng_key']) == (80.0, 100.0, None)
    settle = receipt['settle']
    assert (settle['start_seconds'], settle['end_seconds'], settle['calendar_seconds_run']) == (216000, 216033, 33)
    assert settle['sim_seconds'] == 1 and settle['calendar_seconds_requested'] == 33
    assert settle['player_before'] == settle['player_after'] == PLAYER_POSITION
    assert settle['pin'] == settle['observed'] == PLAYER_POSITION
    assert list(receipt['dumps']) == ['S3b', 'S5', 'S6']
    for name, dump in receipt['dumps'].items():
        assert dump['path'] == 'setup/' + name + '.json'
        assert hashlib.sha256((folder / dump['path']).read_bytes()).hexdigest() == dump['sha256']
    assert [step['step'] for step in receipt['steps']
            if step['request']['command'] in SETUP_MUTATIONS] == ['S2'] + ['S5'] * 5 + ['S4'] * 2
    assert all(step['verdict'] == 'passed' for step in receipt['steps'])
    commands = [row['request']['command'] for row in receipt['steps']]
    # One step per command sent, in order: the opening ping, a ping and setup_info per guard (S0 also
    # reads setup_info), and every ping and poll that until() sends during the settle.
    assert commands[0] == 'ping' and receipt['steps'][0]['step'] == 'S0'
    polls = commands.count('run_until') + commands.count('run_until_status')
    assert commands.count('run_until') == 1 and polls >= 2
    assert commands.count('ping') == 1 + (commands.count('setup_info') - 1) + polls
    assert commands.count('setup_info') - 1 >= 10
    sent = [row for row in fake.requests if row['command'].startswith('setup_')
            or row['command'] in ('run_until', 'run_until_status', 'dump_state')]
    recorded = [row for row in receipt['steps'] if row['request']['command'] in {r['command'] for r in sent}]
    assert [(row['request']['command'], row['request']['params']) for row in recorded] == \
        [(row['command'], row['params']) for row in sent[:len(recorded)]]
    dumps = [row for row in receipt['steps'] if row['request']['command'] == 'dump_state']
    assert [list(row['request']['params']) for row in dumps] == [['filename']] * 3  # The fake offers 0.1 only.
    assert [row['read_back']['path'] for row in dumps] == ['setup/S3b.json', 'setup/S5.json', 'setup/S6.json']
    # Call order: reload, speed preparation, S0..S6, then the origin clock.
    calls = fake.calls[fake.calls.index('commit_saved_origins'):]
    order = calls.index('issue_order')
    origin = max(index for index, command in enumerate(calls[:order]) if command == 'get_clock')
    assert set(calls[origin + 1:order]) == {'ping'}
    assert calls.index('set_game_speed') < calls.index('setup_info')
    assert max(index for index, command in enumerate(calls[:origin]) if command.startswith('setup_')) < origin
    work = [command for command in calls[:origin] if command in SETUP_MUTATIONS + ('run_until', 'dump_state')]
    assert work == (['setup_spawn_squad', 'run_until', 'dump_state'] + ['setup_heal'] * 5
                    + ['dump_state', 'setup_set_relation', 'setup_set_relation', 'dump_state'])
    # Checkpoint 0 is the post-setup world.
    assert execution['initial_clock']['elapsed_seconds'] == 216033
    assert [capture['actual_at'] for capture in execution['checkpoints']] == [0, 2]
    for capture in execution['checkpoints']:
        assert capture['setup']['setup_hash'] == receipt['setup_hash']
        assert capture['setup']['alias_map'] == receipt['alias_map']
        census = capture['setup']['census']
        assert (census['count'], census['truncated'], census['player_count']) == (6, False, 1)
    initial = load_state(execution['checkpoints'][0]['path'])
    relations = {(row['source_id'], row['target_id']): row['value'] for row in initial['relations']}
    assert relations == {('fixture-faction', 'fixture-rival'): -60, ('fixture-rival', 'fixture-faction'): -60}
    # The save is loaded with the opt-in for the repetition only, never for cleanup.
    loads = [row['params'] for row in fake.requests if row['command'] == 'load_save']
    assert [params.get('allow_setup') for params in loads] == [True, None]
    assert guard_for(cfg)['restore_required'] is False


# The setup_hash of scenarios/nature-bandit-ambush.json; a change to the block or to the rule moves it.
NATURE_SETUP_HASH = 'fa89565ed70bc7a3c49c3bc424aa59e6ba9d15b12dda66c56095f27320d0b3e2'


def test_runner_and_comparator_share_one_setup_hash_rule():
    import oracle_scope
    import oracle_setup
    assert oracle_setup.setup_hash is oracle_scope.setup_hash
    assert oracle_setup.RECEIPT_FORMAT == oracle_scope.RECEIPT_FORMAT == 'scene-setup-0.1'
    scenario = json.loads((Path(__file__).resolve().parents[1] / 'scenarios' / 'nature-bandit-ambush.json')
                          .read_text(encoding='utf-8'))
    assert oracle_scope.setup_hash(scenario['setup']) == NATURE_SETUP_HASH
    # Key order does not matter; any value change does.
    assert oracle_scope.setup_hash(dict(reversed(list(scenario['setup'].items())))) == NATURE_SETUP_HASH
    changed = json.loads(json.dumps(scenario['setup']))
    changed['relations'][0]['a_to_b'] = -61
    assert oracle_scope.setup_hash(changed) != NATURE_SETUP_HASH


def test_setup_actions_resolve_aliases_and_record_resolved_params(tmp_path):
    fake, cfg, saved = setup_fixture(tmp_path)
    value = setup_scenario()
    value['actions'][1]['params'] = dict(paused=False)  # A logical resume still sends paused:true.
    value['actions'] += [dict(at=2, command='set_game_speed', params=dict(speed=2)),
                         dict(at=2, command='set_game_speed', params=dict(speed=0))]
    run_setup(fake, cfg, value)
    execution = report_for(cfg)['executions'][0]
    alias_map = execution['setup']['alias_map']
    attack = execution['actions'][0]
    assert attack['request'] == value['actions'][0]
    assert attack['resolved_params'] == dict(type='attack', squad_id=alias_map['raiders'], target_id=saved[0])
    assert attack['result']['affected_characters'] == 4
    sent = next(row['params'] for row in fake.requests if row['command'] == 'issue_order')
    assert sent == attack['resolved_params']
    # resolved_params are the parameters actually sent, not the request as written.
    assert [row['request'] for row in execution['actions'][1:]] == value['actions'][1:]
    assert [row['resolved_params'] for row in execution['actions'][1:]] == [
        dict(paused=True), dict(speed=2, preserve_pause=True), dict(paused=True)]


def test_alias_resolution_refuses_unbound_or_mismatched_aliases():
    from oracle_setup import resolve_aliases
    alias_map = {'player': 'p', 'raiders': 's', 'raiders/t/1': 'm'}
    assert resolve_aliases(dict(type='attack', character_alias='raiders/t/1', target_alias='player'),
                           alias_map) == dict(type='attack', character_id='m', target_id='p')
    with pytest.raises(ScenarioError, match='not bound'):
        resolve_aliases(dict(type='attack', squad_alias='raiders', target_alias='raiders/t/2'), alias_map)
    with pytest.raises(ScenarioError, match='does not name'):
        resolve_aliases(dict(type='attack', squad_alias='player', target_alias='raiders/t/1'), alias_map)
    with pytest.raises(ScenarioError, match='does not name'):
        resolve_aliases(dict(type='attack', squad_alias='raiders', target_alias='raiders'), alias_map)


def test_setup_variability_keys_spawned_ids_by_alias(tmp_path):
    from oracle_runner import flatten_state
    from oracle_setup import alias_ids
    fake, cfg, _ = setup_fixture(tmp_path)
    run_setup(fake, cfg, setup_scenario(repeat=2))
    report = report_for(cfg)
    first, second = (execution['setup']['alias_map'] for execution in report['executions'])
    assert first.keys() == second.keys() and first['raiders'] != second['raiders']
    for name in ('initial', 'later'):
        result = report['variability'][name]
        assert result['repeatability_evaluated'] and result['variable_field_count'] == 0
        paths = result['stable_paths']
        assert '/characters/alias:raiders~1fixture-leader~11/state' in paths
        assert '/squads/alias:raiders/leader_id' in paths
        assert not any('local:fake' in path for path in paths)
    later = load_state(report['executions'][0]['checkpoints'][1]['path'])
    flat = flatten_state(later, aliases=alias_ids(first))
    assert flat['/squads/alias:raiders/leader_id'] == 'alias:raiders/fixture-leader/1'
    assert flat['/squads/alias:raiders/members/0'] == 'alias:raiders/fixture-leader/1'
    assert flat['/characters/alias:raiders~1fixture-member~12/order/target_id'] == 'alias:player'
    assert not any('local:fake' in str(item) for item in flat.values())


def test_unknown_build_commit_is_accepted_with_its_limitation(tmp_path):
    fake, cfg, _ = setup_fixture(tmp_path)
    fake.build_commit = 'unknown'
    assert run_setup(fake, cfg)['status'] == 'completed'
    report = report_for(cfg)
    assert report['build_commit'] == 'unknown' and report['build_commit_known'] is False
    assert 'commit unknown' in report['limitations']
    receipt = report['executions'][0]['setup']
    assert receipt['build_commit_known'] is False and 'commit unknown' in receipt['limitations']


def test_report_records_build_commit_without_setup_and_never_sends_allow_setup(tmp_path):
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    value = scenario()
    value['repeat'] = 1
    asyncio.run(execute_scenario(value, cfg, client=fake))
    report = report_for(cfg)
    assert report['build_commit'] == fake.build_commit and report['build_commit_known'] is True
    assert report['limitations'] == []
    assert all('allow_setup' not in row['params'] for row in fake.requests if row['command'] == 'load_save')
    assert 'setup_info' not in fake.calls and 'setup' not in report['executions'][0]


def test_changed_build_commit_between_repetitions_fails_the_run(tmp_path):
    cfg = config(tmp_path)

    class CommitChangingProbe(FakeProbe):
        async def call(self, command, **params):
            if command == 'load_save':
                self.build_commit = 'f' * 40
            return await super().call(command, **params)
    fake = CommitChangingProbe(cfg['oracle_output'])
    value = scenario()
    value['repeat'] = 1
    with pytest.raises(ScenarioError, match='build_commit changed'):
        asyncio.run(execute_scenario(value, cfg, client=fake))
    assert report_for(cfg)['restoration']['verified'] is True


@pytest.mark.parametrize('case,match', [
    ('capability absent', 'capability scene_setup'),
    ('missing pin', 'No engine profile entry'),
    ('unpinned save', 'No engine profile pins exist'),
    ('no engine facts', 'engine_facts'),
    ('no build commit', 'build_commit'),
    ('pre-0.11 probe', 'capability scene_setup'),
    ('capabilities not a list', 'capability scene_setup'),
])
def test_setup_refusals_before_the_guard_is_armed(tmp_path, case, match):
    fake, cfg, _ = setup_fixture(tmp_path, fingerprint='sha256:' + 'b' * 64 if case == 'missing pin' else None,
                                 save='another-save' if case == 'unpinned save' else SETUP_SAVE)
    facts = None
    value = setup_scenario()
    if case == 'capability absent':
        fake.capabilities = []
    elif case == 'unpinned save':
        value['save'] = 'another-save'
    elif case == 'no engine facts':
        facts = {}
    elif case == 'no build commit':
        fake.build_commit = None
    elif case == 'pre-0.11 probe':
        fake.capabilities, fake.build_commit = [], None
    elif case == 'capabilities not a list':
        fake.capabilities = 'scene_setup'
    with pytest.raises(ScenarioError, match=match):
        run_setup(fake, cfg, value, facts=facts)
    assert set(fake.calls) <= {'ping'}
    assert fake.loads == [value['save']]  # The preload only.
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()
    assert report_for(cfg)['status'] == 'failed'


def _unconscious_member(fake):
    fake.spawned()[0]['state'] = 'unconscious'


def _move_player(fake):
    fake.state['characters'][0]['position'][0] += 1


def _partial_heal(fake, params, result):
    result['after']['parts'][0]['stun'] = 5


def _heal_moves_relation(fake, params, result):
    fake._write_relation('fixture-bystander', 'fixture-faction', -10)


def _extra_relation_cell(fake, params, result):
    fake._write_relation('fixture-bystander', 'fixture-rival', -5)
    result['changes'].append(dict(source_id='fixture-bystander', target_id='fixture-rival',
                                  relation_before=0, relation_after=-5, is_enemy_before=False,
                                  is_enemy_after=False, at_war_before=None, at_war_after=None))
    result['changed_cells'] += 1


def _kill_member(fake, params, result):
    if params['source_id'] == 'fixture-faction':
        fake.spawned()[1]['state'] = 'dead'


def _restart(fake, params, result):
    fake.instance_id = 'replacement-instance'


def _reply(command, change):
    """A hook that returns a changed copy of one setup reply (the world itself is unchanged)."""
    def hook(fake, params, result):
        result = deepcopy(result)
        change(result)
        return result
    return command, hook


def _drop(key):
    return lambda result: result.pop(key)


def _set(key, value):
    return lambda result: result.__setitem__(key, value)


def _nudge_y(result):
    result['position'][1] += 0.5


def _census_center(result):
    result['center'][0] += 1


def _drop_mutation_refusal(result):
    del result['gate']['mutation_refusal']


def _world_unpaused(result):
    result['world_after']['paused'] = False


def _census_row(key, value):
    def change(result):
        result['characters'][0][key] = value
    return change


def _at_war(fake, params, result):
    result = deepcopy(result)
    result['source_to_target']['before']['at_war'] = False
    result['source_to_target']['after']['at_war'] = True
    return result


def _at_war_missing(fake, params, result):
    result = deepcopy(result)
    del result['target_to_source']['after']['at_war']
    return result


def _mutation_refused(fake, params, result):
    if result['gate']['mutation_refusal'] is None and fake.world_mutated is False and fake.calls.count('setup_info') > 2:
        result = deepcopy(result)
        result['gate']['mutation_refusal'] = dict(code='not_allowed', message='the game must be paused')
    return result


def _epoch_change(fake, params, result):
    if fake.calls.count('setup_heal') == 2:
        result = deepcopy(result)
        result['gate']['epoch'] += 1
    return result


def _gate_without_opt_in(fake, params, result):
    if fake.world_mutated:
        result = deepcopy(result)
        result['gate']['allow_setup'] = False
    return result


REPLY_FAILURES = [
    ('S0', 'census center echo', _reply('setup_area_census', _census_center), 'echoed center'),
    ('S0', 'census radius echo', _reply('setup_area_census', _set('radius', 1499.5)), 'echoed radius'),
    ('S0', 'census gate closed', _reply('setup_area_census', lambda r: r['gate'].update(open=False)),
     'census gate'),
    ('S0', 'census row without faction', _reply('setup_area_census', _census_row('faction_id', None)),
     'census row is malformed'),
    ('S0', 'census row is_player missing', _reply('setup_area_census', _census_row('is_player', 1)),
     'census row is malformed'),
    ('S0', 'census row squad_id number', _reply('setup_area_census', _census_row('squad_id', 3)),
     'census row is malformed'),
    ('S0', 'gate without mutation_refusal', _reply('setup_info', _drop_mutation_refusal), 'incomplete'),
    ('S0', 'native squad_size reported',
     _reply('setup_info', _set('squad_size', dict(source='settings.cfg', multiplier=1.0, line=SETTINGS_LINE,
                                                  sha256='0' * 64, path='settings.cfg'))),
     'null on the original'),
    ('S2', 'spawn position echo', _reply('setup_spawn_squad', _nudge_y), 'echoed position'),
    ('S2', 'spawn template echo', _reply('setup_spawn_squad', _set('template_id', 'fixture-other')),
     'echoed template_id'),
    ('S2', 'spawn faction echo', _reply('setup_spawn_squad', _set('faction_id', 'fixture-bystander')),
     'echoed faction_id'),
    ('S2', 'spawn max_count echo', _reply('setup_spawn_squad', _set('max_count', 3)), 'echoed max_count'),
    ('S2', 'spawn permanent echo', _reply('setup_spawn_squad', _set('permanent', True)), 'echoed permanent'),
    ('S2', 'spawn size_multiplier', _reply('setup_spawn_squad', _set('size_multiplier', 2.0)),
     'size_multiplier'),
    ('S2', 'spawn without world_before', _reply('setup_spawn_squad', _drop('world_before')), 'world_before'),
    ('S2', 'spawn without gate', _reply('setup_spawn_squad', _drop('gate')), 'mutation reply gate'),
    ('S2', 'spawn world resumed', _reply('setup_spawn_squad', _world_unpaused), 'world_after'),
    ('S5', 'heal character echo', _reply('setup_heal', _set('character_id', 'char:other')),
     'echoed character_id'),
    ('S5', 'heal saved', _reply('setup_heal', _set('saved', True)), 'saved:false'),
    ('S4', 'relation value echo', _reply('setup_set_relation', _set('value', -59.0)), 'echoed value'),
    ('S4', 'relation source echo', _reply('setup_set_relation', _set('source_id', 'fixture-bystander')),
     'echoed source_id'),
    ('S4', 'relation target echo', _reply('setup_set_relation', _set('target_id', 'fixture-bystander')),
     'echoed target_id'),
    ('S4', 'war flag changed', ('setup_set_relation', _at_war), 'war flag'),
    ('S4', 'war flag key missing', ('setup_set_relation', _at_war_missing), 'no complete target_to_source'),
    ('S2', 'mutation refused', ('setup_info', _mutation_refused), 'mutation refused'),
    ('S5', 'epoch changed', ('setup_info', _epoch_change), 'epoch changed'),
    ('S2', 'opt-in lost', ('setup_info', _gate_without_opt_in), 'allow_setup load'),
]


@pytest.mark.parametrize('step,case,hook,match', REPLY_FAILURES, ids=[row[1] for row in REPLY_FAILURES])
def test_setup_reply_checks_fail_the_step_and_restore(tmp_path, step, case, hook, match):
    fake, cfg, _ = setup_fixture(tmp_path)
    command, change = hook
    fake.hooks[command] = change
    with pytest.raises(ScenarioError, match=match) as caught:
        run_setup(fake, cfg)
    assert 'Scene setup ' + step + ' failed' in str(caught.value)
    report = report_for(cfg)
    receipt = report['executions'][0]['setup']
    assert receipt['verdict'] == 'failed' and receipt['failure']['step'] == step
    assert report['executions'][0]['checkpoints'] == [] and 'issue_order' not in fake.calls
    assert report['restoration']['verified'] is True and guard_for(cfg)['restore_required'] is False


@pytest.mark.parametrize('step,case,match', [
    ('S0', 'autosave enabled', 'autosave'),
    ('S0', 'autosave configured', 'autosave'),
    ('S0', 'multiplier mismatch', 'multiplier'),
    ('S0', 'intruder', 'expected-absent faction'),
    ('S0', 'Y mismatch before settle', 'pin before settle'),
    ('S2', 'count mismatch', 'returned 3 members'),
    ('S2', 'template mismatch', 'template plan differs'),
    ('S2', 'instance restart', 'restarted'),
    ('S2', 'native rng_key', 'rng_key'),
    ('S3', 'Y mismatch', 'pin after settle'),
    ('S3', 'X/Z mismatch', 'pin after settle'),
    ('S3b', 'unconscious', 'unconscious before heal'),
    ('S5', 'heal not full', 'heal not full'),
    ('S5', 'heal moved a relation', 'heal moved a relation'),
    ('S4', 'extra relation cell', 'outside the pair'),
    ('S4', 'not hostile', 'does not read hostile'),
    ('S6', 'alias dead', 'dead or unconscious after setup'),
])
def test_each_setup_step_failure_restores_without_retry(tmp_path, step, case, match):
    fake, cfg, _ = setup_fixture(tmp_path, y_after=7.5 if case == 'Y mismatch' else 7.25)
    facts = None
    if case == 'autosave enabled':
        fake.autosave_enabled = True
    elif case == 'autosave configured':
        fake.autosave_configured = True
    elif case == 'multiplier mismatch':
        facts = squad_facts('Squad size multiplier=2')
    elif case == 'intruder':
        fake.initial_state['characters'][1]['faction_id'] = 'fixture-rival'
    elif case == 'Y mismatch before settle':
        fake.initial_state['characters'][0]['position'][1] = 7.5
    elif case == 'count mismatch':
        fake.squad_templates['fixture-squad'] = ['fixture-leader'] + ['fixture-member'] * 2
    elif case == 'template mismatch':
        fake.squad_templates['fixture-squad'] = ['fixture-leader'] * 2 + ['fixture-member'] * 2
    elif case == 'instance restart':
        fake.hooks['setup_spawn_squad'] = _restart
    elif case == 'native rng_key':
        fake.hooks['setup_spawn_squad'] = lambda probe, params, result: dict(result, rng_key='7')
    elif case == 'X/Z mismatch':
        fake.advance_hook = _move_player
    elif case == 'unconscious':
        fake.advance_hook = _unconscious_member
    elif case == 'heal not full':
        fake.hooks['setup_heal'] = _partial_heal
    elif case == 'heal moved a relation':
        fake.hooks['setup_heal'] = _heal_moves_relation
    elif case == 'extra relation cell':
        fake.hooks['setup_set_relation'] = _extra_relation_cell
    elif case == 'not hostile':
        fake.hostility_threshold = -70
    elif case == 'alias dead':
        fake.hooks['setup_set_relation'] = _kill_member
    with pytest.raises(ScenarioError, match=match) as caught:
        run_setup(fake, cfg, facts=facts)
    assert 'Scene setup ' + step + ' failed' in str(caught.value)
    report = report_for(cfg)
    execution = report['executions'][0]
    receipt = execution['setup']
    assert report['status'] == execution['status'] == 'failed'
    assert receipt['verdict'] == 'failed' and receipt['failure']['step'] == step
    assert re.search(match, receipt['failure']['message'])
    folder = Path(report['output']) / '1'
    assert json.loads((folder / 'setup' / 'setup.json').read_text(encoding='utf-8')) == receipt
    assert execution['checkpoints'] == [] and 'issue_order' not in fake.calls
    # No retry: each mutation went at most once per planned use, and nothing followed the failure.
    assert fake.calls.count('setup_spawn_squad') <= 1 and fake.calls.count('setup_heal') <= 5
    assert fake.calls.count('setup_set_relation') <= 2 and fake.calls.count('run_until') <= 1
    failed = [row for row in receipt['steps'] if row['verdict'] == 'failed']
    assert len(failed) <= 1 and (not failed or failed[0] == receipt['steps'][-1])
    assert all(row['step'] == step for row in failed)
    if case == 'instance restart':
        assert 'restarted' in report['restoration_error'] and guard_for(cfg)['restore_required'] is True
        assert fake.loads == [SETUP_SAVE, SETUP_SAVE]
    else:
        assert report['restoration']['verified'] is True and guard_for(cfg)['restore_required'] is False
        assert fake.loads == [SETUP_SAVE] * 3  # Preload, the repetition, then cleanup.
        cleanup = [row['params'] for row in fake.requests if row['command'] == 'load_save'][-1]
        assert 'allow_setup' not in cleanup and fake.world_mutated is False


def _cancel_heal(fake, params, result):
    raise asyncio.CancelledError()


def test_cancellation_mid_setup_still_writes_the_failed_receipt(tmp_path):
    fake, cfg, _ = setup_fixture(tmp_path)
    fake.hooks['setup_heal'] = _cancel_heal
    with pytest.raises(ScenarioError):
        run_setup(fake, cfg)
    report = report_for(cfg)
    assert report['error'] == 'CancelledError: '
    receipt = report['executions'][0]['setup']
    assert receipt['verdict'] == 'failed'
    assert receipt['failure'] == dict(step='S5', message='CancelledError: ')
    folder = Path(report['output']) / '1'
    assert json.loads((folder / 'setup' / 'setup.json').read_text(encoding='utf-8')) == receipt
    assert receipt['steps'][-1]['request']['command'] == 'setup_heal' and receipt['steps'][-1]['reply'] is None
    assert report['restoration']['verified'] is True and guard_for(cfg)['restore_required'] is False


def test_receipt_limitations_reach_the_report_when_setup_fails(tmp_path):
    fake, cfg, _ = setup_fixture(tmp_path)
    fake.hooks['setup_set_relation'] = _kill_member  # Fails at S6, after the S4 limitation.
    with pytest.raises(ScenarioError, match='Scene setup S6 failed'):
        run_setup(fake, cfg)
    report = report_for(cfg)
    assert report['executions'][0]['setup']['limitations'] == ['war flag not observable on original']
    assert report['limitations'] == ['war flag not observable on original']


def test_mirrored_relation_cells_pass_as_on_both_engines(tmp_path):
    fake, cfg, _ = setup_fixture(tmp_path)
    fake.mirror_relations = True  # One set changes both cells, the second changes none (Observed/Verified).
    assert run_setup(fake, cfg)['status'] == 'completed'
    receipt = report_for(cfg)['executions'][0]['setup']
    sets = [row for row in receipt['steps'] if row['request']['command'] == 'setup_set_relation']
    assert [row['read_back']['changed_cells'] for row in sets] == [2, 0]


def _sleep_on(command, seconds):
    def wrap(fake):
        send = fake.call

        async def call(sent, /, **params):
            if sent == command:
                await asyncio.sleep(seconds)
            return await send(sent, **params)
        fake.call = call
    return wrap


def _lose_reply(fake, params, result):
    raise ProbeError('Jeu figé ou non lancé : délai expiré ou connexion impossible')


def _restart_on_advance(fake):
    fake.instance_id = 'replacement-instance'


@pytest.mark.parametrize('case,step,match', [
    ('run_timeout', 'S3', 'run_until'),
    ('run_stalled', 'S3', 'deadline'),
    ('scenario deadline during heal', 'S5', 'scenario_timeout'),
    ('lost spawn reply', 'S2', 'délai expiré'),
    ('restart during settle', 'S3', 'restarted'),
])
def test_setup_timeouts_and_lost_replies_fail_once_and_restore(tmp_path, case, step, match):
    fake, cfg, _ = setup_fixture(tmp_path)
    if case in ('run_timeout', 'run_stalled'):
        fake.mode = case
    elif case == 'scenario deadline during heal':
        _sleep_on('setup_heal', 30)(fake)
        cfg['scenario_timeout'] = 3
    elif case == 'lost spawn reply':
        fake.hooks['setup_spawn_squad'] = _lose_reply
    else:
        fake.advance_hook = _restart_on_advance
    with pytest.raises(ScenarioError, match=match) as caught:
        run_setup(fake, cfg)
    assert 'Scene setup ' + step + ' failed' in str(caught.value)
    report = report_for(cfg)
    receipt = report['executions'][0]['setup']
    assert receipt['failure']['step'] == step and report['executions'][0]['checkpoints'] == []
    assert receipt['steps'][-1]['verdict'] == 'failed'
    assert all(row['verdict'] == 'passed' for row in receipt['steps'][:-1])
    assert fake.calls.count('setup_spawn_squad') <= 1 and fake.calls.count('run_until') <= 1
    assert 'issue_order' not in fake.calls
    if case == 'restart during settle':
        # The old operation is never sent to the new process, and the guard stays armed.
        assert 'cancel_run_until' not in fake.calls
        assert 'restarted' in report['restoration_error'] and guard_for(cfg)['restore_required'] is True
    else:
        assert fake.calls.count('cancel_run_until') == (1 if case.startswith('run_') else 0)
        assert report['restoration']['verified'] is True and guard_for(cfg)['restore_required'] is False


def _keep_world_mutated(fake, params, result):
    """Pings after the cleanup reload still report the scene-setup world as mutated."""
    if len(fake.loads) >= 3:
        return dict(result, world_mutated=True)


@pytest.mark.parametrize('fail', [False, True])
def test_cleanup_reload_that_keeps_world_mutated_leaves_the_guard_armed(tmp_path, fail):
    fake, cfg, _ = setup_fixture(tmp_path)
    fake.hooks['ping'] = _keep_world_mutated
    if fail:
        fake.hooks['setup_set_relation'] = _kill_member
    with pytest.raises(ScenarioError, match='restoration required'):
        run_setup(fake, cfg)
    report = report_for(cfg)
    assert 'did not clear world_mutated' in report['restoration_error']
    assert 'restoration' not in report and guard_for(cfg)['restore_required'] is True
    assert 'prepare_scene_control' not in fake.calls  # Controls are never restored over that world.


def test_recovery_of_a_scene_setup_probe_requires_world_mutated_cleared(tmp_path):
    cfg = config(tmp_path)
    fake = SetupProbe(cfg['oracle_output'])
    fake.hooks['ping'] = lambda probe, params, result: dict(result, world_mutated=True) if probe.loads else None
    original = asyncio.run(fake.call('get_scene_state'))
    Path(cfg['runtime']).mkdir()
    guard = dict(restore_required=True, save='Synthetic save', controls=original, instance_id='old-instance')
    (Path(cfg['runtime']) / 'oracle-restoration.json').write_text(json.dumps(guard), encoding='utf-8')
    with pytest.raises(ScenarioError, match='did not clear world_mutated'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    pending = guard_for(cfg)
    assert pending['restore_required'] is True and 'world_mutated' in pending['recovery_attempt']['error']
    assert 'prepare_scene_control' not in fake.calls
    # The same probe recovers once its reload clears the flag.
    fake.hooks.clear()
    assert asyncio.run(restore_interrupted_scenario(cfg, client=fake))['restored'] is True


def test_meitou_squad_size_and_rng_key_follow_the_target_shape():
    from oracle_setup import SetupFailure, _Block
    block = _Block(None, setup_scenario(), '.', None, None)
    block.target = 'meitou'
    line = 'Squad size multiplier=1'
    reported = dict(source='settings.cfg', multiplier=1.0, line=line,
                    sha256=hashlib.sha256(line.encode('utf-8')).hexdigest(), path='settings.cfg')
    assert block.squad_size_facts(dict(squad_size=reported)) == dict(reported, source='setup_info')
    for wrong in (dict(reported, source='default'), dict(reported, source='user_config'), None,
                  dict(reported, sha256='0' * 64), dict(reported, line=None, sha256=None),
                  dict(reported, multiplier=2.0)):
        with pytest.raises(SetupFailure):
            block.squad_size_facts(dict(squad_size=wrong))
    two = 'Squad size multiplier=2'
    with pytest.raises(SetupFailure, match='multiplier'):
        block.squad_size_facts(dict(squad_size=dict(reported, line=two, multiplier=2.0,
                                                    sha256=hashlib.sha256(two.encode('utf-8')).hexdigest())))
    for wrong in (dict(reported, path='other.cfg'), dict(reported, multiplier=True),
                  dict(reported, path=None)):
        with pytest.raises(SetupFailure):
            block.squad_size_facts(dict(squad_size=wrong))
    # The original never reads setup_info for the multiplier: engine facts are the only source,
    # and setup_info reports null there.
    block.target = 'original'
    with pytest.raises(SetupFailure, match='null on the original'):
        block.squad_size_facts(dict(squad_size=reported))
    with pytest.raises(SetupFailure, match='missing'):
        block.squad_size_facts(dict(squad_size=None))
    native = dict(reported, source='engine_facts')
    block.facts = dict(squad_size=dict(native, multiplier=True))
    with pytest.raises(SetupFailure, match='missing'):
        block.squad_size_facts(dict(squad_size=None))
    block.facts = dict(squad_size=native)
    assert block.squad_size_facts(dict(squad_size=None)) == native


def test_meitou_setup_pins_resolve_from_the_save_source_for_every_seed(tmp_path):
    from oracle_setup import prepare_setup
    fake, cfg, _ = setup_fixture(tmp_path)
    profile = json.loads(Path(cfg['engine_profile']).read_text(encoding='utf-8'))
    entry = profile['entries'][0]
    meitou = dict(entry, target='meitou', seed=None)
    profile['entries'] = [meitou, dict(meitou, seed='1', evidence='seed one')]
    Path(cfg['engine_profile']).write_text(json.dumps(profile), encoding='utf-8')
    ping = dict(target='meitou', capabilities=['scene_setup'], save_root=fake.save_root)
    fingerprint, entries = asyncio.run(prepare_setup(OracleSession(cfg, fake), setup_scenario(), cfg, ping,
                                                     None, ['0', '1'], None))
    assert fingerprint == entry['source_fingerprint']
    assert [row['evidence'] for row in entries] == ['synthetic', 'seed one']
    assert fake.calls == []
    with pytest.raises(ScenarioError, match='No engine profile entry'):
        asyncio.run(prepare_setup(OracleSession(cfg, fake), setup_scenario(), cfg, dict(ping, target='original'),
                                  'sha256:' + 'c' * 64, [None], squad_facts()))
