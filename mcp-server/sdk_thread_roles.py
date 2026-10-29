"""Validate copied SDK thread roles and join whole-thread CPU identities."""
import math

ROLES={'world_ai_non_render','world_navmesh','physics_backthread'}
OPTIONAL_ROLES={'world_physics_interface','resource_loader','save_file_system','navmesh_generator'}


def validate(scene,pid):
    if not scene['paused'] or scene['frame_speed_multiplier']!=0:
        raise ValueError('SDK thread roles require a paused snapshot')
    data=scene['sdk_threads']
    if data['process_id']!=pid or data['frame']!=scene['frame']:
        raise ValueError('SDK role process or frame disagreement')
    if not math.isfinite(data['observed_qpc_ms']): raise ValueError('Invalid SDK role timestamp')
    rows=data['roles'];roles=[r['role'] for r in rows]
    if len(roles)!=len(set(roles)) or not ROLES.issubset(roles) or not set(roles)<=ROLES|OPTIONAL_ROLES:
        raise ValueError('Missing, unknown or duplicate SDK roles')
    for row in rows:
        if not isinstance(row['available'],bool) or not isinstance(row['identity_verified'],bool):
            raise ValueError('Invalid SDK role flags')
        if not row['identity_verified']: continue
        if not row['available']: raise ValueError('Verified unavailable SDK object')
        tid=row['sdk_thread_id'];created=row['created_filetime']
        if (isinstance(tid,bool) or not isinstance(tid,int) or not 0<tid<=0xffffffff or
            row['kernel_thread_id']!=tid or row['kernel_process_id']!=pid):
            raise ValueError('SDK and kernel thread identities disagree')
        if not isinstance(created,str) or not created.isascii() or not created.isdecimal() or not 0<int(created)<2**64:
            raise ValueError('Invalid SDK role creation FILETIME')
    return {r['role']:r for r in rows}


def join_cpu(before,after,resources,pid):
    a,b=validate(before,pid),validate(after,pid)
    if after['frame']<before['frame']:raise ValueError('SDK role frame regressed')
    if resources['pid']!=pid or resources['before']['created_at']!=resources['after']['created_at']:
        raise ValueError('CPU process identity changed')
    wall=resources['elapsed_seconds'];cpu=resources['user_seconds']+resources['system_seconds']
    if wall<=0 or not math.isfinite(wall) or not math.isfinite(cpu) or cpu<0: raise ValueError('Invalid CPU interval')
    threads=resources['thread_cpu']['threads'];indexed={(r['tid'],r['created_filetime']):r for r in threads}
    if len(indexed)!=len(threads): raise ValueError('Duplicate CPU thread identity')
    rows=[];matched=set()
    for role in sorted(a.keys()|b.keys()):
        row=dict(role=role,status='unverified',cpu_seconds=None,logical_cpu_equivalents=None)
        if role not in a or role not in b:
            row['status']='optional_role_not_in_both_snapshots';rows.append(row);continue
        first,last=a[role],b[role]
        if first['identity_verified'] and last['identity_verified']:
            key=(first['kernel_thread_id'],first['created_filetime'])
            row.update(thread_id=key[0],created_filetime=key[1])
            if key!=(last['kernel_thread_id'],last['created_filetime']): row['status']='role_identity_changed'
            elif key not in indexed: row['status']='not_in_both_cpu_endpoints'
            else:
                value=indexed[key]['cpu_seconds'];row.update(status='matched',cpu_seconds=value,
                    logical_cpu_equivalents=value/wall,fraction_of_process_cpu=value/cpu if cpu else None);matched.add(key)
        rows.append(row)
    return dict(roles=rows,unique_matched_threads=len(matched),
        scope='SDK object roles, not exclusive functions; two roles may reference the same OS thread, so their CPU must not be summed.')
