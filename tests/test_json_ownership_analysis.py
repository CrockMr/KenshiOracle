from copy import deepcopy
import pytest
from analyze_json_ownership import OPS,analyze


def sample():
    data=dict(completed=True,synthetic_only=True,fixture_generator_matches=True,compiler_flags='/O2 /EHsc /MD /W3; vcvarsall amd64; MSVC 2010',binary_sha256='a'*64,source_sha256={'plugin/json.h':'b'*64},runs=[])
    for index in range(3):
        rows=[]
        for fixture in range(3):
            for rep in range(7):
                for order in range(4):
                    op=OPS[(order+rep)%4];duration=.5 if op.endswith('transfer') else 1
                    rows.append(dict(fixture=fixture,repetition=rep,operation=op,bytes=80+fixture*100,fnv1a32=fixture,elapsed_ms=duration*60,per_operation_ms=duration))
        data['runs'].append(dict(index=index,returncode=0,stderr='',elapsed_seconds=1,native=dict(schema=1,compiler=1600,pointer_bytes=8,iterations=60,repeats=7,synthetic_only=True,rows=rows,checksum=112560)))
    return data


def test_pairing_and_inclusive_wall_difference():
    report=analyze(sample());pair=report['fixtures'][1]['paired']['pipeline']
    assert pair['count']==21 and pair['ratio_median']==2 and pair['difference_mean_ms']==.5


@pytest.mark.parametrize('mutation',['incomplete','fixture_source','compiler','bool_plan','missing','order','checksum','negative','nan','units','fixture','hash','run_identity','bool_elapsed'])
def test_bad_plan_or_timings_rejected(mutation):
    data=sample();run=data['runs'][0];row=run['native']['rows'][0]
    if mutation=='incomplete':data['completed']=False
    elif mutation=='fixture_source':data['fixture_generator_matches']=False
    elif mutation=='compiler':run['native']['compiler']=1900
    elif mutation=='bool_plan':run['native']['schema']=True
    elif mutation=='missing':run['native']['rows'].pop()
    elif mutation=='order':row['operation']='pipeline_transfer'
    elif mutation=='checksum':run['native']['checksum']+=1
    elif mutation=='negative':row['elapsed_ms']=-1
    elif mutation=='nan':row['elapsed_ms']=float('nan')
    elif mutation=='units':row['elapsed_ms']*=1000
    elif mutation=='fixture':data['runs'][1]['native']['rows'][0]['fnv1a32']=123
    elif mutation=='hash':data['binary_sha256']='x'*64
    elif mutation=='run_identity':run['index']=True
    elif mutation=='bool_elapsed':run['elapsed_seconds']=True
    with pytest.raises(ValueError):analyze(data)
