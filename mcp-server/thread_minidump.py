"""External normal minidump filtered to selected, exact thread lifetimes.

No VA clone/full-memory/code-segment dump and no debugger attachment. DbgHelp
captures the selected contexts/stacks; a separate offline DbgEng helper unwinds.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import struct
import subprocess
import time
from thread_metadata import WindowsThreadMetadata
from stack_snapshot import DBGHELP,_dbghelp_lock


class CallbackInput(C.Structure):
    _pack_=4
    _fields_=[('ProcessId',W.DWORD),('ProcessHandle',W.HANDLE),('CallbackType',W.DWORD)]


def read_thread_lifetimes(path):
    raw=Path(path).read_bytes()
    if len(raw)<32 or raw[:4]!=b'MDMP':raise ValueError('Not a minidump')
    version,count,offset=struct.unpack_from('<III',raw,4)
    if version&0xffff!=42899 or not 1<=count<=128 or offset+12*count>len(raw):raise ValueError('Invalid dump directory')
    directories={}
    for i in range(count):
        kind,size,rva=struct.unpack_from('<III',raw,offset+i*12)
        if kind==0:
            if size or rva:raise ValueError('Malformed unused dump directory slot')
            continue
        if kind in directories or rva+size>len(raw):raise ValueError('Invalid/duplicate dump stream')
        directories[kind]=(rva,size)
    if 3 not in directories or 17 not in directories:raise ValueError('Missing thread or exact thread-info stream')
    rva,size=directories[3];n,=struct.unpack_from('<I',raw,rva)
    if not 1<=n<=8 or 4+48*n>size:raise ValueError('Thread list exceeds selected bound')
    ids=[]
    for i in range(n):
        at=rva+4+i*48;tid,=struct.unpack_from('<I',raw,at)
        context_size,context_rva=struct.unpack_from('<II',raw,at+40)
        if context_size<256 or context_rva+context_size>len(raw):raise ValueError('Missing recorded thread context')
        ids.append(tid)
    if len(set(ids))!=len(ids):raise ValueError('Duplicate recorded thread ID')
    rva,size=directories[17];header,entry,count=struct.unpack_from('<III',raw,rva)
    if header<12 or entry<64 or count>4096 or header+entry*count>size:raise ValueError('Invalid thread-info bounds')
    rows={}
    for i in range(count):
        at=rva+header+i*entry;tid,flags,error,exit_code=struct.unpack_from('<IIII',raw,at)
        creation,=struct.unpack_from('<Q',raw,at+16)
        if tid in rows:raise ValueError('Duplicate exact thread-info identity')
        rows[tid]=dict(tid=tid,created_filetime=str(creation),dump_flags=flags,dump_error=hex(error),exit_status=exit_code)
    if any(tid not in rows or rows[tid]['dump_flags']&0x3f or rows[tid]['dump_error']!='0x0' for tid in ids):
        raise ValueError('Thread-info contains incomplete/error/exited context')
    return [rows[tid] for tid in ids]


def read_memory_range(path,address,size):
    """Read an exact captured range, never fall back to live process memory."""
    raw=Path(path).read_bytes()
    if len(raw)<32 or raw[:4]!=b'MDMP' or not 0<size<=1024*1024:raise ValueError('Invalid dump/range')
    count,directory=struct.unpack_from('<II',raw,8)
    if count>128 or directory+12*count>len(raw):raise ValueError('Invalid dump directory')
    matches=[]
    for i in range(count):
        kind,length,rva=struct.unpack_from('<III',raw,directory+i*12)
        if kind!=5:continue
        if rva+length>len(raw) or length<4:raise ValueError('Invalid recorded memory list')
        n,=struct.unpack_from('<I',raw,rva)
        if n>65536 or 4+16*n>length:raise ValueError('Invalid recorded memory count')
        for j in range(n):
            start,amount,data=struct.unpack_from('<QII',raw,rva+4+16*j)
            if data+amount>len(raw):raise ValueError('Recorded memory outside file')
            if start<=address and address+size<=start+amount:
                matches.append(raw[data+address-start:data+address-start+size])
    if len(matches)!=1:raise ValueError('Requested memory missing/ambiguous in dump')
    return matches[0]


def metadata_ranges(extra_memory=None,extra_memory_ranges=None):
    """Bound caller-verified metadata, retaining the old single-range input."""
    if extra_memory is not None and extra_memory_ranges is not None:
        raise ValueError('Select one additional-memory input')
    ranges=[extra_memory] if extra_memory is not None else ([] if extra_memory_ranges is None else extra_memory_ranges)
    if not isinstance(ranges,(tuple,list)) or len(ranges)>8:raise ValueError('At most eight metadata ranges')
    checked=[]
    for pair in ranges:
        if not isinstance(pair,(tuple,list)) or len(pair)!=2:raise ValueError('Invalid metadata range')
        address,size=pair
        if (type(address) is not int or type(size) is not int or not 0<address<2**47 or
            not 0<size<=1024*1024 or address+size>2**47):raise ValueError('Invalid metadata range bounds')
        if any(address<start+amount and start<address+size for start,amount in checked):
            raise ValueError('Overlapping metadata ranges')
        checked.append((address,size))
    if sum(size for _,size in checked)>1024*1024:raise ValueError('Metadata byte bound exceeded')
    return checked


def capture(pid,expected_executable,identities,dump_path,extra_memory=None,extra_memory_ranges=None):
    wanted=dict(identities)
    if not 1<=len(wanted)<=8 or len(wanted)!=len(identities):raise ValueError('Select 1..8 unique thread lifetimes')
    path=Path(dump_path).resolve()
    if path.exists() or not path.parent.is_dir():raise ValueError('Requires a new dump file in an existing directory')
    ranges=metadata_ranges(extra_memory,extra_memory_ranges)
    provider=WindowsThreadMetadata();k=provider.k
    k.OpenThread.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenThread.restype=W.HANDLE
    k.GetThreadId.argtypes=[W.HANDLE];k.GetThreadId.restype=W.DWORD
    k.GetProcessIdOfThread.argtypes=[W.HANDLE];k.GetProcessIdOfThread.restype=W.DWORD
    k.GetThreadTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4;k.GetThreadTimes.restype=W.BOOL
    d=C.WinDLL(str(DBGHELP),use_last_error=True,winmode=0x1100)
    callback_type=C.WINFUNCTYPE(W.BOOL,C.c_void_p,C.POINTER(CallbackInput),C.c_void_p)
    class CallbackInfo(C.Structure):_fields_=[('CallbackRoutine',callback_type),('CallbackParam',C.c_void_p)]
    d.MiniDumpWriteDump.argtypes=[W.HANDLE,W.DWORD,W.HANDLE,W.DWORD,C.c_void_p,C.c_void_p,C.POINTER(CallbackInfo)]
    d.MiniDumpWriteDump.restype=W.BOOL
    result=dict(pid=pid,started_at=time.time(),dump=str(path),dump_type=0x1400,callbacks={},cleanup={},
        scope='Selected user-thread contexts/stacks recorded externally; not an atomic CPU profile.')
    if extra_memory is not None:
        address,size=extra_memory
        result['extra_memory']=dict(address=hex(address),bytes=size)
    result['extra_memory_ranges']=[dict(address=hex(address),bytes=size) for address,size in ranges]
    extra_index=0
    process=None;handles=[];fd=None;started=time.perf_counter()
    try:
        if C.sizeof(CallbackInput)!=16 or CallbackInput.CallbackType.offset!=12:raise RuntimeError('Unexpected minidump callback ABI')
        process=k.OpenProcess(0x410,False,pid)
        if not process:raise C.WinError(C.get_last_error())
        if k.GetProcessId(process)!=pid:raise RuntimeError('Process owner differs')
        length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
        if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)):raise C.WinError(C.get_last_error())
        result['executable']=image.value
        if Path(image.value).resolve()!=Path(expected_executable).resolve():raise RuntimeError('Executable differs')
        times=[W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(process,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
        result['process_created_filetime']=str(provider.ticks(times[0]))
        for tid,created in wanted.items():
            handle=k.OpenThread(0x800,False,tid)
            if not handle:raise C.WinError(C.get_last_error())
            handles.append(handle)
            if k.GetThreadId(handle)!=tid or k.GetProcessIdOfThread(handle)!=pid:raise RuntimeError('Thread owner differs')
            if not k.GetThreadTimes(handle,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
            if str(provider.ticks(times[0]))!=created:raise RuntimeError('Thread creation differs')
        def callback(param,input_ptr,output):
            nonlocal extra_index
            try:
                data=input_ptr.contents;kind=data.CallbackType
                result['callbacks'][str(kind)]=result['callbacks'].get(str(kind),0)+1
                if data.ProcessId!=pid:return False
                if kind==3: # IncludeThreadCallback; union's first DWORD is ThreadId.
                    return C.c_uint32.from_address(C.addressof(data)+16).value in wanted
                if kind==1: # ThreadCallback; remove instruction windows and arbitrary thread data.
                    flags=C.c_uint32.from_address(output);flags.value&=0x47
                if kind==0: # ModuleCallback; identity/debug records only, no module code/data segments.
                    flags=C.c_uint32.from_address(output);flags.value&=0xd
                if kind in (16,17): # Real process; no caller-provided virtual-memory callback service.
                    C.c_uint32.from_address(output).value=0
                if kind==5: # Explicit verified metadata only: SDK table or small SDK base headers.
                    if extra_index<len(ranges):
                        address,size=ranges[extra_index];extra_index+=1
                        C.c_uint64.from_address(output).value=address
                        C.c_uint32.from_address(output+8).value=size
                        return True
                    C.c_uint64.from_address(output).value=0;C.c_uint32.from_address(output+8).value=0
                    return False
                if kind==6: # CancelCallback: bounded library work, no blind cancellation assumption.
                    C.c_uint32.from_address(output).value=1
                    C.c_uint32.from_address(output+4).value=time.perf_counter()-started>10
                return True
            except Exception as e:result['callback_error']=str(e);return False
        fn=callback_type(callback);info=CallbackInfo(fn,None)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_BINARY,0o600)
        with _dbghelp_lock:
            C.set_last_error(0);ok=d.MiniDumpWriteDump(process,pid,msvcrt.get_osfhandle(fd),0x1400,None,None,C.byref(info))
            result['write_succeeded']=bool(ok);result['write_error']=hex(C.get_last_error())
        if not ok:raise RuntimeError('MiniDumpWriteDump failed: '+result['write_error'])
        os.close(fd);fd=None
        result['bytes']=path.stat().st_size;result['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        if result['bytes']>64*1024*1024:raise RuntimeError('Dump exceeds selected-stack byte bound')
        result['threads']=read_thread_lifetimes(path)
        if {(r['tid'],r['created_filetime']) for r in result['threads']}!=set(identities):raise RuntimeError('Recorded thread lifetimes disagree')
        result['completed']=True
    except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),winerror=getattr(e,'winerror',None))
    finally:
        if fd is not None:os.close(fd)
        result['cleanup']['thread_handles_closed']=all([bool(k.CloseHandle(h)) for h in handles])
        if process:result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
        result['cleanup_verified']=all(result['cleanup'].values());result['elapsed_seconds']=time.perf_counter()-started
    return result


def unwind(path,output,local_symbols,local_images,helper):
    args=[str(Path(helper).resolve()),str(Path(path).resolve()),str(Path(local_symbols).resolve()),str(Path(local_images).resolve())]
    done=subprocess.run(args,capture_output=True,text=True,errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    Path(output).write_text(done.stdout,encoding='utf-8')
    return dict(argv=args,returncode=done.returncode,stderr=done.stderr,result=json.loads(done.stdout))
