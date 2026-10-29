"""Own helper observations, not guaranteed counter resolution or game-hook cost."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json,math,statistics
from pathlib import Path

def count(v):
    if type(v) is not int or v<0:raise ValueError('Invalid calibration count')
    return v
def number(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('Invalid calibration timing')
    return v
def validate_native(n):
    if (n['compiler'],n['pointer_bytes'],n['iterations'],n['repeats'])!=(1600,8,20000,7):raise ValueError('Unexpected calibration plan/toolset')
    if not isinstance(n['created_filetime'],str) or not n['created_filetime'].isascii() or not n['created_filetime'].isdecimal() or not 0<int(n['created_filetime'])<2**64:raise ValueError('Invalid helper creation identity')
    if [r['repeat'] for r in n['read_cost']]!=list(range(7)) or count(n['qpc_frequency'])<=0:raise ValueError('Missing calibration repeats')
    costs=[]
    for row in n['read_cost']:
        elapsed=number(row['elapsed_ms']);cost=number(row['paired_read_mean_us'])
        if not math.isclose(cost,elapsed*1000/20000,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Cached read cost differs')
        costs.append(cost)
    s=n['scan'];wall=number(s['wall_ms'])
    if not 500<=wall<=2000 or count(s['samples'])!=count(s['zero_deltas'])+count(s['positive_deltas']):raise ValueError('Incomplete bounded scan')
    hist=s['histogram'];deltas=[count(r['delta_100ns']) for r in hist]
    if len(hist)>32 or len(deltas)!=len(set(deltas)) or any(v==0 for v in deltas):raise ValueError('Invalid delta histogram')
    if sum(count(r['count']) for r in hist)+count(s['histogram_overflow'])!=s['positive_deltas']:raise ValueError('Histogram accounting differs')
    if s['histogram_overflow']:raise ValueError('Truncated quantum histogram cannot establish observed gcd')
    weighted=sum(r['delta_100ns']*r['count'] for r in hist);gcd=math.gcd(*deltas) if deltas else 0
    if count(s['cpu_delta_100ns'])!=weighted or count(s['positive_gcd_100ns'])!=gcd:raise ValueError('Counter deltas/gcd do not reconcile')
    return dict(paired_read_mean_us=costs,scan_wall_ms=wall,scan_cpu_counter_ms=weighted*.0001,
                observed_positive_delta_gcd_ms=gcd*.0001 if gcd else None,positive_delta_histogram=hist,zero_deltas=s['zero_deltas'],samples=s['samples'])

def analyze(path):
    path=Path(path);raw=path.read_bytes();d=json.loads(raw);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if d.get('completed') is not True or len(d['runs'])!=3:raise ValueError('Incomplete helper controller')
    for name,value in d['source_sha256'].items():
        if sha(name)!=value:raise ValueError('Calibration helper source changed')
    if sha(d['native_exe'])!=d['native_exe_sha256']:raise ValueError('Calibration helper binary changed')
    a,b=d['before'],d['after']
    if not a['paused'] or not b['paused'] or a['game_total_hours']!=b['game_total_hours'] or a['scene_camera_control_owned'] or b['scene_camera_control_owned']:raise ValueError('Game pause was not preserved')
    rows=[]
    for run in d['runs']:
        if run['returncode']!=0 or run['stderr'] or sha(run['stdout'])!=run['stdout_sha256']:raise ValueError('Native calibration run differs')
        n=json.loads(Path(run['stdout']).read_bytes())
        if n!=run['native']:raise ValueError('Cached native calibration differs')
        rows.append(validate_native(n))
    costs=[v for row in rows for v in row['paired_read_mean_us']]
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(),runs=rows,median_paired_read_us=statistics.median(costs),minimum_paired_read_us=min(costs),maximum_paired_read_us=max(costs),
        scope='Own helpers only. Pair cost includes loop/raw conversion/checks, not the full plugin. Observed positive counter increments are not guaranteed resolution. Unit100ns is not precision; do not clamp CPU deltas or treat per-call zeros as no work.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('controller',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if hashlib.sha256(a.controller.read_bytes()).hexdigest()!=a.expected_sha256:raise ValueError('Controller SHA differs')
    result=analyze(a.controller)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(a.output),median_paired_read_us=result['median_paired_read_us'],observed_gcd_ms=[r['observed_positive_delta_gcd_ms'] for r in result['runs']])))
