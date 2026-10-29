"""Reproducible read-only xperf exports filtered to one verified game lifetime."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from etw_analysis import controller,digest,span,lifetimes,stacks,sampled_profile

XPERF=Path(r'C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe')


def export(controller_path,output=None,top_threads=3,allow_incomplete=False,xperf=XPERF,runner=subprocess.run):
    data,source=controller(controller_path,allow_incomplete)
    if not 0<=top_threads<=8:raise ValueError('Top thread count must be 0..8')
    folder=Path(output) if output else Path(controller_path).resolve().parent/('analysis-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(parents=True,exist_ok=False)
    report=dict(source=source,completed=False,symbols_enabled=False,commands=[],outputs={},thread_reports=[],
        limitations=['PID/lifetime filtered exports; symbols intentionally not resolved.',
                    'Top threads come from the enclosing OS interval, which differs from ETL bounds.',
                    'A stack observation is not an exclusive function/subsystem cost.'])
    manifest=folder/'analysis.json'
    def publish():manifest.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def run(name,*action):
        target=(folder/name).resolve();args=[str(xperf),'-i',source['trace'],'-o',str(target),'-a',*map(str,action)]
        entry=dict(argv=args);report['commands'].append(entry);publish()
        try:
            result=runner(args,capture_output=True,text=True,errors='replace',timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            entry.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
            if result.returncode!=0 or not target.is_file():raise RuntimeError('xperf export failed: '+name)
            report['outputs'][name]=dict(path=str(target),bytes=target.stat().st_size,sha256=digest(target));publish()
            return target.read_text(encoding='utf-8-sig')
        except Exception as e:entry['error']=str(e);publish();raise
    publish()
    try:
        report['tool']=dict(path=str(Path(xperf).resolve()),sha256=digest(xperf))
        report['span']=span(run('span.txt','tracestats','-timespan','actual'))
        if report['span']['lost_events'] or report['span']['lost_buffers']:raise ValueError('ETL reports event/buffer loss; no complete-result claim')
        report['global_sampled_profile']=sampled_profile(run('events.txt','tracestats','-detail','stack'))
        report['lifetimes']=lifetimes(run('processes.txt','process','-thread','-image'),source['pid'],source['executable'])
        report['game_stacks']=stacks(run('game-stacks.html','stack','-pid',source['pid'],'-butterfly','1'),source['pid'])
        cpu=data.get('process_resources',{}).get('thread_cpu',{})
        report['cpu_interval_omissions']=cpu.get('omitted_reasons')
        rows=sorted(cpu.get('threads',[]),key=lambda r:r['cpu_seconds'],reverse=True)[:top_threads]
        seen=set()
        for row in rows:
            tid=row['tid']
            if isinstance(tid,bool) or not isinstance(tid,int) or not 0<tid<=0xffffffff or tid in seen:raise ValueError('Invalid or duplicate CPU thread')
            seen.add(tid);keys=report['lifetimes']['thread_keys'].get(str(tid),[])
            entry=dict(tid=tid,created_filetime=row['created_filetime'],enclosing_cpu_seconds=row['cpu_seconds'],etl_thread_keys=keys)
            report['thread_reports'].append(entry)
            if len(keys)!=1:
                entry['status']='missing_or_ambiguous_etl_lifetime';continue
            life=report['lifetimes']['thread_lifetimes'].get(str(tid),[])
            entry['etl_lifetimes']=life
            if not life or not all(r['start']=='MIN' and r['end']=='MAX' for r in life):
                entry['status']='etl_thread_does_not_span_trace';continue
            entry['stacks']=stacks(run('thread-'+str(tid)+'.html','stack','-pid',source['pid'],'-tid',tid,'-butterfly','1'),source['pid'])
            entry['status']='exported'
        if digest(source['trace'])!=source['trace_sha256']:raise ValueError('ETL changed during export')
        report['completed']=True
    except Exception as e:report['error']=dict(type=type(e).__name__,message=str(e))
    publish()
    return manifest,report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('controller',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--top-threads',type=int,default=3);p.add_argument('--allow-incomplete',action='store_true')
    args=p.parse_args();path,report=export(args.controller,args.output,args.top_threads,args.allow_incomplete)
    print(json.dumps(dict(output=str(path),completed=report['completed'],error=report.get('error'),pid=report['source']['pid'],stack_observations=report.get('game_stacks',{}).get('observations'))))
    raise SystemExit(0 if report['completed'] else 1)
