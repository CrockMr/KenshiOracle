import asyncio
from copy import deepcopy
import pytest
import server
from statistics_detail import validate, per_frame_rows, navmesh_slow_rows
from benchmark import validate_nav_diagnostics
from chars_diagnostics import validate as chars
from function_diagnostics import validate as function
from test_root_cpu_analysis import sample as root_sample


def full_sample():
    s=deepcopy(root_sample()['phases'][1]['statistics'])
    s.update(navmesh_slow_calls=[],navmesh_slow_calls_total=0,navmesh_slow_calls_capacity=32,
             navmesh_slow_calls_threshold_ms=10,navmesh_slow_calls_retention_truncated=False)
    return s


def compact(stats=None):
    s=deepcopy(full_sample() if stats is None else stats)
    s['statistics_detail']=dict(mode='aggregates',per_frame_rows_omitted=len(s['per_frame']),navmesh_slow_rows_omitted=len(s['navmesh_slow_calls']))
    s['per_frame']=s['navmesh_slow_calls']=None
    return s


def test_compact_preserves_all_aggregates_and_does_not_invent_observed_rows():
    full=full_sample();s=compact(full);original=deepcopy(s)
    assert validate(full)=='full' and validate(s)=='aggregates'
    assert per_frame_rows(s)==navmesh_slow_rows(s)==[]
    assert chars(s)==chars(full) and function(s)==function(full)
    validate_nav_diagnostics(full);validate_nav_diagnostics(s)
    assert s==original and s['per_frame'] is None and s['navmesh_slow_calls'] is None
    assert {k:v for k,v in s.items() if k not in ('statistics_detail','per_frame','navmesh_slow_calls')}=={k:v for k,v in full.items() if k not in ('per_frame','navmesh_slow_calls')}


def test_native_retention_truncation_is_not_confused_with_omission():
    s=compact();s.update(count=120,last_frame=s['first_frame']+119,series_truncated=True,
                         navmesh_slow_calls_total=8,navmesh_slow_calls_capacity=4,navmesh_slow_calls_retention_truncated=True)
    s['statistics_detail'].update(per_frame_rows_omitted=100,navmesh_slow_rows_omitted=3)
    assert validate(s)=='aggregates' and navmesh_slow_rows(s)==[]
    assert s['navmesh_slow_calls_total']==8 and s['statistics_detail']['navmesh_slow_rows_omitted']==3


def test_navigation_aggregate_keeps_slow_count_without_fabricating_a_call():
    from test_benchmark import nav_stats
    full=nav_stats();full.update(count=3,mean_ms=4,series_truncated=False,per_frame=[dict(frame=f) for f in range(10,13)])
    s=compact(full)
    validate_nav_diagnostics(full);validate_nav_diagnostics(s)
    assert s['navmesh_slow_calls'] is None and s['navmesh_slow_calls_total']==1
    assert s['statistics_detail']['navmesh_slow_rows_omitted']==1


def test_empty_native_buffer_has_explicit_zero_omission_and_unavailable_mean():
    s=dict(count=0,mean_ms=None,per_frame=None,navmesh_slow_calls=None,
           statistics_detail=dict(mode='aggregates',per_frame_rows_omitted=0,navmesh_slow_rows_omitted=0))
    assert validate(s)=='aggregates'
    assert per_frame_rows(s)==navmesh_slow_rows(s)==[]
    for key,value in [('mean_ms',0),('first_frame',0)]:
        poisoned=deepcopy(s);poisoned[key]=value
        with pytest.raises(ValueError):validate(poisoned)
    s['statistics_detail']['navmesh_slow_rows_omitted']=1
    with pytest.raises(ValueError):validate(s)


@pytest.mark.parametrize('poison',['metadata','mode','unknown_field','frame_array','slow_array','missing_frame','missing_slow','frame_count','slow_count','slow_bool','count_bool','bounds','series_flag','slow_capacity','slow_total','slow_flag','mean','empty_frame_omission'])
def test_implicit_omissions_and_contradictory_retention_fail_closed(poison):
    s=compact();d=s['statistics_detail']
    if poison=='metadata':s.pop('statistics_detail')
    elif poison=='mode':d['mode']='full'
    elif poison=='unknown_field':d['claimed_complete']=True
    elif poison=='frame_array':s['per_frame']=[]
    elif poison=='slow_array':s['navmesh_slow_calls']=[]
    elif poison=='missing_frame':s.pop('per_frame')
    elif poison=='missing_slow':s.pop('navmesh_slow_calls')
    elif poison=='frame_count':d['per_frame_rows_omitted']+=1
    elif poison=='slow_count':d['navmesh_slow_rows_omitted']=s['navmesh_slow_calls_total']+1
    elif poison=='slow_bool':d['navmesh_slow_rows_omitted']=False
    elif poison=='count_bool':s['count']=True
    elif poison=='bounds':s['last_frame']+=1
    elif poison=='series_flag':s['series_truncated']=True
    elif poison=='slow_capacity':s['navmesh_slow_calls_capacity']=0
    elif poison=='slow_total':s['navmesh_slow_calls_total']=-1
    elif poison=='slow_flag':s['navmesh_slow_calls_retention_truncated']=not s['navmesh_slow_calls_retention_truncated']
    elif poison=='mean':s['mean_ms']=None
    else:s['count']=0
    for validator in [validate,chars,function,validate_nav_diagnostics]:
        with pytest.raises(ValueError):validator(s)


def test_legacy_optional_fixture_shapes_remain_accepted_without_metadata():
    assert validate({})=='full' and function(dict(systems={})) is None
    validate_nav_diagnostics(dict(systems={}))
    for key in ['per_frame','navmesh_slow_calls']:
        with pytest.raises(ValueError):validate({key:None})


def test_mcp_aggregate_default_and_explicit_full_are_forwarded(monkeypatch):
    calls=[]
    async def fake(command,**params):calls.append((command,params));return params
    monkeypatch.setattr(server,'call',fake)
    assert asyncio.run(server.get_frame_stats(3600))==dict(n=3600,detail='aggregates')
    assert asyncio.run(server.get_frame_stats(3600,'full'))==dict(n=3600,detail='full')
    assert asyncio.run(server.get_frame_stats(3600,'aggregates'))==dict(n=3600,detail='aggregates')
    assert len(calls)==3


@pytest.mark.parametrize('detail',[None,True,0,1.2,[],{},'compact','Full',''])
def test_mcp_detail_does_not_coerce_invalid_types_or_unknown_mode(detail):
    with pytest.raises(ValueError):asyncio.run(server.get_frame_stats(5,detail))


@pytest.mark.parametrize('n',[0,3601,True,1.0,'5'])
def test_mcp_request_bounds_remain_one_to_3600_including_compact(n):
    with pytest.raises(ValueError):asyncio.run(server.get_frame_stats(n,'aggregates'))


def test_oracle_preserves_statistics_tool_with_compact_default():
    tools=asyncio.run(server.mcp.list_tools())
    names={tool.name for tool in tools}
    assert len(names)==len(tools)
    assert {'get_frame_stats','get_clock','dump_state','run_scenario','load_save'} <= names
    schema=next(t.inputSchema for t in tools if t.name=='get_frame_stats')
    assert schema['properties']['detail']['default']=='aggregates'
