import asyncio
from pathlib import Path

import pytest

import launcher.watchdog as module
from test_probe import make_watchdog


@pytest.mark.parametrize('error', [OSError('full diagnostic disk'), ValueError('closed diagnostic stream')])
def test_archive_and_diagnostic_failures_do_not_prevent_restart(tmp_path, monkeypatch, error):
    watchdog, _, spawned = make_watchdog(tmp_path)
    watchdog.cfg['port'] = 12345

    async def heartbeat(client, command, **params):
        return {'frame': 1, 'timestamp_ms': 1}

    def copy(source, destination, *args, **kwargs):
        raise PermissionError('synthetic locked archive evidence')

    def diagnostic(*args, **kwargs):
        raise error

    monkeypatch.setattr(module.Client, 'call', heartbeat)
    monkeypatch.setattr(module.shutil, 'copy2', copy)
    monkeypatch.setattr(module, 'print', diagnostic, raising=False)
    spawned[0].dead = True
    asyncio.run(watchdog.step())
    assert len(spawned) == 2 and not spawned[-1].dead
    assert watchdog.archive_errors[0]['operation'] == 'copy_log'
    assert (Path(watchdog.archive_path)/'reason.txt').read_text() == 'process_exit'
