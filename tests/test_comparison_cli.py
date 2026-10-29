"""Actual offline CLI and MCP comparisons need no game, watchdog or game config."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from test_oracle_comparison import campaign, save_report


ROOT = Path(__file__).resolve().parents[1]


def files(tmp_path, *, n=5, missing_provenance=False):
    original, meitou = tmp_path/'original', tmp_path/'meitou'
    report = campaign(original, 'original', n=n)
    campaign(meitou, 'meitou', n=n)
    if missing_provenance:
        del report['reference_profile']
        save_report(original, report)
    return original/'report.json', meitou/'report.json', tmp_path/'comparison'


def environment(tmp_path):
    return dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1',
                KENSHI_PROBE_CONFIG=str(tmp_path/'deliberately-absent-game-config.json'))


def cli(tmp_path, original, meitou, output, *options):
    return subprocess.run([sys.executable, '-m', 'launcher', 'compare', str(original), str(meitou),
        str(output), *map(str, options)], cwd=tmp_path, env=environment(tmp_path),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def check_outputs(result, output):
    assert result['original_n'] == result['meitou_n'] == 5
    assert result['classifications']['stable_divergent'] > 0
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    markdown = (output/'report.md').read_text(encoding='utf-8')
    assert report['original']['n'] == report['meitou']['n'] == 5
    for text in ('Original N = 5', 'MeitouClient N = 5', 'range', 'median', 'Outside range', 'Tolerance'):
        assert text in markdown
    assert '../../' in markdown or '../original/' in markdown
    drafts = list((output/'issues').glob('*.md'))
    assert drafts
    text = drafts[0].read_text(encoding='utf-8')
    assert 'Local draft for review. No issue has been published.' in text
    assert 'Original N=5; Meitou N=5' in text
    assert 'Tolerance:' in text
    assert 'observations outside' in text
    return report


def test_actual_cli_compare_has_no_config_argument_dependency_and_writes_statistics_and_drafts(tmp_path):
    original, meitou, output = files(tmp_path)
    rules = tmp_path/'explicit-rules.json'
    rules.write_text('{}', encoding='utf-8')
    result = cli(tmp_path, original, meitou, output, '--position-tolerance', '.25',
        '--number-tolerance', '.125', '--arrival-radius', '7.5', '--known-deviations', rules)
    assert result.returncode == 0, result.stderr
    report = check_outputs(json.loads(result.stdout), output)
    assert report['tolerances'] == dict(position=.25, number=.125)
    assert report['arrival_radius_world_units'] == 7.5
    assert not (tmp_path/'config.json').exists()
    assert not (tmp_path/'deliberately-absent-game-config.json').exists()


@pytest.mark.parametrize('failure', ['too_few_repetitions', 'missing_provenance', 'invalid_minimum_argument'])
def test_cli_invalid_inputs_fail_without_output_or_game_config(tmp_path, failure):
    original, meitou, output = files(tmp_path, n=4 if failure == 'too_few_repetitions' else 5,
                                    missing_provenance=failure == 'missing_provenance')
    options = ['--minimum-repetitions', '0'] if failure == 'invalid_minimum_argument' else []
    result = cli(tmp_path, original, meitou, output, *options)
    assert result.returncode == (2 if failure == 'invalid_minimum_argument' else 1)
    assert not output.exists()
    expected = ('between 1 and 100' if failure == 'invalid_minimum_argument'
                else 'minimum' if failure == 'too_few_repetitions' else 'provenance')
    assert expected in result.stderr
    assert 'config.json' not in result.stderr and "has no attribute 'config'" not in result.stderr


async def mcp_compare(tmp_path, arguments):
    parameters = StdioServerParameters(command=sys.executable,
        args=[str(ROOT/'mcp-server'/'server.py')], cwd=str(tmp_path), env=environment(tmp_path))
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            schema = tools['compare_scenarios'].inputSchema
            assert set(schema['required']) == {'original_report', 'meitou_report', 'output'}
            assert schema['properties']['minimum_repetitions']['default'] == 5
            assert schema['properties']['position_tolerance']['default'] == .000001
            return await session.call_tool('compare_scenarios', arguments)


def test_actual_mcp_tool_compares_certified_files_without_loading_game_configuration(tmp_path):
    original, meitou, output = files(tmp_path)
    response = asyncio.run(mcp_compare(tmp_path, dict(original_report=str(original), meitou_report=str(meitou),
        output=str(output), position_tolerance=.25, number_tolerance=.125, arrival_radius=7.5)))
    assert not response.isError, response.content
    result = response.structuredContent if response.structuredContent is not None else json.loads(response.content[0].text)
    report = check_outputs(result, output)
    assert report['tolerances'] == dict(position=.25, number=.125)
    assert report['arrival_radius_world_units'] == 7.5
    assert not (tmp_path/'deliberately-absent-game-config.json').exists()


@pytest.mark.parametrize('failure', ['too_few_repetitions', 'missing_provenance'])
def test_actual_mcp_tool_rejects_invalid_cohorts_without_creating_output(tmp_path, failure):
    original, meitou, output = files(tmp_path, n=4 if failure == 'too_few_repetitions' else 5,
                                    missing_provenance=failure == 'missing_provenance')
    response = asyncio.run(mcp_compare(tmp_path, dict(original_report=str(original), meitou_report=str(meitou), output=str(output))))
    assert response.isError
    text = ' '.join(block.text for block in response.content if hasattr(block, 'text'))
    assert ('minimum' if failure == 'too_few_repetitions' else 'provenance') in text
    assert not output.exists()
