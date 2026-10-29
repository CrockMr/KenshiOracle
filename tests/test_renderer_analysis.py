from copy import deepcopy
import json
import pytest
from analyze_renderer import analyze,NAME
from function_diagnostics import RENDERER_SCOPE
from test_chars_split_analysis import sample as city_sample


def totals(calls=2,mean=1,maximum=1):
    return dict(calls_total=calls,mean_ms=mean,max_call_ms=maximum,cpu_available_calls=0,cpu_unavailable_calls=calls,cpu_user_total_ms=None,cpu_kernel_total_ms=None)
def sample():
    data=city_sample();data['initial_ping'].update(plugin_version='0.8.17',profiled_function=NAME,function_hook_reuses_service=True,renderer_update_profiling=True,main_loop_gpu_sensitive_profiling=False,
        dedicated_system_hook_count=2,service_hook_count=2,installed_hook_count=4,havok_character_update_profiling=False,function_thread_cpu_enabled=False)
    for row in data['phases']:
        t=totals();t.update(function=NAME,cpu_enabled=False,thread_identity_mode='tls_creation_once',thread_capacity=8,threads_truncated=False,
            threads=[dict(totals(),thread_id=7,created_filetime='123')],unlisted=totals(0,0,0),nested_entries_skipped_total=0,scope=RENDERER_SCOPE,hook_source='existing_renderer_service_hook',leading_service_excluded=True)
        s=row['statistics'];s['systems'].update(profiled_function=t,ai_profiled_function=None,ai_periodicUpdate=None,charsUpdateUT_mean_ms=None,physics_backThreadUpdate=None)
        for frame in s['per_frame']:frame.update(function_ms=1,function_calls=1,function_nested_entries_skipped=0,ai_function_ms=None,ai_function_calls=None,ai_function_nested_entries_skipped=None,charsUpdateUT_ms=None)
        row['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(s,separators=(',',':')).encode())
    return data


def test_renderer_reuses_one_hook_and_keeps_cpu_identity_separate():
    result=analyze(sample());row=result['phases'][1]
    assert row['selected_function']['function']==NAME
    assert row['selected_function_cpu_identity_matches']['threads'][0]['matched_cpu_identity']


@pytest.mark.parametrize('field,value',[('function_hook_reuses_service',False),('dedicated_system_hook_count',3),('installed_hook_count',5),('havok_character_update_profiling',True),('function_thread_cpu_enabled',True),('profiled_function','Renderer::guessed'),('main_loop_gpu_sensitive_profiling',True),('renderer_update_profiling',False)])
def test_hook_counts_or_coexisting_probe_not_hidden(field,value):
    data=sample();data['initial_ping'][field]=value
    with pytest.raises(ValueError):analyze(data)


def test_selected_scope_is_rechecked_from_raw_statistics():
    data=sample();s=data['phases'][0]['statistics'];s['systems']['profiled_function']['leading_service_excluded']=False
    data['phases'][0]['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(s,separators=(',',':')).encode())
    with pytest.raises(ValueError):analyze(data)
