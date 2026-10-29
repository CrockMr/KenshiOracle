"""Reference certification at orchestration boundaries, using synthetic games."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from fake_probe import FakeProbe
from oracle_runner import ScenarioError, execute_scenario, run_scenario_file
from test_oracle_runner import config, report_for, scenario, stability_clock
from test_rekenshi_profile import transaction, evidence, prepared, start


class ReferenceProbe(FakeProbe):
    def __init__(self, directory, tx, *, capable=True):
        super().__init__(directory)
        self.tx, self.capable = tx, capable
        self.reference_queries = 0
        self.corrupt_at = None
        self.query_failure = False

    async def call(self, command, **params):
        if command == 'get_rekenshi_settings':
            self.calls.append(command)
            self.requests.append(dict(command=command, params=deepcopy(params)))
            self.reference_queries += 1
            if self.query_failure:
                raise RuntimeError('synthetic independent verifier unavailable')
            payload = evidence(self.tx)
            if self.reference_queries == self.corrupt_at:
                payload['settings']['MaxSquadsOverride'] = True
            return payload
        result = await super().call(command, **params)
        if command in ('ping', 'heartbeat'):
            result['rekenshi_settings_available'] = self.capable
        return result


def setup_reference(tx, cfg):
    prepared(tx)
    fake = ReferenceProbe(cfg['oracle_output'], tx)
    start(tx)
    tx.observed.update(pid=42, instance_id=fake.instance_id)
    return fake


def test_new_probe_requires_reference_launcher_before_any_game_mutation(tmp_path, transaction):
    cfg = config(tmp_path)
    fake = ReferenceProbe(cfg['oracle_output'], transaction)
    with pytest.raises(ScenarioError, match='reference launcher'):
        asyncio.run(execute_scenario(scenario(), cfg, repeat=1, client=fake))
    assert fake.calls == ['ping']
    report = report_for(cfg)
    assert report['status'] == 'failed' and report['executions'] == []
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()


def test_every_execution_and_capture_has_independent_reference_provenance(tmp_path, transaction, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = setup_reference(transaction, cfg)
    result = asyncio.run(execute_scenario(scenario(), cfg, repeat=2, client=fake,
                                         reference_profile=transaction.profile))
    report = report_for(cfg)
    assert result['status'] == 'completed' and result['restored']
    assert fake.reference_queries == 1 + 2 + 4  # Preflight, each execution, each snapshot.
    assert report['reference_profile']['state'] == 'verified'
    for execution in report['executions']:
        assert execution['reference_profile']['effective']['evidence']['crt_exports_unmodified'] is True
        on_disk = json.loads((Path(report['output']) / str(execution['execution']) / 'execution.json').read_text(encoding='utf-8'))
        assert on_disk['reference_profile'] == execution['reference_profile']
        for capture in execution['checkpoints']:
            proof = capture['reference_profile']
            assert proof['state'] == 'verified' and proof['effective']['process']['pid'] == 42
            assert all(value is False for value in proof['requested'].values())
            assert 'bytes_base64' not in json.dumps(proof)
            assert str(transaction.config) not in json.dumps(proof)


def test_reference_drift_rejects_next_capture_and_keeps_prior_evidence(tmp_path, transaction, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = setup_reference(transaction, cfg)
    fake.corrupt_at = 4  # After initial capture, before the second capture.
    with pytest.raises(ScenarioError, match='reference profile'):
        asyncio.run(execute_scenario(scenario(), cfg, repeat=1, client=fake,
                                     reference_profile=transaction.profile))
    report = report_for(cfg)
    assert report['status'] == 'failed'
    assert len(report['executions'][0]['checkpoints']) == 1
    assert fake.calls.count('dump_state') == 1
    assert report['executions'][0]['checkpoints'][0]['reference_profile']['state'] == 'verified'
    assert report['reference_profile']['state'] == 'prepared'
    assert report['reference_profile']['effective'] is None
    assert report['restoration']['verified'] is True


def test_runtime_query_failure_prevents_scenario_actions(tmp_path, transaction):
    cfg = config(tmp_path)
    fake = setup_reference(transaction, cfg)
    fake.query_failure = True
    with pytest.raises(ScenarioError, match='verifier unavailable'):
        asyncio.run(execute_scenario(scenario(), cfg, repeat=1, client=fake,
                                     reference_profile=transaction.profile))
    assert not fake.loads and 'dump_state' not in fake.calls
    assert report_for(cfg)['status'] == 'failed'


def test_old_phase1_probe_remains_compatible_without_profile(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = FakeProbe(cfg['oracle_output'])
    result = asyncio.run(execute_scenario(scenario(), cfg, repeat=1, client=fake))
    assert result['status'] == 'completed'
    assert 'get_rekenshi_settings' not in fake.calls
    assert 'reference_profile' not in report_for(cfg)


def test_run_scenario_file_forwards_explicit_profile(tmp_path, transaction, monkeypatch):
    stability_clock(monkeypatch)
    cfg = config(tmp_path)
    fake = setup_reference(transaction, cfg)
    source = tmp_path / 'scenario.json'
    source.write_text(json.dumps(scenario()), encoding='utf-8')
    result = asyncio.run(run_scenario_file(source, cfg, repeat=1, client=fake,
                                           reference_profile=transaction.profile))
    assert result['status'] == 'completed'
    assert fake.reference_queries == 4
