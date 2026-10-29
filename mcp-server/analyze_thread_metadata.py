"""Join start-procedure metadata to CPU identities, never to current stacks."""
import argparse
import hashlib
import json
from pathlib import Path


def analyze(metadata,evidence):
    if not metadata['metadata'].get('completed') or not metadata['metadata']['cleanup_verified']:
        raise ValueError('Successful metadata capture and cleanup required')
    if metadata['pid']!=evidence['pid'] or metadata['metadata']['pid']!=metadata['pid']:
        raise ValueError('Process PID disagreement')
    entries=metadata['metadata']['threads']
    indexed={(r['tid'],r['created_filetime']):r for r in entries if r['created_filetime']!='0'}
    if len(indexed)!=sum(r['created_filetime']!='0' for r in entries):
        raise ValueError('Duplicate metadata thread identity')
    phases=[]
    for row in evidence['phases']:
        if not row.get('completed'): continue
        resources=row['process_resources']
        if (resources['pid']!=metadata['pid'] or resources['before']['created_at']!=metadata['created_at'] or
            resources['after']['created_at']!=metadata['created_at'] or
            str(Path(resources['executable']).resolve()).casefold()!=str(Path(metadata['executable']).resolve()).casefold()):
            raise ValueError('Process lifetime or executable disagreement')
        groups={};unmatched=[];interests=[];wall=resources['elapsed_seconds']
        cpu=resources['user_seconds']+resources['system_seconds']
        threads=resources['thread_cpu']['threads']
        identities={(r['tid'],r['created_filetime']) for r in threads}
        if len(identities)!=len(threads): raise ValueError('Duplicate CPU thread identity')
        for thread in threads:
            entry=indexed.get((thread['tid'],thread['created_filetime']))
            if entry is None:
                unmatched.append(dict(tid=thread['tid'],cpu_seconds=thread['cpu_seconds'],reason='No matching metadata creation identity'))
                continue
            module=entry['start_module'];key=module['path'] if module else '<unmapped>'
            if key not in groups:
                groups[key]=dict(start_module_name=module['name'] if module else None,path=key,threads=0,cpu_seconds=0)
            groups[key]['threads']+=1;groups[key]['cpu_seconds']+=thread['cpu_seconds']
            if thread['tid'] in (35716,37324,39984,32072,37196):
                interests.append(dict(tid=thread['tid'],created_filetime=thread['created_filetime'],
                    win32_start_address=entry['win32_start_address'],start_module=module,
                    cpu_seconds=thread['cpu_seconds'],logical_cpu_equivalents=thread['cpu_seconds']/wall))
        for group in groups.values():
            group['logical_cpu_equivalents']=group['cpu_seconds']/wall
            group['fraction_of_process_cpu']=group['cpu_seconds']/cpu if cpu else None
        phases.append(dict(label=row['label'],process_cpu_seconds=cpu,elapsed_seconds=wall,
            groups_by_start_module=sorted(groups.values(),key=lambda g:g['cpu_seconds'],reverse=True),
            unmatched=unmatched,unmatched_metadata_cpu_seconds=sum(r['cpu_seconds'] for r in unmatched),
            residual_cpu_seconds=resources['thread_cpu']['residual_cpu_seconds'],threads_of_interest=interests))
    return dict(pid=metadata['pid'],metadata_threads=len(entries),phases=phases,
        limits=['A start procedure can be a shared runtime wrapper and is not the current call stack.',
                'CPU belongs to whole matched threads, grouped by their start module, not exclusive module execution.',
                'Metadata and CPU were captured at different times; creation identities are required.',
                'Groups are not normalized; signed process/thread sampling residual remains.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('metadata',type=Path);p.add_argument('cpu',type=Path)
    p.add_argument('--output',type=Path,default=Path('runtime/thread-metadata-analysis.json'))
    args=p.parse_args();a,b=args.metadata.read_bytes(),args.cpu.read_bytes()
    report=dict(metadata_source=str(args.metadata),metadata_sha256=hashlib.sha256(a).hexdigest(),
        cpu_source=str(args.cpu),cpu_sha256=hashlib.sha256(b).hexdigest(),result=analyze(json.loads(a),json.loads(b)))
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),pid=report['result']['pid'],phases=len(report['result']['phases']))))
