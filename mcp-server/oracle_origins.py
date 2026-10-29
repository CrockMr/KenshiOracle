"""Bounded, read-only saved HAND manifest from the published FCS save layout.

This is our own narrow reader of the public format, not a game-file importer.
Only ``quick.save`` and its explicitly indexed platoon files are read. No names,
definitions, positions or partial HANDs are used to associate identities. The
manifest describes records in this source snapshot; it does not resolve aliases.

Primary format/API references, independently checked for this implementation:
https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Fcs/FcsReader.cs
https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveFile.cs
https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveGame.cs
https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/Hand.cs
https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/save.md

All save strings are decoded losslessly. ``byteSize`` is bookkeeping in these
files, not a record boundary; every typed field and trailer is parsed to EOF.
Only type 15 is supported. In particular an editor-authored type 17 platoon is
explicitly unsupported instead of being mistaken for a type 15 save.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
from typing import Any


MANIFEST_VERSION = '0.1'
_FINGERPRINT_SCOPE = 'quick.save-and-indexed-platoon-files'
_HANDLE_KEYS = tuple('handle' + part for part in ('TYPE', 'C', 'CS', 'I', 'S'))
_RESERVED_NAME = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


class SavedOriginError(ValueError):
    """A source is unsafe, corrupt, ambiguous, changed, or unsupported."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class OriginReadLimits:
    max_files: int = 4096
    max_file_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 256 * 1024 * 1024
    max_records: int = 100_000
    max_count: int = 100_000
    max_string_bytes: int = 1024 * 1024
    max_items_per_file: int = 1_000_000
    max_origins: int = 100_000

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')


def _fail(code: str, message: str) -> None:
    raise SavedOriginError(code, message)


def _component(value: str, label: str, maximum: int = 255) -> None:
    if (type(value) is not str or not value or len(value) > maximum
            or value in ('.', '..') or value != value.strip()
            or value.endswith('.') or _RESERVED_NAME.match(value)
            or any(ord(c) < 32 or ord(c) == 127 or c in '<>:"/\\|?*'
                   or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        _fail('unsafe_path', f'Unsafe {label}')


def _content_path(value: str) -> str | None:
    # Exactly this sentinel denotes a platoon with no individual state file.
    if value == 'platoon/':
        return None
    parts = value.split('/')
    if len(parts) != 2 or parts[0] != 'platoon':
        _fail('unsafe_path', 'Content file must be platoon/<name>.platoon')
    _component(parts[1], 'platoon file name')
    if not parts[1].endswith('.platoon'):
        _fail('unsupported', 'Only .platoon content files are supported')
    return value


def _safe_path(root: Path, relative: str, *, directory: bool = False) -> Path:
    path = root
    try:
        # Reject both symlinks and Windows junctions/reparse points. Do not let a
        # file named inside an accepted save send the reader outside that save.
        for part in ('', *relative.split('/')):
            if part:
                path /= part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                _fail('unsafe_path', 'Save source contains a link or reparse point')
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root.resolve(strict=True)):
            _fail('unsafe_path', 'Save source escapes its configured root')
        if directory and not path.is_dir():
            _fail('invalid_source', 'Save source is not a directory')
        if not directory and not stat.S_ISREG(info.st_mode):
            _fail('invalid_source', 'Save source is not a regular file')
        return path
    except OSError as exc:
        raise SavedOriginError('read_failed', f'Cannot access save source: {exc}') from exc


def _identity_text(value: str, label: str) -> None:
    if not value or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        _fail('unsupported', f'{label} must be a nonempty Unicode identifier')


class _Reader:
    def __init__(self, data: bytes, relative: str, limits: OriginReadLimits):
        self.data, self.relative, self.limits = data, relative, limits
        self.at = 0
        self.items = 0

    def error(self, message: str, code: str = 'invalid_format') -> None:
        _fail(code, f'{self.relative} at byte {self.at}: {message}')

    def take(self, size: int) -> bytes:
        if size > len(self.data) - self.at:
            self.error('Truncated field')
        value = self.data[self.at:self.at + size]
        self.at += size
        return value

    def number(self, fmt: str = 'i') -> Any:
        size = struct.calcsize('<' + fmt)
        if size > len(self.data) - self.at:
            self.error('Truncated numeric field')
        values = struct.unpack_from('<' + fmt, self.data, self.at)
        self.at += size
        return values[0] if len(values) == 1 else values

    def count(self, maximum: int | None = None) -> int:
        value = self.number()
        if value < 0:
            self.error('Negative count')
        if value > (maximum if maximum is not None else self.limits.max_count):
            self.error('Count exceeds configured limit', 'limit_exceeded')
        self.items += value
        if self.items > self.limits.max_items_per_file:
            self.error('Aggregate item count exceeds configured limit', 'limit_exceeded')
        return value

    def string(self) -> str:
        length = self.number()
        if length < 0:
            self.error('Negative string length')
        if length > self.limits.max_string_bytes:
            self.error('String exceeds configured limit', 'limit_exceeded')
        return self.take(length).decode('utf-8', 'surrogateescape')

    def parse(self, trailer_count: int) -> dict:
        file_type = self.number()
        if file_type != 15:
            self.error(f'FCS file type {file_type} is unsupported; expected 15', 'unsupported')
        self.number()  # next numeric record ID, not an identity component
        count = self.count(self.limits.max_records)
        records, ids = [], set()
        for index in range(count):
            offset = self.at
            self.number('I')  # byteSize is NOT a size by which to skip save records
            record_type = self.number()
            self.number()  # numeric record ID, not the scoped string ID
            self.string()  # human-readable record name never used for identity
            record_id = self.string()
            _identity_text(record_id, 'Record string ID')
            if record_id in ids:
                self.error('Duplicate record string ID', 'ambiguous')
            ids.add(record_id)
            self.number('I')  # flags
            integers, filenames = {}, {}
            for kind, fmt in (('bool', 'B'), ('float', 'f'), ('int', 'i'),
                              ('vec3', 'fff'), ('vec4', 'ffff'),
                              ('string', None), ('filename', None)):
                keys = set()
                for _ in range(self.count()):
                    key = self.string()
                    if key in keys:
                        self.error(f'Duplicate {kind} property', 'ambiguous')
                    keys.add(key)
                    value = self.string() if fmt is None else self.number(fmt)
                    if kind == 'bool' and value not in (0, 1):
                        self.error('Boolean value is neither 0 nor 1')
                    if kind == 'int' and key in _HANDLE_KEYS:
                        integers[key] = value
                    elif kind == 'filename' and key == 'content file':
                        filenames[key] = value
            categories = set()
            for _ in range(self.count()):
                category = self.string()
                if category in categories:
                    self.error('Duplicate reference category', 'ambiguous')
                categories.add(category)
                for _ in range(self.count()):
                    self.string()
                    self.number('iii')
            instances, instance_ids = [], set()
            for _ in range(self.count()):
                instance_id = self.string()
                self.string()  # definition target is shared and not an identity
                self.number('fff')
                self.number('ffff')
                states = [self.string() for _ in range(self.count())]
                if instance_id in instance_ids:
                    self.error('Duplicate instance ID in collection', 'ambiguous')
                instance_ids.add(instance_id)
                if len(set(states)) != len(states):
                    self.error('Duplicate state reference in instance', 'ambiguous')
                if record_type == 30:
                    _identity_text(instance_id, 'Collection instance ID')
                    instances.append({'id': instance_id, 'states': states})
            records.append(dict(type=record_type, record_id=record_id, index=index,
                                offset=offset, integers=integers,
                                filenames=filenames, instances=instances))
        slot_counts = []
        for _ in range(trailer_count):
            slots = self.count()
            self.take(slots * 4)
            slot_counts.append(slots)
        if self.at != len(self.data):
            self.error('Unexpected bytes after the documented slot lists')
        return dict(records=records, file_type=file_type, record_count=count,
                    slot_counts=slot_counts)


def _saved_hand(record: dict, expected_type: int) -> str:
    values = record['integers']
    if not all(key in values for key in _HANDLE_KEYS):
        _fail('unsupported', 'Identity record does not contain all five HAND components')
    # The FCS fields are int32; the native public HAND fields carry those same
    # 32 bits as uint32. Negative serialized serials must not become negative IDs.
    components = [values[key] & 0xFFFFFFFF for key in _HANDLE_KEYS]
    if components[0] != expected_type:
        _fail('unsupported', 'Saved HAND type does not match the identity record')
    return 'hand:' + ':'.join(map(str, components))


def _record_origin(record: dict, relative: str, saved_id: str) -> dict:
    return dict(saved_id=saved_id, file=relative, record_id=record['record_id'],
                record_index=record['index'], record_offset=record['offset'])


def _manifest_fingerprint(files: list[dict]) -> str:
    fingerprint_bytes = json.dumps(
        [(item['path'], item['size'], item['sha256'])
         for item in sorted(files, key=lambda item: item['path'])],
        ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return 'sha256:' + hashlib.sha256(fingerprint_bytes).hexdigest()


def _checked_manifest_files(manifest: dict, limits: OriginReadLimits) -> list[dict]:
    """Validate all read-controlling metadata before opening any source file."""
    if type(manifest) is not dict:
        _fail('invalid_format', 'Saved origin manifest must be an object')
    if manifest.get('version') != MANIFEST_VERSION:
        _fail('unsupported', 'Unsupported saved origin manifest version')
    if manifest.get('fingerprint_scope') != _FINGERPRINT_SCOPE:
        _fail('unsupported', 'Unsupported saved origin fingerprint scope')
    _component(manifest.get('save_name'), 'manifest save name', 128)
    files = manifest.get('files')
    if type(files) is not list or not files:
        _fail('invalid_format', 'Saved origin manifest must contain source files')
    if len(files) > limits.max_files:
        _fail('limit_exceeded', 'Saved origin manifest exceeds configured file count')
    for collection in ('characters', 'squads'):
        if type(manifest.get(collection)) is not list:
            _fail('invalid_format', f'Saved origin manifest {collection} must be a list')
    if len(manifest['characters']) + len(manifest['squads']) > limits.max_origins:
        _fail('limit_exceeded', 'Saved origin manifest exceeds configured origin count')

    total_bytes, paths = 0, set()
    for evidence in files:
        if type(evidence) is not dict:
            _fail('invalid_format', 'Saved origin file evidence must be an object')
        relative = evidence.get('path')
        if type(relative) is not str:
            _fail('unsafe_path', 'Saved origin file path must be a string')
        if relative != 'quick.save' and _content_path(relative) is None:
            _fail('unsafe_path', 'A source file cannot be the no-file sentinel')
        folded = relative.casefold()
        if folded in paths:
            _fail('ambiguous', 'Duplicate source path in saved origin manifest')
        paths.add(folded)
        size, record_count = evidence.get('size'), evidence.get('record_count')
        if type(size) is not int or size < (28 if relative == 'quick.save' else 12):
            _fail('invalid_format', 'Saved origin file size must be a valid FCS length')
        if size > limits.max_file_bytes:
            _fail('limit_exceeded', 'Saved origin manifest exceeds configured file byte limit')
        total_bytes += size
        if total_bytes > limits.max_total_bytes:
            _fail('limit_exceeded', 'Saved origin manifest exceeds configured total byte limit')
        if type(record_count) is not int or record_count < 0:
            _fail('invalid_format', 'Saved origin record count must be nonnegative')
        if record_count > limits.max_records:
            _fail('limit_exceeded', 'Saved origin record count exceeds configured limit')
        if type(evidence.get('file_type')) is not int or evidence['file_type'] != 15:
            _fail('unsupported', 'Saved origin files must have FCS type 15')
        digest = evidence.get('sha256')
        if type(digest) is not str or not _SHA256.fullmatch(digest):
            _fail('invalid_format', 'Saved origin file hash must be a lowercase SHA-256')
        slots = evidence.get('slot_counts')
        if type(slots) is not list or len(slots) != (4 if relative == 'quick.save' else 0):
            _fail('invalid_format', 'Saved origin slot counts do not match the source type')
        for count in slots:
            if type(count) is not int or count < 0:
                _fail('invalid_format', 'Saved origin slot count must be nonnegative')
            if count > limits.max_count:
                _fail('limit_exceeded', 'Saved origin slot count exceeds configured limit')
    if 'quick.save' not in paths:
        _fail('invalid_format', 'Saved origin manifest has no quick.save')
    if manifest.get('fingerprint') != _manifest_fingerprint(files):
        _fail('invalid_format', 'Saved origin fingerprint does not match its file evidence')
    return files


def verify_saved_origins(save_root: Path, manifest: dict, *,
                         limits: OriginReadLimits | None = None) -> None:
    """Check source files still match a previously parsed manifest, read-only.

    This validates the manifest's read-controlling metadata, then reads only
    those exact files with path/reparse protections and byte limits. It does
    not decode records or recompute identities. Missing, truncated, replaced or
    changed content raises ``source_changed``; unsafe paths/reparse points keep
    ``unsafe_path``. Invalid manifests fail before any source file is opened.
    The input manifest is not modified; the return value is None.

    A successful check describes the bytes read during this pass. It cannot
    lock out external writes after the check; callers should verify immediately
    before committing their prepared engine identity context.
    """
    limits = limits or OriginReadLimits()
    files = _checked_manifest_files(manifest, limits)
    try:
        folder = _safe_path(Path(save_root).absolute(), manifest['save_name'], directory=True)
        for evidence in files:
            path = _safe_path(folder, evidence['path'])
            with path.open('rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    _fail('source_changed', 'Opened save source is no longer a regular file')
                data = stream.read(evidence['size'] + 1)
            if (len(data) != evidence['size']
                    or hashlib.sha256(data).hexdigest() != evidence['sha256']):
                _fail('source_changed', 'Save source no longer matches its origin manifest')
            if struct.unpack_from('<i', data, 0)[0] != 15:
                _fail('invalid_format', 'Saved origin file evidence has an inconsistent FCS type')
            if struct.unpack_from('<i', data, 8)[0] != evidence['record_count']:
                _fail('invalid_format', 'Saved origin file evidence has an inconsistent record count')
    except SavedOriginError as exc:
        if exc.code in ('read_failed', 'invalid_source'):
            raise SavedOriginError('source_changed', 'Save source is no longer available as parsed') from exc
        raise
    except OSError as exc:
        raise SavedOriginError('source_changed', 'Cannot read the previously parsed save source') from exc


def read_saved_origins(save_root: Path, save_name: str, *,
                       limits: OriginReadLimits | None = None) -> dict:
    """Return a JSON-ready manifest without writing files or contacting the game.

    ``save_root`` is the explicitly selected saves directory; ``save_name`` is
    one safe Windows directory component. Errors expose a ``SavedOriginError``
    ``code`` (unsafe_path, read_failed, invalid_source, invalid_format,
    unsupported, ambiguous, limit_exceeded, source_changed). Returned origins
    are sorted by their complete saved HAND. ``fingerprint`` covers only the
    declared ``fingerprint_scope``, not the uninspected zones/portraits.
    """
    limits = limits or OriginReadLimits()
    _component(save_name, 'save name', 128)
    root = Path(save_root).absolute()
    folder = _safe_path(root, save_name, directory=True)
    files, source_paths, characters, squads = [], [], [], []
    total_bytes = 0

    def read(relative: str, trailer_count: int) -> dict:
        nonlocal total_bytes
        if len(files) >= limits.max_files:
            _fail('limit_exceeded', 'Save source exceeds configured file count')
        path = _safe_path(folder, relative)
        ceiling = min(limits.max_file_bytes, limits.max_total_bytes - total_bytes)
        try:
            with path.open('rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    _fail('invalid_source', 'Opened save source is not a regular file')
                data = stream.read(ceiling + 1)
        except OSError as exc:
            raise SavedOriginError('read_failed', f'Cannot read save source: {exc}') from exc
        if len(data) > ceiling:
            _fail('limit_exceeded', 'Save source exceeds configured byte limit')
        total_bytes += len(data)
        parsed = _Reader(data, relative, limits).parse(trailer_count)
        files.append(dict(path=relative, size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                          file_type=parsed['file_type'], record_count=parsed['record_count'],
                          slot_counts=parsed['slot_counts']))
        source_paths.append(relative)
        return parsed

    quick = read('quick.save', 4)
    saved_ids, content_files = set(), set()
    for platoon in quick['records']:
        if platoon['type'] != 34:
            continue
        saved_id = _saved_hand(platoon, 34)
        if saved_id in saved_ids:
            _fail('ambiguous', 'Duplicate complete saved HAND')
        saved_ids.add(saved_id)
        if 'content file' not in platoon['filenames']:
            _fail('unsupported', 'PLATOON record has no content file property')
        relative = _content_path(platoon['filenames']['content file'])
        squad = _record_origin(platoon, 'quick.save', saved_id)
        squad['content_file'] = relative
        squads.append(squad)
        if len(characters) + len(squads) > limits.max_origins:
            _fail('limit_exceeded', 'Save source exceeds configured origin count')
        if relative is None:
            continue
        folded = relative.casefold()
        if folded in content_files:
            _fail('ambiguous', 'Multiple PLATOON records index the same content file')
        content_files.add(folded)
        parsed = read(relative, 0)
        records = {record['record_id']: record for record in parsed['records']}
        links: dict[str, list] = {}
        instance_ids = set()
        for collection in parsed['records']:
            for instance in collection['instances']:
                if instance['id'] in instance_ids:
                    _fail('ambiguous', 'Duplicate instance ID across collections in a file')
                instance_ids.add(instance['id'])
                character_states = []
                for state in instance['states']:
                    if state not in records:
                        _fail('unsupported', 'Instance state does not name a record in its file')
                    if records[state]['type'] == 36:
                        character_states.append(state)
                        links.setdefault(state, []).append((collection, instance))
                if len(character_states) > 1:
                    _fail('ambiguous', 'One collection instance links multiple character states')
        for record in parsed['records']:
            if record['type'] != 36:
                continue
            matches = links.get(record['record_id'], [])
            if len(matches) != 1:
                _fail('ambiguous', 'Character state must have exactly one collection instance')
            character_id = _saved_hand(record, 1)
            if character_id in saved_ids:
                _fail('ambiguous', 'Duplicate complete saved HAND')
            saved_ids.add(character_id)
            collection, instance = matches[0]
            origin = _record_origin(record, relative, character_id)
            origin.update(collection_record_id=collection['record_id'],
                          instance_id=instance['id'], saved_platoon_id=saved_id)
            characters.append(origin)
            if len(characters) + len(squads) > limits.max_origins:
                _fail('limit_exceeded', 'Save source exceeds configured origin count')

    # Re-read only the exact indexed files under the same limits. A successful
    # manifest must describe one unchanged source pass, not a mixed save update.
    for relative, evidence in zip(source_paths, files):
        path = _safe_path(folder, relative)
        try:
            with path.open('rb') as stream:
                data = stream.read(evidence['size'] + 1)
        except OSError as exc:
            raise SavedOriginError('read_failed', f'Cannot verify save source: {exc}') from exc
        if len(data) != evidence['size'] or hashlib.sha256(data).hexdigest() != evidence['sha256']:
            _fail('source_changed', 'Save source changed while its origins were read')
    files.sort(key=lambda item: item['path'])
    return dict(version=MANIFEST_VERSION, save_name=save_name,
                fingerprint=_manifest_fingerprint(files),
                fingerprint_scope=_FINGERPRINT_SCOPE, files=files,
                characters=sorted(characters, key=lambda item: item['saved_id']),
                squads=sorted(squads, key=lambda item: item['saved_id']))
