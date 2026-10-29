"""Observe one disposable battle, retain raw states and always reload the copy.

Select a non-player CHARACTER template from a prior town inventory.
No save is written; spawning can partially succeed and must never be retried
without a reload. Random character generation is not seeded by this harness.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from benchmark import validate_camera_stability, validate_nav_diagnostics
from live_restore import restore_test
from live_suite import wait_loaded, pause_ready
from probe import Client, config, read_runtime_state
from resources import ProcessResources


async def main(template, pairs, seconds, town, focus=False, interval=1, faction='', opponent='', opponent_faction='', client=None, thread_cpu=False):
    c = client or Client()
    cfg = config()
    state_file = Path(cfg['runtime'])/'state.json'
    pid = (await read_runtime_state(state_file))['pid']
    source = Path.home()/'AppData/Local/kenshi/save/KenshiProbe_validation/quick.save'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == '04488b407bc57f8fdb1cbbdd8d1afc006d2b179f020ff89a9acf459df934fbeb'
    initial = await c.call('get_scene_state')
    reference = None
    output = Path('runtime/scenarios')/time.strftime('battle-%Y%m%dT%H%M%SZ.json', time.gmtime())
    data = dict(pid=pid, town=town, focus_requested=focus, template_id=template, pairs=pairs, duration_requested=seconds,
                source_sha256_before=digest, observations=[], random_seed_controlled=False,
                sampling_interval_seconds=interval, faction_name=faction,
                opponent_template_id=opponent, opponent_faction_name=opponent_faction,
                transport=getattr(c, 'transport', 'tcp'), thread_cpu_requested=thread_cpu)
    files = dict(mods=Path(cfg['working_directory'])/'data/mods.cfg',
                 settings=Path(cfg['working_directory'])/'settings.cfg',
                 plugin=Path(cfg['working_directory'])/'mods/KenshiProbe/KenshiProbe.dll')
    data['configuration_fingerprints'] = {name: dict(path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)
        for name, path in files.items()}
    try:
        await wait_loaded(c, 0)
        reference = await restore_test(c, initial['free_camera'])
        data['reference_scene'] = reference
        data['town_preparation'] = await c.call('prepare_town_scene', name=town)
        # restore_test already selected x1 before pausing. A second speed command
        # immediately after unpause can race loading triggered by the teleport.
        await pause_ready(c, False)
        await asyncio.sleep(10)
        await wait_loaded(c, 0, stable_seconds=3)
        await pause_ready(c, True)
        if focus:
            data['focused'] = await c.call('focus_town', name=town)
            await asyncio.sleep(2)
        data['before'] = await c.call('get_scene_state')
        data['initial_ping'] = await c.call('ping')
        data['prepared'] = await c.call('prepare_battle_scene', template_id=template, pairs=pairs,
            faction_name=faction, opponent_template_id=opponent, opponent_faction_name=opponent_faction)
        if not data['prepared']['prepared']:
            raise RuntimeError('Partial setup; reload required, no retry')
        data['initial'] = await c.call('get_scene_state')
        if data['initial']['battle']['matched_loaded'] != pairs*2:
            raise RuntimeError('Not all spawned characters found in update list')
        await c.call('pause', paused=False)
        if thread_cpu:
            data['thread_roles_before'] = await c.call('heartbeat')
        resources = ProcessResources(pid, cfg['executable'], sample_threads=thread_cpu)
        started = time.monotonic()
        while time.monotonic()-started < seconds:
            await asyncio.sleep(interval)
            scene = await c.call('get_scene_state')
            data['observations'].append(dict(elapsed=time.monotonic()-started, scene=scene))
            if (await read_runtime_state(state_file))['pid'] != pid:
                raise RuntimeError('Game process changed during battle')
            if scene['paused'] or scene['frame_speed_multiplier'] != 1:
                raise RuntimeError('Battle simulation interrupted')
            validate_camera_stability(data['initial'], scene)
        if thread_cpu:
            data['thread_roles_after'] = await c.call('heartbeat')
        data['process_resources'] = resources.finish()
        await c.call('pause', paused=True)
        data['statistics'] = await c.call('get_frame_stats', n=600, detail='full')
        validate_nav_diagnostics(data['statistics'])
        if thread_cpu:
            from thread_resources import assign_roles
            context = await c.call('get_frame_stats', n=3600, detail='full')
            validate_nav_diagnostics(context)
            data['thread_attribution_statistics'] = context
            a, b = data['thread_roles_before'], data['thread_roles_after']
            game = {a['game_thread']} if a['game_thread'] == b['game_thread'] else set()
            renderer = {a['service_thread']} if a['service_thread'] == b['service_thread'] else set()
            nav = {row['thread_id'] for row in context['navmesh_slow_calls']
                   if a['frame'] <= row['completion_frame'] <= b['frame']}
            assign_roles(data['process_resources']['thread_cpu'], game, renderer, nav)
        # These statistics describe the trailing window, not the entire fight.
        data['completed'] = True
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        try:
            data['restored'] = await restore_test(c, initial['free_camera'], reference)
        except Exception as exc:
            data['restoration_error'] = dict(type=type(exc).__name__, message=str(exc))
            raise
        finally:
            data['source_sha256_after'] = hashlib.sha256(source.read_bytes()).hexdigest()
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(dict(output=str(output), completed=data.get('completed'),
                error=data.get('error'), restoration_error=data.get('restoration_error'),
                prepared=data.get('prepared'), source_unchanged=data['source_sha256_after']==digest)), flush=True)
    assert data['source_sha256_after'] == digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('template_id')
    parser.add_argument('--pairs', type=int, default=1, choices=range(1,21))
    parser.add_argument('--seconds', type=int, default=20)
    parser.add_argument('--town', default='Heng')
    parser.add_argument('--focus', action='store_true', help='test camera proximity after player relocation')
    parser.add_argument('--interval', type=float, default=1, help='seconds between scene observations')
    parser.add_argument('--faction', default='')
    parser.add_argument('--opponent-template', default='')
    parser.add_argument('--opponent-faction', default='')
    parser.add_argument('--mcp', action='store_true', help='run all game commands through a real MCP stdio session')
    parser.add_argument('--thread-cpu', action='store_true', help='collect Windows CPU by thread without new game hooks')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('seconds must be in 1..120')
    if not .1 <= args.interval <= 5:
        parser.error('interval must be in .1..5 seconds')
    positional = (args.template_id, args.pairs, args.seconds, args.town, args.focus, args.interval,
                  args.faction, args.opponent_template, args.opponent_faction)
    if args.mcp:
        from live_mcp_battle import run
        asyncio.run(run(main, *positional, thread_cpu=args.thread_cpu))
    else:
        asyncio.run(main(*positional, thread_cpu=args.thread_cpu))
