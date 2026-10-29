"""Exercise the actual MCP stdio server against an isolated synthetic game."""
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fake_probe import FakeProbe, sample_state
from oracle_schema import load_state, canonical_bytes
from probe import config
from launcher.watchdog import Watchdog


def scenario():
    return dict(schema_version='0.1', name='mcp-fixture', save='fixture-save', speed=1, repeat=3,
                actions=[dict(at=0, command='issue_order', params=dict(type='move',
                    character_id=sample_state()['characters'][0]['id'], position=[15, 0, 0]))],
                checkpoints=[dict(at=0, name='before'), dict(at=30, name='after')])


def result(response):
    assert not response.isError, response.content
    if response.structuredContent is not None:
        return response.structuredContent
    return json.loads(response.content[0].text)


def test_stdio_oracle_load_dump_run_and_scenario(tmp_path):
    async def run():
        async with FakeProbe(tmp_path / 'native') as fake:
            path = tmp_path / 'scenario.json'
            path.write_text(json.dumps(scenario()), encoding='utf-8')
            cfg = tmp_path / 'config.json'
            cfg.write_text(json.dumps(dict(port=fake.port, timeout=2, load_timeout=2,
                run_until_timeout=2, scenario_timeout=15, runtime=str(tmp_path/'runtime'),
                runs=str(tmp_path/'runs'), oracle_output=str(fake.output_directory))), encoding='utf-8')
            params = StdioServerParameters(command=sys.executable,
                args=[str(Path('mcp-server/server.py').resolve())],
                env=dict(os.environ, KENSHI_PROBE_CONFIG=str(cfg)))
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    assert tools['get_frame_stats'].inputSchema['properties']['detail']['default'] == 'aggregates'
                    assert tools['restore_scenario'].inputSchema['properties']['save']['default'] is None
                    assert 'save' not in tools['restore_scenario'].inputSchema.get('required', [])
                    assert {'prepare_scene_control', 'commit_scene_control', 'restore_scene_control'} <= tools.keys()
                    assert tools['commit_scene_control'].inputSchema['properties']['token']['type'] == 'string'
                    assert result(await session.call_tool('ping', {}))['schema_version'] == '0.1'
                    loaded = result(await session.call_tool('load_save', dict(name='fixture-save', lock_edge=True)))
                    assert loaded['accepted'] and loaded['ready']['paused']
                    for _ in range(2):
                        capture = result(await session.call_tool('dump_state', {}))
                        data = Path(capture['path']).read_bytes()
                        assert data == canonical_bytes(load_state(capture['path']))
                    clock = result(await session.call_tool('get_clock', {}))
                    assert clock['speed'] == 0
                    scene = result(await session.call_tool('get_scene_state', {}))
                    assert scene['selected_game_speed'] is None
                    result(await session.call_tool('set_game_speed', dict(speed=1, preserve_pause=True)))
                    advanced = result(await session.call_tool('run_until',
                        dict(target_seconds=clock['elapsed_seconds']+1, timeout_seconds=2)))
                    assert advanced['status'] == 'completed' and advanced['clock']['paused']
                    # Release the intentionally acquired standalone load lock before
                    # capturing the scenario's original controls.
                    result(await session.call_tool('set_camera_free', dict(enabled=False, release_edge=True)))
                    completed = result(await session.call_tool('run_scenario', dict(path=str(path))))
                    assert completed['status'] == 'completed' and completed['restored']
                    report = json.loads(Path(completed['report']).read_text(encoding='utf-8'))
                    assert len(report['executions']) == 3
                    assert report['variability']['after']['variable_field_count'] == 0
                    assert fake.loads == ['fixture-save'] * 5  # standalone + 3 repetitions + cleanup
                    paths = [Path(row['checkpoints'][1]['path']) for row in report['executions']]
                    assert paths[0].read_bytes() == paths[1].read_bytes() == paths[2].read_bytes()
                    invalid = await session.call_tool('issue_order', dict(type='attack', target_id='missing'))
                    assert invalid.isError
                    assert result(await session.call_tool('restore_scenario', {}))['reason'] == 'already_restored'
                    # An explicit source is needed when the captured controls
                    # belonged to a different save. Keep the original evidence.
                    record = tmp_path / 'runtime' / 'oracle-restoration.json'
                    guard = json.loads(record.read_text(encoding='utf-8'))
                    guard['restore_required'] = True
                    record.write_text(json.dumps(guard), encoding='utf-8')
                    before = record.read_bytes()
                    count = len(fake.requests)
                    rejected = await session.call_tool('restore_scenario', dict(save='../invalid'))
                    assert rejected.isError and len(fake.requests) == count
                    assert record.read_bytes() == before
                    recovered = result(await session.call_tool('restore_scenario', dict(save='original-view-save')))
                    assert recovered['restored'] and recovered['recovery_save'] == 'original-view-save'
                    assert fake.loads[-1] == 'original-view-save'
                    final_guard = json.loads(record.read_text(encoding='utf-8'))
                    assert final_guard['save'] == 'fixture-save'
                    assert final_guard['controls'] == guard['controls']
                    assert final_guard['recovery_save'] == 'original-view-save'
                    assert final_guard['restore_required'] is False
                    # The public restoration tool retains the native top-level
                    # result while exposing its verified two-stage observations.
                    scene = result(await session.call_tool('get_scene_state', {}))
                    from oracle_runner import control_params
                    controls = control_params(scene)
                    first = len(fake.requests)
                    restored = result(await session.call_tool('restore_scene_control', controls))
                    assert restored['restored'] and restored['pose_verified_in_pause']
                    assert restored['scene']['scene_camera_control_owned'] is False
                    commands = [row['command'] for row in fake.requests[first:]]
                    assert commands.count('prepare_scene_control') == 1
                    assert commands.count('commit_scene_control') == 1
                    assert 'restore_scene_control' not in commands
                    first = len(fake.requests)
                    invalid = await session.call_tool('commit_scene_control', dict(token='\n'))
                    assert invalid.isError and len(fake.requests) == first
    asyncio.run(run())


def test_watchdog_passes_scoped_output_and_port_without_mutating_environment(tmp_path, monkeypatch):
    seen = {}
    class Process:
        pid = 1
        def poll(self):
            return None
    def spawn(args, **kwargs):
        seen.update(kwargs)
        return Process()
    monkeypatch.setenv('KENSHI_PROBE_PORT', 'old')
    cfg = dict(executable='fixture.exe', runtime=str(tmp_path/'runtime'),
               oracle_output=str(tmp_path/'snapshots'), port=48123)
    Watchdog(cfg, spawn=spawn).start()
    assert seen['env']['KENSHI_PROBE_PORT'] == '48123'
    assert seen['env']['KENSHI_ORACLE_OUTPUT'] == str((tmp_path/'snapshots').resolve())
    assert os.environ['KENSHI_PROBE_PORT'] == 'old'
    assert (tmp_path/'snapshots').is_dir()


def test_oracle_paths_resolve_relative_to_config_not_process_cwd(tmp_path):
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps(dict(oracle_output='native', runs='results', runtime='runtime')))
    value = config(cfg)
    assert value['oracle_output'] == str(tmp_path/'native')
    assert value['runs'] == str(tmp_path/'results')
