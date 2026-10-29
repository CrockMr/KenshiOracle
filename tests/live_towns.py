"""Read-only town inventory and scene snapshot; keeps disposable world paused."""
import asyncio
import json
from pathlib import Path
from probe import Client


async def main():
    c = Client()
    await c.call('pause', paused=True)
    data = dict(scene=await c.call('get_scene_state'), inventory=await c.call('list_towns', limit=100, name_filter=''))
    path = Path('runtime/scenarios/town-inventory.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
