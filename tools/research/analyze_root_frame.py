"""Original zero-argument Ogre frame, inclusive of nested probes/services/waits."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json
from pathlib import Path,PureWindowsPath
from analyze_chars_split import analyze as analyze_city
from function_diagnostics import validate as function,match_cpu,ROOT_FRAME_EXPORT

NAME='Ogre::Root::renderOneFrame'
OGRE_SHA256='7d3888d21398647519f10a89b1f300d8606f761ad159e6021a797b1b9b3df5f6'
def normalized(path):
    if not isinstance(path,str) or not path:raise ValueError('Missing loaded Ogre path')
    return PureWindowsPath(path).as_posix().casefold()

def analyze(data,expected_cpu=False):
    if type(expected_cpu) is not bool:raise ValueError('CPU mode must be explicit bool')
    result=analyze_city(data,expected_version='0.8.18');p=data['initial_ping'];module=data['function_module']
    if (p.get('profiled_function')!=NAME or p.get('ogre_render_one_frame_profiling') is not True or p.get('function_hook_reuses_service') is not False or
        p.get('dedicated_system_hook_count')!=3 or p.get('service_hook_count')!=2 or p.get('installed_hook_count')!=5 or
        p.get('function_thread_cpu_enabled') is not expected_cpu or
        any(p.get(k) is not False for k in ('main_loop_gpu_sensitive_profiling','renderer_update_profiling','havok_character_update_profiling'))):raise ValueError('Root selection/hook counts/CPU not explicit')
    if p.get('function_binding_source')!='loaded_module_export' or p.get('function_binding_symbol')!=ROOT_FRAME_EXPORT:raise ValueError('Wrong Root overload binding')
    if module.get('sha256')!=OGRE_SHA256 or module.get('bytes')!=10207744 or module['loaded'].get('size')!=10260480:raise ValueError('Loaded Ogre build differs')
    path=normalized(module['path'])
    if path!=normalized(module['loaded']['path']) or path!=normalized(p['function_binding_module_path']) or PureWindowsPath(module['path']).name.casefold()!='ogremain_x64.dll':raise ValueError('Root module paths disagree')
    export=module['export'];rva=export.get('rva')
    if export.get('name')!=ROOT_FRAME_EXPORT or export.get('forwarder') is not None or type(rva) is not int or not 0<rva<module['loaded']['size']:raise ValueError('Missing local named Root entry')
    address=int(module['loaded']['base'],16)+rva
    if not 0<address<2**64 or int(p['function_binding_address'],16)!=address:raise ValueError('Native resolved address differs from loaded export')
    for summary,row in zip(result['phases'],data['phases']):
        total=function(row['statistics'])
        if total is None or total['function']!=NAME or total['cpu_enabled'] is not expected_cpu or total['calls_total']<=0:raise ValueError('Root completed original calls unavailable')
        if normalized(total['binding_module_path'])!=path or int(total['binding_address'],16)!=address:raise ValueError('Root statistics binding differs')
        summary['selected_function']=total;summary['selected_function_cpu_identity_matches']=match_cpu(total,row['process_resources'])
    result['scope']='Original zero-argument Ogre root-frame calls; inclusive original work, waits, callbacks and nested probe/command service included. Completed-call bucket admission can cross boundaries. Not exclusive CPU or GPU time; no subtraction from frame/OS CPU, pooled phase comparison or causal gain. Three profiled boundaries, three dedicated plus two service detours; Renderer/MainLoop/Havok selections inactive.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.input.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=args.expected_sha256:raise SystemExit('Source SHA256 mismatch')
    out=dict(source_sha256=digest,result=analyze(json.loads(raw)))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),source_sha256=digest)))
