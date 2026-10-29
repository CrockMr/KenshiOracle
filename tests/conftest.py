"""Offline tests must never accidentally connect to the installed game."""
import pytest
from probe import Client


@pytest.fixture(autouse=True)
def forbid_live_probe_connection(monkeypatch):
    original = Client.call

    async def offline_only(self, command, **params):
        if self.port in (47800, 47801):
            raise AssertionError('Offline test attempted to contact a real oracle probe port')
        return await original(self, command, **params)

    monkeypatch.setattr(Client, 'call', offline_only)
