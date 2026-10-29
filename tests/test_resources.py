from types import SimpleNamespace
import pytest
from resources import ProcessResources


class Process:
    created = 10
    user = 1
    system = 2

    def exe(self): return 'fake-game.exe'
    def create_time(self): return self.created
    def cpu_times(self): return SimpleNamespace(user=self.user, system=self.system)
    def memory_info(self): return SimpleNamespace(rss=1234)
    def num_threads(self): return 8


def sampler():
    process = Process()
    ticks = iter([100, 102])
    return ProcessResources(42, 'fake-game.exe', lambda pid: process, 8, lambda: next(ticks)), process


def test_process_cpu_can_exceed_one_logical_cpu():
    resources, process = sampler()
    process.user, process.system = 3, 3
    data = resources.finish()
    assert data['one_cpu_percent'] == 150
    assert data['machine_capacity_percent'] == 18.75
    assert data['logical_cpu_equivalents'] == 1.5


def test_reused_pid_is_rejected():
    resources, process = sampler()
    process.created = 11
    with pytest.raises(RuntimeError, match='identity changed'):
        resources.finish()


def test_wrong_executable_is_rejected():
    with pytest.raises(RuntimeError, match='executable mismatch'):
        ProcessResources(42, 'different.exe', lambda pid: Process(), 8)


def test_optional_thread_sampling_reports_unassigned_process_cpu():
    process = Process()
    def thread(user, observed):
        return dict(threads=[dict(tid=7, created_filetime='123', user_100ns=user,
            kernel_100ns=0, observed_monotonic_seconds=observed)])
    snapshots = iter([thread(0,100), thread(20000000,102)])
    ticks = iter([100,102])
    resources = ProcessResources(42, 'fake-game.exe', lambda pid: process, 8,
        lambda: next(ticks), thread_sampler=lambda: next(snapshots))
    process.user, process.system = 3, 3
    result = resources.finish()
    assert result['thread_cpu']['covered_cpu_seconds'] == 2
    assert result['thread_cpu']['residual_cpu_seconds'] == 1
