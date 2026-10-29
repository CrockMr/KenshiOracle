import json
from pathlib import Path
from types import SimpleNamespace
from export_etw import export
from etw_analysis import digest
from test_etw_analysis import fixture,SPAN,PROCESSES,HTML,EVENTS


class Runner:
    def __init__(self,fail=False,ambiguous=False,mutate=None):self.calls=[];self.fail=fail;self.ambiguous=ambiguous;self.mutate=mutate
    def __call__(self,args,**kwargs):
        self.calls.append(args);target=Path(args[args.index('-o')+1])
        if self.fail:return SimpleNamespace(returncode=1,stdout='',stderr='synthetic export failure')
        content=SPAN if target.name=='span.txt' else EVENTS if target.name=='events.txt' else PROCESSES if target.name=='processes.txt' else HTML
        if self.ambiguous and target.name=='processes.txt':content+='MIN, MAX, Thread, 0x457, Kenshi_x64.exe (7), 10, 0\n'
        target.write_text(content,encoding='utf-8')
        if self.mutate is not None and target.name=='game-stacks.html':self.mutate.write_bytes(b'changed')
        return SimpleNamespace(returncode=0,stdout='',stderr='')


def setup(tmp_path):
    p,d=fixture(tmp_path);tool=tmp_path/'fake-xperf.exe';tool.write_bytes(b'fake tool')
    return p,d,tool


def test_exports_are_read_only_filtered_and_hash_anchored(tmp_path):
    p,d,tool=setup(tmp_path);run=Runner();path,r=export(p,tmp_path/'analysis',xperf=tool,runner=run)
    assert r['completed'] and r['game_stacks']['observations']==5 and r['span']['lost_events']==0
    assert all('-i' in cmd and not {'-start','-stop','-cancel'}&set(cmd) for cmd in run.calls)
    assert r['source']['trace_sha256']==d['trace_sha256'] and r['tool']['sha256']==digest(tool)
    assert json.loads(path.read_text())['completed']


def test_failed_export_is_retained_as_failure(tmp_path):
    p,d,tool=setup(tmp_path);path,r=export(p,tmp_path/'analysis',xperf=tool,runner=Runner(fail=True))
    assert not r['completed'] and r['error'] and path.is_file()
    assert digest(tmp_path/'cpu.etl')==d['trace_sha256']


def test_ambiguous_thread_is_not_mixed_into_stack_export(tmp_path):
    p,d,tool=setup(tmp_path);d['process_resources']=dict(pid=7,before=dict(created_at=100),after=dict(created_at=100),
        thread_cpu=dict(threads=[dict(tid=10,created_filetime='123',cpu_seconds=1)],omitted_reasons={}))
    p.write_text(json.dumps(d));run=Runner(ambiguous=True);_,r=export(p,tmp_path/'analysis',xperf=tool,runner=run)
    assert r['completed'] and r['thread_reports'][0]['status']=='missing_or_ambiguous_etl_lifetime'
    assert not any('-tid' in cmd for cmd in run.calls)


def test_source_change_during_processing_is_not_hidden(tmp_path):
    p,d,tool=setup(tmp_path);_,r=export(p,tmp_path/'analysis',xperf=tool,runner=Runner(mutate=tmp_path/'cpu.etl'))
    assert not r['completed'] and 'changed during export' in r['error']['message']


def test_partial_etl_thread_lifetime_is_not_joined_to_enclosing_cpu(tmp_path):
    p,d,tool=setup(tmp_path);d['process_resources']=dict(pid=7,before=dict(created_at=100),after=dict(created_at=100),
        thread_cpu=dict(threads=[dict(tid=10,created_filetime='123',cpu_seconds=1)],omitted_reasons={}))
    p.write_text(json.dumps(d));run=Runner()
    def partial(args,**kwargs):
        result=run(args,**kwargs)
        out=Path(args[args.index('-o')+1])
        if out.name=='processes.txt':out.write_text(PROCESSES.replace('MIN, MAX, Thread','100, MAX, Thread'))
        return result
    _,r=export(p,tmp_path/'analysis',xperf=tool,runner=partial)
    assert r['completed'] and r['thread_reports'][0]['status']=='etl_thread_does_not_span_trace'
    assert not any('-tid' in cmd for cmd in run.calls)
