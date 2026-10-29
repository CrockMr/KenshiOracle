"""Summarize one captured CPU interval, preserving nonexclusive role scope."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse
import hashlib
import json
from pathlib import Path


def summarize(data):
    resources = data['process_resources']
    if data['pid'] != resources['pid'] or resources['before']['created_at'] != resources['after']['created_at']:
        raise ValueError('Process identity disagreement in captured CPU interval')
    threads = resources['thread_cpu']
    wall = resources['elapsed_seconds']
    cpu = resources['user_seconds']+resources['system_seconds']
    if wall <= 0 or cpu < 0:
        raise ValueError('Invalid captured CPU interval')
    groups = [dict(group=name, cpu_seconds=seconds, logical_cpu_equivalents=seconds/wall,
                   fraction_of_process_cpu=seconds/cpu if cpu else None)
              for name, seconds in threads['accounting_group_cpu_seconds'].items()]
    return dict(pid=data['pid'], plugin_version=data['initial_ping']['plugin_version'],
        transport=data.get('transport'), completed=data.get('completed', False),
        elapsed_seconds=wall, process_cpu_seconds=cpu, process_logical_cpu_equivalents=cpu/wall,
        groups=groups, matched_threads=len(threads['threads']), omitted_reasons=threads['omitted_reasons'],
        residual_cpu_seconds=threads['residual_cpu_seconds'], top_threads=threads['threads'][:12],
        endpoint_collection_ms={key: resources[key]['thread_snapshot']['collection_seconds']*1000
                                for key in ('before','after')},
        role_evidence=threads['role_evidence'],
        navigation_context_retention_truncated=data['thread_attribution_statistics']['navmesh_slow_calls_retention_truncated'],
        limits=threads['limits']+[
            'GameWorld and Renderer service share a thread here; whole-thread CPU is not exclusive simulation CPU.',
            'Only retained navigation calls identify navigation threads; other workers can remain unclassified.',
            'This interval does not establish scaling, optimization gain, or causal comparison to other cohorts.'])


def main(source, output):
    raw = source.read_bytes()
    report = dict(source=str(source), source_sha256=hashlib.sha256(raw).hexdigest(), result=summarize(json.loads(raw)))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), result={key:value for key,value in report['result'].items()
                                                    if key not in ('top_threads','limits')})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('runtime/thread-cpu-analysis.json'))
    args = parser.parse_args()
    main(args.source, args.output)
