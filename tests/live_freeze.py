"""Suspend only the supervised disposable process; always resume if recovery fails."""

# Resolve shared oracle/research imports without a private PYTHONPATH.
import sys
from pathlib import Path
for _folder in ('mcp-server', 'tools/research', 'tests'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / _folder))
import asyncio
import json
import os
import time
from pathlib import Path
import psutil
from probe import config


async def main():
    cfg = config()
    path = Path(cfg['runtime'])/'state.json'
    before = json.loads(path.read_text())
    if not before.get('running') or time.time()-before['updated_at'] > 5:
        raise RuntimeError('Active watchdog required')
    process = psutil.Process(before['pid'])
    expected = os.path.normcase(os.path.realpath(cfg['executable']))
    if os.path.normcase(os.path.realpath(process.exe())) != expected:
        raise RuntimeError('Process executable does not match project config')
    created = process.create_time()
    if time.time()-created < cfg.get('startup_grace', 120)+1:
        raise RuntimeError('Wait until startup grace expires before freeze test')
    process.suspend()
    print(json.dumps(dict(suspended_pid=process.pid)), flush=True)
    try:
        deadline = time.monotonic()+cfg.get('heartbeat_timeout', 30)+30
        while time.monotonic() < deadline:
            state = json.loads(path.read_text())
            if state.get('running') and state['pid'] != process.pid and state.get('reason') == 'heartbeat_timeout':
                archive = sorted(Path(cfg['crashes']).iterdir())[-1]
                if (archive/'reason.txt').read_text() != 'heartbeat_timeout':
                    raise RuntimeError('Freeze archive missing')
                print(json.dumps(dict(recovered_state=state, archive=str(archive))), flush=True)
                return
            await asyncio.sleep(1)
        raise TimeoutError('Recovery from suspended game not observed')
    finally:
        try:
            if process.is_running() and process.create_time() == created:
                process.resume()
        except psutil.NoSuchProcess:
            pass


if __name__ == '__main__':
    asyncio.run(main())
