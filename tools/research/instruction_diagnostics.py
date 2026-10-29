"""Validate bounded PSS RIP observations; counts are not CPU percentages."""

import _research_bootstrap  # Repository-relative imports for direct execution.
from collections import Counter
import math
from pathlib import Path
from thread_metadata import locate_module


def validate(snapshot, pid, executable, process_created, lifetimes):
    wanted = set(lifetimes)
    if not 1 <= len(wanted) <= 8 or len(wanted) != len(lifetimes):
        raise ValueError('Invalid requested lifetimes')
    if (snapshot.get('completed') is not True or snapshot.get('error') or
            snapshot.get('pid') != pid or snapshot.get('process_created_filetime') != process_created or
            Path(snapshot['executable']).resolve() != Path(executable).resolve()):
        raise ValueError('Capture completion or process identity differs')
    expected_cleanup = dict(marker_free_returncode=0, snapshot_free_returncode=0, process_handle_closed=True)
    if snapshot.get('cleanup_verified') is not True or snapshot.get('cleanup') != expected_cleanup:
        raise ValueError('Capture cleanup incomplete')
    if snapshot.get('capture_flags') != 0x180 or snapshot.get('context_flags') != 0x100003 or snapshot.get('capture_returncode') != 0:
        raise ValueError('Unexpected capture mechanism')
    for key in ('capture_seconds', 'elapsed_seconds'):
        value = snapshot[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid capture duration')
    if snapshot['capture_seconds'] > snapshot['elapsed_seconds']:
        raise ValueError('Capture duration exceeds helper duration')
    if snapshot['missing_requested_lifetimes']:
        raise ValueError('Requested thread lifetime missing')
    observed = set()
    for row in snapshot['threads']:
        identity = (row['tid'], row['created_filetime'])
        if identity in observed or identity not in wanted or row.get('error'):
            raise ValueError('Invalid observed lifetime or context')
        observed.add(identity)
        if row.get('context_flags', 0) & 0x100003 != 0x100003 or not 256 <= row['context_bytes'] <= 16384:
            raise ValueError('Missing control/integer context')
        rip = int(row['rip'], 16)
        if not 0 < rip < 2**64 or row.get('module') != locate_module(rip, snapshot['modules']):
            raise ValueError('RIP/module evidence disagrees')
        stamp = row['capture_filetime']
        if not isinstance(stamp, str) or not stamp.isascii() or not stamp.isdecimal() or not 0 < int(stamp) < 2**64:
            raise ValueError('Invalid capture FILETIME')
    if observed != wanted:
        raise ValueError('Selected lifetimes not captured exactly once')
    return snapshot


def summarize(samples, pid, executable, process_created, lifetimes):
    if not 1 <= len(samples) <= 120:
        raise ValueError('Requires 1..120 observations')
    counts = {key: Counter() for key in lifetimes}
    modules = None
    stamps = {}
    for sample in samples:
        validate(sample, pid, executable, process_created, lifetimes)
        if modules is not None and sample['modules'] != modules:
            raise ValueError('Module inventory changed between captures')
        modules = sample['modules']
        for row in sample['threads']:
            key = (row['tid'], row['created_filetime'])
            stamp = int(row['capture_filetime'])
            if key in stamps and stamp <= stamps[key]:
                raise ValueError('Capture FILETIMEs are not increasing')
            stamps[key] = stamp
            module = row['module']
            address = (module['name'], module['path'], module['offset']) if module else (None, None, row['rip'])
            counts[key][address] += 1
    return dict(observations=len(samples), threads=[dict(tid=key[0], created_filetime=key[1],
        addresses=[dict(module=name, path=path, offset_or_unmapped_rip=offset, observations=n)
                   for (name, path, offset), n in counts[key].most_common()]) for key in lifetimes],
        capture_seconds_sum=sum(s['capture_seconds'] for s in samples),
        helper_seconds_sum=sum(s['elapsed_seconds'] for s in samples),
        helper_seconds_max=max(s['elapsed_seconds'] for s in samples),
        scope='Discrete current user RIP observations, not stacks, time-weighted CPU percentages or exclusive function cost.')
