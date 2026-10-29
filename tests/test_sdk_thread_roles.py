from copy import deepcopy
import pytest
from sdk_thread_roles import validate,join_cpu,ROLES


def scene():
    return dict(frame=10,paused=True,frame_speed_multiplier=0,sdk_threads=dict(process_id=1,frame=10,observed_qpc_ms=100,
        roles=[dict(role=role,available=True,identity_verified=True,sdk_thread_id=7,kernel_thread_id=7,
                    kernel_process_id=1,created_filetime='123') for role in sorted(ROLES)]))


def resources():
    return dict(pid=1,before=dict(created_at=10),after=dict(created_at=10),elapsed_seconds=2,user_seconds=1,system_seconds=0,
                thread_cpu=dict(threads=[dict(tid=7,created_filetime='123',cpu_seconds=1)]))


def test_alias_roles_do_not_invent_three_distinct_threads():
    result=join_cpu(scene(),scene(),resources(),1)
    assert result['unique_matched_threads']==1
    assert all(r['status']=='matched' and r['logical_cpu_equivalents']==.5 for r in result['roles'])


@pytest.mark.parametrize('change',['pid','frame','duplicate','kernel_tid','kernel_pid','creation','pause','available'])
def test_invalid_roles_are_rejected(change):
    s=scene();row=s['sdk_threads']['roles'][0]
    if change=='pid': s['sdk_threads']['process_id']=2
    elif change=='frame': s['sdk_threads']['frame']=11
    elif change=='duplicate': s['sdk_threads']['roles'][1]['role']=row['role']
    elif change=='kernel_tid': row['kernel_thread_id']=8
    elif change=='kernel_pid': row['kernel_process_id']=2
    elif change=='creation': row['created_filetime']='NaN'
    elif change=='pause': s['paused']=False
    else: row['available']=False
    with pytest.raises(ValueError):validate(s,1)


def test_unverified_and_changed_roles_are_not_filled_with_zero():
    before,after=scene(),scene()
    before['sdk_threads']['roles'][0].update(identity_verified=False,kernel_process_id=2)
    after['sdk_threads']['roles'][1]['created_filetime']='456'
    result=join_cpu(before,after,resources(),1)
    assert result['roles'][0]['status']=='unverified' and result['roles'][0]['cpu_seconds'] is None
    assert result['roles'][1]['status']=='role_identity_changed' and result['roles'][1]['cpu_seconds'] is None


def test_reused_cpu_tid_is_not_assigned_to_old_sdk_role():
    cpu=resources();cpu['thread_cpu']['threads'][0]['created_filetime']='456'
    result=join_cpu(scene(),scene(),cpu,1)
    assert not result['unique_matched_threads']
    assert all(r['status']=='not_in_both_cpu_endpoints' and r['cpu_seconds'] is None for r in result['roles'])


def optional_scene():
    s=scene();row=deepcopy(s['sdk_threads']['roles'][0]);row['role']='world_physics_interface'
    s['sdk_threads']['roles'].append(row)
    return s


def test_optional_role_alias_preserves_unique_identity_count():
    result=join_cpu(optional_scene(),optional_scene(),resources(),1)
    assert len(result['roles'])==4 and result['unique_matched_threads']==1
    assert all(r['status']=='matched' for r in result['roles'])


def test_optional_role_at_one_endpoint_is_unknown_and_old_join_unchanged():
    result=join_cpu(scene(),optional_scene(),resources(),1)
    extra=next(r for r in result['roles'] if r['role']=='world_physics_interface')
    assert extra['status']=='optional_role_not_in_both_snapshots' and extra['cpu_seconds'] is None
    assert [r for r in result['roles'] if r is not extra]==join_cpu(scene(),scene(),resources(),1)['roles']


@pytest.mark.parametrize('kind',['unknown','duplicate','missing_core'])
def test_optional_extension_cannot_hide_invalid_core_roles(kind):
    s=optional_scene();rows=s['sdk_threads']['roles']
    if kind=='unknown':rows[-1]['role']='guessed_worker'
    elif kind=='duplicate':rows.append(deepcopy(rows[-1]))
    else:rows.pop(0)
    with pytest.raises(ValueError):validate(s,1)


def test_loader_and_generator_are_distinct_but_unavailable_saver_stays_unknown():
    s=optional_scene();rows=s['sdk_threads']['roles']
    for role,tid in [('resource_loader',8),('navmesh_generator',9)]:
        rows.append(dict(role=role,available=True,identity_verified=True,sdk_thread_id=tid,kernel_thread_id=tid,
                         kernel_process_id=1,created_filetime=str(123+tid)))
    rows.append(dict(role='save_file_system',available=True,identity_verified=False,sdk_thread_id=0))
    cpu=resources();cpu['thread_cpu']['threads'].extend([
        dict(tid=8,created_filetime='131',cpu_seconds=.25),dict(tid=9,created_filetime='132',cpu_seconds=.125)])
    result=join_cpu(s,s,cpu,1);indexed={r['role']:r for r in result['roles']}
    assert len(result['roles'])==7 and result['unique_matched_threads']==3
    assert indexed['resource_loader']['cpu_seconds']==.25
    assert indexed['navmesh_generator']['cpu_seconds']==.125
    assert indexed['save_file_system']['status']=='unverified' and indexed['save_file_system']['cpu_seconds'] is None
