import pytest
from analyze_thread_metadata import analyze


def inputs():
    module=dict(name='runtime.dll',path='runtime.dll',offset='0x10')
    metadata=dict(pid=1,created_at=10,executable='game.exe',metadata=dict(pid=1,completed=True,cleanup_verified=True,
        threads=[dict(tid=2,created_filetime='123',win32_start_address='0x1010',start_module=module)]))
    evidence=dict(pid=1,phases=[dict(label='test',completed=True,process_resources=dict(pid=1,executable='game.exe',
        before=dict(created_at=10),after=dict(created_at=10),elapsed_seconds=2,user_seconds=1,system_seconds=0,
        thread_cpu=dict(residual_cpu_seconds=-.1,threads=[dict(tid=2,created_filetime='123',cpu_seconds=1.1)])))])
    return metadata,evidence


def test_whole_thread_origin_groups_keep_signed_residual_and_do_not_normalize():
    a,b=inputs();phase=analyze(a,b)['phases'][0]
    assert phase['groups_by_start_module'][0]['fraction_of_process_cpu']==pytest.approx(1.1)
    assert phase['residual_cpu_seconds']==-.1
    assert phase['unmatched_metadata_cpu_seconds']==0


def test_tid_reuse_is_unmatched_instead_of_inheriting_start_module():
    a,b=inputs();a['metadata']['threads'][0]['created_filetime']='different'
    phase=analyze(a,b)['phases'][0]
    assert not phase['groups_by_start_module']
    assert phase['unmatched_metadata_cpu_seconds']==1.1


@pytest.mark.parametrize('change',['pid','inner_pid','created','executable','cleanup','duplicate'])
def test_refuses_bad_identity_or_cleanup(change):
    a,b=inputs()
    if change=='pid': a['pid']=2
    elif change=='inner_pid': a['metadata']['pid']=2
    elif change=='created': a['created_at']=11
    elif change=='executable': a['executable']='other.exe'
    elif change=='cleanup': a['metadata']['cleanup_verified']=False
    else: a['metadata']['threads']*=2
    with pytest.raises(ValueError): analyze(a,b)
