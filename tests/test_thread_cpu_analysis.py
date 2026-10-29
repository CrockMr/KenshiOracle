import pytest
from analyze_thread_cpu import summarize


def capture():
    endpoint = dict(created_at=10, thread_snapshot=dict(collection_seconds=.01))
    return dict(pid=42, initial_ping=dict(plugin_version='0.7.5'), completed=True,
        process_resources=dict(pid=42, before=dict(endpoint), after=dict(endpoint),
            elapsed_seconds=1, user_seconds=1, system_seconds=0,
            thread_cpu=dict(threads=[], accounting_group_cpu_seconds=dict(game_thread=1.1),
                omitted_reasons={}, residual_cpu_seconds=-.1, role_evidence={}, limits=[])),
        thread_attribution_statistics=dict(navmesh_slow_calls_retention_truncated=True))


def test_report_does_not_force_quantized_group_total_to_100_percent():
    report = summarize(capture())
    assert report['groups'][0]['fraction_of_process_cpu'] == 1.1
    assert report['residual_cpu_seconds'] == -.1
    assert report['navigation_context_retention_truncated']


@pytest.mark.parametrize('change', ['pid', 'creation'])
def test_report_rejects_process_identity_disagreement(change):
    data = capture()
    if change == 'pid':
        data['process_resources']['pid'] = 99
    else:
        data['process_resources']['after']['created_at'] = 11
    with pytest.raises(ValueError, match='identity disagreement'):
        summarize(data)
