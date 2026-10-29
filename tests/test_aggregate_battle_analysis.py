from copy import deepcopy
import json
import pytest
from analyze_aggregate_battle import analyze
from test_root_battle_analysis import sample as battle_sample


def compact(s):
    s.setdefault('navmesh_slow_calls',[])
    s.update(navmesh_slow_calls_total=0,navmesh_slow_calls_capacity=32,navmesh_slow_calls_retention_truncated=False)
    s['statistics_detail']=dict(mode='aggregates',per_frame_rows_omitted=min(s['count'],100),navmesh_slow_rows_omitted=len(s['navmesh_slow_calls']))
    s['per_frame']=None;s['navmesh_slow_calls']=None;s['series_truncated']=s['count']>100
    return s


def plan(s):
    return dict(requested_maximum=s['count'],selected_count=s['count'],detail='aggregates',attempts=[dict(n=s['count'],ok=True,compact_bytes=len(json.dumps(s,separators=(',',':')).encode()))])


def sample():
    d=battle_sample();d['statistics_detail_requested']='aggregates';d['initial_ping'].update(plugin_version='0.8.19',frame_stats_aggregates_available=True)
    for row in d['windows']:
        context=deepcopy(row['statistics']);context.update(count=3600,first_frame=1,last_frame=3600)
        row['context']=compact(context);row['context_collection']=plan(row['context'])
        compact(row['statistics']);row['statistics_collection']=plan(row['statistics']);row['navigation_detail_roles_available']=False
    return d


def test_complete_aggregate_windows_retain_cpu_and_damage_without_detail_fabrication():
    d=sample();original=deepcopy(d);r=analyze(d)
    assert d==original and len(r['windows'])==4 and len(r['actors'])==40
    assert all(w['root_cpu_counter_total_ms']==31.25 for w in r['windows'])
    assert all(w['statistics']['count']==8 for w in r['windows'])
    assert d['windows'][0]['statistics']['per_frame'] is None


@pytest.mark.parametrize('poison',['version','capability','requested_mode','shrunk','retries','byte_count','null_detail','nav_role'])
def test_compact_capture_contract_cannot_claim_full_range_after_reduction(poison):
    d=sample();w=d['windows'][0]
    if poison=='version':d['initial_ping']['plugin_version']='0.8.18'
    elif poison=='capability':d['initial_ping']['frame_stats_aggregates_available']=False
    elif poison=='requested_mode':d['statistics_detail_requested']='full'
    elif poison=='shrunk':w['statistics_collection']['selected_count']=4
    elif poison=='retries':w['statistics_collection']['attempts'].insert(0,dict(n=16,ok=False,error='response too large; reduce n or limit'))
    elif poison=='byte_count':w['statistics_collection']['attempts'][0]['compact_bytes']+=1
    elif poison=='null_detail':w['statistics']['statistics_detail']=None
    else:w['navigation_detail_roles_available']=True
    with pytest.raises((ValueError,TypeError)):analyze(d)
