"""Two paused reloads, bounded roster observations, no combat simulation."""
import asyncio
import hashlib
import json
from pathlib import Path
import time
from environment_diagnostics import collect,compare
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_snapshot_horizon import validate_baseline
from live_suite import wait_loaded
from probe import config,read_runtime_state
from resources import ProcessResources


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:
        raise RuntimeError('Final thirty minutes reserved for closure')
    proof_path=Path('runtime/scenarios/snapshot-20261028T022539600581Z.json')
    baseline_path=Path('runtime/scenarios/snapshot-paused-settling-075.json')
    proof=json.loads(proof_path.read_text(encoding='utf-8'))
    baseline=json.loads(baseline_path.read_text(encoding='utf-8'))['runs'][0]['observations'][0]['scene']
    snapshot=Path(proof['snapshot_path'])
    if manifest(snapshot)!=proof['snapshot_manifest']:
        raise RuntimeError('Snapshot manifest changed')
    source_proof=json.loads(Path('runtime/scenarios/battle-campaign-073-final.json').read_text(encoding='utf-8'))
    save_root=Path.home()/'AppData/Local/kenshi/save'
    if any(manifest(save_root/slot)!=data['files'] for slot,data in source_proof['save_manifests'].items()):
        raise RuntimeError('Protected saves changed')
    state_path=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state_path))['pid']
    identity=ProcessResources(pid,cfg['executable'])
    reference=await c.call('get_scene_state')
    if not reference['paused'] or reference['battle']['active'] or reference['free_camera']:
        raise RuntimeError('Requires restored test copy paused in normal camera mode')
    settings=Path(cfg['working_directory'])/'settings.cfg';before_settings=settings.read_bytes()
    output=Path('runtime/scenarios')/time.strftime('environment-preflight-%Y%m%dT%H%M%SZ.json',time.gmtime())
    data=dict(pid=pid,transport=c.transport,snapshot=proof['name'],runs=[],
        snapshot_proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        baseline_proof_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        scope='Paused update-list preflight; no simulation or performance comparison',query_limit=250)
    try:
        for _ in range(2):
            row=dict(captures=[]);data['runs'].append(row)
            await c.call('set_camera_free',enabled=True)
            old=await c.call('ping');row['load']=await c.call('load_save',name=proof['name'])
            if not row['load']['battle_tracking_restored'] or not row['load']['pause_on_ready']:
                raise RuntimeError('Managed snapshot ownership unavailable')
            row['first_ready']=await wait_loaded(c,old['frame'])
            if not row['first_ready']['paused']: raise RuntimeError('Snapshot became ready unpaused')
            await c.call('set_camera_free',enabled=True,lock_edge=True)
            started=time.monotonic()
            for delay in (0,2):
                await asyncio.sleep(max(0,delay-(time.monotonic()-started)))
                capture=await collect(c,250)
                row['captures'].append(dict(elapsed=time.monotonic()-started,**capture))
                capture['cohort_comparison']=validate_baseline(baseline,capture['scene_before'])
                row['captures'][-1]['cohort_comparison']=capture['cohort_comparison']
                if not capture['summary']['paused_at_bounds'] or not capture['summary']['clock_unchanged']:
                    raise RuntimeError('Simulation advanced during paused inventory')
                if (await read_runtime_state(state_path))['pid']!=pid: raise RuntimeError('PID changed')
            row['within_load']=compare(row['captures'][0]['summary'],row['captures'][1]['summary'])
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        data['between_loads']=compare(data['runs'][0]['captures'][-1]['summary'],data['runs'][1]['captures'][-1]['summary'])
        data['identity_interval']=identity.finish()
        data['completed']=True
    except Exception as exc:
        data['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        try:
            data['restored']=await restore_test(c,False,reference)
        except Exception as exc:
            data['restoration_error']=str(exc);raise
        finally:
            data['source_and_copy_unchanged']=all(manifest(save_root/slot)==v['files'] for slot,v in source_proof['save_manifests'].items())
            data['snapshot_unchanged']=manifest(snapshot)==proof['snapshot_manifest']
            data['settings_unchanged']=settings.read_bytes()==before_settings
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(output=str(output),completed=data.get('completed'),error=data.get('error'),
                restored=bool(data.get('restored')),source_and_copy_unchanged=data['source_and_copy_unchanged'],
                snapshot_unchanged=data['snapshot_unchanged'],settings_unchanged=data['settings_unchanged'],
                between_loads=data.get('between_loads'))),flush=True)


if __name__=='__main__': asyncio.run(run(main))
