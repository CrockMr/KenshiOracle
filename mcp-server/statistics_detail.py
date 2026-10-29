"""Distinguish explicitly omitted detail from retained rows and native truncation."""
import math


def _count(value,label,maximum=2**53):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError('Invalid '+label)
    return value


def validate(stats):
    """Return full or aggregates without changing any payload or fabricating rows."""
    if 'statistics_detail' not in stats:
        # Historical specialised fixtures may omit arrays they do not inspect.
        # Explicit null, however, cannot claim omission without provenance.
        for key in ('per_frame','navmesh_slow_calls'):
            if key in stats and not isinstance(stats[key],list):
                raise ValueError('Statistics detail missing omission metadata: '+key)
        return 'full'
    detail=stats['statistics_detail']
    if (not isinstance(detail,dict) or set(detail)!={'mode','per_frame_rows_omitted','navmesh_slow_rows_omitted'} or
            detail['mode']!='aggregates'):
        raise ValueError('Unknown statistics detail contract')
    if any(key not in stats or stats[key] is not None for key in ('per_frame','navmesh_slow_calls')):
        raise ValueError('Aggregate statistics must explicitly omit both detail arrays')
    n=_count(stats.get('count'),'retained frame count',3600)
    frame_rows=_count(detail['per_frame_rows_omitted'],'omitted frame count',100)
    slow_rows=_count(detail['navmesh_slow_rows_omitted'],'omitted slow-call count')
    if frame_rows!=min(n,100):raise ValueError('Omitted frame count contradicts native retention')
    if n==0:
        if 'mean_ms' not in stats or stats['mean_ms'] is not None or slow_rows!=0:
            raise ValueError('Empty native statistics contain measured data')
        # Empty native buffers return their historical short shape plus omission metadata.
        for key in ('first_frame','last_frame','series_truncated','navmesh_slow_calls_total',
                    'navmesh_slow_calls_capacity','navmesh_slow_calls_retention_truncated'):
            if key in stats:raise ValueError('Empty native buffer has unexpected retained-window metadata')
        return 'aggregates'
    mean=stats.get('mean_ms')
    if type(mean) not in (int,float) or not math.isfinite(mean) or mean<0:
        raise ValueError('Aggregate frame mean is unavailable')
    first=_count(stats.get('first_frame'),'first retained frame')
    last=_count(stats.get('last_frame'),'last retained frame')
    if last-first+1!=n:raise ValueError('Aggregate retained frame bounds differ')
    if type(stats.get('series_truncated')) is not bool or stats['series_truncated']!=(n>100):
        raise ValueError('Native series retention differs from omitted row count')
    total=_count(stats.get('navmesh_slow_calls_total'),'slow-call total')
    capacity=_count(stats.get('navmesh_slow_calls_capacity'),'slow-call capacity')
    if not capacity or slow_rows>min(total,capacity):
        raise ValueError('Omitted slow-call rows exceed native retention')
    truncated=stats.get('navmesh_slow_calls_retention_truncated')
    if type(truncated) is not bool or truncated!=(slow_rows<total):
        raise ValueError('Native slow-call retention contradicts omitted row count')
    return 'aggregates'


def per_frame_rows(stats):
    """Rows for optional validation only; aggregates stay null in the input/output."""
    return [] if validate(stats)=='aggregates' else stats.get('per_frame',[])


def navmesh_slow_rows(stats):
    """Rows for optional validation only; omitted calls never become observed calls."""
    return [] if validate(stats)=='aggregates' else stats['navmesh_slow_calls']
