from copy import deepcopy
import json
import pytest
from analyze_chars_split import analyze
from chars_diagnostics import SCOPE
from benchmark import simulation_progress
from environment_diagnostics import summarize
from thread_resources import thread_deltas


def scene(frame=1,paused=True,hours=404):
    return dict(frame=frame,paused=paused,frame_speed_multiplier=0 if paused else 5,game_total_hours=hours,observed_qpc_ms=frame*1000,
        free_camera=False,scene_camera_control_owned=False,battle=dict(active=False),loaded_character_count=1,camera_center=[1,2,3],camera_position=[4,5,6])
def environment(value):
    env=dict(scene_before=value,scene_after=deepcopy(value),limit=500,inventory=dict(total_update_list=1,characters=[dict(name='Synthetic',faction='Synthetic',position=[1,2,3])]))
    env['summary']=summarize(env);return env
def totals(calls,call,post):
    return dict(calls_total=calls,call_wall_total_ms=call,post_call_to_lock_total_ms=post,legacy_total_ms=call+post,
        call_wall_mean_ms=call/2,post_call_to_lock_mean_ms=post/2,legacy_mean_ms=(call+post)/2,max_call_wall_ms=1 if calls else 0,max_post_call_to_lock_ms=.5 if calls else 0,max_legacy_ms=1.5 if calls else 0)
def statistics(first):
    root=totals(2,2,1);root.update(function='GameWorld::charsUpdate',scope=SCOPE,cpu_enabled=False,cpu_user_total_ms=None,cpu_kernel_total_ms=None,
        thread_identity_mode='tls_creation_once',thread_capacity=8,threads_truncated=False,threads=[dict(totals(2,2,1),thread_id=7,created_filetime='123',identity_verified=True)],unlisted=totals(0,0,0))
    return dict(count=2,first_frame=first,last_frame=first+1,mean_ms=10,p99_ms=11,series_truncated=False,systems=dict(charsUpdate_split=root,charsUpdate_mean_ms=1.5),
        per_frame=[dict(frame=f,charsUpdate_calls=1,charsUpdate_call_wall_ms=1,charsUpdate_ms=1.5) for f in (first,first+1)])
def resources():
    before=dict(created_at=10,monotonic_seconds=0,user_seconds=0,system_seconds=0,thread_snapshot=dict(threads=[dict(tid=7,created_filetime='123',user_100ns=0,kernel_100ns=0,observed_monotonic_seconds=0)]))
    after=dict(created_at=10,monotonic_seconds=12,user_seconds=1,system_seconds=0,thread_snapshot=dict(threads=[dict(tid=7,created_filetime='123',user_100ns=10000000,kernel_100ns=0,observed_monotonic_seconds=12)]))
    return dict(pid=99,executable='e:/synthetic/game.exe',before=before,after=after,elapsed_seconds=12,user_seconds=1,system_seconds=0,logical_cpu_equivalents=1/12,thread_cpu=thread_deltas(before['thread_snapshot'],after['thread_snapshot'],12,1))
def sdk(value):
    value=deepcopy(value);value['sdk_threads']=dict(process_id=99,frame=value['frame'],observed_qpc_ms=1,roles=[dict(role=k,available=True,identity_verified=True,sdk_thread_id=7,kernel_thread_id=7,kernel_process_id=99,created_filetime='123') for k in ('world_ai_non_render','world_navmesh','physics_backthread')]);return value
def sample():
    data=dict(completed=True,protected_files_unchanged=True,settings_unchanged=True,pid=99,created_at=10,executable='E:/synthetic/game.exe',transport='mcp-stdio',active_speed=5,seconds_requested=12,
        initial_ping=dict(plugin_version='0.8.15',system_hook_count=3,chars_update_split_profiling=True,chars_update_bucket_bytes=696,telemetry_sample_bytes=696,chars_update_history_bytes=2523600),
        sdk_roles_before=sdk(scene()),sdk_roles_after=sdk(scene(50,hours=404.5)),camera_reference=scene(),source_reference=scene(),final_scene=scene(100),phases=[])
    for index,(label,paused) in enumerate([('paused_before',True),('running_x5',False),('paused_after',True)]):
        first=10+index*10;hours=404.5 if index==2 else 404;a=scene(first,paused,hours);b=scene(first+4,paused,404.5 if index else 404);stats=statistics(first+1)
        plan=dict(requested_maximum=2,selected_count=2,attempts=[dict(n=2,ok=True,compact_bytes=len(json.dumps(stats,separators=(',',':')).encode()))])
        data['phases'].append(dict(label=label,expected_paused=paused,completed=True,scene_before=a,scene_after=b,selection_scene=scene(first+3,paused,hours),requested_frames=2,
            observations=[dict(elapsed=12,scene=b)],simulation_progress=simulation_progress(a,b),environment_before=environment(a),environment_after=environment(b),statistics=stats,
            statistics_collection=plan,process_resources=resources(),roles_before=dict(game_thread=7,service_thread=7),roles_after=dict(game_thread=7,service_thread=7)))
    return data


def test_replay_separates_wall_intervals_and_whole_thread_cpu():
    result=analyze(sample());row=result['phases'][1]
    assert row['post_fraction_of_legacy_wall']==1/3
    assert row['thread_identity_matches'][0]['whole_thread_cpu_seconds']==1
    assert row['thread_identity_matches'][0]['matches_game_thread_at_bounds']


@pytest.mark.parametrize('mutation',['incomplete','order','clock','stats','bytes','cpu','cached_cpu','identity','environment','restore','version','frame','short','guard'])
def test_corrupt_or_unrestored_campaign_rejected(mutation):
    data=sample();row=data['phases'][1]
    if mutation=='incomplete':data['completed']=False
    elif mutation=='order':data['phases'].reverse()
    elif mutation=='clock':row['simulation_progress']['game_hours']=99
    elif mutation=='stats':row['statistics']['systems']['charsUpdate_split']['call_wall_total_ms']+=1
    elif mutation=='bytes':row['statistics_collection']['attempts'][0]['compact_bytes']+=1
    elif mutation=='cpu':row['process_resources']['user_seconds']=2
    elif mutation=='cached_cpu':row['process_resources']['thread_cpu']['residual_cpu_seconds']=99
    elif mutation=='identity':row['process_resources']['after']['created_at']=20
    elif mutation=='environment':row['environment_before']['summary']['complete']=False
    elif mutation=='restore':data['final_scene']['paused']=False
    elif mutation=='version':data['initial_ping']['system_hook_count']=4
    elif mutation=='frame':row['statistics']['first_frame']=0
    elif mutation=='short':row['observations'][0]['elapsed']=1
    elif mutation=='guard':data['restoration_error']='failed'
    with pytest.raises((ValueError,RuntimeError)):analyze(data)
