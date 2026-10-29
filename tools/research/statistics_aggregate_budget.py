"""One compact getter for the full requested tail; never shrink its time range."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import json
from probe import ProbeError
from statistics_detail import validate
from statistics_budget import validate_plan


async def collect(client,maximum,trace=None):
    if type(maximum) is not int or not 1<=maximum<=3600:raise ValueError('Invalid statistics maximum')
    if trace is None:trace={}
    attempts=[];trace.update(requested_maximum=maximum,selected_count=None,detail='aggregates',attempts=attempts)
    try:stats=await client.call('get_frame_stats',n=maximum,detail='aggregates')
    except ProbeError as exc:
        attempts.append(dict(n=maximum,ok=False,error=str(exc)));raise
    if validate(stats)!='aggregates' or stats['count']!=maximum:raise ValueError('Compact statistics range or mode differs')
    size=len(json.dumps(stats,separators=(',',':'),allow_nan=False).encode('utf-8'))
    attempts.append(dict(n=maximum,ok=True,compact_bytes=size));trace['selected_count']=maximum
    if size>=65536:raise ValueError('Compact statistics exceeds response budget')
    validate_plan(trace,maximum)
    return stats,trace
