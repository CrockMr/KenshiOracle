"""Validate the selected outermost AI function and historical periodic payloads."""
from call_diagnostics import validate as validate_buckets,match_cpu
import math


def validate(stats):
    systems=stats.get('systems',{});generic=systems.get('ai_profiled_function');legacy=systems.get('ai_periodicUpdate')
    key='ai_profiled_function' if generic is not None else 'ai_periodicUpdate'
    total=validate_buckets(stats,key)
    if total is None:return None
    name=total.get('function','AI::periodicUpdate')
    if generic is not None:
        if total.get('function') not in {'AI::periodicUpdate','AI::update4Frame'}:
            raise ValueError('Invalid selected AI function')
        if legacy is not None and (name!='AI::periodicUpdate' or legacy!=generic):
            raise ValueError('Legacy periodic alias disagrees with selected AI function')
    elif name!='AI::periodicUpdate':
        raise ValueError('Nonperiodic function under legacy periodic name')
    if systems.get('physics_backThreadUpdate') is not None or systems.get('charsUpdateUT_mean_ms') is not None:
        raise ValueError('AI periodic telemetry and retired system probe both present')
    nested=total['nested_entries_skipped_total']
    if isinstance(nested,bool) or not isinstance(nested,int) or nested<0:
        raise ValueError('Invalid AI nested entry count')
    if not isinstance(total['scope'],str) or not total['scope']:
        raise ValueError('Missing AI inclusive scope')
    if 'thread_identity_mode' in total and total['thread_identity_mode']!='tls_creation_once':
        raise ValueError('Unknown AI thread identity mode')
    return total


def function_name(stats):
    total=validate(stats)
    return total.get('function','AI::periodicUpdate') if total is not None else None

