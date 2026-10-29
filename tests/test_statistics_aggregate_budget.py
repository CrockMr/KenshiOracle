import asyncio
import pytest
from probe import ProbeError
from statistics_aggregate_budget import collect


def compact(n):
    return dict(count=n,first_frame=10,last_frame=9+n,mean_ms=7,per_frame=None,navmesh_slow_calls=None,
                series_truncated=n>100,navmesh_slow_calls_total=0,navmesh_slow_calls_capacity=32,
                navmesh_slow_calls_retention_truncated=False,
                statistics_detail=dict(mode='aggregates',per_frame_rows_omitted=min(n,100),navmesh_slow_rows_omitted=0))


def test_full_requested_tail_is_kept_in_one_getter():
    class Client:
        async def call(self,command,**params):
            assert command=='get_frame_stats' and params==dict(n=3600,detail='aggregates')
            return compact(3600)
    data,plan=asyncio.run(collect(Client(),3600))
    assert data['count']==plan['selected_count']==3600 and len(plan['attempts'])==1
    assert data['per_frame'] is None and plan['detail']=='aggregates'


def test_size_error_is_preserved_without_discarding_frames_in_a_retry():
    class Client:
        calls=0
        async def call(self,*a,**kw):
            self.calls+=1;raise ProbeError('response too large; reduce n or limit')
    c=Client();trace={}
    with pytest.raises(ProbeError):asyncio.run(collect(c,3600,trace))
    assert c.calls==1 and trace['selected_count'] is None and len(trace['attempts'])==1


@pytest.mark.parametrize('fault',['count','mode','missing_metadata','false_omission'])
def test_wrong_compact_response_fails_without_retry(fault):
    class Client:
        async def call(self,*a,**kw):
            s=compact(300)
            if fault=='count':s['count']=299
            elif fault=='mode':s['statistics_detail']['mode']='full'
            elif fault=='missing_metadata':s.pop('statistics_detail')
            else:s['statistics_detail']['per_frame_rows_omitted']=0
            return s
    with pytest.raises(ValueError):asyncio.run(collect(Client(),300))
