from types import SimpleNamespace
import pytest
from thread_resources import WindowsThreadSampler, thread_deltas, assign_roles


def row(tid=7, created='134000000000000001', user=0, kernel=0, observed=0):
    return dict(tid=tid, created_filetime=created, user_100ns=user, kernel_100ns=kernel,
                observed_monotonic_seconds=observed)


def snapshot(*rows):
    return dict(threads=list(rows))


def test_tid_reuse_does_not_become_cpu_of_the_old_thread():
    result = thread_deltas(snapshot(row(user=10)), snapshot(row(created='134000000000000002', user=500, observed=2)), 2, 1)
    assert not result['threads']
    assert result['omitted_reasons'] == {'tid_reused': 1}


def test_renderer_and_game_role_overlap_does_not_double_count():
    result = thread_deltas(snapshot(row()), snapshot(row(user=10000000, observed=2)), 2, 1)
    assign_roles(result, {7}, {7}, set())
    assert result['accounting_group_cpu_seconds'] == {'game_thread': 1}
    assert result['threads'][0]['observed_roles'] == ['game_thread', 'renderer_service_thread']


def test_missing_endpoint_is_not_treated_as_zero_start_cpu():
    result = thread_deltas(snapshot(row()), snapshot(row(tid=8, user=10000000, observed=2)), 2, 1)
    assert not result['threads']
    assert result['omitted_reasons'] == {'not_observed_after': 1, 'not_observed_before': 1}


def test_negative_residual_is_preserved_for_nonatomic_quantized_snapshots():
    result = thread_deltas(snapshot(row()), snapshot(row(user=11000000, observed=2)), 2, 1)
    assert result['residual_cpu_seconds'] == pytest.approx(-.1)


def test_counter_regression_is_excluded_instead_of_clamped():
    result = thread_deltas(snapshot(row(user=10)), snapshot(row(user=5, observed=2)), 2, 1)
    assert result['omitted_reasons'] == {'counter_or_interval_invalid': 1}


@pytest.mark.parametrize('owner,query', [(42, False), (99, True)])
def test_windows_query_handle_is_closed_on_failure(owner, query):
    sampler = object.__new__(WindowsThreadSampler)
    sampler.pid = 42
    ticks = iter([0,1])
    sampler.clock = lambda: next(ticks)
    sampler.process = lambda pid: SimpleNamespace(threads=lambda: [SimpleNamespace(id=7)])
    sampler.FILETIME = lambda: None
    sampler.ctypes = SimpleNamespace(byref=lambda value: value, get_last_error=lambda: 5)
    closed = []
    sampler.kernel = SimpleNamespace(OpenThread=lambda *args: 123,
        GetProcessIdOfThread=lambda handle: owner, GetThreadTimes=lambda *args: query,
        CloseHandle=lambda handle: closed.append(handle))
    result = sampler()
    assert closed == [123]
    assert result['threads'][0]['error'] in ('owner_mismatch', 'get_thread_times')


def test_duplicate_snapshot_thread_identity_is_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        thread_deltas(snapshot(row(),row()), snapshot(row(observed=2)), 2, 1)
