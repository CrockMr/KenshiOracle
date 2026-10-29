from copy import deepcopy
import pytest
from ai_diagnostics import validate,match_cpu,function_name
from test_physics_diagnostics import stats as physics_stats


def stats():
    s=physics_stats();p=s['systems'].pop('physics_backThreadUpdate')
    p.update(nested_entries_skipped_total=2,scope='Completed outermost calls, inclusive')
    s['systems'].update(ai_periodicUpdate=p,physics_backThreadUpdate=None)
    return s


def test_ai_partial_cpu_reconciles_and_nested_entries_are_separate():
    p=validate(stats());assert p['calls_total']==6 and p['nested_entries_skipped_total']==2
    assert p['cpu_available_calls']==5 and p['threads_truncated']
    assert p['threads'][0]['cpu_user_total_ms']>p['threads'][0]['mean_ms']*10
    assert validate(dict(systems={})) is None


@pytest.mark.parametrize('field,value',[('nested_entries_skipped_total',-1),('nested_entries_skipped_total',True),('scope','')])
def test_invalid_ai_scope_or_nested_entries_rejected(field,value):
    s=stats();s['systems']['ai_periodicUpdate'][field]=value
    with pytest.raises(ValueError):validate(s)


@pytest.mark.parametrize('old',['physics_backThreadUpdate','charsUpdateUT_mean_ms'])
def test_retired_system_probe_cannot_coexist_with_ai(old):
    s=stats();s['systems'][old]=0
    with pytest.raises(ValueError):validate(s)


def test_ai_tid_reuse_remains_distinct_and_invalid_partition_rejected():
    s=stats();p=s['systems']['ai_periodicUpdate'];p['threads'][1]['thread_id']=7
    assert validate(s)['threads'][1]['created_filetime']=='200'
    p['unlisted']['calls_total']+=1
    with pytest.raises(ValueError):validate(s)


def test_ai_cpu_join_uses_creation_identity_and_preserves_missing_thread():
    cpu=dict(elapsed_seconds=2,before=dict(created_at=10),after=dict(created_at=10),
        thread_cpu=dict(threads=[dict(tid=7,created_filetime='100',cpu_seconds=.5),dict(tid=8,created_filetime='999',cpu_seconds=1)]))
    rows=match_cpu(validate(stats()),cpu)['threads']
    assert rows[0]['matched_cpu_identity'] and rows[0]['whole_thread_logical_cpu_equivalents']==.25
    assert not rows[1]['matched_cpu_identity'] and rows[1]['whole_thread_cpu_seconds'] is None
    cpu['after']['created_at']=11
    with pytest.raises(ValueError):match_cpu(validate(stats()),cpu)


def selected_stats(name='AI::update4Frame'):
    s=stats();p=s['systems'].pop('ai_periodicUpdate');p['function']=name
    s['systems'].update(ai_profiled_function=p,ai_periodicUpdate=None)
    return s


def test_selected_function_has_explicit_identity_without_periodic_alias():
    s=selected_stats();assert validate(s)['function']=='AI::update4Frame'
    assert function_name(s)=='AI::update4Frame'
    assert function_name(stats())=='AI::periodicUpdate'


@pytest.mark.parametrize('change',['unknown','missing','wrong_alias','different_alias','legacy_mislabel'])
def test_selected_function_cannot_be_mislabelled_or_double_counted(change):
    s=selected_stats();p=s['systems']['ai_profiled_function']
    if change=='unknown':p['function']='AI::guessed'
    elif change=='missing':p.pop('function')
    elif change=='wrong_alias':s['systems']['ai_periodicUpdate']=deepcopy(p)
    elif change=='different_alias':
        p['function']='AI::periodicUpdate';s['systems']['ai_periodicUpdate']=deepcopy(p)
        s['systems']['ai_periodicUpdate']['nested_entries_skipped_total']+=1
    else:s['systems'].update(ai_profiled_function=None,ai_periodicUpdate=p)
    with pytest.raises(ValueError):validate(s)


def test_periodic_alias_is_accepted_as_one_function_when_identical():
    s=selected_stats('AI::periodicUpdate');s['systems']['ai_periodicUpdate']=deepcopy(s['systems']['ai_profiled_function'])
    assert validate(s)['calls_total']==6 and function_name(s)=='AI::periodicUpdate'


def test_cpu_disabled_keeps_identity_for_whole_thread_join_and_missing_identity_unknown():
    s=selected_stats();p=s['systems']['ai_profiled_function']
    p.update(cpu_enabled=False,thread_identity_mode='tls_creation_once')
    for r in [p,p['unlisted']]+p['threads']:
        r.update(cpu_available_calls=0,cpu_unavailable_calls=r['calls_total'],cpu_user_total_ms=None,cpu_kernel_total_ms=None)
    p['threads'][1]['created_filetime']=None
    total=validate(s)
    cpu=dict(elapsed_seconds=2,before=dict(created_at=10),after=dict(created_at=10),
        thread_cpu=dict(threads=[dict(tid=7,created_filetime='100',cpu_seconds=.5),dict(tid=8,created_filetime='200',cpu_seconds=1)]))
    rows=match_cpu(total,cpu)['threads']
    assert rows[0]['matched_cpu_identity'] and rows[0]['whole_thread_cpu_seconds']==.5
    assert not rows[1]['matched_cpu_identity'] and rows[1]['whole_thread_cpu_seconds'] is None
    assert p['cpu_user_total_ms'] is None and p['cpu_available_calls']==0


def test_unknown_identity_collection_mode_is_not_silently_accepted():
    s=selected_stats();s['systems']['ai_profiled_function']['thread_identity_mode']='tid_only'
    with pytest.raises(ValueError,match='identity mode'):validate(s)
