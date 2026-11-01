"""Local engine profile: pinned scene-setup facts per target, save, source and seed.

The profile is a local file named by the config key engine_profile and is never
committed (docs/scene-setup.md, Engine profile). Every lookup fails closed: an
unpinned save, a missing entry or an ambiguous match raises.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

from oracle_identity import validate_origin_fingerprint


PROFILE_FORMAT = 'engine-profile-0.1'
PINNED_SAVES = ('oracle-base-nature',)
TARGETS = ('original', 'meitou')
MAX_PROFILE_BYTES = 1024 * 1024
_SCHEMA = Path(__file__).resolve().parent.parent / 'schema' / 'engine-profile.schema.json'


class EngineProfileError(ValueError):
    """An engine profile is invalid, or a lookup or pin check fails closed."""


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EngineProfileError(f'Duplicate JSON object key in engine profile: {key!r}')
        result[key] = value
    return result


def _reject_constant(value):
    raise EngineProfileError(f'Non-finite number in engine profile: {value}')


def _seed_text(value):
    if type(value) is int and 0 <= value < 2**64:
        return str(value)
    if type(value) is str and value.isascii() and value.isdecimal() and len(value) <= 20 \
            and (value == '0' or value[0] != '0') and int(value) < 2**64:
        return value
    raise EngineProfileError('MeitouClient seed must be an unsigned 64-bit decimal string')


def _key(entry):
    return entry['target'], entry['save'], entry['source_fingerprint'], entry['seed']


def validate_profile(profile):
    """Validate shape and semantics; return a deep copy."""
    errors = sorted(_validator().iter_errors(profile), key=lambda error: list(error.path))
    if errors:
        location = '/'.join(str(part) for part in errors[0].path) or '$'
        raise EngineProfileError(f'Engine profile is invalid at {location}: {errors[0].message}')
    seen = set()
    for index, entry in enumerate(profile['entries']):
        if entry['save'] not in PINNED_SAVES:
            raise EngineProfileError(f'entries/{index}: pins exist for {", ".join(PINNED_SAVES)} only')
        if entry['seed'] is not None:
            _seed_text(entry['seed'])
        player = entry['player']
        if not all(math.isfinite(value) for value in (*player['xz'], player['y_before_settle'],
                                                       player['y_after_settle'])):
            raise EngineProfileError(f'entries/{index}: pins must be finite')
        if _key(entry) in seen:
            raise EngineProfileError(f'entries/{index}: duplicate lookup key makes the profile ambiguous')
        seen.add(_key(entry))
    return deepcopy(profile)


def load_profile(path):
    path = Path(path)
    try:
        with path.open('rb') as handle:
            raw = handle.read(MAX_PROFILE_BYTES + 1)
    except OSError as exc:
        raise EngineProfileError(f'Cannot read engine profile {path}: {exc}') from exc
    if len(raw) > MAX_PROFILE_BYTES:
        raise EngineProfileError(f'Engine profile exceeds {MAX_PROFILE_BYTES} bytes: {path}')
    try:
        profile = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise EngineProfileError(f'Cannot parse engine profile {path}: {exc}') from exc
    return validate_profile(profile)


def configured_profile(cfg):
    """Load the profile named by cfg['engine_profile']; absent configuration fails closed."""
    if not cfg.get('engine_profile'):
        raise EngineProfileError('Set engine_profile to the local engine profile file')
    return load_profile(cfg['engine_profile'])


def lookup(profile, target, save, source_fingerprint, seed=None):
    """Return the single entry for one repetition, or raise."""
    if target not in TARGETS:
        raise EngineProfileError('target must be original or meitou')
    if save not in PINNED_SAVES:
        raise EngineProfileError(f'No engine profile pins exist for save {save!r}')
    try:
        validate_origin_fingerprint(source_fingerprint)
    except ValueError as exc:
        raise EngineProfileError(str(exc)) from exc
    if target == 'original':
        if seed is not None:
            raise EngineProfileError('The original target has no seed; its lookup seed is null')
    else:
        seed = _seed_text(seed)
    candidates = [entry for entry in profile['entries']
                  if (entry['target'], entry['save'], entry['source_fingerprint'])
                  == (target, save, source_fingerprint)]
    for matches in ([entry for entry in candidates if entry['seed'] == seed],
                    [entry for entry in candidates if entry['seed'] is None]):
        if len(matches) > 1:
            raise EngineProfileError('Engine profile lookup is ambiguous')
        if matches:
            return deepcopy(matches[0])
    raise EngineProfileError(f'No engine profile entry for {target} {save} {source_fingerprint}'
                             + ('' if seed is None else ' seed ' + seed))


def resolve_repetitions(profile, target, save, source_fingerprint, seeds):
    """Resolve every planned repetition before any mutation; one failure fails all."""
    return [lookup(profile, target, save, source_fingerprint, seed) for seed in seeds]


def check_pin(observed, pin, decimals, label='value'):
    if type(observed) not in (int, float) or not math.isfinite(observed):
        raise EngineProfileError(f'Observed {label} is not a finite number')
    delta = observed - pin
    if not abs(delta) <= 0.5 * 10**-decimals:
        raise EngineProfileError(f'Observed {label} {observed!r} differs from pin {pin!r} '
                                 f'at {decimals} decimals')
    return dict(pin=pin, observed=observed, delta=delta)


def check_player(entry, position, phase):
    """Check a player [x,y,z] against an entry; phase is before_settle or after_settle."""
    if phase not in ('before_settle', 'after_settle'):
        raise ValueError('phase must be before_settle or after_settle')
    if type(position) not in (list, tuple) or len(position) != 3:
        raise EngineProfileError('Player position must have three numbers')
    player = entry['player']
    pin = [player['xz'][0], player['y_' + phase], player['xz'][1]]
    checks = [check_pin(value, expected, player['decimals'], axis)
              for value, expected, axis in zip(position, pin, 'xyz')]
    return dict(pin=pin, observed=[check['observed'] for check in checks],
                delta=[check['delta'] for check in checks], decimals=player['decimals'])
