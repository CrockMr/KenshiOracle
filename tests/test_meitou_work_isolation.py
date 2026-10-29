"""The supervised opt-in session never persists over player settings."""
import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from launcher.meitou_watchdog import isolated_work_config, run


def files(tmp_path):
    player, binary = tmp_path / 'player', tmp_path / 'bin'
    player.mkdir()
    binary.mkdir()
    return dict(target='meitou', port=47801, runtime=str(tmp_path / 'runtime'),
                working_directory=str(player), executable=str(binary / 'MeitouClient.exe'),
                oracle_output=str(tmp_path / 'dumps'), arguments=[])


def test_copies_player_settings_to_private_first_choice_directory(tmp_path):
    cfg = files(tmp_path)
    original = deepcopy(cfg)
    player = Path(cfg['working_directory']) / 'meitou.user.json'
    player.write_bytes(b'{"fpsLimit":47}\r\n')
    result = isolated_work_config(cfg)
    private = Path(result['working_directory']) / 'meitou.user.json'
    assert private.read_bytes() == player.read_bytes()
    private.write_bytes(b'{"fpsLimit":30}')
    assert player.read_bytes() == b'{"fpsLimit":47}\r\n'
    assert cfg == original


def test_falls_back_to_executable_settings_without_writing_them(tmp_path):
    cfg = files(tmp_path)
    player = Path(cfg['executable']).parent / 'meitou.user.json'
    player.write_bytes(b'{"vsync":true}')
    result = isolated_work_config(cfg)
    assert (Path(result['working_directory']) / player.name).read_bytes() == player.read_bytes()


def test_missing_settings_create_private_defaults_not_a_player_file(tmp_path):
    cfg = files(tmp_path)
    result = isolated_work_config(cfg)
    assert (Path(result['working_directory']) / 'meitou.user.json').read_bytes() == b'{}\n'
    assert not (Path(cfg['working_directory']) / 'meitou.user.json').exists()
    assert not (Path(cfg['executable']).parent / 'meitou.user.json').exists()


def test_oversize_settings_are_refused_before_private_file_write(tmp_path):
    cfg = files(tmp_path)
    player = Path(cfg['working_directory']) / 'meitou.user.json'
    original = b'x' * (1024 * 1024 + 1)
    player.write_bytes(original)
    with pytest.raises(RuntimeError, match='size limit'):
        isolated_work_config(cfg)
    assert player.read_bytes() == original
    assert not (Path(cfg['runtime']) / 'game-work/meitou.user.json').exists()


def test_supervisor_receives_opt_in_arguments_and_isolated_workdir(tmp_path, monkeypatch):
    import launcher.watchdog as watchdog
    import psutil
    cfg = files(tmp_path)
    observed = []

    class FakeWatchdog:
        def __init__(self, config, spawn):
            observed.append(config)

        async def run(self):
            return

    monkeypatch.setattr(watchdog, 'Watchdog', FakeWatchdog)
    monkeypatch.setattr(psutil, 'process_iter', lambda _: [])
    asyncio.run(run(cfg))
    assert observed[0]['working_directory'] == str(Path(cfg['runtime']) / 'game-work')
    assert observed[0]['arguments'][:3] == ['--oracle', '--oracle-port', '47801']
    assert observed[0]['arguments'][-2:] == ['--oracle-output', str(Path(cfg['oracle_output']).resolve())]
    assert (Path(observed[0]['working_directory']) / 'meitou.user.json').is_file()
