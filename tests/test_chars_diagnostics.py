from copy import deepcopy
import pytest
from chars_diagnostics import SCOPE,validate


def totals(calls=2,call=2,post=1,n=2):
    return dict(calls_total=calls,call_wall_total_ms=call,post_call_to_lock_total_ms=post,legacy_total_ms=call+post,
        call_wall_mean_ms=call/n,post_call_to_lock_mean_ms=post/n,legacy_mean_ms=(call+post)/n,
        max_call_wall_ms=call/calls if calls else 0,max_post_call_to_lock_ms=post/calls if calls else 0,max_legacy_ms=(call+post)/calls if calls else 0)


def sample():
    root=totals();thread=dict(root,thread_id=7,created_filetime='134376698083790089',identity_verified=True)
    root.update(function='GameWorld::charsUpdate',scope=SCOPE,cpu_enabled=False,cpu_user_total_ms=None,cpu_kernel_total_ms=None,
        thread_identity_mode='tls_creation_once',thread_capacity=8,threads=[thread],unlisted=totals(0,0,0),threads_truncated=False)
    return dict(count=2,first_frame=10,last_frame=11,series_truncated=False,systems=dict(charsUpdate_split=root,charsUpdate_mean_ms=1.5),
        per_frame=[dict(frame=f,charsUpdate_calls=1,charsUpdate_call_wall_ms=1,charsUpdate_ms=1.5) for f in (10,11)])


def test_disjoint_intervals_reconcile_and_zero_calls_admitted():
    data=sample();assert validate(data)['call_wall_mean_ms']==1
    root=totals(0,0,0);root.update({k:v for k,v in data['systems']['charsUpdate_split'].items() if k not in root})
    root['threads']=[];data['systems'].update(charsUpdate_split=root,charsUpdate_mean_ms=0)
    for row in data['per_frame']:row.update(charsUpdate_calls=0,charsUpdate_call_wall_ms=0,charsUpdate_ms=0)
    assert validate(data)['calls_total']==0


@pytest.mark.parametrize('mutation',['legacy','sum','mean','negative','nan','max','counts','duplicate','identity','unknown','cpu','capacity','flag','series','frame','series_sum','scope','bool_count','missing'])
def test_invalid_timing_identity_or_scope_rejected(mutation):
    data=sample();root=data['systems']['charsUpdate_split']
    if mutation=='legacy':data['systems']['charsUpdate_mean_ms']=9
    elif mutation=='sum':root['legacy_total_ms']=10
    elif mutation=='mean':root['call_wall_mean_ms']=2
    elif mutation=='negative':root['post_call_to_lock_total_ms']=-1
    elif mutation=='nan':root['call_wall_total_ms']=float('nan')
    elif mutation=='max':root['max_legacy_ms']=100
    elif mutation=='counts':root['threads'][0]['calls_total']=1
    elif mutation=='duplicate':root['threads'].append(deepcopy(root['threads'][0]))
    elif mutation=='identity':root['threads'][0]['created_filetime']=134376698083790089
    elif mutation=='unknown':root['threads'][0]['identity_verified']=False
    elif mutation=='cpu':root['cpu_user_total_ms']=0
    elif mutation=='capacity':root['thread_capacity']=True
    elif mutation=='flag':root['threads_truncated']=True
    elif mutation=='series':data['per_frame'].pop()
    elif mutation=='frame':data['per_frame'][1]['frame']=13
    elif mutation=='series_sum':data['per_frame'][0]['charsUpdate_call_wall_ms']=.5
    elif mutation=='scope':root['scope']='exclusive CPU'
    elif mutation=='bool_count':data['count']=True
    elif mutation=='missing':data['systems'].pop('charsUpdate_split')
    with pytest.raises(ValueError):validate(data)


def test_unknown_creation_is_not_verified_but_wall_time_remains_valid():
    data=sample();data['systems']['charsUpdate_split']['threads'][0].update(created_filetime=None,identity_verified=False)
    assert not validate(data)['threads'][0]['identity_verified']


def test_overflow_threads_and_totals_reconcile():
    data=sample();root=data['systems']['charsUpdate_split'];root.update(totals(10,10,5));root.update(max_call_wall_ms=1,max_post_call_to_lock_ms=.5,max_legacy_ms=1.5)
    root['threads']=[dict(totals(1,1,.5),thread_id=i+1,created_filetime=str(100+i),identity_verified=True) for i in range(8)]
    root['unlisted']=totals();root['threads_truncated']=True;data['systems']['charsUpdate_mean_ms']=7.5
    for row in data['per_frame']:row.update(charsUpdate_calls=5,charsUpdate_call_wall_ms=5,charsUpdate_ms=7.5)
    assert validate(data)['unlisted']['calls_total']==2


def test_truncated_series_is_not_the_full_aggregate():
    data=sample();root=data['systems']['charsUpdate_split'];root.update(totals(120,120,60,n=120))
    root['threads']=[dict(totals(120,120,60,n=120),thread_id=7,created_filetime='123',identity_verified=True)];root['unlisted']=totals(0,0,0,n=120)
    data.update(count=120,first_frame=10,last_frame=129,series_truncated=True)
    data['per_frame']=[dict(frame=f,charsUpdate_calls=1,charsUpdate_call_wall_ms=1,charsUpdate_ms=1.5) for f in range(30,130)]
    assert validate(data)['calls_total']==120


def test_zero_duration_still_has_an_observed_call_count():
    data=sample();root=data['systems']['charsUpdate_split'];root.update(totals(2,0,0));root['threads'][0].update(totals(2,0,0));data['systems']['charsUpdate_mean_ms']=0
    for row in data['per_frame']:row.update(charsUpdate_call_wall_ms=0,charsUpdate_ms=0)
    assert validate(data)['calls_total']==2
