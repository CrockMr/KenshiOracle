"""Manual population proof after moving the player group on the disposable save."""
import argparse
import asyncio
import hashlib
import json
import math
import time
from pathlib import Path
from live_restore import restore_test
from live_suite import wait_loaded
from probe import Client, config


async def main(name, observe_existing=None):
    c = Client()
    path = Path('runtime/scenarios') / ('populated-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    source = Path.home()/'AppData/Local/kenshi/save/KenshiProbe_validation/quick.save'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == '04488b407bc57f8fdb1cbbdd8d1afc006d2b179f020ff89a9acf459df934fbeb'
    data = dict(town=name, source_sha256_before=digest, snapshots=[])
    state_path = Path(config()['runtime'])/'state.json'
    data['pid_before'] = json.loads(state_path.read_text())['pid']
    initial = await c.call('get_scene_state')
    try:
        if observe_existing:
            prior = json.loads(Path(observe_existing).read_text(encoding='utf-8'))
            assert prior['town'] == name and prior['pid_before'] == data['pid_before']
            data['baseline'], data['prepared'] = prior['baseline'], prior['prepared']
            data['resumed_from'] = observe_existing
        else:
            data['baseline'] = await restore_test(c, False)
            data['prepared'] = await c.call('prepare_town_scene', name=name)
        print(json.dumps(dict(stage='prepared', players=data['prepared']['players'])), flush=True)
        await c.call('pause', paused=False)
        await c.call('set_game_speed', speed=1)
        for index in range(6):
            await asyncio.sleep(5)
            await wait_loaded(c, 0)
            scene = await c.call('get_scene_state')
            characters = await c.call('list_characters', limit=500)
            target = data['prepared']['target_position']
            nearby = [row for row in characters['characters'] if math.hypot(row['position'][0]-target[0], row['position'][2]-target[2]) <= 2000]
            snapshot = dict(elapsed_seconds=(index+1)*5, scene=scene, characters=characters, within_2000_count=len(nearby))
            data['snapshots'].append(snapshot)
            print(json.dumps(dict(elapsed=snapshot['elapsed_seconds'], scene=scene, within_2000_count=len(nearby))), flush=True)
            if json.loads(state_path.read_text())['pid'] != data['pid_before']:
                raise RuntimeError('Process changed during city preparation')
    finally:
        try:
            data['restored'] = await restore_test(c, initial['free_camera'])
        finally:
            data['source_sha256_after'] = hashlib.sha256(source.read_bytes()).hexdigest()
            data['pid_after'] = json.loads(state_path.read_text())['pid']
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(dict(path=str(path), restored=data.get('restored'), source_unchanged=data['source_sha256_after']==digest)), flush=True)
    assert data['source_sha256_after'] == digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('town')
    parser.add_argument('--observe-existing')
    args = parser.parse_args()
    asyncio.run(main(args.town, args.observe_existing))
