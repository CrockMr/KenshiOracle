"""Windows thread start metadata only; never a current stack or CPU sample.

PSS_CAPTURE_THREADS=0x80, context flags zero, no clone/context/VA capture. A
local snapshot is freed with the current-process pseudo handle, not the target.
Declarations verified against Windows SDK 10.0.26100.0 ProcessSnapshot.h and
TlHelp32.h. No module bytes, reserved fields or context pointers are read.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import os
from pathlib import Path
import time


def locate_module(address,modules):
    if address is None: return None
    matches=[m for m in modules if int(m['base'],16)<=address<int(m['base'],16)+m['size']]
    if len(matches)>1: raise ValueError('Overlapping module ranges')
    if not matches: return None
    m=matches[0]
    return dict(name=m['name'],path=m['path'],offset=hex(address-int(m['base'],16)))


class WindowsThreadMetadata:
    def __init__(self):
        if os.name!='nt': raise RuntimeError('Windows metadata requires Windows')
        import ctypes as C
        from ctypes import wintypes as W
        if C.sizeof(C.c_void_p)!=8: raise RuntimeError('Requires an x64 helper')
        self.C,self.W=C,W
        class Entry(C.Structure):
            _fields_=[('ExitStatus',W.DWORD),('TebBaseAddress',C.c_void_p),
                ('ProcessId',W.DWORD),('ThreadId',W.DWORD),('AffinityMask',C.c_size_t),
                ('Priority',C.c_int),('BasePriority',C.c_int),('LastSyscallFirstArgument',C.c_void_p),
                ('LastSyscallNumber',W.WORD),('CreateTime',W.FILETIME),('ExitTime',W.FILETIME),
                ('KernelTime',W.FILETIME),('UserTime',W.FILETIME),('Win32StartAddress',C.c_void_p),
                ('CaptureTime',W.FILETIME),('Flags',C.c_int),('SuspendCount',W.WORD),
                ('SizeOfContextRecord',W.WORD),('ContextRecord',C.c_void_p)]
        class Module(C.Structure):
            _fields_=[('dwSize',W.DWORD),('th32ModuleID',W.DWORD),('th32ProcessID',W.DWORD),
                ('GlblcntUsage',W.DWORD),('ProccntUsage',W.DWORD),('modBaseAddr',C.c_void_p),
                ('modBaseSize',W.DWORD),('hModule',W.HMODULE),('szModule',W.WCHAR*256),('szExePath',W.WCHAR*260)]
        if C.sizeof(Entry)!=120 or Entry.Win32StartAddress.offset!=88 or C.sizeof(Module)!=1080:
            raise RuntimeError('Unexpected x64 Windows structure layout')
        self.Entry,self.Module=Entry,Module
        k=C.WinDLL('kernel32',use_last_error=True)
        signatures={
            'OpenProcess':([W.DWORD,W.BOOL,W.DWORD],W.HANDLE),
            'GetProcessId':([W.HANDLE],W.DWORD),
            'QueryFullProcessImageNameW':([W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)],W.BOOL),
            'GetProcessTimes':([W.HANDLE]+[C.POINTER(W.FILETIME)]*4,W.BOOL),
            'GetCurrentProcess':([],W.HANDLE),'CloseHandle':([W.HANDLE],W.BOOL),
            'PssCaptureSnapshot':([W.HANDLE,W.DWORD,W.DWORD,C.POINTER(W.HANDLE)],W.DWORD),
            'PssFreeSnapshot':([W.HANDLE,W.HANDLE],W.DWORD),
            'PssWalkMarkerCreate':([C.c_void_p,C.POINTER(W.HANDLE)],W.DWORD),
            'PssWalkMarkerFree':([W.HANDLE],W.DWORD),
            'PssWalkSnapshot':([W.HANDLE,C.c_int,W.HANDLE,C.c_void_p,W.DWORD],W.DWORD),
            'CreateToolhelp32Snapshot':([W.DWORD,W.DWORD],W.HANDLE),
            'Module32FirstW':([W.HANDLE,C.POINTER(Module)],W.BOOL),
            'Module32NextW':([W.HANDLE,C.POINTER(Module)],W.BOOL)}
        for name,(args,result) in signatures.items():
            function=getattr(k,name);function.argtypes=args;function.restype=result
        self.k=k

    @staticmethod
    def ticks(value): return (value.dwHighDateTime<<32)|value.dwLowDateTime

    def modules(self,pid):
        C,W,k=self.C,self.W,self.k
        snapshot=k.CreateToolhelp32Snapshot(0x18,pid) # modules only, including 32-bit modules
        if snapshot==C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
        rows=[]
        try:
            entry=self.Module();entry.dwSize=C.sizeof(entry)
            ok=k.Module32FirstW(snapshot,C.byref(entry))
            while ok:
                if entry.th32ProcessID!=pid: raise RuntimeError('Module owner mismatch')
                rows.append(dict(name=entry.szModule,path=entry.szExePath,base=hex(entry.modBaseAddr or 0),size=entry.modBaseSize))
                if len(rows)>=4096: raise RuntimeError('Module inventory bound reached')
                ok=k.Module32NextW(snapshot,C.byref(entry))
            if C.get_last_error()!=18: raise C.WinError(C.get_last_error())
            return rows
        finally:
            if not k.CloseHandle(snapshot): raise C.WinError(C.get_last_error())

    def capture(self,pid,expected_executable):
        C,W,k=self.C,self.W,self.k
        result=dict(pid=pid,capture_flags=0x80,context_flags=0,threads=[],cleanup={},
                    started_at=time.time(),entry_size=C.sizeof(self.Entry),module_entry_size=C.sizeof(self.Module))
        process=snapshot=marker=None
        try:
            process=k.OpenProcess(0x0400,False,pid) # PROCESS_QUERY_INFORMATION only
            if not process: raise C.WinError(C.get_last_error())
            if k.GetProcessId(process)!=pid: raise RuntimeError('Process owner mismatch')
            length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
            if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)): raise C.WinError(C.get_last_error())
            if Path(image.value).resolve()!=Path(expected_executable).resolve(): raise RuntimeError('Executable mismatch')
            result['executable']=image.value
            created,exited,kernel,user=(W.FILETIME() for _ in range(4))
            if not k.GetProcessTimes(process,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)):
                raise C.WinError(C.get_last_error())
            result['process_created_filetime']=str(self.ticks(created))
            handle=W.HANDLE();code=k.PssCaptureSnapshot(process,0x80,0,C.byref(handle))
            result['capture_returncode']=code
            if code: raise C.WinError(code)
            snapshot=handle.value
            handle=W.HANDLE();code=k.PssWalkMarkerCreate(None,C.byref(handle))
            if code: raise C.WinError(code)
            marker=handle.value
            for _ in range(4097):
                entry=self.Entry();code=k.PssWalkSnapshot(snapshot,3,marker,C.byref(entry),C.sizeof(entry))
                if code==259: break # ERROR_NO_MORE_ITEMS
                if code: raise C.WinError(code)
                if len(result['threads'])>=4096: raise RuntimeError('Thread inventory bound reached')
                if entry.ProcessId!=pid: raise RuntimeError('Thread owner mismatch')
                if entry.SizeOfContextRecord or entry.ContextRecord:
                    raise RuntimeError('Unexpected context data; metadata-only capture refused')
                result['threads'].append(dict(tid=entry.ThreadId,created_filetime=str(self.ticks(entry.CreateTime)),
                    win32_start_address=hex(entry.Win32StartAddress) if entry.Win32StartAddress else None,
                    priority=entry.Priority,base_priority=entry.BasePriority,flags=entry.Flags,
                    suspend_count_observed=entry.SuspendCount,capture_filetime=str(self.ticks(entry.CaptureTime))))
            result['modules']=self.modules(pid)
            for row in result['threads']:
                address=row['win32_start_address']
                row['start_module']=locate_module(int(address,16) if address else None,result['modules'])
            result['completed']=True
        except Exception as exc:
            result['error']=dict(type=type(exc).__name__,message=str(exc),winerror=getattr(exc,'winerror',None))
        finally:
            if marker: result['cleanup']['marker_free_returncode']=int(k.PssWalkMarkerFree(marker))
            # PSS descriptor lives in this helper, even when capturing a remote target.
            if snapshot: result['cleanup']['snapshot_free_returncode']=int(k.PssFreeSnapshot(k.GetCurrentProcess(),snapshot))
            if process: result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
            result['cleanup_verified']=all(v==0 if key.endswith('returncode') else v is True for key,v in result['cleanup'].items())
            result['finished_at']=time.time()
        return result
