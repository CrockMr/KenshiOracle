import asyncio
import json
import os
import sys
from pathlib import Path
import pytest
from probe import Client, ProbeError, read_runtime_state
from fake_plugin import FakePlugin
from launcher.watchdog import Watchdog
import server


def test_fragmented_protocol_and_commands():
    async def run():
        async with FakePlugin() as fake:
            c = Client(fake.port)
            assert (await c.call('ping'))['frame'] == 1
            assert (await c.call('get_frame_stats', n=50))['count'] == 50
            assert len((await c.call('list_characters', limit=1))['characters']) == 1
            with pytest.raises(ProbeError, match='unsupported'):
                await c.call('load_save', name='test')
    asyncio.run(run())


def test_scene_thread_details_option_is_validated_and_forwarded(monkeypatch):
    calls=[]
    async def fake(command,**params):calls.append((command,params));return params
    monkeypatch.setattr(server,'call',fake)
    assert asyncio.run(server.get_scene_state(True))==dict(thread_details=True)
    assert calls==[('get_scene_state',dict(thread_details=True))]
    with pytest.raises(ValueError):asyncio.run(server.get_scene_state('yes'))


def test_speed_pause_option_is_explicit_and_validated_before_transport(monkeypatch):
    calls = []
    async def fake(command, **params):
        calls.append((command, params))
        return params
    monkeypatch.setattr(server, 'call', fake)
    assert asyncio.run(server.set_game_speed(1)) == dict(speed=1)
    assert asyncio.run(server.set_game_speed(2, True)) == dict(speed=2, preserve_pause=True)
    for invalid in ('true', 1, None):
        with pytest.raises(ValueError):
            asyncio.run(server.set_game_speed(1, invalid))
    with pytest.raises(ValueError):
        asyncio.run(server.set_game_speed(0, True))
    assert calls == [('set_game_speed', dict(speed=1)),
                     ('set_game_speed', dict(speed=2, preserve_pause=True))]


@pytest.mark.parametrize('mode,match', [('hang', 'Jeu figé'), ('wrong_id', 'Identifiant'), ('invalid', 'invalide')])
def test_failed_responses(mode, match):
    async def run():
        async with FakePlugin(mode) as fake:
            with pytest.raises(ProbeError, match=match):
                await Client(fake.port, .1).call('ping')
    asyncio.run(run())


def test_tools_against_fake(tmp_path, monkeypatch):
    async def run():
        async with FakePlugin() as fake:
            cfg = tmp_path / 'config.json'
            cfg.write_text(json.dumps(dict(port=fake.port, runtime=str(tmp_path), log=str(tmp_path/'test.log'))))
            monkeypatch.setenv('KENSHI_PROBE_CONFIG', str(cfg))
            (tmp_path/'test.log').write_text('a\nb\nc\n')
            assert (await server.ping())['plugin_version'] == 'fake'
            assert (await server.pause(False))['paused'] is False
            assert (await server.set_game_speed(5))['speed'] == 5
            assert (await server.get_frame_stats(100))['count'] == 100
            assert await server.read_log(2) == 'b\nc\n'
            assert (await server.game_status())['running'] is False
            with pytest.raises(ValueError):
                await server.list_characters(501)
            with pytest.raises(ValueError):
                await server.set_game_speed(float('nan'))
    asyncio.run(run())


def test_stdio_mcp(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        async with FakePlugin() as fake:
            cfg = tmp_path/'config.json'
            cfg.write_text(json.dumps(dict(port=fake.port)))
            env = dict(os.environ, KENSHI_PROBE_CONFIG=str(cfg))
            params = StdioServerParameters(command=sys.executable, args=[str(Path('mcp-server/server.py').resolve())], env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    names = {tool.name for tool in tools}
                    assert len(names) == len(tools)
                    assert {'heartbeat', 'ping', 'get_frame_stats', 'pause', 'set_game_speed',
                            'list_characters', 'get_scene_state', 'set_camera_free', 'list_towns',
                            'focus_town', 'prepare_town_scene', 'prepare_battle_scene',
                            'save_scene_snapshot', 'load_save', 'game_status', 'restart_game',
                            'read_log', 'get_clock', 'dump_state', 'run_until', 'run_until_status',
                            'cancel_run_until', 'issue_order', 'restore_scene_control', 'run_scenario',
                            'setup_info', 'setup_area_census', 'setup_spawn_squad', 'setup_set_relation',
                            'setup_heal'} <= names
                    assert 'setup_teleport_character' not in names
                    response = await session.call_tool('ping', {})
                    assert not response.isError
                    assert 'fake' in response.content[0].text
    asyncio.run(run())


class Process:
    pid = 42
    def __init__(self):
        self.dead = False
    def poll(self):
        return 1 if self.dead else None
    def kill(self):
        self.dead = True
    def wait(self, timeout):
        return 1


def make_watchdog(tmp_path):
    log = tmp_path/'RE_Kenshi.log'
    log.write_text('evidence')
    cfg = dict(executable='fake.exe', runtime=str(tmp_path/'runtime'), crashes=str(tmp_path/'crashes'), log=str(log), dump_directory=str(tmp_path), startup_grace=10, heartbeat_timeout=30, restart_delay=0)
    ticks = [0]
    spawned = []
    def spawn(*a, **kw):
        p = Process()
        spawned.append(p)
        return p
    w = Watchdog(cfg, spawn, lambda: ticks[0])
    w.start()
    return w, ticks, spawned


def test_watchdog_grace_and_stall(tmp_path):
    w, ticks, spawned = make_watchdog(tmp_path)
    ticks[0] = 9
    assert w.failure() is None
    ticks[0] = 31
    assert w.failure() == 'heartbeat_timeout'
    spawned[0].dead = True
    assert w.failure() == 'process_exit'


def test_watchdog_restart_archive_ack(tmp_path):
    async def run():
        async with FakePlugin() as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg['port'] = fake.port
            (tmp_path/'crash.dmp').write_bytes(b'fake dump')
            (w.runtime/'restart.request').write_text('token')
            await w.step()
            assert spawned[0].dead and len(spawned) == 2
            assert w.restart_ack == 'token'
            assert not (w.runtime/'restart.request').exists()
            archive = next((tmp_path/'crashes').iterdir())
            assert (archive/'RE_Kenshi.log').read_text() == 'evidence'
            assert (archive/'crash.dmp').read_bytes() == b'fake dump'
            assert json.loads((w.runtime/'state.json').read_text())['running']
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['exit', 'stall'])
def test_watchdog_automatic_restart(tmp_path, failure):
    async def run():
        async with FakePlugin('hang') as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg.update(port=fake.port, timeout=.03)
            ticks[0] = 31
            if failure == 'exit':
                spawned[0].dead = True
            await w.step()
            assert spawned[0].dead
            assert len(spawned) == 2
            assert w.reason == ('process_exit' if failure == 'exit' else 'heartbeat_timeout')
    asyncio.run(run())


@pytest.mark.parametrize('operation', [
    'create_directory', 'write_reason', 'stat_log', 'copy_log',
    'list_dumps', 'stat_dump', 'copy_dump',
])
def test_watchdog_restarts_after_archive_io_failure_and_keeps_partial_evidence(
        tmp_path, monkeypatch, capsys, operation):
    import launcher.watchdog as watchdog_module
    w, ticks, spawned = make_watchdog(tmp_path)
    w.cfg['port'] = 12345
    bad_dump, good_dump = tmp_path/'bad.dmp', tmp_path/'good.dmp'
    bad_dump.write_bytes(b'bad dump')
    good_dump.write_bytes(b'good dump')
    log = Path(w.cfg['log'])
    crashes = Path(w.cfg['crashes'])

    async def heartbeat(client, command, **params):
        assert client.port == 12345 and command == 'heartbeat'
        return dict(frame=1, timestamp_ms=1)

    monkeypatch.setattr(watchdog_module.Client, 'call', heartbeat)
    original_mkdir, original_write = Path.mkdir, Path.write_text
    original_stat, original_iterdir = Path.stat, Path.iterdir
    original_copy = watchdog_module.shutil.copy2

    def mkdir(path, *args, **kwargs):
        if operation == 'create_directory' and path.parent == crashes:
            raise PermissionError('synthetic archive lock')
        return original_mkdir(path, *args, **kwargs)

    def write(path, *args, **kwargs):
        if operation == 'write_reason' and path.name == 'reason.txt':
            raise PermissionError('synthetic archive lock')
        return original_write(path, *args, **kwargs)

    def file_stat(path, *args, **kwargs):
        if ((operation == 'stat_log' and path == log)
                or (operation == 'stat_dump' and path == bad_dump)):
            raise PermissionError('synthetic archive lock')
        return original_stat(path, *args, **kwargs)

    def iterdir(path):
        if operation == 'list_dumps' and path == tmp_path:
            raise PermissionError('synthetic archive lock')
        return original_iterdir(path)

    def copy(source, destination, *args, **kwargs):
        if ((operation == 'copy_log' and source == log)
                or (operation == 'copy_dump' and source == bad_dump)):
            raise PermissionError('synthetic archive lock')
        return original_copy(source, destination, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', mkdir)
    monkeypatch.setattr(Path, 'write_text', write)
    monkeypatch.setattr(Path, 'stat', file_stat)
    monkeypatch.setattr(Path, 'iterdir', iterdir)
    monkeypatch.setattr(watchdog_module.shutil, 'copy2', copy)
    spawned[0].dead = True
    asyncio.run(w.step())

    assert len(spawned) == 2 and not spawned[-1].dead
    state = json.loads((w.runtime/'state.json').read_text())
    assert state['running'] and state['reason'] == 'process_exit'
    assert len(state['archive_errors']) == 1
    assert state['archive_errors'][0]['operation'] == operation
    assert state['archive_errors'][0]['message'] == 'synthetic archive lock'
    assert operation in capsys.readouterr().err
    archive = Path(state['archive_path'])
    if operation == 'create_directory':
        assert not archive.exists()
    else:
        if operation != 'write_reason':
            assert (archive/'reason.txt').read_text() == 'process_exit'
        if operation not in ('stat_log', 'copy_log'):
            assert (archive/log.name).read_text() == 'evidence'
        if operation != 'list_dumps':
            assert (archive/'good.dmp').read_bytes() == b'good dump'
            if operation not in ('stat_dump', 'copy_dump'):
                assert (archive/'bad.dmp').read_bytes() == b'bad dump'


def test_watchdog_requested_restart_ack_survives_failed_archive_and_next_attempt_clears_errors(
        tmp_path, monkeypatch):
    import launcher.watchdog as watchdog_module
    w, ticks, spawned = make_watchdog(tmp_path)
    w.cfg['port'] = 12345

    async def heartbeat(client, command, **params):
        assert client.port == 12345 and command == 'heartbeat'
        return dict(frame=1, timestamp_ms=1)

    monkeypatch.setattr(watchdog_module.Client, 'call', heartbeat)
    original_copy = watchdog_module.shutil.copy2

    def locked(*args, **kwargs):
        raise PermissionError('synthetic locked log')

    monkeypatch.setattr(watchdog_module.shutil, 'copy2', locked)
    (w.runtime/'restart.request').write_text('token')
    asyncio.run(w.step())
    assert len(spawned) == 2 and spawned[0].dead and not spawned[1].dead
    failed_archive = Path(w.archive_path)
    assert (failed_archive/'reason.txt').read_text() == 'requested'
    state = json.loads((w.runtime/'state.json').read_text())
    assert state['restart_ack'] == 'token' and state['archive_errors']
    assert not (w.runtime/'restart.request').exists()

    monkeypatch.setattr(watchdog_module.shutil, 'copy2', original_copy)
    spawned[1].dead = True
    asyncio.run(w.step())
    assert len(spawned) == 3 and not spawned[2].dead
    state = json.loads((w.runtime/'state.json').read_text())
    assert state['running'] and state['archive_errors'] == []
    assert Path(state['archive_path']) != failed_archive
    assert (Path(state['archive_path'])/'RE_Kenshi.log').read_text() == 'evidence'
    assert (failed_archive/'reason.txt').read_text() == 'requested'


@pytest.mark.parametrize('failure', ['locked', 'missing_after_exists', 'invalid_bytes', 'oversized'])
@pytest.mark.parametrize('process_state', ['healthy', 'exited', 'stalled'])
def test_restart_request_read_failure_is_observable_and_never_blocks_health_recovery(
        tmp_path, monkeypatch, capsys, failure, process_state):
    import launcher.watchdog as watchdog_module
    w, ticks, spawned = make_watchdog(tmp_path)
    w.cfg['port'] = 12345
    request = w.runtime/'restart.request'
    request.write_bytes(b'\xff' if failure == 'invalid_bytes' else b'x'*129 if failure == 'oversized' else b'token')
    original_open = Path.open

    def open_request(path, *args, **kwargs):
        if path == request and args and args[0] == 'rb':
            if failure == 'locked':
                raise PermissionError('synthetic request sharing violation')
            if failure == 'missing_after_exists':
                raise FileNotFoundError('synthetic request removed after exists')
        return original_open(path, *args, **kwargs)

    async def heartbeat(client, command, **params):
        assert client.port == 12345 and command == 'heartbeat'
        if process_state == 'stalled':
            raise ProbeError('synthetic stalled probe')
        return dict(frame=1, timestamp_ms=1)

    monkeypatch.setattr(Path, 'open', open_request)
    monkeypatch.setattr(watchdog_module.Client, 'call', heartbeat)
    spawned[0].dead = process_state == 'exited'
    if process_state == 'stalled':
        ticks[0] = 31
    asyncio.run(w.step())
    assert len(spawned) == (1 if process_state == 'healthy' else 2)
    assert not spawned[-1].dead
    state = json.loads((w.runtime/'state.json').read_text())
    assert state['running'] and state['restart_ack'] is None
    assert state['restart_request_failures'] == 1
    assert state['restart_request_error']['operation'] == 'read_request'
    assert state['restart_request_error']['path'] == str(request)
    assert 'Watchdog restart request failed (read_request)' in capsys.readouterr().err
    if process_state != 'healthy':
        reason = 'process_exit' if process_state == 'exited' else 'heartbeat_timeout'
        assert state['reason'] == reason
        assert (Path(state['archive_path'])/'reason.txt').read_text() == reason
    else:
        assert state['reason'] is None and state['archive_path'] is None


def test_denied_request_consumption_keeps_ack_avoids_repeat_restart_and_accepts_new_token(
        tmp_path, monkeypatch, capsys):
    import launcher.watchdog as watchdog_module
    w, _, spawned = make_watchdog(tmp_path)
    w.cfg['port'] = 12345
    request = w.runtime/'restart.request'
    request.write_text('first-token', encoding='ascii')
    original_unlink = Path.unlink
    state = dict(deny=True, attempts=0)

    def unlink(path, *args, **kwargs):
        if path == request:
            state['attempts'] += 1
            if state['deny']:
                raise PermissionError('synthetic denied request unlink')
        return original_unlink(path, *args, **kwargs)

    async def heartbeat(client, command, **params):
        assert client.port == 12345 and command == 'heartbeat'
        return dict(frame=1, timestamp_ms=1)

    monkeypatch.setattr(Path, 'unlink', unlink)
    monkeypatch.setattr(watchdog_module.Client, 'call', heartbeat)
    asyncio.run(w.step())
    assert len(spawned) == 2 and w.restart_ack == 'first-token'
    published = json.loads((w.runtime/'state.json').read_text())
    assert published['running'] and published['restart_request_error']['operation'] == 'consume_request'
    assert request.read_text() == 'first-token' and state['attempts'] == 1

    asyncio.run(w.step())
    assert len(spawned) == 2 and w.restart_ack == 'first-token'
    assert state['attempts'] == 2 and w.restart_request_failures == 2
    assert 'synthetic denied request unlink' in capsys.readouterr().err
    state['deny'] = False
    request.write_text('second-token', encoding='ascii')
    asyncio.run(w.step())
    assert len(spawned) == 3 and w.restart_ack == 'second-token'
    assert not request.exists() and state['attempts'] == 3
    assert w.restart_request_error is None
    assert len(list(Path(w.cfg['crashes']).iterdir())) == 2


def test_request_consumption_preserves_a_newer_token_seen_after_restart(tmp_path, monkeypatch):
    import launcher.watchdog as watchdog_module
    w, _, spawned = make_watchdog(tmp_path)
    w.cfg['port'] = 12345
    request = w.runtime/'restart.request'
    request.write_text('first-token', encoding='ascii')
    consume = w._consume_restart_request
    replaced = False

    def newer_request(token):
        nonlocal replaced
        if not replaced:
            request.write_text('newer-token', encoding='ascii')
            replaced = True
        return consume(token)

    async def heartbeat(client, command, **params):
        assert client.port == 12345 and command == 'heartbeat'
        return dict(frame=1, timestamp_ms=1)

    monkeypatch.setattr(w, '_consume_restart_request', newer_request)
    monkeypatch.setattr(watchdog_module.Client, 'call', heartbeat)
    asyncio.run(w.step())
    assert len(spawned) == 2 and w.restart_ack == 'first-token'
    assert request.read_text() == 'newer-token'
    asyncio.run(w.step())
    assert len(spawned) == 3 and w.restart_ack == 'newer-token'
    assert not request.exists() and w.restart_request_error is None


def test_watchdog_real_fake_process(tmp_path):
    w, _, _ = make_watchdog(tmp_path)
    import subprocess
    w.cfg.update(executable=sys.executable, arguments=['-c', 'import time; time.sleep(60)'])
    w.spawn = subprocess.Popen
    w.start()
    try:
        assert w.process.poll() is None
    finally:
        w.stop()
    assert w.process.poll() is not None


def test_stale_status(tmp_path, monkeypatch):
    cfg = tmp_path/'config.json'
    cfg.write_text(json.dumps(dict(runtime=str(tmp_path))))
    monkeypatch.setenv('KENSHI_PROBE_CONFIG', str(cfg))
    (tmp_path/'state.json').write_text(json.dumps(dict(running=True, updated_at=0)))
    state = asyncio.run(server.game_status())
    assert state['watchdog_stale'] and state['running'] is None


def test_watchdog_waits_for_gameplay_at_responsive_menu(tmp_path):
    async def run():
        async with FakePlugin('menu') as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg['port'] = fake.port
            ticks[0] = 200
            await w.step()
            assert w.awaiting_gameplay
            assert len(spawned) == 1
            assert w.failure() is None
            # An unresponsive network after the last menu response must still time out.
            fake.mode = 'hang'
            w.cfg['timeout'] = .03
            ticks[0] = 240
            await w.step()
            assert len(spawned) == 2
            assert w.reason == 'heartbeat_timeout'
    asyncio.run(run())


def test_watchdog_detects_stalled_renderer_at_menu(tmp_path):
    async def run():
        async with FakePlugin('renderer_menu') as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg['port'] = fake.port
            ticks[0] = 200
            await w.step()
            assert not w.awaiting_gameplay
            assert w.heartbeat['source'] == 'render'
            assert w.heartbeat['game_frame'] == 0
            assert len(spawned) == 1
            fake.mode = 'renderer_frozen'
            ticks[0] = 231
            await w.step()
            assert len(spawned) == 2
            assert w.reason == 'heartbeat_timeout'
    asyncio.run(run())


def test_watchdog_loading_grace_is_bounded(tmp_path):
    async def run():
        async with FakePlugin('loading') as fake:
            fake.frame = 1
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg.update(port=fake.port, loading_timeout=120)
            ticks[0] = 200
            await w.step()
            ticks[0] = 240
            await w.step()
            assert len(spawned) == 1
            assert w.loading_since == 200
            ticks[0] = 321
            await w.step()
            assert len(spawned) == 2
            assert w.reason == 'heartbeat_timeout'
    asyncio.run(run())


def test_watchdog_falls_back_to_game_when_render_counter_is_zero(tmp_path):
    async def run():
        async with FakePlugin('service_zero') as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg['port'] = fake.port
            ticks[0] = 200
            await w.step()
            assert w.frame > 0 and not w.awaiting_gameplay
            assert w.heartbeat['source'] == 'game'
    asyncio.run(run())


def test_autoload_is_not_retried_after_uncertain_or_failed_mutation(tmp_path):
    async def run():
        async with FakePlugin('renderer_menu') as fake:
            w, ticks, spawned = make_watchdog(tmp_path)
            w.cfg.update(port=fake.port, startup_save='test')
            await w.step()
            await w.step()
            assert w.autoload_requested and w.autoload_error
            assert fake.calls.count('load_save') == 1
    asyncio.run(run())


def test_expired_campaign_never_starts_a_process(tmp_path):
    cfg = dict(runtime=str(tmp_path), session_until=10)
    def forbidden_spawn(*a, **kw):
        raise AssertionError('Expired campaign launched a process')
    w = Watchdog(cfg, spawn=forbidden_spawn, wall_clock=lambda: 11)
    asyncio.run(w.run())
    assert json.loads((tmp_path/'state.json').read_text())['reason'] == 'session_deadline'
    assert w.process is None


def test_campaign_deadline_stops_owned_game(tmp_path):
    w, ticks, spawned = make_watchdog(tmp_path)
    w.cfg['session_until'] = 10
    values = iter([9, 11, 11])
    w.wall_clock = lambda: next(values)
    # run owns its new fake process; no network request occurs after the deadline.
    asyncio.run(w.run())
    assert spawned[-1].dead
    assert w.reason == 'session_deadline'


@pytest.mark.parametrize('limit,filter_text', [(0, ''), (501, ''), (1, 'é'*65)])
def test_town_inventory_rejects_invalid_bounds_before_network(limit, filter_text):
    with pytest.raises(ValueError):
        asyncio.run(server.list_towns(limit, filter_text))


@pytest.mark.parametrize('name', ['', 'é'*65])
def test_town_focus_rejects_invalid_name_before_network(name):
    with pytest.raises(ValueError):
        asyncio.run(server.focus_town(name))


@pytest.mark.parametrize('enabled', [0, 1, 'false', None])
def test_camera_mode_rejects_non_boolean_before_network(enabled):
    with pytest.raises(ValueError):
        asyncio.run(server.set_camera_free(enabled))


@pytest.mark.parametrize('name', ['', 'é'*65])
def test_town_preparation_rejects_invalid_name_before_network(name):
    with pytest.raises(ValueError):
        asyncio.run(server.prepare_town_scene(name))


@pytest.mark.parametrize('template,pairs', [('', 1), ('x'*129, 1), ('samurai', 0), ('samurai', 21), ('samurai', 1.5), ('samurai', True)])
def test_battle_invalid_request_never_reaches_game(template, pairs):
    with pytest.raises(ValueError):
        asyncio.run(server.prepare_battle_scene(template, pairs))


def test_detailed_inventory_bounds_response_before_network():
    with pytest.raises(ValueError):
        asyncio.run(server.list_characters(101, True))


@pytest.mark.parametrize('args', [dict(faction_name='x'*129), dict(faction_name='a\0b'),
    dict(opponent_faction_name='enemy'), dict(opponent_template_id='x'*129)])
def test_opponent_selection_invalid_before_game(args):
    with pytest.raises(ValueError):
        asyncio.run(server.prepare_battle_scene('samurai', **args))


@pytest.mark.parametrize('name', ['KenshiProbe_validation', 'KenshiProbe_test', '',
    'KenshiProbe_test_scene_../x', 'KenshiProbe_test_scene_', 'KenshiProbe_test_scene_'+'x'*41])
def test_snapshot_namespace_protects_existing_saves_before_network(name):
    with pytest.raises(ValueError):
        asyncio.run(server.save_scene_snapshot(name))


def test_reader_recovers_from_windows_status_replace(tmp_path, monkeypatch):
    state = tmp_path/'state.json'
    state.write_text('{"pid": 42}', encoding='utf-8')
    original = Path.read_text
    attempts = []
    def transient(path, **kwargs):
        attempts.append(path)
        if len(attempts) < 3:
            raise PermissionError('replace in progress')
        return original(path, **kwargs)
    monkeypatch.setattr(Path, 'read_text', transient)
    assert asyncio.run(read_runtime_state(state)) == {'pid': 42}
    assert len(attempts) == 3


def test_reader_does_not_hide_persistent_status_failure(tmp_path, monkeypatch):
    attempts = []
    def locked(path, **kwargs):
        attempts.append(path)
        raise PermissionError('persistent lock')
    monkeypatch.setattr(Path, 'read_text', locked)
    with pytest.raises(PermissionError):
        asyncio.run(read_runtime_state(tmp_path/'state.json'))
    assert len(attempts) == 4


def test_watchdog_retries_temporary_windows_state_lock(tmp_path, monkeypatch):
    w, _, spawned = make_watchdog(tmp_path)
    original = Path.replace
    attempts = []
    def transient(path, target):
        attempts.append(path)
        if len(attempts) < 3:
            raise PermissionError('temporary sharing violation')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', transient)
    assert w.publish()
    assert len(attempts) == 3 and not spawned[0].dead


def test_watchdog_keeps_supervising_when_state_is_locked(tmp_path, monkeypatch, capsys):
    async def run():
        async with FakePlugin() as fake:
            w, _, spawned = make_watchdog(tmp_path)
            w.cfg['port'] = fake.port
            original = Path.replace
            def locked(path, target):
                raise PermissionError('persistent sharing violation')
            monkeypatch.setattr(Path, 'replace', locked)
            await w.step()
            await w.step()
            assert not spawned[0].dead and len(spawned) == 1
            assert w.publication_failures == 2
            assert capsys.readouterr().err.count('supervision continues') == 1
            monkeypatch.setattr(Path, 'replace', original)
            assert w.publish()
            state = json.loads((w.runtime/'state.json').read_text())
            assert state['running'] and state['state_publication_failures'] == 2
    asyncio.run(run())


@pytest.mark.parametrize('name,flag',[('../validation',True),('',True),('KenshiProbe_test','true'),('KenshiProbe_test',1)])
def test_load_camera_lock_rejects_invalid_name_or_wrong_type(name,flag):
    with pytest.raises(ValueError):asyncio.run(server.load_save(name,flag))


def test_load_lock_and_explicit_release_are_forwarded(monkeypatch):
    calls=[]
    async def fake(command,**params):calls.append((command,params));return params
    monkeypatch.setattr(server,'call',fake)
    assert asyncio.run(server.load_save('KenshiProbe_test',True,wait=False))==dict(name='KenshiProbe_test',lock_edge=True,pause_on_ready=True)
    assert asyncio.run(server.load_save('Oracle_city',True,wait=False))==dict(name='Oracle_city',lock_edge=True,pause_on_ready=True)
    assert asyncio.run(server.set_camera_free(False,release_edge=True))==dict(enabled=False,lock_edge=False,release_edge=True)
    with pytest.raises(ValueError):asyncio.run(server.set_camera_free(False,True,True))


def test_setup_tools_validate_before_transport_and_forward(monkeypatch):
    calls = []
    async def fake(command, **params):
        calls.append((command, params))
        return params
    monkeypatch.setattr(server, 'call', fake)
    assert asyncio.run(server.setup_info()) == {}
    asyncio.run(server.setup_area_census([1, 2, 3], 1500, 100))
    asyncio.run(server.setup_spawn_squad('squad', 'faction', [1, 2, 3], 4))
    asyncio.run(server.setup_spawn_squad('squad', 'faction', [1, 2, 3], 4, permanent=True))
    asyncio.run(server.setup_set_relation('a', 'b', -60))
    asyncio.run(server.setup_heal('hand:1:7:101:1:1001'))
    assert calls == [
        ('setup_info', {}),
        ('setup_area_census', dict(center=[1, 2, 3], radius=1500, limit=100)),
        ('setup_spawn_squad', dict(template_id='squad', faction_id='faction', position=[1, 2, 3], max_count=4)),
        ('setup_spawn_squad', dict(template_id='squad', faction_id='faction', position=[1, 2, 3], max_count=4,
                                   permanent=True)),
        ('setup_set_relation', dict(source_id='a', target_id='b', value=-60)),
        ('setup_heal', dict(character_id='hand:1:7:101:1:1001'))]
    for invalid, match in [
            (lambda: server.setup_area_census([1, 2], 10), 'center must have three numbers'),
            (lambda: server.setup_area_census([1, 2, float('inf')], 10), 'invalid position coordinate'),
            (lambda: server.setup_area_census([1, 2, 3], 0.01), 'invalid number: radius'),
            (lambda: server.setup_area_census([1, 2, 3], 10, 101), 'invalid number: limit'),
            (lambda: server.setup_area_census([1, 2, 3], 10, 1.5), 'limit must be an integer'),
            (lambda: server.setup_spawn_squad('', 'f', [0, 0, 0], 1), 'invalid string: template_id'),
            (lambda: server.setup_spawn_squad('s', 'f'*129, [0, 0, 0], 1), 'invalid string: faction_id'),
            (lambda: server.setup_spawn_squad('s', 'f', [0, 0, 0], 17), 'invalid number: max_count'),
            (lambda: server.setup_spawn_squad('s', 'f', [0, 0, 0], True), 'invalid number: max_count'),
            (lambda: server.setup_spawn_squad('s', 'f', [0, 0, 0], 1, 'yes'), 'invalid boolean: permanent'),
            (lambda: server.setup_set_relation('a', 'b', -101), 'invalid number: value'),
            (lambda: server.setup_heal('a\0b'), 'invalid string: character_id')]:
        with pytest.raises(ValueError, match=match):
            asyncio.run(invalid())
    assert len(calls) == 6


def test_load_sends_allow_setup_only_when_true(monkeypatch):
    calls = []
    async def fake(command, **params):
        calls.append((command, params))
        return params
    monkeypatch.setattr(server, 'call', fake)
    asyncio.run(server.load_save('Synthetic save', wait=False))
    asyncio.run(server.load_save('Synthetic save', wait=False, allow_setup=True))
    assert calls == [('load_save', dict(name='Synthetic save', lock_edge=False, pause_on_ready=True)),
                     ('load_save', dict(name='Synthetic save', lock_edge=False, pause_on_ready=True,
                                        allow_setup=True))]
    with pytest.raises(ValueError):
        asyncio.run(server.load_save('Synthetic save', allow_setup='true'))
    async def ignored(command, **params):
        return dict(accepted=True, name=params['name'])
    monkeypatch.setattr(server, 'call', ignored)
    with pytest.raises(ProbeError, match='allow_setup'):
        asyncio.run(server.load_save('Synthetic save', wait=False, allow_setup=True))


def test_waited_load_with_allow_setup_opens_the_setup_gate(tmp_path, monkeypatch):
    from fake_probe import FakeProbe
    async def run():
        async with FakeProbe(tmp_path/'snapshots') as fake:
            cfg = tmp_path/'config.json'
            cfg.write_text(json.dumps(dict(port=fake.port)))
            monkeypatch.setenv('KENSHI_PROBE_CONFIG', str(cfg))
            loaded = await server.load_save('Synthetic save', allow_setup=True)
            assert loaded['allow_setup'] is True and loaded['ready']['world_mutated'] is False
            gate = (await server.setup_info())['gate']
            assert gate['open'] and gate['allow_setup'] and gate['probe_loaded_save'] == 'Synthetic save'
            assert gate['refusal'] is None and gate['mutation_refusal'] is None
            assert (await server.load_save('Synthetic save'))['allow_setup'] is False
            gate = (await server.setup_info())['gate']
            assert not gate['open'] and gate['refusal']['message'] == (
                'scene setup was not enabled: load the save with allow_setup:true')
            with pytest.raises(ProbeError, match='scene setup was not enabled'):
                await server.setup_area_census([0, 0, 0], 10)
    asyncio.run(run())


G2_TEXT = "scene setup requires a world loaded by the probe's load_save"
G3_TEXT = 'scene setup was not enabled: load the save with allow_setup:true'
M1_TEXT = 'scene setup mutations require a paused world and no run_until'
M2_TEXT = 'scene setup mutations are refused while autosave is enabled'
SPAWN = dict(template_id='fixture-squad', faction_id='fixture-rival', position=[30, 0, 0], max_count=4)
RELATION = dict(source_id='fixture-rival', target_id='fixture-faction', value=-60)
HEAL = dict(character_id='hand:1:7:101:1:1001')
MUTATIONS = [('setup_spawn_squad', SPAWN), ('setup_set_relation', RELATION), ('setup_heal', HEAL)]


def setup_fake(tmp_path, allow_setup=True):
    from fake_probe import FakeProbe
    fake = FakeProbe(tmp_path/'snapshots')
    asyncio.run(fake.call('load_save', name='Synthetic save', pause_on_ready=True, allow_setup=allow_setup))
    return fake


def refusal(fake, command, params, code, message):
    from fake_probe import SetupRefusal
    with pytest.raises(SetupRefusal) as raised:
        asyncio.run(fake.call(command, **params))
    assert (raised.value.code, raised.value.message) == (code, message)


def test_fake_setup_ping_reports_capability_and_mutation_state(tmp_path):
    fake = setup_fake(tmp_path)
    status = asyncio.run(fake.call('ping'))
    assert status['capabilities'] == ['scene_setup'] and status['world_mutated'] is False
    assert status['state_schema_version'] == '0.2' and len(status['build_commit']) == 40
    assert status['world_readiness']['world_ready'] is True and 'window' not in status['world_readiness']
    asyncio.run(fake.call('setup_heal', **HEAL))
    assert asyncio.run(fake.call('ping'))['world_mutated'] is True
    asyncio.run(fake.call('load_save', name='Synthetic save', pause_on_ready=True))
    assert asyncio.run(fake.call('ping'))['world_mutated'] is False


@pytest.mark.parametrize('command,params', MUTATIONS)
def test_fake_setup_refuses_a_mutation_when_not_paused(tmp_path, command, params):
    fake = setup_fake(tmp_path)
    asyncio.run(fake.call('pause', paused=False))
    refusal(fake, command, params, 'invalid_request', M1_TEXT)
    assert asyncio.run(fake.call('setup_area_census', center=[0, 0, 0], radius=10, limit=10))['count'] == 2
    assert fake.world_mutated is False


@pytest.mark.parametrize('command,params', MUTATIONS)
def test_fake_setup_refuses_a_mutation_during_run_until(tmp_path, command, params):
    fake = setup_fake(tmp_path)
    asyncio.run(fake.call('set_game_speed', speed=1, preserve_pause=True))
    asyncio.run(fake.call('run_until', target_seconds=216033))
    fake.state['clock']['paused'] = True  # Still refused while the operation runs.
    refusal(fake, command, params, 'invalid_request', M1_TEXT)


@pytest.mark.parametrize('command,params', MUTATIONS + [
    ('setup_area_census', dict(center=[0, 0, 0], radius=10, limit=10))])
def test_fake_setup_refuses_outside_the_probe_load_epoch(tmp_path, command, params):
    from fake_probe import FakeProbe
    refusal(FakeProbe(tmp_path/'unloaded'), command, params, 'not_allowed', G2_TEXT)
    fake = setup_fake(tmp_path)
    fake.simulate_ui_load()
    refusal(fake, command, params, 'not_allowed', G2_TEXT)
    refusal(setup_fake(tmp_path, allow_setup=False), command, params, 'not_allowed', G3_TEXT)
    fake = setup_fake(tmp_path)
    fake.world_ready = False
    refusal(fake, command, params, 'world_not_ready', 'world is unavailable or a save is loading')


def test_fake_setup_ui_load_clears_the_opt_in_but_keeps_world_mutated(tmp_path):
    fake = setup_fake(tmp_path)
    asyncio.run(fake.call('setup_heal', **HEAL))
    fake.simulate_ui_load()
    info = asyncio.run(fake.call('setup_info'))
    assert info['world_mutated'] is True and info['probe_loaded_save'] is None
    assert info['gate']['allow_setup'] is False and info['gate']['refusal']['message'] == G2_TEXT


@pytest.mark.parametrize('enabled', [True, None])
@pytest.mark.parametrize('command,params', MUTATIONS)
def test_fake_setup_refuses_a_mutation_when_autosave_is_on(tmp_path, command, params, enabled):
    fake = setup_fake(tmp_path)
    fake.autosave_enabled = enabled
    refusal(fake, command, params, 'not_allowed', M2_TEXT)
    assert asyncio.run(fake.call('setup_info'))['gate']['mutation_refusal'] == dict(
        code='not_allowed', message=M2_TEXT)


@pytest.mark.parametrize('change,code,message', [
    (dict(faction_id='fixture-faction'), 'invalid_request', 'spawning into the player faction is refused'),
    (dict(position=[2001.5, 0, 0]), 'invalid_request',
     'spawn position must be within 2000 units (horizontal) of a player character'),
    (dict(max_count=17), 'invalid_request', 'invalid number: max_count'),
    (dict(max_count=1.5), 'invalid_request', 'max_count must be an integer'),
    (dict(position=[0, 0]), 'invalid_request', 'position must have three numbers'),
    (dict(template_id='absent'), 'not_found', 'template not found'),
    (dict(template_id='fixture-member'), 'invalid_request', 'template is not a SQUAD_TEMPLATE record'),
    (dict(faction_id='absent'), 'not_found', 'faction not found'),
    (dict(permanent='yes'), 'invalid_request', 'invalid boolean: permanent'),
    (dict(name_prefix='x'), 'invalid_request', 'unknown parameter: name_prefix')])
def test_fake_spawn_refusals_leave_the_world_unmutated(tmp_path, change, code, message):
    fake = setup_fake(tmp_path)
    refusal(fake, 'setup_spawn_squad', dict(SPAWN, **change), code, message)
    assert fake.world_mutated is False and len(fake.state['characters']) == 2


def test_fake_setup_checks_unknown_keys_before_the_gate_and_the_gate_before_values(tmp_path):
    from fake_probe import FakeProbe
    unloaded = FakeProbe(tmp_path/'unloaded')
    refusal(unloaded, 'setup_info', dict(extra=1), 'invalid_request', 'unknown parameter: extra')
    refusal(unloaded, 'setup_spawn_squad', dict(SPAWN, max_count=17), 'not_allowed', G2_TEXT)
    fake = setup_fake(tmp_path)
    fake.player_faction_id = 'nobody'
    refusal(fake, 'setup_area_census', dict(center=[0, 0, 0], radius=10, limit=10),
            'state_unavailable', 'player unavailable')


def test_fake_setup_commands_reply_with_contract_keys(tmp_path):
    fake = setup_fake(tmp_path)
    common = {'saved', 'world_mutated', 'gate', 'world_before', 'world_after'}
    spawned = asyncio.run(fake.call('setup_spawn_squad', **SPAWN))
    assert set(spawned) == common | {'template_id', 'faction_id', 'position', 'max_count', 'permanent',
                                     'size_multiplier', 'squad_type', 'returned_squad_id', 'returned_members',
                                     'new_loaded_count', 'new_loaded_truncated', 'rng_key'}
    assert spawned['saved'] is False and spawned['world_mutated'] is True and spawned['gate']['open']
    assert spawned['new_loaded_count'] == len(spawned['returned_members']) == 4
    assert [row['template_id'] for row in spawned['returned_members']] == ['fixture-leader'] + ['fixture-member']*3
    assert {row['squad_id'] for row in spawned['returned_members']} == {spawned['returned_squad_id']}
    assert set(spawned['returned_members'][0]) == {'id', 'template_id', 'faction_id', 'squad_id', 'position',
                                                   'dead', 'unconscious', 'medical'}
    census = asyncio.run(fake.call('setup_area_census', center=[0, 0, 0], radius=1500, limit=3))
    assert census['count'] == 6 and census['truncated'] and len(census['characters']) == 3
    assert census['player_count'] == 2 and census['alive_count'] == 6
    assert [row['distance_xz'] for row in census['characters']] == [0, 1, 30]
    member = spawned['returned_members'][1]['id']
    healed = asyncio.run(fake.call('setup_heal', character_id=member))
    assert set(healed) == common | {'character_id', 'before', 'after'}
    assert healed['before']['parts'][0] == dict(id='fixture-head:neither', flesh=75, stun=10, max=100)
    assert healed['after']['parts'][0] == dict(id='fixture-head:neither', flesh=100, stun=0, max=100)
    relation = asyncio.run(fake.call('setup_set_relation', **RELATION))
    assert relation['source_to_target']['after'] == dict(relation=-60, is_enemy=True, at_war=None)
    assert relation['target_to_source']['after']['relation'] == 0
    assert relation['changed_cells'] == 1 and relation['faction_count'] == 2
    assert relation['changes'][0]['source_id'] == 'fixture-rival'
    refusal(fake, 'setup_set_relation', dict(RELATION, target_id='fixture-rival'),
            'invalid_request', 'source and target must differ')
    fake.state['characters'][0]['state'] = 'dead'
    refusal(fake, 'setup_heal', HEAL, 'invalid_request', 'character is dead')
    refusal(fake, 'setup_heal', dict(character_id='absent'), 'not_found', 'character is not loaded')
    with pytest.raises(ProbeError, match='not_implemented'):
        asyncio.run(fake.call('setup_teleport_character'))


def test_fake_snapshot_is_refused_while_mutated_and_orders_stay_id_only(tmp_path):
    fake = setup_fake(tmp_path)
    with pytest.raises(ProbeError, match='not_implemented'):
        asyncio.run(fake.call('save_scene_snapshot', name='KenshiProbe_test_scene_a'))
    asyncio.run(fake.call('setup_set_relation', **RELATION))
    refusal(fake, 'save_scene_snapshot', dict(name='KenshiProbe_test_scene_a'),
            'not_allowed', 'the world was changed by scene setup; reload it before saving')
    for alias in (dict(squad_alias='bandits'), dict(target_alias='player')):
        with pytest.raises(ProbeError, match='invalid_params'):
            asyncio.run(fake.call('issue_order', type='attack', character_id='hand:1:7:101:1:1001',
                                  target_id='hand:1:7:101:2:1002', **alias))


def test_fake_setup_refusal_crosses_the_wire_with_the_contract_code_and_message(tmp_path):
    from fake_probe import FakeProbe
    async def run():
        async with FakeProbe(tmp_path/'snapshots') as fake:
            client = Client(fake.port, 1)
            with pytest.raises(ProbeError) as raised:
                await client.call('setup_heal', **HEAL)
            assert str(raised.value) == str(dict(code='not_allowed', message=G2_TEXT))
    asyncio.run(run())
