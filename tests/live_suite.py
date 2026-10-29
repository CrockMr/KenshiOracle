"""Manual paired measurements on the named disposable save; restores initial speed."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from benchmark import main as benchmark_main
from probe import Client, ProbeError, config


async def wait_loaded(c, minimum_frame, timeout=120, stable_seconds=0):
    deadline = time.monotonic()+timeout
    ready_since = None
    while time.monotonic() < deadline:
        try:
            beat = await c.call('heartbeat')
            if not beat.get('loading') and beat['frame'] > minimum_frame:
                state = await c.call('ping')
                if state.get('world_ready'):
                    if ready_since is None:
                        ready_since = time.monotonic()
                    if time.monotonic()-ready_since >= stable_seconds:
                        return state
                else:
                    ready_since = None
            else:
                ready_since = None
        except ProbeError:
            ready_since = None
        await asyncio.sleep(1)
    raise TimeoutError('Loading did not complete')


async def pause_ready(c, paused, timeout=120):
    """Retry only the pre-mutation world-not-ready rejection of pause.

    A scene move can start loading in the frame between ping and pause.
    Transport errors and all other failures propagate without a retry.
    """
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        await wait_loaded(c, 0, timeout=max(.1, deadline-time.monotonic()))
        try:
            return await c.call('pause', paused=paused)
        except ProbeError as exc:
            if 'world not ready' not in str(exc):
                raise
        await asyncio.sleep(.25)
    raise TimeoutError('World did not accept pause before deadline')


async def main(order):
    c = Client()
    initial = await c.call('ping')
    if not initial.get('world_ready') or initial.get('paused') is not False:
        raise RuntimeError('Requires the unpaused disposable test world')
    cfg = config()
    pid = json.loads((Path(cfg['runtime'])/'state.json').read_text())['pid']
    output_root = Path('runtime/measurements')/time.strftime('paired-%Y%m%dT%H%M%SZ', time.gmtime())
    try:
        for speed in order:
            before = await c.call('ping')
            print(json.dumps(dict(stage='load', speed=speed)), flush=True)
            await c.call('load_save', name='KenshiProbe_test')
            await wait_loaded(c, before['frame'])
            await c.call('pause', paused=False)
            await c.call('set_game_speed', speed=speed)
            await asyncio.sleep(.2)
            state = await c.call('ping')
            if state['frame_speed_multiplier'] != speed:
                raise RuntimeError('Requested speed not observed')
            print(json.dumps(dict(stage='measure', speed=speed, state=state)), flush=True)
            args = argparse.Namespace(config='config.json', samples=3, frames=300,
                warmup=5, label='gut-paired-x'+str(speed), save='KenshiProbe_test',
                scene='Gut, two player characters, no prepared battle',
                camera='unchanged after each reload', resolution='1280x720',
                concurrent_load='Codex, Firefox, Steam, Discord open; CPU load not quantified',
                output=str(output_root/('x'+str(speed)+'.json')))
            await benchmark_main(args)
            if json.loads((Path(cfg['runtime'])/'state.json').read_text())['pid'] != pid:
                raise RuntimeError('Game process changed during paired measurements')
    finally:
        await c.call('pause', paused=False)
        await c.call('set_game_speed', speed=initial['frame_speed_multiplier'])
        print(json.dumps(dict(restored=await c.call('ping'), output=str(output_root.resolve()))), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--order', type=int, nargs=2, choices=(1, 5), default=(1, 5))
    args = p.parse_args()
    if set(args.order) != {1, 5}:
        p.error('order must contain both 1 and 5')
    asyncio.run(main(args.order))
