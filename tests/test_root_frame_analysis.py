import json
import pytest
from analyze_root_frame import analyze,NAME,OGRE_SHA256
from function_diagnostics import ROOT_FRAME_SCOPE,ROOT_FRAME_EXPORT
from test_renderer_analysis import sample as renderer_sample

def sample():
    d=renderer_sample();p=d['initial_ping'];path='E:/Synthetic/OgreMain_x64.dll'
    p.update(plugin_version='0.8.18',profiled_function=NAME,function_hook_reuses_service=False,renderer_update_profiling=False,ogre_render_one_frame_profiling=True,
        dedicated_system_hook_count=3,installed_hook_count=5,function_binding_source='loaded_module_export',function_binding_symbol=ROOT_FRAME_EXPORT,
        function_binding_module_path=path,function_binding_address='0x10000010')
    d['function_module']=dict(path=path,sha256=OGRE_SHA256,bytes=10207744,loaded=dict(path=path,base='0x10000000',size=10260480),export=dict(name=ROOT_FRAME_EXPORT,rva=16,forwarder=None))
    for row in d['phases']:
        f=row['statistics']['systems']['profiled_function'];f.update(function=NAME,hook_source='loaded_ogre_export',leading_service_excluded=False,scope=ROOT_FRAME_SCOPE,
            binding_module='OgreMain_x64.dll',binding_symbol=ROOT_FRAME_EXPORT,binding_module_path=path,binding_address='0x10000010')
        row['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(row['statistics'],separators=(',',':')).encode())
    return d

def test_loaded_named_root_export_matches_native_binding_and_cpu_identity():
    r=analyze(sample())['phases'][1]
    assert r['selected_function']['function']==NAME and r['selected_function_cpu_identity_matches']['threads'][0]['matched_cpu_identity']
    assert r['selected_function']['leading_service_excluded'] is False

@pytest.mark.parametrize('field,value',[('function_hook_reuses_service',True),('dedicated_system_hook_count',2),('installed_hook_count',4),('renderer_update_profiling',True),
    ('main_loop_gpu_sensitive_profiling',True),('ogre_render_one_frame_profiling',False),('havok_character_update_profiling',True),('function_binding_symbol','?renderOneFrame@Root@Ogre@@QEAA_NM@Z'),
    ('function_binding_address','0x10000020'),('function_binding_module_path','E:/other/OgreMain_x64.dll')])
def test_root_counts_overload_and_loaded_module_cannot_be_mislabelled(field,value):
    d=sample();d['initial_ping'][field]=value
    with pytest.raises(ValueError):analyze(d)

@pytest.mark.parametrize('poison',['hash','loaded_path','forwarder','entry','scope','service_excluded','stats_address'])
def test_root_source_and_service_scope_rechecked_from_raw_data(poison):
    d=sample();m=d['function_module'];s=d['phases'][0]['statistics'];f=s['systems']['profiled_function']
    if poison=='hash':m['sha256']='0'*64
    elif poison=='loaded_path':m['loaded']['path']='E:/other/OgreMain_x64.dll'
    elif poison=='forwarder':m['export']['forwarder']='other.dll.Export'
    elif poison=='entry':m['export']['rva']=True
    elif poison=='scope':f['scope']='GPU time'
    elif poison=='service_excluded':f['leading_service_excluded']=True
    else:f['binding_address']='0x10000020'
    d['phases'][0]['statistics_collection']['attempts'][-1]['compact_bytes']=len(json.dumps(s,separators=(',',':')).encode())
    with pytest.raises(ValueError):analyze(d)
