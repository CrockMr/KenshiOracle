from copy import deepcopy
import pytest
from analyze_environment import analyze
from environment_diagnostics import summarize
from test_environment_diagnostics import capture


def data():
    c=capture();c.update(elapsed=.1,summary=summarize(c))
    return dict(pid=1,runs=[dict(captures=[c,deepcopy(c)])],
        identity_interval=dict(pid=1,before=dict(created_at=10),after=dict(created_at=10)))


def test_recomputes_and_refuses_stale_cached_inventory():
    d=data();d['runs'][0]['captures'][0]['inventory']['characters'][0]['name']='Changed'
    with pytest.raises(ValueError,match='Cached'): analyze(d)


@pytest.mark.parametrize('change',['pid','created'])
def test_refuses_disagreeing_process_identity(change):
    d=data()
    if change=='pid': d['identity_interval']['pid']=2
    else: d['identity_interval']['after']['created_at']=11
    with pytest.raises(ValueError,match='identity'): analyze(d)


def test_partial_capture_is_not_a_completed_campaign():
    d=data();d['runs'][0]['captures'].pop()
    result=analyze(d)
    assert not result['completed'] and not result['restored']
    assert result['runs'][0]['within_load'] is None and result['between_loads'] is None


def test_flat_heavy_capture_does_not_invent_elapsed_time_or_admit_partial_middle():
    full=capture();full['summary']=summarize(full)
    partial=deepcopy(full);partial['inventory']['characters'].pop();partial['summary']=summarize(partial)
    result=analyze(dict(pid=1,captures=[full,partial,deepcopy(full)]))
    assert [r['accepted'] for r in result['offline_admission_replay']]==[True,False,True]
    assert result['runs'][0]['captures'][0]['elapsed'] is None
    assert result['runs'][0]['within_load']['exact_positions_equal']
