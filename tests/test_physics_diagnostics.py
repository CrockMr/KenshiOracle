from copy import deepcopy
import pytest
from physics_diagnostics import validate


def metrics(calls,mean,maximum,available,user,kernel):
    return dict(calls_total=calls,mean_ms=mean,max_call_ms=maximum,cpu_available_calls=available,
        cpu_unavailable_calls=calls-available,cpu_user_total_ms=user,cpu_kernel_total_ms=kernel)


def stats():
    a=dict(metrics(2,1,6,1,15.625,0),thread_id=7,created_filetime='100')
    b=dict(metrics(3,2,7,3,0,15.625),thread_id=8,created_filetime='200')
    total=dict(metrics(6,3.5,7,5,15.625,15.625),cpu_enabled=True,thread_capacity=8,
        threads=[a,b],unlisted=metrics(1,.5,5,1,0,0),threads_truncated=True)
    return dict(count=10,systems=dict(charsUpdateUT_mean_ms=None,physics_backThreadUpdate=total))


def test_reconciles_partial_cpu_and_unlisted_threads_without_cpu_clamp():
    result=validate(stats())
    assert result['cpu_available_calls']==5 and result['threads_truncated']
    assert result['threads'][0]['cpu_user_total_ms']>result['threads'][0]['mean_ms']*10


@pytest.mark.parametrize('change',['count','duration','maximum','availability','cpu','duplicate','overflow','retired','creation'])
def test_bad_physics_telemetry_is_rejected(change):
    data=stats();p=data['systems']['physics_backThreadUpdate']
    if change=='count': p['calls_total']+=1;p['cpu_unavailable_calls']+=1
    elif change=='duration': p['mean_ms']+=1
    elif change=='maximum': p['max_call_ms']+=1
    elif change=='availability': p['cpu_available_calls']+=1
    elif change=='cpu': p['threads'][0]['cpu_user_total_ms']=-1
    elif change=='duplicate': p['threads'][1].update(thread_id=7,created_filetime='100')
    elif change=='overflow': p['threads_truncated']=False
    elif change=='retired': data['systems']['charsUpdateUT_mean_ms']=0
    else: p['threads'][0]['created_filetime']='NaN'
    with pytest.raises(ValueError): validate(data)


def test_disabled_cpu_and_older_payloads_stay_explicit():
    data=stats();p=data['systems']['physics_backThreadUpdate'];p['cpu_enabled']=False
    for row in [p,p['unlisted']]+p['threads']:
        row.update(cpu_available_calls=0,cpu_unavailable_calls=row['calls_total'],cpu_user_total_ms=None,cpu_kernel_total_ms=None)
    assert validate(data)['cpu_user_total_ms'] is None
    assert validate(dict(systems={})) is None


def test_same_tid_different_creation_is_not_merged():
    data=stats();p=data['systems']['physics_backThreadUpdate'];p['threads'][1]['thread_id']=7
    assert validate(data)['threads'][0]['created_filetime']!=p['threads'][1]['created_filetime']
