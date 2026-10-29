"""Exercise existing 500-row inventory and completeness gates in paused Heng.

No performance comparison, new hook, native deployment or save write. Keeps
full/limited/full captures and always restores the pristine test view in pause.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio
import hashlib
import json
from pathlib import Path
import time
from environment_diagnostics import collect,compare,admission
from live_mcp_battle import run
from live_restore import restore_test
from live_scene_snapshot import manifest
from live_suite import wait_loaded,pause_ready
from probe import config,read_runtime_state
from resources import ProcessResources


async def main(client=None):
    c=client;cfg=config()
    if time.time()+1800>=cfg['session_until']:
        raise RuntimeError('Last thirty minutes reserved for closure')
    proof=Path('runtime/scenarios/battle-campaign-073-final.json')
    saved=json.loads(proof.read_text(encoding='utf-8'));root=Path.home()/'AppData/Local/kenshi/save'
    if any(manifest(root/slot)!=v['files'] for slot,v in saved['save_manifests'].items()):
        raise RuntimeError('Protected save manifest changed')
    state=Path(cfg['runtime'])/'state.json';pid=(await read_runtime_state(state))['pid']
    identity=ProcessResources(pid,cfg['executable'])
    settings=Path(cfg['working_directory'])/'settings.cfg';settings_before=settings.read_bytes()
    reference=await c.call('get_scene_state')
    if not reference['paused'] or reference['free_camera'] or reference['battle']['active']:
        raise RuntimeError('Requires restored copy paused in normal camera mode')
    output=Path('runtime/scenarios')/time.strftime('heavy-inventory-%Y%m%dT%H%M%SZ.json',time.gmtime())
    data=dict(pid=pid,town='Heng',transport=c.transport,captures=[],
        scope='Coverage and admission checks; no performance comparison',
        manifest_reference_sha256=hashlib.sha256(proof.read_bytes()).hexdigest())
    try:
        data['copy_loaded']=await restore_test(c,False,reference)
        data['town_preparation']=await c.call('prepare_town_scene',name='Heng')
        await pause_ready(c,False)
        await asyncio.sleep(10)
        await wait_loaded(c,0,stable_seconds=3)
        await pause_ready(c,True)
        for limit in (500,250,500):
            capture=await collect(c,limit)
            # This is a reserialization of parsed result, not the original wire.
            capture['reserialized_result_bytes']=len(json.dumps(capture['inventory'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8'))
            data['captures'].append(capture)
            if (await read_runtime_state(state))['pid']!=pid: raise RuntimeError('PID changed')
            if not capture['summary']['paused_at_bounds'] or not capture['summary']['clock_unchanged']:
                raise RuntimeError('City resumed during inventory')
        a,b,last=[x['summary'] for x in data['captures']]
        data['full_comparison']=compare(a,last)
        data['limited_admission']=admission(a,b)
        data['heavy_case_validated']=bool(a['total_update_list']>250 and a['comparable'] and last['comparable']
            and not b['complete'] and not data['limited_admission']['accepted'])
        data['identity_interval']=identity.finish();data['completed']=True
    except Exception as exc:
        data['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        try:
            data['restored']=await restore_test(c,False,reference)
        except Exception as exc:
            data['restoration_error']=str(exc);raise
        finally:
            data['source_and_copy_unchanged']=all(manifest(root/slot)==v['files'] for slot,v in saved['save_manifests'].items())
            data['settings_unchanged']=settings.read_bytes()==settings_before
            output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(output=str(output),completed=data.get('completed'),error=data.get('error'),
                heavy_case_validated=data.get('heavy_case_validated'),counts=[x['summary']['returned_count'] for x in data['captures']],
                totals=[x['summary']['total_update_list'] for x in data['captures']],
                result_bytes=[x['reserialized_result_bytes'] for x in data['captures']],restored=bool(data.get('restored')),
                source_and_copy_unchanged=data['source_and_copy_unchanged'],settings_unchanged=data['settings_unchanged'])),flush=True)


if __name__=='__main__': asyncio.run(run(main))
