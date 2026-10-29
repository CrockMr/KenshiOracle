"""Synthetic settings/process transactions; never launch or contact a game."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import rekenshi_profile as profile_module
from rekenshi_profile import (KNOWN_DEVIATIONS, REQUESTED_SETTINGS, RUNTIME_METHOD,
                              ReKenshiProfile, ReKenshiProfileError)


METADATA = {'kenshi_version': '1.0.65', 'rekenshi_version': '0.3.5',
            'rekenshi_sha256': 'a' * 64, 'executable_sha256': 'b' * 64}


@pytest.fixture
def transaction(tmp_path):
    settings = dict.fromkeys(REQUESTED_SETTINGS, True)
    settings.update(GameSpeeds=[1, 2, 5, 20], HeightmapMode=2, PlayerNote='été')
    raw = b'\xef\xbb\xbf' + (json.dumps(settings, ensure_ascii=False, indent=4) + '\r\n').encode()
    config = tmp_path / 'game' / 'RE_Kenshi.ini'
    config.parent.mkdir()
    config.write_bytes(raw)
    journal = tmp_path / 'runtime' / 'rekenshi-profile.json'
    observed = {'running': False, 'owned': False}
    profile = ReKenshiProfile(config, journal, process_state=lambda: dict(observed), metadata=METADATA)
    return SimpleNamespace(config=config, journal=journal, original=raw, observed=observed, profile=profile)


def start(tx, *, restore=False):
    journal = json.loads(tx.journal.read_text(encoding='utf-8'))
    tx.observed.update(running=True, owned=True, pid=1234, instance_id='synthetic-instance',
                       started_at=journal['restored_at' if restore else 'prepared_at'] + .01)


def evidence(tx, *, restore=False):
    settings = (json.loads(tx.original.decode('utf-8-sig')) if restore else REQUESTED_SETTINGS)
    settings = {key: settings[key] for key in REQUESTED_SETTINGS}
    unchanged = not settings['FixRNG']
    rows = {symbol: {'symbol': symbol, 'export_rva': 4096 + i * 32,
                     'disk_file_offset': 1024 + i * 32, 'checked_bytes': 16,
                     'disk_prefix_hex': '90' * 16,
                     'memory_prefix_hex': ('90' if unchanged else 'cc') * 16,
                     'unmodified': unchanged, 'relocation_overlap': False,
                     'comparison': 'identical' if unchanged else 'different'}
            for i, symbol in enumerate(('rand', 'srand'))}
    return {'settings': settings, 'verification_method': RUNTIME_METHOD,
            'evidence_source': 'runtime_ui', 'process_id': tx.observed['pid'],
            'instance_id': tx.observed['instance_id'], 'crt_exports': rows,
            'crt_exports_unmodified': unchanged, 'crt_exports_modified': not unchanged,
            'runtime_settings_consistent': True, 'effective_fix_rng_disabled': unchanged,
            'rng_hook_owner_verified': False}


def prepared(tx):
    tx.profile.capture()
    tx.profile.prepare()


def test_capture_is_durable_before_prepare_and_retains_exact_original(transaction):
    tx = transaction
    result = tx.profile.capture()
    journal = json.loads(tx.journal.read_text(encoding='utf-8'))
    assert tx.config.read_bytes() == tx.original
    assert base64.b64decode(journal['original']['bytes_base64']) == tx.original
    assert journal['original']['sha256'] == hashlib.sha256(tx.original).hexdigest()
    assert result['restore_required'] and result['effective'] is None
    result = tx.profile.prepare()
    changed = json.loads(tx.config.read_text(encoding='utf-8'))
    assert all(changed[key] is False for key in REQUESTED_SETTINGS)
    assert changed['GameSpeeds'] == [1, 2, 5, 20]
    assert changed['HeightmapMode'] == 2 and changed['PlayerNote'] == 'été'
    assert result['known_deviations'] == KNOWN_DEVIATIONS
    assert str(tx.config) not in json.dumps(result)
    assert 'bytes_base64' not in json.dumps(result)


def test_verified_run_and_separate_runtime_restoration(transaction):
    tx = transaction
    prepared(tx)
    start(tx)
    result = tx.profile.verify_effective(evidence(tx))
    assert result['state'] == 'verified'
    assert result['effective']['evidence']['crt_exports_unmodified'] is True
    tx.observed.update(running=False, owned=False)
    result = tx.profile.restore()
    assert tx.config.read_bytes() == tx.original
    assert result['restore_required'] is False
    assert result['restoration']['file_verified'] is True
    assert result['restoration']['runtime_verified'] is False
    start(tx, restore=True)
    result = tx.profile.verify_restored_effective(evidence(tx, restore=True))
    assert result['restoration']['runtime_verified'] is True
    assert result['restoration']['effective']['evidence']['rng_hook_owner_verified'] is False


def test_recovery_after_controller_loss_uses_journal_not_constructor_metadata(transaction):
    tx = transaction
    prepared(tx)
    recovered = ReKenshiProfile(tx.config, tx.journal, process_state=lambda: tx.observed)
    assert recovered.provenance()['restore_required'] is True
    assert recovered.restore()['restoration']['file_verified'] is True
    assert tx.config.read_bytes() == tx.original


@pytest.mark.parametrize('operation', ['capture', 'prepare', 'restore'])
@pytest.mark.parametrize('owned', [False, True])
def test_never_mutates_settings_while_game_runs(transaction, operation, owned):
    tx = transaction
    if operation != 'capture':
        tx.profile.capture()
    before = tx.config.read_bytes()
    tx.observed.update(running=True, owned=owned, pid=1234,
                       instance_id='synthetic-instance', started_at=1)
    with pytest.raises(ReKenshiProfileError) as failure:
        getattr(tx.profile, operation)()
    assert failure.value.code == ('process_running' if owned else 'unowned_process')
    assert tx.config.read_bytes() == before


@pytest.mark.parametrize('raw', [
    b'{"FixRNG":true,"FixRNG":false}', b'[]', b'{"FixRNG":0}',
    b'{"FixRNG":true,"UseCustomGameSpeeds":null}', b'{"value":NaN}',
    b'{"value":1e9999}', b'\xff\xfe\x00', b'{"nested":{"x":1,"x":2}}',
])
def test_rejects_ambiguous_or_ill_typed_settings_before_mutation(transaction, raw):
    tx = transaction
    tx.config.write_bytes(raw)
    with pytest.raises(ReKenshiProfileError):
        tx.profile.capture()
    assert tx.config.read_bytes() == raw
    assert not tx.journal.exists()


def test_unknown_process_state_is_not_assumed_stopped(transaction):
    tx = transaction
    tx.observed.clear()
    with pytest.raises(ReKenshiProfileError, match='explicit running'):
        tx.profile.capture()
    assert not tx.journal.exists()


@pytest.mark.parametrize('mutation', [
    lambda p: p.pop('crt_exports'),
    lambda p: p.update(verification_method='read_RE_Kenshi.ini'),
    lambda p: p.update(evidence_source='settings_file'),
    lambda p: p.update(process_id=999),
    lambda p: p.update(instance_id='stale-instance'),
    lambda p: p.update(crt_exports_unmodified=False),
    lambda p: p.update(runtime_settings_consistent=False),
    lambda p: p.update(effective_fix_rng_disabled=False),
    lambda p: p['settings'].update(FixRNG=True),
    lambda p: p['settings'].update(MaxSquadsOverride=True),
    lambda p: p['settings'].update(FixRNG=0),
    lambda p: p['crt_exports']['rand'].update(memory_prefix_hex='cc' * 16),
    lambda p: p['crt_exports']['rand'].update(checked_bytes=8),
    lambda p: p['crt_exports']['rand'].update(relocation_overlap=True),
    lambda p: p['crt_exports']['rand'].update(comparison='different'),
])
def test_config_false_alone_or_inconsistent_live_evidence_is_never_certified(transaction, mutation):
    tx = transaction
    prepared(tx)
    start(tx)
    payload = evidence(tx)
    mutation(payload)
    with pytest.raises(ReKenshiProfileError):
        tx.profile.verify_effective(payload)
    provenance = tx.profile.provenance()
    assert provenance['state'] == 'prepared' and provenance['effective'] is None
    assert provenance['restore_required'] is True


def test_validator_injection_cannot_waive_core_invariants(transaction):
    tx = transaction
    prepared(tx)
    start(tx)
    with pytest.raises(ReKenshiProfileError):
        tx.profile.verify_effective({'settings': REQUESTED_SETTINGS}, validator=lambda value, expected: value)


def test_live_process_must_have_started_after_prepare(transaction):
    tx = transaction
    prepared(tx)
    start(tx)
    tx.observed['started_at'] = 1
    with pytest.raises(ReKenshiProfileError) as failure:
        tx.profile.verify_effective(evidence(tx))
    assert failure.value.code == 'cold_start_required'


def test_changed_player_settings_after_capture_are_not_overwritten(transaction):
    tx = transaction
    tx.profile.capture()
    changed = tx.original + b' '
    tx.config.write_bytes(changed)
    with pytest.raises(ReKenshiProfileError) as failure:
        tx.profile.prepare()
    assert failure.value.code == 'source_changed'
    assert tx.config.read_bytes() == changed


def test_failed_prepare_leaves_durable_recovery_record(transaction, monkeypatch):
    tx = transaction
    tx.profile.capture()
    original = profile_module._atomic
    def fail_config(path, data, before_replace=None):
        if Path(path) == tx.config:
            raise OSError('synthetic config replacement failure')
        return original(path, data, before_replace)
    monkeypatch.setattr(profile_module, '_atomic', fail_config)
    with pytest.raises(OSError):
        tx.profile.prepare()
    journal = json.loads(tx.journal.read_text(encoding='utf-8'))
    assert journal['state'] == 'prepare_failed' and journal['restore_required'] is True
    monkeypatch.setattr(profile_module, '_atomic', original)
    tx.profile.restore()
    assert tx.config.read_bytes() == tx.original


def test_restore_write_failure_cannot_claim_restoration(transaction, monkeypatch):
    tx = transaction
    prepared(tx)
    original = profile_module._atomic
    def fail_config(path, data, before_replace=None):
        if Path(path) == tx.config:
            raise OSError('synthetic restore failure')
        return original(path, data, before_replace)
    monkeypatch.setattr(profile_module, '_atomic', fail_config)
    with pytest.raises(OSError):
        tx.profile.restore()
    provenance = tx.profile.provenance()
    assert provenance['state'] == 'restore_failed' and provenance['restore_required'] is True
    assert provenance['restoration']['file_verified'] is False
    monkeypatch.setattr(profile_module, '_atomic', original)
    assert tx.profile.restore()['restoration']['file_verified'] is True


def test_corrupted_backup_is_never_written_over_player_settings(transaction):
    tx = transaction
    prepared(tx)
    record = json.loads(tx.journal.read_text(encoding='utf-8'))
    record['original']['sha256'] = '0' * 64
    tx.journal.write_text(json.dumps(record), encoding='utf-8')
    before = tx.config.read_bytes()
    with pytest.raises(ReKenshiProfileError) as failure:
        tx.profile.restore()
    assert failure.value.code == 'invalid_journal'
    assert tx.config.read_bytes() == before


def test_reparse_point_is_rejected_before_read(transaction, monkeypatch):
    tx = transaction
    original = Path.lstat
    def lstat(path):
        value = original(path)
        if path == tx.config:
            return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400, st_nlink=1)
        return value
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ReKenshiProfileError) as failure:
        tx.profile.capture()
    assert failure.value.code == 'unsafe_path'
    assert not tx.journal.exists()


def test_unfinished_profile_cannot_be_recaptured(transaction):
    tx = transaction
    prepared(tx)
    with pytest.raises(ReKenshiProfileError) as failure:
        tx.profile.capture()
    assert failure.value.code == 'recovery_required'
    assert tx.profile.provenance()['before']['sha256'] == hashlib.sha256(tx.original).hexdigest()


def test_boot_reformat_requires_final_stopped_reapply_and_preserves_runtime_proof(transaction):
    tx = transaction
    prepared(tx)
    tx.profile.restore()
    start(tx, restore=True)
    original_settings = json.loads(tx.original.decode('utf-8-sig'))
    tx.config.write_text(json.dumps(original_settings, indent=2), encoding='utf-8')
    result = tx.profile.verify_restored_effective(evidence(tx, restore=True))
    assert result['restoration']['runtime_verified'] is True
    assert result['restoration']['file_verified'] is False
    assert result['restoration']['byte_reapply_required'] is True
    assert result['restore_required'] is True
    with pytest.raises(ReKenshiProfileError):
        tx.profile.restore(reapply=True)  # Even an explicit reapply cannot write to a live game.
    tx.observed.update(running=False, owned=False)
    with pytest.raises(ReKenshiProfileError, match='explicit'):
        tx.profile.restore()
    result = tx.profile.restore(reapply=True)
    assert tx.config.read_bytes() == tx.original
    assert result['restore_required'] is False
    assert result['restoration']['file_verified'] and result['restoration']['runtime_verified']
    assert result['restoration']['effective']['evidence']['settings'] == {
        key: original_settings[key] for key in REQUESTED_SETTINGS}
    assert result['restoration']['before_reapply_sha256'] != result['before']['sha256']


def test_runtime_restoration_rejects_changed_unrelated_settings(transaction):
    tx = transaction
    prepared(tx)
    tx.profile.restore()
    start(tx, restore=True)
    changed = json.loads(tx.original.decode('utf-8-sig'))
    changed['HeightmapMode'] = 99
    tx.config.write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(ReKenshiProfileError, match='semantics'):
        tx.profile.verify_restored_effective(evidence(tx, restore=True))
    assert tx.profile.provenance()['restoration']['runtime_verified'] is False


def test_failed_reverification_invalidates_old_success(transaction):
    tx = transaction
    prepared(tx)
    start(tx)
    tx.profile.verify_effective(evidence(tx))
    bad = evidence(tx)
    bad['settings']['UseCustomGameSpeeds'] = True
    with pytest.raises(ReKenshiProfileError):
        tx.profile.verify_effective(bad)
    result = tx.profile.provenance()
    assert result['state'] == 'prepared' and result['effective'] is None
