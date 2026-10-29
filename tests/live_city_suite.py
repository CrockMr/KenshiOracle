"""Paired city measurements after a fresh disposable-save load per condition."""
import argparse
import asyncio
import hashlib
import json
import math
import time
from pathlib import Path
from benchmark import collect, validate_nav_diagnostics, validate_camera_stability
from live_restore import restore_test
from live_suite import wait_loaded, pause_ready
from probe import Client, config, read_runtime_state
from resources import ProcessResources


async def census(c, target):
    scene = await c.call('get_scene_state')
    chars = await c.call('list_characters', limit=500)
    nearby = [row for row in chars['characters'] if math.hypot(row['position'][0]-target[0], row['position'][2]-target[2]) <= 2000]
    return dict(scene=scene, characters=chars, within_2000_count=len(nearby))


async def main(town, order, samples=3, frames=300):
    c = Client()
    cfg = config()
    state_file = Path(cfg['runtime'])/'state.json'
    pid = (await read_runtime_state(state_file))['pid']
    source = Path.home()/'AppData/Local/kenshi/save/KenshiProbe_validation/quick.save'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == '04488b407bc57f8fdb1cbbdd8d1afc006d2b179f020ff89a9acf459df934fbeb'
    root = Path('runtime/measurements')/time.strftime('city-paired-%Y%m%dT%H%M%SZ', time.gmtime())
    root.mkdir(parents=True)
    initial = await c.call('get_scene_state')
    manifest = dict(town=town, order=order, pid=pid, source_sha256_before=digest, conditions=[])
    reference = None
    try:
        for speed in order:
            baseline = await restore_test(c, False, reference)
            if reference is None:
                reference = baseline
                manifest['reference_scene'] = reference
            prepared = await c.call('prepare_town_scene', name=town)
            await pause_ready(c, False)
            # Streaming dwell uses the same speed for both conditions.
            await asyncio.sleep(10)
            await wait_loaded(c, 0)
            # Diagnostic context may include pre-transition frames; keep its IDs explicit.
            transition_stats = await c.call('get_frame_stats', n=3600, detail='full')
            validate_nav_diagnostics(transition_stats)
            await c.call('set_game_speed', speed=speed)
            await asyncio.sleep(5)
            await wait_loaded(c, 0)
            before = await census(c, prepared['target_position'])
            if before['within_2000_count'] < 50:
                raise RuntimeError('Not enough characters near the town for this scenario')
            mods = Path(cfg['working_directory'])/'data/mods.cfg'
            context = dict(save='KenshiProbe_test', scene='player group relocated to '+town,
                camera=before['scene'], resolution='1280x720', streaming_dwell_seconds_x1=10,
                warmup_seconds_at_target_speed=5, order=order,
                enforce_scene_stability=True,
                concurrent_load='Process CPU recorded over enclosing collection interval; other applications not quantified',
                mods_sha256=hashlib.sha256(mods.read_bytes()).hexdigest() if mods.exists() else None,
                prepared=prepared, population_before=before,
                scene_transition_statistics=transition_stats)
            resources = ProcessResources(pid, cfg['executable'])
            measured = await collect(c, samples, frames, town+'-x'+str(speed), context)
            measured['process_resources'] = resources.finish()
            measured['population_after'] = await census(c, prepared['target_position'])
            validate_camera_stability(before['scene'], measured['population_after']['scene'])
            if measured['population_after']['within_2000_count'] < 50:
                raise RuntimeError('Town population left the observed area during measurements')
            if (await read_runtime_state(state_file))['pid'] != pid:
                raise RuntimeError('Process changed during measurements')
            output = root/('x'+str(speed)+'.json')
            output.write_text(json.dumps(measured, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            manifest['conditions'].append(str(output))
            print(json.dumps(dict(speed=speed, population_before=before['within_2000_count'],
                population_after=measured['population_after']['within_2000_count'],
                process_resources=measured['process_resources'],
                windows=[{k:v for k,v in w['statistics'].items() if k not in ('per_frame','navmesh_slow_calls')} for w in measured['windows']])), flush=True)
        manifest['measurements_completed'] = True
    except Exception as exc:
        manifest['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        try:
            expected = reference if reference and reference['free_camera']==initial['free_camera'] else None
            manifest['restored'] = await restore_test(c, initial['free_camera'], expected)
        except Exception as exc:
            manifest['restoration_error'] = dict(type=type(exc).__name__, message=str(exc))
            raise
        finally:
            manifest['source_sha256_after'] = hashlib.sha256(source.read_bytes()).hexdigest()
            (root/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(dict(output=str(root), restored=manifest.get('restored'), source_unchanged=manifest['source_sha256_after']==digest)), flush=True)
    assert manifest['source_sha256_after'] == digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('town')
    parser.add_argument('--order', type=int, nargs=2, choices=(1,5), default=(1,5))
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--frames', type=int, default=300)
    args = parser.parse_args()
    if set(args.order) != {1,5}:
        parser.error('order must contain both 1 and 5')
    if args.samples < 1 or not 1 <= args.frames <= 3600:
        parser.error('samples >= 1 and frames in 1..3600 required')
    asyncio.run(main(args.town, args.order, args.samples, args.frames))
