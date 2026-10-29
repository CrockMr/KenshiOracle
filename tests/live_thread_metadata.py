"""Validate remote metadata on an owned helper before optional paused game read."""
import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
import psutil
from benchmark import validate_camera_stability
from probe import Client,config,read_runtime_state
from resources import ProcessResources
from thread_metadata import WindowsThreadMetadata
from thread_resources import WindowsThreadSampler


def helper():
    self_file=Path('runtime/thread-metadata-self.json')
    if not json.loads(self_file.read_text(encoding='utf-8'))['self_validation_passed']:
        raise RuntimeError('Local metadata capability proof required')
    target=Path('tests/metadata_target.py').resolve()
    child=subprocess.Popen([sys.executable,'-u',str(target)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    data=dict(self_proof_sha256=hashlib.sha256(self_file.read_bytes()).hexdigest(),wrapper_pid=child.pid)
    owned=None
    try:
        target_info=json.loads(child.stdout.readline())
        owned=psutil.Process(target_info['pid']);created=owned.create_time();executable=owned.exe()
        if owned.pid!=child.pid and child.pid not in [p.pid for p in owned.parents()]:
            raise RuntimeError('Target is not the owned child')
        if str(target) not in owned.cmdline(): raise RuntimeError('Target command mismatch')
        resources=ProcessResources(owned.pid,executable)
        cpu=WindowsThreadSampler(owned.pid)();identities={r['tid']:r.get('created_filetime') for r in cpu['threads']}
        data['metadata']=WindowsThreadMetadata().capture(owned.pid,executable)
        data['identity_interval']=resources.finish()
        data['target']=dict(pid=owned.pid,created_at=created,executable=executable,worker_tid=target_info['worker_tid'])
        matching=[r for r in data['metadata']['threads'] if r['tid']==target_info['worker_tid']]
        data['worker_creation_matches']=len(matching)==1 and matching[0]['created_filetime']==identities.get(target_info['worker_tid'])
        data['remote_validation_passed']=bool(data['metadata'].get('completed') and data['metadata']['cleanup_verified'] and data['worker_creation_matches'])
    except Exception as exc:
        data['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        # Request normal shutdown only on the fresh, explicitly owned identity.
        if owned is not None and owned.is_running():
            current=psutil.Process(owned.pid)
            if current.create_time()!=created or current.exe()!=executable or str(target) not in current.cmdline():
                raise RuntimeError('Helper identity changed before shutdown')
            data['stop_identity_verified']=True
        stdout,stderr=child.communicate('\n',timeout=35)
        data['helper_exit_code']=child.returncode;data['helper_stderr']=stderr
        data['remote_validation_passed']=bool(data.get('remote_validation_passed') and child.returncode==0)
        output=Path('runtime/thread-metadata-remote-helper.json')
        output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(output=str(output),passed=data.get('remote_validation_passed'),
            capture_error=data.get('metadata',{}).get('error'),cleanup=data.get('metadata',{}).get('cleanup'),exit_code=child.returncode)),flush=True)


async def game():
    cfg=config()
    if time.time()+1800>=cfg['session_until']: raise RuntimeError('Closure window reserved')
    helper_proof=Path('runtime/thread-metadata-remote-helper.json')
    if not json.loads(helper_proof.read_text(encoding='utf-8'))['remote_validation_passed']:
        raise RuntimeError('Remote owned-helper validation required')
    state=await read_runtime_state(Path(cfg['runtime'])/'state.json')
    resources=ProcessResources(state['pid'],cfg['executable'])
    c=Client();before=await c.call('get_scene_state')
    if not before['paused'] or before['free_camera'] or before['battle']['active']:
        raise RuntimeError('Requires restored test copy paused in normal view')
    metadata=WindowsThreadMetadata().capture(state['pid'],cfg['executable'])
    identity=resources.finish();after=await c.call('get_scene_state')
    validate_camera_stability(before,after)
    if not after['paused'] or after['game_total_hours']!=before['game_total_hours']:
        raise RuntimeError('Paused game state changed during metadata read')
    data=dict(observed_at=time.time(),pid=state['pid'],created_at=identity['before']['created_at'],
        executable=identity['executable'],helper_proof_sha256=hashlib.sha256(helper_proof.read_bytes()).hexdigest(),
        metadata=metadata,identity_interval=identity,before=before,after=after)
    output=Path('runtime/thread-metadata-game.json')
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),completed=metadata.get('completed'),error=metadata.get('error'),
        cleanup=metadata['cleanup'],threads=len(metadata['threads']),paused=after['paused'])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--game',action='store_true');args=p.parse_args()
    if args.game: asyncio.run(game())
    else: helper()
