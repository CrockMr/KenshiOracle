"""Read-only validation of the SDK ThreadClass base header.

The 24-byte prefix comes from ThreadClass.h: vptr, handle, TID, running flag.
No derived-class layout, arbitrary heap scan, handle duplication or write.
"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import struct
import time
from thread_metadata import WindowsThreadMetadata


def parse_base_header(data,tid):
    if len(data)!=24:raise ValueError('ThreadClass base prefix must contain 24 bytes')
    vptr,handle,actual_tid,running=struct.unpack_from('<QQIB',data)
    if actual_tid!=tid or not 0<tid<2**32:raise ValueError('SDK base thread ID differs')
    if not 0<vptr<2**47 or vptr%8:raise ValueError('Invalid SDK base vptr')
    if not handle or running not in (0,1):raise ValueError('Invalid SDK base handle/running metadata')
    return dict(vptr=hex(vptr),target_handle_value=hex(handle),thread_id=actual_tid,running=bool(running))


def read_base(pid,expected_executable,process_created_filetime,tid,created_filetime,address):
    if type(address) is not int or address%8 or not 0<address<2**47-24:raise ValueError('Invalid SDK base address')
    provider=WindowsThreadMetadata();k=provider.k
    k.OpenThread.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenThread.restype=W.HANDLE
    k.GetThreadId.argtypes=[W.HANDLE];k.GetThreadId.restype=W.DWORD
    k.GetProcessIdOfThread.argtypes=[W.HANDLE];k.GetProcessIdOfThread.restype=W.DWORD
    k.GetThreadTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4;k.GetThreadTimes.restype=W.BOOL
    k.GetExitCodeThread.argtypes=[W.HANDLE,C.POINTER(W.DWORD)];k.GetExitCodeThread.restype=W.BOOL
    k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
    process=None;thread=None;result=dict(pid=pid,tid=tid,created_filetime=created_filetime,address=hex(address),observed_at=time.time(),verified=False,cleanup={})
    def read():
        data=C.create_string_buffer(24);count=C.c_size_t()
        if not k.ReadProcessMemory(process,C.c_void_p(address),data,24,C.byref(count)):raise C.WinError(C.get_last_error())
        if count.value!=24:raise RuntimeError('Short SDK base prefix read')
        return data.raw
    def lifetime():
        times=[W.FILETIME() for _ in range(4)];code=W.DWORD()
        if k.GetThreadId(thread)!=tid or k.GetProcessIdOfThread(thread)!=pid:raise RuntimeError('Thread owner differs')
        if not k.GetThreadTimes(thread,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
        if str(provider.ticks(times[0]))!=created_filetime:raise RuntimeError('Thread creation differs')
        if not k.GetExitCodeThread(thread,C.byref(code)):raise C.WinError(C.get_last_error())
        if code.value!=259:raise RuntimeError('Thread no longer active')
    try:
        process=k.OpenProcess(0x410,False,pid)
        if not process:raise C.WinError(C.get_last_error())
        if k.GetProcessId(process)!=pid:raise RuntimeError('Process owner differs')
        length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
        if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)):raise C.WinError(C.get_last_error())
        if Path(image.value).resolve()!=Path(expected_executable).resolve():raise RuntimeError('Game executable differs')
        times=[W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(process,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
        if str(provider.ticks(times[0]))!=process_created_filetime:raise RuntimeError('Process creation differs')
        thread=k.OpenThread(0x800,False,tid)
        if not thread:raise C.WinError(C.get_last_error())
        lifetime();first=read();a=parse_base_header(first,tid)
        second=read();b=parse_base_header(second,tid);lifetime()
        if first[:20]!=second[:20]:raise RuntimeError('SDK base identity changed during reads')
        result.update(verified=True,base_header=a,second_base_header=b,base_header_hex=first.hex(),identity_bytes_stable=True,
            scope='Read-only candidate validation; target handle is only a numeric field, not an independent lifetime proof.')
    except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),winerror=getattr(e,'winerror',None))
    finally:
        if thread:result['cleanup']['thread_handle_closed']=bool(k.CloseHandle(thread))
        if process:result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
        result['cleanup_verified']=all(result['cleanup'].values())
    return result
