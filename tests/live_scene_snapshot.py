"""Create a new disposable snapshot and test visible actor state across reloads.

Uses the real MCP stdio session. Never overwrites a save. The settings backup is
restored after the trial; source and pristine-copy files are checked in full.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from live_mcp_battle import run
from live_restore import restore_test
from live_suite import pause_ready, wait_loaded
from probe import Client, ProbeError, config, read_runtime_state


def manifest(root):
    return {str(path.relative_to(root)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file()}


def visible_comparison(before, after):
    a = {row['name']: row for row in before['battle']['members']}
    b = {row['name']: row for row in after['battle']['members']}
    if not a or a.keys() != b.keys():
        return dict(matches=False, reason='actor names missing or changed')
    numeric = []
    position = []
    for name in a:
        if not (a[name]['health']['complete'] and b[name]['health']['complete']):
            return dict(matches=False, reason='medical read incomplete')
        old = [a[name]['blood']] + sum(a[name]['health']['parts_flesh_stun_max'], [])
        new = [b[name]['blood']] + sum(b[name]['health']['parts_flesh_stun_max'], [])
        if len(old) != len(new):
            return dict(matches=False, reason='body part count changed')
        numeric.extend(abs(x-y) for x,y in zip(old,new))
        position.extend(abs(x-y) for x,y in zip(a[name]['position'],b[name]['position']))
        if any(a[name][key] != b[name][key] for key in ('dead', 'unconscious', 'is_player')):
            return dict(matches=False, reason='actor state changed')
    return dict(matches=max(numeric) <= 1e-4 and max(position) <= 1,
                max_medical_difference=max(numeric), max_position_component_difference=max(position))


async def wait_written(c, path, timeout=90):
    deadline = time.monotonic()+timeout
    previous = None
    while time.monotonic() < deadline:
        try:
            ping = await c.call('ping')
            if ping.get('save_signal') == 0 and (path/'quick.save').is_file():
                current = manifest(path)
                if previous == current:
                    return current
                previous = current
        except (ProbeError, PermissionError, FileNotFoundError):
            previous = None
        await asyncio.sleep(1)
    raise TimeoutError('Snapshot write did not become stable')


async def main(client=None):
    c = client or Client()
    cfg = config()
    token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    name = 'KenshiProbe_test_scene_'+token
    output = Path('runtime/scenarios')/('snapshot-'+token+'.json')
    settings = Path(cfg['working_directory'])/'settings.cfg'
    guard_file = Path('runtime/scene-snapshot-state.json')
    if guard_file.exists() and json.loads(guard_file.read_text(encoding='utf-8')).get('restore_required'):
        raise RuntimeError('An interrupted snapshot trial still needs its recorded settings backup restored')
    original_settings = settings.read_bytes()
    backup = Path('runtime/settings-before-scene-snapshot.cfg')
    backup.write_bytes(original_settings)
    guard = dict(restore_required=True, settings=str(settings), backup=str(backup.resolve()), snapshot_name=name)
    guard_file.write_text(json.dumps(guard, indent=2), encoding='utf-8')
    data = dict(name=name, transport=getattr(c, 'transport', 'tcp'), reloads=[])
    reference = None
    proof = json.loads(Path('runtime/scenarios/battle-campaign-073-final.json').read_text())
    source_root = Path.home()/'AppData/Local/kenshi/save'
    expected = proof['save_manifests']
    snapshot_path = None
    try:
        for slot in expected:
            assert manifest(source_root/slot) == expected[slot]['files']
        pid = (await read_runtime_state(Path(cfg['runtime'])/'state.json'))['pid']
        data['pid'] = pid
        reference = await restore_test(c)
        data['town'] = await c.call('prepare_town_scene', name='Mongrel')
        await pause_ready(c, False)
        await asyncio.sleep(10)
        await wait_loaded(c, 0, stable_seconds=3)
        await pause_ready(c, True)
        await c.call('focus_town', name='Mongrel')
        await asyncio.sleep(2)
        data['prepared'] = await c.call('prepare_battle_scene', template_id='16863-gamedata.base', pairs=1,
            faction_name='Bloodraiders', opponent_template_id='1227-gamedata.base', opponent_faction_name='Mercenary Guild')
        assert data['prepared']['prepared']
        data['before_save'] = await c.call('get_scene_state')
        data['save_request'] = await c.call('save_scene_snapshot', name=name)
        snapshot_path = Path(data['save_request']['save_root'])/name
        data['snapshot_manifest'] = await wait_written(c, snapshot_path)
        await pause_ready(c, True)
        try:
            await c.call('save_scene_snapshot', name=name)
        except ProbeError as exc:
            if 'already exists' not in str(exc):
                raise
            data['overwrite_rejected'] = True
        else:
            raise RuntimeError('Existing snapshot was not rejected')
        for _ in range(2):
            await c.call('set_camera_free', enabled=True)
            prior = await c.call('ping')
            accepted = await c.call('load_save', name=name)
            assert accepted['battle_tracking_restored']
            assert accepted['pause_on_ready']
            loaded = await wait_loaded(c, prior['frame'])
            assert loaded['paused'], 'Owned snapshot became ready before automatic pause'
            await pause_ready(c, True)
            await c.call('set_camera_free', enabled=True, lock_edge=True)
            scene = await c.call('get_scene_state')
            data['reloads'].append(dict(accepted=accepted, first_ready_ping=loaded, scene=scene))
            assert scene['battle']['matched_loaded'] == 2
            assert (await read_runtime_state(Path(cfg['runtime'])/'state.json'))['pid'] == pid
        data['comparison'] = visible_comparison(data['reloads'][0]['scene'], data['reloads'][1]['scene'])
        data['auto_pause_on_ready_verified'] = all(row['first_ready_ping']['paused'] for row in data['reloads'])
        data['snapshot_files_unchanged_after_load'] = manifest(snapshot_path) == data['snapshot_manifest']
        data['completed'] = True
    except Exception as exc:
        data['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        try:
            data['restored'] = await restore_test(c, False, reference)
        except Exception as exc:
            data['restoration_error'] = str(exc)
            raise
        finally:
            settings.write_bytes(original_settings)
            guard['restore_required'] = False
            guard_file.write_text(json.dumps(guard, indent=2), encoding='utf-8')
            data['settings_restored_exactly'] = settings.read_bytes() == original_settings
            data['source_and_copy_unchanged'] = all(manifest(source_root/slot) == expected[slot]['files'] for slot in expected)
            data['snapshot_path'] = str(snapshot_path) if snapshot_path else None
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(dict(output=str(output), completed=data.get('completed'), error=data.get('error'),
                comparison=data.get('comparison'), reload_paused=[row['first_ready_ping']['paused'] for row in data['reloads']],
                restored=bool(data.get('restored')), settings_restored=data['settings_restored_exactly'],
                source_and_copy_unchanged=data['source_and_copy_unchanged'])), flush=True)
    assert data['source_and_copy_unchanged'] and data['settings_restored_exactly']


if __name__ == '__main__':
    asyncio.run(run(main))
