"""Engine-profile lookups and pin checks fail closed, with synthetic profiles only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

import oracle_engine_profile as engine
from oracle_engine_profile import EngineProfileError
from oracle_targets import target_config

ROOT = Path(__file__).resolve().parent.parent
SAVE = 'oracle-base-nature'
FINGERPRINT = 'sha256:' + 'ab' * 32
OTHER = 'sha256:' + 'cd' * 32


def entry(target='original', seed=None, y=(10.25, 9.5), fingerprint=FINGERPRINT, save=SAVE):
    return dict(target=target, save=save, source_fingerprint=fingerprint, seed=seed,
                player=dict(xz=[100.0, -200.0], y_before_settle=y[0], y_after_settle=y[1], decimals=3),
                evidence='runs/synthetic')


def profile(*entries):
    return dict(profile_format='engine-profile-0.1', entries=list(entries) or [entry()])


def write(tmp_path, value, name='profile.json'):
    path = tmp_path / name
    path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding='utf-8')
    return path


def test_example_profile_validates_and_holds_placeholders_only():
    loaded = engine.load_profile(ROOT / 'engine-profile.example.json')
    for row in loaded['entries']:
        assert row['source_fingerprint'] == 'sha256:' + '0' * 64
        assert row['player'] == dict(xz=[0, 0], y_before_settle=0, y_after_settle=0, decimals=3)
        assert row['evidence'].startswith('placeholder only, not evidence')


def test_original_lookup_by_target_save_and_fingerprint(tmp_path):
    loaded = engine.load_profile(write(tmp_path, profile(entry(), entry('meitou', y=(1, 2)))))
    found = engine.lookup(loaded, 'original', SAVE, FINGERPRINT)
    assert found['player']['y_before_settle'] == 10.25
    found['player']['y_before_settle'] = 0
    assert engine.lookup(loaded, 'original', SAVE, FINGERPRINT)['player']['y_before_settle'] == 10.25


def test_meitou_null_seed_applies_to_every_seed_and_exact_seed_takes_precedence():
    loaded = engine.validate_profile(profile(entry('meitou', None, (5, 6)), entry('meitou', '1', (7, 8))))
    assert engine.lookup(loaded, 'meitou', SAVE, FINGERPRINT, '0')['player']['y_after_settle'] == 6
    with pytest.raises(EngineProfileError, match='decimal string'):
        engine.lookup(loaded, 'meitou', SAVE, FINGERPRINT, 0)
    assert engine.lookup(loaded, 'meitou', SAVE, FINGERPRINT, '1')['player']['y_after_settle'] == 8
    assert [row['seed'] for row in engine.resolve_repetitions(
        loaded, 'meitou', SAVE, FINGERPRINT, ['0', '1', '2'])] == [None, '1', None]


@pytest.mark.parametrize('target,save,fingerprint,seed,match', [
    ('original', SAVE, OTHER, None, 'No engine profile entry'),
    ('meitou', SAVE, FINGERPRINT, '0', 'No engine profile entry'),
    ('original', 'oracle-base-town', FINGERPRINT, None, 'No engine profile pins'),
    ('original', SAVE, FINGERPRINT, '0', 'no seed'),
    ('meitou', SAVE, FINGERPRINT, None, 'seed'),
    ('meitou', SAVE, FINGERPRINT, '01', 'seed'),
    ('meitou', SAVE, FINGERPRINT, str(2**64), 'seed'),
    ('meitou', SAVE, FINGERPRINT, True, 'seed'),
    ('other', SAVE, FINGERPRINT, None, 'target'),
    ('original', SAVE, 'sha256:AB', None, 'source_fingerprint'),
])
def test_missing_or_unpinned_lookup_fails_closed(target, save, fingerprint, seed, match):
    with pytest.raises(EngineProfileError, match=match):
        engine.lookup(engine.validate_profile(profile()), target, save, fingerprint, seed)


def test_one_unresolved_repetition_fails_every_repetition():
    loaded = engine.validate_profile(profile(entry('meitou', '0')))
    with pytest.raises(EngineProfileError, match='seed 1'):
        engine.resolve_repetitions(loaded, 'meitou', SAVE, FINGERPRINT, ['0', '1'])


@pytest.mark.parametrize('rows', [
    [entry(), entry(y=(1, 2))],
    [entry('meitou', None), entry('meitou', None, (1, 2))],
    [entry('meitou', '3'), entry('meitou', '3', (1, 2))],
])
def test_ambiguous_profile_is_rejected_on_load(rows):
    with pytest.raises(EngineProfileError, match='ambiguous'):
        engine.validate_profile(profile(*rows))


def test_ambiguous_match_fails_closed_even_without_load_validation():
    unchecked = profile(entry('meitou', None), entry('meitou', None, (1, 2)))
    with pytest.raises(EngineProfileError, match='ambiguous'):
        engine.lookup(unchecked, 'meitou', SAVE, FINGERPRINT, '4')


def invalid(mutation):
    value = profile(entry('meitou', '2'))
    mutation(value)
    return value


@pytest.mark.parametrize('value', [
    invalid(lambda v: v.update(profile_format='engine-profile-0.2')),
    invalid(lambda v: v.update(entries=[])),
    invalid(lambda v: v.update(extra=1)),
    invalid(lambda v: v['entries'][0].update(target='rekenshi')),
    invalid(lambda v: v['entries'][0].update(save='oracle-base-town')),
    invalid(lambda v: v['entries'][0].update(source_fingerprint='sha256:' + 'AB' * 32)),
    invalid(lambda v: v['entries'][0].update(seed=2)),
    invalid(lambda v: v['entries'][0].update(seed='007')),
    invalid(lambda v: v['entries'][0].update(seed=str(2**64))),
    invalid(lambda v: v['entries'][0].update(target='original')),
    invalid(lambda v: v['entries'][0].pop('evidence')),
    invalid(lambda v: v['entries'][0].update(evidence='')),
    invalid(lambda v: v['entries'][0]['player'].update(decimals=1.5)),
    invalid(lambda v: v['entries'][0]['player'].update(decimals=7)),
    invalid(lambda v: v['entries'][0]['player'].update(xz=[1])),
    invalid(lambda v: v['entries'][0]['player'].update(y_after_settle='736.593')),
    invalid(lambda v: v['entries'][0]['player'].update(wobble=1)),
])
def test_invalid_profile_is_rejected(value):
    with pytest.raises(EngineProfileError):
        engine.validate_profile(value)


@pytest.mark.parametrize('text,match', [
    ('{"profile_format": "engine-profile-0.1", "profile_format": "engine-profile-0.1", "entries": []}',
     'Duplicate'),
    ('{"profile_format": "engine-profile-0.1", "entries": [NaN]}', 'Non-finite'),
    ('{"profile_format": ', 'parse'),
])
def test_malformed_profile_file_is_rejected(tmp_path, text, match):
    with pytest.raises(EngineProfileError, match=match):
        engine.load_profile(write(tmp_path, text))


def test_overflowing_pin_and_oversized_or_missing_file_are_rejected(tmp_path):
    text = json.dumps(profile()).replace('10.25', '1e400')
    with pytest.raises(EngineProfileError):
        engine.load_profile(write(tmp_path, text))
    with pytest.raises(EngineProfileError, match='exceeds'):
        engine.load_profile(write(tmp_path, ' ' * (engine.MAX_PROFILE_BYTES + 1), 'large.json'))
    with pytest.raises(EngineProfileError, match='Cannot read'):
        engine.load_profile(tmp_path / 'absent.json')


def test_configured_profile_requires_the_config_key(tmp_path):
    with pytest.raises(EngineProfileError, match='Set engine_profile'):
        engine.configured_profile({})
    path = write(tmp_path, profile())
    assert engine.configured_profile(dict(engine_profile=str(path)))['entries'][0]['save'] == SAVE


@pytest.mark.parametrize('observed,accepted', [
    (736.593, True), (736.5934999, True), (736.5925001, True),
    (736.5936, False), (736.592, False), (float('nan'), False), (float('inf'), False),
])
def test_pin_check_uses_half_unit_in_last_decimal(observed, accepted):
    if accepted:
        result = engine.check_pin(observed, 736.593, 3, 'y')
        assert result['pin'] == 736.593 and result['observed'] == observed
        assert result['delta'] == observed - 736.593
    else:
        with pytest.raises(EngineProfileError):
            engine.check_pin(observed, 736.593, 3, 'y')


@pytest.mark.parametrize('observed', [True, None, '736.593'])
def test_pin_check_rejects_non_numbers(observed):
    with pytest.raises(EngineProfileError, match='finite'):
        engine.check_pin(observed, 736.593, 3)


def test_player_check_compares_xz_and_the_phase_height():
    row = entry()
    before = engine.check_player(row, [100.0002, 10.25, -200.0], 'before_settle')
    assert before['pin'] == [100.0, 10.25, -200.0] and before['decimals'] == 3
    s0 = [100.0002, 10.25, -200.0]
    assert engine.check_player(row, [100.0, 9.5, -200.0], 'after_settle', s0)['observed'] == [100.0, 9.5, -200.0]
    with pytest.raises(EngineProfileError, match='y'):
        engine.check_player(row, [100.0, 10.25, -200.0], 'after_settle', s0)
    with pytest.raises(EngineProfileError, match='z'):
        engine.check_player(row, [100.0, 10.25, -199.0], 'before_settle')
    with pytest.raises(EngineProfileError, match='three'):
        engine.check_player(row, [100.0, 10.25], 'before_settle')
    with pytest.raises(ValueError, match='phase'):
        engine.check_player(row, [100.0, 10.25, -200.0], 'settle')


def test_meitou_target_inherits_the_original_profile_path(tmp_path):
    meitou = tmp_path / 'config.meitou.json'
    meitou.write_text(json.dumps(dict(target='meitou', port=47901, runtime='meitou-runtime')), encoding='utf-8')
    original = dict(meitou_config=str(meitou), port=47900, runtime=str(tmp_path / 'runtime'),
                    engine_profile=str(tmp_path / 'runtime' / 'engine-profile.json'))
    assert target_config(original, 'meitou')['engine_profile'] == original['engine_profile']
    own = deepcopy(original)
    meitou.write_text(json.dumps(dict(target='meitou', port=47901, runtime='meitou-runtime',
                                      engine_profile='mine.json')), encoding='utf-8')
    assert target_config(own, 'meitou')['engine_profile'] == str((tmp_path / 'mine.json').resolve())


def test_after_settle_needs_xz_unchanged_from_s0_not_only_near_the_pin():
    row = entry()
    with pytest.raises(EngineProfileError, match='S0 player position'):
        engine.check_player(row, [100.0, 9.5, -200.0], 'after_settle')
    with pytest.raises(EngineProfileError, match='three'):
        engine.check_player(row, [100.0, 9.5, -200.0], 'after_settle', [100.0, 10.25])
    # Both readings are within half a unit of the pin, but X moved 0.0008 between S0 and S3.
    with pytest.raises(EngineProfileError, match='x unchanged from S0'):
        engine.check_player(row, [100.0004, 9.5, -200.0], 'after_settle', [99.9996, 10.25, -200.0])
