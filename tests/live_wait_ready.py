"""Observe a fully automatic restart without sending any mutations."""
import argparse
import asyncio
import json
import time
from probe import Client, ProbeError


async def main(deadline_seconds):
    c = Client(timeout=2)
    end = time.monotonic()+deadline_seconds
    while time.monotonic() < end:
        try:
            beat = await c.call('heartbeat')
            if beat.get('loading') or not beat['frame']:
                await asyncio.sleep(1)
                continue
            state = await c.call('ping')
            if state.get('world_ready'):
                if beat.get('service_thread') != beat.get('game_thread'):
                    raise RuntimeError('Service and game thread IDs differ')
                print(json.dumps(dict(ready=state, heartbeat=beat)), flush=True)
                return
        except ProbeError:
            pass
        await asyncio.sleep(1)
    raise TimeoutError('Automatic restart did not reach a ready world')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--deadline', type=float, default=180)
    asyncio.run(main(p.parse_args().deadline))
