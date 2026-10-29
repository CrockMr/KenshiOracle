"""Validate split charsUpdate wall intervals and bounded native thread buckets."""

import _research_bootstrap  # Repository-relative imports for direct execution.
import math
from statistics_detail import validate as validate_statistics_detail, per_frame_rows
SCOPE='All completed calls, including nested calls if any; bucket admission at telemetry-lock acquisition. Original-call wall and post-call-to-lock wall are disjoint intervals, not CPU time; post-call includes timer overhead and scheduling, not pure lock contention.'
TOTALS=('call_wall_total_ms','post_call_to_lock_total_ms','legacy_total_ms')
MEANS=('call_wall_mean_ms','post_call_to_lock_mean_ms','legacy_mean_ms')
MAXIMA=('max_call_wall_ms','max_post_call_to_lock_ms','max_legacy_ms')


def close(a,b):return math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-7)
def number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('Invalid chars wall duration')
    return value
def count(value):
    if type(value) is not int or not 0<=value<=2**53:raise ValueError('Invalid chars count')
    return value


def totals(row,n):
    calls=count(row['calls_total'])
    for key in TOTALS+MEANS+MAXIMA:number(row[key])
    if not close(row[TOTALS[0]]+row[TOTALS[1]],row[TOTALS[2]]):raise ValueError('Chars intervals do not reconcile')
    for total,mean,maximum in zip(TOTALS,MEANS,MAXIMA):
        if not close(row[mean],row[total]/n) or row[maximum]>row[total] and not close(row[maximum],row[total]):raise ValueError('Chars mean/max differs')
    if not calls and any(row[k]!=0 for k in TOTALS+MEANS+MAXIMA):raise ValueError('Chars time without calls')
    if row[MAXIMA[2]]+1e-7<max(row[MAXIMA[0]],row[MAXIMA[1]]) or row[MAXIMA[2]]>row[MAXIMA[0]]+row[MAXIMA[1]]+1e-7:raise ValueError('Chars maxima inconsistent')


def validate(stats):
    detail=validate_statistics_detail(stats)
    n=count(stats['count'])
    if not 1<=n<=3600:raise ValueError('Chars validation needs a retained frame window')
    systems=stats['systems']
    if 'charsUpdate_split' not in systems:raise ValueError('Chars split unavailable in this build')
    data=systems['charsUpdate_split']
    if data is None:
        if systems['charsUpdate_mean_ms'] is not None:raise ValueError('Legacy chars enabled without split')
        return None
    if data['function']!='GameWorld::charsUpdate' or data['scope']!=SCOPE or data['thread_identity_mode']!='tls_creation_once':raise ValueError('Unknown chars scope')
    if data['cpu_enabled'] is not False or data['cpu_user_total_ms'] is not None or data['cpu_kernel_total_ms'] is not None:raise ValueError('Chars CPU was not measured')
    if type(data['thread_capacity']) is not int or data['thread_capacity']!=8 or type(data['threads_truncated']) is not bool:raise ValueError('Chars capacity/flags invalid')
    totals(data,n);totals(data['unlisted'],n)
    if not close(number(systems['charsUpdate_mean_ms']),data['legacy_mean_ms']):raise ValueError('Historical chars mean disagrees')
    rows=data['threads'];keys=set()
    if len(rows)>8:raise ValueError('Too many chars threads')
    for row in rows:
        totals(row,n)
        if not row['calls_total'] or type(row['thread_id']) is not int or not 0<row['thread_id']<=0xffffffff or type(row['identity_verified']) is not bool:raise ValueError('Invalid chars thread identity')
        stamp=row['created_filetime']
        if row['identity_verified']:
            if type(stamp) is not str or not stamp.isascii() or not stamp.isdecimal() or not 0<int(stamp)<2**64:raise ValueError('Invalid chars creation FILETIME')
        elif stamp is not None:raise ValueError('Unverified chars creation must be null')
        key=(row['thread_id'],stamp)
        if key in keys:raise ValueError('Duplicate chars thread identity')
        keys.add(key)
    all_rows=rows+[data['unlisted']]
    if sum(r['calls_total'] for r in all_rows)!=data['calls_total']:raise ValueError('Chars calls not reconciled')
    for key in TOTALS:
        if not close(sum(r[key] for r in all_rows),data[key]):raise ValueError('Chars thread times not reconciled')
    for key in MAXIMA:
        if not close(max([r[key] for r in all_rows]),data[key]):raise ValueError('Chars thread maxima not reconciled')
    if data['threads_truncated']!=(data['unlisted']['calls_total']>0) or data['threads_truncated'] and len(rows)!=8:raise ValueError('Chars overflow flag differs')
    series=per_frame_rows(stats)
    if detail=='full' and (len(series)!=min(n,100) or stats['series_truncated']!=(n>100)):raise ValueError('Chars frame retention differs')
    if stats['last_frame']-stats['first_frame']+1!=n:raise ValueError('Chars frame window differs')
    calls=0;call=legacy=0
    for index,row in enumerate(series):
        if row['frame']!=stats['last_frame']-len(series)+1+index:raise ValueError('Chars series frame differs')
        calls+=count(row['charsUpdate_calls']);call+=number(row['charsUpdate_call_wall_ms']);legacy+=number(row['charsUpdate_ms'])
        if row['charsUpdate_call_wall_ms']>row['charsUpdate_ms']+1e-7:raise ValueError('Chars call exceeds legacy interval')
    if detail=='full':
        for actual,expected in ((calls,data['calls_total']),(call,data['call_wall_total_ms']),(legacy,data['legacy_total_ms'])):
            if n<=100 and not close(actual,expected) or n>100 and actual>expected+1e-7:raise ValueError('Chars series totals differ')
    return data
