"""Validate optional native service wall time; never infer exclusive CPU."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import math

SCOPE='Wall time of execute/response assignment/debug log; excludes telemetry attachment, event signal, network JSON serialization/send and client transport. Not CPU time.'


def validate(result,command,*,require_identity=True):
    row=result['_probe_service']
    if type(row['schema_version']) is not int or row['schema_version']!=1 or row['command']!=command or row['scope']!=SCOPE:
        raise ValueError('Unknown command service contract')
    if type(row['menu_service']) is not bool or type(row['identity_verified']) is not bool:
        raise ValueError('Invalid service flags')
    if type(row['thread_id']) is not int or not 0<row['thread_id']<=0xffffffff or type(row['frame']) is not int or row['frame']<0:
        raise ValueError('Invalid service thread/frame')
    created=row['created_filetime']
    if row['identity_verified']:
        if type(created) is not str or not created.isascii() or not created.isdecimal() or not 0<int(created)<2**64:
            raise ValueError('Invalid service creation FILETIME')
    elif created is not None or require_identity:raise ValueError('Unverified service identity')
    keys=('queued_qpc_ms','started_qpc_ms','finished_qpc_ms','queue_wait_ms','service_ms')
    if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) or row[k]<0 for k in keys):
        raise ValueError('Invalid service clock')
    q,s,f=(row[k] for k in keys[:3])
    if not q<=s<=f or not math.isclose(row['queue_wait_ms'],s-q,abs_tol=1e-7) or not math.isclose(row['service_ms'],f-s,abs_tol=1e-7):
        raise ValueError('Inconsistent service clock')
    if 'frame' in result and result['frame']!=row['frame']:raise ValueError('Result/service frame disagreement')
    return row


def summarize(rows):
    """Retain first-read effects and ranges rather than claiming causal overhead."""
    if not rows:raise ValueError('Empty command sample')
    groups={}
    for item in rows:
        timing=validate(item['result'],item['command'])
        wall=item['client_ms']
        if type(wall) not in (int,float) or not math.isfinite(wall) or wall<0:raise ValueError('Invalid client duration')
        # Native flag identifies the restricted Renderer drain, also active in gameplay.
        if timing['menu_service'] and item['command']!='ping':raise ValueError('Unexpected Renderer command')
        groups.setdefault(item['label'],[]).append((timing,wall))
    out={}
    for name,items in groups.items():
        out[name]={'count':len(items),'renderer_service_reads':sum(t['menu_service'] for t,_ in items),'identities':sorted({(t['thread_id'],t['created_filetime']) for t,_ in items}),
                   'first_frame':min(t['frame'] for t,_ in items),'last_frame':max(t['frame'] for t,_ in items)}
        for key,values in [('service_ms',[t['service_ms'] for t,_ in items]),('queue_wait_ms',[t['queue_wait_ms'] for t,_ in items]),('client_ms',[w for _,w in items])]:
            out[name][key]=dict(first=values[0],minimum=min(values),maximum=max(values),mean=sum(values)/len(values))
    return out
