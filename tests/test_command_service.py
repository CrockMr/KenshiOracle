from copy import deepcopy
import pytest
from command_service import SCOPE,summarize,validate


def sample():
    return dict(frame=12,_probe_service=dict(schema_version=1,command='ping',scope=SCOPE,menu_service=False,
        identity_verified=True,created_filetime='134376698083790089',thread_id=7,frame=12,
        queued_qpc_ms=100,started_qpc_ms=105,finished_qpc_ms=107,queue_wait_ms=5,service_ms=2))


def test_exact_identity_and_separate_clocks():
    value=sample();assert validate(value,'ping')['created_filetime']=='134376698083790089'
    summary=summarize([dict(label='ping',command='ping',result=value,client_ms=50)])
    assert summary['ping']['service_ms']['mean']==2
    assert summary['ping']['queue_wait_ms']['mean']==5 and summary['ping']['client_ms']['mean']==50


@pytest.mark.parametrize('key,value',[('schema_version',True),('schema_version',2),('thread_id',True),('thread_id',0),
    ('frame',-1),('created_filetime',134376698083790089),('created_filetime','0'),('created_filetime','١٢'),
    ('identity_verified',False),('queue_wait_ms',0),('service_ms',float('nan')),('service_ms',float('inf')),
    ('finished_qpc_ms',104),('started_qpc_ms',99),('menu_service',0),('scope','CPU'),('command','pause')])
def test_invalid_contract_rejected(key,value):
    item=sample();item['_probe_service'][key]=value
    with pytest.raises(ValueError):validate(item,'ping')


def test_absent_identity_can_be_reported_unavailable_but_not_joined():
    item=sample();item['_probe_service'].update(identity_verified=False,created_filetime=None)
    with pytest.raises(ValueError):validate(item,'ping')
    assert validate(item,'ping',require_identity=False)['created_filetime'] is None


def test_frame_join_must_match_and_missing_metadata_not_zero():
    item=sample();item['frame']=13
    with pytest.raises(ValueError):validate(item,'ping')
    with pytest.raises(KeyError):validate({},'ping')


def test_loaded_game_summary_allows_renderer_ping_but_rejects_other_commands():
    item=sample();item['_probe_service']['menu_service']=True
    assert summarize([dict(label='ping',command='ping',result=item,client_ms=50)])['ping']['renderer_service_reads']==1
    item['_probe_service']['command']='get_scene_state'
    with pytest.raises(ValueError):summarize([dict(label='scene',command='get_scene_state',result=item,client_ms=50)])
    with pytest.raises(ValueError):summarize([])
    item=sample()
    with pytest.raises(ValueError):summarize([dict(label='ping',command='ping',result=item,client_ms=-1)])
