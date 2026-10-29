"""Deterministic oracle protocol fixture; never reads or launches Kenshi.

The historical FakePlugin remains unchanged. This fixture reuses its loopback
server lifecycle, while making unsupported oracle commands fail explicitly.
Time advances only when a pending run_until operation is polled to completion.
The initial fixture has already been prepared with an explicit x1 selection.
Loading invalidates that tracked selection, as in the native 0.9.1 protocol.
"""
import asyncio
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import time

from fake_plugin import FakePlugin
from oracle_identity import validate_saved_handles
from oracle_schema import canonical_bytes
from probe import ProbeError


def sample_state():
    """Own synthetic data, unrelated to any game save or asset."""
    first, second = 'hand:1:7:101:1:1001', 'hand:1:7:101:2:1002'
    squad = 'hand:34:7:101:0:0'
    return dict(
        schema_version='0.1',
        clock=dict(day=2, hour=12, elapsed_seconds=216000, speed=0, paused=True),
        characters=[dict(id=identity, name=name, race_id='fixture-race',
                         faction_id='fixture-faction', squad_id=squad,
                         position=[index, 0, 0], state='alive',
                         health=[dict(id='fixture-head:neither', current=100, stun=0, maximum=100)],
                         order=None)
                    for index, (identity, name) in enumerate(((first, 'Alpha'), (second, 'Beta')))],
        squads=[dict(id=squad, faction_id='fixture-faction', members=[first, second], leader_id=first)],
        factions=[dict(id='fixture-faction', name='Fixture faction')], relations=[])


class FakeProbe(FakePlugin):
    def __init__(self, output_directory, state=None, *, mode='normal', completion_polls=1,
                 require_saved_origins=False, save_root=None, origin_aliases=None,
                 camera_tracking_base_offset=None, camera_move_duration=0):
        super().__init__(mode)
        self.output_directory = Path(output_directory).resolve()
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.initial_state = deepcopy(sample_state() if state is None else state)
        self.state = deepcopy(self.initial_state)
        self.selected_speed = self.state['clock']['speed'] or 1
        self.requests = []
        self.loads = []
        self.operations = {}
        self.completion_polls = completion_polls
        self.free_camera = False
        self.edge_scrolling = True
        self.camera_owned = False
        self._saved_edge = True
        self.camera_center = [0, 0, 0]
        self.camera_orientation = [1, 0, 0, 0]
        self.camera_zoom = -20
        self.camera_follow_id = None
        self.camera_follow_offset = [0, 0, 0]
        self.camera_tracking_base_offset = list([0, 0, 0] if camera_tracking_base_offset is None else camera_tracking_base_offset)
        if (len(self.camera_tracking_base_offset) != 3
                or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e7
                       for v in self.camera_tracking_base_offset)
                or type(camera_move_duration) not in (int, float)
                or not math.isfinite(camera_move_duration) or not 0 <= camera_move_duration <= 10):
            raise ValueError('Invalid synthetic camera baseline or move duration')
        self.camera_move_duration = camera_move_duration
        self._camera_pending = None
        self._camera_sequence = 0
        self._camera_tracking_active = False
        self._camera_transition = None
        self.failures = {}
        if type(require_saved_origins) is not bool or (require_saved_origins and save_root is None):
            raise ValueError('Required saved origins need an explicit synthetic save_root')
        self.require_saved_origins = require_saved_origins
        self.save_root = str(Path(save_root).resolve()) if save_root is not None else None
        self.origin_aliases = deepcopy({} if origin_aliases is None else origin_aliases)
        if type(self.origin_aliases) is not dict or any(
                type(value) is not str or not value for value in self.origin_aliases.values()):
            raise ValueError('origin_aliases must map complete saved handles to current string IDs')
        for identity in self.origin_aliases:
            validate_saved_handles([identity])
        self.world_ready = True
        self.instance_id = self._origin_instance = 'fake-instance'
        self._origin_sequence = 0
        self._loaded_save = None
        self._clear_origins()

    def _clear_origins(self):
        self._origin_committed = None
        self._origin_pending = None
        self._origin_bindings = {}

    def _origin_state(self):
        committed, pending = self._origin_committed, self._origin_pending
        result = dict(prepared=committed is not None,
                      save_name=committed['save_name'] if committed else None,
                      source_fingerprint=committed['source_fingerprint'] if committed else None,
                      count=len(committed['ids']) if committed else 0,
                      pending_count=len(pending['ids']) if pending else 0,
                      expected_count=pending['count'] if pending else 0)
        if pending:
            result['token'] = pending['token']
        return result

    @staticmethod
    def _origin_keys(params, names):
        if set(params) != set(names):
            raise ProbeError('invalid_request: missing or unknown origin parameter')

    @staticmethod
    def _origin_ids(ids):
        try:
            return validate_saved_handles(ids)
        except ValueError as exc:
            raise ProbeError('invalid_request: ' + str(exc)) from exc

    def _require_origin_checkpoint(self):
        if not self.world_ready:
            raise ProbeError('world_not_ready')
        if any(o['status'] == 'running' for o in self.operations.values()):
            raise ProbeError('busy: wait for run_until before resolving or registering origins')
        if not self.state['clock']['paused']:
            raise ProbeError('invalid_request: pause before resolving or registering origins')

    def _origin_resolution(self, saved):
        collection = 'characters' if saved.split(':')[1] == '1' else 'squads'
        current = self.origin_aliases.get(saved, saved)
        loaded = any(row['id'] == current for row in self.state[collection])
        return dict(saved_id=saved, current_id=current if loaded else None, loaded=loaded,
                    resolved=saved in self.origin_aliases or loaded)

    def _origin_token(self, candidate):
        if (type(candidate) is not str or not candidate or len(candidate) > 200 or '\0' in candidate):
            raise ProbeError('invalid_request: invalid origin token')
        if self._origin_pending is None or self._origin_pending['token'] != candidate:
            raise ProbeError('origin_context_token_invalid: absent or stale token')
        return self._origin_pending

    def _origin_snapshot(self):
        if self._origin_committed is None:
            raise ProbeError('origin_context_required: prepare saved origins before dump_state')
        snapshot, bindings = self._build_origin_snapshot(self._origin_committed, self._origin_bindings)
        self._origin_bindings = bindings
        return snapshot

    def _build_origin_snapshot(self, committed, previous_bindings):
        live = {row['id'] for collection in ('characters', 'squads') for row in self.state[collection]}
        bindings = {current: saved for current, saved in previous_bindings.items() if current in live}
        reverse = {saved: current for current, saved in bindings.items()}
        for saved in committed['ids']:
            current = self._origin_resolution(saved)['current_id']
            if current is None:
                # Exact complete equality also covers a retained object whose
                # synthetic resolver no longer reports it. No name/partial key.
                current = saved if saved in live else None
            if current is None:
                continue
            if ((current in bindings and bindings[current] != saved)
                    or (saved in reverse and reverse[saved] != current)
                    or (current != saved and saved in live)):
                raise ProbeError('origin_identity_ambiguous: origin resolution is not bijective')
            bindings[current], reverse[saved] = saved, current
        snapshot = deepcopy(self.state)
        for row in snapshot['characters']:
            for key in ('id', 'squad_id'):
                row[key] = bindings.get(row[key], row[key])
            if row['order'] is not None:
                target = row['order']['target_id']
                row['order']['target_id'] = bindings.get(target, target)
        for row in snapshot['squads']:
            for key in ('id', 'leader_id'):
                row[key] = bindings.get(row[key], row[key])
            row['members'] = sorted(bindings.get(value, value) for value in row['members'])
            if len(set(row['members'])) != len(row['members']):
                raise ProbeError('origin_identity_ambiguous: duplicate canonical squad member')
        for collection in ('characters', 'squads'):
            rows = snapshot[collection]
            rows.sort(key=lambda row: row['id'])
            if len({row['id'] for row in rows}) != len(rows):
                raise ProbeError('origin_identity_ambiguous: duplicate canonical entity ID')
        return snapshot, bindings

    def _origin_source(self):
        current_characters = {row['id'] for row in self.state['characters']}
        return dict(save_name=self._origin_committed['save_name'],
                    source_fingerprint=self._origin_committed['source_fingerprint'],
                    count=len(self._origin_committed['ids']), matched_count=len(self._origin_bindings),
                    remapped_characters=sum(current != saved and current in current_characters
                                            for current, saved in self._origin_bindings.items()),
                    remapped_squads=sum(current != saved and current not in current_characters
                                        for current, saved in self._origin_bindings.items()))

    def _input_id(self, identity, collection):
        live = {row['id'] for row in self.state[collection]}
        if identity in live:
            return identity
        cached = next((current for current, saved in self._origin_bindings.items()
                       if saved == identity and current in live), None)
        resolved = None
        if identity in self.origin_aliases:
            resolved = self._origin_resolution(identity)['current_id']
            if resolved not in live:
                resolved = None
        if cached is not None:
            if resolved is not None and resolved != cached:
                raise ProbeError('origin_identity_ambiguous: saved input resolves to another loaded object')
            return cached
        return resolved if resolved is not None else identity

    def _clock(self):
        self.state['clock']['speed'] = 0 if self.state['clock']['paused'] else (self.selected_speed or 1)
        return deepcopy(self.state['clock'])

    def _advance(self, seconds):
        clock = self.state['clock']
        clock.update(elapsed_seconds=seconds, day=int(seconds // 86400), hour=(seconds % 86400) / 3600)
        for character in self.state['characters']:
            order = character['order']
            if order is not None and order['type'] == 'move':
                character['position'] = deepcopy(order['position'])

    def _operation(self, operation_id):
        if operation_id not in self.operations:
            raise ProbeError('not_found: unknown run_until operation')
        return self.operations[operation_id]

    def _operation_result(self, operation):
        return dict(operation_id=operation['operation_id'], status=operation['status'],
                    target_seconds=operation['target_seconds'], clock=self._clock())

    def _camera_params(self, params):
        required = {'camera_center', 'camera_orientation', 'camera_zoom', 'free_camera',
                    'edge_scrolling', 'speed', 'paused'}
        if not required <= set(params) or set(params)-required-{'camera_position', 'camera_follow_id'}:
            raise ProbeError('invalid_request: missing or unknown camera parameter')
        def vector(value, size, bound):
            return (type(value) is list and len(value) == size
                    and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= bound for v in value))
        if (not vector(params['camera_center'], 3, 1e7)
                or ('camera_position' in params and not vector(params['camera_position'], 3, 1e7))
                or not vector(params['camera_orientation'], 4, 1.001)
                or abs(sum(v*v for v in params['camera_orientation'])-1) > .01):
            raise ProbeError('invalid_request: invalid camera center or quaternion')
        if any(type(params[key]) is not bool for key in ('free_camera', 'edge_scrolling', 'paused')):
            raise ProbeError('invalid_request: camera flags must be boolean')
        zoom, speed = params['camera_zoom'], params['speed']
        if (type(zoom) not in (int, float) or not math.isfinite(zoom) or abs(zoom) > 1e7
                or (not params['free_camera'] and zoom >= 0)
                or type(speed) not in (int, float) or not 0.000001 <= speed <= 5):
            raise ProbeError('invalid_request: invalid camera zoom or speed')
        follow = params.get('camera_follow_id')
        if follow is not None and (type(follow) is not str or not follow or len(follow) > 512 or '\0' in follow):
            raise ProbeError('invalid_request: invalid camera follow identity')
        follow = self._input_id(follow, 'characters')
        if follow is not None and not any(row['id'] == follow for row in self.state['characters']):
            raise ProbeError('not_found: camera follow target is not a loaded character')
        result = deepcopy(params)
        result['raw_follow_id'] = follow
        return result

    def _camera_baseline(self):
        if self.camera_follow_id is None:
            return deepcopy(self._camera_pending['camera_center'] if self._camera_pending else self.camera_center)
        actor = next((row for row in self.state['characters'] if row['id'] == self.camera_follow_id), None)
        if actor is None:
            return deepcopy(self.camera_center)
        return [actor['position'][i]+self.camera_tracking_base_offset[i]+self.camera_follow_offset[i]
                for i in range(3)]

    def _update_camera(self):
        if self._camera_transition is not None:
            transition = self._camera_transition
            progress = min(1, (time.monotonic()-transition['started'])/self.camera_move_duration)
            baseline = self._camera_baseline()
            self.camera_center = [old+(new-old)*progress for old, new in zip(transition['from'], baseline)]
            if progress >= 1:
                self._camera_transition = None
        elif self._camera_tracking_active:
            self.camera_center = self._camera_baseline()

    def _scene_state(self):
        self._update_camera()
        clock = self._clock()
        return dict(paused=clock['paused'], game_speed=clock['speed'], selected_game_speed=self.selected_speed,
                    frame_speed_multiplier=clock['speed'], free_camera=self.free_camera,
                    edge_scrolling=self.edge_scrolling, scene_camera_control_owned=self.camera_owned,
                    camera_position=deepcopy(self.camera_center), camera_center=deepcopy(self.camera_center),
                    camera_orientation=deepcopy(self.camera_orientation), camera_zoom=self.camera_zoom,
                    camera_node_position=[0, 0, self.camera_zoom],
                    camera_follow_id=(self._origin_bindings.get(self.camera_follow_id, self.camera_follow_id)
                                      if self._origin_committed is not None else self.camera_follow_id),
                    camera_restore_token=self._camera_pending['token'] if self._camera_pending else None,
                    camera_move_duration=self.camera_move_duration,
                    game_total_hours=clock['elapsed_seconds']/3600,
                    loaded_character_count=len(self.state['characters']), frame=self.frame)

    async def call(self, command, **params):
        """Also usable as an in-process client by tests of orchestration failures."""
        self.calls.append(command)
        self.requests.append(dict(command=command, params=deepcopy(params)))
        if command in self.failures:
            raise ProbeError(self.failures[command])
        if not self.world_ready or self.instance_id != self._origin_instance:
            self._clear_origins()
            self._camera_pending = self._camera_transition = None
            self._camera_tracking_active = False
            if self.instance_id != self._origin_instance:
                self._loaded_save = None
            self._origin_instance = self.instance_id
        self.frame += 1
        if command in ('ping', 'heartbeat'):
            return dict(plugin_version='fake-oracle', game_version='fake', schema_version='0.1',
                        process_id=42, instance_id=self.instance_id, oracle_available=True,
                        frame=self.frame, service_frame=self.frame, timestamp_ms=self.frame,
                        service_timestamp_ms=self.frame, world_ready=self.world_ready, loading=False,
                        paused=self.state['clock']['paused'],
                        frame_speed_multiplier=self._clock()['speed'],
                        set_game_speed_preserve_pause_available=True,
                        test_save_pause_on_ready_available=True, load_pause_pending=False, save_signal=0,
                        save_root=self.save_root, saved_origins_required=self.require_saved_origins,
                        saved_origins_prepared=self._origin_committed is not None,
                        saved_origins=self._origin_state())
        if command == 'resolve_saved_handles':
            self._origin_keys(params, ('ids',))
            ids = self._origin_ids(params['ids'])
            self._require_origin_checkpoint()
            return dict(resolutions=[self._origin_resolution(saved) for saved in ids])
        if command == 'begin_saved_origins':
            self._origin_keys(params, ('save_name', 'source_fingerprint', 'count'))
            save, fingerprint, count = params['save_name'], params['source_fingerprint'], params['count']
            if (type(save) is not str or not save or len(save.encode('utf-8')) > 128
                    or save in ('.', '..') or save.endswith(('.', ' '))
                    or any(ord(c) < 32 or ord(c) == 127 or c in '<>:"/\\|?*' for c in save)):
                raise ProbeError('invalid_request: invalid saved origin save_name')
            if type(fingerprint) is not str or re.fullmatch(r'sha256:[0-9a-f]{64}', fingerprint) is None:
                raise ProbeError('invalid_request: invalid source_fingerprint')
            if (type(count) not in (int, float) or not 0 <= count <= 100000
                    or not math.isfinite(count) or count != int(count)):
                raise ProbeError('invalid_request: origin count must be an integer from 0 to 100000')
            self._require_origin_checkpoint()
            if save != self._loaded_save:
                raise ProbeError('origin_context_save_mismatch')
            self._origin_sequence += 1
            self._origin_pending = dict(save_name=save, source_fingerprint=fingerprint,
                                        count=int(count), ids=[],
                                        token=f'{self.instance_id}:origins:{self._origin_sequence}')
            return self._origin_state()
        if command == 'add_saved_origins':
            self._origin_keys(params, ('token', 'ids'))
            ids = self._origin_ids(params['ids'])
            self._require_origin_checkpoint()
            pending = self._origin_token(params['token'])
            if len(pending['ids']) + len(ids) > pending['count']:
                raise ProbeError('invalid_request: origin chunk exceeds registration count')
            if len(set(ids)) != len(ids) or set(ids).intersection(pending['ids']):
                raise ProbeError('origin_identity_ambiguous: duplicate complete saved origin ID')
            pending['ids'].extend(ids)
            return self._origin_state()
        if command == 'commit_saved_origins':
            self._origin_keys(params, ('token',))
            self._require_origin_checkpoint()
            pending = self._origin_token(params['token'])
            if len(pending['ids']) != pending['count']:
                raise ProbeError('origin_context_incomplete')
            candidate = deepcopy(pending)
            _, bindings = self._build_origin_snapshot(candidate, {})
            # Publish neither the context nor its aliases until the complete
            # candidate is verified. An exception keeps old context + token.
            self._origin_committed = candidate
            self._origin_pending = None
            self._origin_bindings = bindings
            return self._origin_state()
        if command == 'get_clock':
            return self._clock()
        if command == 'pause':
            paused = params.get('paused', True)
            if type(paused) is not bool:
                raise ProbeError('invalid_params')
            self.state['clock']['paused'] = paused
            self._clock()
            if paused:
                for operation in self.operations.values():
                    if operation['status'] == 'running':
                        operation['status'] = 'cancelled'
            return dict(paused=paused)
        if command == 'set_game_speed':
            speed = params.get('speed', 1)
            if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 <= speed <= 5:
                raise ProbeError('invalid_params')
            if params.get('preserve_pause', False) and speed == 0:
                raise ProbeError('invalid_request: preserve_pause requires a positive speed')
            before = self.state['clock']['paused']
            if speed > 0:
                self.selected_speed = speed
            if not params.get('preserve_pause', False):
                self.state['clock']['paused'] = speed == 0
            self._clock()
            return dict(speed=speed, paused_before=before, paused=self.state['clock']['paused'],
                        preserve_pause=params.get('preserve_pause', False))
        if command == 'load_save':
            name = params.get('name')
            if not isinstance(name, str) or not name or any(x in name for x in '/\\:\r\n\0') or name in ('.', '..'):
                raise ProbeError('invalid_params')
            self.loads.append(name)
            self._loaded_save = name
            self._clear_origins()
            self._camera_pending = self._camera_transition = None
            self._camera_tracking_active = False
            self.state = deepcopy(self.initial_state)
            self.selected_speed = None
            self.camera_follow_id = None
            self.state['clock']['paused'] = params.get('pause_on_ready', True)
            self._clock()
            for operation in self.operations.values():
                if operation['status'] == 'running':
                    operation['status'] = 'cancelled'
            if params.get('lock_edge', False):
                self._lock_camera()
            return dict(accepted=True, name=name, pause_on_ready=self.state['clock']['paused'],
                        camera_edge_locked=self.camera_owned, battle_tracking_restored=False,
                        save_root=self.save_root)
        if command == 'run_until':
            target = params.get('target_seconds')
            timeout = params.get('timeout_seconds', 120)
            if (type(target) not in (int, float) or not math.isfinite(target)
                    or not 0 <= target <= 1e9
                    or type(timeout) not in (int, float) or not math.isfinite(timeout) or not .1 <= timeout <= 3600):
                raise ProbeError('invalid_params')
            if any(o['status'] == 'running' for o in self.operations.values()):
                raise ProbeError('busy')
            if not self.state['clock']['paused'] or self.selected_speed is None or self.selected_speed <= 0:
                raise ProbeError('invalid_request: run_until requires pause and an explicitly selected positive speed')
            complete = target <= self.state['clock']['elapsed_seconds']
            operation = dict(operation_id=str(len(self.operations) + 1),
                             status='completed' if complete else 'running', target_seconds=target,
                             polls=0, timeout_seconds=timeout)
            self.operations[operation['operation_id']] = operation
            self.state['clock']['paused'] = complete
            return self._operation_result(operation)
        if command in ('run_until_status', 'cancel_run_until'):
            operation = self._operation(params.get('operation_id'))
            if operation['status'] == 'running':
                if command == 'cancel_run_until':
                    operation['status'] = 'cancelled'
                elif self.mode == 'run_timeout':
                    operation['status'] = 'timed_out'
                elif self.mode != 'run_stalled':
                    operation['polls'] += 1
                    if operation['polls'] >= self.completion_polls:
                        self._advance(operation['target_seconds'])
                        operation['status'] = 'completed'
                self.state['clock']['paused'] = operation['status'] != 'running'
            return self._operation_result(operation)
        if command == 'dump_state':
            filename = params.get('filename')
            if not isinstance(filename, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,100}\.json', filename) is None:
                raise ProbeError('invalid_params')
            if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])\.json', filename, re.I):
                raise ProbeError('invalid_params')
            if not self.state['clock']['paused'] or any(o['status'] == 'running' for o in self.operations.values()):
                raise ProbeError('invalid_request: pause before taking a checkpoint')
            path = self.output_directory / filename
            self._clock()
            if not self.world_ready:
                raise ProbeError('world_not_ready')
            snapshot = self._origin_snapshot() if self.require_saved_origins else self.state
            payload = canonical_bytes(snapshot)
            if self.mode == 'invalid_state':
                payload = b'{"schema_version":"0.1"}\n'
            try:
                with path.open('xb') as output:
                    output.write(payload)
            except FileExistsError as exc:
                raise ProbeError('already_exists') from exc
            result = dict(path=str(path), schema_version='0.1', bytes=len(payload))
            if self.require_saved_origins:
                result['identity_source'] = self._origin_source()
            return result
        if command == 'issue_order':
            kind = params.get('type')
            if not self.state['clock']['paused']:
                raise ProbeError('invalid_request: issue_order requires pause')
            if kind not in ('move', 'attack') or ('character_id' in params) == ('squad_id' in params):
                raise ProbeError('invalid_params')
            actor_id = self._input_id(params['character_id'], 'characters') if 'character_id' in params else None
            squad_id = self._input_id(params['squad_id'], 'squads') if 'squad_id' in params else None
            actors = [row for row in self.state['characters']
                      if (row['id'] == actor_id if actor_id is not None else row['squad_id'] == squad_id)]
            if not actors:
                raise ProbeError('entity_not_found')
            if kind == 'move':
                position = params.get('position')
                if (not isinstance(position, list) or len(position) != 3 or 'target_id' in params
                        or any(type(value) not in (int, float) or not math.isfinite(value) for value in position)):
                    raise ProbeError('invalid_params')
            elif 'position' in params or not any(row['id'] == self._input_id(params.get('target_id'), 'characters') for row in self.state['characters']):
                raise ProbeError('entity_not_found')
            for actor in actors:
                actor['order'] = dict(type=kind, target_id=self._input_id(params.get('target_id'), 'characters'), position=deepcopy(params.get('position')))
            return dict(accepted=True, type=kind, affected_characters=len(actors))
        if command == 'get_scene_state':
            return self._scene_state()
        if command == 'prepare_scene_control':
            if not self.world_ready:
                raise ProbeError('world_not_ready')
            if self._camera_pending is not None:
                raise ProbeError('camera_restore_busy')
            if not self.state['clock']['paused']:
                raise ProbeError('invalid_request: pause before preparing camera restoration')
            requested = self._camera_params(params)
            self._camera_sequence += 1
            requested['token'] = f'{self.instance_id}:camera:{self._camera_sequence}'
            self._camera_pending = requested
            self._lock_camera()
            self.free_camera = requested['free_camera']
            self.camera_orientation = deepcopy(requested['camera_orientation'])
            self.camera_zoom = requested['camera_zoom']
            self.camera_follow_id = requested['raw_follow_id']
            self.camera_follow_offset = [0, 0, 0]
            self.selected_speed = requested['speed']
            self.state['clock']['paused'] = True
            self._camera_tracking_active = self.camera_follow_id is not None
            if self.camera_move_duration:
                self._camera_transition = dict(started=time.monotonic(), **{'from': deepcopy(self.camera_center)})
            else:
                self.camera_center = self._camera_baseline()
            return dict(self._scene_state(), prepared=True, restored=False, token=requested['token'])
        if command == 'commit_scene_control':
            self._origin_keys(params, ('token',))
            token = params['token']
            if (type(token) is not str or not token or len(token) > 200 or '\0' in token):
                raise ProbeError('invalid_request: invalid camera restore token')
            requested = self._camera_pending
            if requested is None or token != requested['token']:
                raise ProbeError('camera_restore_token_invalid')
            self._update_camera()
            if (not self.state['clock']['paused'] or not self.camera_owned or self.edge_scrolling
                    or self.free_camera != requested['free_camera']
                    or self.camera_zoom != requested['camera_zoom']
                    or self.camera_orientation != requested['camera_orientation']
                    or self.selected_speed != requested['speed']
                    or self.camera_follow_id != requested['raw_follow_id']):
                raise ProbeError('camera_restore_state_changed')
            if self.camera_follow_id is not None:
                correction = [wanted-observed for wanted, observed
                              in zip(requested['camera_center'], self.camera_center)]
                offset = [old+delta for old, delta in zip(self.camera_follow_offset, correction)]
                if any(not math.isfinite(value) or abs(value) > 1e7 for value in offset):
                    raise ProbeError('invalid_request: camera correction exceeds bounds')
                self.camera_follow_offset = offset
            self._camera_transition = None
            self.camera_center = deepcopy(requested['camera_center'])
            self.edge_scrolling = requested['edge_scrolling']
            self.camera_owned = False
            self.selected_speed = requested['speed']
            self.state['clock']['paused'] = requested['paused']
            self._camera_pending = None
            return dict(self._scene_state(), prepared=False, restored=True)
        if command == 'set_camera_free':
            self.free_camera = params['enabled']
            if params.get('lock_edge', False):
                self._lock_camera()
            if params.get('release_edge', False):
                self.edge_scrolling = self._saved_edge
                self.camera_owned = False
            return dict(free_camera=self.free_camera, edge_scrolling=self.edge_scrolling,
                        scene_camera_control_owned=self.camera_owned)
        if command == 'restore_scene_control':
            zoom, free = params.get('camera_zoom'), params.get('free_camera')
            if (type(zoom) not in (int, float) or not math.isfinite(zoom) or abs(zoom) > 1e7
                    or type(free) is not bool):
                raise ProbeError('invalid_request: invalid camera zoom or mode')
            if not free and zoom >= 0:
                raise ProbeError('invalid_request: strategy camera_zoom must be negative local Z')
            follow_id = self._input_id(params.get('camera_follow_id'), 'characters')
            if follow_id is not None and not any(row['id'] == follow_id for row in self.state['characters']):
                raise ProbeError('not_found: camera follow target is not a loaded character')
            self.camera_center = deepcopy(params['camera_center'])
            self._camera_pending = self._camera_transition = None
            self._camera_tracking_active = False
            self.camera_orientation = deepcopy(params['camera_orientation'])
            self.camera_zoom = params['camera_zoom']
            self.camera_follow_id = follow_id
            self.free_camera = params['free_camera']
            self.edge_scrolling = params['edge_scrolling']
            self.camera_owned = False
            self.selected_speed = params['speed']
            self.state['clock']['paused'] = params['paused']
            self._clock()
            return dict(restored=True, paused=self.state['clock']['paused'])
        if command == 'get_frame_stats':
            return dict(count=params.get('n', 300), mean_ms=16,
                        statistics_detail=dict(mode=params.get('detail', 'aggregates')))
        raise ProbeError('not_implemented: ' + command)

    def _lock_camera(self):
        if not self.camera_owned:
            self._saved_edge = self.edge_scrolling
        self.camera_owned = True
        self.edge_scrolling = False

    async def handle(self, reader, writer):
        try:
            while raw := await reader.readline():
                request_id = None
                try:
                    request = json.loads(raw)
                    if not isinstance(request, dict) or not isinstance(request.get('id'), str):
                        raise ValueError('request id required')
                    request_id = request['id']
                    if not isinstance(request.get('command'), str) or not isinstance(request.get('params', {}), dict):
                        raise ValueError('invalid command or params')
                    if self.mode == 'hang':
                        await reader.read()
                        return
                    result = await self.call(request['command'], **request.get('params', {}))
                    reply = dict(id=request_id, result=result)
                except (ValueError, TypeError, KeyError, ProbeError) as exc:
                    reply = dict(id=request_id, error=dict(code='invalid_request' if request_id is None else str(exc).split(':')[0], message=str(exc)))
                if self.mode == 'wrong_id':
                    reply['id'] = 'wrong'
                wire = (json.dumps(reply, allow_nan=False) + '\n').encode('utf-8')
                if self.mode == 'invalid':
                    wire = b'not json\n'
                writer.write(wire[:3])
                await writer.drain()
                writer.write(wire[3:])
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
