import json
import pytest
from etw_analysis import controller,digest,span,lifetimes,stacks,sampled_profile

SPAN='''Start time (UTC) : 2026/10/28:07:00:41.3974028
End time (UTC) : 2026/10/28:07:00:44.4739986
Total # Lost Buffers : 0
Total # Lost Events : 0
'''
PROCESSES='MIN, MAX, Process, 0x123, Kenshi_x64.exe (7), 4, 5\nMIN, MAX, Thread, 0x456, Kenshi_x64.exe (7), 10, 0\n'
HTML="""<a id='TblP'></a><table><tr><th>process</th><th>pid</th><th>hits</th><th>percent</th></tr>
<tr><td>Kenshi_x64.exe</td><td>7</td><td>5</td><td>100.00%</td></tr></table>
<a id='TblME'></a><table><tr><th>module</th><th>hits</th><th>percent</th></tr>
<tr><td>Kenshi_x64.exe</td><td>3</td><td>60%</td></tr><tr><td>***unknown***</td><td>2</td><td>40%</td></tr></table>"""
EVENTS='0x2e 0x00 0x0002 10 160 Sampled Profile 8\n'


def fixture(tmp_path):
    trace=tmp_path/'cpu.etl';trace.write_bytes(b'fake ETL')
    data=dict(instance='KenshiProbePilot_'+'0'*12,pid=7,created_at=100,executable=r'C:\game\Kenshi_x64.exe',cleanup_required=False,
        start=dict(returncode=0),stop=dict(returncode=0),before=dict(paused=True,frame=1),after=dict(paused=True,frame=2),
        trace_bytes=trace.stat().st_size,trace_sha256=digest(trace))
    path=tmp_path/'controller.json';path.write_text(json.dumps(data));return path,data


def test_controller_hashes_stopped_trace_before_use(tmp_path):
    p,d=fixture(tmp_path);actual,source=controller(p)
    assert source['kind']=='pilot' and source['pid']==7 and source['trace_sha256']==d['trace_sha256']
    (tmp_path/'cpu.etl').write_bytes(b'changed')
    with pytest.raises(ValueError,match='digest'):controller(p)


@pytest.mark.parametrize('change',['pid','creation','cleanup','start','stop','pause','frame','cpu_lifetime'])
def test_unverified_recording_is_rejected(tmp_path,change):
    p,d=fixture(tmp_path)
    if change=='pid':d['pid']=True
    elif change=='creation':d['created_at']=float('nan')
    elif change=='cleanup':d['cleanup_required']=True
    elif change in ('start','stop'):d[change]['returncode']=1
    elif change=='pause':d['after']['paused']=False
    elif change=='frame':d['after']['frame']=0
    else:d['process_resources']=dict(pid=7,before=dict(created_at=101),after=dict(created_at=101))
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):controller(p)


def test_partial_heng_requires_explicit_opt_in(tmp_path):
    p,d=fixture(tmp_path);d.update(instance='KenshiProbeHeng_'+'0'*12,wpr_commands=dict(start=d['start'],stop=d['stop']),completed=False,error=dict(message='interrupted'))
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='incomplete'):controller(p)
    _,source=controller(p,True);assert source['scenario_completed'] is False and source['scenario_error']


def test_span_preserves_seven_digit_timestamp_and_real_duration():
    r=span(SPAN);assert r['seconds']==pytest.approx(3.0765958) and r['lost_events']==0
    assert r['start_utc'].endswith('3974028')


@pytest.mark.parametrize('change',['pid_reuse','wrong_name','partial_lifetime','contradictory_same_key'])
def test_pid_name_and_full_lifetime_are_required(change):
    text=PROCESSES
    if change=='pid_reuse':text+='MIN, MAX, Process, 0x124, Kenshi_x64.exe (7), 4, 5\n'
    elif change=='wrong_name':text=text.replace('Kenshi_x64.exe','another.exe')
    elif change=='contradictory_same_key':text+='100, MAX, Process, 0x123, Kenshi_x64.exe (7), 4, 5\n'
    else:text=text.replace('MIN, MAX, Process','100, MAX, Process')
    with pytest.raises(ValueError):lifetimes(text,7,r'C:\game\Kenshi_x64.exe')


def test_threads_keep_ambiguous_etl_keys_separate():
    text=PROCESSES+'MIN, MAX, Thread, 0x457, Kenshi_x64.exe (7), 10, 0\n'
    r=lifetimes(text,7,r'C:\game\Kenshi_x64.exe');assert len(r['thread_keys']['10'])==2


def test_stack_leaf_counts_reconcile_without_inventing_symbol_names():
    r=stacks(HTML,7);assert r['observations']==5 and r['modules'][1]['module']=='***unknown***'
    with pytest.raises(ValueError):stacks(HTML.replace('<td>2</td>','<td>1</td>'),7)
    with pytest.raises(ValueError):stacks(HTML,8)


def test_missing_sample_metadata_is_unknown_not_zero():
    assert sampled_profile('unrecognized export format') is None
    assert sampled_profile(EVENTS)==dict(events=10,with_associated_stack=8)
    with pytest.raises(ValueError):sampled_profile(EVENTS.replace('160 Sampled Profile 8','160 Sampled Profile 11'))


@pytest.mark.parametrize('change',['valid','pause','clock','camera'])
def test_complete_heng_checks_raw_condition_and_progress(tmp_path,change):
    from test_pause_cpu_analysis import phase
    p,d=fixture(tmp_path);r=phase('running_x1',False)
    d.update(instance='KenshiProbeHeng_'+'0'*12,wpr_commands=dict(start=d['start'],stop=d['stop']),completed=True,
        scene_before=r['scene_before'],scene_after=r['scene_after'],observations=r['observations'],simulation_progress=r['simulation_progress'])
    if change=='pause':d['observations'][0]['scene']['paused']=True
    elif change=='clock':d['simulation_progress']['game_hours']=0
    elif change=='camera':d['scene_after']['camera_center']=[999,0,0]
    p.write_text(json.dumps(d))
    if change=='valid':assert controller(p)[1]['condition_validation']=='running_x1_at_observations_and_positive_progress'
    else:
        with pytest.raises((ValueError,RuntimeError)):controller(p)
