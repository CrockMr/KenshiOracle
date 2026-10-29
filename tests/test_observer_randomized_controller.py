import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import live_observer_randomized as pilot


def registration(tmp_path):
    for name in pilot.OWN_SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('own test source: ' + name, encoding='utf-8')
    document = tmp_path / 'docs/randomized-observer-protocol.md'
    document.parent.mkdir()
    document.write_text('fixed protocol', encoding='utf-8')
    path = tmp_path / 'runtime/session/registration.json'
    path.parent.mkdir(parents=True)
    symbols = tmp_path / 'runtime/symbols/0.8.20/manifest.json'
    symbols.parent.mkdir(parents=True)
    symbols.write_text('{"fixture":true}', encoding='utf-8')
    value = dict(protocol=pilot.PROTOCOL, randomization_seed=123, plan=pilot.make_plan(123),
                 plugin_version='0.8.20', registered_at=100, source_sha256=pilot.source_hashes(tmp_path),
                 symbol_manifest=dict(path='runtime/symbols/0.8.20/manifest.json', sha256=hashlib.sha256(symbols.read_bytes()).hexdigest()),
                 protocol_document=dict(path='docs/randomized-observer-protocol.md',
                     sha256=hashlib.sha256(document.read_bytes()).hexdigest()))
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, value


def test_registration_binds_plan_sources_protocol_and_prior_time(tmp_path):
    path, expected = registration(tmp_path)
    value, raw, started = pilot.registration_for_run(path, '0.8.20', 123, root=tmp_path, wall_clock=lambda: 101)
    assert value == expected and json.loads(raw) == expected and started == 101


@pytest.mark.parametrize('change', ['seed', 'plan', 'future', 'nan_time', 'bool_time', 'inventory', 'protocol_path', 'version'])
def test_changed_or_malformed_registration_rejected_before_game_access(tmp_path, change):
    path, value = registration(tmp_path)
    if change == 'seed': value['randomization_seed'] = True
    elif change == 'plan': value['plan'].reverse()
    elif change == 'future': value['registered_at'] = 102
    elif change == 'nan_time': value['registered_at'] = float('nan')
    elif change == 'bool_time': value['registered_at'] = True
    elif change == 'inventory': value['source_sha256']['../outside'] = 'bad'
    elif change == 'protocol_path': value['protocol_document']['path'] = '../outside'
    elif change == 'version': value['plugin_version'] = '0.8.19'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(RuntimeError):
        pilot.registration_for_run(path, '0.8.20', 123, root=tmp_path, wall_clock=lambda: 101)


@pytest.mark.parametrize('name', [pilot.OWN_SOURCES[0], 'docs/randomized-observer-protocol.md', 'runtime/symbols/0.8.20/manifest.json'])
def test_changed_registered_file_rejected(tmp_path, name):
    path, _ = registration(tmp_path)
    (tmp_path / name).write_text('changed after registration', encoding='utf-8')
    with pytest.raises(RuntimeError):
        pilot.registration_for_run(path, '0.8.20', 123, root=tmp_path, wall_clock=lambda: 101)


def test_registration_outside_runtime_rejected(tmp_path):
    path, value = registration(tmp_path)
    outside = tmp_path / 'outside.json'
    outside.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(RuntimeError, match='runtime'):
        pilot.registration_for_run(outside, '0.8.20', 123, root=tmp_path)


class Client:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    async def call(self, command, **params):
        self.calls.append((command, params))
        if self.fail:
            raise RuntimeError('transport gone')
        return dict(ok=True)


@pytest.mark.parametrize('command,params', [('pause', {'paused': True}),
    ('set_camera_free', {'enabled': False, 'release_edge': True})])
def test_dead_server_cleanup_uses_verified_idempotent_tcp(command, params):
    mcp, direct, checks, events = Client(True), Client(), [], []
    result = asyncio.run(pilot.cleanup_call(mcp, direct, lambda: checks.append(True), events, command, **params))
    assert result == {'ok': True} and len(checks) == 2
    assert direct.calls == mcp.calls == [(command, params)]
    assert events[0]['recovered'] and events[0]['fallback'] == 'direct-tcp'


def test_healthy_mcp_does_not_duplicate_mutation():
    mcp, direct, checks, events = Client(), Client(), [], []
    asyncio.run(pilot.cleanup_call(mcp, direct, lambda: checks.append(True), events, 'pause', paused=True))
    assert len(checks) == 1 and len(mcp.calls) == 1 and not direct.calls and not events


def test_identity_change_forbids_tcp_retry():
    mcp, direct, checks, events = Client(True), Client(), [], []
    def identity():
        checks.append(True)
        if len(checks) == 2:
            raise RuntimeError('game identity changed')
    with pytest.raises(RuntimeError, match='identity changed'):
        asyncio.run(pilot.cleanup_call(mcp, direct, identity, events, 'pause', paused=True))
    assert not direct.calls and events[0]['recovered'] is False


@pytest.mark.parametrize('command,params', [('set_game_speed', {'speed': 1}), ('pause', {'paused': False}),
    ('set_camera_free', {'enabled': True, 'release_edge': True}), ('load_save', {'name': 'KenshiProbe_test'})])
def test_fallback_never_retries_arbitrary_mutations(command, params):
    mcp, direct, events = Client(True), Client(), []
    with pytest.raises(ValueError, match='idempotent'):
        asyncio.run(pilot.cleanup_call(mcp, direct, lambda: None, events, command, **params))
    assert not mcp.calls and not direct.calls and not events
