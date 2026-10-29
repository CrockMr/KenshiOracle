"""Real reader/runner/MCP integration using exclusively synthetic FCS bytes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from fake_probe import FakeProbe, sample_state
from oracle_origins import read_saved_origins
from oracle_runner import OracleSession, ScenarioError, execute_scenario
from oracle_schema import canonical_bytes, load_state
from probe import ProbeError
from test_oracle_origins import handle, record, write_source


SAVE_NAME = 'Synthetic save'


def source_fixture(tmp_path, *, probe_class=FakeProbe, character_count=2):
    root = tmp_path/'synthetic-saves'
    root.mkdir()
    records = [record(30, 'collection', instances=[
        (f'instance-{index}', [f'character-{index}']) for index in range(character_count)])]
    records += [record(36, f'character-{index}', int=handle(slot=index+1, object_serial=1000+index))
                for index in range(character_count)]
    folder = write_source(root, platoons={'synthetic.platoon': records})
    manifest = read_saved_origins(root, SAVE_NAME)
    saved = [row['saved_id'] for row in manifest['characters'][:2]] + [manifest['squads'][0]['saved_id']]
    raw = ['char:A', 'char:B', 'squad:fixture']
    state = sample_state()
    for index, character in enumerate(state['characters']):
        character.update(id=raw[index], squad_id=raw[2])
    state['characters'][0]['order'] = dict(type='attack', target_id=raw[1], position=None)
    state['squads'][0].update(id=raw[2], members=raw[:2], leader_id=raw[0])
    fake = probe_class(tmp_path/'native', state, require_saved_origins=True,
                       save_root=root, origin_aliases=dict(zip(saved, raw)))
    cfg = dict(runtime=str(tmp_path/'runtime'), runs=str(tmp_path/'runs'),
               oracle_output=str(fake.output_directory), timeout=2, load_timeout=3,
               run_until_timeout=2, scenario_timeout=10)
    return fake, cfg, manifest, saved, folder


def source_bytes(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob('*') if path.is_file()}


def read_report(cfg):
    reports = list(Path(cfg['runs']).glob('*/*/report.json'))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding='utf-8'))


def read_guard(cfg):
    return json.loads((Path(cfg['runtime'])/'oracle-restoration.json').read_text(encoding='utf-8'))


def scenario(saved):
    return dict(schema_version='0.1', name='origin-integration', save=SAVE_NAME, speed=1,
                repeat=3, actions=[dict(at=0, command='issue_order', params=dict(
                    type='attack', character_id=saved[0], target_id=saved[1]))],
                checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])


def test_session_load_parses_real_synthetic_fcs_and_attaches_only_external_provenance(tmp_path):
    async def run():
        fake, cfg, manifest, saved, folder = source_fixture(tmp_path)
        before = source_bytes(folder)
        session = OracleSession(cfg, fake)
        loaded = await session.load(SAVE_NAME)
        assert loaded['saved_origins']['prepared']
        assert loaded['saved_origins']['source_fingerprint'] == manifest['fingerprint']
        assert loaded['saved_origins']['count'] == 3
        state, capture = await session.dump()
        assert [row['id'] for row in state['characters']] == saved[:2]
        assert state['characters'][0]['order']['target_id'] == saved[1]
        assert state['squads'][0]['id'] == saved[2]
        assert state['squads'][0]['members'] == saved[:2]
        assert state['squads'][0]['leader_id'] == saved[0]
        assert all(row['squad_id'] == saved[2] for row in state['characters'])
        assert capture['identity_source'] == dict(save_name=SAVE_NAME,
            source_fingerprint=manifest['fingerprint'], count=3, matched_count=3,
            remapped_characters=2, remapped_squads=1)
        assert 'identity_source' not in state
        payload = Path(capture['path']).read_bytes()
        assert payload == canonical_bytes(state) == Path(capture['source_path']).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == capture['sha256']
        assert source_bytes(folder) == before
        assert [request['command'] for request in fake.requests].count('commit_saved_origins') == 1
    asyncio.run(run())


class ShiftingRawIdentities(FakeProbe):
    async def call(self, command, **params):
        result = await super().call(command, **params)
        if command == 'load_save':
            epoch = len(self.loads)
            previous = [row['id'] for row in self.state['characters']] + [self.state['squads'][0]['id']]
            current = [f'char:A:load:{epoch}', f'char:B:load:{epoch}', f'squad:load:{epoch}']
            changed = dict(zip(previous, current))
            for character in self.state['characters']:
                character['id'] = changed[character['id']]
                character['squad_id'] = changed[character['squad_id']]
                if character['order'] is not None:
                    target = character['order']['target_id']
                    character['order']['target_id'] = changed.get(target, target)
            for squad in self.state['squads']:
                squad['id'] = changed[squad['id']]
                squad['members'] = [changed[value] for value in squad['members']]
                squad['leader_id'] = changed[squad['leader_id']]
            # initial_state is intentionally unchanged across the synthetic
            # reload, so map the same saved identities to this epoch explicitly.
            self.origin_aliases = dict(zip(self.origin_aliases, current))
            self.raw_epochs = getattr(self, 'raw_epochs', []) + [tuple(current)]
        return result


def test_three_repetitions_reload_shifted_raw_handles_but_export_stable_saved_ids(tmp_path):
    async def run():
        fake, cfg, manifest, saved, folder = source_fixture(tmp_path, probe_class=ShiftingRawIdentities)
        before = source_bytes(folder)
        await OracleSession(cfg, fake).load(SAVE_NAME, lock_edge=False)
        await fake.call('set_game_speed', speed=1, preserve_pause=True)
        fake.camera_follow_id = fake.origin_aliases[saved[0]]
        assert (await fake.call('get_scene_state'))['camera_follow_id'] == saved[0]
        assert 'dump_state' not in fake.calls
        result = await execute_scenario(scenario(saved), cfg, client=fake)
        report = read_report(cfg)
        assert result['restored'] and report['status'] == 'completed'
        assert report['source_fingerprint'] == manifest['fingerprint']
        assert len(fake.raw_epochs) == len(set(fake.raw_epochs)) == 5  # preload, 3 runs, cleanup
        for checkpoint in ('initial', 'later'):
            captures = [next(c for c in execution['checkpoints'] if c['name'] == checkpoint)
                        for execution in report['executions']]
            assert len({Path(capture['path']).read_bytes() for capture in captures}) == 1
            assert report['variability'][checkpoint]['variable_field_count'] == 0
            for capture in captures:
                state = load_state(capture['path'])
                assert [row['id'] for row in state['characters']] == saved[:2]
                assert state['characters'][0]['order']['target_id'] == saved[1]
                assert state['squads'][0]['members'] == saved[:2]
                assert capture['identity_source']['source_fingerprint'] == manifest['fingerprint']
        assert source_bytes(folder) == before
        assert read_guard(cfg)['restore_required'] is False
        assert report['restoration']['verified'] is True
        assert read_guard(cfg)['controls']['camera_follow_id'] == saved[0]
        assert report['restoration']['scene']['camera_follow_id'] == saved[0]
        assert fake.camera_follow_id == fake.raw_epochs[-1][0] != saved[0]
        restore = [row for row in fake.requests if row['command'] == 'prepare_scene_control']
        assert restore[-1]['params']['camera_follow_id'] == saved[0]
    asyncio.run(run())


@pytest.mark.parametrize('context', ['unprepared', 'different_save'])
def test_scenario_requires_prepared_context_for_the_same_save_before_guard_or_mutation(tmp_path, context):
    async def run():
        fake, cfg, _, saved, _ = source_fixture(tmp_path)
        value = scenario(saved)
        if context == 'different_save':
            await OracleSession(cfg, fake).load(SAVE_NAME, lock_edge=False)
            await fake.call('set_game_speed', speed=1, preserve_pause=True)
            value['save'] = 'Other synthetic save'
        before = len(fake.requests)
        loads = fake.loads[:]
        with pytest.raises(ScenarioError, match=r'Load this scenario save through load_save\(wait=True\)'):
            await execute_scenario(value, cfg, client=fake)
        assert [row['command'] for row in fake.requests[before:]] == ['ping']
        assert fake.loads == loads
        assert not (Path(cfg['runtime'])/'oracle-restoration.json').exists()
        report = read_report(cfg)
        assert report['status'] == 'failed' and report['executions'] == []
        assert 'control_capture_observations' not in report
        assert not list(fake.output_directory.glob('*.json'))
    asyncio.run(run())


def test_configured_root_mismatch_is_refused_before_any_game_mutation(tmp_path):
    async def run():
        fake, cfg, _, _, _ = source_fixture(tmp_path)
        cfg['save_root'] = str(tmp_path/'different-root')
        with pytest.raises(ScenarioError, match='Configured save_root differs'):
            await OracleSession(cfg, fake).load(SAVE_NAME)
        assert fake.loads == [] and fake.calls == ['ping']
        assert not fake._origin_committed and not fake._origin_pending
    asyncio.run(run())


def test_source_modified_during_load_never_begins_an_identity_context(tmp_path):
    class ChangedDuringLoad(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'load_save':
                source = Path(self.save_root)/SAVE_NAME/'quick.save'
                source.write_bytes(source.read_bytes()+b'synthetic concurrent save update')
            return result

    async def run():
        fake, cfg, _, _, _ = source_fixture(tmp_path, probe_class=ChangedDuringLoad)
        session = OracleSession(cfg, fake)
        with pytest.raises(ScenarioError, match='source_changed'):
            await session.load(SAVE_NAME)
        assert fake.loads == [SAVE_NAME]
        assert 'begin_saved_origins' not in fake.calls and session.identity_source is None
        with pytest.raises(ProbeError, match='origin_context_required'):
            await session.dump()
        assert not list(fake.output_directory.glob('*.json'))
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['pending_count', 'second_chunk_count', 'restart'])
def test_registration_failure_cannot_publish_a_partial_saved_identity_context(tmp_path, failure):
    class BrokenRegistration(FakeProbe):
        async def call(self, command, **params):
            result = await super().call(command, **params)
            if command == 'begin_saved_origins' and failure == 'pending_count':
                result['expected_count'] += 1
            if command == 'add_saved_origins':
                if failure == 'second_chunk_count' and result['pending_count'] > 128:
                    result['pending_count'] -= 1
                if failure == 'restart':
                    self.instance_id = 'synthetic-replacement-instance'
            return result

    async def run():
        fake, cfg, _, _, _ = source_fixture(tmp_path, probe_class=BrokenRegistration, character_count=129)
        session = OracleSession(cfg, fake)
        expected = {'pending_count': 'inconsistent pending', 'second_chunk_count': 'inconsistent saved identity batch',
                    'restart': 'Game restarted'}[failure]
        with pytest.raises(ScenarioError, match=expected):
            await session.load(SAVE_NAME)
        assert session.identity_source is None
        assert 'commit_saved_origins' not in fake.calls
        assert (await fake.call('ping'))['saved_origins_prepared'] is False
        with pytest.raises(ProbeError, match='origin_context_required'):
            await session.dump()
        assert not list(fake.output_directory.glob('*.json'))
    asyncio.run(run())


@pytest.mark.parametrize('restoration_fails', [False, True])
def test_changed_source_between_repetitions_is_failed_and_guard_matches_cleanup_scope(tmp_path, restoration_fails):
    class ChangedBetweenRuns(FakeProbe):
        async def call(self, command, **params):
            if command == 'load_save' and getattr(self, 'changed', False):
                self.loads_after_change = getattr(self, 'loads_after_change', 0)+1
                if restoration_fails and self.loads_after_change == 2:
                    raise ProbeError('synthetic cleanup load failed')
            result = await super().call(command, **params)
            if command == 'dump_state':
                self.dump_count = getattr(self, 'dump_count', 0)+1
                if self.dump_count == 2:
                    # Change only a human-readable name, leaving valid FCS and
                    # every saved identity unchanged. The source hash must differ.
                    source = Path(self.save_root)/SAVE_NAME/'quick.save'
                    source.write_bytes(source.read_bytes().replace(b'Synthetic record', b'Synthetic change', 1))
                    self.changed = True
            return result

    async def run():
        fake, cfg, manifest, saved, _ = source_fixture(tmp_path, probe_class=ChangedBetweenRuns)
        await OracleSession(cfg, fake).load(SAVE_NAME, lock_edge=False)
        await fake.call('set_game_speed', speed=1, preserve_pause=True)
        with pytest.raises(ScenarioError, match='Starting save changed between scenario repetitions'):
            await execute_scenario(scenario(saved), cfg, client=fake)
        report = read_report(cfg)
        assert report['status'] == 'failed' and report['source_fingerprint'] == manifest['fingerprint']
        assert len(report['executions']) == 2
        assert report['executions'][0]['status'] == 'completed'
        assert report['executions'][1]['status'] == 'failed'
        assert report['executions'][1]['checkpoints'] == []
        changed_source = report['executions'][1]['load']['saved_origins']['source_fingerprint']
        assert changed_source != manifest['fingerprint']
        assert read_guard(cfg)['restore_required'] is restoration_fails
        if restoration_fails:
            assert 'synthetic cleanup load failed' in report['restoration_error']
        else:
            assert report['restoration']['verified'] is True
    asyncio.run(run())


def test_stdio_mcp_load_and_dump_prepare_context_from_synthetic_fcs_files(tmp_path):
    def value(response):
        assert not response.isError, response.content
        return response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)

    async def run():
        fake, cfg, manifest, saved, folder = source_fixture(tmp_path)
        before = source_bytes(folder)
        async with fake:
            cfg['port'] = fake.port
            config_file = tmp_path/'config.json'
            config_file.write_text(json.dumps(cfg), encoding='utf-8')
            parameters = StdioServerParameters(command=sys.executable,
                args=[str(Path('mcp-server/server.py').resolve())],
                env=dict(os.environ, KENSHI_PROBE_CONFIG=str(config_file)))
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    loaded = value(await session.call_tool('load_save', dict(name=SAVE_NAME)))
                    assert loaded['accepted'] and loaded['ready']['paused']
                    status = value(await session.call_tool('ping', {}))
                    assert status['saved_origins_prepared']
                    assert status['saved_origins']['source_fingerprint'] == manifest['fingerprint']
                    capture = value(await session.call_tool('dump_state', {}))
                    state = load_state(capture['path'])
                    assert [row['id'] for row in state['characters']] == saved[:2]
                    assert capture['identity_source']['source_fingerprint'] == manifest['fingerprint']
                    assert capture['identity_source']['matched_count'] == 3
                    assert Path(capture['path']).read_bytes() == canonical_bytes(state)
            assert fake.loads == [SAVE_NAME]
            assert fake.calls.count('begin_saved_origins') == fake.calls.count('commit_saved_origins') == 1
        assert source_bytes(folder) == before
    asyncio.run(run())
