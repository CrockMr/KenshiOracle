"""Validate CPU-off AI identity in Heng through real MCP, then restore the copy.

No WPR session or administrator token is required. Standalone absolute-path entry.
This is an attribution/availability check, not a performance comparison.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2]
for directory in (ROOT,ROOT/'mcp-server',ROOT/'tests'):sys.path.insert(0,str(directory))
import psutil
from ai_diagnostics import validate,match_cpu
from benchmark import validate_camera_stability,simulation_progress
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import wait_loaded,pause_ready
from probe import Client,ProbeError,config,read_runtime_state
from resources import ProcessResources
from sdk_thread_roles import validate as validate_roles,join_cpu


async def capture(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:raise RuntimeError('Closure window reserved')
    await wait_loaded(c,0)
    expected=json.loads((ROOT/'runtime/scenarios/battle-campaign-073-final.json').read_text())
    snapshot=json.loads((ROOT/'runtime/scenarios/snapshot-20261028T022539600581Z.json').read_text())
    snapshot_path=Path(snapshot['snapshot_path']);save_root=snapshot_path.parent
    if any(manifest(save_root/k)!=v['files'] for k,v in expected['save_manifests'].items()):raise RuntimeError('Protected save mismatch')
    if manifest(snapshot_path)!=snapshot['snapshot_manifest']:raise RuntimeError('Protected snapshot mismatch')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid']
    def identity():
        p=psutil.Process(pid)
        if Path(p.exe()).resolve()!=Path(cfg['executable']).resolve():raise RuntimeError('Wrong game executable')
        return dict(pid=pid,executable=p.exe(),created_at=p.create_time(),cmdline=p.cmdline())
    output=ROOT/'runtime/scenarios'/('ai-identity-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    data=dict(identity(),transport=c.transport,observations=[],world_mutations_started=False,completed=False,
        scope='CPU-off identity and whole-thread join validation; no optimization or exclusive coverage claim.')
    entry=await c.call('get_scene_state')
    if not entry['paused'] or entry['free_camera'] or entry['battle']['active']:raise RuntimeError('Requires paused test copy')
    data['initial_ping']=ping=await c.call('ping')
    if ping['plugin_version']!='0.8.3' or ping['system_hook_count']!=3 or ping['ai_thread_cpu_enabled']:
        raise RuntimeError('Requires 0.8.3 with three probes and AI CPU off')
    if ping.get('ai_thread_identity_mode')!='tls_creation_once' or not ping.get('ai_thread_identity_independent_of_cpu'):
        raise RuntimeError('Missing independent TLS identity capability')
    if ping['ai_profiled_function']!='AI::update4Frame' or not ping['ai_profiling']:raise RuntimeError('Unexpected AI probe')
    data['configuration_fingerprints']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [settings,Path(cfg['executable']),Path(cfg['working_directory'])/'data/mods.cfg',Path(cfg['working_directory'])/'mods/KenshiProbe/KenshiProbe.dll',Path(__file__)]}
    reference=None
    def publish():output.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    try:
        # Raw protocol omission, rather than MCP's default-injected false.
        data['raw_optional_camera_flag']=await Client().call('set_camera_free',enabled=False)
        try:await Client().call('set_camera_free',enabled=False,lock_edge='invalid')
        except ProbeError as e:data['raw_invalid_camera_flag_rejected']=str(e)
        else:raise RuntimeError('Native optional flag accepted a string')
        data['world_mutations_started']=True;publish()
        reference=await restore_test(c,False,lock_edge=True);data['source_reference']=reference
        data['town']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False);await asyncio.sleep(10);await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True);await asyncio.sleep(1)
        data['roles_before']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_before'],pid)
        await c.call('set_game_speed',speed=1);await asyncio.sleep(3)
        data['scene_before']=camera=await c.call('get_scene_state')
        if camera['paused'] or camera['frame_speed_multiplier']!=1:raise RuntimeError('x1 not active')
        resources=ProcessResources(pid,cfg['executable'],sample_threads=True)
        started=time.monotonic()
        while time.monotonic()-started<10:
            await asyncio.sleep(.5);scene=await c.call('get_scene_state')
            validate_camera_stability(camera,scene)
            if scene['paused'] or scene['frame_speed_multiplier']!=1:raise RuntimeError('x1 changed')
            if identity()['created_at']!=data['created_at'] or (await read_runtime_state(state_path))['pid']!=pid:
                raise RuntimeError('Game lifetime changed')
            data['observations'].append(dict(elapsed=time.monotonic()-started,scene=scene))
        # Collect the function window while the OS interval is still open, then
        # read its enclosing scene bound. A later stats request can advance frames.
        data['statistics_tail']=stats=await c.call('get_frame_stats',n=600,detail='full')
        data['scene_after']=await c.call('get_scene_state');validate_camera_stability(camera,data['scene_after'])
        data['process_resources']=resources.finish()
        data['simulation_progress']=simulation_progress(camera,data['scene_after'])
        if data['simulation_progress']['game_hours']<=0:raise RuntimeError('Clock did not advance')
        total=validate(stats)
        if total['cpu_enabled'] or total.get('thread_identity_mode')!='tls_creation_once' or not total['calls_total']:
            raise RuntimeError('No CPU-off AI calls measured')
        rows=[total,total['unlisted']]+total['threads']
        if any(r['cpu_available_calls'] or r['cpu_user_total_ms'] is not None or r['cpu_kernel_total_ms'] is not None for r in rows):
            raise RuntimeError('CPU-off values reported as measured')
        if not total['threads'] or any(r['created_filetime'] is None for r in total['threads']):
            raise RuntimeError('AI identity unavailable')
        if not camera['frame']<=stats['first_frame']<=stats['last_frame']<=data['scene_after']['frame']:
            raise RuntimeError('Function tail not contained by measured scene interval')
        data['ai_thread_cpu_join']=matched=match_cpu(total,data['process_resources'])
        if not all(r['matched_cpu_identity'] for r in matched['threads']):raise RuntimeError('CPU-off identity did not join OS')
        await pause_ready(c,True)
        data['roles_after']=await c.call('get_scene_state',thread_details=True);validate_roles(data['roles_after'],pid)
        data['role_cpu_join']=join_cpu(data['roles_before'],data['roles_after'],data['process_resources'],pid)
        data['measured_conditions_valid']=True
    except Exception as e:data['error']=dict(type=type(e).__name__,message=str(e))
    finally:
        if data['world_mutations_started']:
            try:
                data['restored']=await restore_test(c,False,reference,lock_edge=True)
            except Exception as e:data['restoration_error']=str(e)
            try:
                await c.call('pause',paused=True)
                data['camera_release']=await c.call('set_camera_free',enabled=False,release_edge=True)
            except Exception as e:data['camera_release_error']=str(e)
        try:
            data['source_and_copy_unchanged']=all(manifest(save_root/k)==v['files'] for k,v in expected['save_manifests'].items())
            data['old_snapshot_unchanged']=manifest(snapshot_path)==snapshot['snapshot_manifest']
            after=settings.read_bytes();data['settings_unchanged']=after==settings_before
            if after!=settings_before:
                output.with_suffix('.settings-before.cfg').write_bytes(settings_before)
                output.with_suffix('.settings-after.cfg').write_bytes(after)
            data['final_scene']=await c.call('get_scene_state')
        except Exception as e:data['verification_error']=str(e)
        data['completed']=bool(data.get('measured_conditions_valid') and not any(data.get(k) for k in
            ('error','restoration_error','camera_release_error','verification_error')) and
            data.get('source_and_copy_unchanged') and data.get('old_snapshot_unchanged') and data.get('settings_unchanged') and
            data.get('final_scene',{}).get('paused') and not data.get('final_scene',{}).get('scene_camera_control_owned'))
        publish()
        print(json.dumps(dict(output=str(output),completed=data['completed'],error=data.get('error'),restoration_error=data.get('restoration_error'),
            matched_ai_threads=data.get('ai_thread_cpu_join',{}).get('threads'),settings_unchanged=data['settings_unchanged'])),flush=True)


if __name__=='__main__':
    os.chdir(ROOT)
    asyncio.run(run(capture))
