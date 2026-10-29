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
                            'cancel_run_until', 'issue_order', 'restore_scene_control', 'run_scenario'} <= names
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
