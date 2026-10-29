"""Read-only frame-statistics fallback for the native response-size limit."""
import json
from probe import ProbeError

SIZE_ERROR='response too large; reduce n or limit'


def validate_plan(plan,maximum):
    if type(maximum) is not int or not 1<=maximum<=3600:raise ValueError('Invalid statistics maximum')
    attempts=plan['attempts'];expected=maximum
    if not 1<=len(attempts)<=12:raise ValueError('Invalid statistics attempt count')
    for index,row in enumerate(attempts):
        if type(row['n']) is not int or row['n']!=expected:raise ValueError('Statistics shrink sequence differs')
        if index==len(attempts)-1:
            if row.get('ok') is not True or 'error' in row:raise ValueError('Statistics request did not succeed')
            if type(row['compact_bytes']) is not int or row['compact_bytes']<=0:raise ValueError('Invalid statistics byte count')
        else:
            if row.get('ok') is not False or SIZE_ERROR not in row.get('error','') or expected==1:
                raise ValueError('Unsupported statistics retry reason')
            expected=max(1,expected//2)
    if plan['requested_maximum']!=maximum or plan['selected_count']!=expected:raise ValueError('Statistics selected count differs')
    return expected


async def collect(client,maximum,trace=None):
    if type(maximum) is not int or not 1<=maximum<=3600:raise ValueError('Invalid statistics maximum')
    if trace is None:trace={}
    attempts=[];count=maximum
    trace.update(requested_maximum=maximum,selected_count=None,attempts=attempts)
    while True:
        try:stats=await client.call('get_frame_stats',n=count,detail='full')
        except ProbeError as exc:
            attempts.append(dict(n=count,ok=False,error=str(exc)))
            if SIZE_ERROR not in str(exc) or count==1:raise
            count=max(1,count//2)
            continue
        if stats['count']!=count:raise ValueError('Statistics response count differs')
        attempts.append(dict(n=count,ok=True,compact_bytes=len(json.dumps(stats,separators=(',',':')).encode('utf-8'))))
        trace['selected_count']=count;plan=trace
        validate_plan(plan,maximum)
        return stats,plan
