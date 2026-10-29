"""Current RIP observations from PSS contexts, without cloning memory/unwinding.

This is not a call stack or time-weighted CPU profile. PSS-owned context records
are copied before freeing the snapshot. No thread suspension API or hook added.
"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import time
from thread_metadata import WindowsThreadMetadata,locate_module
from stack_snapshot import ContextHead


class WindowsInstructionSnapshot(WindowsThreadMetadata):
    def capture(self,pid,expected_executable,identities):
        if not isinstance(pid,int) or isinstance(pid,bool) or pid<=0:raise ValueError('Invalid PID')
        wanted=set()
        for tid,created in identities:
            if isinstance(tid,bool) or not isinstance(tid,int) or not 0<tid<=0xffffffff:
                raise ValueError('Invalid thread ID')
            if not isinstance(created,str) or not created.isascii() or not created.isdecimal() or not 0<int(created)<2**64:
                raise ValueError('Invalid exact creation FILETIME')
            if (tid,created) in wanted:raise ValueError('Duplicate thread lifetime')
            wanted.add((tid,created))
        if not 1<=len(wanted)<=8:raise ValueError('Select 1..8 lifetimes')
        k=self.k;process=snapshot=marker=None;started=time.perf_counter()
        result=dict(pid=pid,capture_flags=0x180,context_flags=0x100003,started_at=time.time(),threads=[],cleanup={},
            scope='Captured user RIP/register addresses only; not a stack, CPU attribution fraction or complete execution coverage.')
        try:
            process=k.OpenProcess(0x400,False,pid)
            if not process:raise C.WinError(C.get_last_error())
            if k.GetProcessId(process)!=pid:raise RuntimeError('Process owner mismatch')
            length=W.DWORD(32768);image=C.create_unicode_buffer(length.value)
            if not k.QueryFullProcessImageNameW(process,0,image,C.byref(length)):raise C.WinError(C.get_last_error())
            result['executable']=image.value
            if Path(image.value).resolve()!=Path(expected_executable).resolve():raise RuntimeError('Executable mismatch')
            times=[W.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(process,*[C.byref(t) for t in times]):raise C.WinError(C.get_last_error())
            result['process_created_filetime']=str(self.ticks(times[0]))
            modules=self.modules(pid);handle=W.HANDLE();t=time.perf_counter()
            code=k.PssCaptureSnapshot(process,0x180,0x100003,C.byref(handle))
            result['capture_returncode']=code;result['capture_seconds']=time.perf_counter()-t
            if code:raise C.WinError(code)
            snapshot=handle.value
            if self.modules(pid)!=modules:raise RuntimeError('Module inventory changed during snapshot')
            result['modules']=modules
            handle=W.HANDLE();code=k.PssWalkMarkerCreate(None,C.byref(handle))
            if code:raise C.WinError(code)
            marker=handle.value;seen=set();count=0
            for _ in range(4097):
                entry=self.Entry();code=k.PssWalkSnapshot(snapshot,3,marker,C.byref(entry),C.sizeof(entry))
                if code==259:break
                if code:raise C.WinError(code)
                count+=1
                if count>4096:raise RuntimeError('Thread inventory bound reached')
                if entry.ProcessId!=pid:raise RuntimeError('Thread process differs')
                key=(entry.ThreadId,str(self.ticks(entry.CreateTime)))
                if key in seen:raise RuntimeError('Duplicate captured thread lifetime')
                seen.add(key)
                if key not in wanted:continue
                row=dict(tid=key[0],created_filetime=key[1],capture_filetime=str(self.ticks(entry.CaptureTime)),
                    context_bytes=entry.SizeOfContextRecord)
                result['threads'].append(row)
                if not entry.ContextRecord or not 256<=entry.SizeOfContextRecord<=16384:
                    row['error']='Captured control/integer context unavailable';continue
                context=ContextHead.from_buffer_copy(C.string_at(entry.ContextRecord,C.sizeof(ContextHead)))
                if context.ContextFlags&0x100003!=0x100003:
                    row['error']='Missing AMD64 control/integer flags';continue
                row.update(rip=hex(context.Rip),rsp=hex(context.Rsp),rbp=hex(context.Rbp),
                    module=locate_module(context.Rip,modules),context_flags=int(context.ContextFlags))
            result['thread_inventory_count']=count
            result['missing_requested_lifetimes']=[dict(tid=t,created_filetime=c) for t,c in sorted(wanted-seen)]
            result['completed']=True
        except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e),winerror=getattr(e,'winerror',None))
        finally:
            if marker:result['cleanup']['marker_free_returncode']=int(k.PssWalkMarkerFree(marker))
            if snapshot:result['cleanup']['snapshot_free_returncode']=int(k.PssFreeSnapshot(k.GetCurrentProcess(),snapshot))
            if process:result['cleanup']['process_handle_closed']=bool(k.CloseHandle(process))
            result['cleanup_verified']=all(v==0 if key.endswith('returncode') else v is True for key,v in result['cleanup'].items())
            result['finished_at']=time.time();result['elapsed_seconds']=time.perf_counter()-started
        return result
