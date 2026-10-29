"""Static, hash-bound KenshiLib stub/RVA and AMD64 unwind metadata.

No target code is loaded or executed. No process is opened. The .br suffix is
not a compression declaration: KenshiLib InitRVAs reads little-endian int32s.
https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Source/core/Functions.cpp
https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64

The output is a static pairing selected by the caller. A loaded pointer-table
comparison is still required to verify that pairing against a process snapshot.
Unwind regions are not inferred source-function extents; aliases stay plural.
"""
from bisect import bisect_right
from collections import defaultdict
import hashlib
from pathlib import Path
import struct

MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 1_000_000
EXECUTE = 0x20000000
WRITE = 0x80000000


def _read(path):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= MAX_FILE_BYTES:
        raise ValueError('Unsupported source size/type')
    data = path.read_bytes()
    after = path.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if stamp(before) != stamp(after) or len(data) != before.st_size:
        raise ValueError('Source changed while reading')
    return data, dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


class _PE:
    def __init__(self, data):
        self.data = data
        if len(data) < 64 or data[:2] != b'MZ':
            raise ValueError('Invalid DOS header')
        pe = self.unpack('<I', 0x3c)[0]
        if pe < 64 or self.bytes(pe, 4) != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        machine, count, stamp, _, _, optional_size, flags = self.unpack('<HHIIIHH', pe+4)
        if machine != 0x8664 or not 1 <= count <= 96:
            raise ValueError('Requires a bounded AMD64 PE section table')
        optional = pe+24
        self.bytes(optional, optional_size)
        if optional_size < 112 or self.unpack('<H', optional)[0] != 0x20b:
            raise ValueError('Requires PE32+ optional header')
        self.image_base = self.unpack('<Q', optional+24)[0]
        self.size_image, self.size_headers = self.unpack('<II', optional+56)
        directories = self.unpack('<I', optional+108)[0]
        if directories > 64 or optional_size < 112+8*directories:
            raise ValueError('Invalid data-directory table')
        self.directories = [self.unpack('<II', optional+112+8*i) for i in range(directories)]
        section_table = optional+optional_size
        self.bytes(section_table, count*40)
        if not section_table+count*40 <= self.size_headers <= len(data) or self.size_image < self.size_headers:
            raise ValueError('Invalid header/image bounds')
        self.sections = []
        for i in range(count):
            off = section_table+40*i
            raw_name = self.bytes(off, 8).split(b'\0')[0]
            name = raw_name.decode('ascii', errors='backslashreplace')
            virtual_size, va, raw_size, raw = self.unpack('<IIII', off+8)
            characteristics = self.unpack('<I', off+36)[0]
            size = max(virtual_size, raw_size)
            if not size or va < self.size_headers or va+size > self.size_image:
                raise ValueError('Invalid section image bounds')
            if raw_size:
                if raw < self.size_headers:
                    raise ValueError('Section overlaps headers')
                self.bytes(raw, raw_size)
            row = dict(name=name, rva=va, virtual_size=virtual_size, memory_size=size,
                       raw_offset=raw, raw_size=raw_size, characteristics=characteristics)
            for previous in self.sections:
                if max(va, previous['rva']) < min(va+size, previous['rva']+previous['memory_size']):
                    raise ValueError('Overlapping section image ranges')
                if raw_size and previous['raw_size'] and max(raw, previous['raw_offset']) < min(raw+raw_size, previous['raw_offset']+previous['raw_size']):
                    raise ValueError('Overlapping section file ranges')
            self.sections.append(row)
        self.metadata = dict(machine='amd64', bits=64, timestamp=stamp, image_base=hex(self.image_base),
                             size_of_image=self.size_image, size_of_headers=self.size_headers,
                             dll=bool(flags & 0x2000), sections=self.sections)

    def bytes(self, offset, size):
        if offset < 0 or size < 0 or offset+size > len(self.data):
            raise ValueError('PE file range is out of bounds')
        return self.data[offset:offset+size]

    def unpack(self, fmt, offset):
        return struct.unpack(fmt, self.bytes(offset, struct.calcsize(fmt)))

    def section(self, rva, size=1, raw=False):
        if rva < 0 or size <= 0 or rva+size > self.size_image:
            raise ValueError('RVA image range is out of bounds')
        matches = [s for s in self.sections if s['rva'] <= rva and
                   rva+size <= s['rva']+(s['raw_size'] if raw else s['memory_size'])]
        if len(matches) != 1:
            raise ValueError('RVA does not resolve to one complete section range')
        return matches[0]

    def raw(self, rva, size):
        section = self.section(rva, size, raw=True)
        return self.bytes(section['raw_offset']+rva-section['rva'], size)

    def string(self, rva):
        section = self.section(rva, raw=True)
        available = section['rva']+section['raw_size']-rva
        data = self.raw(rva, min(available, 8192))
        end = data.find(b'\0')
        if end < 0:
            raise ValueError('Unterminated or oversized export string')
        try:
            return data[:end].decode('ascii')
        except UnicodeDecodeError as error:
            raise ValueError('Non-ASCII export string') from error

    def directory(self, index):
        rva, size = self.directories[index] if index < len(self.directories) else (0, 0)
        if bool(rva) != bool(size):
            raise ValueError('Incomplete data-directory bounds')
        if rva:
            self.raw(rva, size)
        return rva, size

    def exports(self):
        rva, size = self.directory(0)
        if size < 40:
            raise ValueError('Missing export directory')
        _, _, _, _, dll_name, base, functions, names, functions_rva, names_rva, ordinals_rva = struct.unpack('<IIHHIIIIIII', self.raw(rva, 40))
        if not 0 < functions <= MAX_ENTRIES or names > MAX_ENTRIES or base+functions > 2**32:
            raise ValueError('Invalid export table count')
        library_name = self.string(dll_name)
        addresses = struct.unpack('<%dI' % functions, self.raw(functions_rva, functions*4))
        name_addresses = struct.unpack('<%dI' % names, self.raw(names_rva, names*4)) if names else []
        ordinals = struct.unpack('<%dH' % names, self.raw(ordinals_rva, names*2)) if names else []
        seen = set()
        result = []
        for name_rva, index in zip(name_addresses, ordinals):
            if index >= functions:
                raise ValueError('Export ordinal index is out of bounds')
            name = self.string(name_rva)
            if not name or name in seen:
                raise ValueError('Duplicate or empty export name')
            seen.add(name)
            address = addresses[index]
            if not address:
                raise ValueError('Named export has a null RVA')
            self.section(address)
            forwarder = self.string(address) if rva <= address < rva+size else None
            if forwarder is not None and address+len(forwarder)+1 > rva+size:
                raise ValueError('Forwarder string exceeds export directory')
            result.append(dict(name=name, ordinal=base+index, rva=address, forwarder=forwarder))
        return result, dict(dll_name=library_name, directory_rva=rva, directory_size=size,
                            function_count=functions, named_export_count=names)

    def imports(self):
        """Validate ordinary import descriptors/thunks without resolving/loading DLLs."""
        rva, size = self.directory(1)
        if not size:
            return dict(directory_rva=0, directory_size=0, descriptors=[])
        if size < 20 or size//20 > MAX_ENTRIES:
            raise ValueError('Invalid import descriptor bounds')
        rows = []
        terminated = False
        for off in range(0, size-19, 20):
            original, stamp, forwarder_chain, name, iat = struct.unpack('<IIIII', self.raw(rva+off, 20))
            if not any((original, stamp, forwarder_chain, name, iat)):
                terminated = True
                break
            if not name or not iat:
                raise ValueError('Incomplete import descriptor')
            dll = self.string(name)
            if not dll:
                raise ValueError('Empty imported DLL name')
            lookup = original or iat
            count = 0
            names_verified = bool(original or not stamp)
            for index in range(MAX_ENTRIES):
                value = struct.unpack('<Q', self.raw(lookup+index*8, 8))[0]
                if not value:
                    break
                if names_verified:
                    if value & (1 << 63):
                        if value & ~((1 << 63) | 0xffff):
                            raise ValueError('Invalid ordinal import thunk')
                    else:
                        if value >= 2**32:
                            raise ValueError('Import-name thunk is not an RVA')
                        self.raw(value, 2)  # Hint, not a function address.
                        if not self.string(value+2):
                            raise ValueError('Empty imported symbol name')
                count += 1
            else:
                raise ValueError('Unterminated import thunk table')
            self.raw(iat, (count+1)*8)
            if struct.unpack('<Q', self.raw(iat+count*8, 8))[0]:
                raise ValueError('Import address table has no matching terminator')
            rows.append(dict(dll=dll, lookup_rva=original, iat_rva=iat, timestamp=stamp,
                             thunk_count=count, names_validated=names_verified))
        if not terminated:
            raise ValueError('Unterminated import descriptor table')
        return dict(directory_rva=rva, directory_size=size, descriptors=rows)

    def pdata(self):
        rva, size = self.directory(3)
        if not size:
            return [], dict(directory_rva=0, directory_size=0, count=0, source_order_sorted=True,
                            source_order_regressions=[], lookup_order='sorted_index_of_source_records')
        if size % 12 or size//12 > MAX_ENTRIES:
            raise ValueError('Invalid AMD64 exception table size')
        result = []
        previous_begin = -1
        regressions = []
        for index, (begin, end, unwind) in enumerate(struct.iter_unpack('<III', self.raw(rva, size))):
            if begin >= end:
                raise ValueError('Invalid unwind region')
            if begin < previous_begin:
                regressions.append(dict(table_index=index, previous_begin_rva=previous_begin, begin_rva=begin))
            if not self.section(begin, end-begin)['characteristics'] & EXECUTE:
                raise ValueError('Unwind region is not executable')
            header = self.raw(unwind, 4)
            version, flags, count = header[0] & 7, header[0] >> 3, header[2]
            chain = None
            if version in (1, 2):
                codes_size = (4+count*2+3) & ~3
                self.raw(unwind, codes_size)
                if flags & 4:
                    if flags & 3:
                        raise ValueError('Chained unwind also declares an exception handler')
                    cb, ce, cu = struct.unpack('<III', self.raw(unwind+codes_size, 12))
                    if cb >= ce or not self.section(cb, ce-cb)['characteristics'] & EXECUTE:
                        raise ValueError('Invalid chained unwind code bounds')
                    self.raw(cu, 4)
                    chain = dict(begin_rva=cb, end_rva=ce, unwind_rva=cu)
                elif flags & 3:
                    handler = struct.unpack('<I', self.raw(unwind+codes_size, 4))[0]
                    if not self.section(handler)['characteristics'] & EXECUTE:
                        raise ValueError('Exception handler is not executable')
            result.append(dict(source_table_index=index, begin_rva=begin, end_rva=end, unwind_rva=unwind,
                               unwind_version=version, unwind_flags=flags, optional_unwind_fields_decoded=version in (1,2),
                               chained_region=chain))
            previous_begin = begin
        # Retain source indices and expose the anomaly; sorting an index never
        # repairs the target's unwind table or validates a Windows stack walk.
        return result, dict(directory_rva=rva, directory_size=size, count=len(result),
                            source_order_sorted=not regressions, source_order_regressions=regressions,
                            lookup_order='sorted_index_of_source_records')


def build(lib_path, rva_table_path, exe_path):
    """Build static metadata; never claims the file table equals a loaded table."""
    lib_bytes, lib_source = _read(lib_path)
    table_bytes, table_source = _read(rva_table_path)
    exe_bytes, exe_source = _read(exe_path)
    lib, exe = _PE(lib_bytes), _PE(exe_bytes)
    if not lib.metadata['dll'] or exe.metadata['dll']:
        raise ValueError('Expected library DLL and game executable')
    imports = dict(library=lib.imports(), executable=exe.imports())
    if len(table_bytes) % 4 or len(table_bytes)//4 > MAX_ENTRIES:
        raise ValueError('RVA table must contain bounded little-endian uint32 entries')
    table = struct.unpack('<%dI' % (len(table_bytes)//4), table_bytes)
    exports, export_meta = lib.exports()
    named = {row['name']: row for row in exports}
    if any(name not in named or named[name]['forwarder'] for name in ('FUNC_BEGIN', 'FUNC_END')):
        raise ValueError('Missing local stub boundary exports')
    begin, end = named['FUNC_BEGIN']['rva'], named['FUNC_END']['rva']
    stride = 6  # AMD64 FF25 disp32, verified independently for every slot below.
    if begin >= end or (end-begin) % stride or not lib.section(begin, end-begin)['characteristics'] & EXECUTE:
        raise ValueError('Invalid executable stub bounds')
    count = (end-begin)//stride
    if not 0 < count <= MAX_ENTRIES or len(table) < count:
        raise ValueError('RVA table is shorter than the verified stub interval')
    pointer_table = None
    for slot in range(count):
        address = begin+slot*stride
        code = lib.raw(address, stride)
        if code[:2] != b'\xff\x25':
            raise ValueError('Unsupported non-FF25 stub')
        target = address+stride+struct.unpack_from('<i', code, 2)[0]
        if pointer_table is None:
            pointer_table = target
        if pointer_table % 8 or target != pointer_table+slot*8:
            raise ValueError('Stub pointer slots are not one aligned contiguous table')
    if not lib.section(pointer_table, len(table)*8)['characteristics'] & WRITE:
        raise ValueError('Loaded pointer table section is not writable')
    by_slot = defaultdict(list)
    for row in exports:
        if row['forwarder'] is None and begin <= row['rva'] < end:
            if (row['rva']-begin) % stride:
                raise ValueError('Named export is not aligned to a verified stub')
            if row['name'] != 'FUNC_BEGIN':
                by_slot[(row['rva']-begin)//stride].append(dict(name=row['name'], ordinal=row['ordinal']))
    slots, aliases = [], defaultdict(list)
    for slot, target in enumerate(table[:count]):
        if not exe.section(target)['characteristics'] & EXECUTE:
            raise ValueError('A function slot does not target executable game memory')
        row = dict(slot=slot, stub_rva=begin+slot*stride, game_rva=target, aliases=by_slot.get(slot, []))
        slots.append(row)
        for alias in row['aliases']:
            if alias['name'] != 'FUNC_BEGIN':
                aliases[hex(target)].append(dict(alias, slot=slot, stub_rva=row['stub_rva']))
    trailing = []
    for slot in range(count, len(table)):
        section = exe.section(table[slot])
        trailing.append(dict(slot=slot, game_rva=table[slot], section=section['name'],
                             executable=bool(section['characteristics'] & EXECUTE), classification='not_a_verified_function_stub'))
    pdata, pdata_meta = exe.pdata()
    lookup = sorted(range(len(pdata)), key=lambda i: (pdata[i]['begin_rva'], pdata[i]['end_rva'], i))
    begins, prefix_ends, high, overlap_count = [], [], 0, 0
    for source_index in lookup:
        region = pdata[source_index]
        if region['begin_rva'] < high:
            overlap_count += 1
        begins.append(region['begin_rva'])
        high = max(high, region['end_rva'])
        prefix_ends.append(high)
    # Detect replacement/changes during parsing; never silently rebind provenance.
    for original in (lib_source, table_source, exe_source):
        _, again = _read(original['path'])
        if again != original:
            raise ValueError('A source changed during map construction')
    return dict(format_version=1, architecture='amd64', sources=dict(library=lib_source, rva_table=table_source, executable=exe_source),
                library=lib.metadata, executable=exe.metadata, exports=export_meta,
                imports=imports,
                resolver=dict(stub_begin_rva=begin, stub_end_rva=end, stub_size=stride, function_slot_count=count,
                    table_entry_count=len(table), pointer_table_rva=pointer_table, pointer_size=8,
                    named_stub_slots=len(by_slot), unnamed_stub_slots=[i for i in range(count) if not by_slot.get(i)]),
                slots=slots, aliases_by_game_rva=dict(aliases), trailing_slots=trailing,
                pdata=pdata, pdata_metadata=dict(pdata_meta, overlap_count=overlap_count),
                pdata_lookup_indices=lookup, pdata_begins=begins, pdata_prefix_max_end=prefix_ends,
                runtime_binding_verified=False,
                loaded_slot_verification=dict(address_formula='library_base + pointer_table_rva + slot * pointer_size',
                    expected_value_formula='game_executable_base + slots[slot].game_rva',
                    method='Read the pointer from the same captured snapshot; compare full value, module hashes and process lifetime.'),
                limitations=['Static caller-selected pairing, not proof of which RVA table is loaded in a process.',
                    'All names sharing an entry are aliases; none is selected as the unique source function.',
                    'Unwind regions may be fragments/chained or missing for leaf functions; they are not inferred source-function extents.',
                    'Unsorted source exception tables are explicitly marked; a sorted lookup index is not a repair or proof of runtime unwind validity.',
                    'Unknown unwind versions are retained without decoding their optional fields.',
                    'Import descriptors/thunks are validated, not resolved or executed; delayed imports are not part of the name mapping.',
                    'No nearest-symbol fallback and no function end inferred from the next SDK entry.',
                    'Return-address adjustment, if wanted, belongs to the caller and must preserve the original address.'])


def annotate(game_rva, address_map):
    """Annotate exactly one RVA with a unique containing unwind region or exact entry.

    This never changes a return address to PC-1. The caller knows its address kind.
    """
    if isinstance(game_rva, bool) or not isinstance(game_rva, int) or not 0 <= game_rva < 2**32:
        raise ValueError('Expected uint32 game RVA')
    if address_map.get('format_version') != 1 or address_map.get('architecture') != 'amd64':
        raise ValueError('Unsupported address map')
    regions = address_map['pdata']
    lookup = address_map['pdata_lookup_indices']
    begins, prefix = address_map['pdata_begins'], address_map['pdata_prefix_max_end']
    if len(regions) != len(begins) or len(regions) != len(prefix) or len(regions) != len(lookup):
        raise ValueError('Incomplete unwind index')
    exact = address_map['aliases_by_game_rva'].get(hex(game_rva), [])
    hits = []
    index = bisect_right(begins, game_rva)-1
    while index >= 0 and prefix[index] > game_rva:
        region = regions[lookup[index]]
        if region['begin_rva'] <= game_rva < region['end_rva']:
            hits.append(region)
        index -= 1
    result = dict(game_rva=game_rva, runtime_binding_verified=address_map['runtime_binding_verified'],
                  aliases=[], exact_entry_aliases=exact, unwind_region=None)
    if len(hits) > 1:
        return dict(result, status='unknown_ambiguous_unwind_region', candidate_unwind_regions=hits)
    if hits:
        region = hits[0]
        status = 'unwind_region' if address_map['pdata_metadata']['source_order_sorted'] else 'static_unwind_region_unsorted_source'
        return dict(result, status=status, unwind_region=region,
                    source_table_order_sorted=address_map['pdata_metadata']['source_order_sorted'],
                    aliases=address_map['aliases_by_game_rva'].get(hex(region['begin_rva']), []),
                    scope='Aliases match this unwind-region entry exactly; no entire source-function extent inferred.')
    if exact:
        return dict(result, status='exact_entry_only', aliases=exact,
                    scope='Exact named entry without a containing static unwind region; no extent known.')
    return dict(result, status='unknown_no_unwind_region')
