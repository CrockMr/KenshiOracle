"""Join current CPU lifetimes, offline frame contexts and recorded SDK bases.

Only the named disposable copy is prepared. The native plugin stays unchanged.
The second filtered dump contains the SDK table, BirdManager RTTI/vftable
metadata and 24-byte ThreadClass prefixes, all explicitly bounded.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio
import ctypes as C
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from benchmark import simulation_progress,validate_camera_stability
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import pause_ready,wait_loaded
from loaded_sdk_map import verify,compare_pointer_table
from probe import config,read_runtime_state
from resources import ProcessResources
from sdk_address_map import build
from sdk_thread_roles import validate as validate_roles,join_cpu
from thread_minidump import capture,unwind,read_memory_range
from thread_object_identity import read_base,parse_base_header


async def main(client=None):
    c=client;cfg=config();state_path=Path(cfg['runtime'])/'state.json'
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    state=await read_runtime_state(state_path);pid=state['pid'];p=psutil.Process(pid)
    created=p.create_time()
    def identity():
        p=psutil.Process(pid)
        if p.create_time()!=created or Path(p.exe()).resolve()!=Path(cfg['executable']).resolve() or p.cmdline()!=[p.exe(),'--norestart']:
            raise RuntimeError('Game identity changed')
        return dict(pid=pid,executable=p.exe(),created_at=p.create_time(),cmdline=p.cmdline())
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    save_root=Path(snapshot['snapshot_path']).parent
    def protected():return all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items()) and manifest(Path(snapshot['snapshot_path']))==snapshot['snapshot_manifest']
    assert protected()
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    initial=await c.call('get_scene_state')
    assert initial['paused'] and not initial['free_camera'] and not initial['battle']['active']
    folder=ROOT/'runtime/worker-objects'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');folder.mkdir(parents=True)
    output=folder/'controller.json';sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    helper=ROOT/'plugin/build/native-tests/dump_contexts.exe'
    data=dict(identity(),transport=c.transport,admin=bool(C.windll.shell32.IsUserAnAdmin()),completed=False,world_mutations_started=False,
              objects=[],scope='SDK base and RTTI join for whole-thread CPU lifetimes; not exclusive function CPU or statistical stack sampling.')
    reference=None
    def publish():output.write_text(json.dumps(data,indent=2),encoding='utf-8')
    def clock_equal(a,b):
        if a['game_total_hours']!=b['game_total_hours']:raise RuntimeError('Paused simulation clock advanced')
    try:
        ping=await c.call('ping');data['initial_ping']=ping
        assert ping['plugin_version']=='0.8.7' and ping['set_game_speed_preserve_pause_available'] and ping['system_hook_count']==3
        address_map=build(ROOT/'Re_Kenshi/KenshiLib.dll',ROOT/'Re_Kenshi/RE_Kenshi/RVAs/Steam_1.0.65.br',cfg['executable'])
        data['map_sources']=address_map['sources'];data['binding_before']=binding=verify(pid,cfg['executable'],address_map)
        if not binding['verified'] or not binding['cleanup_verified']:raise RuntimeError('Loaded SDK pairing failed')
        base=int(binding['modules']['executable']['base'],16);table_address=int(binding['pointer_table_address'],16)
        table_size=address_map['resolver']['function_slot_count']*8
        proof_path=ROOT/'runtime/re-worker-087-static/threadproc-this-proof.json';proof=json.loads(proof_path.read_text())
        if proof['status']!='static_checks_passed' or proof['sources']['executable']['sha256']!=address_map['sources']['executable']['sha256']:
            raise RuntimeError('Static receiver proof does not match this build')
        # These metadata RVAs are recorded static observations of this exact EXE,
        # not callable SDK APIs or an invented BirdManager object layout.
        bird_vtable=0x16aad48;col=0x1816d48;type_descriptor=0x1c53d98
        image=Path(cfg['executable']).read_bytes();preferred=int(address_map['executable']['image_base'],16)
        def file_bytes(rva,size):
            sections=[s for s in address_map['executable']['sections'] if s['rva']<=rva and rva+size<=s['rva']+s['raw_size']]
            if len(sections)!=1:raise RuntimeError('Static metadata span missing/ambiguous')
            section=sections[0];at=section['raw_offset']+rva-section['rva'];return image[at:at+size]
        static_vtable=file_bytes(bird_vtable-8,40);static_col=file_bytes(col,24)
        type_name=b'.?AVBirdManager@@\0';static_type=file_bytes(type_descriptor,16+len(type_name))
        if static_type[16:]!=type_name or struct.unpack('<IIIIII',static_col)!=(1,0,0,type_descriptor,0x1816d78,col):
            raise RuntimeError('BirdManager RTTI identity differs')
        static_pointers=struct.unpack('<5Q',static_vtable)
        expected_pointers=tuple(base+x-preferred for x in static_pointers)
        data['static_metadata']=dict(vtable_rva=hex(bird_vtable),col_rva=hex(col),type_descriptor_rva=hex(type_descriptor),
                                    type_name=type_name[:-1].decode(),receiver_proof=str(proof_path),receiver_proof_sha256=sha(proof_path))
        artifacts=[Path(__file__),ROOT/'tools/research/dump_contexts.cpp',helper,ROOT/'tools/research/thread_minidump.py',
                   ROOT/'tools/research/thread_object_identity.py',ROOT/'tools/research/loaded_sdk_map.py',
                   ROOT/'Re_Kenshi/mods/KenshiProbe/KenshiProbe.dll',settings]
        data['artifacts_before']={str(f):sha(f) for f in artifacts}
        data['world_mutations_started']=True;publish()
        reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        data['town']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True)
        data['roles_before']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_before'],pid)
        await c.call('set_game_speed',speed=1);await asyncio.sleep(3)
        data['cpu_scene_before']=camera=await c.call('get_scene_state')
        assert not camera['paused'] and camera['frame_speed_multiplier']==1
        resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
        await asyncio.sleep(8)
        data['cpu_scene_after']=await c.call('get_scene_state');data['process_resources']=resources.finish()
        validate_camera_stability(camera,data['cpu_scene_after'])
        assert not data['cpu_scene_after']['paused'] and data['cpu_scene_after']['frame_speed_multiplier']==1
        data['simulation_progress']=simulation_progress(camera,data['cpu_scene_after'])
        assert data['simulation_progress']['game_hours']>0
        await pause_ready(c,True);await asyncio.sleep(1)
        data['roles_after']=paused=await c.call('get_scene_state',thread_details=True);validate_roles(paused,pid)
        data['sdk_cpu_join']=join_cpu(data['roles_before'],paused,data['process_resources'],pid)
        selected=sorted(data['process_resources']['thread_cpu']['threads'],key=lambda x:x['cpu_seconds'],reverse=True)[:4]
        data['selected_lifetimes']=selected;lifetimes=[(r['tid'],r['created_filetime']) for r in selected]
        def paused_dump(name,ranges):
            identity();row=dict(dump=str(folder/(name+'.dmp')))
            row['capture']=capture(pid,cfg['executable'],lifetimes,row['dump'],extra_memory_ranges=ranges)
            if not row['capture'].get('completed') or not row['capture']['cleanup_verified']:raise RuntimeError('Selected dump failed')
            if row['capture']['process_created_filetime']!=binding['process_created_filetime']:raise RuntimeError('Recorded process creation differs')
            row['sdk_binding_from_dump']=compare_pointer_table(read_memory_range(row['dump'],table_address,table_size),base,address_map['slots'])
            if not row['sdk_binding_from_dump']['verified']:raise RuntimeError('Recorded SDK slots disagree')
            row['unwind']=u=unwind(row['dump'],folder/(name+'.contexts.json'),ROOT/'runtime/symbols/0.8.7',ROOT/'Re_Kenshi/RE_Kenshi',helper)
            if u['returncode'] or u['result']['open_hresult']!='0x0' or u['result']['result_hresult']!='0x0':raise RuntimeError('Offline contexts failed')
            recorded={(r['tid'],r['created_filetime']) for r in row['capture']['threads']}
            for thread in u['result']['threads']:
                thread['created_filetime']=next(s for t,s in recorded if t==thread['tid'])
                if thread['stack_hresult']!='0x0' or len(thread['frames'])>=64:raise RuntimeError('Incomplete recorded context stack')
            return row
        data['discovery']=discovery=paused_dump('discovery',[(table_address,table_size)])
        await c.call('ping');after_discovery=await c.call('get_scene_state');clock_equal(paused,after_discovery)
        if not after_discovery['paused']:raise RuntimeError('Pause lost during offline discovery')
        candidates=[]
        for thread in discovery['unwind']['result']['threads']:
            frames=[f for f in thread['frames'] if int(f['pc'],16) in {base+0x25fd3a,base+0x25fe08}]
            if not frames:continue
            if len(frames)!=1:raise RuntimeError('Ambiguous ThreadWannabe frame')
            frame=frames[0]
            if frame['pc']!=frame['context_pc'] or frame['sp']!=frame['context_sp'] or int(frame['context_flags'],16)&0x100003!=0x100003:
                raise RuntimeError('Frame context does not match selected frame')
            address=int(frame['nonvolatile']['rbp'],16)
            check=read_base(pid,cfg['executable'],binding['process_created_filetime'],thread['tid'],thread['created_filetime'],address)
            data['objects'].append(dict(tid=thread['tid'],created_filetime=thread['created_filetime'],address=hex(address),discovery_frame=frame,live_candidate_check=check))
            if not check['verified'] or not check['cleanup_verified']:raise RuntimeError('SDK base candidate failed identity checks')
            candidates.append((address,24))
        if not candidates or len(candidates)>4 or len(set(candidates))!=len(candidates):raise RuntimeError('No unique bounded SDK base candidates')
        ranges=[(table_address,table_size),(base+bird_vtable-8,40),(base+col,24),(base+type_descriptor,len(static_type))]+candidates
        data['confirmation']=confirmation=paused_dump('confirmation',ranges)
        # All fields below come from the confirmation file, never a live fallback.
        if struct.unpack('<5Q',read_memory_range(confirmation['dump'],base+bird_vtable-8,40))!=expected_pointers:
            raise RuntimeError('Recorded BirdManager vftable pointers differ')
        if read_memory_range(confirmation['dump'],base+col,24)!=static_col:raise RuntimeError('Recorded RTTI locator differs')
        if read_memory_range(confirmation['dump'],base+type_descriptor+16,len(type_name))!=type_name:raise RuntimeError('Recorded RTTI type differs')
        data['same_dump_rtti_verified']=True
        for obj in data['objects']:
            thread=next(r for r in confirmation['unwind']['result']['threads'] if (r['tid'],r['created_filetime'])==(obj['tid'],obj['created_filetime']))
            frames=[f for f in thread['frames'] if int(f['pc'],16) in {base+0x25fd3a,base+0x25fe08}]
            if len(frames)!=1 or int(frames[0]['nonvolatile']['rbp'],16)!=int(obj['address'],16):raise RuntimeError('Receiver identity changed in confirmation dump')
            frame=frames[0]
            if frame['context_pc']!=frame['pc'] or frame['context_sp']!=frame['sp']:raise RuntimeError('Confirmation context mismatched')
            obj['confirmation_frame']=frame
            header=parse_base_header(read_memory_range(confirmation['dump'],int(obj['address'],16),24),obj['tid'])
            obj['base_from_same_dump']=header;obj['bird_manager_vptr_matched']=int(header['vptr'],16)==base+bird_vtable
            if header['vptr']!=obj['live_candidate_check']['base_header']['vptr']:raise RuntimeError('Candidate vptr changed')
        data['bird_manager_objects']=[dict(tid=o['tid'],created_filetime=o['created_filetime'],address=o['address']) for o in data['objects'] if o['bird_manager_vptr_matched']]
        if len(data['bird_manager_objects'])!=1:raise RuntimeError('BirdManager receiver missing/ambiguous')
        data['scene_after_metadata']=await c.call('get_scene_state');clock_equal(paused,data['scene_after_metadata'])
        assert data['scene_after_metadata']['paused'];validate_camera_stability(paused,data['scene_after_metadata'])
        identity();data['binding_after']=verify(pid,cfg['executable'],address_map)
        if not data['binding_after']['verified'] or data['binding_after']['process_created_filetime']!=binding['process_created_filetime']:
            raise RuntimeError('SDK binding changed')
        if any(sha(f)!=data['artifacts_before'][str(f)] for f in artifacts):raise RuntimeError('Source/helper/configuration changed during capture')
        data['dynamic_join_valid']=True
    except Exception as e:data['error']=dict(type=type(e).__name__,message=str(e))
    finally:
        if data['world_mutations_started']:
            try:
                data['restored']=await restore_test(c,False,reference,lock_edge=True)
                if reference:clock_equal(reference,data['restored'])
            except Exception as e:data['restoration_error']=str(e)
            try:
                identity();data['cleanup_pause']=await c.call('pause',paused=True)
                data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as e:data['camera_release_error']=str(e)
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before
        data['final_scene']=await c.call('get_scene_state',thread_details=True)
        data['completed']=bool(data.get('dynamic_join_valid') and not any(data.get(k) for k in ['error','restoration_error','camera_release_error']) and
                               data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and not data['final_scene']['scene_camera_control_owned'])
        publish()
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),restoration_error=data.get('restoration_error'),
                              bird_manager=data.get('bird_manager_objects'),admin=data['admin'],protected_files_unchanged=data['protected_files_unchanged'])),flush=True)


if __name__=='__main__':
    os.chdir(ROOT);asyncio.run(run(main))
