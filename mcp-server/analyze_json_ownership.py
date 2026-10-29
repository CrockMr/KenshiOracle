"""Replay paired native ownership wall times; no game/CPU attribution."""
import argparse,hashlib,json,math,statistics
from pathlib import Path
OPS=('envelope_copy','envelope_transfer','pipeline_copy','pipeline_transfer')


def analyze(data):
    if data['completed'] is not True or data.get('error') or data['synthetic_only'] is not True or data['fixture_generator_matches'] is not True or len(data['runs'])!=3:raise ValueError('Incomplete ownership benchmark')
    if data['compiler_flags']!='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010':raise ValueError('Compiler differs')
    for digest in [data['binary_sha256'],*data['source_sha256'].values()]:
        if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid provenance hash')
    fixtures={};rows=[]
    for index,run in enumerate(data['runs']):
        if type(run['index']) is not int or run['index']!=index or type(run['returncode']) is not int or run['returncode']!=0 or run['stderr']:raise ValueError('Native process failed')
        if type(run['elapsed_seconds']) not in (int,float) or not math.isfinite(run['elapsed_seconds']) or run['elapsed_seconds']<=0:raise ValueError('Invalid process duration')
        native=run['native'];plan=('schema','compiler','pointer_bytes','iterations','repeats')
        if any(type(native[k]) is not int for k in plan) or tuple(native[k] for k in plan)!=(1,1600,8,60,7) or native['synthetic_only'] is not True or len(native['rows'])!=84:raise ValueError('Native plan differs')
        for row_index,row in enumerate(native['rows']):
            fixture,offset=divmod(row_index,28);rep,order=divmod(offset,4)
            if type(row['fixture']) is not int or type(row['repetition']) is not int or (row['fixture'],row['repetition'],row['operation'])!=(fixture,rep,OPS[(order+rep)%4]):raise ValueError('Timing order differs')
            if type(row['bytes']) is not int or not 0<row['bytes']<=65536 or type(row['fnv1a32']) is not int or not 0<=row['fnv1a32']<2**32:raise ValueError('Invalid fixture fingerprint')
            fingerprint=(row['bytes'],row['fnv1a32'])
            if fixture in fixtures and fixtures[fixture]!=fingerprint:raise ValueError('Fixture output differs')
            fixtures[fixture]=fingerprint
            if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) or row[k]<=0 for k in ('elapsed_ms','per_operation_ms')):raise ValueError('Invalid duration')
            if not math.isclose(row['elapsed_ms']/60,row['per_operation_ms'],rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Timing units differ')
        # 4 operations consume result.size(2), root.size(4/3/3), id.size(17).
        if type(native['checksum']) is not int or native['checksum']!=420*4*(23+22+22):raise ValueError('Consumption checksum differs')
        rows.extend(native['rows'])
    result=[]
    for fixture in range(3):
        values={op:[r['per_operation_ms'] for r in rows if r['fixture']==fixture and r['operation']==op] for op in OPS}
        summary={op:dict(count=len(v),mean_ms=statistics.mean(v),minimum_ms=min(v),maximum_ms=max(v)) for op,v in values.items()}
        paired={}
        for name in ('envelope','pipeline'):
            old,new=values[name+'_copy'],values[name+'_transfer'];ratio=[a/b for a,b in zip(old,new)];delta=[a-b for a,b in zip(old,new)]
            paired[name]=dict(count=21,ratio_median=statistics.median(ratio),ratio_minimum=min(ratio),ratio_maximum=max(ratio),difference_mean_ms=statistics.mean(delta))
        result.append(dict(fixture=fixture,bytes=fixtures[fixture][0],fnv1a32=fixtures[fixture][1],operations=summary,paired=paired))
    return dict(fixtures=result,scope='Native v100 x64 /O2; synthetic own payload initially cloned in both paths, 3 processes x 7 rotating repetitions x 60 operations. Wall time including destruction; no actual game construction, thread/event scheduling, network serialization, FPS or exclusive CPU measurement.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--expected-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw=args.input.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise SystemExit('Input SHA256 mismatch')
    data=json.loads(raw)
    for run in data['runs']:
        stdout=(args.input.parent/('run-'+str(run['index'])+'.stdout.json')).read_bytes()
        if hashlib.sha256(stdout).hexdigest()!=run['stdout_sha256'] or json.loads(stdout)!=run['native']:raise SystemExit('Native stdout provenance differs')
    if hashlib.sha256((args.input.parent/'benchmark_json_ownership.exe').read_bytes()).hexdigest()!=data['binary_sha256']:raise SystemExit('Own binary provenance differs')
    result=dict(source_sha256=digest,result=analyze(data))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=digest)))
