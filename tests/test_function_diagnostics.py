from copy import deepcopy
import pytest
from function_diagnostics import validate,function_name,match_cpu
from function_diagnostics import MAIN_LOOP_SCOPE
from test_ai_diagnostics import selected_stats,stats as legacy_stats


def stats():
    s=selected_stats();p=s['systems'].pop('ai_profiled_function')
    p.update(function='GameWorld::charsUpdateUT',thread_identity_mode='tls_creation_once')
    s['systems'].update(profiled_function=p,ai_profiled_function=None,charsUpdateUT_mean_ms=p['mean_ms'])
    s['per_frame']=[dict(function_ms=2,function_calls=1,function_nested_entries_skipped=0,
        ai_function_ms=None,ai_function_calls=None,ai_function_nested_entries_skipped=None,charsUpdateUT_ms=2)]
    return s


def test_world_function_has_truthful_identity_without_ai_aliases():
    s=stats();assert function_name(s)=='GameWorld::charsUpdateUT' and validate(s)['calls_total']==6
    assert function_name(legacy_stats())=='AI::periodicUpdate'
    assert validate(dict(systems={})) is None


def main_loop_stats():
    s=stats();p=s['systems']['profiled_function'];p.update(function='GameWorld::mainLoop_GPUSensitiveStuff',scope=MAIN_LOOP_SCOPE,hook_source='existing_main_service_hook',leading_service_excluded=True)
    s['systems']['charsUpdateUT_mean_ms']=None;s['per_frame'][0]['charsUpdateUT_ms']=None;return s


def test_reused_main_loop_source_and_leading_service_scope_explicit():
    s=main_loop_stats();assert function_name(s)=='GameWorld::mainLoop_GPUSensitiveStuff'
    assert validate(s)['calls_total']==6


@pytest.mark.parametrize('field,value',[('hook_source','dedicated_system_hook'),('hook_source',None),('leading_service_excluded',False),('leading_service_excluded',1),('scope','exclusive CPU')])
def test_main_loop_cannot_hide_hook_reuse_or_scope(field,value):
    s=main_loop_stats();s['systems']['profiled_function'][field]=value
    with pytest.raises(ValueError):validate(s)


@pytest.mark.parametrize('change',['ai','periodic','physics','scalar','bool_scalar','unknown','nested','scope','identity','ai_series','world_series','missing_series'])
def test_mislabelled_or_coexisting_function_is_rejected(change):
    s=stats();p=s['systems']['profiled_function']
    if change in ('ai','periodic','physics'):
        s['systems'][{'ai':'ai_profiled_function','periodic':'ai_periodicUpdate','physics':'physics_backThreadUpdate'}[change]]=deepcopy(p)
    elif change=='scalar':s['systems']['charsUpdateUT_mean_ms']+=1
    elif change=='bool_scalar':s['systems']['charsUpdateUT_mean_ms']=True
    elif change=='unknown':p['function']='GameWorld::guessed'
    elif change=='nested':p['nested_entries_skipped_total']=-1
    elif change=='scope':p['scope']=''
    elif change=='identity':p['thread_identity_mode']='tid_only'
    elif change=='ai_series':s['per_frame'][0]['ai_function_ms']=2
    elif change=='world_series':s['per_frame'][0]['charsUpdateUT_ms']=3
    else:s['per_frame'][0].pop('function_calls')
    with pytest.raises(ValueError):validate(s)


def test_ai_alias_can_be_retained_but_must_match_exactly():
    s=selected_stats();p=s['systems']['ai_profiled_function'];p['thread_identity_mode']='tls_creation_once'
    s['systems']['profiled_function']=deepcopy(p)
    assert validate(s)==p
    s['systems']['ai_profiled_function']['scope']='different'
    with pytest.raises(ValueError):validate(s)
    s['systems']['profiled_function']=None
    with pytest.raises(ValueError):validate(s)


def test_cpu_disabled_world_function_keeps_exact_os_identity_join():
    s=stats();p=s['systems']['profiled_function'];p['cpu_enabled']=False
    for row in [p,p['unlisted']]+p['threads']:
        row.update(cpu_available_calls=0,cpu_unavailable_calls=row['calls_total'],cpu_user_total_ms=None,cpu_kernel_total_ms=None)
    cpu=dict(elapsed_seconds=2,before=dict(created_at=10),after=dict(created_at=10),
        thread_cpu=dict(threads=[dict(tid=7,created_filetime='100',cpu_seconds=.5),dict(tid=8,created_filetime='999',cpu_seconds=1)]))
    rows=match_cpu(validate(s),cpu)['threads']
    assert rows[0]['matched_cpu_identity'] and not rows[1]['matched_cpu_identity']


def zone_stats():
    s=stats()
    s['systems']['profiled_function']['function']='ZoneManager::updateRendertimeThread'
    s['systems']['charsUpdateUT_mean_ms']=None
    s['per_frame'][0]['charsUpdateUT_ms']=None
    return s


@pytest.mark.parametrize('name',['ZoneManager::updateRendertimeThread','MedicalSystem::periodicUpdate','HavokCharacter::update'])
def test_non_ai_function_has_no_world_or_ai_alias(name):
    s=zone_stats()
    s['systems']['profiled_function']['function']=name
    assert function_name(s)==name
    assert validate(s)['calls_total']==6


@pytest.mark.parametrize('poison',['world_scalar','world_series','ai','physics','guessed_name'])
@pytest.mark.parametrize('name',['ZoneManager::updateRendertimeThread','MedicalSystem::periodicUpdate','HavokCharacter::update'])
def test_non_ai_function_rejects_retired_or_invented_labels(poison,name):
    s=zone_stats();p=s['systems']['profiled_function']
    p['function']=name
    if poison=='world_scalar':s['systems']['charsUpdateUT_mean_ms']=0
    elif poison=='world_series':s['per_frame'][0]['charsUpdateUT_ms']=0
    elif poison=='ai':s['systems']['ai_profiled_function']=deepcopy(p)
    elif poison=='physics':s['systems']['physics_backThreadUpdate']=deepcopy(p)
    else:p['function']='BirdManager::guessed'
    with pytest.raises(ValueError):validate(s)


def renderer_stats():
    from function_diagnostics import RENDERER_SCOPE
    s=main_loop_stats();s['systems']['profiled_function'].update(function='Renderer::update',scope=RENDERER_SCOPE,hook_source='existing_renderer_service_hook')
    return s


def test_renderer_original_scope_and_identity_without_gpu_claim():
    s=renderer_stats();assert function_name(s)=='Renderer::update' and validate(s)['calls_total']==6


@pytest.mark.parametrize('field,value',[('hook_source','existing_main_service_hook'),('hook_source',None),('leading_service_excluded',False),('leading_service_excluded',1),('scope','GPU time')])
def test_renderer_cannot_mislabel_service_or_gpu_time(field,value):
    s=renderer_stats();s['systems']['profiled_function'][field]=value
    with pytest.raises(ValueError):validate(s)


def root_frame_stats():
    from function_diagnostics import ROOT_FRAME_SCOPE,ROOT_FRAME_EXPORT
    s=renderer_stats();s['systems']['profiled_function'].update(function='Ogre::Root::renderOneFrame',scope=ROOT_FRAME_SCOPE,hook_source='loaded_ogre_export',leading_service_excluded=False,
        binding_module='OgreMain_x64.dll',binding_module_path='E:/Synthetic/OgreMain_x64.dll',binding_symbol=ROOT_FRAME_EXPORT,binding_address='0x10000010')
    return s


def test_root_frame_has_loaded_export_and_includes_nested_services():
    assert function_name(root_frame_stats())=='Ogre::Root::renderOneFrame'


@pytest.mark.parametrize('field,value',[('hook_source','existing_renderer_service_hook'),('leading_service_excluded',True),('scope','GPU time'),('binding_module','other.dll'),('binding_module_path','E:/Synthetic/other.dll'),('binding_module_path',None),('binding_address',None),('binding_address','0x0'),('binding_symbol','?renderOneFrame@Root@Ogre@@QEAA_NM@Z')])
def test_root_frame_cannot_hide_wrong_overload_or_scope(field,value):
    s=root_frame_stats();s['systems']['profiled_function'][field]=value
    with pytest.raises(ValueError):validate(s)
