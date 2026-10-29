"""Read-only observer of an already-triggered watchdog recovery."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from probe import config


async def main(old_pid, reason):
    cfg = config()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        state = json.loads((Path(cfg['runtime'])/'state.json').read_text())
        if state.get('pid') != old_pid and state.get('running') and state.get('reason') == reason:
            archive = sorted(Path(cfg['crashes']).iterdir())[-1]
            if (archive/'reason.txt').read_text() != reason:
                raise RuntimeError('Recovery archive reason mismatch')
            print(json.dumps(dict(previous_pid=old_pid, recovered_state=state, archive=str(archive))), flush=True)
            return
        await asyncio.sleep(.5)
    raise TimeoutError('Watchdog recovery not observed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('old_pid', type=int)
    p.add_argument('reason', choices=['process_exit', 'heartbeat_timeout'])
    args = p.parse_args()
    asyncio.run(main(args.old_pid, args.reason))
