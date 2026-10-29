"""Validate and replay the synthetic native JSON benchmark without game access."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json,math,statistics
from pathlib import Path

OPS=('construct_destroy','copy_destroy','envelope_copy_destroy','serialize_legacy','serialize_current')


def analyze(data):
    if not data['completed'] or data.get('error') or data['synthetic_only'] is not True or len(data['runs'])!=3:raise ValueError('Incomplete synthetic benchmark')
    if data['compiler_flags']!='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010':raise ValueError('Compiler plan differs')
    for value in [data['binary_sha256'],*data['source_sha256'].values()]:
        if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid provenance hash')
    fixtures={};all_rows=[]
    for index,run in enumerate(data['runs']):
        if run['index']!=index or run['returncode']!=0 or run['stderr'] or not math.isfinite(run['elapsed_seconds']) or run['elapsed_seconds']<=0:raise ValueError('Native process failed')
        native=run['native']
        if (native['schema'],native['compiler'],native['pointer_bytes'],native['iterations'],native['repeats'])!=(1,1600,8,60,7) or native['synthetic_only'] is not True:raise ValueError('Native compiler/plan differs')
        rows=native['rows']
        if len(rows)!=105:raise ValueError('Incomplete timings')
        for row_index,row in enumerate(rows):
            fixture,offset=divmod(row_index,35);rep,order=divmod(offset,5);op=OPS[(order+rep)%5]
            if (row['fixture'],row['repetition'],row['operation'])!=(fixture,rep,op):raise ValueError('Timing order differs')
            if type(row['bytes']) is not int or not 0<row['bytes']<=65536 or type(row['fnv1a32']) is not int or not 0<=row['fnv1a32']<2**32:raise ValueError('Invalid synthetic fixture fingerprint')
            fingerprint=(row['bytes'],row['fnv1a32'])
            if fixture in fixtures and fixtures[fixture]!=fingerprint:raise ValueError('Fixture bytes differ')
            fixtures[fixture]=fingerprint
            for key in ('elapsed_ms','per_operation_ms'):
                if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or row[key]<=0:raise ValueError('Invalid measured duration')
            if not math.isclose(row['elapsed_ms']/60,row['per_operation_ms'],rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Inconsistent duration')
        checksum=420*(26+2*sum(fixtures[k][0] for k in range(3)))
        if native['checksum']!=checksum:raise ValueError('Benchmark consumption checksum differs')
        all_rows.extend(rows)
    result=[]
    for fixture in range(3):
        values={op:[r['per_operation_ms'] for r in all_rows if r['fixture']==fixture and r['operation']==op] for op in OPS}
        summary={op:dict(count=len(v),mean_ms=statistics.mean(v),median_ms=statistics.median(v),minimum_ms=min(v),maximum_ms=max(v)) for op,v in values.items()}
        ratios=[values['serialize_legacy'][i]/values['serialize_current'][i] for i in range(21)]
        # Same run/repetition pairing; wall timings, not a whole-program speedup.
        result.append(dict(fixture=fixture,bytes=fixtures[fixture][0],fnv1a32=fixtures[fixture][1],operations=summary,
            paired_legacy_over_current=dict(count=21,minimum=min(ratios),median=statistics.median(ratios),maximum=max(ratios))))
    return dict(fixtures=result,scope='Synthetic deterministic own trees, native v100 x64 /O2, 3 processes x 7 rotating repetitions x 60 operations. Inclusive wall time; ambient load and allocation effects remain. No game, FPS or exclusive CPU claim.')


def compare(baseline,candidate):
    a,b=analyze(baseline),analyze(candidate)
    if baseline['compiler_flags']!=candidate['compiler_flags'] or set(baseline['source_sha256'])!=set(candidate['source_sha256']):raise ValueError('Source/compiler inventory differs')
    for name,value in baseline['source_sha256'].items():
        if name!='plugin/json.h' and candidate['source_sha256'][name]!=value:raise ValueError('Uncontrolled benchmark source change')
    if [(r['bytes'],r['fnv1a32']) for r in a['fixtures']]!=[(r['bytes'],r['fnv1a32']) for r in b['fixtures']]:raise ValueError('Fixture output changed')
    return dict(baseline=a,candidate=b,changed_sources=[k for k,v in baseline['source_sha256'].items() if candidate['source_sha256'][k]!=v],
        scope='Candidate/reference are paired inside each native process; cross-capture means are descriptive, not a causal game comparison.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path);parser.add_argument('--baseline-sha256',required=True);parser.add_argument('--candidate-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    inputs=[]
    for path,expected in [(args.baseline,args.baseline_sha256),(args.candidate,args.candidate_sha256)]:
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=expected:raise SystemExit('Input SHA256 mismatch')
        data=json.loads(raw)
        for row in data['runs']:
            stdout=(path.parent/('run-'+str(row['index'])+'.stdout.json')).read_bytes()
            if hashlib.sha256(stdout).hexdigest()!=row['stdout_sha256'] or json.loads(stdout)!=row['native']:raise SystemExit('Native stdout provenance differs')
        if hashlib.sha256((path.parent/'benchmark_json.exe').read_bytes()).hexdigest()!=data['binary_sha256']:raise SystemExit('Own native binary provenance differs')
        inputs.append(data)
    result=dict(baseline_source_sha256=args.baseline_sha256,candidate_source_sha256=args.candidate_sha256,result=compare(*inputs))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),changed_sources=result['result']['changed_sources'])))
