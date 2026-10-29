"""Root battle with compact aggregates for every requested frame, no shrinking."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import argparse,hashlib,json
from pathlib import Path
from analyze_root_battle import analyze as root_battle
from statistics_detail import validate
from statistics_budget import validate_plan


def analyze(data):
    if data.get('statistics_detail_requested')!='aggregates' or data['initial_ping'].get('frame_stats_aggregates_available') is not True:
        raise ValueError('Aggregate contract not explicit')
    result=root_battle(data,expected_version='0.8.19')
    for row in data['windows']:
        for key,plan_key,maximum in [('statistics','statistics_collection',row['requested_frames']),('context','context_collection',3600)]:
            s=row[key];plan=row[plan_key]
            if validate(s)!='aggregates' or plan.get('detail')!='aggregates' or len(plan['attempts'])!=1 or validate_plan(plan,maximum)!=maximum or s['count']!=maximum:
                raise ValueError('Aggregate window shrank or omitted detail mode')
            if plan['attempts'][0]['compact_bytes']!=len(json.dumps(s,separators=(',',':'),allow_nan=False).encode('utf-8')) or plan['attempts'][0]['compact_bytes']>=65536:
                raise ValueError('Aggregate compact byte attestation differs')
        if row.get('navigation_detail_roles_available') is not False:raise ValueError('Omitted navigation detail misrepresented')
    result['statistics_detail_scope']='All requested tail frames retained in one getter per statistics/context request. Per-frame and slow-navigation detail explicitly null with omission counts; aggregation unchanged. Moving queries still have separate scene/OS bounds, not an immutable snapshot or exclusive cost.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.input.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=a.expected_sha256:raise ValueError('Source SHA differs')
    with a.output.open('x',encoding='utf-8') as f:json.dump(dict(source_sha256=sha,result=analyze(json.loads(raw))),f,indent=2);f.write('\n')
    print(json.dumps(dict(output=str(a.output),source_sha256=sha)))
