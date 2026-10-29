"""Native pause-preserving speed regression on the named disposable copy.

No save writes, admin privileges or UI. Start before a deployment launch with
--previous-pid to retain the first-ready clock as an independent reference.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT/'mcp-server', ROOT/'tests'):
    sys.path.insert(0, str(folder))
import psutil
from benchmark import validate_camera_stability
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from probe import Client, ProbeError, config, read_runtime_state


async def main(previous_pid, baseline=None, client=None):
    c = client
    cfg = config()
    assert cfg['startup_save'] == 'KenshiProbe_test'
    assert time.time()+1800 < cfg['session_until']
    source = json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot = json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    save_root = Path(snapshot['snapshot_path']).parent
    settings = Path(cfg['working_directory'])/'settings.cfg'
    settings_before = settings.read_bytes()
    output = ROOT/'runtime/scenarios'/('restore-pause-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data = dict(completed=False, transport=c.transport, previous_pid=previous_pid,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                speed_checks=[], reloads=[], boot_observations=[])
    prior_capture = None
    if baseline:
        prior_capture = json.loads(Path(baseline).read_text())
        data['baseline'] = dict(path=str(baseline), sha256=hashlib.sha256(Path(baseline).read_bytes()).hexdigest(),
                                original_completed=prior_capture['completed'])

    def protected():
        return (all(manifest(save_root/k) == v['files'] for k, v in source['save_manifests'].items()) and
                manifest(Path(snapshot['snapshot_path'])) == snapshot['snapshot_manifest'])

    def publish():
        output.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def identity(pid):
        p = psutil.Process(pid)
        if Path(p.exe()).resolve() != Path(cfg['executable']).resolve() or p.cmdline() != [p.exe(), '--norestart']:
            raise RuntimeError('Wrong project game identity')
        return dict(pid=pid, executable=p.exe(), created_at=p.create_time(), cmdline=p.cmdline())

    def clock_equal(a, b):
        assert a['game_total_hours'] == b['game_total_hours'], 'Paused game hours advanced'

    async def stable(reference, count=3):
        rows = []
        for _ in range(count):
            scene = await c.call('get_scene_state')
            assert scene['paused'] and scene['frame_speed_multiplier'] == 0
            clock_equal(reference, scene)
            rows.append(scene)
            await asyncio.sleep(.4)
        return rows

    assert protected()
    publish()
    print(json.dumps(dict(stage='waiting_for_deployment', output=str(output))), flush=True)
    active_identity = None
    try:
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            try:
                state = await read_runtime_state(ROOT/'runtime/state.json')
                if state['pid'] == previous_pid and not prior_capture:
                    await asyncio.sleep(.1)
                    continue
                ping = await c.call('ping')
            except (ProbeError, FileNotFoundError):
                await asyncio.sleep(.1)
                continue
            data['boot_observations'].append(dict(at=time.time(), state=state, ping=ping))
            assert ping['plugin_version'] == '0.8.7'
            assert ping['set_game_speed_preserve_pause_available'] and ping['system_hook_count'] == 3
            if state.get('autoload_requested') and ping['world_ready']:
                assert ping['paused'] and not ping['load_pause_pending']
                active_identity = identity(state['pid'])
                if prior_capture:
                    assert active_identity == prior_capture['identity'], 'Baseline is from another game lifetime'
                data['identity'] = active_identity
                data['ready_observed'] = ping
                break
            await asyncio.sleep(.1)
        else:
            raise TimeoutError('Deployed game did not load the test copy')
        initial = await c.call('get_scene_state')
        assert initial['paused'] and not initial['free_camera'] and not initial['battle']['active']
        data['autoload_scene'] = initial
        if prior_capture:
            clock_equal(prior_capture['autoload_scene'], initial)
        data['autoload_stability'] = await stable(initial)

        # Reject malformed raw protocol input before touching speed or pause.
        direct = Client(cfg['port'], cfg['timeout'])
        try:
            await direct.call('set_game_speed', speed=2, preserve_pause='true')
        except ProbeError as e:
            assert 'preserve_pause must be bool' in str(e)
            data['invalid_boolean_error'] = str(e)
        else:
            raise AssertionError('Native speed handler accepted invalid flag')
        data['invalid_boolean_state'] = await c.call('get_scene_state')
        clock_equal(initial, data['invalid_boolean_state'])
        assert data['invalid_boolean_state']['paused']

        # Zero means pause to the SDK and conflicts with preserving a running state.
        # Both public MCP validation and raw native validation reject it before mutation.
        for name, endpoint in [('mcp', c), ('native', direct)]:
            try:
                await endpoint.call('set_game_speed', speed=0, preserve_pause=True)
            except ProbeError as e:
                assert ('strictement positive' if name == 'mcp' else 'positive speed') in str(e)
                data[name+'_zero_rejected'] = str(e)
            else:
                raise AssertionError('Zero speed with preserve_pause was accepted')
        data['zero_rejection_state'] = await c.call('get_scene_state')
        clock_equal(initial, data['zero_rejection_state'])
        assert data['zero_rejection_state']['paused']

        for speed in (2, 5, 1):
            row = dict(requested=speed)
            data['speed_checks'].append(row)
            row['result'] = await c.call('set_game_speed', speed=speed, preserve_pause=True)
            assert row['result']['preserve_pause'] and row['result']['paused_before'] and row['result']['paused']
            row['stable'] = await stable(initial)
        # Prove the selected nonzero speed is retained for a later explicit resume.
        data['set_resume_x2'] = await c.call('set_game_speed', speed=2, preserve_pause=True)
        data['resume'] = await c.call('pause', paused=False)
        await asyncio.sleep(.3)
        data['resumed_state'] = await c.call('get_scene_state')
        assert not data['resumed_state']['paused'] and data['resumed_state']['frame_speed_multiplier'] == 2
        data['unpaused_preserve_x1'] = await c.call('set_game_speed', speed=1, preserve_pause=True)
        assert not data['unpaused_preserve_x1']['paused_before'] and not data['unpaused_preserve_x1']['paused']
        assert data['unpaused_preserve_x1']['frame_speed_multiplier'] == 1
        data['unpaused_preserve'] = []
        for speed in (2, 5, 1):
            result = await c.call('set_game_speed', speed=speed, preserve_pause=True)
            assert not result['paused_before'] and not result['paused'] and result['frame_speed_multiplier'] == speed
            data['unpaused_preserve'].append(result)
        try:
            await direct.call('set_game_speed', speed=0, preserve_pause=True)
        except ProbeError as e:
            assert 'positive speed' in str(e)
            data['unpaused_native_zero_rejected'] = str(e)
        else:
            raise AssertionError('Running zero/preserve request accepted')
        data['unpaused_after_zero_rejection'] = await c.call('ping')
        assert not data['unpaused_after_zero_rejection']['paused'] and data['unpaused_after_zero_rejection']['frame_speed_multiplier'] == 1
        await c.call('pause', paused=True)
        # Default wire request remains compatible: an explicit speed resumes.
        data['legacy_default_x1'] = await c.call('set_game_speed', speed=1)
        assert not data['legacy_default_x1']['preserve_pause'] and not data['legacy_default_x1']['paused']
        await c.call('pause', paused=True)
        for _ in range(2):
            restored = await restore_test(c, False, lock_edge=True)
            data['reloads'].append(restored)
            clock_equal(initial, restored)
            data['reloads'][-1]['stable_observations'] = await stable(restored)
        assert identity(active_identity['pid']) == active_identity
        data['validation_passed'] = True
    except Exception as e:
        data['error'] = dict(type=type(e).__name__, message=str(e))
    finally:
        if active_identity is not None:
            try:
                assert identity(active_identity['pid']) == active_identity
                data['cleanup_pause'] = await c.call('pause', paused=True)
                restored = await restore_test(c, False, lock_edge=True)
                data['final_restored'] = restored
                if data.get('autoload_scene'):
                    clock_equal(data['autoload_scene'], restored)
            except Exception as e:
                data['cleanup_error'] = dict(type=type(e).__name__, message=str(e))
            finally:
                try:
                    assert identity(active_identity['pid']) == active_identity
                    data['cleanup_pause_final'] = await c.call('pause', paused=True)
                    data['release_camera'] = await c.call('set_camera_free', enabled=False, release_edge=True)
                    data['final_scene'] = await c.call('get_scene_state', thread_details=True)
                    assert data['final_scene']['paused'] and not data['final_scene']['scene_camera_control_owned']
                    assert data['final_scene']['edge_scrolling'] == source['scene']['edge_scrolling']
                except Exception as e:
                    data['release_error'] = dict(type=type(e).__name__, message=str(e))
        data['protected_files_unchanged'] = protected()
        data['settings_unchanged'] = settings.read_bytes() == settings_before
        data['completed'] = bool(data.get('validation_passed') and not data.get('error') and not data.get('cleanup_error') and not data.get('release_error')
                                 and data['protected_files_unchanged'] and data['settings_unchanged'])
        publish()
        print(json.dumps(dict(output=str(output), completed=data['completed'], error=data.get('error'),
                              cleanup_error=data.get('cleanup_error'), identity=active_identity,
                              reloads=len(data['reloads']), protected_files_unchanged=data['protected_files_unchanged'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous-pid', type=int, required=True)
    parser.add_argument('--baseline', type=Path, help='Prior first-ready observation from this exact process lifetime')
    args = parser.parse_args()
    os.chdir(ROOT)
    asyncio.run(run(main, args.previous_pid, args.baseline))
