import json
import pytest
from analyze_root_cpu import analyze
from analyze_root_frame import analyze as cpu_off
from test_root_frame_analysis import sample as root_sample

def sample():
    d=root_sample();d['expected_function_cpu_enabled']=True;d['initial_ping'].update(function_thread_cpu_enabled=True,function_thread_cpu_startup_read_mean_us=.3)
    for row in d['phases']:
        s=row['statistics'];f=s['systems']['profiled_function'];f['cpu_enabled']=True
        for part in [f,f['unlisted']]+f['threads']:
            calls=part['calls_total'];part.update(cpu_available_calls=calls,cpu_unavailable_calls=0,cpu_user_total_ms=15.625*calls,cpu_kernel_total_ms=0)
        row['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(s,separators=(',',':')).encode())
    return d

def test_quantified_counter_mean_may_exceed_short_call_wall_without_clamping():
    d=sample();r=analyze(d)['phases'][1]
    assert r['root_cpu_counter_total_ms']==31.25 and r['root_cpu_counter_mean_ms_per_retained_frame']==15.625
    assert r['selected_function']['mean_ms']==1
    with pytest.raises(ValueError):cpu_off(d)

@pytest.mark.parametrize('poison',['marker','native_mode','cost','zero_cost','partial','negative'])
def test_missing_cpu_mode_or_partial_counter_coverage_is_not_full_measurement(poison):
    d=sample();s=d['phases'][0]['statistics'];f=s['systems']['profiled_function']
    if poison=='marker':d['expected_function_cpu_enabled']=False
    elif poison=='native_mode':d['initial_ping']['function_thread_cpu_enabled']=False
    elif poison=='cost':d['initial_ping']['function_thread_cpu_startup_read_mean_us']=None
    elif poison=='zero_cost':d['initial_ping']['function_thread_cpu_startup_read_mean_us']=0
    elif poison=='partial':f['cpu_available_calls']=1;f['cpu_unavailable_calls']=1
    else:f['cpu_user_total_ms']=-1
    d['phases'][0]['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(s,separators=(',',':')).encode())
    with pytest.raises(ValueError):analyze(d)
