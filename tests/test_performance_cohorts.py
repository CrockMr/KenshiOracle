from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from analyze_performance_cohorts import analyze_manifest,canonical,digest,markdown,phase_summary,process_identity
from test_renderer_analysis import sample as renderer_sample
from test_chars_split_analysis import sample as chars_sample
from test_heavy_battle_analysis import data as battle_sample
from test_root_frame_analysis import sample as root_sample
from test_root_cpu_analysis import sample as root_cpu_sample
from test_root_battle_analysis import sample as root_battle_sample
from test_aggregate_battle_analysis import sample as aggregate_battle_sample


def write_cohort(root,data=None,name='renderer',kind='renderer',file=None):
    data=renderer_sample() if data is None else data
    file=file or name+'.json';raw=json.dumps(data).encode();(root/file).write_bytes(raw)
    return dict(id=name,analyzer=kind,source=file,sha256=hashlib.sha256(raw).hexdigest(),
                plugin_version=data['initial_ping']['plugin_version'],selected_function=data['initial_ping'].get('profiled_function'),scenario='Synthetic independent cohort')

def manifest(*entries):return json.dumps(dict(schema_version=1,cohorts=list(entries))).encode()


def test_replays_raw_capture_and_preserves_disjoint_scopes_and_signed_residual(tmp_path):
    entry=write_cohort(tmp_path);result=analyze_manifest(manifest(entry),tmp_path);row=result['cohorts'][0]['phases'][1]
    assert result['cohort_count']==1 and len(result['cohorts'][0]['phases'])==3
    assert row['frame_statistics']['count']==2 and row['os_cpu']['elapsed_seconds']==12
    assert row['selected_function']['whole_thread_identity_join']['threads'][0]['matched_cpu_identity']
    assert row['os_cpu']['residual_cpu_seconds']==0
    assert row['chars_split']['call_wall_total_ms']==2 and row['chars_split']['post_call_to_lock_total_ms']==1
    assert 'fraction_of_frame_cpu' not in canonical(result).decode() and 'exclusive_cpu_seconds' not in canonical(result).decode()


def test_equal_tids_across_versions_stay_in_separate_cohorts(tmp_path):
    first=write_cohort(tmp_path);data=chars_sample()
    second=write_cohort(tmp_path,data,'chars','chars_split')
    report=analyze_manifest(manifest(first,second),tmp_path)
    assert [r['plugin_version'] for r in report['cohorts']]==['0.8.17','0.8.15']
    assert all(c['process_identity']['pid']==99 for c in report['cohorts'])
    assert len(report['cohorts'])==2 and 'pooled_threads' not in report and 'speedup' not in report


def test_root_frame_is_a_separate_inclusive_export_cohort(tmp_path):
    one=write_cohort(tmp_path);two=write_cohort(tmp_path,root_sample(),'root','root_frame')
    result=analyze_manifest(manifest(one,two),tmp_path)
    assert [c['plugin_version'] for c in result['cohorts']]==['0.8.17','0.8.18']
    f=result['cohorts'][1]['phases'][1]['selected_function']
    assert f['leading_service_excluded'] is False and f['binding_symbol'].endswith('QEAA_NXZ')


def test_cpu_on_does_not_replace_cpu_off_or_clamp_quantified_counters(tmp_path):
    a=write_cohort(tmp_path,root_sample(),'off','root_frame');b=write_cohort(tmp_path,root_cpu_sample(),'on','root_cpu')
    report=analyze_manifest(manifest(a,b),tmp_path)
    off,on=[c['phases'][1]['selected_function'] for c in report['cohorts']]
    assert off['cpu_user_total_ms'] is None and on['cpu_user_total_ms']==31.25 and on['mean_ms']==1


@pytest.mark.parametrize('change',['id','source','hash','version','selection','kind','scenario','schema','missing'])
def test_manifest_cannot_relabel_or_misidentify_a_capture(tmp_path,change):
    entry=write_cohort(tmp_path)
    if change=='id':entry['id']='bad|row'
    elif change=='source':entry['source']='../renderer.json'
    elif change=='hash':entry['sha256']='0'*64
    elif change=='version':entry['plugin_version']='0.8.16'
    elif change=='selection':entry['selected_function']='HavokCharacter::update'
    elif change=='kind':entry['analyzer']='guess'
    elif change=='scenario':entry['scenario']=False
    elif change=='missing':entry['source']='absent.json'
    raw=manifest(entry) if change!='schema' else json.dumps(dict(schema_version=True,cohorts=[entry])).encode()
    with pytest.raises((ValueError,FileNotFoundError)):analyze_manifest(raw,tmp_path)


@pytest.mark.parametrize('change',['same_id','same_path','same_content'])
def test_duplicate_capture_is_not_counted_as_an_independent_repetition(tmp_path,change):
    one=write_cohort(tmp_path);two=deepcopy(one)
    if change!='same_id':two['id']='second'
    if change=='same_content':two['source']='copy.json';(tmp_path/'copy.json').write_bytes((tmp_path/'renderer.json').read_bytes())
    with pytest.raises(ValueError):analyze_manifest(manifest(one,two),tmp_path)


@pytest.mark.parametrize('poison',['incomplete','clock','cpu','function_scope','nonfinite'])
def test_recomputed_raw_hash_does_not_bypass_specialized_validation(tmp_path,poison):
    data=renderer_sample()
    if poison=='incomplete':data['completed']=False
    elif poison=='clock':data['phases'][1]['simulation_progress']['game_hours']=999
    elif poison=='cpu':data['phases'][1]['process_resources']['user_seconds']=999
    elif poison=='function_scope':data['phases'][1]['statistics']['systems']['profiled_function']['scope']='GPU time'
    else:data['unused_metadata']=float('nan')
    entry=write_cohort(tmp_path,data)
    with pytest.raises(ValueError):analyze_manifest(manifest(entry),tmp_path)


def test_exact_filetime_strings_survive_json_without_float_conversion(tmp_path):
    identity='134376841722811107';data=json.loads(json.dumps(renderer_sample()).replace('"123"','"'+identity+'"'))
    for phase in data['phases']:
        phase['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(phase['statistics'],separators=(',',':')).encode())
    entry=write_cohort(tmp_path,data);report=analyze_manifest(manifest(entry),tmp_path)
    row=report['cohorts'][0]['phases'][1]
    assert row['os_cpu']['threads'][0]['created_filetime']==identity
    assert row['selected_function']['whole_thread_identity_join']['threads'][0]['created_filetime']==identity


def test_incomplete_heavy_battle_is_rejected_before_summary(tmp_path):
    data=battle_sample();data['completed']=False;data['initial_ping'].update(plugin_version='0.8.10',system_hook_count=3)
    entry=write_cohort(tmp_path,data,'battle','heavy_battle')
    with pytest.raises(ValueError):analyze_manifest(manifest(entry),tmp_path)


def test_absent_historical_split_is_unknown_not_a_synthetic_zero():
    row=renderer_sample()['phases'][1];del row['statistics']['systems']['charsUpdate_split']
    result=phase_summary(row)
    assert result['chars_split'] is None and result['legacy_chars_mean_ms']==1.5
    assert 'telemetry-lock' in result['legacy_chars_scope']


def test_complete_historical_battle_adapter_keeps_all_four_windows(tmp_path):
    data=battle_sample();data['initial_ping'].update(plugin_version='0.8.10',system_hook_count=3)
    for row in data['windows']:
        r=row['process_resources'];r['logical_cpu_equivalents']=(r['user_seconds']+r['system_seconds'])/r['elapsed_seconds']
    entry=write_cohort(tmp_path,data,'battle','heavy_battle');report=analyze_manifest(manifest(entry),tmp_path)
    assert len(report['cohorts'][0]['phases'])==4 and report['cohorts'][0]['battle_observations']['tracked_actors']==2
    assert all(r['chars_split'] is None for r in report['cohorts'][0]['phases'])


def test_root_battle_keeps_four_windows_and_forty_actors_separate_from_city(tmp_path):
    data=root_battle_sample()
    for row in data['windows']:
        r=row['process_resources'];r['logical_cpu_equivalents']=(r['user_seconds']+r['system_seconds'])/r['elapsed_seconds']
    battle=write_cohort(tmp_path,data,'root_battle','root_battle')
    city=write_cohort(tmp_path,root_cpu_sample(),'root_city','root_cpu')
    report=analyze_manifest(manifest(city,battle),tmp_path)
    assert [len(c['phases']) for c in report['cohorts']]==[3,4]
    cohort=report['cohorts'][1]
    assert cohort['battle_observations']['tracked_actors']==40 and cohort['battle_observations']['actors_with_damage_signal']==1
    assert cohort['phases'][0]['selected_function']['cpu_user_total_ms']==31.25
    assert 'pooled_threads' not in report and 'speedup' not in report


def test_aggregate_battle_keeps_null_details_and_whole_requested_tail(tmp_path):
    data=aggregate_battle_sample()
    for row in data['windows']:
        r=row['process_resources'];r['logical_cpu_equivalents']=(r['user_seconds']+r['system_seconds'])/r['elapsed_seconds']
    report=analyze_manifest(manifest(write_cohort(tmp_path,data,'compact_battle','aggregate_battle')),tmp_path)
    cohort=report['cohorts'][0]
    assert len(cohort['phases'])==4 and cohort['battle_observations']['tracked_actors']==40
    assert all(r['frame_statistics']['collection']['selected_count']==r['frame_statistics']['collection']['requested_maximum'] for r in cohort['phases'])
    assert data['windows'][0]['statistics']['per_frame'] is None


def test_old_capture_without_root_identity_uses_verified_cpu_endpoints():
    data=renderer_sample();del data['created_at'];del data['executable']
    identity=process_identity(data,data['phases'])
    assert identity['created_at']==10 and identity['creation_source']=='first_cpu_endpoint_checked_across_all_phases'
    assert identity['executable_source']=='first_cpu_interval_checked_across_all_phases'
    data['phases'][-1]['process_resources']['before']['created_at']=11
    with pytest.raises(ValueError):process_identity(data,data['phases'])


def test_same_pid_creation_with_a_different_executable_is_not_joined():
    data=renderer_sample();data['phases'][-1]['process_resources']['executable']='e:/other/game.exe'
    with pytest.raises(ValueError):process_identity(data,data['phases'])


def test_sdk_role_is_not_assigned_by_tid_when_its_creation_changes(tmp_path):
    data=renderer_sample()
    for role in data['sdk_roles_after']['sdk_threads']['roles']:role['created_filetime']='999'
    report=analyze_manifest(manifest(write_cohort(tmp_path,data)),tmp_path)
    row=report['cohorts'][0]['phases'][1]
    assert row['selected_function']['whole_thread_identity_join']['threads'][0]['matched_cpu_identity']
    assert row['sdk_role_cpu_join']['unique_matched_threads']==0
    assert all(r['status']=='role_identity_changed' and r['cpu_seconds'] is None for r in row['sdk_role_cpu_join']['roles'])


def test_markdown_keeps_ms_units_windows_and_limitations(tmp_path):
    report=analyze_manifest(manifest(write_cohort(tmp_path)),tmp_path);text=markdown(report)
    assert 'Intervalle moyen ms' in text and 'Fenêtre CPU s' in text and 'Mur moyen ms/frame' in text
    assert 'not displayed FPS' in text and 'not CPU of a selected function' in text
    assert report['manifest_sha256'] in text


def test_cli_is_deterministic_and_refuses_overwriting_sources(tmp_path):
    entry=write_cohort(tmp_path);path=tmp_path/'manifest.json';raw=manifest(entry);path.write_bytes(raw)
    cli=Path(__file__).resolve().parents[1]/'mcp-server/analyze_performance_cohorts.py'
    common=[sys.executable,str(cli),str(path),'--expected-manifest-sha256',digest(raw),'--root',str(tmp_path)]
    for name in ['first','second']:
        result=subprocess.run(common+['--output',str(tmp_path/(name+'.json'))],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
    assert (tmp_path/'first.json').read_bytes()==(tmp_path/'second.json').read_bytes()
    original=(tmp_path/'renderer.json').read_bytes()
    result=subprocess.run(common+['--output',str(tmp_path/'renderer.json')],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and (tmp_path/'renderer.json').read_bytes()==original
    bad=common.copy();bad[bad.index(digest(raw))]='0'*64
    result=subprocess.run(bad+['--output',str(tmp_path/'bad.json')],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and not (tmp_path/'bad.json').exists()
