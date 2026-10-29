"""Validate one selected system function and its explicit historical aliases."""
import math
import re
from pathlib import PureWindowsPath
from call_diagnostics import validate as validate_buckets,match_cpu
from ai_diagnostics import validate as validate_ai
from statistics_detail import validate as validate_statistics_detail, per_frame_rows

MAIN_LOOP_SCOPE='Completed outermost original main-loop calls; leading pause protection/command draining excluded. Any service callbacks reached inside the original remain included; inclusive wall, not exclusive CPU.'

RENDERER_SCOPE='Completed outermost original renderer-update calls; leading heartbeat/pause protection/command draining/load-state service excluded. Any callbacks reached inside the original remain included; inclusive wall, not GPU or exclusive CPU.'

ROOT_FRAME_SCOPE='Completed outermost zero-argument Ogre::Root::renderOneFrame calls; inclusive work, waits and nested probe/service callbacks included. Not exclusive CPU or GPU time. Bucket admission on completed-call recording; spans may cross frame boundaries.'
ROOT_FRAME_EXPORT='?renderOneFrame@Root@Ogre@@QEAA_NXZ'

FUNCTIONS={'Ogre::Root::renderOneFrame','Renderer::update','AI::periodicUpdate','AI::update4Frame','GameWorld::charsUpdateUT','ZoneManager::updateRendertimeThread','MedicalSystem::periodicUpdate','HavokCharacter::update','GameWorld::mainLoop_GPUSensitiveStuff'}


def validate(stats):
    validate_statistics_detail(stats)
    systems=stats.get('systems',{})
    if 'profiled_function' not in systems:return validate_ai(stats)
    total=validate_buckets(stats,'profiled_function')
    if total is None:
        if any(systems.get(k) is not None for k in ('ai_profiled_function','ai_periodicUpdate','charsUpdateUT_mean_ms')):
            raise ValueError('Alias exists without selected function')
        return None
    name=total.get('function')
    if name not in FUNCTIONS:raise ValueError('Unknown selected function')
    if name=='GameWorld::mainLoop_GPUSensitiveStuff' and (total.get('hook_source')!='existing_main_service_hook' or total.get('leading_service_excluded') is not True or total.get('scope')!=MAIN_LOOP_SCOPE):raise ValueError('Main-loop source/service exclusion not explicit')
    if name=='Renderer::update' and (total.get('hook_source')!='existing_renderer_service_hook' or total.get('leading_service_excluded') is not True or total.get('scope')!=RENDERER_SCOPE):raise ValueError('Renderer source/service exclusion not explicit')
    if name=='Ogre::Root::renderOneFrame' and (total.get('hook_source')!='loaded_ogre_export' or total.get('leading_service_excluded') is not False or total.get('scope')!=ROOT_FRAME_SCOPE or total.get('binding_module')!='OgreMain_x64.dll' or total.get('binding_symbol')!=ROOT_FRAME_EXPORT or not isinstance(total.get('binding_module_path'),str) or PureWindowsPath(total['binding_module_path']).name.casefold()!='ogremain_x64.dll'):raise ValueError('Root export binding or inclusive scope not explicit')
    if name=='Ogre::Root::renderOneFrame' and (not isinstance(total.get('binding_address'),str) or not re.fullmatch('0x[0-9a-fA-F]{1,16}',total['binding_address']) or not 0<int(total['binding_address'],16)<2**64):raise ValueError('Missing exact Root export address')
    nested=total['nested_entries_skipped_total']
    if isinstance(nested,bool) or not isinstance(nested,int) or nested<0:raise ValueError('Invalid nested entries')
    if not isinstance(total['scope'],str) or not total['scope']:raise ValueError('Missing function scope')
    if total.get('thread_identity_mode')!='tls_creation_once':raise ValueError('Unknown function identity mode')
    if name.startswith('AI::'):
        if validate_ai(stats)!=total:raise ValueError('Selected and AI function aliases disagree')
    else:
        if any(systems.get(k) is not None for k in ('ai_profiled_function','ai_periodicUpdate','physics_backThreadUpdate')):
            raise ValueError('Selected non-AI function and retired probe coexist')
        mean=systems.get('charsUpdateUT_mean_ms')
        if name=='GameWorld::charsUpdateUT' and (isinstance(mean,bool) or not isinstance(mean,(int,float)) or not math.isclose(mean,total['mean_ms'],rel_tol=1e-7,abs_tol=1e-7)):
            raise ValueError('charsUpdateUT scalar alias disagrees')
        if name!='GameWorld::charsUpdateUT' and mean is not None:
            raise ValueError('Retired charsUpdateUT scalar present')
    for row in per_frame_rows(stats):
        for field in ('ms','calls','nested_entries_skipped'):
            if 'function_'+field not in row:raise ValueError('Missing selected function series')
            expected=row['function_'+field] if name.startswith('AI::') else None
            if row.get('ai_function_'+field)!=expected:raise ValueError('AI series alias disagrees')
        if name=='GameWorld::charsUpdateUT' and row.get('charsUpdateUT_ms')!=row['function_ms']:
            raise ValueError('World series alias disagrees')
        if name!='GameWorld::charsUpdateUT' and row.get('charsUpdateUT_ms') is not None:
            raise ValueError('Retired world series present')
    return total


def function_name(stats):
    value=validate(stats)
    return value.get('function','AI::periodicUpdate') if value is not None else None
