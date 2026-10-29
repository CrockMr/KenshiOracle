"""A capable producer must honor the requested schema; legacy probes still work."""
import asyncio
from copy import deepcopy

import pytest

from fake_probe import sample_state
from oracle_runner import OracleSession, ScenarioError
from oracle_schema import canonical_bytes


class SchemaClient:
    def __init__(self, tmp_path, *, capable=True, actual='0.2'):
        self.root, self.capable, self.actual = tmp_path, capable, actual
        self.supported, self.requests = ['0.1', '0.2'], []

    async def call(self, command, **params):
        self.requests.append((command, deepcopy(params)))
        if command == 'ping':
            result = dict(instance_id='synthetic-instance', schema_version='0.2' if self.capable else '0.1')
            if self.capable:
                result['supported_schema_versions'] = self.supported
            return result
        assert command == 'dump_state'
        state = sample_state()
        state['schema_version'] = self.actual
        if self.actual == '0.2':
            for row in state['characters']:
                row.update(identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=None)
            for row in state['squads']:
                row.update(identity_origin='saved', template_id=None, origin_town_id=None)
        path = self.root / params['filename']
        path.write_bytes(canonical_bytes(state))
        return dict(path=str(path))


@pytest.mark.parametrize('requested', [None, '0.1', '0.2'])
def test_capable_probe_receives_explicit_schema_and_files_match(tmp_path, requested):
    selected = requested or '0.2'
    client = SchemaClient(tmp_path, actual=selected)
    cfg = dict(oracle_output=str(tmp_path), runs=str(tmp_path / 'runs'))
    if requested:
        cfg['state_schema'] = requested

    async def run():
        session = OracleSession(cfg, client)
        await session.ping()
        state, _ = await session.dump()
        assert state['schema_version'] == selected
    asyncio.run(run())
    assert client.requests[-1][1]['schema_version'] == selected


def test_legacy_probe_is_not_sent_new_parameters(tmp_path):
    client = SchemaClient(tmp_path, capable=False, actual='0.1')

    async def run():
        session = OracleSession(dict(oracle_output=str(tmp_path), runs=str(tmp_path / 'runs')), client)
        await session.ping()
        await session.dump()
    asyncio.run(run())
    assert set(client.requests[-1][1]) == {'filename'}


def test_mismatched_snapshot_is_rejected_before_copy(tmp_path):
    client = SchemaClient(tmp_path, actual='0.1')

    async def run():
        session = OracleSession(dict(oracle_output=str(tmp_path), runs=str(tmp_path / 'runs')), client)
        await session.ping()
        with pytest.raises(ScenarioError, match='differs from the negotiated'):
            await session.dump(tmp_path / 'accepted.json')
    asyncio.run(run())
    assert not (tmp_path / 'accepted.json').exists()


def test_schema_support_cannot_change_mid_execution(tmp_path):
    client = SchemaClient(tmp_path)

    async def run():
        session = OracleSession({}, client)
        await session.ping()
        client.supported = ['0.1']
        with pytest.raises(ScenarioError, match='changed state schema'):
            await session.ping()
    asyncio.run(run())
