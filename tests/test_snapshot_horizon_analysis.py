from copy import deepcopy
import pytest
from analyze_snapshot_horizon import analyze, summarize_run


def run():
    scene=dict(battle=dict(members=[dict(name='actor',blood=100,unconscious=False,dead=False,
        health=dict(complete=True,part_count=1,flesh_sum=100,flesh_stun_sum=0))]))
    return dict(speed=1,completed=True,baseline_comparison=dict(matches=True),
        initial=deepcopy(scene),final=deepcopy(scene),
        observations=[dict(scene=dict(**scene,loaded_character_count=50))],
        progress=dict(game_hours=.51,wall_seconds=55),
        process_resources=dict(before=dict(created_at=10),after=dict(created_at=10),
            user_seconds=30,system_seconds=3,elapsed_seconds=55.2,
            thread_cpu=dict(accounting_group_cpu_seconds={'game_thread':20,'other_threads':13.1},
                omitted_reasons={},residual_cpu_seconds=-.1)))


def test_overshoot_and_cpu_interval_kept_distinct():
    result=summarize_run(run(),.5)
    assert result['horizon_overshoot_hours']==pytest.approx(.01)
    assert result['cpu_seconds_per_observed_game_hour']==pytest.approx(33/.51)
    assert result['cpu_enclosing_wall_seconds']==55.2
    assert result['progress']['wall_seconds']==55
    assert result['residual_cpu_seconds']==-.1


@pytest.mark.parametrize('change',['baseline','identity','clock','missing','duplicate','medical','cpu'])
def test_bad_completed_run_is_not_summarized(change):
    row=run()
    if change=='baseline': row['baseline_comparison']['matches']=False
    elif change=='identity': row['process_resources']['after']['created_at']=11
    elif change=='clock': row['progress']['game_hours']=.49
    elif change=='missing': row['final']['battle']['members']=[]
    elif change=='duplicate': row['final']['battle']['members']*=2
    elif change=='medical': row['final']['battle']['members'][0]['blood']=float('nan')
    else: row['process_resources']['user_seconds']=-100
    with pytest.raises(ValueError): summarize_run(row,.5)


def test_rejected_run_does_not_enter_completed_group():
    row=dict(speed=5,excluded='baseline differs',baseline_comparison=dict(matches=False))
    data=dict(pid=1,snapshot='test',target_game_hours=.5,runs=[run(),row])
    result=analyze(data)
    assert result['groups'][0]['completed_runs']==1
    assert result['groups'][1]['completed_runs']==0
    assert result['groups'][1]['cpu_seconds_per_observed_game_hour'] is None
    assert not result['completed'] and not result['restored']


def test_ko_observation_keeps_wall_and_simulation_clocks_separate():
    row=run()
    row['clock_start']={'game_total_hours':404}
    observation=row['observations'][0]
    observation['elapsed']=12
    observation['scene']['game_total_hours']=404.2
    observation['scene']['battle']['members'][0]['unconscious']=True
    event=summarize_run(row,.5)['actors']['actor']['first_unconscious_observation']
    assert event['elapsed_seconds']==12
    assert event['game_hours_since_start']==pytest.approx(.2)
