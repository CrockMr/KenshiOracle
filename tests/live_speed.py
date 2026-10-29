"""Manual mutation check on the disposable save, with state restoration."""

# Resolve shared oracle/research imports without a private PYTHONPATH.
import sys
from pathlib import Path
for _folder in ('mcp-server', 'tools/research', 'tests'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / _folder))
import asyncio
import json
from probe import Client


async def main():
    c = Client()
    initial = await c.call('ping')
    print(json.dumps(dict(initial=initial)), flush=True)
    if not initial.get('world_ready') or initial.get('paused') is not False:
        raise RuntimeError('Requires a loaded, unpaused disposable test save')
    speed = initial['frame_speed_multiplier']
    try:
        print(json.dumps(dict(pause=await c.call('pause', paused=True))), flush=True)
        print(json.dumps(dict(paused_state=await c.call('ping'))), flush=True)
        await c.call('pause', paused=False)
        for target in (2, 5):
            immediate = await c.call('set_game_speed', speed=target)
            await asyncio.sleep(.3)
            observed = await c.call('ping')
            print(json.dumps(dict(requested=target, immediate=immediate, observed=observed)), flush=True)
    finally:
        await c.call('pause', paused=False)
        await c.call('set_game_speed', speed=speed)
        print(json.dumps(dict(restored=await c.call('ping'))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
