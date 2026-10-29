"""Entirely synthetic public-format FCS fixtures; no game files or connections."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct

import pytest

from oracle_origins import (OriginReadLimits, SavedOriginError,
                            read_saved_origins, verify_saved_origins)


def integer(value):
    return struct.pack('<i', value)


def string(value):
    data = value if isinstance(value, bytes) else value.encode('utf-8')
    return integer(len(data)) + data


def handle(kind=1, container=7, serial=-1, slot=3, object_serial=-2147483648):
    return dict(zip(('handleTYPE', 'handleC', 'handleCS', 'handleI', 'handleS'),
                    (kind, container, serial, slot, object_serial)))


def record(kind, sid, **extra):
    return dict(type=kind, sid=sid, name='Synthetic record', **extra)


def encode_record(value):
    # A zero byteSize is deliberate: public saves do not use it as a byte count.
    out = struct.pack('<Iii', value.get('byte_size', 0), value['type'], 1)
    out += string(value['name']) + string(value['sid']) + struct.pack('<I', 0)
    for kind, fmt in (('bool', 'B'), ('float', 'f'), ('int', 'i'), ('vec3', 'fff'),
                      ('vec4', 'ffff'), ('string', None), ('filename', None)):
        fields = value.get(kind, {})
        fields = list(fields.items()) if isinstance(fields, dict) else fields
        out += integer(len(fields))
        for key, item in fields:
            out += string(key)
            if fmt is None:
                out += string(item)
            else:
                items = item if isinstance(item, tuple) else (item,)
                out += struct.pack('<' + fmt, *items)
    refs = value.get('refs', [])
    out += integer(len(refs))
    for category, entries in refs:
        out += string(category) + integer(len(entries))
        for target, a, b, c in entries:
            out += string(target) + struct.pack('<iii', a, b, c)
    instances = value.get('instances', [])
    out += integer(len(instances))
    for iid, states in instances:
        out += string(iid) + string('Shared synthetic definition')
        out += struct.pack('<fffffff', 1, 2, 3, 1, 0, 0, 0)
        out += integer(len(states)) + b''.join(map(string, states))
    return out


def file_bytes(records, *, slots=0, file_type=15):
    return (struct.pack('<iii', file_type, 123, len(records))
            + b''.join(map(encode_record, records)) + integer(0) * slots)


def write_source(tmp_path, *, quick=None, platoons=None, name='Synthetic save'):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    if quick is None:
        quick = [record(34, 'squad-state', int=handle(34),
                        filename={'content file': 'platoon/synthetic.platoon'})]
    if platoons is None:
        platoons = {'synthetic.platoon': [
            record(30, 'collection', instances=[('instance-one', ['character-state'])]),
            record(36, 'character-state', int=handle())]}
    (folder / 'quick.save').write_bytes(file_bytes(quick, slots=4))
    if platoons:
        (folder / 'platoon').mkdir(exist_ok=True)
    for filename, records in platoons.items():
        (folder / 'platoon' / filename).write_bytes(file_bytes(records))
    return folder


def assert_error(code, tmp_path, **kwargs):
    with pytest.raises(SavedOriginError) as caught:
        read_saved_origins(tmp_path, 'Synthetic save', **kwargs)
    assert caught.value.code == code
    return str(caught.value)


def test_manifest_has_scoped_provenance_unsigned_complete_handles_and_no_name_matching(tmp_path):
    folder = write_source(tmp_path)
    before = {p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    result = read_saved_origins(tmp_path, 'Synthetic save')
    assert result['version'] == '0.1'
    assert result['fingerprint_scope'] == 'quick.save-and-indexed-platoon-files'
    assert result['fingerprint'].startswith('sha256:')
    assert len(result['fingerprint']) == 71
    assert result['characters'] == [dict(
        saved_id='hand:1:7:4294967295:3:2147483648', file='platoon/synthetic.platoon',
        record_id='character-state', record_index=1,
        record_offset=12 + len(encode_record(record(
            30, 'collection', instances=[('instance-one', ['character-state'])]))),
        collection_record_id='collection', instance_id='instance-one',
        saved_platoon_id='hand:34:7:4294967295:3:2147483648')]
    assert result['squads'] == [dict(
        saved_id='hand:34:7:4294967295:3:2147483648', file='quick.save',
        record_id='squad-state', record_index=0, record_offset=12,
        content_file='platoon/synthetic.platoon')]
    assert [item['path'] for item in result['files']] == [
        'platoon/synthetic.platoon', 'quick.save']
    assert [item['slot_counts'] for item in result['files']] == [[], [0, 0, 0, 0]]
    for item in result['files']:
        assert item['sha256'] == hashlib.sha256(before[folder / item['path']]).hexdigest()
    assert read_saved_origins(tmp_path, 'Synthetic save') == result
    assert json.loads(json.dumps(result)) == result
    assert before == {p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    assert 'Synthetic record' not in json.dumps(result)


def test_no_file_sentinel_keeps_squad_without_inventing_characters(tmp_path):
    write_source(tmp_path, quick=[record(34, 'abstract', int=handle(34),
                 filename={'content file': 'platoon/'})], platoons={})
    result = read_saved_origins(tmp_path, 'Synthetic save')
    assert result['characters'] == []
    assert result['squads'][0]['content_file'] is None
    assert len(result['files']) == 1


def test_only_indexed_files_are_read(tmp_path):
    folder = write_source(tmp_path)
    baseline = read_saved_origins(tmp_path, 'Synthetic save')
    (folder / 'platoon' / 'orphan.platoon').write_bytes(b'not a valid FCS file')
    (folder / 'zone').mkdir()
    (folder / 'zone' / 'uninspected.zone').write_bytes(b'not a valid FCS file')
    (folder / 'portrait.png').write_bytes(b'synthetic irrelevant bytes')
    assert read_saved_origins(tmp_path, 'Synthetic save') == baseline


def test_same_I_S_and_shared_names_do_not_merge_distinct_full_handles(tmp_path):
    chars = [record(36, 'first', int=handle(container=1)),
             record(36, 'second', int=handle(container=2))]
    write_source(tmp_path, platoons={'synthetic.platoon': [record(
        30, 'collection', instances=[('one', ['first']), ('two', ['second'])]), *chars]})
    result = read_saved_origins(tmp_path, 'Synthetic save')
    assert len(result['characters']) == 2
    assert {row['record_id'] for row in result['characters']} == {'first', 'second'}


def test_all_public_property_reference_instance_fields_are_consumed(tmp_path):
    auxiliary = record(999, 'extension', bool={'b': 1}, float={'nan': float('nan')},
                       int={'extra': -3}, vec3={'v3': (1, 2, 3)},
                       vec4={'v4': (4, 5, 6, 7)}, string={'lossless': b'\xff'},
                       filename={'unused': 'anything'}, refs=[('r', [('target', 1, 2, 3)])],
                       instances=[('irrelevant', [])], byte_size=0xFFFFFFFF)
    write_source(tmp_path, platoons={'synthetic.platoon': [
        auxiliary, record(30, 'collection', instances=[('one', ['state'])]),
        record(36, 'state', int=handle())]})
    result = read_saved_origins(tmp_path, 'Synthetic save')
    assert len(result['characters']) == 1
    assert result['characters'][0]['record_index'] == 2


@pytest.mark.parametrize('value', ['', '.', '..', '../outside', 'foo/bar', 'foo\\bar',
                                  'C:outside', 'NUL', 'com1.sav', ' trailing', 'trailing.',
                                  'a\x00b', 'a\nb', 'a\udcffb', 'a' * 129, 3, None])
def test_unsafe_save_names_rejected_before_read(tmp_path, value):
    with pytest.raises(SavedOriginError) as caught:
        read_saved_origins(tmp_path, value)
    assert caught.value.code == 'unsafe_path'


@pytest.mark.parametrize('value', ['../outside.platoon', 'platoon/../x.platoon',
                                  'platoon/a/b.platoon', '/platoon/x.platoon',
                                  'platoon\\x.platoon', 'platoon/C:x.platoon',
                                  'platoon/NUL.platoon', 'platoon/x.platoon ',
                                  'platoon/x\x00.platoon', 'platoon/'])
def test_content_path_restrictions_and_exact_sentinel(tmp_path, value):
    write_source(tmp_path, quick=[record(34, 's', int=handle(34),
                 filename={'content file': value})], platoons={})
    if value == 'platoon/':
        assert read_saved_origins(tmp_path, 'Synthetic save')['characters'] == []
    else:
        assert_error('unsafe_path', tmp_path)


def test_unsupported_content_extension(tmp_path):
    write_source(tmp_path, quick=[record(34, 's', int=handle(34),
                 filename={'content file': 'platoon/x.zone'})], platoons={})
    assert_error('unsupported', tmp_path)


def test_missing_indexed_file_is_explicit_error(tmp_path):
    write_source(tmp_path, platoons={})
    assert_error('read_failed', tmp_path)


@pytest.mark.parametrize('target', ['quick.save', 'platoon/synthetic.platoon'])
@pytest.mark.parametrize('file_type', [0, 16, 17, -1])
def test_non15_files_fail_explicitly_without_fallback(tmp_path, target, file_type):
    folder = write_source(tmp_path)
    path = folder / target
    data = path.read_bytes()
    path.write_bytes(integer(file_type) + data[4:])
    assert 'unsupported' in assert_error('unsupported', tmp_path)


@pytest.mark.parametrize('kind', ['record', 'handle', 'instance', 'state', 'link', 'character-per-instance',
                                 'collection-instance', 'property', 'reference'])
def test_ambiguous_origins_fail_closed(tmp_path, kind):
    collection = record(30, 'collection', instances=[('one', ['state'])])
    character = record(36, 'state', int=handle())
    records = [collection, character]
    if kind == 'record':
        records.append(deepcopy(character))
    elif kind == 'handle':
        records.append({**deepcopy(character), 'sid': 'other'})
        collection['instances'].append(('two', ['other']))
    elif kind == 'instance':
        collection['instances'].append(('one', ['state']))
    elif kind == 'state':
        collection['instances'][0] = ('one', ['state', 'state'])
    elif kind == 'link':
        collection['instances'].append(('two', ['state']))
    elif kind == 'character-per-instance':
        records.append(record(36, 'other', int=handle(container=2)))
        collection['instances'][0] = ('one', ['state', 'other'])
    elif kind == 'collection-instance':
        records.append(record(30, 'collection-two', instances=[('one', [])]))
    elif kind == 'property':
        character['int'] = [('handleTYPE', 1), ('handleTYPE', 1)]
    elif kind == 'reference':
        character['refs'] = [('duplicate', []), ('duplicate', [])]
    write_source(tmp_path, platoons={'synthetic.platoon': records})
    assert_error('ambiguous', tmp_path)


@pytest.mark.parametrize('kind', ['no-link', 'missing-state', 'missing-component', 'wrong-type',
                                 'missing-content', 'duplicate-indexed-file', 'duplicate-squad'])
def test_unsupported_or_ambiguous_sources_have_no_partial_manifest(tmp_path, kind):
    quick = [record(34, 'squad', int=handle(34),
                    filename={'content file': 'platoon/synthetic.platoon'})]
    collection = record(30, 'collection', instances=[('one', ['state'])])
    character = record(36, 'state', int=handle())
    expected = 'unsupported'
    if kind == 'no-link':
        collection['instances'] = []
        expected = 'ambiguous'
    elif kind == 'missing-state':
        collection['instances'][0] = ('one', ['missing'])
    elif kind == 'missing-component':
        del character['int']['handleS']
    elif kind == 'wrong-type':
        character['int']['handleTYPE'] = 11
    elif kind == 'missing-content':
        quick[0]['filename'] = {}
    elif kind == 'duplicate-indexed-file':
        quick.append(record(34, 'other', int=handle(34, container=8),
                     filename={'content file': 'platoon/SYNTHETIC.platoon'}))
        expected = 'ambiguous'
    elif kind == 'duplicate-squad':
        quick.append({**deepcopy(quick[0]), 'sid': 'other'})
        expected = 'ambiguous'
    write_source(tmp_path, quick=quick, platoons={'synthetic.platoon': [collection, character]})
    assert_error(expected, tmp_path)


@pytest.mark.parametrize('target', ['quick.save', 'platoon/synthetic.platoon'])
def test_every_truncation_is_rejected(tmp_path, target):
    folder = write_source(tmp_path)
    path = folder / target
    original = path.read_bytes()
    for length in range(len(original)):
        path.write_bytes(original[:length])
        with pytest.raises(SavedOriginError):
            read_saved_origins(tmp_path, 'Synthetic save')


@pytest.mark.parametrize('target,suffix', [('quick.save', b'\x00'),
                                         ('quick.save', integer(0)),
                                         ('platoon/synthetic.platoon', integer(0))])
def test_unexpected_trailer_bytes_are_rejected(tmp_path, target, suffix):
    folder = write_source(tmp_path)
    path = folder / target
    path.write_bytes(path.read_bytes() + suffix)
    assert_error('invalid_format', tmp_path)


@pytest.mark.parametrize('offset,value,code', [(8, -1, 'invalid_format'),
                                            (8, 100_001, 'limit_exceeded'),
                                            (24, -1, 'invalid_format'),
                                            (24, 1024 * 1024 + 1, 'limit_exceeded')])
def test_negative_and_excessive_counts_are_rejected(tmp_path, offset, value, code):
    folder = write_source(tmp_path)
    path = folder / 'quick.save'
    data = bytearray(path.read_bytes())
    struct.pack_into('<i', data, offset, value)
    path.write_bytes(data)
    assert_error(code, tmp_path)


@pytest.mark.parametrize('field,value', [('max_files', 1), ('max_file_bytes', 16),
                                      ('max_total_bytes', 16), ('max_items_per_file', 1),
                                      ('max_string_bytes', 3), ('max_origins', 1)])
def test_configured_read_bounds(tmp_path, field, value):
    write_source(tmp_path)
    assert_error('limit_exceeded', tmp_path,
                 limits=replace(OriginReadLimits(), **{field: value}))


@pytest.mark.parametrize('value', [0, -1, True, 1.5, None])
def test_limits_require_positive_integers(value):
    with pytest.raises(ValueError):
        OriginReadLimits(max_files=value)


def test_source_change_during_read_is_rejected(tmp_path, monkeypatch):
    folder = write_source(tmp_path)
    quick = folder / 'quick.save'
    original = Path.open
    quick_reads = 0

    def changed_open(path, *args, **kwargs):
        nonlocal quick_reads
        if path == quick and args and args[0] == 'rb':
            quick_reads += 1
            if quick_reads == 2:
                with original(path, 'ab') as stream:
                    stream.write(b'changed')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', changed_open)
    assert_error('source_changed', tmp_path)


def test_symlinked_save_or_content_is_rejected(tmp_path):
    folder = write_source(tmp_path)
    outside = tmp_path / 'outside.platoon'
    outside.write_bytes(b'synthetic')
    target = folder / 'platoon' / 'synthetic.platoon'
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks requires Windows Developer Mode or privilege')
    assert_error('unsafe_path', tmp_path)


def test_windows_reparse_point_attribute_is_rejected(tmp_path, monkeypatch):
    write_source(tmp_path)
    original = Path.lstat

    def fake_reparse(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path.name == 'synthetic.platoon':
            class Reparse:
                st_mode = info.st_mode
                st_file_attributes = getattr(info, 'st_file_attributes', 0) | 0x400
            return Reparse()
        return info

    monkeypatch.setattr(Path, 'lstat', fake_reparse)
    assert_error('unsafe_path', tmp_path)


def assert_verify_error(code, tmp_path, manifest, **kwargs):
    with pytest.raises(SavedOriginError) as caught:
        verify_saved_origins(tmp_path, manifest, **kwargs)
    assert caught.value.code == code
    return str(caught.value)


def test_verify_is_read_only_bounded_and_does_not_redecode_records(tmp_path, monkeypatch):
    folder = write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    original_manifest = deepcopy(manifest)
    before = {p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    original_open = Path.open
    opened = []

    def readonly_open(path, *args, **kwargs):
        assert args == ('rb',)
        opened.append(path)
        return original_open(path, *args, **kwargs)

    def no_redecode(*args, **kwargs):
        raise AssertionError('Verification must not decode records')

    monkeypatch.setattr(Path, 'open', readonly_open)
    monkeypatch.setattr('oracle_origins._Reader.parse', no_redecode)
    assert verify_saved_origins(tmp_path, manifest) is None
    assert opened == [folder / item['path'] for item in manifest['files']]
    assert manifest == original_manifest
    monkeypatch.setattr(Path, 'open', original_open)
    assert before == {p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}


@pytest.mark.parametrize('target', ['quick.save', 'platoon/synthetic.platoon'])
def test_verify_detects_changed_content_even_with_same_size_and_mtime(tmp_path, target):
    folder = write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    path = folder / target
    before = path.stat()
    changed = bytearray(path.read_bytes())
    changed[4] ^= 1  # Different nextId; the complete FCS shape remains parseable.
    path.write_bytes(changed)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert_verify_error('source_changed', tmp_path, manifest)


@pytest.mark.parametrize('target', ['quick.save', 'platoon/synthetic.platoon'])
@pytest.mark.parametrize('change', ['missing', 'truncated', 'grown', 'directory'])
def test_verify_detects_unavailable_or_different_previously_parsed_files(tmp_path, target, change):
    folder = write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    path = folder / target
    data = path.read_bytes()
    if change in ('missing', 'directory'):
        path.unlink()
        if change == 'directory':
            path.mkdir()
    elif change == 'truncated':
        path.write_bytes(data[:-1])
    elif change == 'grown':
        path.write_bytes(data + b'changed')
    assert_verify_error('source_changed', tmp_path, manifest)


def test_verify_ignores_changes_outside_the_manifest_scope(tmp_path):
    folder = write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    (folder / 'platoon' / 'new-unindexed.platoon').write_bytes(b'synthetic ignored')
    (folder / 'new-file.anything').write_bytes(b'synthetic ignored')
    assert verify_saved_origins(tmp_path, manifest) is None


@pytest.mark.parametrize('change', ['missing-name', 'missing-root', 'root-is-save', 'different-save'])
def test_verify_does_not_fall_back_to_another_source_when_root_or_name_mismatch(tmp_path, change):
    write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    root = tmp_path
    if change == 'missing-name':
        manifest['save_name'] = 'Other safe name'
    elif change == 'missing-root':
        root = tmp_path / 'Missing root'
    elif change == 'root-is-save':
        root = tmp_path / 'Synthetic save'
    elif change == 'different-save':
        other = write_source(tmp_path, name='Different save')
        path = other / 'quick.save'
        data = bytearray(path.read_bytes())
        data[4] ^= 1
        path.write_bytes(data)
        manifest['save_name'] = 'Different save'
    assert_verify_error('source_changed', root, manifest)


@pytest.mark.parametrize('value', [None, [], 'manifest', 3])
def test_verify_rejects_nonobject_manifests(tmp_path, value):
    assert_verify_error('invalid_format', tmp_path, value)


@pytest.mark.parametrize('change,code', [
    ('version', 'unsupported'), ('scope', 'unsupported'), ('unsafe-name', 'unsafe_path'),
    ('files-not-list', 'invalid_format'), ('no-files', 'invalid_format'),
    ('file-not-object', 'invalid_format'), ('unsafe-file', 'unsafe_path'),
    ('file-not-string', 'unsafe_path'), ('no-file-sentinel', 'unsafe_path'),
    ('duplicate-file', 'ambiguous'), ('duplicate-file-case', 'ambiguous'),
    ('negative-size', 'invalid_format'), ('bool-size', 'invalid_format'),
    ('missing-size', 'invalid_format'), ('oversize', 'limit_exceeded'),
    ('negative-records', 'invalid_format'), ('bool-records', 'invalid_format'),
    ('excess-records', 'limit_exceeded'), ('file-type', 'unsupported'),
    ('bad-hash', 'invalid_format'), ('uppercase-hash', 'invalid_format'),
    ('wrong-trailer-count', 'invalid_format'), ('negative-slots', 'invalid_format'),
    ('bool-slots', 'invalid_format'), ('excess-slots', 'limit_exceeded'),
    ('no-quick', 'invalid_format'), ('fingerprint', 'invalid_format'),
    ('characters-not-list', 'invalid_format'), ('squads-not-list', 'invalid_format')])
def test_verify_validates_all_read_controlling_metadata_before_opening(tmp_path, monkeypatch, change, code):
    write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    quick = next(item for item in manifest['files'] if item['path'] == 'quick.save')
    platoon = next(item for item in manifest['files'] if item['path'].endswith('.platoon'))
    if change == 'version':
        manifest['version'] = 'future'
    elif change == 'scope':
        manifest['fingerprint_scope'] = 'all-files'
    elif change == 'unsafe-name':
        manifest['save_name'] = '../escape'
    elif change == 'files-not-list':
        manifest['files'] = {'quick.save': quick}
    elif change == 'no-files':
        manifest['files'] = []
    elif change == 'file-not-object':
        manifest['files'][0] = None
    elif change == 'unsafe-file':
        platoon['path'] = 'platoon/../../escape.platoon'
    elif change == 'file-not-string':
        platoon['path'] = None
    elif change == 'no-file-sentinel':
        platoon['path'] = 'platoon/'
    elif change == 'duplicate-file':
        manifest['files'].append(deepcopy(platoon))
    elif change == 'duplicate-file-case':
        manifest['files'].append({**platoon, 'path': 'platoon/SYNTHETIC.platoon'})
    elif change == 'negative-size':
        quick['size'] = -1
    elif change == 'bool-size':
        quick['size'] = True
    elif change == 'missing-size':
        del quick['size']
    elif change == 'oversize':
        quick['size'] = OriginReadLimits().max_file_bytes + 1
    elif change == 'negative-records':
        quick['record_count'] = -1
    elif change == 'bool-records':
        quick['record_count'] = False
    elif change == 'excess-records':
        quick['record_count'] = OriginReadLimits().max_records + 1
    elif change == 'file-type':
        quick['file_type'] = 17
    elif change == 'bad-hash':
        quick['sha256'] = 'not-a-hash'
    elif change == 'uppercase-hash':
        quick['sha256'] = quick['sha256'].upper()
    elif change == 'wrong-trailer-count':
        quick['slot_counts'] = []
    elif change == 'negative-slots':
        quick['slot_counts'][0] = -1
    elif change == 'bool-slots':
        quick['slot_counts'][0] = True
    elif change == 'excess-slots':
        quick['slot_counts'][0] = OriginReadLimits().max_count + 1
    elif change == 'no-quick':
        manifest['files'].remove(quick)
    elif change == 'fingerprint':
        manifest['fingerprint'] = 'sha256:' + '0' * 64
    elif change == 'characters-not-list':
        manifest['characters'] = None
    elif change == 'squads-not-list':
        manifest['squads'] = None

    def forbidden_open(*args, **kwargs):
        raise AssertionError('Invalid manifest must fail before opening files')

    monkeypatch.setattr(Path, 'open', forbidden_open)
    assert_verify_error(code, tmp_path, manifest)


@pytest.mark.parametrize('field,value', [('max_files', 1), ('max_file_bytes', 28),
                                      ('max_total_bytes', 28), ('max_records', 1),
                                      ('max_origins', 1)])
def test_verify_applies_current_configured_limits(tmp_path, field, value):
    write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    assert_verify_error('limit_exceeded', tmp_path, manifest,
                        limits=replace(OriginReadLimits(), **{field: value}))


def test_verify_rejects_inconsistent_record_count_without_redecoding(tmp_path):
    write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    # Record count is validation metadata rather than part of the content hash.
    manifest['files'][0]['record_count'] += 1
    assert_verify_error('invalid_format', tmp_path, manifest)


def test_verify_rejects_reparse_points_at_the_time_of_revalidation(tmp_path, monkeypatch):
    write_source(tmp_path)
    manifest = read_saved_origins(tmp_path, 'Synthetic save')
    original = Path.lstat

    def fake_reparse(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path.name == 'synthetic.platoon':
            class Reparse:
                st_mode = info.st_mode
                st_file_attributes = getattr(info, 'st_file_attributes', 0) | 0x400
            return Reparse()
        return info

    monkeypatch.setattr(Path, 'lstat', fake_reparse)
    assert_verify_error('unsafe_path', tmp_path, manifest)
