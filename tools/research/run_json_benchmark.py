"""Capture native synthetic benchmark plus exact own-source/binary provenance."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
    if not args.label.isascii() or not args.label.replace('-','').isalnum():raise ValueError('Invalid label')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    binary=ROOT/'plugin/build/native-tests/benchmark_json.exe'
    own=['plugin/json.h','tests/json_legacy_serializer.h','tools/research/benchmark_json.cpp','tools/research/benchmark-json-v100.cmd','tools/research/run_json_benchmark.py']
    sources={p:sha(ROOT/p) for p in own};digest=sha(binary)
    output=ROOT/'runtime/json-benchmark'/args.label;output.mkdir(parents=True)
    (output/'benchmark_json.exe').write_bytes(binary.read_bytes())
    data=dict(label=args.label,started_at=time.time(),synthetic_only=True,source_sha256=sources,binary_sha256=digest,
        executable=str(binary),compiler_flags='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010',runs=[],completed=False)
    target=output/'controller.json'
    def save():target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for i in range(3):
            before=time.perf_counter();run=subprocess.run([str(binary)],cwd=ROOT,capture_output=True,timeout=60)
            row=dict(index=i,elapsed_seconds=time.perf_counter()-before,returncode=run.returncode,stderr=run.stderr.decode('utf-8',errors='replace'))
            data['runs'].append(row);(output/('run-'+str(i)+'.stdout.json')).write_bytes(run.stdout)
            row['stdout_sha256']=hashlib.sha256(run.stdout).hexdigest()
            if run.returncode:raise RuntimeError('Native benchmark failed')
            row['native']=json.loads(run.stdout);save()
        if sha(binary)!=digest or any(sha(ROOT/p)!=v for p,v in sources.items()):raise RuntimeError('Source/binary changed during acquisition')
        data['completed']=True
    except Exception as exc:data['error']=str(exc)
    finally:data['finished_at']=time.time();save()
    print(json.dumps(dict(output=str(target),completed=data['completed'],error=data.get('error'))))
    if not data['completed']:raise SystemExit(1)


if __name__=='__main__':main()
