import json
from copy import deepcopy
import pytest
from command_service import SCOPE,summarize
from analyze_command_service import analyze


def scene(frame=10,count=0):
    thread=dict(available=True,identity_verified=True,sdk_thread_id=7,kernel_thread_id=7,kernel_process_id=99,created_filetime='134376698083790089')
    return dict(frame=frame,paused=True,frame_speed_multiplier=0,game_total_hours=404,free_camera=count>0,scene_camera_control_owned=count>0,
        camera_center=[1,2,3],camera_position=[4,5,6],battle=dict(active=count>0,matched_loaded=count,members=[{} for _ in range(count)]),
        sdk_threads=dict(process_id=99,frame=frame,observed_qpc_ms=90,roles=[dict(role=key,**thread) for key in ('world_ai_non_render','world_navmesh','physics_backthread')]))


def timing(command,frame,clock):
    return dict(schema_version=1,command=command,scope=SCOPE,menu_service=False,identity_verified=True,thread_id=7,
        created_filetime='134376698083790089',frame=frame,queued_qpc_ms=clock,started_qpc_ms=clock+1,finished_qpc_ms=clock+2,queue_wait_ms=1,service_ms=1)


def fixture():
    ping=dict(plugin_version='0.8.11',system_hook_count=3,command_service_timing_enabled=True,_probe_service=timing('ping',5,80))
    data=dict(completed=True,measurement_valid=True,protected_files_unchanged=True,settings_unchanged=True,transport='mcp-stdio',repetitions=12,
        initial_ping=ping,pid=99,phases=[],final_scene=scene(),source_reference=scene())
    defs=[('ping','ping',{}),('scene','get_scene_state',{}),('scene_roles','get_scene_state',dict(thread_details=True)),('statistics_60','get_frame_stats',dict(n=60))]
    for name,count in [('copy_no_battle',0),('mongrel_40_paused',40)]:
        rows=[]
        for index in range(48):
            rep,offset=divmod(index,4);label,cmd,params=defs[(rep+offset)%4]
            result=scene(12+index,count) if cmd=='get_scene_state' else (dict(count=60) if cmd=='get_frame_stats' else deepcopy(ping))
            result['_probe_service']=timing(cmd,12+index,100+index*10)
            rows.append(dict(repetition=rep,label=label,command=cmd,params=params,result=result,client_ms=10,compact_result_bytes=len(json.dumps(result,separators=(',',':')).encode())))
        snapshot=dict(threads=[dict(tid=7,created_filetime='134376698083790089')])
        data['phases'].append(dict(label=name,actor_count=count,before=scene(10,count),after=scene(100,count),requests=rows,
            thread_before=snapshot,thread_after=deepcopy(snapshot),completed=True,summary=json.loads(json.dumps(summarize(rows)))))
    return data


def test_complete_plan_replayed_from_raw_clocks():
    report=analyze(fixture());assert len(report['phases'])==2
    assert report['phases'][1]['summary']['scene']['count']==12


def test_renderer_ping_in_ready_game_is_retained_and_counted():
    data=fixture();phase=data['phases'][0];phase['requests'][0]['result']['_probe_service']['menu_service']=True
    item=phase['requests'][0];item['compact_result_bytes']=len(json.dumps(item['result'],separators=(',',':')).encode())
    phase['summary']=json.loads(json.dumps(summarize(phase['requests'])))
    assert analyze(data)['phases'][0]['summary']['ping']['renderer_service_reads']==1


@pytest.mark.parametrize('mutation',['incomplete','files','order','identity','clock','frame','size','summary','missing','paused','restoration'])
def test_malformed_or_incomplete_capture_not_admitted(mutation):
    data=fixture();phase=data['phases'][0];item=phase['requests'][1]
    if mutation=='incomplete':data['completed']=False
    elif mutation=='files':data['protected_files_unchanged']=False
    elif mutation=='order':item['params']={'thread_details':True}
    elif mutation=='identity':phase['thread_after']['threads']=[]
    elif mutation=='clock':item['result']['_probe_service']['queued_qpc_ms']=0
    elif mutation=='frame':item['result']['_probe_service']['frame']=1000
    elif mutation=='size':item['compact_result_bytes']+=1
    elif mutation=='summary':phase['summary']['scene']['count']=99
    elif mutation=='missing':phase['requests'].pop()
    elif mutation=='paused':phase['after']['game_total_hours']+=1
    elif mutation=='restoration':data['final_scene']['scene_camera_control_owned']=True
    with pytest.raises(ValueError):analyze(data)
