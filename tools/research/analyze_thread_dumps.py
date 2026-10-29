"""Recheck selected dump hashes, exact thread lifetimes and same-file SDK slots.

Does not capture, attach, unwind or execute a target. Uses retained offline frame
results, with their limitations; counts of snapshots are never CPU percentages.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from benchmark import simulation_progress,validate_camera_stability
from loaded_sdk_map import compare_pointer_table
from sdk_address_map import build,annotate
from sdk_thread_roles import join_cpu
from thread_minidump import read_thread_lifetimes,read_memory_range


def analyze(path):
    path=Path(path).resolve();raw=path.read_bytes();d=json.loads(raw)
    if not d.get('completed') or d.get('error') or not d.get('capture_conditions_valid'):
        raise ValueError('Capture controller did not complete')
    if not d['protected_files_unchanged'] or not d['settings_unchanged'] or not d['final_scene']['paused']:
        raise ValueError('Restoration or protected-file verification failed')
    sources=d['static_map_sources'];m=build(sources['library']['path'],sources['rva_table']['path'],sources['executable']['path'])
    if m['sources']!=sources:raise ValueError('Static source identity changed')
    before,after=d['binding_before'],d['binding_after']
    if not before['verified'] or not after['verified'] or before['process_created_filetime']!=after['process_created_filetime']:
        raise ValueError('Loaded SDK/process binding changed')
    if before['pointer_table']['actual_sha256']!=after['pointer_table']['actual_sha256']:
        raise ValueError('Loaded SDK slots changed')
    cpu=d['process_resources']
    if cpu['pid']!=d['pid'] or cpu['before']['created_at']!=d['created_at'] or cpu['after']['created_at']!=d['created_at']:
        raise ValueError('CPU process differs')
    if join_cpu(d['roles_before'],d['roles_after'],cpu,d['pid'])!=d['sdk_role_cpu_join']:
        raise ValueError('Cached SDK role join differs')
    if simulation_progress(d['scene_before'],d['scene_after'])!=d['simulation_progress'] or d['simulation_progress']['game_hours']<=0:
        raise ValueError('Clock provenance differs')
    identities={(r['tid'],r['created_filetime']) for r in d['selected_lifetimes']};rows=[];totals=Counter()
    address=int(before['pointer_table_address'],16);size=m['resolver']['function_slot_count']*8
    game_base=int(before['modules']['executable']['base'],16)
    for sample in d['samples']:
        cap=sample['capture'];dump=Path(sample['dump']);blob=dump.read_bytes()
        if not cap['write_succeeded'] or not cap['cleanup_verified'] or len(blob)!=cap['bytes'] or hashlib.sha256(blob).hexdigest()!=cap['sha256']:
            raise ValueError('Dump content or cleanup differs')
        if cap['process_created_filetime']!=before['process_created_filetime']:raise ValueError('Dump process lifetime differs')
        actual={(r['tid'],r['created_filetime']) for r in read_thread_lifetimes(dump)}
        if actual!=identities:raise ValueError('Dump thread lifetime differs')
        binding=compare_pointer_table(read_memory_range(dump,address,size),game_base,m['slots'])
        if not binding['verified'] or binding!=sample['sdk_binding_from_dump']:raise ValueError('Same-dump SDK pairing differs')
        for scene in (sample['scene_before'],sample['scene_after']):
            validate_camera_stability(d['scene_before'],scene)
            if scene['paused'] or scene['frame_speed_multiplier']!=1:raise ValueError('Captured scene not x1')
        u=sample['offline_unwind']
        if u['returncode']!=0 or not u['result']['offline_only']:raise ValueError('Offline unwind failed')
        ids={t['tid'] for t in u['result']['threads']}
        if ids!={t for t,c in identities}:raise ValueError('Offline unwind thread selection differs')
        threads=[]
        for thread in u['result']['threads']:
            if (thread['tid'],thread['created_filetime']) not in identities or thread['stack_hresult']!='0x0':
                raise ValueError('Unwind lifetime/status differs')
            observations=[]
            for frame in thread['frames']:
                if Path(frame['image']).resolve()!=Path(sources['executable']['path']).resolve():continue
                if int(frame['module_base'],16)!=game_base:raise ValueError('Frame module base differs')
                rva=int(frame['pc'],16)-game_base;a=annotate(rva,m)
                names=[r['name'] for r in a['aliases']];totals.update(names)
                observations.append(dict(pc=frame['pc'],game_rva=hex(rva),region=a['unwind_region'],aliases=names,
                    status=a['status'],same_dump_sdk_pairing_verified=True,return_address_adjusted=False))
            threads.append(dict(tid=thread['tid'],created_filetime=thread['created_filetime'],frame_count=len(thread['frames']),
                frame_limit=thread['frame_limit'],frame_limit_reached=len(thread['frames'])==thread['frame_limit'],game_frames=observations))
        rows.append(dict(index=sample['index'],dump_sha256=cap['sha256'],bytes=cap['bytes'],capture_helper_seconds=cap['elapsed_seconds'],threads=threads))
    return dict(source=str(path),source_sha256=hashlib.sha256(raw).hexdigest(),verified=True,pid=d['pid'],admin=d['admin'],
        same_dump_sdk_slots_checked=m['resolver']['function_slot_count'],samples=rows,
        sdk_alias_frame_occurrences=dict(totals),capture_helper_seconds_total=sum(r['capture_helper_seconds'] for r in rows),
        process_cpu_elapsed_seconds=cpu['elapsed_seconds'],simulation_progress=d['simulation_progress'],
        source_pdata_anomalies=m['pdata_metadata'],
        limitations=['Four context observations are not time-weighted CPU or exclusive subsystem costs.',
            'Unwind results are retained DbgEng observations, not rerun by this analyzer.',
            'PE exception metadata is unsorted/overlapping; unique regions and ambiguity remain explicit.',
            'Original installation sources with matching hashes are required to recompute the SDK map.',
            'SDK aliases can name one shared entry; no unique source function is chosen.',
            'Helper duration includes work other than any temporary target-thread suspension; it is not a measured pause duration.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=analyze(a.source);a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),verified=result['verified'],samples=len(result['samples']),admin=result['admin'],
        same_dump_slots=result['same_dump_sdk_slots_checked'],source_sha256=result['source_sha256'])))
