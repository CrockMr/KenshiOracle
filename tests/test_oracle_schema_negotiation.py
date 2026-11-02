"""A capable producer must honor the requested schema; legacy probes still work."""
import asyncio
from copy import deepcopy

import pytest

from fake_probe import sample_state
from oracle_runner import OracleSession, ScenarioError
from oracle_schema import canonical_bytes


class SchemaClient:
    def __init__(self, tmp_path, *, capable=True, actual='0.2', supported=('0.1', '0.2')):
        self.root, self.capable, self.actual = tmp_path, capable, actual
        self.supported, self.requests = list(supported), []

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
        if self.actual in ('0.2', '0.3'):
            for row in state['characters']:
                row.update(identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=None)
            for row in state['squads']:
                row.update(identity_origin='saved', template_id=None, origin_town_id=None)
        if self.actual == '0.3':
            for row in state['characters']:
                row.update(slave_state=None, slave_owner_faction_id=None)
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


def negotiate(tmp_path, supported, requested=None, actual=None):
    client = SchemaClient(tmp_path, supported=supported, actual=actual or requested or max(supported))
    cfg = dict(oracle_output=str(tmp_path), runs=str(tmp_path / 'runs'))
    if requested:
        cfg['state_schema'] = requested

    async def run():
        session = OracleSession(cfg, client)
        await session.ping()
        state, record = await session.dump()
        return session, state, record
    return client, *asyncio.run(run())


def test_03_is_selected_when_both_sides_support_it(tmp_path):
    client, session, state, record = negotiate(tmp_path, ('0.1', '0.2', '0.3'))
    assert session.state_schema == state['schema_version'] == record['schema_version'] == '0.3'
    assert client.requests[-1][1]['schema_version'] == '0.3'
    assert all(row['slave_state'] is None for row in state['characters'])


@pytest.mark.parametrize('supported', [('0.1', '0.2'), ('0.2',)])
def test_02_only_target_still_negotiates_02(tmp_path, supported):
    client, session, state, _ = negotiate(tmp_path, supported)
    assert session.state_schema == state['schema_version'] == '0.2'
    assert client.requests[-1][1]['schema_version'] == '0.2'
    assert all('slave_state' not in row for row in state['characters'])


@pytest.mark.parametrize('requested', ['0.1', '0.2', '0.3'])
def test_explicit_request_is_honoured_on_a_03_producer(tmp_path, requested):
    client, session, state, _ = negotiate(tmp_path, ('0.1', '0.2', '0.3'), requested)
    assert session.state_schema == state['schema_version'] == requested
    assert client.requests[-1][1]['schema_version'] == requested


def test_explicit_03_request_never_falls_back_on_a_02_producer(tmp_path):
    client = SchemaClient(tmp_path, supported=('0.1', '0.2'))

    async def run():
        session = OracleSession(dict(state_schema='0.3'), client)
        with pytest.raises(ScenarioError, match='requested state schema'):
            await session.ping()
    asyncio.run(run())


@pytest.mark.parametrize('requested', ['0.4', '0.30', 0.3, ''])
def test_unknown_requested_versions_are_rejected_at_configuration(requested):
    with pytest.raises(ValueError, match='0.1, 0.2 or 0.3'):
        OracleSession(dict(state_schema=requested), SchemaClient(None))


def test_unknown_advertised_versions_are_ignored_by_negotiation(tmp_path):
    client, session, state, _ = negotiate(tmp_path, ('0.2', '0.4'), actual='0.2')
    assert session.state_schema == '0.2'


def test_02_snapshot_from_a_producer_that_promised_03_is_rejected(tmp_path):
    client = SchemaClient(tmp_path, supported=('0.1', '0.2', '0.3'), actual='0.2')

    async def run():
        session = OracleSession(dict(oracle_output=str(tmp_path), runs=str(tmp_path / 'runs')), client)
        await session.ping()
        with pytest.raises(ScenarioError, match='differs from the negotiated'):
            await session.dump(tmp_path / 'accepted.json')
    asyncio.run(run())
    assert not (tmp_path / 'accepted.json').exists()
