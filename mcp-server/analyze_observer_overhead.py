"""Reproducible paired observer pilot; no engine control or causal FPS estimate."""
import argparse
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path

from benchmark import validate_camera_stability, validate_nav_diagnostics
from command_service import validate as service
from function_diagnostics import validate as function, match_cpu
from statistics_detail import validate as detail
from thread_resources import thread_deltas
from analyze_pause_cpu import bounded_tail_count
from statistics_budget import validate_plan

PROTOCOL = 'observer-overhead-v1'
BLOCK_SECONDS = 5
REQUEST_FRAMES = 60
EXPECTED_DLL_SHA256 = {
    '0.8.19': '796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3',
    '0.8.20': '0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e',
}


def version_identifier(value):
    if type(value) is not str or not value or value != value.strip():
        raise ValueError('Expected version must be a nonempty identifier without surrounding whitespace')
    return value


def make_plan():
    """Every order once per frequency, frequencies interleaved deterministically."""
    plan = []
    for order_index, order in enumerate(itertools.permutations(('baseline', 'full', 'aggregates'))):
        for frequency_index, frequency in enumerate((1, 10)):
            for position, condition in enumerate(order):
                plan.append(dict(triad_index=order_index * 2 + frequency_index,
                                 frequency_hz=frequency, position=position, condition=condition))
    return plan


def number(value, label, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError('Invalid ' + label)
    return value


def equal(actual, expected, label):
    if type(actual) not in (int, float) or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-7):
        raise ValueError('Inconsistent ' + label)


def distribution(values):
    return dict(count=len(values), minimum=min(values), median=statistics.median(values),
                maximum=max(values), mean=statistics.mean(values)) if values else None


def validate_resources(resources, pid, created_at):
    if resources['pid'] != pid:
        raise ValueError('Process PID changed')
    before, after = resources['before'], resources['after']
    if before['created_at'] != created_at or after['created_at'] != created_at:
        raise ValueError('Process creation changed')
    elapsed = after['monotonic_seconds'] - before['monotonic_seconds']
    if number(elapsed, 'CPU interval') == 0:
        raise ValueError('Empty CPU interval')
    user = number(after['user_seconds'] - before['user_seconds'], 'user delta')
    kernel = number(after['system_seconds'] - before['system_seconds'], 'kernel delta')
    equal(resources['elapsed_seconds'], elapsed, 'CPU elapsed')
    equal(resources['user_seconds'], user, 'CPU user')
    equal(resources['system_seconds'], kernel, 'CPU kernel')
    equal(resources['logical_cpu_equivalents'], (user + kernel) / elapsed, 'CPU normalization')
    derived = thread_deltas(before['thread_snapshot'], after['thread_snapshot'], elapsed, user + kernel)
    if derived != resources['thread_cpu']:
        raise ValueError('Thread CPU differs from raw endpoint snapshots')
    return derived


def paired_summary(rows):
    """Within-triad signed differences; retain all repetitions and their ranges."""
    result = []
    for frequency in (1, 10):
        selected = [r for r in rows if r['frequency_hz'] == frequency]
        for treatment, reference in [('full', 'baseline'), ('aggregates', 'baseline'), ('aggregates', 'full')]:
            differences = []
            for triad in sorted({r['triad_index'] for r in selected}):
                values = {r['condition']: r for r in selected if r['triad_index'] == triad}
                if set(values) != {'baseline', 'full', 'aggregates'}:
                    raise ValueError('Incomplete paired triad')
                differences.append(dict(triad_index=triad, **{
                    name: values[treatment][name] - values[reference][name]
                    for name in ('game_logical_cpus', 'root_thread_logical_cpus', 'controller_logical_cpus', 'callback_mean_ms')
                }))
            result.append(dict(frequency_hz=frequency, treatment=treatment, reference=reference,
                               differences=differences, distributions={
                                   name: distribution([r[name] for r in differences]) for name in differences[0] if name != 'triad_index'
                               }))
    return result


def analyze(data, expected_version='0.8.19'):
    return _analyze(data, expected_version, protocol=PROTOCOL, plan=make_plan())


def _analyze(data, expected_version, *, protocol, plan):
    """Shared strict measurements; public v1 fixes its original protocol and plan."""
    expected_version = version_identifier(expected_version)
    if expected_version not in EXPECTED_DLL_SHA256:
        raise ValueError('No trusted DLL SHA-256 registered for expected version ' + expected_version)
    if data.get('protocol') != protocol or not data.get('completed'):
        raise ValueError('Incomplete or unknown observer pilot')
    clock = data['measurement_clock']
    if (clock['name'] != 'perf_counter' or clock['monotonic'] is not True or clock['adjustable'] is not False or
            not 0 < number(clock['resolution'], 'measurement clock resolution') < .001):
        raise ValueError('Unknown or insufficient measurement clock')
    if any(data.get(k) for k in ('error', 'restoration_error', 'camera_release_error', 'final_audit_error', 'pre_release_error', 'final_scene_error')):
        raise ValueError('Observer pilot contains an error')
    if (data.get('protected_files_unchanged') is not True or data.get('settings_unchanged') is not True or
            data.get('own_sources_unchanged') is not True):
        raise ValueError('Protected state was not preserved')
    if (any(data['guards_before'].values()) or any(data['guards_after'].values()) or
            data['installed_dll_sha256_before'] != data['installed_dll_sha256_after'] or
            data['installed_dll_sha256_before'] != EXPECTED_DLL_SHA256[expected_version]):
        raise ValueError('DLL or restoration guards differ')
    ping = data['initial_ping']
    if (ping['plugin_version'] != expected_version or ping['system_hook_count'] != 3 or
            not ping['frame_stats_aggregates_available'] or not ping['function_thread_cpu_enabled'] or
            ping['profiled_function'] != 'Ogre::Root::renderOneFrame' or
            (ping['dedicated_system_hook_count'], ping['service_hook_count'], ping['installed_hook_count']) != (3, 2, 5) or
            not ping['ogre_render_one_frame_profiling'] or ping['function_hook_reuses_service']):
        raise ValueError('Unexpected native observer configuration')
    if [r['plan'] for r in data['blocks']] != plan:
        raise ValueError('Observer order or paired block count differs')
    reference = data['initial_scene']
    camera_reference = data['camera_reference']
    def scene_guard(scene, camera=True):
        if (scene['paused'] is not True or scene['frame_speed_multiplier'] != 0 or
                scene['game_total_hours'] != reference['game_total_hours'] or scene['battle']['active']):
            raise ValueError('Paused game state changed')
        if camera:
            validate_camera_stability(camera_reference, scene)
    scene_guard(reference, camera=False)
    scene_guard(camera_reference)
    scene_guard(data['pre_release_scene'])
    scene_guard(data['final_scene'], camera=False)
    for scene in (camera_reference, data['pre_release_scene']):
        if not scene['scene_camera_control_owned'] or scene['edge_scrolling'] or scene['free_camera']:
            raise ValueError('Measured camera reference was not locked')
    if data['final_scene']['scene_camera_control_owned'] or data['final_scene']['free_camera']:
        raise ValueError('Camera control was not released')
    if data['final_scene']['edge_scrolling'] != reference['edge_scrolling']:
        raise ValueError('Original Edge state was not restored')
    rows = []
    for index, block in enumerate(data['blocks']):
        if not block.get('completed'):
            raise ValueError('Incomplete observer block')
        plan = block['plan']; condition = plan['condition']; frequency = plan['frequency_hz']
        for key in ('scene_before', 'scene_after', 'selection_scene'):
            scene_guard(block[key])
            if not block[key]['scene_camera_control_owned'] or block[key]['edge_scrolling'] or block[key]['free_camera']:
                raise ValueError('Camera lock was lost during measurement')
        resources = block['process_resources']
        derived = validate_resources(resources, data['pid'], data['created_at'])
        if Path(resources['executable']).resolve() != Path(data['executable']).resolve():
            raise ValueError('Resource executable differs')
        start = number(block['measured_start_monotonic_seconds'], 'block start')
        end = number(block['measured_end_monotonic_seconds'], 'block end')
        elapsed = end - start
        if elapsed < BLOCK_SECONDS or not resources['before']['monotonic_seconds'] <= start < end <= resources['after']['monotonic_seconds']:
            raise ValueError('Measured block is outside enclosing CPU interval')
        requests = block['requests']; slots = set(); measurements = []
        previous_slot = -1; previous_finish = start
        for request in requests:
            slot = request['slot']
            if type(slot) is not int or not 0 <= slot < BLOCK_SECONDS * frequency or slot in slots:
                raise ValueError('Invalid or duplicated request slot')
            slots.add(slot)
            equal(request['scheduled_offset_seconds'], slot / frequency, 'slot offset')
            begun = number(request['started_monotonic_seconds'], 'request start')
            finished = number(request['finished_monotonic_seconds'], 'request end')
            if not start + slot / frequency <= begun <= finished <= end:
                raise ValueError('Request outside measured block')
            if slot <= previous_slot or previous_finish > start + slot / frequency or begun - start - slot / frequency >= 1 / frequency:
                raise ValueError('Requests overlap, are unordered or catch up a late slot')
            previous_slot, previous_finish = slot, finished
            equal(request['client_ms'], (finished - begun) * 1000, 'request elapsed')
            equal(request['lateness_seconds'], begun - start - slot / frequency, 'request lateness')
            equal(request['overrun_seconds'], max(0, finished - start - BLOCK_SECONDS), 'request overrun')
            result = request['result']
            if condition == 'baseline' or detail(result) != condition or result['count'] != REQUEST_FRAMES:
                raise ValueError('Unexpected request or statistics detail')
            timing = service(result, 'get_frame_stats'); validate_nav_diagnostics(result); function(result)
            if timing['menu_service']:
                raise ValueError('Statistics executed by menu service')
            size = len(json.dumps(result, separators=(',', ':')).encode())
            if type(request['compact_result_bytes']) is not int or request['compact_result_bytes'] != size or size >= 65536:
                raise ValueError('Encoded result byte count differs')
            measurements.append(dict(client_ms=request['client_ms'], service_ms=timing['service_ms'],
                                     queue_wait_ms=timing['queue_wait_ms'], compact_result_bytes=size,
                                     lateness_seconds=request['lateness_seconds'], overrun_seconds=request['overrun_seconds']))
        skipped = block['skipped_slots']
        skipped_indices = [r['slot'] for r in skipped]
        if len(set(skipped_indices)) != len(skipped_indices) or slots.intersection(skipped_indices):
            raise ValueError('Slot was both requested and skipped or skipped twice')
        for missed in skipped:
            slot = missed['slot']
            if type(slot) is not int or not 0 <= slot < BLOCK_SECONDS * frequency:
                raise ValueError('Invalid skipped slot')
            equal(missed['scheduled_offset_seconds'], slot / frequency, 'skipped offset')
            lateness = number(missed['lateness_seconds'], 'skipped lateness')
            if missed['reason'] == 'wake_late':
                if lateness < 1 / frequency:
                    raise ValueError('Skipped slot was not late by a period')
            elif missed['reason'] == 'previous_request_overrun':
                if not any(r['slot'] < slot and r['finished_monotonic_seconds'] > start + slot / frequency for r in requests):
                    raise ValueError('Skipped slot has no preceding overrun')
            else:
                raise ValueError('Unknown skipped slot reason')
        if condition != 'baseline' and slots | set(skipped_indices) != set(range(BLOCK_SECONDS * frequency)):
            raise ValueError('Request slots are missing from evidence')
        if condition == 'baseline' and requests:
            raise ValueError('Baseline unexpectedly issued a getter')
        wakes = block.get('baseline_wakes', [])
        wake_slots = [r['slot'] for r in wakes]
        if condition == 'baseline':
            if (len(set(wake_slots)) != len(wake_slots) or set(wake_slots).intersection(skipped_indices) or
                    set(wake_slots) | set(skipped_indices) != set(range(BLOCK_SECONDS * frequency))):
                raise ValueError('Baseline timer slots are not fully recorded')
            for wake in wakes:
                slot = wake['slot']
                if type(slot) is not int or not 0 <= slot < BLOCK_SECONDS * frequency:
                    raise ValueError('Invalid baseline timer slot')
                equal(wake['scheduled_offset_seconds'], slot / frequency, 'baseline offset')
                begun = number(wake['started_monotonic_seconds'], 'baseline wake')
                if not start + slot / frequency <= begun <= end:
                    raise ValueError('Baseline wake outside block')
                equal(wake['lateness_seconds'], begun - start - slot / frequency, 'baseline lateness')
                if wake['lateness_seconds'] >= 1 / frequency:
                    raise ValueError('Baseline late wake should have been skipped')
        elif wakes:
            raise ValueError('Treatment unexpectedly contains baseline wakes')
        stats = block['statistics_tail']
        if detail(stats) != 'aggregates' or stats['count'] != block['requested_frames']:
            raise ValueError('Endpoint statistics lost requested frames')
        available = block['selection_scene']['frame'] - block['scene_before']['frame'] - 1
        if available > 3600:
            raise ValueError('Endpoint window exceeds the retained history budget')
        requested = bounded_tail_count(block['scene_before']['frame'], block['selection_scene']['frame'], 3600)
        if type(block['requested_frames']) is not int or not 1 <= requested == block['requested_frames'] <= 3600:
            raise ValueError('Endpoint frame request differs from selection')
        if not block['scene_before']['frame'] < stats['first_frame'] <= stats['last_frame'] <= block['scene_after']['frame']:
            raise ValueError('Endpoint statistics outside scene bounds')
        trace = block['statistics_collection']; validate_plan(trace, requested)
        attempts = trace['attempts']
        if (trace.get('detail') != 'aggregates' or trace['selected_count'] != requested or
                len(attempts) != 1 or not attempts[0]['ok'] or
                attempts[0]['compact_bytes'] != len(json.dumps(stats, separators=(',', ':')).encode())):
            raise ValueError('Endpoint statistics required retry or have altered bytes')
        selected = function(stats); validate_nav_diagnostics(stats)
        if (selected['function'] != 'Ogre::Root::renderOneFrame' or len(selected['threads']) != 1 or
                not selected['cpu_enabled'] or selected['cpu_unavailable_calls'] or
                selected['cpu_available_calls'] != selected['calls_total']):
            raise ValueError('Root thread attribution unavailable')
        joined = match_cpu(selected, resources)['threads'][0]
        if not joined['matched_cpu_identity']:
            raise ValueError('Root creation not present at both CPU endpoints')
        key = (joined['thread_id'], joined['created_filetime'])
        root = next(r for r in derived['threads'] if (r['tid'], r['created_filetime']) == key)
        for request in requests:
            timing = request['result']['_probe_service']
            if (timing['thread_id'], timing['created_filetime']) != key:
                raise ValueError('Getter service identity differs from Root')
        before, after = block['controller_cpu_before'], block['controller_cpu_after']
        controller_cpu = sum(number(after[name] - before[name], 'controller CPU delta') for name in ('user', 'system'))
        controller_elapsed = after['monotonic_seconds'] - before['monotonic_seconds']
        if not before['monotonic_seconds'] <= start < end <= after['monotonic_seconds'] or controller_elapsed <= 0:
            raise ValueError('Controller CPU bounds do not enclose the measured block')
        rows.append(dict(index=index, **plan, requests=len(requests), skipped_slots=len(skipped),
            actual_block_seconds=elapsed, process_interval_seconds=resources['elapsed_seconds'],
            game_logical_cpus=resources['logical_cpu_equivalents'], root_thread_logical_cpus=root['logical_cpu_equivalents'],
            controller_logical_cpus=controller_cpu / controller_elapsed, controller_cpu_seconds=controller_cpu,
            controller_interval_seconds=controller_elapsed,
            root_identity=dict(thread_id=key[0], created_filetime=key[1]),
            root_thread_interval_seconds=root['elapsed_seconds'], thread_omissions=derived['omitted'],
            signed_process_thread_residual_seconds=derived['residual_cpu_seconds'],
            callback_mean_ms=number(stats['mean_ms'], 'callback mean'), callback_p99_ms=number(stats['p99_ms'], 'callback p99'),
            callback_frames=stats['count'], callback_first_frame=stats['first_frame'], callback_last_frame=stats['last_frame'],
            request_distributions={name: distribution([r[name] for r in measurements])
                                   for name in ('client_ms', 'service_ms', 'queue_wait_ms', 'compact_result_bytes', 'lateness_seconds', 'overrun_seconds')}))
    return dict(completed=True, protocol=protocol, pid=data['pid'], created_at=data['created_at'], measurement_clock=clock, blocks=rows,
                paired=paired_summary(rows), limits=[
        'Exploratory single-session paused pilot; order is balanced, not randomized. No active-scene or FPS conclusion.',
        'Baseline still includes the existing plugin, watchdog, service hooks, endpoint probes and matched timer wakes.',
        'OS process, OS thread, controller counter and retained callback windows differ. Their timings are not interchangeable.',
        'Endpoint statistics and JSON validation/encoding occur after measured CPU collection; their carry-over is not ruled out.',
        'Controller CPU excludes the separate MCP server process; compact JSON result bytes exclude transport envelopes.',
        'Native service time excludes network serialization/send and client transport; no exclusive CPU inferred from it.',
        'Quantized CPU counters, sequential endpoint samples and scheduler jitter remain; signed residuals are not clamped.',
        'Camera stability is checked after lock settling until immediately before release. Restored Edge scrolling can move the camera after measurement; initial camera coordinates are not restored by this pilot.',
        'No equivalence margin, statistical significance, causal engine speedup or attribution of zero CPU to zero execution claimed.'
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-version', type=version_identifier, default='0.8.19')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    if digest != args.expected_sha256:
        raise ValueError('Capture SHA-256 differs')
    report = dict(source=str(args.source), source_sha256=digest, result=analyze(json.loads(raw), args.expected_version))
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(output=str(args.output), completed=True, blocks=len(report['result']['blocks']))))


if __name__ == '__main__':
    main()
