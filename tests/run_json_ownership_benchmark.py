"""Three native paired ownership runs on deterministic own fixtures only."""
import hashlib,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=(ROOT/'tests/benchmark_json_ownership.cpp').read_text(encoding='utf-8');reference=(ROOT/'tests/benchmark_json.cpp').read_text(encoding='utf-8')
    extract=lambda s:s[s.index('static Value fixture'):s.index('\n}',s.index('static Value fixture'))+2]
    if extract(source)!=extract(reference):raise RuntimeError('Own synthetic fixture generator differs')
    binary=ROOT/'plugin/build/native-tests/benchmark_json_ownership.exe'
    own=['plugin/json.h','tests/benchmark_json_ownership.cpp','tests/benchmark-json-ownership-v100.cmd','tests/run_json_ownership_benchmark.py','tests/benchmark_json.cpp']
    sources={p:sha(ROOT/p) for p in own};digest=sha(binary)
    output=ROOT/'runtime/json-ownership'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');output.mkdir(parents=True)
    (output/'benchmark_json_ownership.exe').write_bytes(binary.read_bytes())
    data=dict(started_at=time.time(),synthetic_only=True,fixture_generator_matches=True,source_sha256=sources,binary_sha256=digest,
        executable=str(binary),compiler_flags='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010',runs=[],completed=False)
    target=output/'controller.json'
    def save():target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for index in range(3):
            started=time.perf_counter();run=subprocess.run([str(binary)],cwd=ROOT,capture_output=True,timeout=60)
            row=dict(index=index,elapsed_seconds=time.perf_counter()-started,returncode=run.returncode,stderr=run.stderr.decode('utf-8',errors='replace'))
            data['runs'].append(row);(output/('run-'+str(index)+'.stdout.json')).write_bytes(run.stdout);row['stdout_sha256']=hashlib.sha256(run.stdout).hexdigest()
            if run.returncode:raise RuntimeError('Native benchmark failed')
            row['native']=json.loads(run.stdout);save()
        if sha(binary)!=digest or any(sha(ROOT/p)!=v for p,v in sources.items()):raise RuntimeError('Source/binary changed during acquisition')
        data['completed']=True
    except Exception as exc:data['error']=str(exc)
    finally:data['finished_at']=time.time();save()
    print(json.dumps(dict(output=str(target),completed=data['completed'],error=data.get('error'))))
    if not data['completed']:raise SystemExit(1)


if __name__=='__main__':main()
