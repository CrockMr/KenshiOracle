"""Read-only Windows thread CPU snapshots, with owner and creation identity.

No thread is suspended or changed. Each query handle is closed immediately.
Missing endpoints remain unaccounted rather than inventing lifetime CPU deltas.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import os
import time
from collections import Counter


class WindowsThreadSampler:
    def __init__(self, pid, clock=time.monotonic):
        if os.name != 'nt':
            raise RuntimeError('Windows thread CPU sampling requires Windows')
        import ctypes
        from ctypes import wintypes
        import psutil
        self.pid, self.clock, self.ctypes, self.FILETIME = pid, clock, ctypes, wintypes.FILETIME
        self.process = psutil.Process
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenThread.restype = wintypes.HANDLE
        kernel.GetProcessIdOfThread.argtypes = (wintypes.HANDLE,)
        kernel.GetProcessIdOfThread.restype = wintypes.DWORD
        kernel.GetThreadTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),)*4
        kernel.GetThreadTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel

    @staticmethod
    def ticks(value):
        return (value.dwHighDateTime << 32) | value.dwLowDateTime

    def __call__(self):
        started = self.clock()
        threads = self.process(self.pid).threads()
        rows = []
        for thread in threads[:4096]:
            row = dict(tid=thread.id)
            rows.append(row)
            handle = self.kernel.OpenThread(0x0800, False, thread.id)  # QUERY_LIMITED_INFORMATION
            if not handle:
                row.update(error='open_thread', winerror=self.ctypes.get_last_error())
                continue
            try:
                owner = self.kernel.GetProcessIdOfThread(handle)
                if owner != self.pid:
                    row.update(error='owner_mismatch', observed_owner_pid=owner)
                    continue
                creation, exited, kernel, user = (self.FILETIME() for _ in range(4))
                if not self.kernel.GetThreadTimes(handle, self.ctypes.byref(creation), self.ctypes.byref(exited),
                        self.ctypes.byref(kernel), self.ctypes.byref(user)):
                    row.update(error='get_thread_times', winerror=self.ctypes.get_last_error())
                    continue
                row.update(created_filetime=str(self.ticks(creation)),
                    user_100ns=self.ticks(user), kernel_100ns=self.ticks(kernel),
                    observed_monotonic_seconds=self.clock())
                # Exit FILETIME is undefined for a live thread; do not interpret it.
            finally:
                self.kernel.CloseHandle(handle)
        finished = self.clock()
        return dict(started_monotonic_seconds=started, finished_monotonic_seconds=finished,
                    collection_seconds=finished-started, enumerated_count=len(threads),
                    truncated=len(threads)>len(rows), threads=rows)


def thread_deltas(before, after, process_elapsed, process_cpu_seconds):
    old = {row['tid']: row for row in before['threads']}
    new = {row['tid']: row for row in after['threads']}
    if len(old) != len(before['threads']) or len(new) != len(after['threads']):
        raise ValueError('Duplicate thread IDs in a single snapshot')
    rows = []
    omitted = []
    for tid in sorted(old.keys() | new.keys()):
        a, b = old.get(tid), new.get(tid)
        reason = None
        if a is None:
            reason = 'not_observed_before'
        elif b is None:
            reason = 'not_observed_after'
        elif a.get('error') or b.get('error'):
            reason = 'query_unavailable'
        elif not a.get('created_filetime') or not b.get('created_filetime'):
            reason = 'creation_identity_missing'
        elif a['created_filetime'] != b['created_filetime']:
            reason = 'tid_reused'
        if reason:
            omitted.append(dict(tid=tid, reason=reason))
            continue
        user = (b['user_100ns']-a['user_100ns'])*1e-7
        kernel = (b['kernel_100ns']-a['kernel_100ns'])*1e-7
        elapsed = b['observed_monotonic_seconds']-a['observed_monotonic_seconds']
        if user < 0 or kernel < 0 or elapsed <= 0:
            omitted.append(dict(tid=tid, reason='counter_or_interval_invalid'))
            continue
        cpu = user+kernel
        rows.append(dict(tid=tid, created_filetime=a['created_filetime'], user_seconds=user,
            kernel_seconds=kernel, cpu_seconds=cpu, elapsed_seconds=elapsed,
            logical_cpu_equivalents=cpu/elapsed,
            process_cpu_fraction=cpu/process_cpu_seconds if process_cpu_seconds>0 else None))
    total = sum(row['cpu_seconds'] for row in rows)
    return dict(threads=sorted(rows, key=lambda row: row['cpu_seconds'], reverse=True), omitted=omitted,
        omitted_reasons=dict(Counter(row['reason'] for row in omitted)),
        covered_cpu_seconds=total, covered_logical_cpu_equivalents=total/process_elapsed,
        process_cpu_seconds=process_cpu_seconds, residual_cpu_seconds=process_cpu_seconds-total,
        limits=['Endpoint samples are sequential, not atomic; process and thread intervals differ slightly.',
                'Threads without both matching creation identities are excluded; residual is not assigned to a subsystem.',
                'Counters are quantized; do not clamp a negative residual or infer zero execution from a zero delta.',
                'A thread observed executing a subsystem can also execute other work.'])


def assign_roles(thread_cpu, game_ids, renderer_ids, navigation_ids):
    """One accounting group per thread; role labels can overlap without double count."""
    groups = Counter()
    for row in thread_cpu['threads']:
        tid = row['tid']
        roles = []
        if tid in game_ids:
            roles.append('game_thread')
        if tid in renderer_ids:
            roles.append('renderer_service_thread')
        if tid in navigation_ids:
            roles.append('observed_navigation_thread')
        row['observed_roles'] = roles
        group = ('game_thread' if tid in game_ids else 'observed_navigation_thread'
                 if tid in navigation_ids else 'other_threads')
        row['accounting_group'] = group
        groups[group] += row['cpu_seconds']
    thread_cpu['accounting_group_cpu_seconds'] = dict(groups)
    thread_cpu['role_evidence'] = dict(game_thread_ids=sorted(game_ids), renderer_thread_ids=sorted(renderer_ids),
        navigation_thread_ids=sorted(navigation_ids),
        note='Navigation identity is observed in retained calls; CPU of that whole thread is not exclusive findPath CPU.')
    return thread_cpu
