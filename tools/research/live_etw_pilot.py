"""Two-second WPR capability pilot on the paused copy, with named cleanup.

Kernel CPU samples include system process/module metadata. Analysis must select
the verified game lifetime. No file/network/registry provider is requested.
Never stops an unrelated recording, changes profiling interval, or kills a PID.
"""

import _research_bootstrap  # Repository-relative imports for direct execution.
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT/'mcp-server'))
from probe import Client, config, read_runtime_state


def command(*args):
    result = subprocess.run([os.environ.get('KENSHI_WPR') or 'wpr.exe', *args], capture_output=True, text=True,
        errors='replace', timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


async def main():
    os.chdir(PROJECT_ROOT)
    cfg = config()
    c = Client()
    state = await read_runtime_state(Path(cfg['runtime'])/'state.json')
    process = psutil.Process(state['pid'])
    assert Path(process.exe()).resolve() == Path(cfg['executable']).resolve()
    ping = await c.call('ping')
    assert ping['paused'] and ping['world_ready']
    instance = 'KenshiProbePilot_'+uuid.uuid4().hex[:12]
    root = Path('runtime/etw')/instance
    root.mkdir(parents=True)
    trace = (root/'cpu.etl').resolve()
    profile = Path('tools/research/cpu-sampling.wprp').resolve()
    data = dict(instance=instance, pid=process.pid, executable=process.exe(),
        created_at=process.create_time(), condition='paused source copy capability pilot',
        profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(), before=ping)
    state_file = root/'controller.json'
    started = False
    try:
        data['status_before'] = command('-status')
        if 'WPR is not recording' not in data['status_before']['stdout']:
            raise RuntimeError('Existing WPR recording found; pilot refused')
        data['start'] = command('-start', str(profile)+'!KenshiCpu', '-filemode',
                                '-recordtempto', str(root.resolve()), '-instancename', instance)
        started = data['start']['returncode'] == 0
        data['cleanup_required'] = started
        state_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        if not started:
            raise RuntimeError('WPR start failed: '+data['start']['stdout']+data['start']['stderr'])
        data['recording_started_at'] = time.time()
        await asyncio.sleep(2)
        data['recording_status'] = command('-status', 'collectors', '-details', '-instancename', instance)
    except Exception as exc:
        data['error'] = str(exc)
    finally:
        if started:
            data['stop'] = command('-stop', str(trace), '-instancename', instance)
        data['status_after'] = command('-status', '-instancename', instance)
        data['cleanup_required'] = 'WPR is not recording' not in data['status_after']['stdout']
        data['after'] = await c.call('ping')
        data['trace_exists'] = trace.is_file()
        if trace.is_file():
            data['trace_bytes'] = trace.stat().st_size
            data['trace_sha256'] = hashlib.sha256(trace.read_bytes()).hexdigest()
        state_file.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(dict(output=str(state_file), error=data.get('error'),
            cleanup_required=data['cleanup_required'], trace_exists=data['trace_exists'],
            trace_bytes=data.get('trace_bytes'), game_paused=data['after']['paused'])), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
