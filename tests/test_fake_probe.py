import asyncio
import json
from copy import deepcopy

import pytest

from fake_probe import FakeProbe, sample_state
from oracle_runner import execute_scenario
from oracle_schema import load_state, validate_state
from probe import Client, ProbeError


ORIGIN_FINGERPRINT = 'sha256:' + 'a' * 64


def origin_fixture(tmp_path, *, aliases=None):
    state = sample_state()
    saved = [row['id'] for row in state['characters']] + [state['squads'][0]['id']]
    current = ['char:A', 'char:B', 'squad:fixture']
    aliases = dict(zip(saved, current)) if aliases is None else aliases
    for index, character in enumerate(state['characters']):
        character.update(id=current[index], squad_id=current[2], name=current[0], race_id=current[0])
        character['health'][0]['id'] = current[1]
    state['characters'][0]['order'] = dict(type='attack', target_id=current[1], position=None)
    state['squads'][0].update(id=current[2], members=current[:2], leader_id=current[0])
    fake = FakeProbe(tmp_path/'native', state, require_saved_origins=True,
                     save_root=tmp_path/'synthetic-sources', origin_aliases=aliases)
    return fake, saved, current


async def prepare_origins(fake, saved, *, count=None):
    await fake.call('load_save', name='Synthetic save', pause_on_ready=True)
    pending = await fake.call('begin_saved_origins', save_name='Synthetic save',
                              source_fingerprint=ORIGIN_FINGERPRINT,
                              count=len(saved) if count is None else count)
    for offset in range(0, len(saved), 128):
        await fake.call('add_saved_origins', token=pending['token'], ids=saved[offset:offset+128])
    return await fake.call('commit_saved_origins', token=pending['token'])


def test_dump_is_valid_and_byte_identical_after_reload(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path)
        first = await fake.call('dump_state', filename='first.json')
        operation = await fake.call('run_until', target_seconds=216060)
        await fake.call('run_until_status', operation_id=operation['operation_id'])
        assert fake.state['clock']['elapsed_seconds'] == 216060
        await fake.call('load_save', name='fixture-save', pause_on_ready=True)
        second = await fake.call('dump_state', filename='second.json')
        assert load_state(first['path']) == load_state(second['path']) == validate_state(sample_state())
        assert (tmp_path / 'first.json').read_bytes() == (tmp_path / 'second.json').read_bytes()
        assert first['bytes'] == second['bytes'] == (tmp_path / 'first.json').stat().st_size
        assert fake.loads == ['fixture-save']
    asyncio.run(run())


def test_dump_never_overwrites_and_rejects_paths_outside_output(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path / 'dumps')
        await fake.call('dump_state', filename='state.json')
        original = (fake.output_directory / 'state.json').read_bytes()
        with pytest.raises(ProbeError, match='already_exists'):
            await fake.call('dump_state', filename='state.json')
        for filename in ('../state.json', 'C:\\state.json', '/state.json', 'nested/state.json', 'state.txt'):
            with pytest.raises(ProbeError, match='invalid_params'):
                await fake.call('dump_state', filename=filename)
        assert (fake.output_directory / 'state.json').read_bytes() == original
    asyncio.run(run())


def test_time_advances_only_at_completion_and_move_is_not_a_teleport(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path, completion_polls=2)
        squad = fake.state['squads'][0]['id']
        await fake.call('issue_order', type='move', squad_id=squad, position=[12, 0, 25])
        assert fake.state['characters'][0]['position'] == [0, 0, 0]
        operation = await fake.call('run_until', target_seconds=216090)
        assert operation['status'] == 'running' and not operation['clock']['paused']
        pending = await fake.call('run_until_status', operation_id=operation['operation_id'])
        assert pending['status'] == 'running' and pending['clock']['elapsed_seconds'] == 216000
        completed = await fake.call('run_until_status', operation_id=operation['operation_id'])
        assert completed['status'] == 'completed' and completed['clock']['paused']
        assert completed['clock']['elapsed_seconds'] == 216090
        assert all(row['position'] == [12, 0, 25] for row in fake.state['characters'])
        validate_state(fake.state)
    asyncio.run(run())


@pytest.mark.parametrize('mode,cancel,status', [('run_timeout', False, 'timed_out'), ('run_stalled', True, 'cancelled')])
def test_interrupted_time_operation_stops_paused_without_fake_progress(tmp_path, mode, cancel, status):
    async def run():
        fake = FakeProbe(tmp_path, mode=mode)
        operation = await fake.call('run_until', target_seconds=216090)
        result = await fake.call('cancel_run_until' if cancel else 'run_until_status', operation_id=operation['operation_id'])
        assert result['status'] == status
        assert result['clock']['paused'] and result['clock']['elapsed_seconds'] == 216000
    asyncio.run(run())


def test_reload_cancels_running_operation_and_restores_members(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path, mode='run_stalled')
        operation = await fake.call('run_until', target_seconds=216090)
        fake.state['characters'].pop()
        await fake.call('load_save', name='fixture-save', lock_edge=True, pause_on_ready=True)
        result = await fake.call('run_until_status', operation_id=operation['operation_id'])
        assert result['status'] == 'cancelled' and result['clock']['paused']
        assert len(fake.state['characters']) == 2 and fake.camera_owned and not fake.edge_scrolling
    asyncio.run(run())


def test_load_invalidates_selected_speed_until_explicit_command_without_advancing_time(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path)
        await fake.call('load_save', name='fixture-save', pause_on_ready=True)
        scene = await fake.call('get_scene_state')
        assert scene['selected_game_speed'] is None and scene['game_speed'] == 0
        with pytest.raises(ProbeError, match='explicitly selected'):
            await fake.call('run_until', target_seconds=216060)
        clock = await fake.call('get_clock')
        await fake.call('set_game_speed', speed=3, preserve_pause=True)
        assert await fake.call('get_clock') == clock
        assert (await fake.call('get_scene_state'))['selected_game_speed'] == 3
        operation = await fake.call('run_until', target_seconds=216060)
        assert operation['clock']['speed'] == 3 and not operation['clock']['paused']
        completed = await fake.call('run_until_status', operation_id=operation['operation_id'])
        assert completed['clock']['speed'] == 0 and completed['clock']['paused']
    asyncio.run(run())


def test_fake_network_rejects_malformed_request_without_losing_server(tmp_path):
    async def run():
        async with FakeProbe(tmp_path) as fake:
            reader, writer = await asyncio.open_connection('127.0.0.1', fake.port)
            writer.write(b'not json\n')
            await writer.drain()
            error = json.loads(await asyncio.wait_for(reader.readline(), 1))
            writer.close()
            await writer.wait_closed()
            assert error['id'] is None and error['error']['code'] == 'invalid_request'
            result = await Client(fake.port, 1).call('ping')
            assert result['schema_version'] == '0.1'
            capture = await Client(fake.port, 1).call('dump_state', filename='network.json')
            validate_state(load_state(capture['path']))
            with pytest.raises(ProbeError, match='not_implemented'):
                await Client(fake.port, 1).call('unavailable_command')
    asyncio.run(run())


@pytest.mark.parametrize('mode,message', [('wrong_id', 'Identifiant'), ('invalid', 'invalide'), ('hang', 'délai')])
def test_fake_protocol_errors_are_bounded(tmp_path, mode, message):
    async def run():
        async with FakeProbe(tmp_path, mode=mode) as fake:
            with pytest.raises(ProbeError, match=message):
                await Client(fake.port, .1).call('get_clock')
    asyncio.run(run())


def test_restore_reinstates_settings_and_releases_camera_ownership(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path)
        await fake.call('set_camera_free', enabled=True, lock_edge=True)
        await fake.call('restore_scene_control', camera_center=[12, 3, 9], camera_orientation=[1, 0, 0, 0],
                        camera_zoom=-70, free_camera=False, edge_scrolling=True, speed=3, paused=True)
        scene = await fake.call('get_scene_state')
        assert scene['camera_center'] == [12, 3, 9] and scene['camera_zoom'] == -70
        assert scene['camera_node_position'] == [0, 0, -70]
        assert not scene['free_camera'] and scene['edge_scrolling'] and not scene['scene_camera_control_owned']
        assert scene['selected_game_speed'] == 3 and scene['paused'] and scene['frame_speed_multiplier'] == 0
    asyncio.run(run())


@pytest.mark.parametrize('free,zoom,accepted', [(False, -70, True), (False, 0, False),
                                              (False, 70, False), (True, -70, True),
                                              (True, 0, True), (True, 70, True)])
def test_restore_zoom_sign_depends_on_final_camera_mode(tmp_path, free, zoom, accepted):
    async def run():
        fake = FakeProbe(tmp_path)
        before = await fake.call('get_scene_state')
        params = dict(camera_center=[12, 3, 9], camera_orientation=[1, 0, 0, 0],
                      camera_zoom=zoom, free_camera=free, edge_scrolling=False, speed=3, paused=True)
        if accepted:
            await fake.call('restore_scene_control', **params)
            scene = await fake.call('get_scene_state')
            assert scene['camera_zoom'] == zoom and scene['camera_node_position'] == [0, 0, zoom]
            assert scene['free_camera'] is free and scene['camera_center'] == [12, 3, 9]
        else:
            with pytest.raises(ProbeError, match='negative local Z'):
                await fake.call('restore_scene_control', **params)
            scene = await fake.call('get_scene_state')
            for key in ('camera_center', 'camera_zoom', 'camera_node_position', 'free_camera',
                        'edge_scrolling', 'selected_game_speed', 'paused'):
                assert scene[key] == before[key]
    asyncio.run(run())


def test_scenario_restores_follow_target_after_load_clears_it(tmp_path):
    async def run():
        cfg = dict(runtime=str(tmp_path / 'runtime'), runs=str(tmp_path / 'runs'),
                   oracle_output=str(tmp_path / 'probe-output'), load_timeout=.5,
                   run_until_timeout=.5, scenario_timeout=10)
        fake = FakeProbe(cfg['oracle_output'])
        identity = fake.state['characters'][0]['id']
        fake.camera_follow_id = identity
        scenario = dict(schema_version='0.1', name='restore-follow', save='Synthetic save',
                        speed=1, repeat=1, actions=[], checkpoints=[dict(at=0, name='initial')])
        result = await execute_scenario(scenario, cfg, client=fake)
        restore = [request for request in fake.requests if request['command'] == 'prepare_scene_control']
        assert result['restored'] and fake.loads == ['Synthetic save', 'Synthetic save']
        assert restore[0]['params']['camera_follow_id'] == identity
        assert (await fake.call('get_scene_state'))['camera_follow_id'] == identity
        await fake.call('load_save', name='Synthetic save')
        assert fake.camera_follow_id is None
    asyncio.run(run())


def test_restore_rejects_unloaded_follow_target_before_mutating_controls(tmp_path):
    async def run():
        fake = FakeProbe(tmp_path)
        before = await fake.call('get_scene_state')
        with pytest.raises(ProbeError, match='not_found'):
            await fake.call('restore_scene_control', camera_center=[12, 3, 9], camera_orientation=[1, 0, 0, 0],
                            camera_zoom=-70, free_camera=True, edge_scrolling=False, speed=3, paused=False,
                            camera_follow_id='missing-character')
        after = await fake.call('get_scene_state')
        for key in ('camera_center', 'camera_zoom', 'free_camera', 'edge_scrolling', 'selected_game_speed',
                    'paused', 'camera_follow_id'):
            assert after[key] == before[key]
    asyncio.run(run())


def test_saved_origins_are_opt_in_and_require_an_explicit_synthetic_root(tmp_path):
    with pytest.raises(ValueError, match='explicit synthetic save_root'):
        FakeProbe(tmp_path/'required', require_saved_origins=True)
    fake = FakeProbe(tmp_path/'default')
    status = asyncio.run(fake.call('ping'))
    assert status['saved_origins_required'] is False and status['save_root'] is None
    assert status['saved_origins'] == dict(prepared=False, save_name=None, source_fingerprint=None,
                                         count=0, pending_count=0, expected_count=0)
    asyncio.run(fake.call('dump_state', filename='stable.json'))


def test_saved_origin_protocol_over_loopback_reports_typed_resolution_and_registration(tmp_path):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        missing = 'hand:1:88:99:0:3'
        absent = 'hand:1:88:99:0:4'
        wrong_kind = 'hand:1:88:99:0:5'
        fake.origin_aliases.update({absent: 'char:not-loaded', wrong_kind: current[2]})
        async with fake:
            client = Client(fake.port, 1)
            status = await client.call('ping')
            assert status['saved_origins_required'] is True
            assert status['save_root'] == str((tmp_path/'synthetic-sources').resolve())
            loaded = await client.call('load_save', name='Synthetic save', pause_on_ready=True)
            assert loaded['save_root'] == status['save_root']
            result = await client.call('resolve_saved_handles', ids=saved+[missing, absent, wrong_kind])
            assert result['resolutions'][:3] == [dict(saved_id=s, current_id=c, loaded=True, resolved=True)
                                                 for s, c in zip(saved, current)]
            assert result['resolutions'][3:] == [
                dict(saved_id=missing, current_id=None, loaded=False, resolved=False),
                dict(saved_id=absent, current_id=None, loaded=False, resolved=True),
                dict(saved_id=wrong_kind, current_id=None, loaded=False, resolved=True)]
            with pytest.raises(ProbeError, match='origin_context_required'):
                await client.call('dump_state', filename='unprepared.json')
            pending = await client.call('begin_saved_origins', save_name='Synthetic save',
                                        source_fingerprint=ORIGIN_FINGERPRINT, count=3)
            assert not pending['prepared'] and pending['pending_count'] == 0
            added = await client.call('add_saved_origins', token=pending['token'], ids=saved)
            assert added['pending_count'] == added['expected_count'] == 3
            committed = await client.call('commit_saved_origins', token=pending['token'])
            assert committed == dict(prepared=True, save_name='Synthetic save', count=3,
                                     source_fingerprint=ORIGIN_FINGERPRINT, pending_count=0, expected_count=0)
            capture = await client.call('dump_state', filename='prepared.json')
            assert capture['identity_source']['matched_count'] == 3
            assert load_state(capture['path'])['characters'][0]['id'] == saved[0]
    asyncio.run(run())


def test_origin_canonicalization_changes_only_typed_snapshot_references(tmp_path):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        original = deepcopy(fake.initial_state)
        await prepare_origins(fake, saved)
        fake.camera_follow_id = current[0]
        capture = await fake.call('dump_state', filename='canonical.json')
        state = load_state(capture['path'])
        first, second = state['characters']
        assert [first['id'], second['id'], state['squads'][0]['id']] == saved
        assert first['squad_id'] == second['squad_id'] == saved[2]
        assert first['order']['target_id'] == saved[1]
        assert state['squads'][0]['members'] == saved[:2]
        assert state['squads'][0]['leader_id'] == saved[0]
        assert first['name'] == first['race_id'] == current[0]
        assert first['health'][0]['id'] == current[1]
        assert state['factions'] == original['factions'] and state['relations'] == original['relations']
        assert fake.state == original and fake.initial_state == original
        assert fake.camera_follow_id == current[0]
        assert (await fake.call('get_scene_state'))['camera_follow_id'] == saved[0]
        assert 'identity_source' not in state
        assert capture['identity_source'] == dict(save_name='Synthetic save',
            source_fingerprint=ORIGIN_FINGERPRINT, count=3, matched_count=3,
            remapped_characters=2, remapped_squads=1)
        # Saved inputs resolve back to raw actors; raw task subjects remain in
        # engine state and only become canonical in the exported common state.
        await fake.call('issue_order', type='attack', character_id=saved[1], target_id=saved[0])
        assert fake.state['characters'][1]['order']['target_id'] == current[0]
        second_capture = await fake.call('dump_state', filename='ordered.json')
        assert load_state(second_capture['path'])['characters'][1]['order']['target_id'] == saved[0]
    asyncio.run(run())


@pytest.mark.parametrize('transition', ['load', 'world_unavailable', 'new_instance'])
def test_origin_context_and_registration_tokens_expire_at_world_boundaries(tmp_path, transition):
    async def run():
        fake, saved, _ = origin_fixture(tmp_path)
        await prepare_origins(fake, saved)
        pending = await fake.call('begin_saved_origins', save_name='Synthetic save',
                                  source_fingerprint=ORIGIN_FINGERPRINT, count=1)
        if transition == 'load':
            await fake.call('load_save', name='Synthetic save', pause_on_ready=True)
        elif transition == 'world_unavailable':
            fake.world_ready = False
            assert (await fake.call('ping'))['world_ready'] is False
            fake.world_ready = True
        else:
            fake.instance_id = 'new-fake-instance'
        assert not (await fake.call('ping'))['saved_origins_prepared']
        with pytest.raises(ProbeError, match='origin_context_token_invalid'):
            await fake.call('add_saved_origins', token=pending['token'], ids=saved[:1])
        with pytest.raises(ProbeError, match='origin_context_required'):
            await fake.call('dump_state', filename='stale.json')
        assert not (fake.output_directory/'stale.json').exists()
        await prepare_origins(fake, saved)
        assert (await fake.call('dump_state', filename='fresh.json'))['identity_source']['count'] == 3
    asyncio.run(run())


@pytest.mark.parametrize('params', [
    dict(source_fingerprint='a'*64), dict(source_fingerprint='sha256:'+'A'*64),
    dict(source_fingerprint='sha256:'+'a'*63), dict(source_fingerprint='sha256:'+'a'*64+'\n'),
    dict(source_fingerprint=None), dict(count=-1), dict(count=100001), dict(count=1.5),
    dict(count=True), dict(count='1'), dict(count=float('nan')), dict(count=10**1000),
    dict(save_name='../Synthetic save'), dict(save_name='Synthetic save.'), dict(save_name='bad\tname'),
    dict(extra=True),
])
def test_origin_begin_validates_entire_request_before_replacing_pending_state(tmp_path, params):
    async def run():
        fake, _, _ = origin_fixture(tmp_path)
        await fake.call('load_save', name='Synthetic save')
        valid = dict(save_name='Synthetic save', source_fingerprint=ORIGIN_FINGERPRINT, count=1)
        pending = await fake.call('begin_saved_origins', **valid)
        with pytest.raises(ProbeError, match='invalid_request'):
            await fake.call('begin_saved_origins', **(valid | params))
        assert (await fake.call('ping'))['saved_origins'] == pending
    asyncio.run(run())


@pytest.mark.parametrize('command', ['resolve_saved_handles', 'add_saved_origins'])
@pytest.mark.parametrize('ids', [[], ['hand:1:0:0:1:1']*129, ['char:A'], ['hand:01:0:0:1:1'],
                                ['hand:1:4294967296:0:1:1'], ['hand:0:0:0:1:1'],
                                ['hand:1:0:0:1:1', 4], 'hand:1:0:0:1:1'])
def test_origin_batches_reject_noncanonical_or_unbounded_saved_ids(tmp_path, command, ids):
    async def run():
        fake, _, _ = origin_fixture(tmp_path)
        await fake.call('load_save', name='Synthetic save')
        pending = await fake.call('begin_saved_origins', save_name='Synthetic save',
                                  source_fingerprint=ORIGIN_FINGERPRINT, count=100000)
        params = dict(ids=ids)
        if command == 'add_saved_origins':
            params['token'] = pending['token']
        with pytest.raises(ProbeError, match='invalid_request'):
            await fake.call(command, **params)
        assert (await fake.call('ping'))['saved_origins']['pending_count'] == 0
    asyncio.run(run())


def test_origin_batches_are_atomic_and_commit_requires_the_complete_count(tmp_path):
    async def run():
        fake, saved, _ = origin_fixture(tmp_path)
        with pytest.raises(ProbeError, match='origin_context_save_mismatch'):
            await fake.call('begin_saved_origins', save_name='Synthetic save',
                            source_fingerprint=ORIGIN_FINGERPRINT, count=3)
        await fake.call('load_save', name='Synthetic save')
        pending = await fake.call('begin_saved_origins', save_name='Synthetic save',
                                  source_fingerprint=ORIGIN_FINGERPRINT, count=3)
        token = pending['token']
        await fake.call('add_saved_origins', token=token, ids=saved[:1])
        with pytest.raises(ProbeError, match='origin_identity_ambiguous'):
            await fake.call('add_saved_origins', token=token, ids=[saved[1], saved[0]])
        with pytest.raises(ProbeError, match='origin_identity_ambiguous'):
            await fake.call('add_saved_origins', token=token, ids=[saved[1], saved[1]])
        assert (await fake.call('ping'))['saved_origins']['pending_count'] == 1
        with pytest.raises(ProbeError, match='origin_context_incomplete'):
            await fake.call('commit_saved_origins', token=token)
        await fake.call('add_saved_origins', token=token, ids=saved[1:])
        with pytest.raises(ProbeError, match='invalid_request'):
            await fake.call('add_saved_origins', token=token, ids=['hand:1:0:0:99:99'])
        result = await fake.call('commit_saved_origins', token=token)
        assert result['prepared'] and result['count'] == 3
        with pytest.raises(ProbeError, match='origin_context_token_invalid'):
            await fake.call('commit_saved_origins', token=token)
        newer = await fake.call('begin_saved_origins', save_name='Synthetic save',
                                source_fingerprint='sha256:'+'b'*64, count=0)
        assert newer['prepared'] and newer['source_fingerprint'] == ORIGIN_FINGERPRINT
        empty = await fake.call('commit_saved_origins', token=newer['token'])
        assert empty['prepared'] and empty['count'] == 0
        dumped = await fake.call('dump_state', filename='empty-context.json')
        assert dumped['identity_source']['matched_count'] == 0
        assert load_state(dumped['path']) == fake.state
    asyncio.run(run())


@pytest.mark.parametrize('collision', ['two_saved_one_current', 'canonical_matches_other_raw'])
def test_ambiguous_origins_fail_commit_before_publishing_a_context(tmp_path, collision):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        if collision == 'two_saved_one_current':
            fake.origin_aliases[saved[1]] = current[0]
        else:
            fake.initial_state['characters'][1]['id'] = saved[0]
        with pytest.raises(ProbeError, match='origin_identity_ambiguous'):
            await prepare_origins(fake, saved)
        assert fake._origin_committed is None
        assert fake._origin_pending['ids'] == saved
        with pytest.raises(ProbeError, match='origin_context_required'):
            await fake.call('dump_state', filename='ambiguous.json')
        assert not (fake.output_directory/'ambiguous.json').exists()
        assert fake._origin_bindings == {}
    asyncio.run(run())


def test_origin_commit_rollback_preserves_previous_context_bindings_and_pending_token(tmp_path):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        await prepare_origins(fake, saved)
        previous_context = deepcopy(fake._origin_committed)
        previous_bindings = deepcopy(fake._origin_bindings)
        pending = await fake.call('begin_saved_origins', save_name='Synthetic save',
                                  source_fingerprint='sha256:'+'b'*64, count=3)
        await fake.call('add_saved_origins', token=pending['token'], ids=saved)
        previous_pending = deepcopy(fake._origin_pending)
        fake.origin_aliases[saved[1]] = current[0]
        with pytest.raises(ProbeError, match='origin_identity_ambiguous'):
            await fake.call('commit_saved_origins', token=pending['token'])
        assert fake._origin_committed == previous_context
        assert fake._origin_bindings == previous_bindings
        assert fake._origin_pending == previous_pending
        fake.origin_aliases[saved[1]] = current[1]
        committed = await fake.call('commit_saved_origins', token=pending['token'])
        assert committed['source_fingerprint'] == 'sha256:'+'b'*64
        assert fake._origin_pending is None
    asyncio.run(run())


def test_camera_follow_metadata_is_canonical_immediately_after_commit_without_resolving_again(tmp_path, monkeypatch):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        await prepare_origins(fake, saved)
        fake.camera_follow_id = current[0]
        assert 'dump_state' not in fake.calls

        def forbidden_scan(saved):
            raise AssertionError('Camera metadata must use already verified alias bindings')

        monkeypatch.setattr(fake, '_origin_resolution', forbidden_scan)
        scene = await fake.call('get_scene_state')
        assert scene['camera_follow_id'] == saved[0]
        assert fake.camera_follow_id == current[0]
        assert (await fake.call('ping'))['saved_origins_prepared']
    asyncio.run(run())


def test_saved_alias_cache_is_kept_only_for_live_complete_current_identities(tmp_path):
    async def run():
        fake, saved, current = origin_fixture(tmp_path)
        await prepare_origins(fake, saved)
        await fake.call('dump_state', filename='first.json')
        del fake.origin_aliases[saved[0]]
        cached = await fake.call('dump_state', filename='cached.json')
        assert saved[0] in {row['id'] for row in load_state(cached['path'])['characters']}
        fake.origin_aliases[saved[0]] = current[1]
        with pytest.raises(ProbeError, match='origin_identity_ambiguous'):
            await fake.call('dump_state', filename='retargeted.json')
        assert fake._origin_bindings[current[0]] == saved[0]
        fake.state['characters'] = [fake.state['characters'][0]]
        fake.state['characters'][0]['id'] = 'char:new'
        fake.origin_aliases[saved[0]] = 'char:new'
        capture = await fake.call('dump_state', filename='replacement.json')
        assert load_state(capture['path'])['characters'][0]['id'] == saved[0]
        assert current[0] not in fake._origin_bindings and current[1] not in fake._origin_bindings
    asyncio.run(run())


def test_origin_maximum_batch_is_accepted_and_superseded_tokens_cannot_commit(tmp_path):
    async def run():
        fake, _, _ = origin_fixture(tmp_path)
        await fake.call('load_save', name='Synthetic save')
        begin = dict(save_name='Synthetic save', source_fingerprint=ORIGIN_FINGERPRINT, count=129)
        previous = await fake.call('begin_saved_origins', **begin)
        pending = await fake.call('begin_saved_origins', **begin)
        assert pending['token'] != previous['token']
        with pytest.raises(ProbeError, match='origin_context_token_invalid'):
            await fake.call('commit_saved_origins', token=previous['token'])
        ids = [f'hand:1:7:101:{index}:1001' for index in range(129)]
        added = await fake.call('add_saved_origins', token=pending['token'], ids=ids[:128])
        assert added['pending_count'] == 128
        await fake.call('add_saved_origins', token=pending['token'], ids=ids[128:])
        committed = await fake.call('commit_saved_origins', token=pending['token'])
        assert committed['count'] == 129
    asyncio.run(run())


@pytest.mark.parametrize('running', [False, True])
def test_origin_commands_require_a_paused_checkpoint_without_an_active_advance(tmp_path, running):
    async def run():
        fake, saved, _ = origin_fixture(tmp_path)
        await fake.call('load_save', name='Synthetic save')
        begin = dict(save_name='Synthetic save', source_fingerprint=ORIGIN_FINGERPRINT, count=3)
        pending = await fake.call('begin_saved_origins', **begin)
        before = deepcopy(fake._origin_pending)
        if running:
            await fake.call('set_game_speed', speed=1, preserve_pause=True)
            await fake.call('run_until', target_seconds=216060)
        else:
            await fake.call('pause', paused=False)
        for command, params in [
                ('resolve_saved_handles', dict(ids=saved)),
                ('begin_saved_origins', begin),
                ('add_saved_origins', dict(token=pending['token'], ids=saved)),
                ('commit_saved_origins', dict(token=pending['token']))]:
            with pytest.raises(ProbeError, match='busy' if running else 'invalid_request: pause'):
                await fake.call(command, **params)
        assert fake._origin_pending == before and fake._origin_committed is None
    asyncio.run(run())


def staged_camera_params(**changes):
    params = dict(camera_center=[12, 3, 9], camera_orientation=[1, 0, 0, 0],
                  camera_zoom=-70, free_camera=False, edge_scrolling=True,
                  speed=3, paused=True, camera_follow_id=None)
    params.update(changes)
    return params


@pytest.mark.parametrize('baseline', [[0, 0, 0], [2.5, 9.8, -3], [-4, 17, 5]])
def test_staged_follow_restore_uses_observed_baseline_and_never_changes_the_actor(tmp_path, baseline):
    async def run():
        fake = FakeProbe(tmp_path, camera_tracking_base_offset=baseline)
        actor = deepcopy(fake.state['characters'][0])
        requested = staged_camera_params(camera_follow_id=actor['id'])
        pending = await fake.call('prepare_scene_control', **requested)
        assert pending['prepared'] and not pending['restored']
        assert pending['camera_restore_token'] == pending['token']
        observed = [actor['position'][i]+baseline[i] for i in range(3)]
        assert pending['camera_center'] == observed
        assert pending['paused'] and pending['scene_camera_control_owned'] and not pending['edge_scrolling']
        assert pending['selected_game_speed'] == requested['speed']
        assert fake.camera_follow_offset == [0, 0, 0]
        restored = await fake.call('commit_scene_control', token=pending['token'])
        assert restored['restored'] and not restored['prepared']
        assert restored['camera_restore_token'] is None
        assert restored['camera_center'] == requested['camera_center']
        assert fake.camera_follow_offset == [wanted-base for wanted, base in zip(requested['camera_center'], observed)]
        assert not restored['scene_camera_control_owned'] and restored['edge_scrolling']
        assert fake.state['characters'][0] == actor
        with pytest.raises(ProbeError, match='camera_restore_token_invalid'):
            await fake.call('commit_scene_control', token=pending['token'])
    asyncio.run(run())


@pytest.mark.parametrize('free,zoom,paused', [(False, -30, True), (True, 30, True), (True, 0, False)])
def test_staged_unfollow_restore_holds_requested_center_then_restores_flags(tmp_path, free, zoom, paused):
    async def run():
        fake = FakeProbe(tmp_path)
        requested = staged_camera_params(free_camera=free, camera_zoom=zoom, paused=paused, edge_scrolling=False)
        prepared = await fake.call('prepare_scene_control', **requested)
        assert prepared['camera_center'] == requested['camera_center']
        assert prepared['paused'] and prepared['scene_camera_control_owned']
        result = await fake.call('commit_scene_control', token=prepared['token'])
        assert result['camera_center'] == requested['camera_center']
        assert result['free_camera'] is free and result['camera_zoom'] == zoom
        assert result['paused'] is paused and not result['edge_scrolling']
        assert not result['scene_camera_control_owned'] and result['camera_follow_id'] is None
    asyncio.run(run())


@pytest.mark.parametrize('change', [dict(camera_center=[1, 2]), dict(camera_center=[float('nan'), 0, 0]),
    dict(camera_orientation=[1, 1, 1, 1]), dict(camera_orientation=[1, 0, 0]), dict(camera_zoom=0),
    dict(speed=0), dict(speed=True), dict(paused=1), dict(edge_scrolling='true'),
    dict(camera_follow_id='missing'), dict(camera_follow_id=[]), dict(extra=True)])
def test_staged_prepare_rejects_invalid_params_before_mutating_camera_or_clock(tmp_path, change):
    async def run():
        fake = FakeProbe(tmp_path)
        before = deepcopy(fake.__dict__)
        with pytest.raises(ProbeError, match='invalid_request|not_found'):
            await fake.call('prepare_scene_control', **staged_camera_params(**change))
        for key in ('state', 'selected_speed', 'camera_center', 'camera_orientation', 'camera_zoom',
                    'camera_follow_id', 'camera_follow_offset', 'free_camera', 'edge_scrolling',
                    'camera_owned', '_camera_pending', '_camera_sequence'):
            assert fake.__dict__[key] == before[key]
    asyncio.run(run())


@pytest.mark.parametrize('field,value', [('camera_owned', False), ('edge_scrolling', True),
    ('free_camera', True), ('camera_zoom', -71), ('camera_orientation', [0, 1, 0, 0]),
    ('selected_speed', 2), ('camera_follow_id', None), ('paused', False)])
def test_staged_commit_refuses_changed_held_state_and_keeps_pending_token(tmp_path, field, value):
    async def run():
        fake = FakeProbe(tmp_path)
        pending = await fake.call('prepare_scene_control',
                                  **staged_camera_params(camera_follow_id=fake.state['characters'][0]['id']))
        expected = deepcopy(fake._camera_pending)
        if field == 'paused':
            fake.state['clock']['paused'] = value
        else:
            setattr(fake, field, value)
        with pytest.raises(ProbeError, match='camera_restore_state_changed'):
            await fake.call('commit_scene_control', token=pending['token'])
        assert fake._camera_pending == expected
    asyncio.run(run())


@pytest.mark.parametrize('transition', ['load', 'world_unavailable', 'new_instance'])
def test_staged_tokens_are_revoked_by_world_boundaries_and_second_prepare_is_busy(tmp_path, transition):
    async def run():
        fake = FakeProbe(tmp_path)
        pending = await fake.call('prepare_scene_control', **staged_camera_params())
        expected = deepcopy(fake._camera_pending)
        with pytest.raises(ProbeError, match='camera_restore_busy'):
            await fake.call('prepare_scene_control', **staged_camera_params(camera_center=[99, 0, 0]))
        assert fake._camera_pending == expected
        if transition == 'load':
            await fake.call('load_save', name='Synthetic save')
        elif transition == 'world_unavailable':
            fake.world_ready = False
            await fake.call('ping')
            fake.world_ready = True
        else:
            fake.instance_id = 'replacement-camera-instance'
        with pytest.raises(ProbeError, match='camera_restore_token_invalid'):
            await fake.call('commit_scene_control', token=pending['token'])
        assert (await fake.call('get_scene_state'))['camera_restore_token'] is None
    asyncio.run(run())
