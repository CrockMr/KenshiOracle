import asyncio
from types import SimpleNamespace
import pytest
import live_suite
from probe import ProbeError


def clock_for_test(monkeypatch):
    clock = SimpleNamespace(value=0)
    async def advance(seconds):
        clock.value += seconds
    monkeypatch.setattr(live_suite, 'time', SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr(live_suite, 'asyncio', SimpleNamespace(sleep=advance))
    return clock


def test_secondary_loading_transition_resets_stable_ready_interval(monkeypatch):
    clock = clock_for_test(monkeypatch)
    states = iter([True, True, False, True, True, True, True])
    class Client:
        async def call(self, command):
            if command == 'heartbeat':
                return dict(frame=1, loading=False)
            return dict(world_ready=next(states))
    assert asyncio.run(live_suite.wait_loaded(Client(), 0, stable_seconds=3))['world_ready']
    assert clock.value == 6


def test_unstable_world_still_obeys_readiness_deadline(monkeypatch):
    clock_for_test(monkeypatch)
    class Client:
        async def call(self, command):
            return dict(frame=1, loading=True)
    with pytest.raises(TimeoutError):
        asyncio.run(live_suite.wait_loaded(Client(), 0, timeout=4, stable_seconds=3))


def test_pause_retries_only_world_not_ready_rejection(monkeypatch):
    clock_for_test(monkeypatch)
    class Client:
        attempts = 0
        async def call(self, command, **params):
            if command == 'heartbeat':
                return dict(frame=1, loading=False)
            if command == 'ping':
                return dict(world_ready=True)
            self.attempts += 1
            if self.attempts == 1:
                raise ProbeError('world not ready')
            return dict(paused=params['paused'])
    client = Client()
    assert asyncio.run(live_suite.pause_ready(client, False)) == {'paused': False}
    assert client.attempts == 2


def test_pause_does_not_retry_transport_failure(monkeypatch):
    clock_for_test(monkeypatch)
    class Client:
        attempts = 0
        async def call(self, command, **params):
            if command == 'heartbeat':
                return dict(frame=1, loading=False)
            if command == 'ping':
                return dict(world_ready=True)
            self.attempts += 1
            raise ProbeError('connection timeout')
    client = Client()
    with pytest.raises(ProbeError, match='timeout'):
        asyncio.run(live_suite.pause_ready(client, False))
    assert client.attempts == 1
