"""Offline ETW provenance and xperf report validation; never executes the target."""
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path,PureWindowsPath
import re
from benchmark import validate_camera_stability,simulation_progress


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def controller(path,allow_incomplete=False):
    path=Path(path).resolve();data=json.loads(path.read_text(encoding='utf-8-sig'))
    if not re.fullmatch(r'KenshiProbe(?:Pilot|Heng)_[0-9a-f]{12}',data['instance']):raise ValueError('Unknown ETW instance kind')
    pid=data['pid'];created=data['created_at']
    if isinstance(pid,bool) or not isinstance(pid,int) or not 0<pid<=0xffffffff:raise ValueError('Invalid game PID')
    if isinstance(created,bool) or not isinstance(created,(int,float)) or not math.isfinite(created) or created<=0:raise ValueError('Invalid game creation time')
    if data.get('cleanup_required') is not False:raise ValueError('Recording cleanup is not verified')
    commands=data.get('wpr_commands',data)
    if any(commands.get(k,{}).get('returncode')!=0 for k in ('start','stop')):raise ValueError('Recording start/stop not successful')
    pilot=data['instance'].startswith('KenshiProbePilot_')
    if pilot:
        if not data['before']['paused'] or not data['after']['paused']:raise ValueError('Pilot pause state changed')
        if data['after']['frame']<data['before']['frame']:raise ValueError('Pilot frame regressed')
    elif not allow_incomplete and (data.get('completed') is not True or data.get('error')):
        raise ValueError('Heng scenario incomplete; explicit partial analysis required')
    condition='paused_at_bounds_only' if pilot else 'not_validated_incomplete_scenario'
    if not pilot and data.get('completed') is True and not data.get('error'):
        before,after=data['scene_before'],data['scene_after']
        for scene in [before]+[r['scene'] for r in data['observations']]+[after]:
            validate_camera_stability(before,scene)
            if scene['paused'] is not False or scene['frame_speed_multiplier']!=1:
                raise ValueError('Heng x1 state disagrees with controller')
        progress=simulation_progress(before,after)
        if progress is None or progress['game_hours']<=0 or progress!=data['simulation_progress']:
            raise ValueError('Heng simulation progress inconsistent')
        condition='running_x1_at_observations_and_positive_progress'
    resources=data.get('process_resources')
    if resources is not None:
        if resources['pid']!=pid or any(resources[k]['created_at']!=created for k in ('before','after')):
            raise ValueError('CPU and ETW controller process identities disagree')
    trace=path.parent/'cpu.etl'
    if isinstance(data['trace_bytes'],bool) or not isinstance(data['trace_bytes'],int) or data['trace_bytes']<=0:
        raise ValueError('Invalid ETL byte count')
    if not trace.is_file() or trace.stat().st_size!=data['trace_bytes'] or digest(trace)!=data['trace_sha256']:
        raise ValueError('ETL size or digest mismatch')
    return data,dict(controller=str(path),controller_sha256=digest(path),trace=str(trace),trace_sha256=data['trace_sha256'],
        trace_bytes=data['trace_bytes'],pid=pid,created_at=created,executable=data['executable'],kind='pilot' if pilot else 'heng',
        scenario_completed=data.get('completed'),scenario_error=data.get('error'),condition_validation=condition,cleanup_verified=True)


def span(text):
    def integer(label):
        match=re.search(r'^'+re.escape(label)+r'\s*:\s*(\d+)\s*$',text,re.M)
        if not match:raise ValueError('Missing trace field: '+label)
        return int(match[1])
    def stamp(label):
        match=re.search(r'^'+re.escape(label)+r'\s*:\s*([0-9/:]+\.[0-9]+)',text,re.M)
        if not match:raise ValueError('Missing trace time')
        raw=match[1];whole,fraction=raw.split('.');seconds=Decimal((datetime.strptime(whole,'%Y/%m/%d:%H:%M:%S')-datetime(1970,1,1)).total_seconds())
        return raw,seconds+Decimal('0.'+fraction)
    first,a=stamp('Start time (UTC)');last,b=stamp('End time (UTC)')
    if b<=a:raise ValueError('Invalid ETL time span')
    return dict(start_utc=first,end_utc=last,seconds=float(b-a),lost_events=integer('Total # Lost Events'),lost_buffers=integer('Total # Lost Buffers'))


def lifetimes(text,pid,executable):
    processes=[];threads={};thread_rows={};suffix='('+str(pid)+')';basename=PureWindowsPath(executable).name.casefold()
    for row in csv.reader(text.splitlines()):
        if len(row)<6:continue
        row=[x.strip() for x in row]
        if not row[4].endswith(suffix):continue
        kind=row[2]
        if kind not in ('Process','Thread'):continue
        key=int(row[3],16)
        if kind=='Process':
            if row[4][:-len(suffix)].strip().casefold()!=basename:raise ValueError('ETL executable name disagrees')
            processes.append(dict(key=str(key),start=row[0],end=row[1]))
        elif row[5].isdigit():
            tid=int(row[5]);threads.setdefault(tid,set()).add(str(key))
            thread_rows.setdefault(tid,[]).append(dict(key=str(key),start=row[0],end=row[1]))
    if len({r['key'] for r in processes})!=1:raise ValueError('PID missing or reused in ETL')
    if not all(r['start']=='MIN' and r['end']=='MAX' for r in processes):raise ValueError('Game lifetime does not span the whole ETL')
    return dict(processes=processes,thread_keys={str(k):sorted(v) for k,v in threads.items()},
        thread_lifetimes={str(k):v for k,v in thread_rows.items()})


class StackTables(HTMLParser):
    def __init__(self):super().__init__();self.table='';self.tables={};self.row=[];self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('id','').startswith('Tbl'):self.table=a['id'];self.tables.setdefault(self.table,[])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
    def handle_data(self,value):
        if self.cell is not None:self.cell+=value
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:self.row.append(' '.join(self.cell.split()));self.cell=None
        if tag=='tr' and self.table:self.tables[self.table].append(self.row)


def stacks(text,pid):
    parser=StackTables();parser.feed(text)
    process=[r for r in parser.tables.get('TblP',[]) if len(r)>=4 and r[1]==str(pid)]
    if len(process)!=1:raise ValueError('Missing or ambiguous filtered game stack report')
    modules=[]
    for row in parser.tables.get('TblME',[])[1:]:
        if len(row)<3:raise ValueError('Malformed module leaf table')
        modules.append(dict(module=row[0],leaf_observations=int(row[1]),reported_percent=row[2]))
    count=int(process[0][2])
    if count<0 or any(r['leaf_observations']<0 for r in modules) or sum(r['leaf_observations'] for r in modules)!=count:
        raise ValueError('Stack module leaf observations do not reconcile')
    return dict(process_name=process[0][0],observations=count,modules=modules,
        scope='Available stack leaf observations, not exclusive subsystem costs or a guarantee of complete call stacks.')


def sampled_profile(text):
    for line in text.splitlines():
        row=line.split()
        if len(row)==8 and row[5:7]==['Sampled','Profile']:
            total,with_stack=int(row[3]),int(row[7])
            if not 0<=with_stack<=total:raise ValueError('Invalid global sample/stack counts')
            return dict(events=total,with_associated_stack=with_stack)
    return None
