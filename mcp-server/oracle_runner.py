"""Original-game scenario orchestration. No engine API or wall-clock simulation.

The probe pauses at each game-clock boundary. Actions at one boundary are applied
in declaration order while paused, before its checkpoints. A resume action takes
effect when advancing to the next boundary. Only immutable JSON crosses TCP.
"""
import asyncio
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from oracle_schema import canonical_bytes, load_scenario, load_state, validate_scenario
from oracle_origins import read_saved_origins, verify_saved_origins, SavedOriginError
from oracle_identity import validate_origin_fingerprint, validate_origin_token, validate_saved_handles
from probe import Client, ProbeError


class ScenarioError(ProbeError):
    pass


def timestamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')


def positive_timeout(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 86400:
        raise ValueError(name + ' must be finite, positive and at most 86400 seconds')
    return float(value)


def save_name(name):
    if (not isinstance(name, str) or not name or len(name.encode('utf-8')) > 128
            or name in ('.', '..') or any(c in name for c in '/\\:\r\n\0')):
        raise ValueError('Invalid save name')
    return name


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                               indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temp.replace(path)


@contextmanager
def scenario_lock(runtime):
    """An OS-owned lock is automatically released if the MCP process exits."""
    root = Path(runtime)
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'oracle-scenario.lock').open('a+b') as handle:
        # Reading a byte owned by another Windows process itself raises a
        # sharing violation. Inspect length without reading the locked range.
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ScenarioError('Another scenario owns this runtime directory') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class OracleSession:
    def __init__(self, cfg, client=None):
        self.cfg = cfg
        self.client = client or Client(cfg.get('port', 47800), cfg.get('timeout', 10))
        self.operation_id = None
        self.instance = None
        self.deadline = None
        self.identity_source = None

    def check_deadline(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise ScenarioError('Scenario exceeded scenario_timeout')

    async def call(self, command, **params):
        self.check_deadline()
        if self.deadline is None:
            return await self.client.call(command, **params)
        try:
            return await asyncio.wait_for(self.client.call(command, **params),
                                          max(.001, self.deadline-time.monotonic()))
        except TimeoutError as exc:
            raise ScenarioError('Scenario exceeded scenario_timeout during ' + command) from exc

    async def ping(self):
        result = await self.call('ping')
        identity = result.get('instance_id')
        if identity is None:
            raise ScenarioError('Probe instance identity is unavailable; update the probe')
        if self.instance is None:
            self.instance = identity
        elif identity != self.instance:
            # Never send an operation ID from the old process to the new one.
            self.operation_id = None
            raise ScenarioError('Game restarted during the scenario; this execution is invalid')
        return result

    async def load(self, name, lock_edge=True):
        save_name(name)
        deadline = time.monotonic() + positive_timeout(self.cfg.get('load_timeout', 120), 'load_timeout')

        async def bounded(factory, label):
            self.check_deadline()
            limit = min(deadline, self.deadline) if self.deadline is not None else deadline
            remaining = limit-time.monotonic()
            if remaining <= 0:
                raise ScenarioError('load_timeout or scenario_timeout expired during ' + label)
            try:
                return await asyncio.wait_for(factory(), remaining)
            except TimeoutError as exc:
                raise ScenarioError('load_timeout or scenario_timeout expired during ' + label) from exc

        before = await self.ping()
        manifest = None
        source_root = None
        if before.get('saved_origins_required') is True:
            native_root = before.get('save_root')
            if type(native_root) is not str or not native_root:
                raise ScenarioError('Probe has no authoritative save_root for saved identities')
            source_root = Path(native_root)
            if not source_root.is_absolute():
                working = self.cfg.get('working_directory')
                if working is None and self.cfg.get('executable'):
                    working = str(Path(self.cfg['executable']).parent)
                if working is None:
                    raise ScenarioError('Relative SDK save_root requires the game working_directory')
                source_root = Path(working)/source_root
            configured = self.cfg.get('save_root')
            if configured is not None and Path(configured).resolve() != source_root.resolve():
                raise ScenarioError('Configured save_root differs from the public SDK save_root')
            try:
                manifest = await bounded(lambda: asyncio.to_thread(read_saved_origins, source_root, name),
                                         'reading saved identities')
            except SavedOriginError as exc:
                raise ScenarioError('Saved identity source '+exc.code+': '+str(exc)) from exc
            await self.ping()  # Never submit a mutation to a replacement process.
        self.identity_source = None
        accepted = await bounded(lambda: self.call('load_save', name=name, lock_edge=lock_edge, pause_on_ready=True),
                                 'requesting save load')
        if accepted.get('accepted') is not True or accepted.get('pause_on_ready') is not True:
            raise ScenarioError('Probe did not accept a protected, paused save load')
        while time.monotonic() < deadline:
            state = await bounded(self.ping, 'waiting for loaded world')
            if (state.get('world_ready') is True and state.get('paused') is True
                    and not state.get('load_pause_pending', False)
                    and state.get('frame', 0) > before.get('frame', 0)):
                if manifest is None:
                    return dict(accepted=accepted, ready=state)
                if state.get('save_root') != before.get('save_root'):
                    raise ScenarioError('SDK save_root changed during save loading')
                try:
                    await bounded(lambda: asyncio.to_thread(verify_saved_origins, source_root, manifest),
                                  'verifying unchanged saved identities')
                except SavedOriginError as exc:
                    raise ScenarioError('Saved identity source '+exc.code+': '+str(exc)) from exc
                ids = [row['saved_id'] for kind in ('characters', 'squads') for row in manifest[kind]]
                fingerprint = validate_origin_fingerprint(manifest['fingerprint'])
                if len(ids) > 100000:
                    raise ScenarioError('Saved identity manifest exceeds the native safety limit')
                await self.ping()
                pending = await bounded(lambda: self.call('begin_saved_origins', save_name=name,
                        source_fingerprint=fingerprint, count=len(ids)), 'starting saved identity context')
                token = validate_origin_token(pending.get('token'))
                if pending.get('expected_count') != len(ids) or pending.get('pending_count') != 0:
                    raise ScenarioError('Probe returned an inconsistent pending saved identity context')
                for start in range(0, len(ids), 128):
                    batch = validate_saved_handles(ids[start:start+128])
                    await self.ping()
                    progress = await bounded(lambda b=batch: self.call('add_saved_origins', token=token, ids=b),
                                             'adding saved identities')
                    if progress.get('pending_count') != start+len(batch) or progress.get('expected_count') != len(ids):
                        raise ScenarioError('Probe returned an inconsistent saved identity batch count')
                await self.ping()
                prepared = await bounded(lambda: self.call('commit_saved_origins', token=token),
                                         'committing saved identities')
                if (prepared.get('prepared') is not True or prepared.get('save_name') != name
                        or prepared.get('source_fingerprint') != fingerprint or prepared.get('count') != len(ids)):
                    raise ScenarioError('Probe did not prepare the complete saved identity context')
                self.identity_source = prepared
                return dict(accepted=accepted, ready=state, saved_origins=prepared)
            await asyncio.sleep(.05)
        raise ScenarioError('Save load did not finish in pause before load_timeout')

    async def until(self, target_seconds, timeout=None):
        if type(target_seconds) not in (int, float) or not math.isfinite(target_seconds) or target_seconds < 0:
            raise ValueError('target_seconds must be a nonnegative finite game-clock time')
        seconds = positive_timeout(timeout if timeout is not None else self.cfg.get('run_until_timeout', 120),
                                   'run_until_timeout')
        if not .1 <= seconds <= 3600 or target_seconds > 1e9:
            raise ValueError('run_until requires timeout 0.1..3600 seconds and target <= 1e9 game seconds')
        await self.ping()  # Bind standalone MCP calls before starting an operation.
        deadline = time.monotonic() + seconds
        result = await self.call('run_until', target_seconds=target_seconds, timeout_seconds=seconds)
        self.operation_id = result.get('operation_id')
        if not isinstance(self.operation_id, str) or not self.operation_id:
            raise ScenarioError('Probe returned no run_until operation identity')
        try:
            while True:
                status = result.get('status')
                if status == 'completed':
                    clock = result.get('clock', {})
                    if clock.get('paused') is not True or clock.get('elapsed_seconds', -1) + .000001 < target_seconds:
                        raise ScenarioError('run_until completion did not reach the requested clock in pause')
                    return result
                if status != 'running':
                    raise ScenarioError('run_until ended with status ' + str(status))
                if time.monotonic() >= deadline:
                    raise ScenarioError('run_until exceeded its wall-clock deadline')
                await asyncio.sleep(.05)
                await self.ping()
                result = await self.call('run_until_status', operation_id=self.operation_id)
                if result.get('operation_id') != self.operation_id:
                    raise ScenarioError('run_until status belongs to a different operation')
        except BaseException as exc:
            try:
                await self.cancel()
            except Exception as cleanup_error:
                exc.add_note('Cancellation also failed: ' + str(cleanup_error))
            raise
        finally:
            if result.get('status') == 'completed':
                self.operation_id = None

    async def cancel(self):
        if self.operation_id is not None:
            operation = self.operation_id
            current = await self.client.call('ping')
            if current.get('instance_id') != self.instance:
                self.operation_id = None
                raise ScenarioError('Game restarted before cancellation; old operation was not sent to the new game')
            await self.client.call('cancel_run_until', operation_id=operation)
            self.operation_id = None

    async def restore_controls(self, original=None, *, params=None,
                               observations=None, baseline_observations=None):
        """Restore once through a held baseline, then verify the released pose.

        A saved scene is the strict reference. Direct control parameters derive
        their eye position from the settled rig's boom, without guessing a
        target's camera height. A requested resume happens only after the pose
        was verified in pause; subsequent reads verify discrete controls only.
        No failed prepare/commit/pause mutation is retried.
        """
        if (original is None) == (params is None):
            raise ValueError('Provide exactly one original scene or control params')
        requested = control_params(original) if original is not None else dict(params)
        desired = restoration_reference(requested, original=original)
        desired_paused = desired['paused']
        prepare_params = dict(requested, paused=True)
        status = await self.ping()
        require_control_world(status)
        if status.get('paused') is not True:
            await self.call('pause', paused=True)
            status = await self.ping()
            require_control_world(status, paused=True)
        prepared = await self.call('prepare_scene_control', **prepare_params)
        if not isinstance(prepared, dict) or prepared.get('prepared') is not True:
            raise ScenarioError('Probe did not prepare held camera controls')
        token = prepared.get('token')
        if (type(token) is not str or not 1 <= len(token) <= 200
                or not token.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ScenarioError('Probe returned no valid camera restoration token')
        baseline = await wait_stable_controls(self, observations=baseline_observations,
                                               held=True, hold_token=token)
        baseline_settings = dict(desired, edge_scrolling=False, paused=True)
        if original is None and requested.get('camera_follow_id') is not None:
            canonical_follow = prepared.get('camera_follow_id')
            if type(canonical_follow) is not str or not canonical_follow:
                raise ScenarioError('Prepared camera controls have no canonical follow identity')
            baseline_settings['camera_follow_id'] = canonical_follow
        check_control_settings(baseline_settings, baseline, camera_lock=True)
        if original is None:
            desired['camera_position'] = [eye + wanted - center for eye, wanted, center in
                                          zip(baseline['camera_position'], desired['camera_center'],
                                              baseline['camera_center'])]
            desired['camera_follow_id'] = baseline.get('camera_follow_id')
        paused_reference = dict(desired, paused=True)
        # Validate the derived reference before publishing any correction.
        check_controls(paused_reference, paused_reference)
        require_control_world(await self.ping(), paused=True)
        response = await self.call('commit_scene_control', token=token)
        if not isinstance(response, dict) or response.get('restored') is not True:
            raise ScenarioError('Probe did not commit prepared camera controls')
        scene = await wait_stable_controls(self, paused_reference, observations=observations)
        result = dict(response=response, scene=scene, baseline=baseline,
                      pose_verified_in_pause=True, unpaused_after_verification=False)
        if not desired_paused:
            require_control_world(await self.ping(), paused=True)
            await self.call('pause', paused=False)
            require_control_world(await self.ping(), paused=False)
            resumed = await self.call('get_scene_state')
            require_control_world(await self.ping(), paused=False)
            check_control_settings(desired, resumed)
            result.update(scene=resumed, verified_paused_scene=scene,
                          unpaused_after_verification=True)
        return result

    async def dump(self, destination=None):
        filename = 'state-' + uuid.uuid4().hex + '.json'
        result = await self.call('dump_state', filename=filename)
        if not isinstance(result, dict) or not isinstance(result.get('path'), str):
            raise ScenarioError('dump_state did not return a file path')
        source = Path(result['path']).resolve()
        allowed = Path(self.cfg['oracle_output']).resolve()
        try:
            source.relative_to(allowed)
        except ValueError as exc:
            raise ScenarioError('Probe snapshot is outside the configured oracle_output directory') from exc
        if source.name != filename or source.stat().st_size > 64 * 1024 * 1024:
            raise ScenarioError('Probe snapshot has an unexpected name or exceeds 64 MiB')
        state = load_state(source)
        payload = canonical_bytes(state)
        identity_source = result.get('identity_source')
        if self.identity_source is not None:
            if (not isinstance(identity_source, dict)
                    or any(identity_source.get(key) != self.identity_source.get(key)
                           for key in ('save_name', 'source_fingerprint', 'count'))):
                raise ScenarioError('Snapshot identity source differs from the prepared save')
        if identity_source is not None:
            if not isinstance(identity_source, dict):
                raise ScenarioError('Snapshot has invalid identity source metadata')
            save_name(identity_source.get('save_name'))
            validate_origin_fingerprint(identity_source.get('source_fingerprint'))
            limits = {'count': 100000, 'matched_count': identity_source.get('count', -1),
                      'remapped_characters': len(state['characters']), 'remapped_squads': len(state['squads'])}
            for key, maximum in limits.items():
                value = identity_source.get(key)
                if type(value) is not int or not 0 <= value <= maximum:
                    raise ScenarioError('Snapshot has invalid identity source '+key)
        if destination is None:
            destination = Path(self.cfg['runs']) / 'dumps' / filename
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as handle:
            handle.write(payload)
        record = dict(path=str(destination.resolve()), source_path=str(source),
                      schema_version=state['schema_version'], sha256=hashlib.sha256(payload).hexdigest(),
                      bytes=len(payload), clock=state['clock'],
                      counts={key: len(state[key]) for key in ('characters', 'squads', 'factions', 'relations')})
        if identity_source is not None:
            record['identity_source'] = identity_source
        self.check_deadline()
        return state, record


def control_params(scene):
    required = ('camera_center', 'camera_orientation', 'camera_zoom', 'free_camera',
                'edge_scrolling', 'selected_game_speed', 'paused')
    if any(key not in scene or scene[key] is None for key in required):
        raise ScenarioError('Probe cannot capture complete camera/time controls for restoration; '
                            'establish a known speed with set_game_speed(speed=1, preserve_pause=True) first')
    selected = scene['selected_game_speed']
    if type(selected) not in (int, float) or not math.isfinite(selected) or not 0 < selected <= 5:
        raise ScenarioError('Probe cannot restore an unknown or nonpositive selected game speed')
    return dict(camera_center=scene['camera_center'], camera_orientation=scene['camera_orientation'],
                camera_zoom=scene['camera_zoom'], free_camera=scene['free_camera'],
                edge_scrolling=scene['edge_scrolling'], speed=scene['selected_game_speed'],
                paused=scene['paused'], camera_follow_id=scene.get('camera_follow_id'))


def restoration_reference(params, *, original=None):
    allowed = {'camera_center', 'camera_position', 'camera_orientation', 'camera_zoom',
               'free_camera', 'edge_scrolling', 'speed', 'paused', 'camera_follow_id'}
    if not isinstance(params, dict) or set(params)-allowed:
        raise ValueError('Unknown scene control parameter')
    required = allowed-{'camera_position', 'camera_follow_id'}
    if not required <= set(params):
        raise ValueError('Incomplete scene control parameters')
    for key in ('free_camera', 'edge_scrolling', 'paused'):
        if type(params[key]) is not bool:
            raise ValueError(key+' must be a boolean')
    reference = dict(original) if original is not None else dict(params)
    reference.update(selected_game_speed=params['speed'], scene_camera_control_owned=False,
                     camera_restore_token=None)
    reference.setdefault('camera_position', params['camera_center'])
    reference.setdefault('camera_follow_id', params.get('camera_follow_id'))
    control_params(reference)
    check_controls(reference, reference)
    return reference


def require_control_world(status, *, paused=None):
    if status.get('world_ready') is not True or status.get('load_pause_pending', False):
        raise ScenarioError('world not ready during camera restoration')
    if paused is not None and status.get('paused') is not paused:
        raise ScenarioError('Restoration mismatch: paused at camera restoration boundary')


def check_control_settings(expected, actual, *, camera_lock=False):
    for key in ('free_camera', 'edge_scrolling', 'paused'):
        if actual.get(key) != expected.get(key):
            raise ScenarioError('Restoration mismatch: ' + key)
    if camera_lock and actual.get('scene_camera_control_owned') is not True:
        raise ScenarioError('Restoration lost the camera lock')
    if not camera_lock and actual.get('scene_camera_control_owned'):
        raise ScenarioError('Restoration left the camera lock owned')
    if not camera_lock and actual.get('camera_restore_token') is not None:
        raise ScenarioError('Restoration left a camera correction pending')
    if actual.get('camera_follow_id') != expected.get('camera_follow_id'):
        raise ScenarioError('Restoration mismatch: camera_follow_id')
    for key in ('camera_orientation',):
        old, new = expected.get(key), actual.get(key)
        size = 4 if key == 'camera_orientation' else 3
        if (not isinstance(old, (list, tuple)) or not isinstance(new, (list, tuple))
                or len(old) != size or len(new) != size
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in (*old, *new))):
            raise ScenarioError('Restoration cannot verify ' + key)
        # A quaternion and its negation encode the same orientation.
        delta = max(abs(a-b) for a, b in zip(old, new))
        if key == 'camera_orientation':
            delta = min(delta, max(abs(a+b) for a, b in zip(old, new)))
        if delta > (.0001 if key == 'camera_orientation' else .05):
            raise ScenarioError('Restoration mismatch: ' + key + ' (max difference ' + str(delta) + ')')
    selected = actual.get('selected_game_speed')
    if (type(selected) not in (int, float) or not math.isfinite(selected)
            or abs(selected - expected['selected_game_speed']) > .000001):
        raise ScenarioError('Restoration mismatch: selected game speed')
    zoom = actual.get('camera_zoom')
    if (type(zoom) not in (int, float) or not math.isfinite(zoom)
            or abs(zoom - expected['camera_zoom']) > .05):
        raise ScenarioError('Restoration mismatch: camera_zoom')


def check_controls(expected, actual, *, camera_lock=False):
    check_control_settings(expected, actual, camera_lock=camera_lock)
    for key in ('camera_center', 'camera_position'):
        old, new = expected.get(key), actual.get(key)
        if (not isinstance(old, (list, tuple)) or not isinstance(new, (list, tuple))
                or len(old) != 3 or len(new) != 3
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in (*old, *new))):
            raise ScenarioError('Restoration cannot verify '+key)
        delta = max(abs(a-b) for a, b in zip(old, new))
        if delta > .05:
            raise ScenarioError('Restoration mismatch: '+key+' (max difference '+str(delta)+')')


async def wait_stable_controls(session, expected=None, *, observations=None,
                               timeout=10.0, stable_seconds=.5, held=False, hold_token=None):
    """Observe three distinct frames over a bounded, continuous ready window.

    Without expected controls, capture the last paused pose of that window
    before arming the restoration guard. With expected controls, every accepted
    pose must match the original reference; a stable wrong pose never succeeds.
    This reads controls after the native release, without retrying a mutation or
    claiming that future user input cannot move the camera.
    """
    timeout = min(10.0, positive_timeout(timeout, 'control stability timeout'))
    stable_seconds = max(.5, positive_timeout(stable_seconds, 'control stability window'))
    if type(held) is not bool or (held and (type(hold_token) is not str or not hold_token)):
        raise ValueError('A held control observation requires its restoration token')
    observations = [] if observations is None else observations
    started = time.monotonic()
    deadline = started + timeout
    anchor = None
    first_at = None
    frames = set()
    last_error = 'no ready camera observations'

    async def read(operation):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return await asyncio.wait_for(operation(), remaining)

    while time.monotonic() < deadline:
        row = dict(elapsed_seconds=time.monotonic() - started, accepted=False)
        observations.append(row)
        try:
            before = await read(session.ping)
            row['ping'] = before
            if (before.get('world_ready') is not True
                    or before.get('load_pause_pending', False)):
                raise ScenarioError('world not ready during control stability observation')
            if expected is None and before.get('paused') is not True:
                raise ScenarioError('Initial game pause is required before capturing scenario controls')
            if expected is not None and before.get('paused') != expected.get('paused'):
                raise ScenarioError('Restoration mismatch: paused before control observation')
            scene = await read(lambda: session.call('get_scene_state'))
            row['scene'] = scene
            # A scene read can itself precede a new loading transition. Bind
            # identity and readiness on both sides of every accepted sample.
            after = await read(session.ping)
            row['ping_after'] = after
            if (after.get('world_ready') is not True
                    or after.get('load_pause_pending', False)):
                raise ScenarioError('world not ready after control stability observation')
            if expected is not None and after.get('paused') != expected.get('paused'):
                raise ScenarioError('Restoration mismatch: paused after control observation')
            if expected is None:
                if scene.get('paused') is not True or after.get('paused') is not True:
                    raise ScenarioError('Initial game pause is required before capturing scenario controls')
                control_params(scene)
            if held:
                if (scene.get('scene_camera_control_owned') is not True
                        or scene.get('edge_scrolling') is not False
                        or scene.get('camera_restore_token') != hold_token
                        or scene.get('paused') is not True
                        or before.get('paused') is not True or after.get('paused') is not True):
                    raise ScenarioError('Camera restoration hold or token was lost')
                control_params(scene)
            reference = expected if expected is not None else (anchor or scene)
            check_controls(reference, scene, camera_lock=held)
            if expected is not None and anchor is not None:
                check_controls(anchor, scene, camera_lock=held)
            frame = scene.get('frame')
            if type(frame) is not int or frame < 0:
                raise ScenarioError('Control observation has no valid frame identity')
            hours = scene.get('game_total_hours')
            if type(hours) not in (int, float) or not math.isfinite(hours):
                raise ScenarioError('Control observation has no finite game clock')
            if anchor is not None and hours != anchor['game_total_hours']:
                raise ScenarioError('Game clock changed during control stability observation')
        except TimeoutError:
            row['error'] = last_error = 'Control observation exceeded its stability deadline'
            break
        except ProbeError as exc:
            message = str(exc)
            row['error'] = last_error = message
            # Only availability and verification failures are read again.
            # Identity changes and transport/other probe failures propagate.
            transient = ('world not ready' in message.lower()
                         or 'world_not_ready' in message.lower()
                         or message.startswith(('Restoration ', 'Game clock changed ')))
            if not transient:
                raise
            anchor = None
            first_at = None
            frames.clear()
        else:
            observed = time.monotonic()
            if observed >= deadline:
                row['error'] = last_error = 'Control observation exceeded its stability deadline'
                break
            if anchor is None:
                anchor, first_at = scene, observed
            distinct = frame not in frames
            frames.add(frame)
            row.update(accepted=True, distinct_frames=len(frames),
                       stable_seconds=observed - first_at)
            if distinct and len(frames) >= 3 and observed - first_at >= stable_seconds:
                return scene
        await asyncio.sleep(min(.05, max(0, deadline-time.monotonic())))
    raise ScenarioError('Camera/time controls did not stabilize before control stability timeout: ' + last_error)


def flatten_state(value, prefix=''):
    """Stable field paths use entity IDs instead of incidental list positions."""
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace('~', '~0').replace('/', '~1')
            out.update(flatten_state(item, prefix + '/' + escaped))
    elif isinstance(value, list):
        if not value:
            out[prefix] = []
        for index, item in enumerate(value):
            identity = str(index)
            if isinstance(item, dict):
                if 'id' in item:
                    identity = item['id']
                elif 'source_id' in item and 'target_id' in item:
                    identity = json.dumps([item['source_id'], item['target_id']],
                                          ensure_ascii=False, separators=(',', ':'))
            out.update(flatten_state(item, prefix + '/' + identity.replace('~', '~0').replace('/', '~1')))
    else:
        out[prefix] = value
    return out


def variability(executions):
    by_checkpoint = defaultdict(list)
    for execution in executions:
        if execution.get('status') != 'completed':
            continue
        for capture in execution['checkpoints']:
            by_checkpoint[capture['name']].append((execution['execution'], flatten_state(load_state(capture['path']))))
    report = {}
    for name, states in by_checkpoint.items():
        paths = sorted(set().union(*(state.keys() for _, state in states)))
        stable, varied = [], []
        for path in paths:
            observations = [dict(execution=index, present=path in state,
                                 **({'value': state[path]} if path in state else {})) for index, state in states]
            signatures = [json.dumps({k: v for k, v in row.items() if k != 'execution'},
                                     sort_keys=True, ensure_ascii=False, allow_nan=False) for row in observations]
            if len(set(signatures)) == 1:
                stable.append(path)
            else:
                varied.append(dict(path=path, observations=observations))
        report[name] = dict(executions=len(states), stable_paths=stable, variable_fields=varied,
                            stable_field_count=len(stable), variable_field_count=len(varied),
                            repeatability_evaluated=len(states) >= 2)
    return report


def markdown_report(report):
    rows = ['# Scenario ' + report['scenario']['name'], '',
            'Status: ' + report['status'] + '. Repetitions completed: ' +
            str(sum(x.get('status') == 'completed' for x in report['executions'])) + '.', '',
            'Times are calendar seconds in the game, relative to the reloaded save. '
            'Each checkpoint records its requested and actual time; the engine is not assumed deterministic.', '',
            '| Checkpoint | Executions | Stable fields | Variable fields |', '| --- | ---: | ---: | ---: |']
    for name, result in report.get('variability', {}).items():
        rows.append('| ' + name + ' | ' + str(result['executions']) + ' | ' +
                    str(result['stable_field_count']) + ' | ' + str(result['variable_field_count']) + ' |')
    rows.extend(['', 'The JSON report lists all stable field paths and all varying observations, '
                 'including missing entities. One execution alone does not establish repeatability.', '',
                 'Restoration: ' + str(report.get('restoration', {}).get('verified', False)) + '.'])
    if report.get('error'):
        rows.extend(['', 'Error: ' + report['error']])
    if report.get('restoration_error'):
        rows.extend(['', 'Restoration error: ' + report['restoration_error']])
    return '\n'.join(rows) + '\n'


async def execute_scenario(scenario, cfg, repeat=None, client=None):
    """Execute after preloading this scenario's save and establishing paused controls.

    The captured controls must belong to that same save; the probe cannot infer
    their source save. Failures leave a report and a restoration guard.
    """
    validate_scenario(scenario)
    repetitions = scenario.get('repeat', 1) if repeat is None else repeat
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError('repeat must be an integer from 1 to 100')
    session = OracleSession(cfg, client)
    with scenario_lock(cfg['runtime']):
        guard_path = Path(cfg['runtime']) / 'oracle-restoration.json'
        if guard_path.exists() and json.loads(guard_path.read_text(encoding='utf-8')).get('restore_required'):
            raise ScenarioError('An interrupted scenario requires restoration: ' + str(guard_path))
        root = Path(cfg['runs']) / scenario['name'] / (timestamp() + '-' + uuid.uuid4().hex[:8])
        root.mkdir(parents=True, exist_ok=False)
        report = dict(schema_version='0.1', scenario=scenario, repeat=repetitions,
                      status='running', executions=[], output=str(root.resolve()))
        write_json(root / 'scenario.json', scenario)
        original = None
        armed = False
        caught = None
        try:
            ping = await session.ping()
            if ping.get('world_ready') is not True:
                raise ScenarioError('Load a game first so its camera/time controls can be restored')
            if ping.get('schema_version') != '0.1':
                raise ScenarioError('Probe does not support state schema 0.1')
            if ping.get('saved_origins_required') is True:
                prepared = ping.get('saved_origins')
                if (ping.get('saved_origins_prepared') is not True or not isinstance(prepared, dict)
                        or prepared.get('prepared') is not True or prepared.get('save_name') != scenario['save']):
                    raise ScenarioError('Load this scenario save through load_save(wait=True) before run_scenario')
                report['source_fingerprint'] = validate_origin_fingerprint(prepared.get('source_fingerprint'))
            report['control_capture_observations'] = []
            original = await wait_stable_controls(
                session, observations=report['control_capture_observations'])
            guard = dict(restore_required=True, save=scenario['save'], controls=original,
                         instance_id=session.instance, run=str(root.resolve()))
            write_json(guard_path, guard)
            armed = True
            deadline = time.monotonic() + positive_timeout(cfg.get('scenario_timeout', 1800), 'scenario_timeout')
            session.deadline = deadline
            for index in range(1, repetitions + 1):
                execution = dict(execution=index, status='running', checkpoints=[], actions=[])
                report['executions'].append(execution)
                folder = root / str(index)
                folder.mkdir()
                if time.monotonic() >= deadline:
                    raise ScenarioError('Scenario exceeded scenario_timeout')
                await session.call('pause', paused=True)
                await session.call('set_camera_free', enabled=original['free_camera'])
                execution['load'] = await session.load(scenario['save'], lock_edge=True)
                saved_origins = execution['load'].get('saved_origins')
                if saved_origins is not None:
                    fingerprint = saved_origins['source_fingerprint']
                    if report.get('source_fingerprint') is not None and fingerprint != report['source_fingerprint']:
                        raise ScenarioError('Starting save changed between scenario repetitions')
                    report['source_fingerprint'] = fingerprint
                if scenario['speed'] > 0:
                    await session.call('set_game_speed', speed=scenario['speed'], preserve_pause=True)
                start = await session.call('get_clock')
                origin = start['elapsed_seconds']
                execution['initial_clock'] = start
                groups = defaultdict(lambda: dict(actions=[], checkpoints=[]))
                for action in scenario['actions']:
                    groups[action['at']]['actions'].append(action)
                for checkpoint in scenario['checkpoints']:
                    groups[checkpoint['at']]['checkpoints'].append(checkpoint)
                logical_pause = scenario['speed'] == 0
                previous_at = 0
                for at, group in sorted(groups.items()):
                    if time.monotonic() >= deadline:
                        raise ScenarioError('Scenario exceeded scenario_timeout')
                    if at > previous_at:
                        if logical_pause:
                            raise ScenarioError('Cannot reach a later game time while an action keeps the game paused')
                        remaining = min(cfg.get('run_until_timeout', 120), deadline-time.monotonic())
                        await session.until(origin + at, remaining)
                    await session.ping()
                    for action in group['actions']:
                        command, params = action['command'], action['params']
                        if command == 'pause':
                            logical_pause = params['paused']
                            result = await session.call('pause', paused=True)
                        elif command == 'set_game_speed':
                            logical_pause = params['speed'] == 0
                            if logical_pause:
                                result = await session.call('pause', paused=True)
                            else:
                                result = await session.call(command, speed=params['speed'], preserve_pause=True)
                        else:
                            result = await session.call(command, **params)
                        execution['actions'].append(dict(request=action, result=result,
                                                         clock=await session.call('get_clock')))
                    for point in group['checkpoints']:
                        state, capture = await session.dump(folder / (point['name'] + '.json'))
                        capture.update(name=point['name'], requested_at=at,
                                       actual_at=state['clock']['elapsed_seconds']-origin,
                                       overshoot_seconds=state['clock']['elapsed_seconds']-origin-at)
                        if state['clock']['paused'] is not True:
                            raise ScenarioError('Checkpoint was not captured in pause')
                        execution['checkpoints'].append(capture)
                    previous_at = at
                    session.check_deadline()
                execution['status'] = 'completed'
                write_json(folder / 'execution.json', execution)
            report['status'] = 'completed'
        except BaseException as exc:
            caught = exc
            report['status'] = 'failed'
            report['error'] = type(exc).__name__ + ': ' + str(exc)
            if report['executions'] and report['executions'][-1]['status'] == 'running':
                report['executions'][-1]['status'] = 'failed'
        finally:
            session.deadline = None  # Cleanup has its own bounded transport/load deadlines.
            if armed:
                try:
                    try:
                        await session.cancel()
                    except Exception as exc:
                        report['cancellation_error'] = str(exc)
                    await session.ping()
                    await session.client.call('pause', paused=True)
                    await session.client.call('set_camera_free', enabled=original['free_camera'])
                    await session.load(scenario['save'], lock_edge=True)
                    report['restoration'] = dict(verified=False, save=scenario['save'],
                                               baseline_observations=[], observations=[])
                    restored = await session.restore_controls(original,
                        observations=report['restoration']['observations'],
                        baseline_observations=report['restoration']['baseline_observations'])
                    report['restoration'].update(verified=True, **restored)
                    guard['restore_required'] = False
                    write_json(guard_path, guard)
                except BaseException as exc:
                    report['restoration_error'] = type(exc).__name__ + ': ' + str(exc)
                    report['status'] = 'failed'
                    if caught is None:
                        caught = exc
            report['variability'] = variability(report['executions'])
            write_json(root / 'report.json', report)
            (root / 'report.md').write_text(markdown_report(report), encoding='utf-8')
        if caught is not None:
            raise ScenarioError(str(caught) + '; report: ' + str(root / 'report.json') +
                                ('; restoration required: ' + str(guard_path) if report.get('restoration_error') else '')) from caught
        return dict(status=report['status'], executions=repetitions, output=str(root.resolve()),
                    report=str((root / 'report.json').resolve()), summary=str((root / 'report.md').resolve()),
                    restored=report['restoration']['verified'],
                    checkpoints={name: {k: v for k, v in result.items() if k not in ('stable_paths', 'variable_fields')}
                                 for name, result in report['variability'].items()})


async def run_scenario_file(path, cfg, repeat=None, client=None):
    return await execute_scenario(load_scenario(path), cfg, repeat=repeat, client=client)


async def restore_interrupted_scenario(cfg, client=None, save=None):
    """Use the saved cleanup record after an MCP exit or a supervised game crash.

This is an explicit recovery operation, never a retry of an uncertain action or
an attempt to resume the invalidated execution in a different game process.
An explicit save overrides only the recovery load, for controls known to belong
to another save. The original record is kept until those controls are verified.
"""
    if save is not None:
        save_name(save)
    with scenario_lock(cfg['runtime']):
        guard_path = Path(cfg['runtime']) / 'oracle-restoration.json'
        if not guard_path.is_file():
            return dict(restored=False, reason='no_restoration_record')
        guard = json.loads(guard_path.read_text(encoding='utf-8'))
        if not guard.get('restore_required'):
            return dict(restored=False, reason='already_restored')
        original = guard['controls']
        control_params(original)
        name = save_name(guard['save'] if save is None else save)
        session = OracleSession(cfg, client)
        status = await session.ping()
        if not status.get('world_ready'):
            raise ScenarioError('Wait for the watchdog to load the game before restoration')
        await session.client.call('pause', paused=True)
        await session.client.call('set_camera_free', enabled=original['free_camera'])
        await session.load(name, lock_edge=True)
        attempt = dict(started_at=timestamp(), instance_id=session.instance,
                       save=name, baseline_observations=[], observations=[])
        try:
            restored = await session.restore_controls(original,
                observations=attempt['observations'],
                baseline_observations=attempt['baseline_observations'])
        except BaseException as exc:
            attempt['error'] = type(exc).__name__ + ': ' + str(exc)
            guard['recovery_attempt'] = attempt
            write_json(guard_path, guard)
            raise
        attempt.update(restored)
        guard['recovery_attempt'] = attempt
        guard.update(restore_required=False, recovered_at=timestamp(),
                     recovery_instance_id=session.instance, recovery_save=name)
        write_json(guard_path, guard)
        return dict(restored=True, save=name, recovery_save=name,
                    scene=restored['scene'], pose_verified_in_pause=restored['pose_verified_in_pause'],
                    unpaused_after_verification=restored['unpaused_after_verification'],
                    record=str(guard_path.resolve()))
