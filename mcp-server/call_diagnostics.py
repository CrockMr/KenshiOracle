"""Validate bounded inclusive call buckets and partial CPU without clamping."""
import math


def validate(stats,key):
    systems=stats.get('systems',{});total=systems.get(key)
    if total is None: return None # Older builds or unavailable hook.
    cpu=total['cpu_enabled'];rows=total['threads'];overflow=total['unlisted']
    if not isinstance(cpu,bool) or total['thread_capacity']!=8 or len(rows)>8:
        raise ValueError('Invalid call capacity or CPU mode')
    ids=[r['thread_id'] for r in rows]
    keys=[(r['thread_id'],r.get('created_filetime')) for r in rows]
    if len(set(keys))!=len(keys) or any(isinstance(x,bool) or not isinstance(x,int) or not 1<=x<=0xffffffff for x in ids):
        raise ValueError('Invalid call thread identities')
    for row in rows:
        created=row.get('created_filetime')
        if created is not None and (not isinstance(created,str) or not created.isascii() or not created.isdecimal() or not 0<int(created)<2**64):
            raise ValueError('Invalid call creation identity')
    for row in [total,overflow]+rows:
        for key in ('calls_total','cpu_available_calls','cpu_unavailable_calls'):
            v=row[key]
            if isinstance(v,bool) or not isinstance(v,int) or v<0: raise ValueError('Invalid call counter')
        if row['cpu_available_calls']+row['cpu_unavailable_calls']!=row['calls_total']:
            raise ValueError('Call CPU availability does not partition calls')
        for key in ('mean_ms','max_call_ms'):
            v=row[key]
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
                raise ValueError('Invalid call timing')
        if not row['calls_total'] and (row['mean_ms'] or row['max_call_ms']):
            raise ValueError('Call time without a call')
        values=[row[k] for k in ('cpu_user_total_ms','cpu_kernel_total_ms')]
        if cpu:
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values):
                raise ValueError('Invalid call CPU values')
        elif values!=[None,None] or row['cpu_available_calls']:
            raise ValueError('Disabled call CPU reported as measured')
    parts=rows+[overflow]
    for key in ('calls_total','cpu_available_calls','cpu_unavailable_calls','mean_ms'):
        if not math.isclose(sum(r[key] for r in parts),total[key],rel_tol=1e-7,abs_tol=1e-7):
            raise ValueError('Call thread totals do not reconcile')
    if cpu:
        for key in ('cpu_user_total_ms','cpu_kernel_total_ms'):
            if not math.isclose(sum(r[key] for r in parts),total[key],rel_tol=1e-7,abs_tol=1e-7):
                raise ValueError('Call thread CPU does not reconcile')
    if not math.isclose(max(r['max_call_ms'] for r in parts),total['max_call_ms'],rel_tol=1e-7,abs_tol=1e-7):
        raise ValueError('Call maxima do not reconcile')
    if total['threads_truncated']!=(overflow['calls_total']>0):
        raise ValueError('Call overflow flag disagrees with calls')
    return total


def match_cpu(total,resources):
    if total is None:return None
    wall=resources['elapsed_seconds']
    if not math.isfinite(wall) or wall<=0 or resources['before']['created_at']!=resources['after']['created_at']:
        raise ValueError('Call CPU interval or process lifetime changed')
    threads=resources['thread_cpu']['threads'];indexed={(r['tid'],r['created_filetime']):r for r in threads}
    if len(indexed)!=len(threads):raise ValueError('Duplicate CPU thread identity')
    rows=[]
    for r in total['threads']:
        key=(r['thread_id'],r.get('created_filetime'));matched=indexed.get(key) if key[1] is not None else None
        rows.append(dict(thread_id=key[0],created_filetime=key[1],matched_cpu_identity=matched is not None,
            whole_thread_cpu_seconds=matched['cpu_seconds'] if matched else None,
            whole_thread_logical_cpu_equivalents=matched['cpu_seconds']/wall if matched else None))
    return dict(threads=rows,scope='Function tail and enclosing OS CPU interval differ; no exclusive coverage fraction inferred.')
