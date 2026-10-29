import asyncio
import pytest

from oracle_identity import validate_saved_handles


@pytest.mark.parametrize('ids', [
    ['hand:1:372:2911010816:4:3090576128'],
    ['hand:34:4294967295:4294967295:0:0'],
    ['hand:1:1:1:1:1'] * 128,
])
def test_complete_saved_handles_fit_public_uint32_api(ids):
    assert validate_saved_handles(ids) is ids


@pytest.mark.parametrize('ids', [
    [], ['hand:1:1:1:1:1'] * 129, 'hand:1:1:1:1:1', None,
    [True], [1], [None], ['Ando'], ['hand:1:1:1:1:1\n'],
    ['hand:1:1:1:1:1:2'], ['hand:1:1:1:1'], ['hand:01:1:1:1:1'],
    ['hand:1:-1:1:1:1'], ['hand:1:4294967296:1:1:1'],
    ['hand:1:1:1:1:4294967296'], ['hand:0:1:1:1:1'],
    ['hand:11:0:0:0:0'], ['hand:１:1:1:1:1'],
])
def test_invalid_identity_batches_are_refused_before_transport(ids):
    with pytest.raises(ValueError):
        validate_saved_handles(ids)


def test_mcp_resolver_validates_then_preserves_complete_identity(monkeypatch):
    import server
    calls = []

    async def fake(command, **params):
        calls.append((command, params))
        return {'resolutions': []}

    monkeypatch.setattr(server, 'call', fake)
    async def run():
        with pytest.raises(ValueError):
            await server.resolve_saved_handles(['hand:1:1:1:1:4294967296'])
        assert not calls
        ids = ['hand:1:372:2911010816:4:3090576128']
        assert await server.resolve_saved_handles(ids) == {'resolutions': []}
        assert calls == [('resolve_saved_handles', {'ids': ids})]
    asyncio.run(run())
