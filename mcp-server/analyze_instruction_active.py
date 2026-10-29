"""Replay retained PSS observations without opening the game or changing state."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from analyze_pause_cpu import validate_phase_state
from benchmark import simulation_progress
from instruction_diagnostics import summarize
from thread_resources import thread_deltas


def analyze(data):
    if data.get('completed') is not True or not data.get('capture_valid') or any(data.get(k) for k in ('error','restoration_error','camera_release_error')):
        raise ValueError('Requires completed capture and restoration')
    if data.get('protected_files_unchanged') is not True or data.get('settings_unchanged') is not True:
        raise ValueError('Protected files/settings controller attestation missing')
    identities = [(r['tid'], r['created_filetime']) for r in data['selected_lifetimes']]
    samples = data['samples']; observations = data['observations']
    if data['requested_count'] != len(samples) or len(observations) != len(samples):
        raise ValueError('Observation count differs')
    result = summarize(samples, data['pid'], data['executable'], data['process_created_filetime'], identities)
    if result != data['summary']: raise ValueError('Cached address counts or durations disagree')
    before, after = data['scene_before'], data['scene_after']
    schedule = data.get('capture_schedule', 'scene_rpc_then_pss')
    if schedule not in ('scene_rpc_then_pss', 'scene_then_jitter_then_pss'):
        raise ValueError('Unknown capture schedule')
    gaps = []
    previous_frame, previous_qpc = before['frame'], before['observed_qpc_ms']
    for index, row in enumerate(observations):
        if (row['index'] != index or not previous_frame <= row['scene']['frame'] <= after['frame'] or
                not previous_qpc < row['scene']['observed_qpc_ms'] <= after['observed_qpc_ms']):
            raise ValueError('Observation scene order/bounds disagree')
        previous_frame, previous_qpc = row['scene']['frame'], row['scene']['observed_qpc_ms']
        cost = row['caller_seconds']
        if not isinstance(cost, (int,float)) or isinstance(cost, bool) or not math.isfinite(cost) or not 0 <= cost <= data['capture_budget_seconds_per_call']:
            raise ValueError('Caller duration exceeds budget or is invalid')
        if cost < samples[index]['elapsed_seconds']:
            raise ValueError('Caller duration shorter than helper duration')
        if schedule == 'scene_then_jitter_then_pss':
            gap = samples[index]['started_at']-row['scene_observed_at']
            if (not .8 <= row['jitter_seconds'] <= 1.2 or not math.isfinite(gap) or gap < .75 or
                    not math.isclose(gap, row['capture_delay_after_scene_seconds'], rel_tol=0, abs_tol=1e-9)):
                raise ValueError('Declared capture/RPC separation disagrees')
            gaps.append(gap)
    for scene in [before, after] + [x['scene'] for x in observations]:
        validate_phase_state(before, scene, False)
        if not scene['scene_camera_control_owned']: raise ValueError('Camera control not owned during acquisition')
    progress = simulation_progress(before, after)
    if progress != data['simulation_progress'] or progress['game_hours'] <= 0:
        raise ValueError('Simulation progression disagrees')
    restored, final = data['restored'], data['final_scene']
    reference_hours = data['source_reference']['game_total_hours']
    if any(not s['paused'] or s['frame_speed_multiplier'] != 0 or s['game_total_hours'] != reference_hours for s in (restored, final)):
        raise ValueError('Restoration pause/clock disagrees')
    if final['scene_camera_control_owned'] or final['free_camera'] or final['battle']['active']:
        raise ValueError('Final camera/battle state not restored')
    resources = data['process_resources']; a, b = resources['before'], resources['after']
    if resources['pid'] != data['pid'] or a['created_at'] != b['created_at'] or a['created_at'] != data['created_at']:
        raise ValueError('CPU process identity differs')
    if Path(resources['executable']).resolve() != Path(data['executable']).resolve():
        raise ValueError('CPU executable differs')
    elapsed = b['monotonic_seconds']-a['monotonic_seconds']
    user, kernel = b['user_seconds']-a['user_seconds'], b['system_seconds']-a['system_seconds']
    if any(not math.isfinite(v) for v in (elapsed,user,kernel)) or elapsed <= 0 or user < 0 or kernel < 0:
        raise ValueError('CPU counters invalid')
    if (elapsed, user, kernel) != (resources['elapsed_seconds'], resources['user_seconds'], resources['system_seconds']):
        raise ValueError('Cached CPU deltas disagree')
    threads = thread_deltas(a['thread_snapshot'], b['thread_snapshot'], elapsed, user+kernel)
    if threads != resources['thread_cpu']: raise ValueError('Cached CPU thread deltas disagree')
    rows = {(r['tid'], r['created_filetime']):r for r in threads['threads']}
    for row, identity in zip(result['threads'], identities):
        row['whole_thread_cpu'] = rows.get(identity)
    result.update(pid=data['pid'], process_created_filetime=data['process_created_filetime'],
        capture_schedule=schedule, capture_delay_after_scene_min=min(gaps) if gaps else None,
        capture_delay_after_scene_max=max(gaps) if gaps else None,
        process_cpu_seconds=user+kernel, cpu_elapsed_seconds=elapsed,
        logical_cpu_equivalents=(user+kernel)/elapsed,
        residual_cpu_seconds=threads['residual_cpu_seconds'], omitted_reasons=threads['omitted_reasons'],
        caller_seconds_sum=sum(x['caller_seconds'] for x in observations),
        caller_seconds_max=max(x['caller_seconds'] for x in observations), simulation_progress=progress,
        restored_game_hours=reference_hours, protected_files_controller_attested=True,
        limits=['Capture/helper duration is not an exact target-suspension duration.',
                'Address counts are sparse wall-time observations, not CPU percentages or exclusive function costs.',
                'Filesystem preservation is a retained controller attestation; the final audit rechecks actual files separately.',
                'Module/RVA observations do not establish a source function or an SDK binding.'])
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('source', type=Path)
    parser.add_argument('--expected-sha256', required=True); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); raw = args.source.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
    if sha != args.expected_sha256: raise ValueError('Controller SHA-256 differs')
    report = dict(source=str(args.source), source_sha256=sha, result=analyze(json.loads(raw)))
    with args.output.open('x', encoding='utf-8') as stream: stream.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output), observations=report['result']['observations'], verified=True)))


if __name__ == '__main__': main()
