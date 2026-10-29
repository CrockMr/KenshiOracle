"""Historical physics validator, sharing the bounded call-bucket contract."""

import _research_bootstrap  # Repository-relative imports for direct execution.
from call_diagnostics import validate as validate_buckets


def validate(stats):
    systems=stats.get('systems',{})
    if systems.get('physics_backThreadUpdate') is not None and systems.get('charsUpdateUT_mean_ms') is not None:
        raise ValueError('Physics and retired charsUpdateUT telemetry both present')
    return validate_buckets(stats,'physics_backThreadUpdate')
