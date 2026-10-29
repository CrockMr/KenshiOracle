"""Own minidump/counter fixtures; optional audit of ignored local campaign.

No shipped bytes are embedded, no process access or new capture is needed.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct

import pytest
import analyze_worker_object as audit


def synthetic_dump(tmp_path):
    raw = bytearray(1024)
    struct.pack_into('<4sIIIIIQ', raw, 0, b'MDMP', 42899, 4, 32, 0, 0, 0x1400)
    for i, row in enumerate([(3, 52, 80), (17, 76, 132), (5, 36, 208), (15, 24, 244)]):
        struct.pack_into('<III', raw, 32+12*i, *row)
    struct.pack_into('<I', raw, 80, 1)
    struct.pack_into('<I', raw, 84, 7)
    struct.pack_into('<II', raw, 124, 256, 320)
    struct.pack_into('<III', raw, 132, 12, 64, 1)
    struct.pack_into('<IIIIQ', raw, 144, 7, 0, 0, 259, 12345)
    struct.pack_into('<I', raw, 208, 2)
    struct.pack_into('<QII', raw, 212, 0x1000, 24, 600)
    struct.pack_into('<QII', raw, 228, 0x2000, 24, 624)
    struct.pack_into('<6I', raw, 244, 24, 3, 42, 10, 0, 0)
    struct.pack_into('<I', raw, 320+48, 0x100003)
    struct.pack_into('<QQ', raw, 320+152, 0x3000, 0x4000)
    struct.pack_into('<Q', raw, 320+248, 0x5000)
    path = tmp_path/'own.dmp'
    path.write_bytes(raw)
    return path, raw, str((11644473600+10)*10_000_000)


def test_dump_pid_creation_contexts_are_native_evidence_not_path_claims(tmp_path):
    path, _, creation = synthetic_dump(tmp_path)
    report = audit.inspect_dump(path, 42, creation)
    assert report['contexts'][7] == dict(pc=0x5000, sp=0x3000, rbp=0x4000)
    assert set(report['lifetimes']) == {(7, '12345')}
    assert report['process']['pid'] == 42
    with pytest.raises(ValueError, match='PID'):
        audit.inspect_dump(path, 999, creation)
    with pytest.raises(ValueError, match='creation second'):
        audit.inspect_dump(path, 42, str(int(creation)+10_000_000))


@pytest.mark.parametrize('damage', ['partial_virtual_overlap', 'duplicate_virtual_range',
                                   'stream_overlap', 'memory_outside_file', 'missing_control_context',
                                   'missing_process_creation', 'duplicate_stream'])
def test_ambiguous_or_incomplete_dump_is_rejected(tmp_path, damage):
    path, raw, creation = synthetic_dump(tmp_path)
    if damage == 'partial_virtual_overlap':
        struct.pack_into('<Q', raw, 228, 0x1010)
    elif damage == 'duplicate_virtual_range':
        struct.pack_into('<Q', raw, 228, 0x1000)
    elif damage == 'stream_overlap':
        struct.pack_into('<I', raw, 32+3*12+8, 132)
    elif damage == 'memory_outside_file':
        struct.pack_into('<I', raw, 212+12, 1010)
    elif damage == 'missing_control_context':
        struct.pack_into('<I', raw, 320+48, 0x100001)
    elif damage == 'missing_process_creation':
        struct.pack_into('<I', raw, 244+4, 1)
    else:
        struct.pack_into('<I', raw, 32+3*12, 5)
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        audit.inspect_dump(path, 42, creation)


def frame(tmp_path):
    exe = tmp_path/'own.exe'
    return exe, dict(pc='0x125fe08', sp='0x7000', module_base='0x1000000', image=str(exe),
                     module_hresult='0x0', context_pc='0x125fe08', context_sp='0x7000',
                     context_flags='0x100003', nonvolatile=dict(rbp='0x8000'))


def test_exact_threadproc_frame_recovers_receiver_but_not_frame_offset(tmp_path):
    exe, f = frame(tmp_path)
    assert audit.validate_frame(f, 0x1000000, exe.resolve(), 0x8000)['rbp'] == '0x8000'
    f['frame_offset'] = '0xDEADBEEF'  # No semantic receiver authority.
    assert audit.validate_frame(f, 0x1000000, exe.resolve(), 0x8000)['rbp'] == '0x8000'


@pytest.mark.parametrize('damage', ['wrong_pc', 'context_pc', 'context_sp', 'stale_rbp', 'base', 'image'])
def test_context_pairing_and_receiver_contradictions_fail(tmp_path, damage):
    exe, f = frame(tmp_path)
    if damage == 'wrong_pc':
        f['pc'] = f['context_pc'] = '0x125fe09'
    elif damage in ('context_pc', 'context_sp'):
        f[damage] = '0x12340000'
    elif damage == 'stale_rbp':
        f['nonvolatile']['rbp'] = '0x9000'
    elif damage == 'base':
        f['module_base'] = '0x1000001'
    else:
        f['image'] = str(tmp_path/'other.exe')
    with pytest.raises(ValueError):
        audit.validate_frame(f, 0x1000000, exe.resolve(), 0x8000)


def counters():
    a = dict(tid=7, created_filetime='12345', user_100ns=10_000_000, kernel_100ns=20_000_000,
             observed_monotonic_seconds=10.0)
    b = dict(a, user_100ns=30_000_000, kernel_100ns=30_000_000, observed_monotonic_seconds=14.0)
    delta = dict(tid=7, created_filetime='12345', user_seconds=2.0, kernel_seconds=1.0,
                 cpu_seconds=3.0, elapsed_seconds=4.0, logical_cpu_equivalents=0.75)
    resources = dict(before=dict(thread_snapshot=dict(threads=[a])),
                     after=dict(thread_snapshot=dict(threads=[b])), thread_cpu=dict(threads=[delta]))
    return resources, [copy.deepcopy(delta)]


def test_cpu_is_recomputed_for_thread_lifetime_and_explicitly_not_function_cpu():
    resources, selected = counters()
    value = audit.cpu_join(resources, selected, [(7, '12345')])[(7, '12345')]
    assert value['cpu_seconds'] == 3 and value['logical_cpu_equivalents'] == 0.75
    assert 'not exclusive' in value['scope']
    assert 'exclusive_seconds' not in value


@pytest.mark.parametrize('damage', ['reuse', 'duplicate', 'negative_ticks', 'negative_time', 'declared_delta'])
def test_cpu_tid_reuse_and_counter_contradictions_never_join(tmp_path, damage):
    resources, selected = counters()
    after = resources['after']['thread_snapshot']['threads']
    if damage == 'reuse':
        after[0]['created_filetime'] = '99999'
    elif damage == 'duplicate':
        after.append(dict(after[0], created_filetime='99999'))
    elif damage == 'negative_ticks':
        after[0]['user_100ns'] = 0
    elif damage == 'negative_time':
        after[0]['observed_monotonic_seconds'] = 9
    else:
        selected[0]['cpu_seconds'] = 300
    with pytest.raises(ValueError):
        audit.cpu_join(resources, selected, [(7, '12345')])


@pytest.mark.parametrize('raw', [b'{"pid":1,"pid":2}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_json_provenance_does_not_silently_normalize_duplicate_or_nonfinite_values(raw):
    with pytest.raises(ValueError):
        audit._json(raw)


def test_source_pin_is_checked_before_following_any_source_paths(tmp_path):
    path = tmp_path/'controller.json'
    path.write_text('{"do_not_follow":"absent.dmp"}')
    with pytest.raises(ValueError, match='Controller SHA256'):
        audit.analyze(path, '0'*64)
    with pytest.raises(ValueError, match='Invalid expected'):
        audit.analyze(path, 'SHA not hex')


def scene_recording():
    names = ('cpu_scene_before', 'cpu_scene_after', 'roles_after', 'scene_after_metadata')
    scenes = [dict(frame=10+i*10, paused=i >= 2, frame_speed_multiplier=0 if i >= 2 else 1,
                   observed_qpc_ms=1000+i*4000, game_total_hours=100 if i == 0 else 101)
              for i in range(4)]
    data = dict(zip(names, scenes))
    data['simulation_progress'] = dict(wall_seconds=4, game_hours=1, game_hours_per_wall_second=0.25,
                                       first_frame=10, last_frame=20)
    return data


def test_scene_progress_and_pause_are_validated_in_scene_clock_domain():
    data = scene_recording()
    report = audit.scene_intervals(data)
    assert report['simulation_progress']['game_hours'] == 1
    assert report['observation_order'][2]['paused'] is True
    assert 'not an equivalence' in report['scope']


@pytest.mark.parametrize('damage', ['x1_paused', 'x1_speed', 'no_simulation', 'capture_unpaused',
                                   'capture_speed', 'paused_clock', 'frame_order', 'qpc_order',
                                   'declared_progress'])
def test_contradictory_scene_states_or_order_cannot_support_temporal_claim(damage):
    data = scene_recording()
    if damage == 'x1_paused':
        data['cpu_scene_after']['paused'] = True
    elif damage == 'x1_speed':
        data['cpu_scene_before']['frame_speed_multiplier'] = 2
    elif damage == 'no_simulation':
        data['cpu_scene_after']['game_total_hours'] = 100
    elif damage == 'capture_unpaused':
        data['roles_after']['paused'] = False
    elif damage == 'capture_speed':
        data['scene_after_metadata']['frame_speed_multiplier'] = 1
    elif damage == 'paused_clock':
        data['scene_after_metadata']['game_total_hours'] += 0.01
    elif damage == 'frame_order':
        data['roles_after']['frame'] = 19
    elif damage == 'qpc_order':
        data['scene_after_metadata']['observed_qpc_ms'] = 4999
    else:
        data['simulation_progress']['game_hours'] = 2
    with pytest.raises(ValueError):
        audit.scene_intervals(data)


LOCAL = Path(__file__).resolve().parents[1]/'runtime/worker-objects/20261028T111210121084Z/controller.json'


@pytest.fixture
def campaign():
    if not LOCAL.exists():
        pytest.skip('Ignored local capture is optional; synthetic checks remain portable')
    return json.loads(LOCAL.read_text())


def test_local_recording_reproduces_join_without_instantiating_runtime_provider(campaign, monkeypatch):
    import thread_metadata
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline analysis must not instantiate a runtime provider')
    monkeypatch.setattr(thread_metadata.WindowsThreadMetadata, '__init__', forbidden)
    digest = hashlib.sha256(LOCAL.read_bytes()).hexdigest()
    result = audit.analyze(LOCAL, digest)
    birds = [o for o in result['objects'] if o['bird_manager_vptr_matched']]
    assert result['verified'] and len(birds) == 1
    assert birds[0]['tid'] == 18796 and birds[0]['created_filetime'] == '134376583564582384'
    assert birds[0]['cpu']['cpu_seconds'] == 2.828125
    assert all(d['sdk_table']['slots_checked'] == 7622 for d in result['dumps'].values())
    assert any('retained DbgEng' in limit for limit in result['limits'])
    assert any('only in confirmation' in limit for limit in result['limits'])


@pytest.mark.parametrize('damage', ['dump_size', 'dump_hash', 'source_hash', 'capture_pid',
                                   'capture_creation', 'sdk_pairing', 'unwind_context',
                                   'receiver_frame_copy', 'receiver_tid', 'header', 'type', 'rtti',
                                   'proof_hash', 'declared_birds', 'process_subsecond',
                                   'x1_paused', 'capture_clock', 'capture_frame_order'])
def test_local_evidence_contradictions_are_rejected_without_recapture(campaign, tmp_path, damage):
    data = campaign
    if damage in ('dump_size', 'dump_hash'):
        data['confirmation']['capture']['bytes' if damage == 'dump_size' else 'sha256'] = 1 if damage == 'dump_size' else '0'*64
    elif damage == 'source_hash':
        data['map_sources']['executable']['sha256'] = '0'*64
    elif damage == 'capture_pid':
        data['discovery']['capture']['pid'] += 1
    elif damage == 'capture_creation':
        data['confirmation']['capture']['process_created_filetime'] = '1'
    elif damage == 'sdk_pairing':
        data['confirmation']['sdk_binding_from_dump']['verified'] = False
    elif damage == 'unwind_context':
        data['confirmation']['unwind']['result']['threads'][0]['frames'][0]['context_sp'] = '0x1000'
    elif damage == 'receiver_frame_copy':
        data['objects'][0]['confirmation_frame']['nonvolatile']['rbp'] = '0x1000'
    elif damage == 'receiver_tid':
        data['objects'][0]['created_filetime'] = '1'
    elif damage == 'header':
        data['objects'][0]['base_from_same_dump']['thread_id'] = 999
    elif damage == 'type':
        data['objects'][0]['bird_manager_vptr_matched'] = False
    elif damage == 'rtti':
        data['static_metadata']['col_rva'] = data['static_metadata']['vtable_rva']
    elif damage == 'proof_hash':
        data['static_metadata']['receiver_proof_sha256'] = '0'*64
    elif damage == 'process_subsecond':
        data['created_at'] += 0.5
        # Keep the redundant CPU creation fields coherent: only exact FILETIME
        # conversion can expose this half-second contradiction.
        for phase in ('before', 'after'):
            data['process_resources'][phase]['created_at'] = data['created_at']
    elif damage == 'x1_paused':
        data['cpu_scene_before']['paused'] = True
    elif damage == 'capture_clock':
        data['scene_after_metadata']['game_total_hours'] += 0.01
    elif damage == 'capture_frame_order':
        data['roles_after']['frame'] = data['cpu_scene_after']['frame']-1
    else:
        data['bird_manager_objects'] = []
    changed = tmp_path/'controller.json'
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        audit.analyze(changed, hashlib.sha256(changed.read_bytes()).hexdigest())


@pytest.mark.parametrize('damage', ['sdk_pointer', 'header_tid', 'vftable', 'col', 'type_name'])
def test_changed_dump_bytes_fail_even_after_declared_hash_is_updated(campaign, tmp_path, damage):
    """Content correspondence, rather than a self-declared digest, establishes identity."""
    data = campaign
    original = Path(data['confirmation']['dump'])
    raw = bytearray(original.read_bytes())
    base = int(data['binding_before']['modules']['executable']['base'], 16)
    metadata = data['static_metadata']
    targets = {
        'sdk_pointer': int(data['binding_before']['pointer_table_address'], 16),
        'header_tid': int(data['objects'][0]['address'], 16)+16,
        'vftable': base+int(metadata['vtable_rva'], 16)+16,
        'col': base+int(metadata['col_rva'], 16)+12,
        'type_name': base+int(metadata['type_descriptor_rva'], 16)+16,
    }
    address = targets[damage]
    count, directory = struct.unpack_from('<II', raw, 8)
    locations = []
    for i in range(count):
        kind, _, at = struct.unpack_from('<III', raw, directory+12*i)
        if kind != 5:
            continue
        n, = struct.unpack_from('<I', raw, at)
        for j in range(n):
            start, size, offset = struct.unpack_from('<QII', raw, at+4+16*j)
            if start <= address < start+size:
                locations.append(offset+address-start)
    assert len(locations) == 1
    raw[locations[0]] ^= 1
    changed_dump = tmp_path/'changed.dmp'
    changed_dump.write_bytes(raw)
    data['confirmation']['dump'] = data['confirmation']['capture']['dump'] = str(changed_dump)
    data['confirmation']['capture']['sha256'] = hashlib.sha256(raw).hexdigest()
    changed = tmp_path/'controller.json'
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        audit.analyze(changed)
