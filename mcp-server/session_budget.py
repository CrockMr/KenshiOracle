"""Optional wall-clock cutoff for bounded live experiments."""
import math
import time


def require_session_budget(cfg, required_seconds, *, wall_clock=time.time):
    if (isinstance(required_seconds, bool) or not isinstance(required_seconds, (int, float))
            or not math.isfinite(required_seconds) or required_seconds < 0):
        raise ValueError('Invalid required session duration')
    deadline = cfg.get('session_until')
    if deadline is None:
        return
    if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
            or not math.isfinite(deadline) or deadline <= 0):
        raise ValueError('Invalid session deadline')
    if wall_clock() + required_seconds >= deadline:
        raise RuntimeError('Insufficient time before reserved session cutoff')
