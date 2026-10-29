from copy import deepcopy
import pytest
from analyze_thread_cpu_calibration import validate_native

def sample():
    return dict(compiler=1600,pointer_bytes=8,iterations=20000,repeats=7,created_filetime='134376841722811107',qpc_frequency=10000000,
        read_cost=[dict(repeat=i,elapsed_ms=1,paired_read_mean_us=.05) for i in range(7)],
        scan=dict(wall_ms=500,samples=3,zero_deltas=1,positive_deltas=2,histogram_overflow=0,positive_gcd_100ns=156250,cpu_delta_100ns=312500,histogram=[dict(delta_100ns=156250,count=2)]))

def test_observed_tick_is_not_mislabeled_as_100ns_resolution():
    r=validate_native(sample());assert r['observed_positive_delta_gcd_ms']==15.625 and r['scan_cpu_counter_ms']==31.25

@pytest.mark.parametrize('poison',['compiler','identity','cost','duration','counts','gcd','cpu','duplicate','overflow'])
def test_inconsistent_calibration_cannot_be_used_as_precision_evidence(poison):
    d=sample();s=d['scan']
    if poison=='compiler':d['compiler']=1900
    elif poison=='identity':d['created_filetime']=134376841722811107
    elif poison=='cost':d['read_cost'][0]['paired_read_mean_us']=99
    elif poison=='duration':s['wall_ms']=1
    elif poison=='counts':s['zero_deltas']=9
    elif poison=='gcd':s['positive_gcd_100ns']=1
    elif poison=='cpu':s['cpu_delta_100ns']=1
    elif poison=='duplicate':s['histogram'].append(deepcopy(s['histogram'][0]))
    else:s['histogram_overflow']=1
    with pytest.raises(ValueError):validate_native(d)
