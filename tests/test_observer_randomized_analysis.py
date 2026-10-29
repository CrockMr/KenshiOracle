from collections import Counter
from copy import deepcopy
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

import analyze_observer_overhead as legacy
import analyze_observer_randomized as randomized
from test_observer_overhead_analysis import sample as old_sample, byte_count
from thread_resources import thread_deltas


ROOT = Path(__file__).resolve().parents[1]


def sample(seed=987654321):
    data = old_sample()
    originals = data['blocks']
    plan = randomized.make_plan(seed)
    data.update(protocol=randomized.PROTOCOL, measurement_valid=True, randomization_seed=seed, plan=plan,
                requested_block_seconds=5, requested_frames=60, warmup_seconds=1,
                started_at_wall_seconds=1001, own_source_sha256={'tests/synthetic.py': '1' * 64},
                cleanup_events=[], mcp_server_cpu={'available': True})
    data['initial_ping']['plugin_version'] = '0.8.20'
    data['installed_dll_sha256_before'] = data['installed_dll_sha256_after'] = legacy.EXPECTED_DLL_SHA256['0.8.20']
    first_function = originals[0]['statistics_tail']['systems']['profiled_function']
    data['initial_ping'].update(function_binding_source='loaded_module_export', command_service_timing_enabled=True,
        **{'function_' + name: first_function[name] for name in ('binding_module_path', 'binding_address', 'binding_symbol')})
    controller = dict(pid=101, created_at=20, executable='E:/Synthetic/python.exe',
                      cmdline=['E:/Synthetic/python.exe', 'tests/live_observer_randomized.py'], parent_pid=1)
    server = dict(pid=102, created_at=30, executable='E:/Synthetic/python.exe', parent_pid=101, token='synthetic-token',
                  cmdline=['E:/Synthetic/python.exe', 'E:/Synthetic/wrapper.py', '--identity', 'identity.json', '--token', 'synthetic-token'])
    data['controller_identity'] = deepcopy(controller)
    data['mcp_server_identity'] = deepcopy(server)
    data['mcp_server_launch_provenance'] = dict(controller_identity=deepcopy(controller), parent_chain=[deepcopy(controller)],
        command=list(server['cmdline']), allowed_executables=['E:/Synthetic/python.exe', 'E:/Synthetic/venv/python.exe'],
        wrapper_path='E:/Synthetic/wrapper.py')
    data['pre_registration'] = dict(path='registration.json', sha256='2' * 64, document=dict(
        protocol=randomized.PROTOCOL, randomization_seed=seed, plan=deepcopy(plan), plugin_version='0.8.20',
        dll_sha256=legacy.EXPECTED_DLL_SHA256['0.8.20'], source_sha256=deepcopy(data['own_source_sha256']),
        protocol_document=dict(path='docs/randomized-observer-protocol.md', sha256='3' * 64), registered_at=1000))
    for name in ('initial_scene', 'camera_reference', 'pre_release_scene', 'final_scene'):
        data[name].update(loaded_character_count=106, active_town_count=1)
    data['blocks'] = []
    for index, item in enumerate(plan):
        original = next(block for block in originals if block['plan']['frequency_hz'] == item['frequency_hz'] and block['plan']['condition'] == item['condition'])
        block = deepcopy(original)
        old_start = block['measured_start_monotonic_seconds']; start = 100 + index * 10
        def shift(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.endswith('monotonic_seconds'):
                        value[key] += start - old_start
                    else:
                        shift(child)
            elif isinstance(value, list):
                for child in value:
                    shift(child)
        shift(block)
        block.update(plan=dict(item), warmup_seconds=1,
                     warmup_start_monotonic_seconds=start-2, warmup_end_monotonic_seconds=start-1)
        r = block['process_resources']
        r['elapsed_seconds'] = r['after']['monotonic_seconds'] - r['before']['monotonic_seconds']
        r['logical_cpu_equivalents'] = (r['user_seconds'] + r['system_seconds']) / r['elapsed_seconds']
        r['thread_cpu'] = thread_deltas(r['before']['thread_snapshot'], r['after']['thread_snapshot'], r['elapsed_seconds'], r['user_seconds']+r['system_seconds'])
        for name in ('scene_before', 'selection_scene', 'scene_after'):
            block[name].update(loaded_character_count=106, active_town_count=1)
        extra = {'baseline': 0, 'full': .2, 'aggregates': .05}[item['condition']]
        block['mcp_server_cpu_before'] = dict(identity=deepcopy(server), user_seconds=100+index, system_seconds=10+index,
                                               monotonic_seconds=start-.04)
        block['mcp_server_cpu_after'] = dict(identity=deepcopy(server), user_seconds=100+index+.01+extra, system_seconds=10+index+.005,
                                              monotonic_seconds=start+5.04)
        data['blocks'].append(block)
    return data


@pytest.fixture(scope='module')
def baseline():
    return sample()


def treatment(data):
    return next(block for block in data['blocks'] if block['plan']['condition'] == 'full')


def detach_request(block):
    block['requests'][0]['result'] = deepcopy(block['requests'][0]['result'])
    return block['requests'][0]


@pytest.mark.parametrize('seed', [0, 1, 987654321, 2**64-1])
def test_randomized_plan_is_reproducible_complete_and_does_not_touch_global_rng(seed):
    state = random.getstate(); plan = randomized.make_plan(seed)
    assert random.getstate() == state and plan == randomized.make_plan(seed)
    assert len(plan) == 36 and [r['triad_index'] for r in plan] == [i for i in range(12) for _ in range(3)]
    for frequency in (1, 10):
        triads = {r['triad_index'] for r in plan if r['frequency_hz'] == frequency}
        assert {tuple(r['condition'] for r in plan if r['triad_index'] == triad) for triad in triads} == set(itertools.permutations(('baseline', 'full', 'aggregates')))
        assert Counter(r['condition'] for r in plan if r['frequency_hz'] == frequency) == dict(baseline=6, full=6, aggregates=6)
    assert [r['position'] for r in plan] == [0, 1, 2] * 12


@pytest.mark.parametrize('seed', [True, False, -1, 2**64, 1.0, '1', None])
def test_seed_is_strict_unsigned_64bit_integer(seed):
    with pytest.raises(ValueError, match='seed'):
        randomized.make_plan(seed)


def test_known_seed_plan_and_separate_cpu_scopes(baseline):
    assert [(row['condition'], row['frequency_hz']) for row in randomized.make_plan(0)[:3]] == [('baseline', 10), ('full', 10), ('aggregates', 10)]
    before = deepcopy(baseline); result = randomized.analyze(baseline)
    assert baseline == before and result['protocol'] == randomized.PROTOCOL
    assert result['validated_request_count'] == 660 and result['baseline_wake_count'] == 330
    assert result['population_reference'] == {'loaded_character_count': 106, 'active_town_count': 1}
    assert result['locked_population_scene_samples'] == 110
    row = result['blocks'][0]
    assert row['mcp_server_interval_seconds'] == pytest.approx(5.08)
    assert row['controller_interval_seconds'] == pytest.approx(5.06)
    assert row['process_interval_seconds'] == pytest.approx(5.02)
    assert row['root_thread_interval_seconds'] == pytest.approx(5.04)
    assert not any('combined' in name or 'total_observer' in name for name in row)
    paired = next(p for p in result['paired'] if p['frequency_hz'] == 10 and p['treatment'] == 'aggregates' and p['reference'] == 'full')
    assert paired['distributions']['mcp_server_cpu_seconds']['median'] == pytest.approx(-.15)
    assert paired['distributions']['mcp_server_logical_cpus']['median'] == pytest.approx(-.15 / 5.08)
    assert len(result['paired_request_comparisons']) == 2
    assert all(len(pair['differences']) == 6 for pair in result['paired_request_comparisons'])


@pytest.mark.parametrize('poison', ['seed', 'top_plan', 'block_plan', 'bool_plan', 'registration_plan', 'registration_seed',
    'registration_version', 'registration_dll', 'registration_sources', 'registration_after', 'registration_sha', 'protocol_sha',
    'duration', 'frames', 'warmup', 'completion', 'cleanup', 'cleanup_events', 'server_unavailable'])
def test_preregistered_protocol_and_complete_restoration_required(baseline, poison):
    data = deepcopy(baseline); registration = data['pre_registration']['document']
    if poison == 'seed': data['randomization_seed'] += 1
    elif poison == 'top_plan': data['plan'].reverse()
    elif poison == 'block_plan': data['blocks'][0]['plan']['position'] = 1
    elif poison == 'bool_plan': data['plan'][0]['triad_index'] = False
    elif poison == 'registration_plan': registration['plan'].reverse()
    elif poison == 'registration_seed': registration['randomization_seed'] += 1
    elif poison == 'registration_version': registration['plugin_version'] = '0.8.19'
    elif poison == 'registration_dll': registration['dll_sha256'] = '0'*64
    elif poison == 'registration_sources': registration['source_sha256']['tests/synthetic.py'] = '4'*64
    elif poison == 'registration_after': registration['registered_at'] = data['started_at_wall_seconds']+1
    elif poison == 'registration_sha': data['pre_registration']['sha256'] = 'z'*64
    elif poison == 'protocol_sha': registration['protocol_document']['sha256'] = 'bad'
    elif poison == 'duration': data['requested_block_seconds'] = 10
    elif poison == 'frames': data['requested_frames'] = 61
    elif poison == 'warmup': data['warmup_seconds'] = True
    elif poison == 'completion': data['completed'] = 1
    elif poison == 'cleanup': data['cleanup_transport_error'] = 'MCP failed; direct restitution done'
    elif poison == 'cleanup_events': data['cleanup_events'] = [{'fallback': True}]
    else: data['mcp_server_cpu']['available'] = False
    with pytest.raises(ValueError): randomized.analyze(data)


@pytest.mark.parametrize('poison', ['pid', 'creation', 'executable', 'command', 'parent', 'token', 'negative', 'nan',
    'bool_counter', 'inside_start', 'inside_end', 'reversed', 'cumulative', 'controller_pid', 'game_pid', 'warmup_short', 'block_overlap'])
def test_cpu_identity_bounds_and_raw_counters_fail_closed(baseline, poison):
    data = deepcopy(baseline); block = data['blocks'][0]; before = block['mcp_server_cpu_before']; after = block['mcp_server_cpu_after']
    if poison == 'pid': after['identity']['pid'] += 1
    elif poison == 'creation': after['identity']['created_at'] += 1
    elif poison == 'executable': after['identity']['executable'] = 'unrelated.exe'
    elif poison == 'command': after['identity']['cmdline'].append('--changed')
    elif poison == 'parent': after['identity']['parent_pid'] = 7
    elif poison == 'token': after['identity']['token'] = 'different'
    elif poison == 'negative': after['user_seconds'] = before['user_seconds']-1
    elif poison == 'nan': before['user_seconds'] = float('nan')
    elif poison == 'bool_counter': before['system_seconds'] = True
    elif poison == 'inside_start': before['monotonic_seconds'] = block['measured_start_monotonic_seconds']+.01
    elif poison == 'inside_end': after['monotonic_seconds'] = block['measured_end_monotonic_seconds']-.01
    elif poison == 'reversed': after['monotonic_seconds'] = before['monotonic_seconds']
    elif poison == 'cumulative': data['blocks'][1]['mcp_server_cpu_before']['user_seconds'] = before['user_seconds']-1
    elif poison == 'controller_pid': data['mcp_server_identity']['pid'] = data['controller_identity']['pid']
    elif poison == 'game_pid': data['mcp_server_identity']['pid'] = data['pid']
    elif poison == 'warmup_short': block['warmup_end_monotonic_seconds'] = block['warmup_start_monotonic_seconds']+.5
    else: data['blocks'][1]['warmup_start_monotonic_seconds'] = block['measured_start_monotonic_seconds']
    with pytest.raises(ValueError): randomized.analyze(data)


def test_cpu_greater_than_wall_remains_valid_and_zero_is_not_inferred_absence(baseline):
    data = deepcopy(baseline)
    data['blocks'][-1]['mcp_server_cpu_after']['user_seconds'] += 100
    result = randomized.analyze(data)
    assert result['blocks'][-1]['mcp_server_logical_cpus'] > 1
    before = data['blocks'][0]['mcp_server_cpu_before']; after = data['blocks'][0]['mcp_server_cpu_after']
    after.update(user_seconds=before['user_seconds'], system_seconds=before['system_seconds'])
    assert randomized.analyze(data)['blocks'][0]['mcp_server_cpu_seconds'] == 0


@pytest.mark.parametrize('poison', ['chain_missing', 'chain_too_long', 'chain_loop', 'parent_link', 'controller_identity', 'exe_allowed', 'argv0', 'argv_tail', 'launch_token', 'parent_newer'])
def test_launch_provenance_excludes_unrelated_children_and_wrappers(baseline, poison):
    data = deepcopy(baseline); launch = data['mcp_server_launch_provenance']
    if poison == 'chain_missing': launch['parent_chain'] = []
    elif poison == 'chain_too_long': launch['parent_chain'] *= 3
    elif poison == 'chain_loop': launch['parent_chain'][0]['pid'] = data['mcp_server_identity']['pid']
    elif poison == 'parent_link': data['mcp_server_identity']['parent_pid'] = 999
    elif poison == 'controller_identity': launch['controller_identity']['created_at'] += 1
    elif poison == 'exe_allowed': launch['allowed_executables'] = ['other.exe']
    elif poison == 'argv0': data['mcp_server_identity']['cmdline'][0] = 'other.exe'
    elif poison == 'argv_tail': data['mcp_server_identity']['cmdline'].append('--extra')
    elif poison == 'launch_token': launch['command'][-1] = 'other-token'
    else: launch['parent_chain'][0]['created_at'] = 100
    with pytest.raises(ValueError): randomized.analyze(data)


def test_single_verified_venv_launcher_is_not_counted_as_server(baseline):
    data = deepcopy(baseline); launch = data['mcp_server_launch_provenance']
    wrapper = dict(pid=103, created_at=25, executable='E:/Synthetic/venv/python.exe', parent_pid=101,
                   cmdline=['E:/Synthetic/venv/python.exe'] + launch['command'][1:])
    launch['command'][0] = 'E:/Synthetic/venv/python.exe'
    launch['parent_chain'].insert(0, wrapper)
    data['mcp_server_identity']['parent_pid'] = 103
    for block in data['blocks']:
        for name in ('mcp_server_cpu_before', 'mcp_server_cpu_after'):
            block[name]['identity']['parent_pid'] = 103
    result = randomized.analyze(data)
    assert result['mcp_server_identity']['pid'] == 102
    assert len(result['mcp_server_launch_provenance']['parent_chain']) == 2


@pytest.mark.parametrize('poison', ['population', 'town', 'pre_release_population', 'root_binding', 'request_root', 'root_cpu',
    'root_creation', 'root_overflow', 'service_creation', 'skip', 'baseline_wake', 'early', 'request_error'])
def test_every_request_root_population_and_slot_is_checked(baseline, poison):
    data = deepcopy(baseline); block = treatment(data); request = detach_request(block)
    if poison == 'population': block['selection_scene']['loaded_character_count'] += 1
    elif poison == 'town': block['scene_after']['active_town_count'] += 1
    elif poison == 'pre_release_population': data['pre_release_scene']['loaded_character_count'] += 1
    elif poison == 'root_binding': request['result']['systems']['profiled_function']['binding_address'] = '0x4567'
    elif poison == 'request_root': request['result']['systems']['profiled_function']['function'] = 'MedicalSystem::periodicUpdate'
    elif poison == 'root_cpu':
        f = request['result']['systems']['profiled_function']; f['cpu_unavailable_calls'] += 1; f['cpu_available_calls'] -= 1
        f['threads'][0]['cpu_unavailable_calls'] += 1; f['threads'][0]['cpu_available_calls'] -= 1
    elif poison == 'root_creation': request['result']['systems']['profiled_function']['threads'][0]['created_filetime'] = '999'
    elif poison == 'root_overflow':
        f = request['result']['systems']['profiled_function']; thread = f['threads'][0]; overflow = f['unlisted']
        f['threads_truncated'] = True
        for name in ('calls_total', 'cpu_available_calls'):
            thread[name] -= 1; overflow[name] = 1
        overflow['mean_ms'] = f['mean_ms'] / 60; thread['mean_ms'] -= overflow['mean_ms']
        overflow['max_call_ms'] = thread['max_call_ms']
        overflow['cpu_user_total_ms'] = 15.625; thread['cpu_user_total_ms'] -= 15.625
    elif poison == 'service_creation': request['result']['_probe_service']['created_filetime'] = '999'
    elif poison == 'skip':
        missing = block['requests'].pop(); block['skipped_slots'].append(dict(slot=missing['slot'], scheduled_offset_seconds=missing['scheduled_offset_seconds'], lateness_seconds=1, reason='wake_late'))
    elif poison == 'baseline_wake': next(b for b in data['blocks'] if b['plan']['condition'] == 'baseline')['baseline_wakes'].pop()
    elif poison == 'early': request['started_monotonic_seconds'] = block['measured_start_monotonic_seconds']-.01
    else: request['error'] = 'failed even though result exists'
    request['compact_result_bytes'] = byte_count(request['result'])
    with pytest.raises(ValueError): randomized.analyze(data)


def test_population_outside_locked_measurement_is_reported_separately(baseline):
    data = deepcopy(baseline); data['initial_scene']['loaded_character_count'] = 105; data['final_scene']['loaded_character_count'] = 107
    report = randomized.analyze(data)
    assert report['population_reference']['loaded_character_count'] == 106
    assert report['initial_population']['loaded_character_count'] == 105
    assert report['final_population']['loaded_character_count'] == 107


def test_optional_frozen_symbol_manifest_is_preserved_and_validated(baseline):
    data = deepcopy(baseline)
    manifest = dict(path='runtime/symbols/0.8.20/manifest.json', sha256='4' * 64)
    data['pre_registration']['document']['symbol_manifest'] = manifest
    assert randomized.analyze(data)['pre_registration']['symbol_manifest'] == manifest
    manifest['sha256'] = 'wrong'
    with pytest.raises(ValueError, match='symbol manifest'):
        randomized.analyze(data)


def test_v1_public_api_does_not_accept_randomized_protocol_or_seeded_order(baseline):
    with pytest.raises(ValueError, match='observer pilot'): legacy.analyze(baseline, '0.8.20')
    with pytest.raises(ValueError, match='0.8.20'): randomized.analyze(baseline, '0.8.19')


def test_cli_hash_exclusive_output_and_hash_seed_determinism(tmp_path, baseline):
    source = tmp_path / 'capture.json'; source.write_text(json.dumps(baseline), encoding='utf-8')
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    command = [sys.executable, str(ROOT / 'mcp-server/analyze_observer_randomized.py'), str(source), '--expected-sha256', sha]
    outputs = []
    for seed in ('0', '8675309'):
        output = tmp_path / ('analysis-' + seed + '.json')
        result = subprocess.run(command + ['--output', str(output)], env={**os.environ, 'PYTHONHASHSEED': seed}, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        outputs.append(output)
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    before = outputs[0].read_bytes()
    result = subprocess.run(command + ['--output', str(outputs[0])], capture_output=True, text=True)
    assert result.returncode != 0 and outputs[0].read_bytes() == before
    bad = tmp_path / 'bad.json'
    result = subprocess.run(command[:-1] + ['0'*64, '--output', str(bad)], capture_output=True, text=True)
    assert result.returncode != 0 and not bad.exists()
