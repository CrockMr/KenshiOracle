from copy import deepcopy
import json
import pytest
from analyze_navigation_timeline import analyze
from test_profiled_function_analysis import data as profile_sample
from thread_resources import thread_deltas,assign_roles


def call(start=5000,completion=700):
    return dict(start_frame=completion-20,completion_frame=completion,started_qpc_ms=start,elapsed_ms=200,
        thread_id=7,game_thread_id_at_start=8,thread_kind='other_threads',start_key=100,goal_key=200,
        start_vector=[1,2,3,99],goal_vector=[4,5,6,0],radius=.4,water=10,hierarchical=True,result=False,
        output_size_before=0,output_size_after=7,thread_cpu_user_ms=218.75,thread_cpu_kernel_ms=0)


def stats(base,rows,first=601,last=1200,total=None):
    s=deepcopy(base);n=last-first+1;total=len(rows) if total is None else total
    s.update(first_frame=first,last_frame=last,count=n,series_truncated=n>100,
        navmesh_slow_calls=deepcopy(rows),navmesh_slow_calls_total=total,navmesh_slow_calls_capacity=32,
        navmesh_slow_calls_threshold_ms=10,navmesh_slow_calls_retention_truncated=len(rows)<total)
    systems=s['systems'];systems.update(navmesh_findPath_calls_total=total,navmesh_findPath_mean_ms=200*total/n,
        navmesh_findPath_max_call_ms=200 if total else 0,navmesh_findPath_threads={})
    for name in ('game_thread','other_threads','unclassified'):
        systems['navmesh_findPath_threads'][name]=dict(calls_total=total if name=='other_threads' else 0,
            mean_ms=200*total/n if name=='other_threads' else 0,max_call_ms=200 if total and name=='other_threads' else 0)
    return s


def sample():
    d=profile_sample();d.update(restored=dict(paused=True),source_and_copy_unchanged=True,settings_unchanged=True)
    d['initial_ping'].update(plugin_version='0.8.10',system_hook_count=3,navmesh_profiling=True)
    for i,row in enumerate(d['phases']):
        r=row['process_resources'];a,b=r['before'],r['after']
        for endpoint,seconds,user in [(a,100+i*30,1),(b,120.1+i*30,4)]:
            endpoint.update(monotonic_seconds=seconds,user_seconds=user,system_seconds=0)
            endpoint['thread_snapshot']['threads']=[dict(tid=t,created_filetime=c,user_100ns=10000000+(delta if endpoint is b else 0),kernel_100ns=0,observed_monotonic_seconds=seconds) for t,c,delta in [(7,'100',20000000),(8,'200',10000000)]]
        wall=b['monotonic_seconds']-a['monotonic_seconds'];r.update(elapsed_seconds=wall,user_seconds=3,system_seconds=0)
        r['thread_cpu']=thread_deltas(a['thread_snapshot'],b['thread_snapshot'],wall,3);assign_roles(r['thread_cpu'],{8},{8},{7})
        calls=[call(),call(8000,1100)] if i==1 else []
        original=row['statistics_tail'];row['statistics_tail']=stats(original,calls)
        context=calls+[call(4000,400)] if i==1 else []
        row['thread_attribution_statistics']=stats(original,context,1,1200)
    return d


def test_deduplicated_calls_have_separate_sources_and_frame_quartiles():
    d=sample();before=deepcopy(d);result=analyze(d);p=result['phases'][1]
    assert d==before and result['unique_retained_call_count']==3
    assert [len(q['call_ids']) for q in p['quartiles_of_tail_frames']]==[1,0,0,1]
    assert p['retained_calls_with_completion_in_tail']==2 and len(p['retained_call_ids_outside_tail'])==1
    assert sorted(len(x['provenances']) for x in result['calls'])==[1,2,2]
    assert p['retained_qpc_envelope']['span_ms']==3200
    assert p['repeated_xyz_parameter_groups'][0]['count']==2
    assert all(x['call_thread_creation_available'] is False for x in p['cpu_thread_candidates'])
    assert all(x['os_endpoint_candidate_status']=='same_tid_stable_os_endpoints' for x in p['cpu_thread_candidates'])
    assert p['cpu_thread_candidates'][0]['candidate_created_filetime']=='100'


@pytest.mark.parametrize('poison',['conflict','duplicate','source_bound','start_frame','qpc_nan','qpc_negative','elapsed','vector','cpu_cache','process_lifetime','aggregate_total','retention_flag','version','restoration'])
def test_conflicting_identity_time_retention_or_capture_is_rejected(poison):
    d=sample();r=d['phases'][1];s=r['statistics_tail'];c=s['navmesh_slow_calls'][0]
    if poison=='conflict':r['thread_attribution_statistics']['navmesh_slow_calls'][0]['goal_vector'][0]+=1
    elif poison=='duplicate':s['navmesh_slow_calls'].append(deepcopy(c));s['navmesh_slow_calls_total']+=1;s['systems']['navmesh_findPath_calls_total']+=1
    elif poison=='source_bound':c['completion_frame']=1201
    elif poison=='start_frame':c['start_frame']=c['completion_frame']+1
    elif poison=='qpc_nan':c['started_qpc_ms']=float('nan')
    elif poison=='qpc_negative':c['started_qpc_ms']=-1
    elif poison=='elapsed':c['elapsed_ms']=float('inf')
    elif poison=='vector':c['start_vector'][0]=None
    elif poison=='cpu_cache':r['process_resources']['thread_cpu']['threads'][0]['cpu_seconds']+=1
    elif poison=='process_lifetime':r['process_resources']['after']['created_at']+=1
    elif poison=='aggregate_total':s['navmesh_slow_calls_total']=3
    elif poison=='retention_flag':s['navmesh_slow_calls_retention_truncated']=True
    elif poison=='version':d['initial_ping']['plugin_version']='0.8.19'
    else:d['source_and_copy_unchanged']=False
    with pytest.raises((ValueError,RuntimeError)):analyze(d)


def test_truncated_retention_reports_unknown_unseen_calls_without_filling_quartiles():
    d=sample();r=d['phases'][1];r['statistics_tail']=stats(r['statistics_tail'],[call()],total=3)
    # Context deliberately supplies only the same one observed call.
    r['thread_attribution_statistics']=stats(r['thread_attribution_statistics'],[call()],1,1200,total=3)
    p=analyze(d)['phases'][1]
    assert p['sources']['statistics_tail']['slow_retention_truncated']
    assert p['sources']['statistics_tail']['slow_calls_total']==3 and p['retained_calls_with_completion_in_tail']==1
    assert sum(len(q['call_ids']) for q in p['quartiles_of_tail_frames'])==1


@pytest.mark.parametrize('name',['statistics_tail','thread_attribution_statistics'])
def test_compact_detail_is_unavailable_not_fabricated_zero_calls(name):
    d=sample();s=d['phases'][1][name];s['statistics_detail']=dict(mode='aggregates',per_frame_rows_omitted=100,navmesh_slow_rows_omitted=len(s['navmesh_slow_calls']))
    s['per_frame']=None;s['navmesh_slow_calls']=None
    with pytest.raises(ValueError,match='requires individual details'):analyze(d)


def test_changed_thread_lifetime_removes_cpu_candidate_instead_of_exact_call_join():
    d=sample();r=d['phases'][1]['process_resources'];r['after']['thread_snapshot']['threads'][0]['created_filetime']='999'
    r['thread_cpu']=thread_deltas(r['before']['thread_snapshot'],r['after']['thread_snapshot'],r['elapsed_seconds'],3);assign_roles(r['thread_cpu'],{8},{8},{7})
    result=analyze(d)['phases'][1]
    assert result['cpu_thread_candidates'][0]['os_endpoint_candidate_status']=='no_stable_os_candidate'
    assert result['cpu_thread_candidates'][0]['whole_thread_cpu_seconds'] is None
    assert result['os_cpu_bounds']['omitted']==[dict(tid=7,reason='tid_reused')]


def test_source_order_does_not_change_call_ids_or_projected_groups():
    d=sample();original=analyze(d)
    for r in d['phases']:
        for name in ['statistics_tail','thread_attribution_statistics']:r[name]['navmesh_slow_calls'].reverse()
    result=analyze(d)
    assert [c['native_call'] for c in result['calls']]==[c['native_call'] for c in original['calls']]
    assert result['phases']==original['phases']
    assert json.dumps(analyze(sample()),sort_keys=True)==json.dumps(original,sort_keys=True)


def test_repeated_identity_inside_one_source_is_rejected_even_when_totals_reconcile():
    d=sample();row=d['phases'][1];duplicate=[call(),call()]
    row['statistics_tail']=stats(row['statistics_tail'],duplicate)
    with pytest.raises(ValueError,match='Duplicate call identity'):analyze(d)


def test_cli_is_hash_bound_refuses_overwrite_and_replays_across_hash_seeds(tmp_path):
    import hashlib,os,subprocess,sys
    from pathlib import Path
    source=tmp_path/'capture.json';source.write_text(json.dumps(sample()),encoding='utf-8')
    sha=hashlib.sha256(source.read_bytes()).hexdigest();script=Path(__file__).resolve().parents[1]/'mcp-server/analyze_navigation_timeline.py'
    reports=[]
    for seed in ('0','8675309'):
        out=tmp_path/('report-'+seed+'.json')
        result=subprocess.run([sys.executable,str(script),str(source),'--expected-sha256',sha,'--output',str(out)],capture_output=True,env=dict(os.environ,PYTHONHASHSEED=seed),timeout=20)
        assert result.returncode==0,result.stderr
        reports.append(out.read_bytes())
    assert reports[0]==reports[1]
    existing=tmp_path/'report-0.json'
    result=subprocess.run([sys.executable,str(script),str(source),'--expected-sha256',sha,'--output',str(existing)],capture_output=True,timeout=20)
    assert result.returncode!=0 and existing.read_bytes()==reports[0]
    rejected=tmp_path/'bad-sha.json'
    result=subprocess.run([sys.executable,str(script),str(source),'--expected-sha256','0'*64,'--output',str(rejected)],capture_output=True,timeout=20)
    assert result.returncode!=0 and not rejected.exists()
