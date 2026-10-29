"""Describe bounded update-list snapshots; names are labels, not identities."""
from collections import Counter
import hashlib
import json
import math


def digest(rows):
    ordered=sorted(rows,key=lambda row:json.dumps(row,ensure_ascii=False,separators=(',',':')))
    return hashlib.sha256(json.dumps(ordered,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def summarize(capture):
    before,after=capture['scene_before'],capture['scene_after']
    inventory=capture['inventory']; rows=inventory['characters']
    total,limit=inventory['total_update_list'],capture['limit']
    if (isinstance(total,bool) or not isinstance(total,int) or total<0 or
        isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500):
        raise ValueError('Invalid inventory bounds')
    if len(rows)>min(total,limit):
        raise ValueError('Inventory exceeds its bounds')
    labels=Counter();positions=[]
    for row in rows:
        name,faction=row['name'],row['faction'];xyz=row['position']
        if not isinstance(name,str) or not (faction is None or isinstance(faction,str)):
            raise ValueError('Invalid character labels')
        if len(xyz)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in xyz):
            raise ValueError('Invalid position')
        labels[(name,faction)]+=1;positions.append([name,faction,*xyz])
    clocks=[before['game_total_hours'],after['game_total_hours']]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in clocks):
        raise ValueError('Invalid scene clock')
    if any(isinstance(s['frame'],bool) or not isinstance(s['frame'],int) or s['frame']<0 for s in (before,after)):
        raise ValueError('Invalid scene frame')
    if after['frame']<before['frame']:
        raise ValueError('Frame counter regressed')
    label_rows=[[name,faction,count] for (name,faction),count in labels.items()]
    factions=Counter(row['faction'] for row in rows)
    complete=len(rows)==total
    paused=before['paused'] and after['paused']
    clock_unchanged=abs(clocks[1]-clocks[0])<=1e-7
    population_agrees=before['loaded_character_count']==total==after['loaded_character_count']
    camera_unchanged=all(before[k]==after[k] for k in ('camera_center','camera_position','free_camera'))
    return dict(returned_count=len(rows),total_update_list=total,limit=limit,complete=complete,
        paused_at_bounds=paused,clock_unchanged=clock_unchanged,population_agrees_at_bounds=population_agrees,
        camera_unchanged=camera_unchanged,first_frame=before['frame'],last_frame=after['frame'],
        game_total_hours=clocks[0],labels_sha256=digest(label_rows),positions_sha256=digest(positions),
        label_multiplicities=sorted(label_rows,key=lambda x:json.dumps(x,ensure_ascii=False)),
        repeated_label_groups=sum(n>1 for n in labels.values()),
        faction_counts=sorted([[name,count] for name,count in factions.items()],key=lambda x:json.dumps(x,ensure_ascii=False)),
        comparable=bool(complete and paused and clock_unchanged and population_agrees and camera_unchanged),
        atomic=False,scope='GameWorld update list bracketed by two scene reads; not all world characters or persistent actor identities.')


def compare(a,b):
    allowed=a['comparable'] and b['comparable'] and abs(a['game_total_hours']-b['game_total_hours'])<=1e-7
    result=dict(full_label_comparison_allowed=allowed,
        total_count_delta=b['total_update_list']-a['total_update_list'],
        reason=None if allowed else 'Incomplete, changing, unpaused or different-clock capture; no full roster difference inferred')
    if allowed:
        old=Counter({(name,faction):n for name,faction,n in a['label_multiplicities']})
        new=Counter({(name,faction):n for name,faction,n in b['label_multiplicities']})
        result.update(labels_equal=a['labels_sha256']==b['labels_sha256'],
            exact_positions_equal=a['positions_sha256']==b['positions_sha256'],
            added_label_occurrences=sum((new-old).values()),removed_label_occurrences=sum((old-new).values()),
            added_labels=sorted([[*key,n] for key,n in (new-old).items()],key=lambda x:json.dumps(x)),
            removed_labels=sorted([[*key,n] for key,n in (old-new).items()],key=lambda x:json.dumps(x)),
            interpretation='Label multiplicity differences only; no persistent identity, spawn, death or movement attribution.')
    return result


def admission(reference,current):
    """Conservative gate for visible environment equality, not determinism."""
    result=compare(reference if reference is not None else current,current)
    result['accepted']=bool(result['full_label_comparison_allowed'] and
        result.get('labels_equal') and result.get('exact_positions_equal'))
    return result


async def collect(client,limit=250):
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500:
        raise ValueError('Invalid requested inventory bound')
    capture=dict(limit=limit,scene_before=await client.call('get_scene_state'))
    capture['inventory']=await client.call('list_characters',limit=limit,details=False)
    capture['scene_after']=await client.call('get_scene_state')
    capture['summary']=summarize(capture)
    return capture
