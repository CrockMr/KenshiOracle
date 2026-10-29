"""Four bounded selected-thread dumps in Heng x1, restore, then unwind offline.

This is contextual execution evidence, not time-weighted CPU profiling. The dump
also records the SDK pointer table whose layout/stubs were independently verified.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import asyncio
import ctypes as C
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(folder))
import psutil
from benchmark import validate_camera_stability,simulation_progress
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import wait_loaded,pause_ready
from loaded_sdk_map import verify,compare_pointer_table
from probe import config,read_runtime_state
from resources import ProcessResources
from sdk_address_map import build,annotate
from sdk_thread_roles import validate as validate_roles,join_cpu
from stack_snapshot import DBGHELP
from thread_minidump import capture,unwind,read_memory_range


async def capture_heng(source,client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    source=Path(source).resolve();baseline=json.loads(source.read_bytes())
    phase=next(p for p in baseline['phases'] if p['label']=='running_x1' and p['completed'])
    if not baseline.get('completed'):raise RuntimeError('Requires completed CPU source')
    pid=baseline['pid'];created=phase['process_resources']['before']['created_at']
    state_path=Path(cfg['runtime'])/'state.json'
    def identity():
        p=psutil.Process(pid)
        if p.create_time()!=created or Path(p.exe()).resolve()!=Path(cfg['executable']).resolve():raise RuntimeError('Game identity changed')
        return dict(pid=pid,executable=p.exe(),created_at=p.create_time(),cmdline=p.cmdline())
    if (await read_runtime_state(state_path))['pid']!=pid:raise RuntimeError('CPU source process is no longer current')
    selected=sorted(phase['process_resources']['thread_cpu']['threads'],key=lambda r:r['cpu_seconds'],reverse=True)[:3]
    lifetimes=[(r['tid'],r['created_filetime']) for r in selected]
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    def protected():return all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items()) and manifest(snapshot_path)==snapshot['snapshot_manifest']
    if not protected():raise RuntimeError('Protected files changed')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    entry=await c.call('get_scene_state')
    if not entry['paused'] or entry['free_camera'] or entry['battle']['active']:raise RuntimeError('Requires restored paused copy')
    root=ROOT/'runtime/stacks'/('heng-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));root.mkdir(parents=True)
    output=root/'controller.json'
    data=dict(identity(),source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),selected_lifetimes=selected,
        transport=c.transport,admin=bool(C.windll.shell32.IsUserAnAdmin()),samples=[],world_mutations_started=False,completed=False,
        scope='Four selected-thread user stacks with observer interruptions; not statistical CPU sampling or an optimization comparison.')
    data['initial_ping']=await c.call('ping')
    data['configuration_fingerprints']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [settings,Path(cfg['executable']),Path(cfg['working_directory'])/'data/mods.cfg',Path(cfg['working_directory'])/'mods/KenshiProbe/KenshiProbe.dll']}
    reference=None;address_map=None
    def publish():output.write_text(json.dumps(data,indent=2),encoding='utf-8')
    try:
        address_map=build(ROOT/'Re_Kenshi/KenshiLib.dll',ROOT/'Re_Kenshi/RE_Kenshi/RVAs/Steam_1.0.65.br',cfg['executable'])
        data['static_map_sources']=address_map['sources'];data['static_resolver']=address_map['resolver']
        data['pdata_metadata']=address_map['pdata_metadata']
        data['binding_before']=binding=verify(pid,cfg['executable'],address_map)
        if not binding['verified'] or not binding['cleanup_verified']:raise RuntimeError('Loaded SDK pairing not verified')
        metadata_address=int(binding['pointer_table_address'],16);metadata_bytes=address_map['resolver']['function_slot_count']*8
        data['world_mutations_started']=True;publish()
        reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        data['town']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True)
        data['roles_before']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_before'],pid)
        await c.call('set_game_speed',speed=1);await asyncio.sleep(3)
        data['scene_before']=camera=await c.call('get_scene_state')
        if camera['paused'] or camera['frame_speed_multiplier']!=1:raise RuntimeError('x1 not active')
        resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
        started=time.perf_counter();data['sample_offsets_requested']=[0,2.3,4.4,7.1]
        for index,offset in enumerate(data['sample_offsets_requested']):
            await asyncio.sleep(max(0,started+offset-time.perf_counter()))
            if time.time()+300>=cfg['session_until']:raise RuntimeError('Leaving time for restoration')
            before=await c.call('get_scene_state');validate_camera_stability(camera,before)
            if before['paused'] or before['frame_speed_multiplier']!=1:raise RuntimeError('x1 changed')
            if identity()['created_at']!=data['created_at']:raise RuntimeError('Game lifetime changed')
            row=dict(index=index,elapsed_seconds=time.perf_counter()-started,scene_before=before,dump=str(root/('sample-'+str(index)+'.dmp')))
            data['samples'].append(row);publish()
            row['capture']=capture(pid,cfg['executable'],lifetimes,row['dump'],extra_memory=(metadata_address,metadata_bytes))
            if not row['capture'].get('completed') or not row['capture']['cleanup_verified']:raise RuntimeError('Minidump capture/cleanup failed')
            if row['capture']['process_created_filetime']!=binding['process_created_filetime']:raise RuntimeError('Dump process FILETIME differs')
            table=read_memory_range(row['dump'],metadata_address,metadata_bytes)
            row['sdk_binding_from_dump']=compare_pointer_table(table,int(binding['modules']['executable']['base'],16),address_map['slots'])
            if not row['sdk_binding_from_dump']['verified']:raise RuntimeError('SDK table in this dump disagrees')
            row['scene_after']=after=await c.call('get_scene_state');validate_camera_stability(camera,after)
            if after['paused'] or after['frame_speed_multiplier']!=1:raise RuntimeError('x1 changed across dump')
            publish();print(json.dumps(dict(stage='dump_recorded',index=index,bytes=row['capture']['bytes'],capture_seconds=row['capture']['elapsed_seconds'])),flush=True)
        data['scene_after']=await c.call('get_scene_state');data['process_resources']=resources.finish()
        data['simulation_progress']=simulation_progress(camera,data['scene_after'])
        if data['simulation_progress']['game_hours']<=0:raise RuntimeError('Clock did not advance')
        await pause_ready(c,True)
        data['roles_after']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_after'],pid)
        data['sdk_role_cpu_join']=join_cpu(data['roles_before'],data['roles_after'],data['process_resources'],pid)
        data['binding_after']=verify(pid,cfg['executable'],address_map)
        if not data['binding_after']['verified'] or data['binding_after']['process_created_filetime']!=binding['process_created_filetime']:
            raise RuntimeError('SDK binding changed after capture')
        data['capture_conditions_valid']=True
    except Exception as e:data['error']=dict(type=type(e).__name__,message=str(e))
    finally:
        if data['world_mutations_started']:
            try:data['restored']=await restore_test(c,False,reference,lock_edge=True)
            except Exception as e:data['restoration_error']=str(e)
            try:
                await c.call('pause',paused=True)
                data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as e:data['camera_release_error']=str(e)
        data['protected_files_unchanged']=protected();data['settings_unchanged']=settings.read_bytes()==settings_before
        data['final_scene']=await c.call('get_scene_state')
        publish()
    # Engine/image loading and symbol formatting occur only after restoration.
    if data.get('capture_conditions_valid') and address_map is not None:
        try:
            d=C.WinDLL(str(DBGHELP),use_last_error=True,winmode=0x1100)
            d.UnDecorateSymbolName.argtypes=[C.c_char_p,C.c_char_p,C.c_uint32,C.c_uint32];d.UnDecorateSymbolName.restype=C.c_uint32
            cache={}
            def demangle(name):
                if name not in cache:
                    out=C.create_string_buffer(4096);n=d.UnDecorateSymbolName(name.encode('ascii'),out,len(out),0)
                    cache[name]=out.value.decode('ascii',errors='replace') if n else None
                return cache[name]
            for row in data['samples']:
                row['offline_unwind']=u=unwind(row['dump'],Path(row['dump']).with_suffix('.stacks.json'),ROOT/'runtime/symbols/0.8.5',
                    ROOT/'Re_Kenshi',ROOT/'plugin/build/native-tests/dump_stacks.exe')
                if u['returncode']!=0:raise RuntimeError('Offline unwind failed')
                recorded={(r['tid'],r['created_filetime']) for r in row['capture']['threads']}
                for thread in u['result']['threads']:
                    thread['created_filetime']=next(c for t,c in recorded if t==thread['tid'])
                    if thread['stack_hresult']!='0x0':raise RuntimeError('One recorded stack failed to unwind')
                    for i,frame in enumerate(thread['frames']):
                        if Path(frame['image']).name.lower()!='kenshi_x64.exe':continue
                        if int(frame['module_base'],16)!=int(binding['modules']['executable']['base'],16):raise RuntimeError('Dump image base differs')
                        rva=int(frame['pc'],16)-int(frame['module_base'],16);annotation=annotate(rva,address_map)
                        annotation.update(original_pc=frame['pc'],return_address_adjusted=False,loaded_table_in_same_dump_verified=True)
                        for alias in annotation['aliases']:alias['undecorated']=demangle(alias['name'])
                        frame['sdk_annotation']=annotation
            data['offline_analysis_valid']=True
        except Exception as e:data['offline_analysis_error']=str(e)
    data['completed']=bool(data.get('capture_conditions_valid') and data.get('offline_analysis_valid') and
        not any(data.get(k) for k in ('error','restoration_error','camera_release_error','offline_analysis_error')) and
        data['protected_files_unchanged'] and data['settings_unchanged'] and data['final_scene']['paused'] and
        not data['final_scene']['scene_camera_control_owned'])
    publish()
    print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),offline_error=data.get('offline_analysis_error'),
        samples=len(data['samples']),admin=data['admin'],protected_files_unchanged=data['protected_files_unchanged'],settings_unchanged=data['settings_unchanged'])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);args=p.parse_args()
    os.chdir(ROOT);asyncio.run(run(capture_heng,args.source))
