"""Preregistered randomized observer confirmation, with separate MCP-server CPU."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import itertools
import json
import random
import re
from pathlib import Path, PureWindowsPath

from analyze_observer_overhead import (
    BLOCK_SECONDS, REQUEST_FRAMES, EXPECTED_DLL_SHA256, _analyze,
    distribution, number, version_identifier,
)
from command_service import validate as service
from function_diagnostics import validate as function, ROOT_FRAME_EXPORT

PROTOCOL = 'observer-overhead-randomized-v2'
WARMUP_SECONDS = 1
IDENTITY_FIELDS = ('pid', 'created_at', 'executable', 'cmdline')
SERVER_METRICS = ('mcp_server_logical_cpus', 'mcp_server_cpu_seconds',
                  'mcp_server_user_seconds', 'mcp_server_system_seconds')


def integer(value, label, low=0, high=None):
    if type(value) is not int or value < low or high is not None and value > high:
        raise ValueError('Invalid ' + label)
    return value


def text(value, label):
    if type(value) is not str or not value or value != value.strip():
        raise ValueError('Invalid ' + label)
    return value


def digest(value, label):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid ' + label)
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def make_plan(seed):
    """Shuffle canonical (permutation, frequency) triads; preserve each triad."""
    integer(seed, 'randomization seed', high=2**64 - 1)
    triads = [(frequency, order)
              for order in itertools.permutations(('baseline', 'full', 'aggregates'))
              for frequency in (1, 10)]
    random.Random(seed).shuffle(triads)
    return [dict(triad_index=index, frequency_hz=frequency, position=position, condition=condition)
            for index, (frequency, order) in enumerate(triads)
            for position, condition in enumerate(order)]


def check_plan(value, expected):
    if type(value) is not list or len(value) != len(expected):
        raise ValueError('Randomized plan has missing or extra blocks')
    for actual, planned in zip(value, expected):
        if (type(actual) is not dict or set(actual) != set(planned) or
                any(type(actual[key]) is not type(planned[key]) or actual[key] != planned[key] for key in planned)):
            raise ValueError('Randomized plan differs from its seed')


def identity(value, label, *, server=False, parent=False):
    if type(value) is not dict:
        raise ValueError('Invalid ' + label + ' identity')
    integer(value['pid'], label + ' PID', 1)
    if number(value['created_at'], label + ' creation') <= 0:
        raise ValueError('Invalid ' + label + ' creation')
    text(value['executable'], label + ' executable')
    command = value['cmdline']
    if type(command) is not list or not command or any(type(part) is not str or not part for part in command):
        raise ValueError('Invalid ' + label + ' command line')
    if server or parent:
        integer(value['parent_pid'], label + ' parent PID', 1)
        if value['parent_pid'] == value['pid']:
            raise ValueError('Self-parented ' + label)
    if server:
        text(value['token'], label + ' launch token')
    return value


def identity_core(value):
    return {key: value[key] for key in IDENTITY_FIELDS}


def normalized_path(value):
    return str(PureWindowsPath(value)).casefold()


def validate_launch(data):
    server = identity(data['mcp_server_identity'], 'MCP server', server=True)
    controller = identity(data['controller_identity'], 'controller')
    integer(data['pid'], 'game PID', 1)
    number(data['created_at'], 'game creation')
    if len({server['pid'], controller['pid'], data['pid']}) != 3:
        raise ValueError('MCP server, controller and game are not distinct processes')
    launch = data['mcp_server_launch_provenance']
    identity(launch['controller_identity'], 'launch controller')
    if canonical(identity_core(launch['controller_identity'])) != canonical(identity_core(controller)):
        raise ValueError('Launch controller identity differs')
    allowed = launch['allowed_executables']
    if type(allowed) is not list or not 1 <= len(allowed) <= 2:
        raise ValueError('Invalid allowed MCP executables')
    allowed_paths = [normalized_path(text(value, 'allowed executable')) for value in allowed]
    if len(set(allowed_paths)) != len(allowed_paths) or normalized_path(server['executable']) not in allowed_paths:
        raise ValueError('MCP executable not allowed or duplicated')
    wrapper = text(launch['wrapper_path'], 'MCP wrapper path')
    command = launch['command']
    if (type(command) is not list or len(command) != 6 or
            any(type(part) is not str or not part for part in command) or
            normalized_path(command[0]) not in allowed_paths or command[1] != wrapper or
            command[2] != '--identity' or command[4] != '--token' or command[5] != server['token']):
        raise ValueError('MCP launch command or token differs')
    def command_matches(value):
        return (normalized_path(value['executable']) in allowed_paths and
                normalized_path(value['cmdline'][0]) in allowed_paths and
                value['cmdline'][1:] == command[1:])
    if not command_matches(server):
        raise ValueError('MCP process command is not the registered wrapper')
    chain = launch['parent_chain']
    if type(chain) is not list or len(chain) not in (1, 2):
        raise ValueError('MCP launch parent chain must be direct or one launcher')
    for value in chain:
        identity(value, 'launch parent', parent=True)
    if (server['parent_pid'] != chain[0]['pid'] or
            len({server['pid'], *(entry['pid'] for entry in chain)}) != len(chain) + 1 or
            any(entry['pid'] == data['pid'] for entry in chain) or
            canonical(identity_core(chain[-1])) != canonical(identity_core(controller))):
        raise ValueError('MCP launch parent chain is inconsistent')
    if len(chain) == 2 and (chain[0]['parent_pid'] != chain[1]['pid'] or not command_matches(chain[0])):
        raise ValueError('MCP launcher is not the registered intermediate')
    child_created = server['created_at']
    for entry in chain:
        if entry['created_at'] > child_created:
            raise ValueError('MCP parent was created after its child')
        child_created = entry['created_at']
    return server, controller, launch


def validate_registration(data, plan, version):
    registration = data['pre_registration']
    text(registration['path'], 'preregistration path')
    digest(registration['sha256'], 'preregistration SHA-256')
    document = registration['document']
    if (document['protocol'] != PROTOCOL or
            type(document['randomization_seed']) is not int or
            document['randomization_seed'] != data['randomization_seed'] or
            document['plugin_version'] != version or document['dll_sha256'] != EXPECTED_DLL_SHA256[version]):
        raise ValueError('Preregistration protocol, seed, version or DLL differs')
    check_plan(document['plan'], plan)
    sources = document['source_sha256']
    if type(sources) is not dict or not sources or canonical(sources) != canonical(data['own_source_sha256']):
        raise ValueError('Preregistered source inventory differs')
    for path, value in sources.items():
        text(path, 'source path'); digest(value, 'source SHA-256')
    protocol_document = document['protocol_document']
    text(protocol_document['path'], 'protocol document path')
    digest(protocol_document['sha256'], 'protocol document SHA-256')
    registered = number(document['registered_at'], 'preregistration timestamp')
    started = number(data['started_at_wall_seconds'], 'capture wall start')
    if not 0 < registered <= started:
        raise ValueError('Preregistration is not before the capture')
    result = dict(path=registration['path'], sha256=registration['sha256'], registered_at=registered,
                protocol_document=protocol_document, source_sha256=sources,
                scope='Inline declared plan and source inventory checked; raw preregistration file SHA is verified separately before acquisition.')
    if 'symbol_manifest' in document:
        symbol_manifest = document['symbol_manifest']
        text(symbol_manifest['path'], 'symbol manifest path')
        digest(symbol_manifest['sha256'], 'symbol manifest SHA-256')
        result['symbol_manifest'] = symbol_manifest
    return result


def population(scene):
    return {name: integer(scene[name], name) for name in ('loaded_character_count', 'active_town_count')}


def server_cpu(block, reference):
    before, after = block['mcp_server_cpu_before'], block['mcp_server_cpu_after']
    for endpoint in (before, after):
        identity(endpoint['identity'], 'MCP endpoint', server=True)
        if canonical(endpoint['identity']) != canonical(reference):
            raise ValueError('MCP server identity changed at a CPU endpoint')
        for name in ('user_seconds', 'system_seconds', 'monotonic_seconds'):
            number(endpoint[name], 'MCP ' + name)
    start, end = before['monotonic_seconds'], after['monotonic_seconds']
    elapsed = end - start
    if not start <= block['measured_start_monotonic_seconds'] < block['measured_end_monotonic_seconds'] <= end or elapsed <= 0:
        raise ValueError('MCP CPU bounds do not enclose measured collection')
    user = number(after['user_seconds'] - before['user_seconds'], 'MCP user CPU delta')
    system = number(after['system_seconds'] - before['system_seconds'], 'MCP system CPU delta')
    return dict(mcp_server_user_seconds=user, mcp_server_system_seconds=system,
                mcp_server_cpu_seconds=user + system, mcp_server_logical_cpus=(user + system) / elapsed,
                mcp_server_interval_seconds=elapsed,
                mcp_server_interval_start_monotonic_seconds=start, mcp_server_interval_end_monotonic_seconds=end)


def root_result(stats, ping, key):
    selected = function(stats)
    if (selected is None or selected['function'] != 'Ogre::Root::renderOneFrame' or
            selected['cpu_enabled'] is not True or selected['cpu_unavailable_calls'] != 0 or
            selected['cpu_available_calls'] != selected['calls_total'] or selected['calls_total'] <= 0 or
            len(selected['threads']) != 1 or selected['threads_truncated'] is not False or selected['unlisted']['calls_total'] != 0 or
            (selected['threads'][0]['thread_id'], selected['threads'][0]['created_filetime']) != key):
        raise ValueError('Request Root function, CPU coverage or creation differs')
    for function_name, ping_name in (
            ('binding_module_path', 'function_binding_module_path'),
            ('binding_symbol', 'function_binding_symbol'), ('binding_address', 'function_binding_address')):
        if selected[function_name] != ping[ping_name]:
            raise ValueError('Request Root export binding differs from initial ping')
    timing = service(stats, 'get_frame_stats')
    if timing['menu_service'] or (timing['thread_id'], timing['created_filetime']) != key:
        raise ValueError('Request service identity differs from Root')


def analyze(data, expected_version='0.8.20'):
    try:
        return _randomized(data, expected_version)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('Missing or malformed randomized observer evidence: ' + str(exc)) from exc


def _randomized(data, expected_version):
    version = version_identifier(expected_version)
    if version != '0.8.20':
        raise ValueError('Randomized confirmation requires expected version 0.8.20')
    plan = make_plan(data['randomization_seed'])
    check_plan(data['plan'], plan)
    check_plan([block['plan'] for block in data['blocks']], plan)
    if (data.get('completed') is not True or data.get('measurement_valid') is not True or
            data.get('cleanup_transport_error') or data.get('cleanup_events') or data.get('mcp_server_cpu_error')):
        raise ValueError('Randomized confirmation is incomplete or cleanup/CPU failed')
    for name, expected in (('requested_block_seconds', BLOCK_SECONDS), ('requested_frames', REQUEST_FRAMES), ('warmup_seconds', WARMUP_SECONDS)):
        if type(data[name]) is not int or data[name] != expected:
            raise ValueError('Randomized confirmation duration/frame contract differs')
    registration = validate_registration(data, plan, version)
    server, controller, launch = validate_launch(data)
    if data['mcp_server_cpu']['available'] is not True:
        raise ValueError('MCP server CPU is not declared available')
    ping = data['initial_ping']
    if (ping['function_binding_source'] != 'loaded_module_export' or ping['function_binding_symbol'] != ROOT_FRAME_EXPORT or
            ping['command_service_timing_enabled'] is not True):
        raise ValueError('Initial Root binding or service timing differs')
    # Fixed v2 protocol/seeded plan enter the shared v1 measurement core. Public
    # v1 still accepts only its original protocol and canonical balanced order.
    result = _analyze(data, version, protocol=PROTOCOL, plan=plan)
    expected_population = population(data['camera_reference'])
    if population(data['pre_release_scene']) != expected_population:
        raise ValueError('Population changed before camera release')
    root = result['blocks'][0]['root_identity']
    root_key = (root['thread_id'], root['created_filetime'])
    previous_end = None
    previous_server_cpu = None
    requests = wakes = 0
    for block, row in zip(data['blocks'], result['blocks']):
        if block['completed'] is not True or block['skipped_slots']:
            raise ValueError('Randomized confirmation requires every scheduled slot')
        if row['root_identity'] != root:
            raise ValueError('Root lifetime changed between randomized blocks')
        if type(block['warmup_seconds']) is not int or block['warmup_seconds'] != WARMUP_SECONDS:
            raise ValueError('Block warmup differs from preregistered duration')
        warm_start = number(block['warmup_start_monotonic_seconds'], 'warmup start')
        warm_end = number(block['warmup_end_monotonic_seconds'], 'warmup end')
        if warm_end - warm_start < WARMUP_SECONDS or previous_end is not None and warm_start < previous_end:
            raise ValueError('Warmup is too short or randomized blocks overlap')
        endpoints = [(block['controller_cpu_before'], block['controller_cpu_after']),
                     (block['process_resources']['before'], block['process_resources']['after']),
                     (block['mcp_server_cpu_before'], block['mcp_server_cpu_after'])]
        for before, after in endpoints:
            start = number(before['monotonic_seconds'], 'CPU endpoint start')
            end = number(after['monotonic_seconds'], 'CPU endpoint end')
            if not warm_end <= start < end:
                raise ValueError('CPU endpoint precedes neutral warmup or is unordered')
        for endpoint in endpoints[0]:
            number(endpoint['user'], 'controller raw user CPU'); number(endpoint['system'], 'controller raw system CPU')
        for endpoint in endpoints[1]:
            number(endpoint['created_at'], 'game creation')
            number(endpoint['user_seconds'], 'game raw user CPU'); number(endpoint['system_seconds'], 'game raw system CPU')
        previous_end = max(after['monotonic_seconds'] for _, after in endpoints)
        for name in ('scene_before', 'selection_scene', 'scene_after'):
            if population(block[name]) != expected_population:
                raise ValueError('Population changed inside randomized blocks')
        row.update(server_cpu(block, server), **expected_population)
        if previous_server_cpu is not None and any(block['mcp_server_cpu_before'][name] < previous_server_cpu[name]
                                                  for name in ('user_seconds', 'system_seconds')):
            raise ValueError('MCP cumulative CPU decreased between blocks')
        previous_server_cpu = block['mcp_server_cpu_after']
        root_result(block['statistics_tail'], ping, root_key)
        for request in block['requests']:
            if request.get('error'):
                raise ValueError('Randomized request contains an error')
            root_result(request['result'], ping, root_key)
        requests += len(block['requests']); wakes += len(block['baseline_wakes'])
    if requests != 660 or wakes != 330:
        raise ValueError('Randomized confirmation requires 660 requests and 330 baseline wakes')
    for pair in result['paired']:
        selected = {row['triad_index']: {} for row in result['blocks'] if row['frequency_hz'] == pair['frequency_hz']}
        for row in result['blocks']:
            if row['frequency_hz'] == pair['frequency_hz']:
                selected[row['triad_index']][row['condition']] = row
        for delta in pair['differences']:
            values = selected[delta['triad_index']]
            delta.update({name: values[pair['treatment']][name] - values[pair['reference']][name] for name in SERVER_METRICS})
        pair['distributions'].update({name: distribution([delta[name] for delta in pair['differences']]) for name in SERVER_METRICS})
    request_pairs = []
    for frequency in (1, 10):
        differences = []
        for triad in sorted({row['triad_index'] for row in result['blocks'] if row['frequency_hz'] == frequency}):
            selected = {row['condition']: row for row in result['blocks'] if row['triad_index'] == triad}
            differences.append(dict(triad_index=triad, **{
                name: selected['aggregates']['request_distributions'][name]['median'] - selected['full']['request_distributions'][name]['median']
                for name in ('client_ms', 'service_ms', 'queue_wait_ms', 'compact_result_bytes')}))
        request_pairs.append(dict(frequency_hz=frequency, treatment='aggregates', reference='full', differences=differences,
            distributions={name: distribution([row[name] for row in differences]) for name in differences[0] if name != 'triad_index'}))
    result.update(randomization_seed=data['randomization_seed'], plan=plan, pre_registration=registration,
        mcp_server_identity=server, controller_identity=controller, mcp_server_launch_provenance=launch,
        mcp_server_cpu_scope='The owned MCP Python process only; excludes its launcher and controller. Raw CPU deltas use each separately enclosing QPC interval; never summed with controller or game.',
        population_reference=expected_population, locked_population_scene_samples=110,
        initial_population=population(data['initial_scene']), final_population=population(data['final_scene']),
        root_identity=root, root_binding={name: ping['function_' + name] for name in ('binding_source', 'binding_module_path', 'binding_address', 'binding_symbol')},
        validated_request_count=requests, baseline_wake_count=wakes, paired_request_comparisons=request_pairs)
    result['limits'][0] = 'Preregistered single-session paused confirmation; the 12 balanced triads were shuffled with the recorded seed. No active-scene or FPS conclusion.'
    result['limits'][4] = 'MCP-server and controller CPU are separate processes sampled over distinct enclosing intervals. No combined CPU total is reported; compact JSON bytes exclude transport envelopes.'
    result['limits'].extend([
        'Stable loaded-character and active-town counts do not prove unchanged entity state, CPU stationarity or absence of carry-over.',
        'The native Root binding, CPU coverage and thread lifetime were checked for every request and endpoint; native call CPU and wider OS counters still have distinct scopes.',
        'Declared preregistration timestamps and inline document are checked here; the capture SHA and external raw preregistration hash are separate provenance checks.',
    ])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-version', type=version_identifier, default='0.8.20')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes(); actual = hashlib.sha256(raw).hexdigest()
    if actual != digest(args.expected_sha256, 'capture SHA-256'):
        raise ValueError('Capture SHA-256 differs')
    report = dict(source=str(args.source), source_sha256=actual, result=analyze(json.loads(raw), args.expected_version))
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps(dict(output=str(args.output), completed=True, blocks=len(report['result']['blocks']))))


if __name__ == '__main__':
    main()
