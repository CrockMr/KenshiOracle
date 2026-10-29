"""Read-only observation while a human moves the pointer; sends no UI input."""
import argparse
import asyncio
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from probe import Client


async def main(seconds):
    c = Client()
    data = dict(started_at=datetime.now(timezone.utc).isoformat(),
                note='Manual pointer experiment; positions of the physical pointer are not measured by this script', samples=[])
    end = time.monotonic()+seconds
    initial = None
    try:
        while time.monotonic() < end:
            scene = await c.call('get_scene_state')
            if initial is None:
                initial = scene
            data['samples'].append(dict(observed_at=datetime.now(timezone.utc).isoformat(),
                scene=scene, displacement_from_first=math.dist(initial['camera_center'],scene['camera_center'])))
            if not scene['paused']:
                data['stopped_reason'] = 'World unpaused; no control input sent'
                break
            await asyncio.sleep(1)
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        data['finished_at'] = datetime.now(timezone.utc).isoformat()
        path = Path('runtime/scenarios/manual-pointer-observation.json')
        path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(path=str(path), samples=len(data['samples']),
            max_displacement=max((row['displacement_from_first'] for row in data['samples']),default=None),
            stopped_reason=data.get('stopped_reason'))),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=60)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('seconds must be in 1..120')
    asyncio.run(main(args.seconds))
