import json
from copy import deepcopy
import pytest
from command_service import SCOPE,summarize
from analyze_json_copy_probe import analyze,compare


def scene(frame=10):return dict(frame=frame,paused=True,frame_speed_multiplier=0,game_total_hours=404,free_camera=False,scene_camera_control_owned=False,battle=dict(active=False),camera_center=[1,2,3],camera_position=[4,5,6])


def sample(version='0.8.12'):
    definitions=[('ping','ping',{}),('scene','get_scene_state',{}),('statistics_60','get_frame_stats',dict(n=60))];rows=[]
    for index in range(36):
        rep,offset=divmod(index,3);label,cmd,params=definitions[(rep+offset)%3];frame=100+index
        result=scene(frame) if cmd=='get_scene_state' else (dict(count=60,first_frame=frame-60,last_frame=frame-1) if cmd=='get_frame_stats' else {})
        result['_probe_service']=dict(schema_version=1,command=cmd,scope=SCOPE,menu_service=False,identity_verified=True,thread_id=7,created_filetime='123456789012345678',frame=frame,queued_qpc_ms=index*10,started_qpc_ms=index*10+1,finished_qpc_ms=index*10+2,queue_wait_ms=1,service_ms=1)
        rows.append(dict(repetition=rep,label=label,command=cmd,params=params,result=result,client_ms=10,compact_result_bytes=len(json.dumps(result,separators=(',',':')).encode())))
    threads=dict(threads=[dict(tid=7,created_filetime='123456789012345678')])
    return dict(completed=True,transport='mcp-stdio',version=version,initial_ping=dict(plugin_version=version,system_hook_count=3,command_service_timing_enabled=True),
        source_reference=scene(),final_scene=scene(200),installed_dll_sha256='a'*64,requests=rows,thread_before=threads,thread_after=deepcopy(threads),summary=json.loads(json.dumps(summarize(rows))),pid=99,created_at=123)


def test_read_only_plan_and_descriptive_difference():
    old=sample();new=sample('0.8.13');assert analyze(old)['summary']['statistics_60']['count']==12
    new['pid']=100;new['created_at']=124
    assert compare(old,new)['after_minus_before_mean_ms']['scene']['service_ms']==0


@pytest.mark.parametrize('mutation',['incomplete','missing','order','identity','frame','stats','size','clock','summary','pause','dll','camera'])
def test_invalid_probe_not_admitted(mutation):
    data=sample();item=data['requests'][2]
    if mutation=='incomplete':data['completed']=False
    elif mutation=='missing':data['requests'].pop()
    elif mutation=='order':item['params']={}
    elif mutation=='identity':data['thread_after']['threads']=[]
    elif mutation=='frame':item['result']['_probe_service']['frame']=999
    elif mutation=='stats':item['result']['first_frame']=0
    elif mutation=='size':item['compact_result_bytes']+=1
    elif mutation=='clock':data['final_scene']['game_total_hours']+=1
    elif mutation=='summary':data['summary']['scene']['count']=99
    elif mutation=='pause':data['final_scene']['paused']=False
    elif mutation=='dll':data['installed_dll_sha256']='x'*64
    elif mutation=='camera':data['final_scene']['camera_center'][0]+=20
    with pytest.raises(ValueError):analyze(data)
