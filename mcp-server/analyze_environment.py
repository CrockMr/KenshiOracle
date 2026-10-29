"""Recompute paused-roster quality and multiplicities from retained raw replies."""
import argparse
import hashlib
import json
from pathlib import Path
from environment_diagnostics import admission,compare,summarize


def analyze(data):
    identity=data.get('identity_interval')
    if identity and (identity['pid']!=data['pid'] or identity['before']['created_at']!=identity['after']['created_at']):
        raise ValueError('Process identity disagreement')
    runs=[]
    captured_runs=data['runs'] if 'runs' in data else [dict(captures=data.get('captures',[]))]
    for run in captured_runs:
        summaries=[]
        for capture in run['captures']:
            summary=summarize(capture)
            if capture.get('summary') is not None and capture['summary']!=summary:
                raise ValueError('Cached inventory summary disagrees with raw replies')
            summaries.append(dict(elapsed=capture.get('elapsed'),**summary,
                                  cohort_comparison=capture.get('cohort_comparison')))
        runs.append(dict(captures=summaries,within_load=compare(summaries[0],summaries[-1]) if len(summaries)>=2 else None))
    across=compare(runs[0]['captures'][-1],runs[-1]['captures'][-1]) if len(runs)>=2 and all(x['captures'] for x in runs) else None
    first=next((capture for run in runs for capture in run['captures']),None)
    replay=[dict(run_index=i,capture_index=j,**admission(first,capture))
            for i,run in enumerate(runs) for j,capture in enumerate(run['captures'])]
    return dict(pid=data['pid'],completed=data.get('completed',False),error=data.get('error'),runs=runs,between_loads=across,
        offline_admission_replay=replay,
        restored=bool(data.get('restored')) and not data.get('restoration_error'),
        source_and_copy_unchanged=data.get('source_and_copy_unchanged'),snapshot_unchanged=data.get('snapshot_unchanged'),
        settings_unchanged=data.get('settings_unchanged'),
        limits=['Labels can repeat and are not persistent identities.',
                'Complete means the observed update list only, with non-atomic scene bookends.',
                'No spawn, death, movement cause, or full simulation determinism inferred.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,default=Path('runtime/environment-analysis.json'))
    args=p.parse_args();raw=args.source.read_bytes()
    report=dict(source=str(args.source),source_sha256=hashlib.sha256(raw).hexdigest(),result=analyze(json.loads(raw)))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),completed=report['result']['completed'],between_loads=report['result']['between_loads']),ensure_ascii=False))
