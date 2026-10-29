"""Restore the disposable save with the camera mode set before loading."""

# Resolve shared oracle/research imports without a private PYTHONPATH.
import sys
from pathlib import Path
for _folder in ('mcp-server', 'tools/research', 'tests'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / _folder))
import argparse
import asyncio
import json
from live_suite import wait_loaded
from benchmark import validate_camera_stability
from probe import Client


async def restore_test(c, free_camera=False, expected_scene=None, lock_edge=False):
    await wait_loaded(c, 0)
    await c.call('pause', paused=True)
    # CameraClass::load uses the current mode; switching it after loading changes the view.
    await c.call('set_camera_free', enabled=free_camera)
    prior = await c.call('ping')
    if not prior.get('set_game_speed_preserve_pause_available'):
        raise RuntimeError('Restoration requires native pause-preserving speed control')
    if lock_edge:await c.call('load_save',name='KenshiProbe_test',lock_edge=True)
    else:await c.call('load_save', name='KenshiProbe_test')
    await wait_loaded(c, prior['frame'])
    loaded = await c.call('get_scene_state')
    if not loaded['paused']:
        await c.call('pause', paused=True)
        raise RuntimeError('Disposable load did not become ready in pause')
    speed = await c.call('set_game_speed', speed=1, preserve_pause=True)
    assert speed['paused_before'] and speed['paused'] and speed['preserve_pause']
    await asyncio.sleep(.5)
    restored = await c.call('get_scene_state')
    assert restored['paused'] and restored['free_camera'] == free_camera
    assert restored['game_total_hours'] == loaded['game_total_hours'], 'Paused clock advanced during speed restoration'
    # getTimeStamp is a real-time stamper and advances even during pause.
    if expected_scene is not None:
        validate_camera_stability(expected_scene, restored)
    return restored


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--free-camera', action='store_true')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(restore_test(Client(), args.free_camera))), flush=True)
