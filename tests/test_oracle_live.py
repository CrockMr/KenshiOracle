"""Live two-target tools: pure pairing on synthetic snapshots, and the MCP tools against stand-in sessions."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from fake_probe import sample_state
from oracle_live import MAX_LIMIT, compare_states, inspect_states
import server

ROOT = Path(__file__).resolve().parents[1]
FIRST = 'hand:1:7:101:1:1001'
SECOND = 'hand:1:7:101:2:1002'


def state():
    result = sample_state()
    result['schema_version'] = '0.2'
    for row in result['characters']:
        row.update(identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=False)
    for row in result['squads']:
        row.update(identity_origin='saved', template_id='fixture-template', origin_town_id=None)
    return result


def character(value, identity):
    return next(row for row in value['characters'] if row['id'] == identity)


def test_identical_snapshots_pair_every_saved_character_without_differences():
    original = state()
    result = compare_states(original, deepcopy(original))
    assert result['counts']['paired'] == len(original['characters']) == 2
    assert result['counts']['paired_with_differences'] == 0
    assert result['differences'] == [] and result['divergent_fields'] == []
    assert result['clock']['meitou_minus_original_seconds'] == 0


def test_pairs_by_complete_handle_despite_order_and_lists_only_changed_fields():
    original = state()
    meitou = deepcopy(original)
    meitou['characters'].reverse()
    character(meitou, FIRST)['name'] = 'Other name'
    character(meitou, SECOND)['position'][0] += 3
    meitou['clock']['elapsed_seconds'] += 1.1
    result = compare_states(original, meitou)
    changed = {row['id']: row['fields'] for row in result['differences']}
    assert changed[FIRST] == {'name': dict(original=character(original, FIRST)['name'], meitou='Other name')}
    assert set(changed[SECOND]) == {'position/0'}
    assert {row['field'] for row in result['divergent_fields']} == {'name', 'position/0'}
    assert result['clock']['meitou_minus_original_seconds'] == pytest.approx(1.1)


def test_position_tolerance_is_explicit_and_applies_to_positions_only():
    original = state()
    meitou = deepcopy(original)
    character(meitou, FIRST)['position'][1] += 0.5
    assert compare_states(original, meitou)['counts']['paired_with_differences'] == 1
    assert compare_states(original, meitou, position_tolerance=1.0)['counts']['paired_with_differences'] == 0


def test_null_on_one_side_is_not_comparable_never_a_difference():
    original = state()
    meitou = deepcopy(original)
    character(meitou, FIRST)['position'] = None
    result = compare_states(original, meitou)
    assert result['differences'] == []
    assert {row['field'] for row in result['not_comparable_fields']} == {'position/0', 'position/1', 'position/2'}


def test_field_prefix_filter_and_limit_truncation():
    original = state()
    meitou = deepcopy(original)
    for row in meitou['characters']:
        row['name'] += ' changed'
        row['position'][0] += 5
    filtered = compare_states(original, meitou, fields=['position'])
    assert {row['field'] for row in filtered['divergent_fields']} == {'position/0'}
    assert filtered['filter'] == ['position']
    # A prefix matches whole path segments only: "pos" selects nothing.
    assert compare_states(original, meitou, fields=['pos'])['counts']['paired_with_differences'] == 0
    limited = compare_states(original, meitou, limit=1)
    assert len(limited['differences']) == 1 and limited['differences_truncated'] is True


def test_unpaired_and_unsaved_characters_are_reported_not_compared():
    original = state()
    meitou = deepcopy(original)
    meitou['characters'] = [row for row in meitou['characters'] if row['id'] == FIRST]
    original_unsaved = deepcopy(original)
    character(original_unsaved, FIRST)['identity_origin'] = 'generated'
    result = compare_states(original, meitou)
    assert result['counts']['only_original'] == 1 and result['only_original'][0]['id'] == SECOND
    assert compare_states(original_unsaved, original)['counts']['saved_original'] == 1


@pytest.mark.parametrize('options', [dict(limit=0), dict(limit=MAX_LIMIT + 1), dict(limit=True),
                                     dict(fields='goal'), dict(fields=['']), dict(position_tolerance=-1),
                                     dict(position_tolerance=float('nan'))])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):
        compare_states(state(), state(), **options)


def test_mixed_state_schemas_are_refused():
    meitou = state()
    meitou['schema_version'] = '0.1'
    with pytest.raises(ValueError):
        compare_states(state(), meitou)


def test_inspect_returns_both_rows_and_differing_fields_for_characters_and_squads():
    original = state()
    meitou = deepcopy(original)
    character(meitou, FIRST)['name'] = 'Other name'
    shown = inspect_states(original, meitou, FIRST)
    assert shown['original']['id'] == shown['meitou']['id'] == FIRST
    assert shown['differing_fields'] == ['name']
    squad = original['squads'][0]['id']
    assert inspect_states(original, meitou, squad)['collection'] == 'squads'
    meitou['characters'] = [row for row in meitou['characters'] if row['id'] != FIRST]
    missing = inspect_states(original, meitou, FIRST)
    assert missing['meitou'] is None and 'differing_fields' not in missing
    with pytest.raises(ValueError):
        inspect_states(original, meitou, 'not-a-handle')


class StandInSession:
    """Replaces OracleSession inside server: records calls, serves per-target snapshots or failures."""
    calls = []
    states = {}
    fail = {}

    def __init__(self, cfg):
        self.target = cfg['target']

    async def until(self, target_seconds, timeout):
        StandInSession.calls.append(('until', self.target, target_seconds, timeout))
        if self.target in StandInSession.fail:
            raise RuntimeError(StandInSession.fail[self.target])
        reached = target_seconds + (1.0 if self.target == 'meitou' else 0.0)
        return dict(status='completed', clock=dict(elapsed_seconds=reached, paused=True))

    async def dump(self):
        StandInSession.calls.append(('dump', self.target))
        if self.target in StandInSession.fail:
            raise RuntimeError(StandInSession.fail[self.target])
        value = StandInSession.states[self.target]
        return deepcopy(value), dict(path=f'{self.target}/state.json')


@pytest.fixture
def stand_in(monkeypatch):
    StandInSession.calls, StandInSession.fail = [], {}
    original = state()
    meitou = deepcopy(original)
    character(meitou, FIRST)['name'] = 'Other name'
    StandInSession.states = dict(original=original, meitou=meitou)
    monkeypatch.setattr(server, 'OracleSession', StandInSession)
    monkeypatch.setattr(server, 'target_settings', lambda target='original': dict(target=target))

    async def clock(command, target, **params):
        assert command == 'get_clock'
        return dict(elapsed_seconds=100.0 if target == 'original' else 101.1)
    monkeypatch.setattr(server, 'target_call', clock)
    server.LIVE_PAIR.clear()
    yield
    server.LIVE_PAIR.clear()


def test_step_both_targets_the_later_clock_plus_advance_on_both(stand_in):
    result = asyncio.run(server.step_both(advance_seconds=120))
    assert result['target_seconds'] == pytest.approx(221.1)
    assert sorted(c[1] for c in StandInSession.calls) == ['meitou', 'original']
    assert result['errors'] == {} and result['meitou_minus_original_seconds'] == pytest.approx(1.0)


def test_step_both_reports_one_target_failure_with_the_other_result(stand_in):
    StandInSession.fail['meitou'] = 'game frozen'
    result = asyncio.run(server.step_both(target_seconds=500))
    assert result['original']['clock']['elapsed_seconds'] == 500
    assert result['meitou'] is None and 'game frozen' in result['errors']['meitou']


@pytest.mark.parametrize('options', [dict(), dict(advance_seconds=1, target_seconds=2), dict(advance_seconds=0),
                                     dict(advance_seconds=float('inf'))])
def test_step_both_needs_exactly_one_valid_time(stand_in, options):
    with pytest.raises(ValueError):
        asyncio.run(server.step_both(**options))


def test_compare_now_keeps_the_pair_for_inspect_both(stand_in):
    with pytest.raises(ValueError, match='compare_now first'):
        asyncio.run(server.inspect_both(FIRST))
    result = asyncio.run(server.compare_now())
    assert result['counts']['paired_with_differences'] == 1
    assert result['snapshots'] == dict(original='original/state.json', meitou='meitou/state.json')
    shown = asyncio.run(server.inspect_both(FIRST))
    assert shown['differing_fields'] == ['name'] and shown['snapshots'] == result['snapshots']


def test_compare_now_failure_keeps_the_previous_pair(stand_in):
    asyncio.run(server.compare_now())
    kept = dict(server.LIVE_PAIR)
    StandInSession.fail['original'] = 'not paused'
    with pytest.raises(server.ProbeError, match='not paused'):
        asyncio.run(server.compare_now())
    assert server.LIVE_PAIR == kept


def test_stdio_server_lists_the_live_tools(tmp_path):
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps(dict(port=1, runtime=str(tmp_path / 'runtime'))), encoding='utf-8')

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'mcp-server' / 'server.py')],
                                       env=dict(os.environ, KENSHI_PROBE_CONFIG=str(cfg)))
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                return {tool.name: tool for tool in (await session.list_tools()).tools}
    tools = asyncio.run(run())
    assert {'step_both', 'compare_now', 'inspect_both'} <= tools.keys()
    assert tools['compare_now'].inputSchema['properties']['limit']['default'] == 20
    assert tools['inspect_both'].inputSchema['required'] == ['saved_id']
