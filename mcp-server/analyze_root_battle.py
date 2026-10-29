"""Forty-NPC battle with inclusive Root wall and quantized thread CPU counters."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PureWindowsPath
from analyze_heavy_battle import analyze as heavy_analysis
from analyze_root_frame import NAME, OGRE_SHA256, normalized
from function_diagnostics import validate as function, match_cpu, ROOT_FRAME_EXPORT

CALIBRATION_SCOPE='Separate own-helper observations, not guaranteed in-game precision'


def root_binding(data,expected_version='0.8.18'):
    if expected_version not in ('0.8.18','0.8.19'):raise ValueError('Unsupported Root battle version')
    p=data['initial_ping'];module=data['function_module']
    if (p.get('plugin_version')!=expected_version or p.get('system_hook_count')!=3 or
            p.get('profiled_function')!=NAME or p.get('ogre_render_one_frame_profiling') is not True or
            p.get('function_hook_reuses_service') is not False or p.get('function_thread_cpu_enabled') is not True or
            p.get('dedicated_system_hook_count')!=3 or p.get('service_hook_count')!=2 or p.get('installed_hook_count')!=5 or
            any(p.get(k) is not False for k in ('main_loop_gpu_sensitive_profiling','renderer_update_profiling','havok_character_update_profiling'))):
        raise ValueError('Root battle selection, CPU mode or hook counts differ')
    if p.get('function_binding_source')!='loaded_module_export' or p.get('function_binding_symbol')!=ROOT_FRAME_EXPORT:
        raise ValueError('Wrong named Root overload binding')
    cost=p.get('function_thread_cpu_startup_read_mean_us')
    if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<=0:
        raise ValueError('Root CPU read calibration unavailable')
    if module.get('sha256')!=OGRE_SHA256 or module.get('bytes')!=10207744 or module['loaded'].get('size')!=10260480:
        raise ValueError('Loaded Ogre build differs')
    path=normalized(module['path'])
    if (path!=normalized(module['loaded']['path']) or path!=normalized(p['function_binding_module_path']) or
            PureWindowsPath(module['path']).name.casefold()!='ogremain_x64.dll'):
        raise ValueError('Root module paths disagree')
    export=module['export'];rva=export.get('rva')
    if export.get('name')!=ROOT_FRAME_EXPORT or export.get('forwarder') is not None or type(rva) is not int or not 0<rva<module['loaded']['size']:
        raise ValueError('Missing local named Root entry')
    address=int(module['loaded']['base'],16)+rva
    if not 0<address<2**64 or int(p['function_binding_address'],16)!=address:
        raise ValueError('Native Root address differs from loaded export')
    return path,address,cost


def analyze(data,expected_version='0.8.18'):
    if data.get('expected_function_cpu_enabled') is not True or data.get('transport')!='mcp-stdio':
        raise ValueError('CPU battle mode or MCP transport not explicit')
    if type(data.get('pairs')) is not int or data['pairs']!=20:
        raise ValueError('Root battle requires forty requested NPCs')
    source=data.get('source_sha256_before')
    if not isinstance(source,str) or not re.fullmatch('[0-9a-f]{64}',source) or data.get('source_sha256_after')!=source:
        raise ValueError('Protected source SHA changed or missing')
    ref=data.get('calibration_reference',{});refpath=ref.get('path');refhash=ref.get('sha256')
    if (not isinstance(refpath,str) or not refpath or PureWindowsPath(refpath).is_absolute() or
            '..' in PureWindowsPath(refpath).parts or PureWindowsPath(refpath).suffix!='.json' or
            not isinstance(refhash,str) or not re.fullmatch('[0-9a-f]{64}',refhash) or ref.get('scope')!=CALIBRATION_SCOPE):
        raise ValueError('Missing separate calibration provenance')
    path,address,cost=root_binding(data,expected_version)
    result=heavy_analysis(data)
    for summary,row in zip(result['windows'],data['windows']):
        f=function(row['statistics'])
        if (f is None or f['function']!=NAME or f['cpu_enabled'] is not True or f['calls_total']<=0 or
                f['cpu_available_calls']!=f['calls_total'] or f['cpu_unavailable_calls']!=0):
            raise ValueError('Root CPU coverage incomplete')
        if normalized(f['binding_module_path'])!=path or int(f['binding_address'],16)!=address:
            raise ValueError('Root statistics binding differs')
        if f['threads_truncated'] or f['unlisted']['calls_total']:
            raise ValueError('Root call identities incomplete')
        joined=match_cpu(f,row['process_resources']);a,b=row['roles_before'],row['roles_after']
        if not a['frame']<=row['statistics']['first_frame']<=row['statistics']['last_frame']<=b['frame']:
            raise ValueError('Root heartbeat roles do not bracket retained frames')
        for identity in joined['threads']:
            tid=identity['thread_id']
            identity['matches_game_thread_at_bounds']=a['game_thread']==b['game_thread']==tid
            identity['matches_renderer_thread_at_bounds']=a['service_thread']==b['service_thread']==tid
            if (not identity['matched_cpu_identity'] or not identity['matches_game_thread_at_bounds'] or
                    not identity['matches_renderer_thread_at_bounds']):
                raise ValueError('Root exact CPU identity or heartbeat role differs')
        summary['selected_function']=f
        summary['selected_function_cpu_identity_matches']=joined
        total=f['cpu_user_total_ms']+f['cpu_kernel_total_ms']
        summary['root_cpu_counter_total_ms']=total
        summary['root_cpu_counter_mean_ms_per_retained_frame']=total/row['statistics']['count']
    result['cpu_startup_read_mean_us']=cost
    result['calibration_reference']=dict(ref)
    result['calibration_reference_scope']='Companion provenance only; this pure analysis does not open the referenced helper report. Its separate hash-bound replay does not guarantee in-game precision.'
    result['scope']='One generated forty-NPC urban battle with zero-argument Ogre Root selected. Inclusive wall and quantized CPU around original work, measurement code and nested callbacks/probes/services. Completed-call buckets, scene snapshots and wider whole-thread OS CPU have different boundaries. No exclusive engine/GPU time, wall-minus-CPU wait estimate, marginal NPC cost, pooled version comparison or optimization gain inferred.'
    result['cpu_counter_scope']='Unit100ns is not precision. Per-call zeros and deltas greater than call wall may reflect quantification; preserve without clamping. Report aggregate user/kernel counters and their arithmetic means only; the helper quantum is not guaranteed in-game resolution.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();raw=args.input.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=args.expected_sha256:raise ValueError('Capture SHA differs')
    result=analyze(json.loads(raw))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(dict(source_sha256=sha,result=result),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=sha,windows=len(result['windows']),actors=len(result['actors']))))
