"""Bounded x64 user stacks from a PSS VA clone and captured contexts.

No debugger attachment, target injection, kernel recorder or live-thread unwind.
All unwind memory reads use the snapshot's borrowed clone handle. No memory bytes
or argument values are retained. DbgHelp is serialized and uses local paths only.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import struct
import threading
import time
from thread_metadata import WindowsThreadMetadata,locate_module

DBGHELP=Path(os.environ.get('KENSHI_DBGHELP') or 'dbghelp.dll')
_dbghelp_lock=threading.Lock()


class Address(C.Structure):
    _fields_=[('Offset',C.c_ulonglong),('Segment',W.WORD),('Mode',C.c_int)]


class KdHelp(C.Structure):
    _fields_=[('Thread',C.c_ulonglong),('ThCallbackStack',W.DWORD),('ThCallbackBStore',W.DWORD),
        ('NextCallback',W.DWORD),('FramePointer',W.DWORD),('KiCallUserMode',C.c_ulonglong),
        ('KeUserCallbackDispatcher',C.c_ulonglong),('SystemRangeStart',C.c_ulonglong),
        ('KiUserExceptionDispatcher',C.c_ulonglong),('StackBase',C.c_ulonglong),('StackLimit',C.c_ulonglong),
        ('BuildVersion',W.DWORD),('RetpolineStubFunctionTableSize',W.DWORD),('RetpolineStubFunctionTable',C.c_ulonglong),
        ('RetpolineStubOffset',W.DWORD),('RetpolineStubSize',W.DWORD),('Reserved0',C.c_ulonglong*2)]


class StackFrame(C.Structure):
    _fields_=[('AddrPC',Address),('AddrReturn',Address),('AddrFrame',Address),('AddrStack',Address),
        ('AddrBStore',Address),('FuncTableEntry',C.c_void_p),('Params',C.c_ulonglong*4),('Far',W.BOOL),
        ('Virtual',W.BOOL),('Reserved',C.c_ulonglong*3),('KdHelp',KdHelp)]


class ContextHead(C.Structure):
    _fields_=[('Home',C.c_ulonglong*6),('ContextFlags',W.DWORD),('MxCsr',W.DWORD),('Segments',W.WORD*6),
        ('EFlags',W.DWORD),('Debug',C.c_ulonglong*6),('Rax',C.c_ulonglong),('Rcx',C.c_ulonglong),
        ('Rdx',C.c_ulonglong),('Rbx',C.c_ulonglong),('Rsp',C.c_ulonglong),('Rbp',C.c_ulonglong),
        ('Rsi',C.c_ulonglong),('Rdi',C.c_ulonglong),('R8',C.c_ulonglong),('R9',C.c_ulonglong),
        ('R10',C.c_ulonglong),('R11',C.c_ulonglong),('R12',C.c_ulonglong),('R13',C.c_ulonglong),
        ('R14',C.c_ulonglong),('R15',C.c_ulonglong),('Rip',C.c_ulonglong)]


class MemoryRegion(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),
        ('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]


def layout():
    return dict(address=C.sizeof(Address),kdhelp=C.sizeof(KdHelp),stackframe=C.sizeof(StackFrame),
        kdhelp_offset=StackFrame.KdHelp.offset,rsp_offset=ContextHead.Rsp.offset,rip_offset=ContextHead.Rip.offset)


class WindowsStackSnapshot(WindowsThreadMetadata):
    def __init__(self,dbghelp=DBGHELP):
        super().__init__()
        if layout()!=dict(address=16,kdhelp=112,stackframe=264,kdhelp_offset=152,rsp_offset=152,rip_offset=248):
            raise RuntimeError('Unexpected x64 stack ABI')
        k=self.k
        k.PssQuerySnapshot.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];k.PssQuerySnapshot.restype=W.DWORD
        k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
        k.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(MemoryRegion),C.c_size_t];k.VirtualQueryEx.restype=C.c_size_t
        if C.sizeof(MemoryRegion)!=48 or MemoryRegion.Protect.offset!=36:raise RuntimeError('Unexpected memory-region ABI')
        self.dbghelp_path=Path(dbghelp).resolve()
        if not self.dbghelp_path.is_file():
            raise RuntimeError('Set KENSHI_DBGHELP to the reviewed x64 Windows SDK dbghelp.dll')
        self.d=C.WinDLL(str(self.dbghelp_path),use_last_error=True,winmode=0x1100)
        sig={
            'SymSetOptions':([W.DWORD],W.DWORD),'SymInitializeW':([W.HANDLE,W.LPCWSTR,W.BOOL],W.BOOL),
            'SymCleanup':([W.HANDLE],W.BOOL),
            'SymLoadModuleExW':([W.HANDLE,W.HANDLE,W.LPCWSTR,W.LPCWSTR,C.c_ulonglong,W.DWORD,C.c_void_p,W.DWORD],C.c_ulonglong),
            'SymFunctionTableAccess64':([W.HANDLE,C.c_ulonglong],C.c_void_p),
            'SymGetModuleBase64':([W.HANDLE,C.c_ulonglong],C.c_ulonglong),
            'StackWalk64':([W.DWORD,W.HANDLE,W.HANDLE,C.POINTER(StackFrame),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p],W.BOOL)}
        for name,(args,result) in sig.items():getattr(self.d,name).argtypes=args;getattr(self.d,name).restype=result

    def capture(self,pid,expected_executable,identities=None,max_frames=48,local_symbols=None):
        if not 1<=max_frames<=128:raise ValueError('Frame bound must be 1..128')
        wanted=None if identities is None else {(int(tid),str(created)) for tid,created in identities}
        if wanted is not None and not 1<=len(wanted)<=8:raise ValueError('Select 1..8 thread lifetimes')
        with _dbghelp_lock:return self._capture(pid,expected_executable,wanted,max_frames,local_symbols)

    def _capture(self,pid,expected_executable,wanted,max_frames,local_symbols):
        k,d=self.k,self.d;process=snapshot=marker=clone=None;symbol_session=False
        flags=0x1|0x80|0x100;context_flags=0x10000b
        result=dict(pid=pid,capture_flags=flags,context_flags=context_flags,started_at=time.time(),threads=[],cleanup={},
            layout=layout(),dbghelp=dict(path=str(self.dbghelp_path),sha256=hashlib.sha256(self.dbghelp_path.read_bytes()).hexdigest()),
            symbols_resolved=False,limitations=['Snapshot/unwind observations are not statistical CPU samples.',
                'Unwind may stop early; no complete-stack claim from a false StackWalk64 result.',
                'Module identities are bounded by matching inventories before/after capture; names do not imply exclusive work.'])
        started=time.monotonic()
        try:
            process=k.OpenProcess(0x490,False,pid) # query, VM read, create-process for VA clone; no write/suspend/debug privilege.
            if not process:raise C.WinError(C.get_last_error())
            if k.GetProcessId(process)!=pid:raise RuntimeError('Process owner mismatch')
            length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
            if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)):raise C.WinError(C.get_last_error())
            result['executable']=image.value
            if Path(image.value).resolve()!=Path(expected_executable).resolve():raise RuntimeError('Executable mismatch')
            times=[W.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(process,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
            result['process_created_filetime']=str(self.ticks(times[0]))
            modules=self.modules(pid);handle=W.HANDLE()
            capture_started=time.monotonic();code=k.PssCaptureSnapshot(process,flags,context_flags,C.byref(handle))
            result['capture_returncode']=code;result['capture_seconds']=time.monotonic()-capture_started
            if code:raise C.WinError(code)
            snapshot=handle.value
            info=W.HANDLE();code=k.PssQuerySnapshot(snapshot,1,C.byref(info),C.sizeof(info))
            if code:raise C.WinError(code)
            clone=info.value
            if not clone:raise RuntimeError('Missing borrowed VA clone handle')
            if self.modules(pid)!=modules:raise RuntimeError('Module inventory changed during capture')
            result['modules']=modules
            # Empty/local paths only: ignore _NT_SYMBOL_PATH, no symbol-server URLs.
            search=str(Path(local_symbols).resolve()) if local_symbols else str(Path(__file__).resolve().parent)
            d.SymSetOptions(0x4|0x1000|0x80000|0x200) # deferred, ignore env, no prompts, fail critical errors.
            if not d.SymInitializeW(clone,search,False):raise C.WinError(C.get_last_error())
            symbol_session=True;loads=[]
            for m in modules:
                base=int(m['base'],16);C.set_last_error(0)
                actual=d.SymLoadModuleExW(clone,None,m['path'],m['name'],base,m['size'],None,0)
                loads.append(dict(name=m['name'],base=m['base'],loaded_base=hex(actual),winerror=C.get_last_error()))
            result['module_loads']=loads
            read_type=C.WINFUNCTYPE(W.BOOL,W.HANDLE,C.c_ulonglong,C.c_void_p,W.DWORD,C.POINTER(W.DWORD))
            def read_memory(h,address,buffer,size,received):
                if h!=clone:return False
                count=C.c_size_t();ok=k.ReadProcessMemory(clone,C.c_void_p(address),buffer,size,C.byref(count))
                if received:received[0]=count.value
                return bool(ok)
            read=read_type(read_memory)
            handle=W.HANDLE();code=k.PssWalkMarkerCreate(None,C.byref(handle))
            if code:raise C.WinError(code)
            marker=handle.value;seen=set();count=0
            for _ in range(4097):
                entry=self.Entry();code=k.PssWalkSnapshot(snapshot,3,marker,C.byref(entry),C.sizeof(entry))
                if code==259:break
                if code:raise C.WinError(code)
                count+=1
                if count>4096:raise RuntimeError('Thread inventory bound reached')
                if entry.ProcessId!=pid:raise RuntimeError('Thread owner mismatch')
                key=(entry.ThreadId,str(self.ticks(entry.CreateTime)))
                if key in seen:raise RuntimeError('Duplicate thread lifetime')
                seen.add(key)
                if wanted is not None and key not in wanted:continue
                if wanted is None and len(result['threads'])>=8:continue
                row=dict(tid=key[0],created_filetime=key[1],capture_filetime=str(self.ticks(entry.CaptureTime)),
                    context_bytes=entry.SizeOfContextRecord,frames=[])
                result['threads'].append(row)
                if not entry.ContextRecord or not 256<=entry.SizeOfContextRecord<=16384:
                    row['error']='Captured context unavailable';continue
                storage=C.create_string_buffer(entry.SizeOfContextRecord+16);address=(C.addressof(storage)+15)&~15
                C.memmove(address,entry.ContextRecord,entry.SizeOfContextRecord);context=ContextHead.from_address(address)
                if context.ContextFlags&0x100003!=0x100003:row['error']='Missing AMD64 control/integer context';continue
                frame=StackFrame()
                frame.AddrPC.Offset=context.Rip;frame.AddrStack.Offset=context.Rsp;frame.AddrFrame.Offset=context.Rbp
                for value in (frame.AddrPC,frame.AddrStack,frame.AddrFrame):value.Mode=3
                used=set();first=True
                for index in range(max_frames):
                    pc,sp=frame.AddrPC.Offset,frame.AddrStack.Offset
                    if not pc:row['stop']='zero_pc';break
                    if not 0<pc<2**47 or not 0<sp<2**47:row['stop']='invalid_user_address';break
                    if (pc,sp) in used:row['stop']='repeated_pc_sp';break
                    region=MemoryRegion()
                    if (not k.VirtualQueryEx(clone,C.c_void_p(pc),C.byref(region),C.sizeof(region)) or
                        region.State!=0x1000 or not region.Protect&0xf0 or region.Protect&0x100):
                        row['stop']='pc_not_in_captured_executable_memory';break
                    if row['frames'] and sp<=int(row['frames'][-1]['sp'],16):row['stop']='nonincreasing_stack_pointer';break
                    used.add((pc,sp));row['frames'].append(dict(pc=hex(pc),sp=hex(sp),module=locate_module(pc,modules),
                        memory_protection=hex(region.Protect),memory_type=hex(region.Type)))
                    ok=d.StackWalk64(0x8664,clone,W.HANDLE(entry.ThreadId),C.byref(frame),C.c_void_p(address),read,
                        d.SymFunctionTableAccess64,d.SymGetModuleBase64,None)
                    if not ok:row['stop']='unwind_stopped_unknown';break
                    if first and (frame.AddrPC.Offset,frame.AddrStack.Offset)==(pc,sp):
                        # Some providers initially return the seeded frame; consume it once.
                        ok=d.StackWalk64(0x8664,clone,W.HANDLE(entry.ThreadId),C.byref(frame),C.c_void_p(address),read,
                            d.SymFunctionTableAccess64,d.SymGetModuleBase64,None)
                        if not ok:row['stop']='unwind_stopped_unknown';break
                    first=False
                else:row['stop']='frame_limit'
                row['truncated']=row['stop']=='frame_limit'
            result['thread_inventory_count']=count
            result['missing_requested_lifetimes']=[dict(tid=t,created_filetime=c) for t,c in sorted((wanted or set())-seen)]
            result['completed']=True
        except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),winerror=getattr(e,'winerror',None))
        finally:
            if symbol_session:result['cleanup']['symbol_handler_closed']=bool(d.SymCleanup(clone))
            if marker:result['cleanup']['marker_free_returncode']=int(k.PssWalkMarkerFree(marker))
            if snapshot:result['cleanup']['snapshot_free_returncode']=int(k.PssFreeSnapshot(k.GetCurrentProcess(),snapshot))
            if process:result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
            result['cleanup_verified']=all(v==0 if key.endswith('returncode') else v is True for key,v in result['cleanup'].items())
            result['finished_at']=time.time();result['elapsed_seconds']=time.monotonic()-started
        return result
