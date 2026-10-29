from copy import deepcopy
import pytest
from analyze_heavy_battle import analyze,validate_cohort
from benchmark import simulation_progress
from thread_resources import thread_deltas,assign_roles
from test_sdk_thread_roles import scene as roles
from test_function_diagnostics import stats
from test_environment_diagnostics import capture


def scene(frame=10,paused=False,hours=404,qpc=1000):
    members=[dict(name='fight_'+str(i),blood=100,is_player=False,under_melee_attack=True,
        unconscious=False,dead=False,health=dict(complete=True,part_count=7,sampled_count=7,
            flesh_sum=700,flesh_stun_sum=0,max_health_sum=700)) for i in range(2)]
    return dict(frame=frame,observed_qpc_ms=qpc,game_total_hours=hours,paused=paused,
        frame_speed_multiplier=0 if paused else 5,free_camera=True,scene_camera_control_owned=True,edge_scrolling=False,
        camera_position=[0,0,0],camera_center=[0,1,0],loaded_character_count=2,
        battle=dict(active=True,prefix='fight_',requested_entities=2,spawned_entities=2,matched_loaded=2,
            members=members,under_melee_attack_count=2,unconscious_count=0,dead_count=0))


def data():
    d=dict(pid=1,created_at=10,executable='game.exe',speed=5,pairs=1,completed=True,protected_files_unchanged=True,
        settings_unchanged=True,initial=scene(paused=True),prepared=dict(prepared=True,mutual_enemies_verified=True,
            members=[dict(name='fight_0'),dict(name='fight_1')]),initial_ping=dict(profiled_function='GameWorld::charsUpdateUT'),
        windows=[],observations=[],environment_before=capture(),environment_after=capture(),
        source_reference=dict(game_total_hours=404),restored=dict(ok=True))
    first,last=roles(),roles();first['frame']=first['sdk_threads']['frame']=1;last['frame']=last['sdk_threads']['frame']=500
    d.update(sdk_roles_before=first,sdk_roles_after=last)
    for i,seconds in enumerate((5,5,10,10)):
        before=scene(frame=20+i*20,hours=404+i*.1,qpc=10000+i*20000)
        after=scene(frame=30+i*20,hours=404+(i+1)*.1,qpc=before['observed_qpc_ms']+seconds*1000)
        after['battle']['members'][0]['blood']=99
        selected=deepcopy(after);selected['frame']-=1
        statistics=stats();statistics.update(first_frame=after['frame']-7,last_frame=after['frame'],count=8,mean_ms=10,p99_ms=20)
        statistics['systems']['navmesh_findPath_calls_total']=0
        a=dict(created_at=10,monotonic_seconds=i*20,user_seconds=1,system_seconds=1,
            thread_snapshot=dict(threads=[dict(tid=7,created_filetime='123',user_100ns=10000000,kernel_100ns=10000000,observed_monotonic_seconds=i*20)]))
        b=dict(created_at=10,monotonic_seconds=i*20+seconds,user_seconds=2,system_seconds=1.5,
            thread_snapshot=dict(threads=[dict(tid=7,created_filetime='123',user_100ns=20000000,kernel_100ns=15000000,observed_monotonic_seconds=i*20+seconds)]))
        cpu=dict(pid=1,executable='game.exe',before=a,after=b,elapsed_seconds=seconds,user_seconds=1,system_seconds=.5,
            thread_cpu=thread_deltas(a['thread_snapshot'],b['thread_snapshot'],seconds,1.5))
        assign_roles(cpu['thread_cpu'],{7},{7},set())
        obs=dict(elapsed=sum((5,5,10,10)[:i+1]),scene=deepcopy(after));d['observations'].append(obs)
        d['windows'].append(dict(label='window_'+str(i+1),requested_seconds=seconds,completed=True,
            scene_before=before,scene_after=after,selection_scene=selected,requested_frames=8,statistics=statistics,
            observations=[obs],process_resources=cpu,simulation_progress=simulation_progress(before,after)))
    final=scene(paused=True);final.update(free_camera=False,scene_camera_control_owned=False);final['battle']['active']=False
    d['final_scene']=final
    return d


def test_heavy_battle_replays_windows_damage_and_external_targets():
    d=data();d['observations'][0]['scene']['battle']['members'][0]['attack_target']=dict(resolved=True,name='guard')
    result=analyze(d)
    assert len(result['windows'])==4 and result['combat_effective_observed']
    assert result['actors_with_damage_signal']==['fight_0']
    assert result['outside_cohort_target_observations']==1
    assert result['windows'][0]['sdk_role_cpu_join']['unique_matched_threads']==1


@pytest.mark.parametrize('change',['missing','duplicate','health','player','speed','camera','tracking','edge','blood'])
def test_incomplete_cohort_does_not_become_death_or_valid_measurement(change):
    baseline=scene(paused=True);s=scene()
    if change=='missing':s['battle']['members'].pop()
    elif change=='duplicate':s['battle']['members'][1]['name']='fight_0'
    elif change=='health':s['battle']['members'][0]['health']['complete']=False
    elif change=='player':s['battle']['members'][0]['is_player']=True
    elif change=='speed':s['frame_speed_multiplier']=1
    elif change=='camera':s['camera_center']=[100,0,0]
    elif change=='tracking':s['battle']['matched_loaded']=1
    elif change=='edge':s['edge_scrolling']=True
    else:s['battle']['members'][0]['blood']=None
    with pytest.raises((ValueError,RuntimeError)):validate_cohort(baseline,s)


@pytest.mark.parametrize('change',['counter','window','frames','lifetime','function','plan','restoration','speed'])
def test_poisoned_benchmark_not_reported_as_complete(change):
    d=data();w=d['windows'][0]
    if change=='counter':w['process_resources']['thread_cpu']['threads'][0]['cpu_seconds']+=1
    elif change=='window':w['statistics']['last_frame']+=1
    elif change=='frames':w['requested_frames']-=1
    elif change=='lifetime':w['process_resources']['after']['created_at']=11
    elif change=='function':d['initial_ping']['profiled_function']='HavokCharacter::update'
    elif change=='plan':d['windows'].pop()
    elif change=='restoration':d['final_scene']['game_total_hours']=405
    else:d['speed']=True
    with pytest.raises((ValueError,RuntimeError)):analyze(d)


def test_no_damage_does_not_fabricate_combat_effectiveness():
    d=data()
    for o in d['observations']:o['scene']['battle']['members'][0]['blood']=100
    assert not analyze(d)['combat_effective_observed']
