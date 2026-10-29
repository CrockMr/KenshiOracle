from copy import deepcopy
import pytest
from analyze_json_benchmark import OPS,analyze,compare


def capture():
    data=dict(completed=True,synthetic_only=True,compiler_flags='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010',
        binary_sha256='a'*64,source_sha256={'plugin/json.h':'b'*64,'tests/benchmark_json.cpp':'c'*64},runs=[])
    for index in range(3):
        rows=[]
        for fixture in range(3):
            for rep in range(7):
                for order in range(5):
                    op=OPS[(order+rep)%5];duration=.5 if op=='serialize_current' else 1
                    rows.append(dict(fixture=fixture,repetition=rep,operation=op,bytes=(fixture+1)*100,fnv1a32=fixture,
                        elapsed_ms=duration*60,per_operation_ms=duration))
        native=dict(schema=1,compiler=1600,pointer_bytes=8,iterations=60,repeats=7,synthetic_only=True,rows=rows,checksum=420*(26+1200))
        data['runs'].append(dict(index=index,returncode=0,stderr='',elapsed_seconds=1,native=native))
    return data


def test_replay_and_paired_wall_ratio():
    data=capture();report=analyze(data)
    assert report['fixtures'][1]['paired_legacy_over_current']['median']==2
    assert report['fixtures'][1]['operations']['copy_destroy']['count']==21
    new=deepcopy(data);new['source_sha256']['plugin/json.h']='d'*64
    assert compare(data,new)['changed_sources']==['plugin/json.h']


@pytest.mark.parametrize('mutation',['incomplete','error','missing','order','checksum','negative','nan','units','bytes','hash','compiler','identity','repeat'])
def test_corrupt_or_uncontrolled_timings_rejected(mutation):
    data=capture();run=data['runs'][0];row=run['native']['rows'][0]
    if mutation=='incomplete':data['completed']=False
    elif mutation=='error':run['returncode']=1
    elif mutation=='missing':run['native']['rows'].pop()
    elif mutation=='order':row['operation']='serialize_current'
    elif mutation=='checksum':run['native']['checksum']+=1
    elif mutation=='negative':row['elapsed_ms']=-1
    elif mutation=='nan':row['per_operation_ms']=float('nan')
    elif mutation=='units':row['elapsed_ms']*=1000
    elif mutation=='bytes':row['bytes']=70000
    elif mutation=='hash':data['binary_sha256']='x'*64
    elif mutation=='compiler':run['native']['compiler']=1900
    elif mutation=='identity':data['runs'][1]['native']['rows'][0]['fnv1a32']=123
    elif mutation=='repeat':run['native']['repeats']=1
    with pytest.raises(ValueError):analyze(data)


def test_fixture_and_benchmark_source_changes_are_not_a_comparison():
    old=capture();new=deepcopy(old);new['source_sha256']['tests/benchmark_json.cpp']='e'*64
    with pytest.raises(ValueError):compare(old,new)
    new=deepcopy(old)
    for run in new['runs']:
        for row in run['native']['rows']:row['fnv1a32']+=100
    with pytest.raises(ValueError):compare(old,new)
