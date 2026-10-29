import pytest
from session_budget import require_session_budget


@pytest.mark.parametrize('cfg', [{}, {'session_until': None}])
def test_cancelled_deadline_allows_bounded_work(cfg):
    require_session_budget(cfg, 400, wall_clock=lambda: 1793225800)


def test_budget_keeps_explicit_cutoff_and_reserve():
    require_session_budget({'session_until': 1000}, 399, wall_clock=lambda: 600)
    for remaining in (400, 401):
        with pytest.raises(RuntimeError, match='cutoff'):
            require_session_budget({'session_until': 1000}, remaining, wall_clock=lambda: 600)
    with pytest.raises(RuntimeError, match='cutoff'):
        require_session_budget({'session_until': 1000}, 0, wall_clock=lambda: 1001)


@pytest.mark.parametrize('deadline', [True, '1000', 0, -1, float('nan'), float('inf')])
def test_malformed_deadline_never_disables_cutoff(deadline):
    with pytest.raises(ValueError, match='deadline'):
        require_session_budget({'session_until': deadline}, 10)


@pytest.mark.parametrize('seconds', [True, '10', -1, float('nan'), float('inf')])
def test_malformed_duration_rejected_even_without_cutoff(seconds):
    with pytest.raises(ValueError, match='duration'):
        require_session_budget({'session_until': None}, seconds)
