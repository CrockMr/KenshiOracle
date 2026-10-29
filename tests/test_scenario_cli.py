"""Exercise the standalone command through real subprocesses and fake TCP."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

from fake_probe import FakeProbe
from oracle_schema import canonical_bytes, load_state


ROOT = Path(__file__).resolve().parents[1]


async def command(*args):
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'launcher', *map(str, args), cwd=ROOT,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
    return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')


def fixture_files(tmp_path, port):
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps(dict(port=port, runtime=str(tmp_path/'runtime'),
        runs=str(tmp_path/'runs'), oracle_output=str(tmp_path/'native'),
        timeout=2, load_timeout=2, run_until_timeout=2, scenario_timeout=20)), encoding='utf-8')
    scenario = tmp_path / 'scenario.json'
    scenario.write_text(json.dumps(dict(schema_version='0.1', name='cli-fixture',
        save='Synthetic save', speed=1, repeat=1, actions=[],
        checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])), encoding='utf-8')
    return cfg, scenario


def test_cli_runs_repeats_and_validates_canonical_files_without_mcp(tmp_path):
    async def run():
        async with FakeProbe(tmp_path/'native') as fake:
            cfg, scenario = fixture_files(tmp_path, fake.port)
            code, stdout, stderr = await command('run-scenario', scenario, '--config', cfg,
                                                  '--repeat', 3, '--prepare')
            assert code == 0, stderr
            result = json.loads(stdout)
            assert result['restored'] is True and result['executions'] == 3
            report = json.loads(Path(result['report']).read_text(encoding='utf-8'))
            assert report['status'] == 'completed' and report['restoration']['verified']
            assert Path(result['summary']).is_file()
            for execution in report['executions']:
                for capture in execution['checkpoints']:
                    payload = Path(capture['path']).read_bytes()
                    assert payload == canonical_bytes(load_state(capture['path']))
                    assert hashlib.sha256(payload).hexdigest() == capture['sha256']
            assert len(fake.loads) == 5  # preparation, three runs, restoration
    asyncio.run(run())


def test_cli_preparation_refuses_to_overwrite_pending_restoration(tmp_path):
    async def run():
        async with FakeProbe(tmp_path/'native') as fake:
            cfg, scenario = fixture_files(tmp_path, fake.port)
            runtime = tmp_path/'runtime'
            runtime.mkdir()
            guard = runtime/'oracle-restoration.json'
            payload = b'{"restore_required": true}\n'
            guard.write_bytes(payload)
            code, _, stderr = await command('run-scenario', scenario, '--config', cfg, '--prepare')
            assert code == 1 and 'restore-scenario' in stderr
            assert guard.read_bytes() == payload and fake.loads == []
    asyncio.run(run())


def test_cli_failed_run_returns_failure_and_preserves_verified_cleanup(tmp_path):
    async def run():
        async with FakeProbe(tmp_path/'native', mode='run_timeout') as fake:
            cfg, scenario = fixture_files(tmp_path, fake.port)
            code, _, stderr = await command('run-scenario', scenario, '--config', cfg, '--prepare')
            assert code == 1 and 'report:' in stderr
            report_path, = (tmp_path/'runs').glob('*/*/report.json')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            assert report['status'] == 'failed' and report['restoration']['verified']
            guard = json.loads((tmp_path/'runtime/oracle-restoration.json').read_text(encoding='utf-8'))
            assert guard['restore_required'] is False
    asyncio.run(run())


def test_cli_rejects_invalid_repeat_before_connecting():
    code, _, stderr = asyncio.run(command('run-scenario', 'absent.json', '--repeat', 101))
    assert code == 2 and 'repeat must be between 1 and 100' in stderr
