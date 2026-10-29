"""Offline tests must never accidentally connect to the installed game."""
import pytest
from probe import Client


@pytest.fixture(autouse=True)
def forbid_live_probe_connection(monkeypatch):
    original = Client.call

    async def offline_only(self, command, **params):
        if self.port == 47800:
            raise AssertionError('Offline test attempted to contact the real Kenshi probe port')
        return await original(self, command, **params)

    monkeypatch.setattr(Client, 'call', offline_only)
