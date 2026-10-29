import asyncio
from copy import deepcopy
import pytest
from probe import ProbeError
from statistics_budget import SIZE_ERROR,collect,validate_plan


class Client:
    def __init__(self,limit):self.limit=limit;self.calls=[]
    async def call(self,command,**params):
        assert command=='get_frame_stats';self.calls.append(params['n'])
        if params['n']>self.limit:raise ProbeError(SIZE_ERROR)
        return dict(count=params['n'])


def test_read_only_shrink_keeps_error_attempts_and_actual_count():
    c=Client(100);stats,plan=asyncio.run(collect(c,1000))
    assert c.calls==[1000,500,250,125,62]
    assert stats['count']==validate_plan(plan,1000)==62
    assert len(plan['attempts'])==5 and plan['attempts'][-1]['ok']


def test_smallest_request_is_bounded_and_not_retried_forever():
    c=Client(0);trace={}
    with pytest.raises(ProbeError):asyncio.run(collect(c,3600,trace))
    assert len(c.calls)<=12 and c.calls[-1]==1
    assert len(trace['attempts'])==len(c.calls) and trace['selected_count'] is None


def test_other_errors_are_not_retried():
    class Failing:
        calls=0
        async def call(self,*args,**kwargs):
            self.calls+=1;raise ProbeError('world not ready')
    c=Failing();trace={}
    with pytest.raises(ProbeError):asyncio.run(collect(c,100,trace))
    assert c.calls==1
    assert trace['attempts'][0]['error']=='world not ready'


@pytest.mark.parametrize('value',[True,0,3601,1.5])
def test_invalid_statistics_bound_rejected(value):
    with pytest.raises(ValueError):asyncio.run(collect(Client(100),value))


@pytest.mark.parametrize('change',['count','reason','sequence','bytes','success'])
def test_false_shrink_provenance_rejected(change):
    _,plan=asyncio.run(collect(Client(100),200));bad=deepcopy(plan)
    if change=='count':bad['selected_count']=1
    elif change=='reason':bad['attempts'][0]['error']='timeout'
    elif change=='sequence':bad['attempts'][1]['n']=99
    elif change=='bytes':bad['attempts'][-1]['compact_bytes']=0
    else:bad['attempts'][-1]['ok']=False
    with pytest.raises(ValueError):validate_plan(bad,200)
