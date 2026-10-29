"""Offline audit of saved worker-object evidence; never opens a process/provider.

Frames and reconstructed registers are retained DbgEng observations, not a new
unwind. All object/RTTI bytes come from the confirmation minidump only.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from sdk_address_map import build, _PE, annotate
from loaded_sdk_map import compare_pointer_table
from thread_minidump import read_memory_range, read_thread_lifetimes
from thread_object_identity import parse_base_header


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) is int or isinstance(value, str), 'Invalid integer metadata')
    return int(value, 0) if isinstance(value, str) and value.startswith('0x') else int(value)


def pointer(value):
    n = number(value)
    require(0 < n < 2**47, 'Noncanonical user pointer')
    return n


def identity(row):
    tid, creation = number(row['tid']), str(row['created_filetime'])
    require(0 < tid < 2**32 and creation.isdecimal() and int(creation) > 0, 'Invalid thread lifetime')
    return tid, creation


def unique(rows):
    result = {}
    tids = set()
    for row in rows:
        key = identity(row)
        require(key not in result and key[0] not in tids, 'Duplicate/conflicting thread lifetime')
        result[key] = row
        tids.add(key[0])
    return result


def file_identity(path, limit=128*1024*1024):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    require(path.is_file() and 0 < before.st_size <= limit, 'Unsupported evidence size')
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            and len(raw) == before.st_size, 'Evidence changed during read')
    return raw, dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def compare_file(actual, declared):
    require(actual['bytes'] == declared['bytes'] and actual['sha256'] == declared['sha256'],
            'Evidence SHA256/size differs')


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def inspect_dump(path, pid, process_creation):
    """Validate stream/memory bounds, ambiguity, PID and native top contexts."""
    raw, provenance = file_identity(path)
    require(raw[:4] == b'MDMP' and len(raw) >= 32, 'Not a minidump')
    count, directory = struct.unpack_from('<II', raw, 8)
    require(0 < count <= 128 and directory >= 32 and directory+12*count <= len(raw), 'Invalid dump directory')
    streams, spans = {}, []
    for i in range(count):
        kind, size, offset = struct.unpack_from('<III', raw, directory+12*i)
        if kind == 0:
            require(size == offset == 0, 'Malformed unused stream')
            continue
        require(kind not in streams and size > 0 and offset+size <= len(raw), 'Invalid duplicate/bounded stream')
        require(offset >= 32 and not (offset < directory+12*count and directory < offset+size), 'Stream overlaps directory')
        require(all(not (offset < end and start < offset+size) for start, end in spans), 'Overlapping dump streams')
        spans.append((offset, offset+size))
        streams[kind] = (offset, size)
    require(15 in streams and 5 in streams and 3 in streams, 'Missing process/memory/context stream')
    at, size = streams[15]
    require(size >= 24, 'Short process metadata')
    declared_size, flags, native_pid, create_seconds = struct.unpack_from('<4I', raw, at)
    require(24 <= declared_size <= size and flags & 3 == 3, 'Missing native PID/creation metadata')
    require(native_pid == pid, 'Dump PID differs')
    expected_seconds = int(process_creation)//10_000_000-11644473600
    require(create_seconds == expected_seconds, 'Dump creation second differs')
    at, size = streams[5]
    require(size >= 4, 'Short memory list')
    n, = struct.unpack_from('<I', raw, at)
    require(n <= 65536 and 4+16*n <= size, 'Invalid memory descriptor count')
    memory = []
    for i in range(n):
        address, amount, data = struct.unpack_from('<QII', raw, at+4+16*i)
        require(amount > 0 and 0 < address < address+amount <= 2**47 and data+amount <= len(raw), 'Invalid memory descriptor')
        memory.append((address, address+amount))
    ordered = sorted(memory)
    require(all(b[0] >= a[1] for a, b in zip(ordered, ordered[1:])), 'Overlapping captured memory')
    lifetimes = unique(read_thread_lifetimes(path))
    at, size = streams[3]
    n, = struct.unpack_from('<I', raw, at)
    contexts = {}
    for i in range(n):
        row = at+4+48*i
        tid, = struct.unpack_from('<I', raw, row)
        context_size, context_rva = struct.unpack_from('<II', raw, row+40)
        require(context_size >= 256 and context_rva+context_size <= len(raw), 'Short AMD64 context')
        flags, = struct.unpack_from('<I', raw, context_rva+48)
        require(flags & 0x100003 == 0x100003, 'Missing AMD64 control/integer context')
        sp, rbp = struct.unpack_from('<QQ', raw, context_rva+152)
        pc, = struct.unpack_from('<Q', raw, context_rva+248)
        contexts[tid] = dict(pc=pc, sp=sp, rbp=rbp)
    return dict(provenance=provenance, lifetimes=lifetimes, contexts=contexts,
                process=dict(pid=native_pid, created_unix_seconds=create_seconds,
                             precision='seconds; exact process FILETIME is separately recorded controller/binding evidence'))


def validate_frame(frame, base, executable, address):
    pc, sp = pointer(frame['pc']), pointer(frame['sp'])
    require(number(frame['module_base']) == base and Path(frame['image']).resolve() == executable,
            'Frame image/base differs')
    require(frame['module_hresult'] == '0x0' and pc-base in (0x25fd3a, 0x25fe08), 'Frame is not an approved threadProc interior')
    require(pointer(frame['context_pc']) == pc and pointer(frame['context_sp']) == sp, 'Frame/context PC/SP differ')
    require(number(frame['context_flags']) & 0x100003 == 0x100003, 'Missing reconstructed integer context')
    require(pointer(frame['nonvolatile']['rbp']) == address and address % 8 == 0, 'Reconstructed receiver differs')
    require(sp % 8 == 0, 'Misaligned reconstructed stack')
    return dict(pc=hex(pc), sp=hex(sp), rbp=hex(address), threadproc_rva=hex(pc-base))


def cpu_join(resources, selected, wanted):
    """Recompute thread-entire deltas by TID AND native creation, never symbols."""
    snapshots = [unique(resources[phase]['thread_snapshot']['threads']) for phase in ('before', 'after')]
    declared, reported = unique(selected), unique(resources['thread_cpu']['threads'])
    result = {}
    for key in wanted:
        require(all(key in rows for rows in (*snapshots, declared, reported)), 'CPU lifetime absent/reused')
        a, b = (rows[key] for rows in snapshots)
        elapsed = b['observed_monotonic_seconds']-a['observed_monotonic_seconds']
        du = number(b['user_100ns'])-number(a['user_100ns'])
        dk = number(b['kernel_100ns'])-number(a['kernel_100ns'])
        require(elapsed > 0 and du >= 0 and dk >= 0, 'Nonmonotonic CPU counters/time')
        values = dict(user_seconds=du/1e7, kernel_seconds=dk/1e7, cpu_seconds=(du+dk)/1e7,
                      elapsed_seconds=elapsed, logical_cpu_equivalents=(du+dk)/1e7/elapsed)
        for original in (declared[key], reported[key]):
            require(all(type(original[k]) in (int, float) and math.isfinite(original[k])
                        and math.isclose(original[k], v, rel_tol=1e-9, abs_tol=1e-9)
                        for k, v in values.items()), 'Recorded CPU contradicts native counters')
        result[key] = dict(tid=key[0], created_filetime=key[1], **values,
                           scope='Entire OS thread in earlier x1 interval; not exclusive BirdManager/function CPU')
    return result


def scene_intervals(data):
    """Check saved game observations on their own frame/QPC clock domains."""
    names = ('cpu_scene_before', 'cpu_scene_after', 'roles_after', 'scene_after_metadata')
    scenes = [data[name] for name in names]
    for i, scene in enumerate(scenes):
        require(type(scene['frame']) is int and scene['frame'] >= 0, 'Invalid scene frame')
        for key in ('game_total_hours', 'observed_qpc_ms', 'frame_speed_multiplier'):
            require(type(scene[key]) in (int, float) and math.isfinite(scene[key]), 'Invalid scene clock/speed')
        require(scene['paused'] is (i >= 2) and scene['frame_speed_multiplier'] == (0 if i >= 2 else 1),
                'Scene does not confirm x1 interval then paused captures')
    require(all(a['frame'] < b['frame'] and a['observed_qpc_ms'] < b['observed_qpc_ms']
                for a, b in zip(scenes, scenes[1:])), 'Scene acquisition order contradicts frames/QPC')
    before, after, pause_before, pause_after = scenes
    hours = after['game_total_hours']-before['game_total_hours']
    seconds = (after['observed_qpc_ms']-before['observed_qpc_ms'])/1000
    require(hours > 0 and seconds > 0, 'No recorded x1 simulation progress')
    require(pause_before['game_total_hours'] >= after['game_total_hours']
            and pause_after['game_total_hours'] == pause_before['game_total_hours'], 'Paused game clock changed')
    computed = dict(wall_seconds=seconds, game_hours=hours, game_hours_per_wall_second=hours/seconds,
                    first_frame=before['frame'], last_frame=after['frame'])
    for key, value in computed.items():
        original = data['simulation_progress'][key]
        require(type(original) in (int, float) and math.isfinite(original)
                and math.isclose(original, value, rel_tol=0, abs_tol=1e-7 if key == 'wall_seconds' else 1e-12),
                'Recorded simulation progress contradicts scene clocks')
    return dict(simulation_progress=computed,
                observation_order=[dict(observation=name, frame=scene['frame'], paused=scene['paused'],
                                        game_total_hours=scene['game_total_hours'], observed_qpc_ms=scene['observed_qpc_ms'])
                                   for name, scene in zip(names, scenes)],
                scope='Saved scene frame/QPC order; not an equivalence between scene QPC, native CPU counter clocks or capture wall-clock timestamps')


def _static_rtti(pe, meta, game_base):
    vt, col, td = (number(meta[k]) for k in ('vtable_rva', 'col_rva', 'type_descriptor_rva'))
    require(meta['type_name'] == '.?AVBirdManager@@', 'Unexpected requested type')
    signature, offset, cd, actual_td, hierarchy, self_rva = struct.unpack('<6I', pe.raw(col, 24))
    require((signature, offset, cd, actual_td, self_rva) == (1, 0, 0, td, col), 'Incoherent static RTTI locator')
    name = pe.string(td+16)
    require(name == meta['type_name'], 'Static RTTI type name differs')
    sig, attrs, n, array = struct.unpack('<4I', pe.raw(hierarchy, 16))
    require(sig == 0 and 0 < n <= 32, 'Invalid static RTTI hierarchy')
    bases = []
    for i in range(n):
        desc, = struct.unpack('<I', pe.raw(array+4*i, 4))
        typ, _, md, pd, vd = struct.unpack('<IIiii', pe.raw(desc, 20))
        bases.append(dict(name=pe.string(typ+16), pmd=[md, pd, vd]))
    require([b['name'] for b in bases] == ['.?AVBirdManager@@', '.?AVThreadWannabe@@', '.?AVThreadClass@@']
            and all(b['pmd'] == [0, -1, 0] for b in bases), 'Unexpected RTTI base chain')
    pointers = struct.unpack('<5Q', pe.raw(vt-8, 40))
    require(pointers[0] == pe.image_base+col, 'Static vftable locator differs')
    targets = []
    for p in pointers[1:]:
        thunk = p-pe.image_base
        require(pe.section(thunk, 5)['characteristics'] & 0x20000000, 'Vftable target is not executable')
        raw = pe.raw(thunk, 5)
        require(raw[0] == 0xe9, 'Unknown virtual thunk form')
        targets.append(thunk+5+struct.unpack('<i', raw[1:])[0])
    require(targets[1:] == [0x25fca0, 0x2627f0, 0x25fbe0], 'Static virtual entry identities differ')
    # This-register proof is independent of RTTI names.
    require(pe.raw(0x25fcb4, 3) == bytes.fromhex('488be9') and pe.raw(0x25fe04, 4) == bytes.fromhex('41ff5310')
            and pe.raw(0x25fe22, 1) == b'\x5d', 'Receiver instruction proof differs')
    type_bytes = pe.raw(td, 16+len(name)+1)
    type_pointer, spare = struct.unpack('<QQ', type_bytes[:16])
    pe.section(type_pointer-pe.image_base)
    expected_type = struct.pack('<QQ', game_base+type_pointer-pe.image_base, spare)+type_bytes[16:]
    expected_vt = struct.pack('<5Q', *(game_base+p-pe.image_base for p in pointers))
    return dict(vtable_rva=vt, bases=bases, type_name=name, virtual_targets=[hex(x) for x in targets]), [
        (game_base+vt-8, expected_vt), (game_base+col, pe.raw(col, 24)), (game_base+td, expected_type)]


def analyze(input_path, expected_sha256=None):
    raw, source = file_identity(input_path, 20*1024*1024)
    if expected_sha256 is not None:
        require(re.fullmatch('[0-9a-fA-F]{64}', expected_sha256) is not None, 'Invalid expected SHA256')
        require(source['sha256'] == expected_sha256.lower(), 'Controller SHA256 differs')
    data = _json(raw)
    require(data['completed'] is True and data['admin'] is False, 'Incomplete/unsupported controller')
    pid = number(data['pid'])
    sources = data['map_sources']
    address_map = build(*(sources[k]['path'] for k in ('library', 'rva_table', 'executable')))
    for kind in ('library', 'rva_table', 'executable'):
        compare_file(address_map['sources'][kind], sources[kind])
    executable = Path(sources['executable']['path']).resolve()
    require(Path(data['executable']).resolve() == executable, 'Controller executable differs')
    binding = data['binding_before']
    process_creation = str(binding['process_created_filetime'])
    require(process_creation.isdecimal() and int(process_creation) > 0, 'Invalid process creation')
    base = pointer(binding['modules']['executable']['base'])
    lib_base = pointer(binding['modules']['library']['base'])
    for b in (binding, data['binding_after']):
        require(b['pid'] == pid and b['process_created_filetime'] == process_creation, 'Process lifetime changed')
        require(b['verified'] is True, 'Unverified recorded binding')
        for kind, expected_base in (('executable', base), ('library', lib_base)):
            mod = b['modules'][kind]
            require(number(mod['base']) == expected_base and mod['size'] == address_map[kind]['size_of_image']
                    and mod['source_sha256'] == sources[kind]['sha256']
                    and Path(mod['path']).resolve() == Path(sources[kind]['path']).resolve(), 'Module identity differs')
    require(base+address_map['executable']['size_of_image'] <= lib_base
            or lib_base+address_map['library']['size_of_image'] <= base, 'Overlapping module ranges')
    require(math.isclose(data['created_at'], int(process_creation)/1e7-11644473600, rel_tol=0, abs_tol=1e-6), 'Controller creation contradicts native binding')
    scene_evidence = scene_intervals(data)
    pe = _PE(Path(executable).read_bytes())
    proof_raw, receiver_proof = file_identity(data['static_metadata']['receiver_proof'], 1024*1024)
    require(receiver_proof['sha256'] == data['static_metadata']['receiver_proof_sha256'], 'Receiver proof SHA256 differs')
    proof = _json(proof_raw)
    require(proof['status'] == 'static_checks_passed' and proof['sources']['executable']['sha256'] == sources['executable']['sha256']
            and proof['function']['entry_rva'] == '0x25fca0'
            and proof['register_flow']['copy_rva'] == '0x25fcb4'
            and proof['register_flow']['copy_to'] == 'RBP'
            and proof['register_flow']['interior_RBP_assignments'] == [], 'Receiver proof provenance/flow differs')
    static, expected_metadata = _static_rtti(pe, data['static_metadata'], base)
    region = annotate(0x25fe08, address_map)
    require(region['unwind_region'] is not None and region['unwind_region']['begin_rva'] == 0x25fca0,
            'Ambiguous threadProc unwind region')
    require(any('threadProc@ThreadWannabe' in a['name'] for a in region['aliases']), 'Missing SDK threadProc identity')
    objects = unique(data['objects'])
    require(0 < len(objects) <= 8, 'Invalid receiver count')
    addresses = [pointer(o['address']) for o in objects.values()]
    require(len(set(addresses)) == len(addresses) and all(abs(a-b) >= 24 for i, a in enumerate(addresses) for b in addresses[i+1:]), 'Overlapping receiver headers')
    dumps, checked_frames = {}, {key: {} for key in objects}
    table_address = lib_base+address_map['resolver']['pointer_table_rva']
    table_size = len(address_map['slots'])*8
    for stage in ('discovery', 'confirmation'):
        recorded = data[stage]
        capture = recorded['capture']
        require(capture['pid'] == pid and capture['process_created_filetime'] == process_creation
                and Path(capture['executable']).resolve() == executable, 'Capture process identity differs')
        require(capture['write_succeeded'] is True and capture['completed'] is True and capture['cleanup_verified'] is True, 'Unsuccessful recorded capture')
        require(Path(capture['dump']).resolve() == Path(recorded['dump']).resolve(), 'Dump provenance path differs')
        dump = inspect_dump(recorded['dump'], pid, process_creation)
        compare_file(dump['provenance'], capture)
        require(set(dump['lifetimes']) == set(unique(capture['threads'])), 'Recorded dump thread lifetimes differ')
        native_table = compare_pointer_table(read_memory_range(recorded['dump'], table_address, table_size), base, address_map['slots'])
        require(native_table['verified'], 'Dump SDK table differs')
        require(native_table == recorded['sdk_binding_from_dump'], 'Recorded SDK verification contradicts dump')
        unwind = recorded['unwind']
        require(unwind['returncode'] == 0 and unwind['result']['offline_only'] is True
                and unwind['result']['open_hresult'] == '0x0' and unwind['result']['result_hresult'] == '0x0', 'Unsuccessful retained DbgEng result')
        threads = unique(unwind['result']['threads'])
        require(set(threads) == set(dump['lifetimes']), 'DbgEng/dump thread lifetimes differ')
        for key, thread in threads.items():
            require(thread['stack_hresult'] == '0x0' and 0 < len(thread['frames']) < thread['frame_limit'], 'Truncated/failed retained stack')
            for frame in thread['frames']:
                require(pointer(frame['pc']) == pointer(frame['context_pc'])
                        and pointer(frame['sp']) == pointer(frame['context_sp']), 'Retained frame/context PC/SP differ')
            top = thread['frames'][0]
            native = dump['contexts'][key[0]]
            require((number(top['context_pc']), number(top['context_sp']), number(top['nonvolatile']['rbp']))
                    == (native['pc'], native['sp'], native['rbp']), 'Retained top context differs from dump')
        for key, obj in objects.items():
            require(key in threads, 'Receiver thread lifetime absent')
            candidates = [f for f in threads[key]['frames'] if number(f['pc'])-base in (0x25fd3a, 0x25fe08)]
            require(len(candidates) == 1, 'Missing/ambiguous threadProc receiver frame')
            frame = candidates[0]
            checked_frames[key][stage] = validate_frame(frame, base, executable, pointer(obj['address']))
            require(obj[stage+'_frame'] == frame, 'Receiver frame copy contradicts retained stack')
        dumps[stage] = dict(provenance=dump['provenance'], process=dump['process'], sdk_table=native_table)
    confirm = data['confirmation']['dump']
    for address, expected in expected_metadata:
        require(read_memory_range(confirm, address, len(expected)) == expected, 'Confirmation RTTI/vftable differs from exact executable')
    resources = data['process_resources']
    require(resources['pid'] == pid and Path(resources['executable']).resolve() == executable
            and all(resources[p]['created_at'] == data['created_at'] for p in ('before', 'after')), 'CPU process provenance differs')
    cpu = cpu_join(resources, data['selected_lifetimes'], objects)
    rows = []
    for key, obj in objects.items():
        header = parse_base_header(read_memory_range(confirm, pointer(obj['address']), 24), key[0])
        require(header == obj['base_from_same_dump'], 'Recorded receiver header contradicts dump')
        bird = number(header['vptr']) == base+static['vtable_rva']
        require(bird == obj['bird_manager_vptr_matched'], 'Recorded receiver type contradicts vptr')
        rows.append(dict(tid=key[0], created_filetime=key[1], address=obj['address'], frames=checked_frames[key],
                         confirmation_header=header, bird_manager_vptr_matched=bird,
                         type='BirdManager' if bird else 'Other ThreadWannabe receiver; dynamic class not decoded', cpu=cpu[key]))
    declared_birds = {(identity(o), pointer(o['address'])) for o in data['bird_manager_objects']}
    require(declared_birds == {(identity(o), pointer(o['address'])) for o in rows if o['bird_manager_vptr_matched']}, 'Declared BirdManager identities contradict dump')
    # Recheck source/dump identities after all separate file-only readers completed.
    for original in [source, receiver_proof]+[d['provenance'] for d in dumps.values()]+list(address_map['sources'].values()):
        _, after = file_identity(original['path'])
        compare_file(after, original)
    return dict(format_version=1, verified=True, controller=source, sources=address_map['sources'], receiver_proof=receiver_proof,
                process=dict(pid=pid, recorded_native_created_filetime=process_creation,
                             exact_creation_authority='Saved capture/binding observations; dump MiscInfo independently records only seconds'),
                dumps=dumps, static_rtti=static, objects=rows,
                measurements=dict(cpu_interval='Earlier x1 native-counter interval, preceding paused discovery/confirmation captures',
                                  enclosing_cpu_elapsed_seconds=resources['elapsed_seconds'], stack_observations=len(dumps),
                                  scene_evidence=scene_evidence),
                limits=['No live process access, provider execution, recapture or re-unwind.',
                        'FrameContexts are retained DbgEng observations in the controller, not independently regenerated; top native contexts are compared with dump bytes.',
                        'Receiver header and RTTI are verified only in confirmation; discovery contains SDK table and contexts, not receiver/RTTI heap evidence.',
                        'Minidump memory and thread capture are not an atomic whole-process snapshot; preserved observations retain this acquisition limit.',
                        'CPU belongs to the entire OS thread in an earlier x1 interval; neither exclusive BirdManager/function CPU nor call frequency is inferred.',
                        'Two stack observations are not a CPU-time distribution. Other receiver class and BirdManager derived layout remain unknown.',
                        'Raw target handle value is metadata, not an independent thread lifetime proof.',
                        'Exact process FILETIME is saved external binding evidence; MiscInfo PID and creation second are separately checked.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    report = analyze(args.input, args.expected_sha256)
    protected = [report['controller']['path'], report['receiver_proof']['path']]+[s['path'] for s in report['sources'].values()]+[d['provenance']['path'] for d in report['dumps'].values()]
    require(args.output.resolve() not in {Path(p).resolve() for p in protected}, 'Output would overwrite evidence')
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
