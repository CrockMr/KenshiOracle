"""Read-only validation of the new SDK clock in a paused disposable world."""
import asyncio
import json
from pathlib import Path
from probe import Client


async def main():
    c = Client()
    before = await c.call('get_scene_state')
    assert before['paused'], 'Pause the disposable world before this check'
    await asyncio.sleep(1)
    after = await c.call('get_scene_state')
    assert after['paused'] and abs(after['game_total_hours']-before['game_total_hours']) < 1e-9
    assert after['observed_qpc_ms'] > before['observed_qpc_ms']
    data = dict(before=before, after=after, passed=True)
    Path('runtime/clock-pause-validation.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
