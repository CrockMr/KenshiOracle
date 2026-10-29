"""Isolated target selection, opt-in launch flags and seed provenance, without sockets."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from fake_probe import FakeProbe
from launcher.meitou_watchdog import launch_config
from oracle_runner import (OracleSession, ScenarioError, execute_scenario,
                           restore_interrupted_scenario, seed_value)
from oracle_targets import target_config
from test_oracle_origin_integration import (SAVE_NAME, read_guard, read_report,
                                            source_bytes, source_fixture)
from test_oracle_runner import scenario, stability_clock


class MeitouProbe(FakeProbe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_saved_origins = False
        self.seed = '77'
        self.seed_before_load = True
        self.load_seeds = []
        self.fail_seed = None
        self.fail_before = None
        self.after_dump = None
        self.dump_count = 0

    async def call(self, command, **params):
        if command == 'load_save':
            self.load_seeds.append(params.get('seed'))
            if 'seed' in params:
                self.seed = params['seed']
            self.seed_before_load = True
        result = await super().call(command, **params)
        if command in ('ping', 'heartbeat'):
            result.update(target='meitou', seed=self.seed,
                          seed_applied_before_load=self.seed_before_load,
                          seed_source='oracle_load_override', saved_origins_required=False)
            if self.load_seeds and len(self.load_seeds) == self.fail_seed:
                result['seed'] = str(int(self.seed) + 1)
            if self.load_seeds and len(self.load_seeds) == self.fail_before:
                result['seed_applied_before_load'] = False
        if command == 'dump_state':
            self.dump_count += 1
            if self.after_dump:
                self.after_dump(self.dump_count)
        return result


def meitou(tmp_path):
    fake, cfg, manifest, saved, folder = source_fixture(tmp_path, probe_class=MeitouProbe)
    cfg.update(target='meitou', base_seed=900)
    return fake, cfg, manifest, saved, folder


def test_meitou_load_binds_same_source_fingerprint_without_native_registration(tmp_path):
    fake, cfg, manifest, saved, folder = meitou(tmp_path)
    before = source_bytes(folder)
    loaded = asyncio.run(OracleSession(cfg, fake).load(SAVE_NAME, seed=2**64-1))
    assert loaded['source_manifest'] == dict(prepared=True, save_name=SAVE_NAME,
        source_fingerprint=manifest['fingerprint'], count=3)
    assert loaded['ready']['seed'] == str(2**64-1)
    assert fake.load_seeds == [str(2**64-1)]
    assert source_bytes(folder) == before
    assert not any(command in fake.calls for command in ('resolve_saved_handles', 'begin_saved_origins',
                                                       'register_saved_origins', 'commit_saved_origins'))


@pytest.mark.parametrize('value', [None, True, False, -1, 2**64, 1.0, '1.5', '-1', 'unknown', '\u0661'])
def test_seed_requires_known_unsigned_integer(value):
    with pytest.raises(ScenarioError, match='known unsigned'):
        seed_value(value)


@pytest.mark.parametrize('fault', ['fail_seed', 'fail_before'])
def test_load_rejects_wrong_seed_or_application_after_loading(tmp_path, fault):
    fake, cfg, *_ = meitou(tmp_path)
    setattr(fake, fault, 1)
    with pytest.raises(ScenarioError, match='requested seed before save loading'):
        asyncio.run(OracleSession(cfg, fake).load(SAVE_NAME, seed=901))
    assert fake.load_seeds == ['901']


@pytest.mark.parametrize('seed,before,base,repeat', [
    (None, True, 0, 1), ('unknown', True, 0, 1), ('77', False, 0, 1),
    ('77', True, 2**64-1, 2), ('77', True, -1, 1), ('77', True, True, 1)])
def test_invalid_initial_seed_or_repetition_overflow_prevents_game_mutation(tmp_path, seed, before, base, repeat):
    fake, cfg, *_ = meitou(tmp_path)
    fake.seed, fake.seed_before_load = seed, before
    cfg['base_seed'] = base
    with pytest.raises(ScenarioError, match='seed'):
        asyncio.run(execute_scenario(scenario(), cfg, repeat=repeat, client=fake))
    assert fake.calls == ['ping']
    assert not fake.loads
    assert not (Path(cfg['runtime']) / 'oracle-restoration.json').exists()


def test_repetitions_seed_each_load_and_restore_original_seed_with_capture_provenance(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    fake, cfg, manifest, saved, folder = meitou(tmp_path)
    before = source_bytes(folder)
    result = asyncio.run(execute_scenario(scenario(), cfg, repeat=3, client=fake))
    assert result['status'] == 'completed'
    assert fake.load_seeds == ['900', '901', '902', '77']
    assert fake.seed == '77'
    assert source_bytes(folder) == before
    report = read_report(cfg)
    assert report['source_fingerprint'] == manifest['fingerprint']
    for index, execution in enumerate(report['executions']):
        provenance = dict(target='meitou', seed=str(900+index), seed_source='oracle_load_override', seed_applied_before_load=True)
        assert execution['provenance'] == provenance
        assert execution['load']['source_manifest']['source_fingerprint'] == manifest['fingerprint']
        for capture in execution['checkpoints']:
            assert capture['provenance'] == provenance
    assert read_guard(cfg)['original_seed'] == '77'
    assert read_guard(cfg)['restore_required'] is False


def test_repetition_rejects_changed_starting_save_fingerprint(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    fake, cfg, *_rest, folder = meitou(tmp_path)
    quick = folder / 'quick.save'
    original = quick.read_bytes()
    def drift(count):
        if count == 2:
            assert b'Synthetic record' in original
            quick.write_bytes(original.replace(b'Synthetic record', b'Different record'))
    fake.after_dump = drift
    with pytest.raises(ScenarioError, match='Starting save changed'):
        asyncio.run(execute_scenario(scenario(), cfg, repeat=2, client=fake))
    report = read_report(cfg)
    assert report['executions'][0]['status'] == 'completed'
    assert report['executions'][1]['status'] != 'completed'
    assert fake.load_seeds[-1] == '77'


def test_recovery_restores_persisted_original_seed_and_rejects_missing_seed_record(tmp_path, monkeypatch):
    stability_clock(monkeypatch)
    fake, cfg, *_ = meitou(tmp_path)
    asyncio.run(execute_scenario(scenario(), cfg, repeat=1, client=fake))
    path = Path(cfg['runtime']) / 'oracle-restoration.json'
    guard = read_guard(cfg)
    guard['restore_required'] = True
    path.write_text(json.dumps(guard), encoding='utf-8')
    fake.seed = '888'
    result = asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert result['restored'] is True
    assert fake.load_seeds[-1] == '77' and fake.seed == '77'
    guard.update(restore_required=True)
    del guard['original_seed']
    path.write_text(json.dumps(guard), encoding='utf-8')
    before = len(fake.load_seeds)
    with pytest.raises(ScenarioError, match='known unsigned'):
        asyncio.run(restore_interrupted_scenario(cfg, client=fake))
    assert len(fake.load_seeds) == before


def target_files(tmp_path, **updates):
    path = tmp_path / 'meitou.json'
    configured = dict(target='meitou', port=53123, runtime='meitou-runtime', oracle_output='meitou-output')
    configured.update(updates)
    path.write_text(json.dumps(configured), encoding='utf-8')
    return dict(port=53122, runtime=str(tmp_path / 'original-runtime'), meitou_config=str(path))


def test_target_selection_and_opt_in_flags_keep_original_configuration_unchanged(tmp_path):
    original = target_files(tmp_path)
    baseline = deepcopy(original)
    assert target_config(original) is original
    selected = target_config(original, 'meitou')
    assert selected['port'] == 53123 and selected['runtime'] != original['runtime']
    assert selected['state_schema'] == '0.2'
    selected['arguments'] = ['--no-precompile', '--seed', '17']
    before = deepcopy(selected)
    launched = launch_config(selected)
    assert launched['arguments'] == [*selected['arguments'], '--oracle', '--oracle-port', '53123',
                                     '--oracle-output', str(Path(selected['oracle_output']).resolve())]
    assert selected == before and original == baseline


@pytest.mark.parametrize('updates', [dict(port=53122), dict(port=True), dict(port=0), dict(port=65536),
                                    dict(runtime='original-runtime'), dict(target='original')])
def test_target_selection_rejects_shared_runtime_port_and_wrong_target(tmp_path, updates):
    with pytest.raises(ValueError):
        target_config(target_files(tmp_path, **updates), 'meitou')


@pytest.mark.parametrize('updates', [dict(target='original'), dict(port=47800), dict(port=True),
    dict(port=0), dict(port=65536), dict(arguments='--oracle'), dict(arguments=[True]),
    dict(arguments=['--oracle']), dict(arguments=['--oracle-port=53123']), dict(arguments=['--oracle-output=x'])])
def test_launch_rejects_implicit_or_conflicting_adapter_options(tmp_path, updates):
    cfg = dict(target='meitou', port=53123, oracle_output=str(tmp_path / 'output'), arguments=[])
    cfg.update(updates)
    before = deepcopy(cfg)
    with pytest.raises(ValueError):
        launch_config(cfg)
    assert cfg == before


def test_unknown_target_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='original or meitou'):
        target_config(target_files(tmp_path), 'unrecognised')


def test_oversized_decimal_seed_is_rejected_before_python_integer_conversion():
    with pytest.raises(ScenarioError, match='known unsigned'):
        seed_value('9' * 5000)


@pytest.mark.skipif(os.name != 'nt', reason='Windows paths are case insensitive')
def test_runtime_alias_differing_only_by_windows_case_is_rejected(tmp_path):
    original = target_files(tmp_path, runtime='ORIGINAL-RUNTIME')
    with pytest.raises(ValueError, match='runtime'):
        target_config(original, 'meitou')


def test_configured_target_must_match_runtime_ping_before_mutation(tmp_path):
    fake, cfg, *_ = meitou(tmp_path)
    cfg['target'] = 'original'
    with pytest.raises(ScenarioError, match='target'):
        asyncio.run(OracleSession(cfg, fake).load(SAVE_NAME, seed=7))
    assert fake.calls == ['ping']
    assert fake.load_seeds == []


def test_unknown_configured_target_is_rejected_before_ping(tmp_path):
    fake, cfg, *_ = meitou(tmp_path)
    cfg['target'] = 'unknown'
    with pytest.raises(ValueError, match='target'):
        OracleSession(cfg, fake)
    assert fake.calls == []
