"""Manual save-load validation; use only a disposable named test save."""
import argparse
import asyncio
import json
import time
from probe import Client, ProbeError


async def main(name, deadline_seconds):
    c = Client()
    before = await c.call('ping')
    print(json.dumps(dict(before=before)), flush=True)
    print(json.dumps(dict(load=await c.call('load_save', name=name))), flush=True)
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        await asyncio.sleep(1)
        try:
            beat = await c.call('heartbeat')
            if beat.get('loading'):
                continue
            state = await c.call('ping')
            if state.get('world_ready') and state['frame'] > before['frame']:
                print(json.dumps(dict(loaded=state)), flush=True)
                if state.get('current_save') != name:
                    print(json.dumps(dict(note='current_save is embedded save metadata, not necessarily the copied directory name', requested_directory=name)), flush=True)
                print(json.dumps(dict(heartbeat=await c.call('heartbeat'))), flush=True)
                return
        except ProbeError:
            pass
    raise TimeoutError('Save loading was not confirmed within the deadline')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('name')
    p.add_argument('--deadline', type=float, default=90)
    args = p.parse_args()
    asyncio.run(main(args.name, args.deadline))
