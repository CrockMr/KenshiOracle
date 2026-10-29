from collections import Counter
from copy import deepcopy
import itertools
import json
import sys

import pytest

import analyze_observer_overhead as observer_analysis
from analyze_observer_overhead import PROTOCOL, analyze, make_plan, validate_resources
from command_service import SCOPE
from test_chars_split_analysis import scene
from test_statistics_detail import full_sample, compact
from thread_resources import thread_deltas


@pytest.mark.parametrize('field,value', [('name','monotonic'),('monotonic',False),('adjustable',True),('resolution',.015625),('resolution',0)])
def test_precise_declared_monotonic_clock_required(field,value):
    data=sample();data['measurement_clock'][field]=value
    with pytest.raises(ValueError,match='measurement clock'):
        analyze(data)


def byte_count(value):
    return len(json.dumps(value, separators=(',', ':')).encode())


def statistics(first):
    value = full_sample()
    template = deepcopy(value['per_frame'][0])
    value.update(count=60, first_frame=first, last_frame=first+59, series_truncated=False,
                 per_frame=[dict(template, frame=first+i) for i in range(60)])
    function = value['systems']['profiled_function']
    for part in [function] + function['threads']:
        part.update(calls_total=60, cpu_available_calls=60, cpu_unavailable_calls=0,
                    cpu_user_total_ms=937.5, cpu_kernel_total_ms=0)
    chars = value['systems']['charsUpdate_split']
    for part in [chars] + chars['threads']:
        part.update(calls_total=60, call_wall_total_ms=60, post_call_to_lock_total_ms=30,
                    legacy_total_ms=90)
    value['_probe_service'] = dict(schema_version=1, command='get_frame_stats', scope=SCOPE,
        menu_service=False, identity_verified=True, created_filetime='123', thread_id=7,
        frame=first+59, queued_qpc_ms=100, started_qpc_ms=101, finished_qpc_ms=102,
        queue_wait_ms=1, service_ms=1)
    return value


def resources(start=100, extra=0):
    a = dict(created_at=10, monotonic_seconds=start-.01, user_seconds=4, system_seconds=2,
        thread_snapshot=dict(threads=[dict(tid=7, created_filetime='123', user_100ns=0,
            kernel_100ns=0, observed_monotonic_seconds=start-.02)]))
    b = dict(created_at=10, monotonic_seconds=start+5.01, user_seconds=5+extra, system_seconds=2.25,
        thread_snapshot=dict(threads=[dict(tid=7, created_filetime='123', user_100ns=round((1.375+extra/2)*1e7),
            kernel_100ns=0, observed_monotonic_seconds=start+5.02)]))
    elapsed = b['monotonic_seconds']-a['monotonic_seconds']
    user = b['user_seconds']-a['user_seconds']; system = b['system_seconds']-a['system_seconds']
    return dict(pid=99, executable='E:/Synthetic/game.exe', before=a, after=b,
        elapsed_seconds=elapsed, user_seconds=user, system_seconds=system,
        logical_cpu_equivalents=(user+system)/elapsed,
        thread_cpu=thread_deltas(a['thread_snapshot'], b['thread_snapshot'], elapsed, user+system))


def locked_scene(frame=1):
    value = scene(frame)
    value.update(scene_camera_control_owned=True, edge_scrolling=False)
    return value


def sample():
    data = dict(protocol=PROTOCOL, completed=True, protected_files_unchanged=True, own_sources_unchanged=True,
        measurement_clock=dict(name='perf_counter',monotonic=True,adjustable=False,resolution=1e-7,implementation='synthetic'),
        settings_unchanged=True, pid=99, created_at=10, executable='E:/Synthetic/game.exe',
        initial_scene=scene(), camera_reference=locked_scene(), pre_release_scene=locked_scene(49999),
        final_scene=scene(50000), initial_ping=dict(plugin_version='0.8.19',
            system_hook_count=3, frame_stats_aggregates_available=True,
            function_thread_cpu_enabled=True, profiled_function='Ogre::Root::renderOneFrame',
            dedicated_system_hook_count=3, service_hook_count=2, installed_hook_count=5,
            ogre_render_one_frame_profiling=True, function_hook_reuses_service=False), blocks=[])
    data.update(guards_before={'scene':False,'settle':False}, guards_after={'scene':False,'settle':False},
        installed_dll_sha256_before='796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3',
        installed_dll_sha256_after='796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3')
    data['initial_scene']['edge_scrolling']=data['final_scene']['edge_scrolling']=True
    for index, plan in enumerate(make_plan()):
        start=100+index*10; first=100+index*100; frequency=plan['frequency_hz']; condition=plan['condition']
        extra={'baseline':0, 'full':.3, 'aggregates':.1}[condition]
        endpoint=compact(statistics(first+1));endpoint['mean_ms']=10+extra;endpoint['p99_ms']=11+extra
        block=dict(plan=plan, completed=True, scene_before=locked_scene(first), selection_scene=locked_scene(first+61),
            scene_after=locked_scene(first+65), process_resources=resources(start, extra),
            measured_start_monotonic_seconds=start, measured_end_monotonic_seconds=start+5,
            requests=[], skipped_slots=[], baseline_wakes=[], statistics_tail=endpoint, requested_frames=60,
            statistics_collection=dict(detail='aggregates', requested_maximum=60, selected_count=60,
                attempts=[dict(n=60, ok=True, compact_bytes=byte_count(endpoint))]),
            controller_cpu_before=dict(user=1, system=1, monotonic_seconds=start-.03),
            controller_cpu_after=dict(user=1.05+extra/10, system=1.01, monotonic_seconds=start+5.03))
        result=statistics(first+1)
        if condition=='aggregates':result=compact(result)
        for slot in range(5*frequency):
            begun=start+slot/frequency+.001; finished=begun+.002
            if condition=='baseline':
                block['baseline_wakes'].append(dict(slot=slot, scheduled_offset_seconds=slot/frequency,
                    started_monotonic_seconds=begun, lateness_seconds=begun-start-slot/frequency))
            else:
                # Immutable synthetic response shared by slots; mutations in tests detach it first.
                block['requests'].append(dict(slot=slot, scheduled_offset_seconds=slot/frequency,
                    started_monotonic_seconds=begun, finished_monotonic_seconds=finished,
                    client_ms=(finished-begun)*1000, lateness_seconds=begun-start-slot/frequency,
                    overrun_seconds=0, result=result, compact_result_bytes=byte_count(result)))
        data['blocks'].append(block)
    return data


def treatment(data, frequency=10, condition='full'):
    return next(b for b in data['blocks'] if b['plan']['condition']==condition and b['plan']['frequency_hz']==frequency)


def test_plan_has_each_permutation_once_per_frequency_and_stable_positions():
    plan=make_plan(); assert len(plan)==36 and plan==make_plan()
    for frequency in (1,10):
        selected=[p for p in plan if p['frequency_hz']==frequency]
        orders=[tuple(p['condition'] for p in selected if p['triad_index']==t) for t in sorted({p['triad_index'] for p in selected})]
        assert set(orders)==set(itertools.permutations(('baseline','full','aggregates')))
        assert Counter(p['condition'] for p in selected)==dict(baseline=6,full=6,aggregates=6)
        assert [p['position'] for p in selected]==[0,1,2]*6


def test_full_synthetic_pilot_replays_signed_pairs_and_different_windows():
    data=sample(); before=deepcopy(data); result=analyze(data)
    assert data==before and result['completed'] and len(result['blocks'])==36
    assert len(result['paired'])==6 and all(len(p['differences'])==6 for p in result['paired'])
    pair=next(p for p in result['paired'] if p['frequency_hz']==10 and p['reference']=='full' and p['treatment']=='aggregates')
    assert pair['distributions']['game_logical_cpus']['median']==pytest.approx(-.2/5.02)
    assert pair['distributions']['callback_mean_ms']['median']==pytest.approx(-.2)
    baseline=result['blocks'][0]
    assert baseline['signed_process_thread_residual_seconds']==pytest.approx(-.125)
    assert baseline['actual_block_seconds']==5 and baseline['process_interval_seconds']==pytest.approx(5.02)
    assert baseline['root_thread_interval_seconds']==pytest.approx(5.04)
    assert baseline['controller_interval_seconds']==pytest.approx(5.06)
    assert baseline['request_distributions']['client_ms'] is None


@pytest.mark.parametrize('poison',['protocol','incomplete','missing_block','order','duplicate_plan','error','restoration','camera_release','protected','settings','unpaused','hours','camera','battle','owned','version','guards','dll','audit','edge'])
def test_incomplete_order_and_unrestored_state_are_rejected(poison):
    d=sample()
    if poison=='protocol':d['protocol']='unknown'
    elif poison=='incomplete':d['completed']=False
    elif poison=='missing_block':d['blocks'].pop()
    elif poison=='order':d['blocks'][0],d['blocks'][1]=d['blocks'][1],d['blocks'][0]
    elif poison=='duplicate_plan':d['blocks'][1]['plan']=deepcopy(d['blocks'][0]['plan'])
    elif poison=='error':d['error']='failed'
    elif poison=='restoration':d['restoration_error']='failed'
    elif poison=='camera_release':d['camera_release_error']='failed'
    elif poison=='protected':d['protected_files_unchanged']=False
    elif poison=='settings':d['settings_unchanged']=False
    elif poison=='unpaused':d['blocks'][0]['scene_after']['paused']=False
    elif poison=='hours':d['final_scene']['game_total_hours']+=1
    elif poison=='camera':d['pre_release_scene']['camera_center']=[100,0,0]
    elif poison=='battle':d['blocks'][0]['scene_after']['battle']['active']=True
    elif poison=='owned':d['final_scene']['scene_camera_control_owned']=True
    elif poison=='version':d['initial_ping']['plugin_version']='0.8.18'
    elif poison=='guards':d['guards_after']['scene']=True
    elif poison=='dll':d['installed_dll_sha256_after']='0'*64
    elif poison=='audit':d['final_audit_error']='failed'
    else:d['final_scene']['edge_scrolling']=False
    with pytest.raises((ValueError,RuntimeError)):analyze(d)


def test_drift_before_lock_and_after_release_is_accepted_with_explicit_scope():
    d=sample()
    d['initial_scene']['camera_center']=[100,200,300]
    d['initial_scene']['camera_position']=[400,500,600]
    d['final_scene']['camera_center']=[1000,2000,3000]
    d['final_scene']['camera_position']=[4000,5000,6000]
    result=analyze(d)
    assert result['completed']
    assert any('after lock settling until immediately before release' in limit and
        'initial camera coordinates are not restored' in limit for limit in result['limits'])


@pytest.mark.parametrize('scene_name', ['scene_before','selection_scene','scene_after'])
def test_camera_drift_within_measured_block_is_rejected(scene_name):
    d=sample()
    d['blocks'][0][scene_name]['camera_center']=[100,0,0]
    with pytest.raises((ValueError,RuntimeError)):analyze(d)


@pytest.mark.parametrize('scene_name', ['camera_reference','pre_release_scene'])
def test_camera_reference_and_pre_release_require_owned_lock(scene_name):
    d=sample()
    d[scene_name]['scene_camera_control_owned']=False
    with pytest.raises(ValueError, match='Measured camera reference was not locked'):analyze(d)


@pytest.mark.parametrize('poison',['pid','creation','elapsed','cpu_user','cpu_kernel','normalization','cached_threads','raw_counter'])
def test_resource_identity_and_counter_recalculation_fail_closed(poison):
    r=resources()
    if poison=='pid':r['pid']=100
    elif poison=='creation':r['after']['created_at']=11
    elif poison=='elapsed':r['elapsed_seconds']+=1
    elif poison=='cpu_user':r['user_seconds']+=1
    elif poison=='cpu_kernel':r['system_seconds']+=1
    elif poison=='normalization':r['logical_cpu_equivalents']+=1
    elif poison=='cached_threads':r['thread_cpu']['residual_cpu_seconds']=0
    else:r['after']['thread_snapshot']['threads'][0]['user_100ns']+=1
    with pytest.raises(ValueError):validate_resources(r,99,10)


@pytest.mark.parametrize('poison',['byte_count','client_clock','outside','offset','catchup','overlap','unordered','duplicate','missing','skip_reason','skip_too_early','skip_overlap','baseline_missing','baseline_getter','compact_null','endpoint_bytes','budget','root_creation','service_creation','controller_negative'])
def test_requests_and_endpoint_evidence_cannot_be_relabelled(poison):
    d=sample();b=treatment(d);r=b['requests'][0]
    if poison=='byte_count':r['compact_result_bytes']+=1
    elif poison=='client_clock':r['client_ms']+=1
    elif poison=='outside':r['started_monotonic_seconds']=b['measured_start_monotonic_seconds']-1
    elif poison=='offset':r['scheduled_offset_seconds']+=1
    elif poison=='catchup':r['started_monotonic_seconds']+=.11;r['finished_monotonic_seconds']+=.11;r['lateness_seconds']+=.11
    elif poison=='overlap':r['finished_monotonic_seconds']+=.15;r['client_ms']+=150
    elif poison=='unordered':b['requests'][0],b['requests'][1]=b['requests'][1],b['requests'][0]
    elif poison=='duplicate':b['requests'][1]['slot']=0
    elif poison=='missing':b['requests'].pop()
    elif poison in ('skip_reason','skip_too_early','skip_overlap'):
        slot=1
        if poison!='skip_overlap':b['requests'].pop(slot)
        b['skipped_slots']=[dict(slot=slot,scheduled_offset_seconds=.1,lateness_seconds=.11 if poison!='skip_too_early' else .01,reason='unknown' if poison=='skip_reason' else 'wake_late')]
    elif poison=='baseline_missing':d['blocks'][0]['baseline_wakes'].pop()
    elif poison=='baseline_getter':d['blocks'][0]['requests']=[deepcopy(r)]
    elif poison=='compact_null':
        b=treatment(d,condition='aggregates');b['requests'][0]['result']=deepcopy(b['requests'][0]['result']);b['requests'][0]['result']['per_frame']=[];b['requests'][0]['compact_result_bytes']=byte_count(b['requests'][0]['result'])
    elif poison=='endpoint_bytes':b['statistics_collection']['attempts'][0]['compact_bytes']+=1
    elif poison=='budget':b['selection_scene']['frame']=b['scene_before']['frame']+3602
    elif poison=='root_creation':
        b['statistics_tail']['systems']['profiled_function']['threads'][0]['created_filetime']='124';b['statistics_collection']['attempts'][0]['compact_bytes']=byte_count(b['statistics_tail'])
    elif poison=='service_creation':
        r['result']=deepcopy(r['result']);r['result']['_probe_service']['created_filetime']='124';r['compact_result_bytes']=byte_count(r['result'])
    else:b['controller_cpu_after']['user']=0
    with pytest.raises((ValueError,RuntimeError)):analyze(d)


def test_previous_overrun_is_recorded_as_skipped_slot_without_catchup():
    d=sample();b=treatment(d);r=b['requests'][0];start=b['measured_start_monotonic_seconds']
    r['finished_monotonic_seconds']=start+.15;r['client_ms']=(r['finished_monotonic_seconds']-r['started_monotonic_seconds'])*1000
    b['requests'].pop(1);b['skipped_slots']=[dict(slot=1,scheduled_offset_seconds=.1,lateness_seconds=.05,reason='previous_request_overrun')]
    result=analyze(d);row=result['blocks'][d['blocks'].index(b)]
    assert row['requests']==49 and row['skipped_slots']==1


def test_baseline_late_wake_is_explicit_and_never_a_getter():
    d=sample();b=treatment(d,condition='baseline');b['baseline_wakes'].pop(1)
    b['skipped_slots']=[dict(slot=1,scheduled_offset_seconds=.1,lateness_seconds=.11,reason='wake_late')]
    result=analyze(d);row=result['blocks'][d['blocks'].index(b)]
    assert row['requests']==0 and row['skipped_slots']==1 and row['request_distributions']['client_ms'] is None


def test_explicit_historical_version_preserves_default_output():
    d=sample()
    assert json.dumps(analyze(d),sort_keys=True)==json.dumps(analyze(d,expected_version='0.8.19'),sort_keys=True)


@pytest.mark.parametrize('version', ['', ' ', '\t', '\n', ' 0.8.19', '0.8.19 ', None, 19])
def test_expected_version_must_be_an_exact_nonempty_identifier(version):
    with pytest.raises(ValueError, match='Expected version'):
        analyze({},expected_version=version)


def test_unregistered_version_is_rejected_before_capture_validation():
    with pytest.raises(ValueError,match='No trusted DLL SHA-256'):
        analyze({},expected_version='unregistered-version')


def test_new_version_requires_explicit_version_and_matching_trusted_dll(monkeypatch):
    d=sample()
    digest='2'*64
    monkeypatch.setitem(observer_analysis.EXPECTED_DLL_SHA256,'0.8.20',digest)
    d['initial_ping']['plugin_version']='0.8.20'
    d['installed_dll_sha256_before']=d['installed_dll_sha256_after']=digest
    assert analyze(d,expected_version='0.8.20')['completed']
    with pytest.raises(ValueError,match='DLL or restoration guards'):
        analyze(d)
    d['installed_dll_sha256_before']=d['installed_dll_sha256_after']='3'*64
    with pytest.raises(ValueError,match='DLL or restoration guards'):
        analyze(d,expected_version='0.8.20')
    d['installed_dll_sha256_before']=d['installed_dll_sha256_after']=digest
    d['initial_ping']['plugin_version']='0.8.19'
    with pytest.raises(ValueError,match='Unexpected native observer configuration'):
        analyze(d,expected_version='0.8.20')


@pytest.mark.parametrize('version', ['', ' ', '\t', ' 0.8.19', '0.8.19 '])
def test_cli_rejects_empty_or_padded_expected_version_before_reading_source(monkeypatch,capsys,version):
    monkeypatch.setattr(sys,'argv',['analyze_observer_overhead.py','does-not-exist.json',
        '--expected-sha256','0'*64,'--expected-version',version,'--output','unused.json'])
    with pytest.raises(SystemExit) as exc:
        observer_analysis.main()
    assert exc.value.code==2
    assert '--expected-version' in capsys.readouterr().err


def test_cli_passes_explicit_version_and_refuses_to_overwrite(monkeypatch,tmp_path):
    source=tmp_path/'source.json';output=tmp_path/'report.json'
    source.write_text('{}',encoding='utf-8')
    digest=observer_analysis.hashlib.sha256(source.read_bytes()).hexdigest()
    called=[]
    def fake_analyze(data,expected_version='0.8.19'):
        called.append((data,expected_version))
        return {'completed':True,'blocks':[]}
    monkeypatch.setattr(observer_analysis,'analyze',fake_analyze)
    monkeypatch.setattr(sys,'argv',['analyze_observer_overhead.py',str(source),
        '--expected-sha256',digest,'--expected-version','0.8.20','--output',str(output)])
    observer_analysis.main()
    assert called==[({},'0.8.20')]
    assert json.loads(output.read_text())==dict(source=str(source),source_sha256=digest,
        result={'completed':True,'blocks':[]})
    original=output.read_bytes()
    with pytest.raises(FileExistsError):observer_analysis.main()
    assert output.read_bytes()==original
