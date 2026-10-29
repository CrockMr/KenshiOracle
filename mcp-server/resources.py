"""Read-only OS process CPU interval, with executable and creation-time checks."""

from research_support import enable_research
enable_research()
import time
from pathlib import Path


class ProcessResources:
    def __init__(self, pid, executable, process_factory=None, logical_cpus=None, clock=time.monotonic,
                 sample_threads=False, thread_sampler=None):
        if process_factory is None:
            import psutil  # Optional developer dependency; no import required by the MCP server.
            process_factory = psutil.Process
            logical_cpus = psutil.cpu_count()
        self.pid, self.executable = pid, str(Path(executable).resolve()).casefold()
        self.factory, self.clock = process_factory, clock
        self.logical_cpus = logical_cpus
        self.thread_sampler = thread_sampler
        if sample_threads and self.thread_sampler is None:
            from thread_resources import WindowsThreadSampler
            self.thread_sampler = WindowsThreadSampler(pid, clock)
        self.before = self.snapshot()

    def snapshot(self):
        process = self.factory(self.pid)  # Fresh object also detects a reused PID.
        actual = str(Path(process.exe()).resolve()).casefold()
        if actual != self.executable:
            raise RuntimeError('CPU measurement process executable mismatch')
        cpu = process.cpu_times()
        result = dict(monotonic_seconds=self.clock(), created_at=process.create_time(),
                    user_seconds=cpu.user, system_seconds=cpu.system,
                    rss_bytes=process.memory_info().rss, threads=process.num_threads())
        if self.thread_sampler is not None:
            result['thread_snapshot'] = self.thread_sampler()
        return result

    def finish(self):
        after = self.snapshot()
        before = self.before
        if after['created_at'] != before['created_at']:
            raise RuntimeError('CPU measurement process identity changed')
        wall = after['monotonic_seconds']-before['monotonic_seconds']
        user = after['user_seconds']-before['user_seconds']
        system = after['system_seconds']-before['system_seconds']
        if wall <= 0 or user < 0 or system < 0:
            raise RuntimeError('CPU measurement interval or counters invalid')
        used = (user+system)/wall
        result = dict(pid=self.pid, executable=self.executable, logical_cpus=self.logical_cpus,
                    before=before, after=after, elapsed_seconds=wall,
                    user_seconds=user, system_seconds=system,
                    logical_cpu_equivalents=used, one_cpu_percent=100*used,
                    machine_capacity_percent=100*used/self.logical_cpus if self.logical_cpus else None,
                    scope='Enclosing collection interval; all threads and modules of this game process, not per-frame or per-hook CPU')
        if self.thread_sampler is not None:
            from thread_resources import thread_deltas
            result['thread_cpu'] = thread_deltas(before['thread_snapshot'], after['thread_snapshot'], wall, user+system)
        return result
