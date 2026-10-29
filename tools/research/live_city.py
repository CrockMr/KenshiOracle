"""Manual camera-only city probe on KenshiProbe_test; reloads and pauses on exit."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from live_restore import restore_test
from probe import Client


async def main(town):
    c = Client()
    path = Path('runtime/scenarios') / ('city-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    source = Path.home() / 'AppData/Local/kenshi/save/KenshiProbe_validation/quick.save'
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert before_hash == '04488b407bc57f8fdb1cbbdd8d1afc006d2b179f020ff89a9acf459df934fbeb', 'Source save no longer matches protected reference'
    data = dict(town=town, source_sha256_before=before_hash, snapshots=[])
    try:
        await c.call('pause', paused=True)
        data['before'] = await c.call('get_scene_state')
        data['focus'] = await c.call('focus_town', name=town)
        await asyncio.sleep(5)
        data['snapshots'].append(dict(stage='paused_5s', scene=await c.call('get_scene_state')))
        await c.call('pause', paused=False)
        await c.call('set_game_speed', speed=1)
        for index in range(3):
            await asyncio.sleep(5)
            data['snapshots'].append(dict(stage='x1_'+str((index+1)*5)+'s', scene=await c.call('get_scene_state')))
        await c.call('pause', paused=True)
        data['characters'] = await c.call('list_characters', limit=500)
    finally:
        try:
            data['restored'] = await restore_test(c, data['before']['free_camera'])
        finally:
            data['source_sha256_after'] = hashlib.sha256(source.read_bytes()).hexdigest()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(dict(path=str(path), snapshots=data['snapshots'], restored=data.get('restored'), source_unchanged=data['source_sha256_after']==before_hash)), flush=True)
    assert data['source_sha256_after'] == before_hash, 'Source save changed'
    assert data['restored']['paused'] is True
    assert data['restored']['free_camera'] == data['before']['free_camera'], 'Camera mode not restored'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('town')
    asyncio.run(main(parser.parse_args().town))
