from copy import deepcopy
import pytest
from analyze_root_battle import analyze, CALIBRATION_SCOPE
from analyze_heavy_battle import analyze as heavy_analysis
from test_heavy_battle_analysis import data as heavy_sample
from test_root_cpu_analysis import sample as cpu_sample


def sample():
    d=heavy_sample();root=cpu_sample()
    d.update(pairs=20,transport='mcp-stdio',expected_function_cpu_enabled=True,
             source_sha256_before='a'*64,source_sha256_after='a'*64,
             initial_ping=deepcopy(root['initial_ping']),function_module=deepcopy(root['function_module']),
             calibration_reference=dict(path='runtime/synthetic-calibration.json',sha256='b'*64,scope=CALIBRATION_SCOPE))
    scenes=[d['initial'],d['final_scene']]+[o['scene'] for o in d['observations']]
    for row in d['windows']:
        scenes += [row['scene_before'],row['scene_after'],row['selection_scene']]+[o['scene'] for o in row['observations']]
        s=row['statistics'];f=deepcopy(root['phases'][1]['statistics']['systems']['profiled_function'])
        f['mean_ms']=f['threads'][0]['mean_ms']=.25
        s['systems'].update(profiled_function=f,ai_profiled_function=None,ai_periodicUpdate=None,physics_backThreadUpdate=None,charsUpdateUT_mean_ms=None)
        s['per_frame']=deepcopy(root['phases'][1]['statistics']['per_frame'])
        for i,r in enumerate(s['per_frame']):r['frame']=s['last_frame']-len(s['per_frame'])+i+1
        row['roles_before']=dict(frame=row['scene_before']['frame'],game_thread=7,service_thread=7)
        row['roles_after']=dict(frame=row['scene_after']['frame'],game_thread=7,service_thread=7)
    for scene in scenes:
        battle=scene['battle'];old=battle['members'];members=[]
        for i in range(40):
            member=deepcopy(old[0] if i==0 else old[1]);member['name']='fight_'+str(i);members.append(member)
        battle.update(members=members,requested_entities=40,spawned_entities=40,matched_loaded=40,under_melee_attack_count=40)
        scene['loaded_character_count']=40
    d['prepared']['members']=[dict(name='fight_'+str(i)) for i in range(40)]
    return d


def test_root_battle_has_forty_actors_and_preserves_quantized_cpu_without_clamping():
    d=sample();saved=deepcopy(d);result=analyze(d);r=result['windows'][0]
    assert d==saved and len(result['actors'])==40 and len(result['windows'])==4
    assert result['actors_with_damage_signal']==['fight_0']
    assert r['root_cpu_counter_total_ms']==31.25 and r['root_cpu_counter_mean_ms_per_retained_frame']==3.90625
    assert r['selected_function']['mean_ms']==.25
    identity=r['selected_function_cpu_identity_matches']['threads'][0]
    assert identity['matched_cpu_identity'] and identity['matches_game_thread_at_bounds'] and identity['matches_renderer_thread_at_bounds']
    assert identity['created_filetime']=='123'


def test_old_heavy_cohort_analyzer_stays_independent_and_input_unmodified():
    d=heavy_sample();original=deepcopy(d);first=heavy_analysis(d)
    with pytest.raises(ValueError):analyze(d)
    assert d==original and heavy_analysis(d)==first


@pytest.mark.parametrize('field,value',[
    ('plugin_version','0.8.10'),('system_hook_count',4),('installed_hook_count',4),('dedicated_system_hook_count',2),
    ('service_hook_count',3),('function_thread_cpu_enabled',False),('function_hook_reuses_service',True),
    ('renderer_update_profiling',True),('main_loop_gpu_sensitive_profiling',True),('havok_character_update_profiling',True),
    ('ogre_render_one_frame_profiling',False),('profiled_function','HavokCharacter::update'),
    ('function_binding_symbol','?renderOneFrame@Root@Ogre@@QEAA_NM@Z'),('function_binding_address','0x10000020'),
    ('function_binding_module_path','E:/Wrong/OgreMain_x64.dll'),('function_binding_source','guessed'),
    ('function_thread_cpu_startup_read_mean_us',0),('function_thread_cpu_startup_read_mean_us',float('nan'))])
def test_binding_mode_and_native_contract_cannot_be_relabelled(field,value):
    d=sample();d['initial_ping'][field]=value
    with pytest.raises(ValueError):analyze(d)


@pytest.mark.parametrize('poison',['marker','transport','pairs','source','missing_source','calibration_hash','calibration_scope','calibration_path','module_hash','module_loaded_path','forwarder','rva','scope','stats_address','partial','cpu_off','identity','game_role','renderer_role','heartbeat_frame'])
def test_capture_provenance_coverage_and_identity_fail_closed(poison):
    d=sample();row=d['windows'][0];f=row['statistics']['systems']['profiled_function']
    if poison=='marker':d['expected_function_cpu_enabled']=False
    elif poison=='transport':d['transport']='direct-tcp'
    elif poison=='pairs':d['pairs']=1
    elif poison=='source':d['source_sha256_after']='c'*64
    elif poison=='missing_source':d.pop('source_sha256_before')
    elif poison=='calibration_hash':d['calibration_reference']['sha256']='invalid'
    elif poison=='calibration_scope':d['calibration_reference']['scope']='precise in-game CPU'
    elif poison=='calibration_path':d['calibration_reference']['path']='../outside.json'
    elif poison=='module_hash':d['function_module']['sha256']='c'*64
    elif poison=='module_loaded_path':d['function_module']['loaded']['path']='E:/Wrong/OgreMain_x64.dll'
    elif poison=='forwarder':d['function_module']['export']['forwarder']='other.Export'
    elif poison=='rva':d['function_module']['export']['rva']=True
    elif poison=='scope':f['scope']='exclusive CPU'
    elif poison=='stats_address':f['binding_address']='0x10000020'
    elif poison=='partial':
        for part in [f,f['threads'][0]]:part['cpu_available_calls']-=1;part['cpu_unavailable_calls']+=1
    elif poison=='cpu_off':f['cpu_enabled']=False
    elif poison=='identity':f['threads'][0]['created_filetime']='456'
    elif poison=='game_role':row['roles_after']['game_thread']=8
    elif poison=='renderer_role':row['roles_before']['service_thread']=8
    else:row['roles_before']['frame']=row['statistics']['first_frame']+1
    with pytest.raises((ValueError,RuntimeError)):analyze(d)
