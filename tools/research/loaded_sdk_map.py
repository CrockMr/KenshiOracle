"""Read-only, process-lifetime binding of a statically verified SDK map.

Only PE headers, verified FF25 stubs and their pointer slots are read. No game
function call, object-layout offset, code write, injection or hook is used.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import ctypes as C
from ctypes import wintypes as W
import hashlib
from pathlib import Path
import struct
import time
from thread_metadata import WindowsThreadMetadata


def compare_pointer_table(data,game_base,slots):
    if len(data)!=8*len(slots):raise ValueError('Loaded table length differs')
    expected=[game_base+r['game_rva'] for r in slots]
    if any(not 0<v<2**64 for v in expected):raise ValueError('Loaded pointer overflow')
    actual=struct.unpack('<%dQ'%len(slots),data)
    bad=[i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b]
    return dict(verified=not bad,slots_checked=len(slots),mismatch_count=len(bad),mismatched_slots=bad[:32],
        actual_sha256=hashlib.sha256(data).hexdigest(),expected_sha256=hashlib.sha256(struct.pack('<%dQ'%len(expected),*expected)).hexdigest())


def verify(pid,expected_executable,address_map):
    p=WindowsThreadMetadata();k=p.k;process=None
    k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
    result=dict(pid=pid,observed_at=time.time(),verified=False,cleanup={})
    def read(address,size):
        if not 0<size<=1024*1024:raise ValueError('Read bound exceeded')
        data=C.create_string_buffer(size);count=C.c_size_t()
        if not k.ReadProcessMemory(process,C.c_void_p(address),data,size,C.byref(count)):raise C.WinError(C.get_last_error())
        if count.value!=size:raise RuntimeError('Short loaded metadata read')
        return data.raw
    try:
        process=k.OpenProcess(0x410,False,pid)
        if not process:raise C.WinError(C.get_last_error())
        if k.GetProcessId(process)!=pid:raise RuntimeError('Process differs')
        length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
        if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)):raise C.WinError(C.get_last_error())
        if Path(image.value).resolve()!=Path(expected_executable).resolve():raise RuntimeError('Executable differs')
        result['executable']=image.value
        times=[W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(process,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
        result['process_created_filetime']=str(p.ticks(times[0]));modules=p.modules(pid)
        selected={}
        for kind in ('library','executable'):
            source=address_map['sources'][kind];file=Path(source['path'])
            blob=file.read_bytes()
            if hashlib.sha256(blob).hexdigest()!=source['sha256']:raise RuntimeError('Static source changed')
            hits=[m for m in modules if Path(m['path']).resolve()==file.resolve()]
            if len(hits)!=1:raise RuntimeError('Loaded module missing/ambiguous')
            module=hits[0];base=int(module['base'],16);meta=address_map[kind]
            if module['size']!=meta['size_of_image']:raise RuntimeError('Loaded image size differs')
            pe,=struct.unpack_from('<I',blob,0x3c);head=read(base+pe,24+64)
            if head[:4]!=b'PE\0\0' or struct.unpack_from('<H',head,4)[0]!=0x8664:
                raise RuntimeError('Loaded PE machine differs')
            if struct.unpack_from('<I',head,8)[0]!=meta['timestamp'] or struct.unpack_from('<I',head,24+56)[0]!=meta['size_of_image']:
                raise RuntimeError('Loaded PE metadata differs')
            selected[kind]=dict(module,source_sha256=source['sha256'])
            if kind=='library':library_bytes=blob
        lib_base=int(selected['library']['base'],16);game_base=int(selected['executable']['base'],16)
        resolver=address_map['resolver'];begin,end=resolver['stub_begin_rva'],resolver['stub_end_rva']
        sections=[s for s in address_map['library']['sections'] if s['rva']<=begin and end<=s['rva']+s['raw_size']]
        if len(sections)!=1:raise RuntimeError('Static stub file span differs')
        section=sections[0];start=section['raw_offset']+begin-section['rva'];expected_stubs=library_bytes[start:start+end-begin]
        actual_stubs=read(lib_base+begin,end-begin)
        result['stub_bytes_sha256']=hashlib.sha256(actual_stubs).hexdigest()
        if actual_stubs!=expected_stubs:raise RuntimeError('Loaded stubs differ from verified SDK')
        table_address=lib_base+resolver['pointer_table_rva'];size=resolver['function_slot_count']*8
        first=read(table_address,size);result['pointer_table']=compare_pointer_table(first,game_base,address_map['slots'])
        second=read(table_address,size)
        result['table_stable_during_reads']=first==second
        if not result['pointer_table']['verified'] or first!=second:raise RuntimeError('Loaded pointer pairing differs/changed')
        if p.modules(pid)!=modules:raise RuntimeError('Module inventory changed during binding')
        result.update(verified=True,modules=selected,pointer_table_address=hex(table_address),
            scope='Exact loaded SDK stub bytes and all function-slot values matched this static pairing at observation time; no write performed.')
    except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),winerror=getattr(e,'winerror',None))
    finally:
        if process:result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
        result['cleanup_verified']=all(result['cleanup'].values())
    return result
