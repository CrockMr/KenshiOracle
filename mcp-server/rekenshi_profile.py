"""Recoverable RE_Kenshi 0.3.5 settings transaction, separate from process launch.

The caller supplies an independent ownership/process observer. This module never
launches or stops a game, and never treats an INI read as runtime verification.
All mutations require the observer to establish that the game is stopped.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid


REQUESTED_SETTINGS = dict.fromkeys(('FixRNG', 'UseCustomGameSpeeds', 'AttackSlotsOverride',
                                   'MaxFactionSizeOverride', 'MaxSquadSizeOverride',
                                   'MaxSquadsOverride'), False)
RUNTIME_METHOD = 'rekenshi_0_3_5_ui_and_crt_exports'
MAX_CONFIG_BYTES = 1024 * 1024
MAX_JOURNAL_BYTES = 4 * 1024 * 1024
_HASH = re.compile(r'^[0-9a-f]{64}$')
_STATES = {'captured', 'preparing', 'prepared', 'verified', 'prepare_failed',
           'restoring', 'restore_failed', 'restored'}
KNOWN_DEVIATIONS = [
    {'id': 'rekenshi-speed-callbacks', 'simulation_effect': 'unknown', 'disableable': False,
     'description': 'Custom speeds are off, but RE_Kenshi still replaces the x2/x5 callbacks and keyboard listener.',
     'source': 'https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1442'},
    {'id': 'rekenshi-startup-srand', 'simulation_effect': 'yes', 'disableable': False,
     'description': 'RE_Kenshi seeds the CRT during initialization even with FixRNG disabled. No original RNG-stream equivalence is claimed.',
     'source': 'https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/MiscHooks.cpp#L267'},
]


class ReKenshiProfileError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise ReKenshiProfileError(code, message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail('invalid_json', 'Duplicate JSON key in settings or recovery journal')
        result[key] = value
    return result


def _constant(_value):
    _fail('invalid_json', 'Non-finite JSON number')


def _decode(data):
    try:
        result = json.loads(data.decode('utf-8-sig'), object_pairs_hook=_pairs,
                            parse_constant=_constant)
        # This also catches overflowing exponent notation such as 1e9999.
        json.dumps(result, allow_nan=False, ensure_ascii=False).encode('utf-8')
    except ReKenshiProfileError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReKenshiProfileError('invalid_json', 'Invalid UTF-8 JSON document') from exc
    if type(result) is not dict:
        _fail('invalid_json', 'Settings or recovery journal must be an object')
    return result


def _settings(value):
    for key in REQUESTED_SETTINGS:
        if type(value.get(key)) is not bool:
            _fail('invalid_settings', 'All six RE_Kenshi gameplay-profile settings must be explicit booleans')
    return value


def _metadata(value):
    if (type(value) is not dict or value.get('kenshi_version') != '1.0.65'
            or value.get('rekenshi_version') != '0.3.5'
            or not _HASH.fullmatch(str(value.get('rekenshi_sha256', '')))):
        _fail('unsupported_reference', 'Reference metadata must pin Kenshi 1.0.65, RE_Kenshi 0.3.5 and its SHA-256')
    return value


def _path(path, *, missing=False):
    # Do not resolve links before examining the spelling and all its ancestors.
    path = Path(os.path.abspath(os.fspath(path)))
    for candidate in reversed((path, *path.parents)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            if missing:
                continue
            _fail('missing_file', 'Required settings/recovery path does not exist')
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            _fail('unsafe_path', 'Settings/recovery path contains a link or reparse point')
        if candidate == path:
            if not stat.S_ISREG(info.st_mode):
                _fail('unsafe_path', 'Settings/recovery path must be a regular file')
            if info.st_nlink > 1:
                _fail('unsafe_path', 'Settings/recovery file has multiple hard links')
        elif not stat.S_ISDIR(info.st_mode):
            _fail('unsafe_path', 'Settings/recovery ancestor is not a directory')
    return path


def _read(path, limit):
    path = _path(path)
    before = path.stat()
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            _fail('source_changed', 'Settings/recovery file changed while opening')
        data = stream.read(limit + 1)
    _path(path)
    after = path.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        _fail('source_changed', 'Settings/recovery file changed while reading')
    if len(data) > limit:
        _fail('document_too_large', 'Settings/recovery document exceeds the byte limit')
    return data


def _directories(parent):
    for item in reversed((parent, *parent.parents)):
        if not item.exists():
            item.mkdir()
        info = item.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            _fail('unsafe_path', 'Recovery directory contains a link or reparse point')


def _atomic(path, data, before_replace=None):
    path = _path(path, missing=True)
    _directories(path.parent)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0), 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _path(path, missing=True)
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
        if os.name != 'nt':
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_runtime_evidence(evidence, expected):
    """Validate independent GUI/CRT evidence; the two settings alone never suffice."""
    if type(evidence) is not dict:
        _fail('runtime_unverified', 'Runtime evidence must be an object')
    if (evidence.get('verification_method') != RUNTIME_METHOD
            or evidence.get('evidence_source') != 'runtime_ui'):
        _fail('runtime_unverified', 'Independent runtime GUI and CRT-export evidence is required')
    if (type(evidence.get('process_id')) is not int or evidence['process_id'] != expected['pid']
            or evidence.get('instance_id') != expected['instance_id']):
        _fail('runtime_process_mismatch', 'Runtime evidence belongs to a different process instance')
    settings = evidence.get('settings')
    if type(settings) is not dict:
        _fail('runtime_unverified', 'Runtime evidence has no settings object')
    _settings(settings)
    if any(settings[key] is not value for key, value in expected['settings'].items()):
        _fail('runtime_settings_mismatch', 'Runtime settings do not match the required reference profile')
    # A true FixRNG installs the CRT hooks; a cold false profile must leave both exports original.
    if evidence.get('crt_exports_unmodified') is not (not expected['settings']['FixRNG']):
        _fail('runtime_rng_hooks_mismatch', 'CRT export evidence disagrees with the expected RNG mode')
    exports = evidence.get('crt_exports')
    if type(exports) is not dict or set(exports) != {'rand', 'srand'}:
        _fail('runtime_unverified', 'Both independently checked CRT exports are required')
    unchanged = []
    for symbol, row in exports.items():
        if (type(row) is not dict or row.get('symbol') != symbol
                or type(row.get('checked_bytes')) is not int or row['checked_bytes'] != 16
                or type(row.get('export_rva')) is not int or not 0 <= row['export_rva'] <= 0xffffffff
                or type(row.get('disk_file_offset')) is not int or row['disk_file_offset'] < 0
                or row.get('relocation_overlap') is not False
                or not re.fullmatch(r'[0-9a-f]{32}', str(row.get('disk_prefix_hex', '')))
                or not re.fullmatch(r'[0-9a-f]{32}', str(row.get('memory_prefix_hex', '')))):
            _fail('runtime_unverified', 'CRT export evidence is incomplete or incomparable')
        equal = row['disk_prefix_hex'] == row['memory_prefix_hex']
        if (row.get('unmodified') is not equal
                or row.get('comparison') != ('identical' if equal else 'different')):
            _fail('runtime_unverified', 'CRT byte comparisons contradict their summaries')
        unchanged.append(equal)
    all_unchanged, all_modified = all(unchanged), not any(unchanged)
    if (evidence.get('crt_exports_unmodified') is not all_unchanged
            or evidence.get('crt_exports_modified') is not all_modified
            or evidence.get('runtime_settings_consistent') is not True
            or evidence.get('effective_fix_rng_disabled') is not (not settings['FixRNG'] and all_unchanged)
            or (settings['FixRNG'] and not all_modified)):
        _fail('runtime_rng_hooks_mismatch', 'Runtime RNG consistency evidence is contradictory')
    return deepcopy(evidence)


class ReKenshiProfile:
    """Synchronous lifecycle; orchestration owns process observation and socket calls.

    process_state() returns running/owned booleans and, while running, pid,
    instance_id and started_at (Unix creation time). Metadata must pin
    kenshi_version=1.0.65, rekenshi_version=0.3.5 and rekenshi_sha256.
    """
    def __init__(self, config_path, journal_path, *, process_state, metadata=None):
        self.config_path = Path(os.path.abspath(os.fspath(config_path)))
        self.journal_path = Path(os.path.abspath(os.fspath(journal_path)))
        if self.config_path == self.journal_path:
            _fail('unsafe_path', 'Settings and recovery journal must have different paths')
        if not callable(process_state):
            _fail('process_state_required', 'An independent process observer is required')
        self.process_state = process_state
        self.metadata = deepcopy(metadata or {})
        self.transaction_id = None

    @contextmanager
    def _locked(self):
        lock = self.journal_path.with_name(self.journal_path.name + '.lock')
        _path(lock, missing=True)
        _directories(lock.parent)
        with lock.open('a+b') as stream:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ReKenshiProfileError('profile_busy', 'Another process owns this profile journal') from exc
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _observe(self, *, running):
        try:
            observed = deepcopy(self.process_state())
        except Exception as exc:
            raise ReKenshiProfileError('process_state_unknown', 'Process observer failed') from exc
        if (type(observed) is not dict or type(observed.get('running')) is not bool
                or type(observed.get('owned')) is not bool):
            _fail('process_state_unknown', 'Process observer must provide explicit running/owned state')
        if observed['running'] and not observed['owned']:
            _fail('unowned_process', 'An already running unowned game cannot use or restore this profile')
        if observed['running'] is not running:
            _fail('process_running' if observed['running'] else 'process_stopped',
                  'The process lifecycle does not permit this profile operation')
        if running:
            if (type(observed.get('pid')) is not int or observed['pid'] <= 0
                    or type(observed.get('instance_id')) is not str or not observed['instance_id']
                    or type(observed.get('started_at')) not in (int, float)
                    or not math.isfinite(observed['started_at'])):
                _fail('process_state_unknown', 'A live owned process requires PID, instance and creation time')
        return observed

    def _write(self, record):
        try:
            data = (json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ReKenshiProfileError('invalid_journal', 'Recovery record is not finite UTF-8 JSON') from exc
        if len(data) > MAX_JOURNAL_BYTES:
            _fail('document_too_large', 'Recovery record exceeds the byte limit')
        _atomic(self.journal_path, data)

    def _load(self):
        record = _decode(_read(self.journal_path, MAX_JOURNAL_BYTES))
        try:
            raw = base64.b64decode(record['original']['bytes_base64'], validate=True)
            valid = (record['format_version'] == 1 and record['state'] in _STATES
                     and type(record['restore_required']) is bool
                     and record['restore_required'] is (record['state'] != 'restored'
                         or record['restoration'].get('byte_reapply_required', False))
                     and record['config_path'] == str(self.config_path)
                     and record['original']['sha256'] == _sha(raw)
                     and record['original']['size_bytes'] == len(raw)
                     and len(raw) <= MAX_CONFIG_BYTES
                     and _settings(_decode(raw)) == record['original']['settings']
                     and record['requested'] == REQUESTED_SETTINGS
                     and _metadata(record['metadata']) == record['metadata']
                     and record['known_deviations'] == KNOWN_DEVIATIONS
                     and type(record['restoration']) is dict
                     and type(record['restoration']['file_verified']) is bool
                     and type(record['restoration']['runtime_verified']) is bool
                     and (record['effective'] is None or type(record['effective']) is dict)
                     and (record['state'] != 'restored'
                          or ((record['restoration']['file_verified'] is True
                               or (record['restoration'].get('byte_reapply_required') is True
                                   and record['restoration']['runtime_verified'] is True))
                              and type(record['restored_at']) in (int, float)
                              and math.isfinite(record['restored_at'])))
                     and (record['state'] not in ('prepared', 'verified')
                          or (type(record['prepared_at']) in (int, float)
                              and math.isfinite(record['prepared_at'])
                              and _HASH.fullmatch(record['prepared_sha256']) is not None))
                     and re.fullmatch(r'[0-9a-f]{32}', record['transaction_id']) is not None)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ReKenshiProfileError('invalid_journal', 'Recovery record is incomplete or damaged') from exc
        if not valid:
            _fail('invalid_journal', 'Recovery bytes, hash, settings or lifecycle do not agree')
        if self.transaction_id is not None and self.transaction_id != record['transaction_id']:
            _fail('profile_replaced', 'The recovery journal belongs to a different transaction')
        self.transaction_id = record['transaction_id']
        return record

    def capture(self):
        with self._locked():
            self._observe(running=False)
            if self.journal_path.exists():
                old = self._load()
                if old['state'] != 'restored' or old['restore_required']:
                    _fail('recovery_required', 'An unfinished profile must be restored before recapturing')
            _metadata(self.metadata)
            raw = _read(self.config_path, MAX_CONFIG_BYTES)
            settings = _settings(_decode(raw))
            record = {'format_version': 1, 'transaction_id': uuid.uuid4().hex,
                      'state': 'captured', 'restore_required': True, 'captured_at': time.time(),
                      'config_path': str(self.config_path), 'metadata': deepcopy(self.metadata),
                      'original': {'bytes_base64': base64.b64encode(raw).decode('ascii'),
                                   'sha256': _sha(raw), 'size_bytes': len(raw), 'settings': settings},
                      'requested': deepcopy(REQUESTED_SETTINGS), 'effective': None,
                      'restoration': {'file_verified': False, 'runtime_verified': False},
                      'known_deviations': deepcopy(KNOWN_DEVIATIONS)}
            self._observe(running=False)
            self._write(record)
            self.transaction_id = record['transaction_id']
            return self._provenance(record)

    def prepare(self):
        with self._locked():
            record = self._load()
            self._observe(running=False)
            if record['state'] != 'captured':
                _fail('invalid_lifecycle', 'Only a captured, unmodified profile can be prepared')
            if _sha(_read(self.config_path, MAX_CONFIG_BYTES)) != record['original']['sha256']:
                _fail('source_changed', 'Player settings changed after capture')
            settings = deepcopy(record['original']['settings'])
            settings.update(REQUESTED_SETTINGS)
            raw = (json.dumps(settings, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
            record.update(state='preparing', prepared_at=time.time(), prepared_sha256=_sha(raw))
            self._write(record)  # Durable rollback bytes precede the first config mutation.
            try:
                _atomic(self.config_path, raw, lambda: self._observe(running=False))
                if _read(self.config_path, MAX_CONFIG_BYTES) != raw:
                    _fail('prepare_readback_failed', 'Prepared settings did not survive readback')
                record['state'] = 'prepared'
                self._write(record)
            except Exception:
                # A preceding durable 'preparing' record is already enough to recover.
                record['state'] = 'prepare_failed'
                try:
                    self._write(record)
                except Exception:
                    pass
                raise
            return self._provenance(record)

    def _verify(self, record, evidence, expected_settings, after, validator):
        observed = self._observe(running=True)
        if observed['started_at'] < record[after]:
            _fail('cold_start_required', 'Runtime verification requires a new process after the settings transaction')
        expected = {'pid': observed['pid'], 'instance_id': observed['instance_id'],
                    'settings': expected_settings, 'metadata': deepcopy(record['metadata'])}
        proof = (validator or validate_runtime_evidence)(deepcopy(evidence), deepcopy(expected))
        # An injected adapter may normalize extra fields, but cannot waive these invariants.
        proof = validate_runtime_evidence(proof, expected)
        after_observation = self._observe(running=True)
        if any(after_observation[key] != observed[key] for key in ('pid', 'instance_id', 'started_at')):
            _fail('runtime_process_mismatch', 'The game process changed during verification')
        return {'verified_at': time.time(), 'process': observed, 'evidence': proof}

    def verify_effective(self, evidence, *, validator=None):
        with self._locked():
            record = self._load()
            if record['state'] not in ('prepared', 'verified'):
                _fail('invalid_lifecycle', 'Runtime verification requires a prepared profile')
            try:
                proof = self._verify(record, evidence, REQUESTED_SETTINGS, 'prepared_at', validator)
                current = _read(self.config_path, MAX_CONFIG_BYTES)
                settings = _settings(_decode(current))
                if any(settings[key] is not value for key, value in REQUESTED_SETTINGS.items()):
                    _fail('settings_file_drift', 'The on-disk reference settings changed during the run')
                proof['settings_file_sha256'] = _sha(current)
            except Exception as exc:
                record.update(state='prepared', effective=None,
                              verification_failure={'at': time.time(), 'code': getattr(exc, 'code', type(exc).__name__)})
                self._write(record)
                raise
            record.update(state='verified', effective=proof)
            self._write(record)
            return self._provenance(record)

    def restore(self, *, reapply=False):
        """Restore exact bytes with the game stopped; reapply permits a logged boot rewrite.

        A verified original-settings runtime proof is retained only for an
        explicit reapply. Byte restoration and runtime evidence remain distinct.
        """
        with self._locked():
            record = self._load()
            self._observe(running=False)
            preserved_runtime = (deepcopy(record['restoration']) if reapply
                                 and record['state'] == 'restored'
                                 and record['restoration'].get('runtime_verified') is True else None)
            if record['state'] == 'restored':
                current_hash = _sha(_read(self.config_path, MAX_CONFIG_BYTES))
                if current_hash == record['original']['sha256'] and not record['restore_required']:
                    return self._provenance(record)
                if not reapply:
                    _fail('restore_changed', 'Previously restored settings changed; explicit stopped-game reapply is required')
                record['restoration']['before_reapply_sha256'] = current_hash
            raw = base64.b64decode(record['original']['bytes_base64'], validate=True)
            record.update(state='restoring', restore_required=True)
            self._write(record)
            try:
                _atomic(self.config_path, raw, lambda: self._observe(running=False))
                current = _read(self.config_path, MAX_CONFIG_BYTES)
                if current != raw or _sha(current) != record['original']['sha256']:
                    _fail('restore_readback_failed', 'Original settings bytes were not restored exactly')
                record.update(state='restored', restore_required=False, restored_at=time.time())
                if preserved_runtime is not None:
                    preserved_runtime['before_reapply_sha256'] = record['restoration'].get('before_reapply_sha256')
                    record['restoration'] = preserved_runtime
                record['restoration'].update(file_verified=True, sha256=_sha(current),
                    runtime_verified=preserved_runtime is not None, byte_reapply_required=False)
                self._write(record)
            except Exception:
                record.update(state='restore_failed', restore_required=True)
                record['restoration'].update(file_verified=False, runtime_verified=False)
                try:
                    self._write(record)
                except Exception:
                    pass
                raise
            return self._provenance(record)

    def verify_restored_effective(self, evidence, *, validator=None):
        with self._locked():
            record = self._load()
            if record['state'] != 'restored' or record['restoration'].get('file_verified') is not True:
                _fail('invalid_lifecycle', 'Restore the settings file before verifying the restarted player process')
            expected = {key: record['original']['settings'][key] for key in REQUESTED_SETTINGS}
            proof = self._verify(record, evidence, expected, 'restored_at', validator)
            current = _read(self.config_path, MAX_CONFIG_BYTES)
            if _settings(_decode(current)) != record['original']['settings']:
                _fail('restore_changed', 'The restarted game changed the original settings semantics')
            needs_reapply = _sha(current) != record['original']['sha256']
            record['restoration'].update(runtime_verified=True, effective=proof,
                observed_file_sha256=_sha(current), byte_reapply_required=needs_reapply,
                file_verified=not needs_reapply)
            record['restore_required'] = needs_reapply
            self._write(record)
            return self._provenance(record)

    @staticmethod
    def _provenance(record):
        return deepcopy({'profile': 'kenshi-1.0.65-rekenshi-0.3.5-rng-off-custom-speeds-off',
                         'transaction_id': record['transaction_id'], 'state': record['state'],
                         'restore_required': record['restore_required'], 'metadata': record['metadata'],
                         'before': {'settings': record['original']['settings'], 'sha256': record['original']['sha256']},
                         'requested': record['requested'], 'prepared_sha256': record.get('prepared_sha256'),
                         'verification_failure': record.get('verification_failure'),
                         'effective': record['effective'], 'restoration': record['restoration'],
                         'known_deviations': record['known_deviations']})

    def provenance(self):
        with self._locked():
            return self._provenance(self._load())
