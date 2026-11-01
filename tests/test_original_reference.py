"""Exercise cold-process ownership and profile cleanup with synthetic processes."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

import original_reference as reference
from rekenshi_profile import REQUESTED_SETTINGS, RUNTIME_METHOD

SCENARIO = dict(schema_version='0.1', name='synthetic-reference', save='synthetic',
                speed=1, repeat=1, actions=[], checkpoints=[dict(at=0, name='initial')])


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    module = tmp_path / 'RE_Kenshi.dll'
    module.write_bytes(b'audited synthetic module')
    exe = tmp_path / 'kenshi_x64.exe'
    exe.write_bytes(b'synthetic executable; never launched')
    ini = tmp_path / 'RE_Kenshi.ini'
    original = (json.dumps(dict.fromkeys(REQUESTED_SETTINGS, True), indent=4) + '\n').encode()
    ini.write_bytes(original)
    settings = tmp_path / 'settings.cfg'
    settings.write_bytes(b'player settings\n')
    cfg = dict(rekenshi_module=str(module), rekenshi_config=str(ini), executable=str(exe),
               working_directory=str(tmp_path), runtime=str(tmp_path / 'runtime'),
               oracle_output=str(tmp_path / 'dumps'), runs=str(tmp_path / 'runs'))
    ctx = SimpleNamespace(cfg=cfg, original=original, ini=ini, settings=settings,
                          events=[], fail=None, games=[])
    monkeypatch.setattr(reference, 'SUPPORTED_REK_HASH', reference.file_hash(module))

    class FakeGame:
        def __init__(self, cfg, output):
            self.process, self.client, self.running = None, self, False
            self.label, self.started, self.instance = None, None, None
            ctx.games.append(self)

        def state(self):
            return (dict(running=True, owned=True, pid=1234, instance_id=self.instance,
                         started_at=self.started) if self.running else dict(running=False, owned=False))

        async def start(self, label):
            assert not self.running
            self.running, self.label = True, label
            self.started, self.instance = time.time() + .01, label
            self.process = SimpleNamespace(poll=lambda: None if self.running else 0)
            ctx.events.append(label + '_start')
            settings.write_bytes(b'changed by synthetic game')
            return dict(process_id=1234, instance_id=label, game_version='1.0.65 Steam')

        async def stop(self):
            if self.running:
                ctx.events.append(self.label + '_stop')
            self.running = False

        async def wait_ping(self, **kwargs):
            return {}

        async def settings_evidence(self):
            return await self.call('get_rekenshi_settings')

        async def call(self, command, **params):
            if command != 'get_rekenshi_settings':
                return {}
            current = json.loads(ini.read_text())
            unchanged = not current['FixRNG']
            prefix = '90' * 16
            rows = {symbol: dict(symbol=symbol, export_rva=4096 + i * 32,
                disk_file_offset=1024 + i * 32, checked_bytes=16, disk_prefix_hex=prefix,
                memory_prefix_hex=prefix if unchanged else 'cc' * 16, relocation_overlap=False,
                unmodified=unchanged, comparison='identical' if unchanged else 'different')
                for i, symbol in enumerate(('rand', 'srand'))}
            payload = dict(settings=current, verification_method=RUNTIME_METHOD, evidence_source='runtime_ui',
                process_id=1234, instance_id=self.instance, module_path=str(module), crt_exports=rows,
                crt_exports_unmodified=unchanged, crt_exports_modified=not unchanged,
                runtime_settings_consistent=True, effective_fix_rng_disabled=unchanged)
            if ctx.fail == self.label:
                payload['crt_exports_unmodified'] = not unchanged
            return payload

    class FakeSession:
        def __init__(self, *args):
            pass

        async def load(self, *args, **kwargs):
            return {}

        async def call(self, *args, **kwargs):
            return {}

    async def execute(scenario, cfg, *, repeat, client, reference_profile):
        ctx.events.append('execute')
        proof = reference_profile.provenance()
        assert proof['state'] == 'verified'
        assert proof['effective']['evidence']['settings'] == REQUESTED_SETTINGS
        if ctx.fail == 'execute':
            raise RuntimeError('synthetic scenario failure')
        path = tmp_path / 'report.json'
        path.write_text(json.dumps(dict(status='completed')))
        return dict(report=str(path), status='completed', restored=True)

    monkeypatch.setattr(reference, 'ReferenceGame', FakeGame)
    monkeypatch.setattr(reference, 'OracleSession', FakeSession)
    monkeypatch.setattr(reference, 'execute_scenario', execute)
    return ctx


def test_complete_reference_cycle_restores_bytes_and_effective_profile(lifecycle):
    ctx = lifecycle
    result = asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert result['reference_restored']
    assert ctx.events == ['reference_start', 'execute', 'reference_stop', 'restoration_start', 'restoration_stop']
    report = json.loads(Path(result['reference_report']).read_text())
    assert report['completed'] and report['reference_profile']['restoration']['runtime_verified']
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not ctx.games[0].running


def test_initially_absent_game_settings_are_removed_after_owned_boot(lifecycle):
    ctx = lifecycle
    ctx.settings.unlink()
    asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert not ctx.settings.exists()


def test_game_settings_backup_survives_controller_loss(lifecycle):
    ctx = lifecycle
    runtime = Path(ctx.cfg['runtime'])
    runtime.mkdir()
    journal = runtime / 'reference-game-settings.json'
    reference.preserve_game_settings(ctx.settings, journal)
    ctx.settings.write_bytes(b'synthetic process change')
    assert reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == b'player settings\n'


@pytest.mark.parametrize('failure', ['reference', 'execute', 'restoration'])
def test_failed_verification_or_scenario_still_stops_and_restores(lifecycle, failure):
    ctx = lifecycle
    ctx.fail = failure
    with pytest.raises(RuntimeError):
        asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not ctx.games[0].running
    if failure == 'reference':
        assert 'execute' not in ctx.events
    report_path, = Path(ctx.cfg['runtime']).glob('reference-lifecycle/*/report.json')
    report = json.loads(report_path.read_text())
    assert report['completed'] is False
    assert report['reference_profile']['restoration']['file_verified']
    assert report['reference_profile']['restoration']['runtime_verified'] is (failure != 'restoration')


@pytest.mark.parametrize('pid,created,owned', [(7, 42, False), (9, 43, False), (9, 42, True)])
def test_process_inventory_never_adopts_foreign_or_reused_pid(tmp_path, monkeypatch, pid, created, owned):
    exe = tmp_path / 'kenshi_x64.exe'
    game = reference.ReferenceGame(dict(executable=str(exe)), tmp_path)
    game.process = SimpleNamespace(pid=9, poll=lambda: None)
    game.identity, game.instance = 42, 'owned-instance'
    process = SimpleNamespace(pid=pid, info=dict(name='kenshi_x64.exe'),
                              create_time=lambda: created, exe=lambda: str(exe))
    monkeypatch.setattr(reference.psutil, 'process_iter', lambda _: [process])
    assert game.state()['owned'] is owned


def settings_transaction(ctx):
    runtime = Path(ctx.cfg['runtime'])
    runtime.mkdir(exist_ok=True)
    journal = runtime / 'reference-game-settings.json'
    reference.preserve_game_settings(ctx.settings, journal)
    return journal


def read_settings_journal(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_game_settings_journal_is_bound_to_exact_target(lifecycle, tmp_path):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    other = tmp_path / 'other-settings.cfg'
    other.write_bytes(b'other player settings\n')
    before = journal.read_bytes()
    with pytest.raises(RuntimeError, match='damaged'):
        reference.restore_game_settings(other, journal, lambda: dict(running=False))
    assert other.read_bytes() == b'other player settings\n'
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert journal.read_bytes() == before
    assert read_settings_journal(journal)['restore_required'] is True


def test_missing_expected_game_settings_journal_does_not_claim_restoration(lifecycle):
    ctx = lifecycle
    missing = Path(ctx.cfg['runtime']) / 'missing.json'
    with pytest.raises(RuntimeError, match='missing'):
        reference.restore_game_settings(ctx.settings, missing, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not missing.exists()


def test_oversized_game_settings_are_rejected_before_journaling(lifecycle):
    ctx = lifecycle
    ctx.settings.write_bytes(b'x' * (1024 * 1024 + 1))
    runtime = Path(ctx.cfg['runtime'])
    runtime.mkdir()
    journal = runtime / 'reference-game-settings.json'
    with pytest.raises(RuntimeError, match='size limit'):
        reference.preserve_game_settings(ctx.settings, journal)
    assert not journal.exists()
    assert ctx.settings.stat().st_size == 1024 * 1024 + 1


@pytest.mark.parametrize('operation', ['preserve', 'restore'])
def test_oversized_game_settings_journal_is_not_read_unbounded(lifecycle, operation):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    journal.write_bytes(b' ' * (2 * 1024 * 1024 + 1))
    before = ctx.settings.read_bytes()
    with pytest.raises(RuntimeError, match='size limit'):
        if operation == 'preserve':
            reference.preserve_game_settings(ctx.settings, journal)
        else:
            reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == before
    assert journal.stat().st_size == 2 * 1024 * 1024 + 1


@pytest.mark.parametrize('mutation', [
    lambda value: value.update(sha256='0' * 64),
    lambda value: value.update(target_sha256='0' * 64),
    lambda value: value.update(existed=1),
    lambda value: value.update(existed=False),
    lambda value: value.update(bytes_base64=base64.b64encode(b'changed backup').decode()),
])
def test_corrupt_game_settings_recovery_record_never_overwrites_target(lifecycle, mutation):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    record = read_settings_journal(journal)
    mutation(record)
    journal.write_text(json.dumps(record), encoding='utf-8')
    ctx.settings.write_bytes(b'current player settings\n')
    with pytest.raises(RuntimeError, match='damaged'):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == b'current player settings\n'
    assert read_settings_journal(journal)['restore_required'] is True


def test_pending_game_settings_backup_cannot_be_replaced(lifecycle):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    original_journal = journal.read_bytes()
    ctx.settings.write_bytes(b'game already changed settings\n')
    with pytest.raises(RuntimeError, match='interrupted'):
        reference.preserve_game_settings(ctx.settings, journal)
    assert journal.read_bytes() == original_journal
    assert ctx.settings.read_bytes() == b'game already changed settings\n'


@pytest.mark.parametrize('target', ['settings', 'journal', 'parent'])
def test_game_settings_reparse_paths_are_rejected_before_restoration(lifecycle, monkeypatch, target):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    guarded = {'settings': ctx.settings, 'journal': journal, 'parent': journal.parent}[target]
    original_lstat = Path.lstat

    def reparse_lstat(path):
        original = original_lstat(path)
        if path == guarded:
            return SimpleNamespace(st_mode=original.st_mode, st_file_attributes=0x400)
        return original

    monkeypatch.setattr(Path, 'lstat', reparse_lstat)
    with pytest.raises(RuntimeError, match='reparse'):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert read_settings_journal(journal)['restore_required'] is True


def test_atomic_game_settings_restore_failure_keeps_recovery_required(lifecycle, monkeypatch):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    ctx.settings.write_bytes(b'game changed settings\n')
    original_replace = Path.replace

    def failing_replace(path, target):
        if Path(target) == ctx.settings:
            raise OSError('synthetic atomic replacement failure')
        return original_replace(path, target)

    monkeypatch.setattr(Path, 'replace', failing_replace)
    with pytest.raises(OSError, match='synthetic'):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=False))
    assert ctx.settings.read_bytes() == b'game changed settings\n'
    assert read_settings_journal(journal)['restore_required'] is True
    assert not list(ctx.settings.parent.glob('settings.cfg.*.tmp'))


def test_game_start_during_existing_settings_restore_prevents_replacement(lifecycle):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    ctx.settings.write_bytes(b'game changed settings\n')
    observed = iter((False, True))
    with pytest.raises(RuntimeError):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=next(observed)))
    assert ctx.settings.read_bytes() == b'game changed settings\n'
    assert read_settings_journal(journal)['restore_required'] is True


def test_game_start_during_absence_restore_prevents_deleting_live_settings(lifecycle):
    ctx = lifecycle
    ctx.settings.unlink()
    journal = settings_transaction(ctx)
    ctx.settings.write_bytes(b'live game settings\n')
    observed = iter((False, True))
    with pytest.raises(RuntimeError):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=next(observed)))
    assert ctx.settings.read_bytes() == b'live game settings\n'
    assert read_settings_journal(journal)['restore_required'] is True


@pytest.mark.parametrize('unknown', [None, 0, ''])
def test_unknown_process_state_never_authorizes_game_settings_restoration(lifecycle, unknown):
    ctx = lifecycle
    journal = settings_transaction(ctx)
    ctx.settings.write_bytes(b'current settings\n')
    with pytest.raises(RuntimeError):
        reference.restore_game_settings(ctx.settings, journal, lambda: dict(running=unknown))
    assert ctx.settings.read_bytes() == b'current settings\n'
    assert read_settings_journal(journal)['restore_required'] is True


@pytest.mark.parametrize('repeat', [0, 101, True, 1.5, '2'])
def test_invalid_repeat_is_rejected_before_process_or_settings_transaction(lifecycle, repeat):
    ctx = lifecycle
    with pytest.raises(ValueError, match='repeat'):
        asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=repeat))
    assert ctx.games == [] and ctx.events == []
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not Path(ctx.cfg['runtime']).exists()


def test_configuration_target_mismatch_is_rejected_before_any_transaction(lifecycle, tmp_path):
    ctx = lifecycle
    other = tmp_path / 'other' / 'RE_Kenshi.ini'
    other.parent.mkdir()
    other.write_bytes(ctx.original)
    ctx.cfg['rekenshi_config'] = str(other)
    with pytest.raises(ValueError, match='working directory'):
        asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert ctx.games == [] and ctx.events == []
    assert other.read_bytes() == ctx.original and ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not Path(ctx.cfg['runtime']).exists()


def test_wrong_audited_module_is_rejected_before_any_transaction(lifecycle):
    ctx = lifecycle
    Path(ctx.cfg['rekenshi_module']).write_bytes(b'unrecognized synthetic module')
    with pytest.raises(ValueError, match='audited'):
        asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert ctx.games == [] and ctx.events == []
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'
    assert not Path(ctx.cfg['runtime']).exists()


SQUAD_LINE = b'Squad size multiplier=1'


@pytest.mark.parametrize('raw,line', [
    (b'Global population multiplier=1\nSquad size multiplier=1\nraidSizeMult=1\n', SQUAD_LINE),
    (b'\xef\xbb\xbfSquad size multiplier=1\r\nAuto save=0\r\n', SQUAD_LINE),
    (b'other=2\r\n  SQUAD Size Multiplier \t= 1.0 \r', b'  SQUAD Size Multiplier \t= 1.0 '),
    (b'squad size multiplier=1.5e0', b'squad size multiplier=1.5e0'),
])
def test_squad_size_line_and_hash_come_from_preserved_bytes(raw, line):
    facts = reference.squad_size_facts(raw)
    assert facts == dict(source='engine_facts', multiplier=float(line.partition(b'=')[2]),
                         line=line.decode(), sha256=hashlib.sha256(line).hexdigest(), path='settings.cfg')


@pytest.mark.parametrize('raw,match', [
    (None, 'found 0'),
    (b'', 'found 0'),
    (b'Squad size multiplier\n', 'found 0'),
    (b'Squad size multiplier1=1\nsquad-size multiplier=1\n', 'found 0'),
    (b'Squad size multiplier=1\nsquad size multiplier=2\n', 'found 2'),
    (b'Squad size multiplier=\n', 'finite decimal'),
    (b'Squad size multiplier=inf\n', 'finite decimal'),
    (b'Squad size multiplier=1_0\n', 'finite decimal'),
    (b'Squad size multiplier=1e999\n', 'finite decimal'),
    (b'Squad size multiplier=1\xff\n', 'finite decimal'),
])
def test_missing_ambiguous_or_unparsable_squad_size_line_raises(raw, match):
    with pytest.raises(RuntimeError, match=match):
        reference.squad_size_facts(raw)


def test_preserve_returns_the_journaled_bytes(lifecycle):
    ctx = lifecycle
    ctx.settings.write_bytes(b'Squad size multiplier=1\n')
    runtime = Path(ctx.cfg['runtime'])
    runtime.mkdir()
    journal = runtime / 'reference-game-settings.json'
    raw = reference.preserve_game_settings(ctx.settings, journal)
    assert base64.b64decode(read_settings_journal(journal)['bytes_base64']) == raw == b'Squad size multiplier=1\n'


def setup_cycle(ctx, monkeypatch):
    received = {}

    async def execute(scenario, cfg, *, repeat, client, reference_profile, engine_facts):
        ctx.events.append('execute')
        received.update(engine_facts)
        path = Path(cfg['runtime']) / 'report.json'
        path.write_text(json.dumps(dict(status='completed')))
        return dict(report=str(path), status='completed', restored=True)

    monkeypatch.setattr(reference, 'validate_scenario', lambda scenario: scenario)
    monkeypatch.setattr(reference, 'execute_scenario', execute)
    return dict(SCENARIO, schema_version='scenario-0.2', setup={}), received


def test_setup_scenario_receives_engine_facts_from_preserved_settings(lifecycle, monkeypatch):
    ctx = lifecycle
    ctx.settings.write_bytes(b'Auto save=0\nSquad size multiplier=1\n')
    scenario, received = setup_cycle(ctx, monkeypatch)
    result = asyncio.run(reference.run_original_reference(scenario, ctx.cfg, repeat=1))
    expected = dict(squad_size=reference.squad_size_facts(b'Squad size multiplier=1'))
    assert received == expected
    assert json.loads(Path(result['reference_report']).read_text())['engine_facts'] == expected
    assert ctx.settings.read_bytes() == b'Auto save=0\nSquad size multiplier=1\n'


def test_setup_scenario_without_squad_size_line_fails_before_launch(lifecycle, monkeypatch):
    ctx = lifecycle
    scenario, received = setup_cycle(ctx, monkeypatch)
    with pytest.raises(RuntimeError, match='Squad size multiplier'):
        asyncio.run(reference.run_original_reference(scenario, ctx.cfg, repeat=1))
    assert ctx.games[0].label is None and 'execute' not in ctx.events and received == {}
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'player settings\n'


def test_setup_scenario_refuses_before_launch_when_the_runner_cannot_take_engine_facts(lifecycle, monkeypatch):
    ctx = lifecycle
    ctx.settings.write_bytes(b'Squad size multiplier=1\n')
    scenario, received = setup_cycle(ctx, monkeypatch)

    async def execute(scenario, cfg, *, repeat, client, reference_profile):
        ctx.events.append('execute')

    monkeypatch.setattr(reference, 'execute_scenario', execute)
    with pytest.raises(RuntimeError, match='cannot apply scene setup'):
        asyncio.run(reference.run_original_reference(scenario, ctx.cfg, repeat=1))
    assert ctx.games[0].label is None and 'execute' not in ctx.events
    assert ctx.ini.read_bytes() == ctx.original
    assert ctx.settings.read_bytes() == b'Squad size multiplier=1\n'


def test_scenario_without_setup_records_no_engine_facts(lifecycle):
    ctx = lifecycle
    result = asyncio.run(reference.run_original_reference(SCENARIO, ctx.cfg, repeat=1))
    assert 'engine_facts' not in json.loads(Path(result['reference_report']).read_text())


@pytest.mark.parametrize('name', ['config.example.json', 'config.meitou.example.json'])
def test_example_configs_name_a_local_engine_profile(name):
    cfg = json.loads((Path(__file__).resolve().parents[1] / name).read_text(encoding='utf-8'))
    assert cfg['engine_profile'] == 'runtime/engine-profile.json'
