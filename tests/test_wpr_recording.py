import subprocess
import pytest
from wpr_recording import Recording


def result(stdout='',code=0):return dict(returncode=code,stdout=stdout,stderr='')
QUIET=result('WPR is not recording')


class Runner:
    def __init__(self,*values):self.values=list(values);self.calls=[]
    def __call__(self,*args):
        self.calls.append(args)
        value=self.values.pop(0)
        if isinstance(value,Exception):raise value
        return value


def session(tmp_path,runner):return Recording('KenshiProbeHeng_test','tools/research/cpu-sampling.wprp',tmp_path,runner)


def test_success_stops_only_owned_instance(tmp_path):
    run=Runner(QUIET,result(),result(),QUIET);r=session(tmp_path,run)
    r.start();r.stop(tmp_path/'cpu.etl');r.stop(tmp_path/'cpu.etl')
    assert not r.cleanup_required and not r.started and len(run.calls)==4
    assert run.calls[2][-2:]==('-instancename',r.instance)


def test_foreign_recording_never_stopped_or_cancelled(tmp_path):
    run=Runner(result('WPR recording is in progress OtherSession'));r=session(tmp_path,run)
    with pytest.raises(RuntimeError):r.start()
    r.stop(tmp_path/'cpu.etl')
    assert run.calls==[('-status',)] and not r.started


def test_failed_start_without_collector_has_no_stop(tmp_path):
    run=Runner(QUIET,result('denied',1),QUIET);r=session(tmp_path,run)
    with pytest.raises(RuntimeError):r.start()
    r.stop(tmp_path/'cpu.etl')
    assert not r.cleanup_required and not any(c[0] in {'-stop','-cancel'} for c in run.calls)


def test_failed_stop_uses_only_named_cancel(tmp_path):
    active=result('WPR recording is in progress KenshiProbeHeng_test')
    run=Runner(QUIET,result(),result('stop failed',1),active,result(),QUIET);r=session(tmp_path,run)
    r.start()
    with pytest.raises(RuntimeError):r.stop(tmp_path/'cpu.etl')
    assert not r.cleanup_required and run.calls[-2]==('-cancel','-instancename',r.instance)


def test_unverified_cleanup_stays_explicit(tmp_path):
    active=result('WPR recording is in progress KenshiProbeHeng_test')
    run=Runner(QUIET,result(),result('failed',1),active,result('failed',1),active);r=session(tmp_path,run)
    r.start()
    with pytest.raises(RuntimeError):r.stop(tmp_path/'cpu.etl')
    assert r.cleanup_required and r.started
    assert all('-instancename' in c for c in run.calls if c[0] in {'-stop','-cancel'})


def test_start_timeout_recovers_only_matching_collector(tmp_path):
    active=result('WPR recording is in progress KenshiProbeHeng_test')
    run=Runner(QUIET,subprocess.TimeoutExpired('wpr',60),active,result(),QUIET);r=session(tmp_path,run)
    with pytest.raises(subprocess.TimeoutExpired):r.start()
    assert r.started and r.cleanup_required
    r.stop(tmp_path/'cpu.etl');assert not r.cleanup_required
