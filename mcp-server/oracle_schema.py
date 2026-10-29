"""Shared oracle 0.1 contracts and canonical, engine-independent state bytes.

Numbers are finite binary64 values with magnitude at most 1e9. Quantization is
floor(abs(x) * 1e6 + .5), signed afterwards: ties away from zero, negative zero
normalized. Decimal output has no exponent and at most six fractional digits.
This deliberately matches the v100 implementation, not decimal-string rounding.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_VERSION = '0.1'
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / 'schema'
_RESERVED_NAME = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)


class OracleSchemaError(ValueError):
    """An oracle document is invalid, ambiguous, or cannot be canonicalized."""


def _reject_constant(value: str) -> None:
    raise OracleSchemaError(f'Non-finite JSON number: {value}')


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise OracleSchemaError(f'Duplicate JSON object key: {key!r}')
        result[key] = value
    return result


def _load_json(path: str | Path) -> dict:
    path = Path(path)
    try:
        with path.open('rb') as stream:
            data = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise OracleSchemaError(f'Document exceeds {MAX_DOCUMENT_BYTES} bytes: {path}')
        return json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise OracleSchemaError(f'Cannot read oracle JSON {path}: {exc}') from exc


@lru_cache(maxsize=2)
def _validator(kind: str) -> Draft202012Validator:
    schema = _load_json(_SCHEMA_DIR / f'{kind}.schema.json')
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _check_json_values(value: Any, path: str = '$') -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        try:
            value.encode('utf-8')
        except UnicodeError as exc:
            raise OracleSchemaError(f'{path}: invalid Unicode scalar value') from exc
        return
    if type(value) in (int, float):
        if abs(value) > 1_000_000_000 or not math.isfinite(value):
            raise OracleSchemaError(f'{path}: number must be finite with magnitude <= 1e9')
        return
    if type(value) is list:
        for index, entry in enumerate(value):
            _check_json_values(entry, f'{path}[{index}]')
        return
    if type(value) is dict:
        for key, entry in value.items():
            if type(key) is not str:
                raise OracleSchemaError(f'{path}: JSON object keys must be strings')
            _check_json_values(key, path)
            _check_json_values(entry, f'{path}.{key}')
        return
    raise OracleSchemaError(f'{path}: unsupported JSON type {type(value).__name__}')


def _validate_shape(value: dict, kind: str) -> None:
    try:
        _check_json_values(value)
        error = next(_validator(kind).iter_errors(value), None)
    except RecursionError as exc:
        raise OracleSchemaError('Oracle document is nested too deeply') from exc
    if error is not None:
        path = '$' + ''.join(f'[{part}]' if isinstance(part, int) else f'.{part}'
                             for part in error.absolute_path)
        raise OracleSchemaError(f'{kind} {path}: {error.message}')


def _unique(rows: list, key, path: str) -> None:
    seen = set()
    for row in rows:
        identity = key(row)
        if identity in seen:
            raise OracleSchemaError(f'{path}: duplicate identity {identity!r}')
        seen.add(identity)


def validate_state(state: dict) -> dict:
    """Validate shape and unique stable identities; return the original unchanged."""
    _validate_shape(state, 'state')
    for collection in ('characters', 'squads', 'factions'):
        _unique(state[collection], lambda row: row['id'], f'$.{collection}')
    _unique(state['relations'], lambda row: (row['source_id'], row['target_id']), '$.relations')
    for character in state['characters']:
        if character['health'] is not None:
            _unique(character['health'], lambda row: row['id'],
                    f'$.characters[{character["id"]}].health')
    return state


def _safe_component(value: str, label: str) -> None:
    if value in ('.', '..') or value != value.strip() or value.endswith('.') or _RESERVED_NAME.match(value):
        raise OracleSchemaError(f'{label}: unsafe Windows path component {value!r}')


def validate_scenario(scenario: dict) -> dict:
    """Validate a scenario and reject a timeline that would wait forever in pause."""
    _validate_shape(scenario, 'scenario')
    _safe_component(scenario['name'], 'name')
    _safe_component(scenario['save'], 'save')
    _unique(scenario['checkpoints'], lambda row: row['name'].casefold(), '$.checkpoints')
    for checkpoint in scenario['checkpoints']:
        _safe_component(checkpoint['name'], 'checkpoint name')
    for collection in ('actions', 'checkpoints'):
        times = [row['at'] for row in scenario[collection]]
        if times != sorted(times):
            raise OracleSchemaError(f'$.{collection}: times must be nondecreasing')
    actions_by_time: dict[float, list] = {}
    for action in scenario['actions']:
        actions_by_time.setdefault(action['at'], []).append(action)
    times = sorted(set(actions_by_time) | {row['at'] for row in scenario['checkpoints']})
    previous = 0
    paused = scenario['speed'] == 0
    selected_known = scenario['speed'] > 0
    for instant in times:
        if instant > previous and paused:
            raise OracleSchemaError(f'Timeline cannot reach {instant}: resume at {previous} before advancing')
        if instant > previous and not selected_known:
            raise OracleSchemaError(f'Timeline cannot reach {instant}: set a positive game speed explicitly before advancing')
        for action in actions_by_time.get(instant, ()):
            if action['command'] == 'pause':
                paused = action['params']['paused']
            elif action['command'] == 'set_game_speed':
                paused = action['params']['speed'] == 0
                if action['params']['speed'] > 0:
                    selected_known = True
        previous = instant
    return scenario


def load_state(path: str | Path) -> dict:
    return validate_state(_load_json(path))


def load_scenario(path: str | Path) -> dict:
    return validate_scenario(_load_json(path))


def _number_text(value: int | float) -> str:
    magnitude = math.floor(abs(float(value)) * 1_000_000.0 + 0.5)
    whole, fraction = divmod(magnitude, 1_000_000)
    text = str(whole)
    if fraction:
        text += '.' + f'{fraction:06d}'.rstrip('0')
    return '-' + text if value < 0 and magnitude else text


def _encode(value: Any) -> str:
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) in (int, float):
        return _number_text(value)
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is list:
        return '[' + ','.join(_encode(item) for item in value) + ']'
    return '{' + ','.join(_encode(key) + ':' + _encode(value[key]) for key in sorted(value)) + '}'


def canonical_bytes(state: dict) -> bytes:
    """Validate and encode a copied state; no timestamps or input mutations."""
    validate_state(state)
    ordered = deepcopy(state)
    for collection in ('characters', 'squads', 'factions'):
        ordered[collection].sort(key=lambda row: row['id'])
    ordered['relations'].sort(key=lambda row: (row['source_id'], row['target_id']))
    for squad in ordered['squads']:
        squad['members'].sort()
    for character in ordered['characters']:
        if character['health'] is not None:
            character['health'].sort(key=lambda row: row['id'])
    return (_encode(ordered) + '\n').encode('utf-8')
