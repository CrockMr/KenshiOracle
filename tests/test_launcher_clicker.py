"""Launcher OK clicker with a fake Win32 layer: nothing real is enumerated or clicked."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import launcher_clicker as lc
import original_reference as reference

EXE = 'synthetic/kenshi_x64.exe'
RUNTIME_TITLE = 'Kenshi 1.0.65 - x64 (Newland)'


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class FakeWin32:
    """windows: hwnd -> dict(pid, cls, title, visible, children, appears_at, closes_on_click)."""
    def __init__(self, clock, windows):
        self.clock, self.windows, self.clicks, self.closed = clock, windows, [], set()

    def _live(self, h):
        return h not in self.closed and self.clock.now() >= self.windows[h].get('appears_at', 0)

    def top_windows(self):
        return [h for h in self.windows if self._live(h)]

    def window_pid(self, h):
        return self.windows[h]['pid']

    def is_visible(self, h):
        return self.windows[h].get('visible', True)

    def class_name(self, h):
        return self.windows[h]['cls']

    def title(self, h):
        return self.windows[h]['title']

    def is_window(self, h):
        return self._live(h)

    def children(self, h):
        return [c['hwnd'] for c in self.windows[h].get('children', [])]

    def _child(self, c):
        return next(x for w in self.windows.values() for x in w.get('children', []) if x['hwnd'] == c)

    def child_class(self, c):
        return self._child(c)['cls']

    def child_id(self, c):
        return self._child(c)['id']

    def child_text(self, c):
        return self._child(c)['text']

    def child_visible(self, c):
        return self._child(c).get('visible', True)

    def child_enabled(self, c):
        return self._child(c).get('enabled', True)

    def click(self, c):
        self.clicks.append(c)
        for h, w in self.windows.items():
            if any(x['hwnd'] == c for x in w.get('children', [])) and w.get('closes_on_click', True):
                self.closed.add(h)
        return True


class FakeProcess:
    def __init__(self, clock, pid=100, created=1.5, exe=EXE, exits_at=None, replaced_at=None):
        self.clock, self.pid, self.created, self.exe = clock, pid, created, exe
        self.exits_at, self.replaced_at = exits_at, replaced_at

    def identity(self, pid):
        if pid != self.pid or (self.exits_at is not None and self.clock.now() >= self.exits_at):
            return None
        reused = self.replaced_at is not None and self.clock.now() >= self.replaced_at
        return dict(create_time=self.created + (1 if reused else 0), exe=self.exe)


def launcher(hwnd=1, pid=100, title='Kenshi', cls='#32770', button=None, **extra):
    button = button or dict(hwnd=hwnd * 10 + 1, cls='Button', id=1003, text='OK')
    others = [dict(hwnd=hwnd * 10 + 2, cls='Button', id=1004, text='Cancel')]
    return dict(pid=pid, cls=cls, title=title, children=[button, *others], **extra)


def run(windows, process=None, timeout=120.0, **kw):
    clock = FakeClock()
    api = FakeWin32(clock, windows)
    proc = process(clock) if process else FakeProcess(clock)
    receipt = lc.accept_launcher(api, proc.identity, pid=100, create_time=1.5, exe=EXE, timeout=timeout,
                                 now=clock.now, sleep=clock.sleep, wall=lambda: '2026-10-31T00:00:00+00:00', **kw)
    json.dumps(receipt)
    return receipt, api


@pytest.mark.parametrize('title', ['Kenshi', RUNTIME_TITLE])
def test_accepts_owned_launcher_once_and_records_window(title):
    receipt, api = run({1: launcher(title=title, appears_at=3.0)})
    assert receipt['result'] == 'clicked' and api.clicks == [11] and lc.auto_ok(receipt)
    window = receipt['window']
    assert (window['class'], window['title'], window['button_id'], window['button_text']) == ('#32770', title, 1003, 'OK')
    assert receipt['clicked_after_seconds'] >= 3.0 and receipt['window_closed_after_click'] is True


def test_windows_of_other_processes_are_ignored():
    receipt, api = run({1: launcher(pid=999), 2: launcher(hwnd=2, appears_at=1.0)})
    assert receipt['result'] == 'clicked' and api.clicks == [21]


def test_non_dialog_game_window_is_not_a_candidate():
    game = dict(pid=100, cls='OgreD3D11Wnd', title='Kenshi', children=[])
    receipt, api = run({1: game, 2: launcher(hwnd=2, appears_at=2.0)})
    assert receipt['result'] == 'clicked' and api.clicks == [21]


@pytest.mark.parametrize('title', ['Kenshi - Error', 'Microsoft Visual C++ Runtime Library',
                                   'Kenshi 1.0.64 - x64 (Newland)', RUNTIME_TITLE + ' ', 'kenshi'])
def test_other_dialogs_of_owned_process_are_refused(title):
    receipt, api = run({1: launcher(title=title)})
    assert receipt['result'] == 'refused_unexpected_dialog' and api.clicks == []


def test_two_candidate_launchers_are_refused():
    receipt, api = run({1: launcher(), 2: launcher(hwnd=2)})
    assert receipt['result'] == 'refused_ambiguous' and api.clicks == []


@pytest.mark.parametrize('button', [
    dict(hwnd=11, cls='Button', id=1, text='OK'),
    dict(hwnd=11, cls='Button', id=1003, text='Play'),
    dict(hwnd=11, cls='Static', id=1003, text='OK'),
    dict(hwnd=11, cls='Button', id=1003, text='OK', enabled=False),
    dict(hwnd=11, cls='Button', id=1003, text='OK', visible=False),
])
def test_wrong_hidden_or_disabled_button_is_refused(button):
    receipt, api = run({1: launcher(button=button)}, timeout=3.0)
    assert receipt['result'] == 'refused_no_ok_button' and api.clicks == []


def test_duplicate_ok_button_is_refused():
    window = launcher()
    window['children'].append(dict(hwnd=19, cls='Button', id=1003, text='OK'))
    receipt, api = run({1: window})
    assert receipt['result'] == 'refused_no_ok_button' and api.clicks == []


@pytest.mark.parametrize('process', [
    lambda c: FakeProcess(c, exe='other/kenshi_x64.exe'),
    lambda c: FakeProcess(c, replaced_at=2.0),
])
def test_pid_identity_mismatch_is_refused(process):
    receipt, api = run({1: launcher(appears_at=5.0)}, process=process)
    assert receipt['result'] == 'refused_process_mismatch' and api.clicks == []


def test_process_exit_ends_the_watch():
    receipt, api = run({1: launcher(appears_at=50.0)}, process=lambda c: FakeProcess(c, exits_at=4.0))
    assert receipt['result'] == 'process_exited' and api.clicks == []


def test_timeout_without_launcher_does_not_click():
    receipt, api = run({}, timeout=5.0)
    assert receipt['result'] == 'timeout_no_launcher' and api.clicks == [] and not lc.auto_ok(receipt)


def test_stop_ends_the_watch_without_click():
    receipt, api = run({1: launcher(appears_at=10.0)}, stop=SimpleNamespace(is_set=lambda: True))
    assert receipt['result'] == 'stopped' and api.clicks == []


def test_launcher_that_stays_open_is_never_clicked_twice():
    receipt, api = run({1: launcher(closes_on_click=False)}, close_wait=2.0)
    assert api.clicks == [11] and receipt['window_closed_after_click'] is False and not lc.auto_ok(receipt)


@pytest.mark.parametrize('value', ['true', 1, None])
def test_switch_must_be_boolean(value):
    with pytest.raises(ValueError):
        lc.enabled(dict(launcher_click=value))
    assert lc.enabled({}) is False and lc.enabled(dict(launcher_click=True)) is True


@pytest.mark.skipif(os.name == 'nt', reason='non-Windows guard')
def test_win32_binding_refuses_outside_windows():
    with pytest.raises(OSError):
        lc.Win32()


class SyncThread:
    def __init__(self, target, daemon, name):
        self.target = target

    def start(self):
        self.target()

    def join(self, timeout=None):
        pass

    def is_alive(self):
        return False


def sync_watch(tmp_path, windows, process=None):
    clock = FakeClock()
    api = FakeWin32(clock, windows)
    proc = (process or FakeProcess)(clock)
    logs = []

    def accept(api_, identity, **kw):
        return lc.accept_launcher(api_, identity, now=clock.now, sleep=clock.sleep, **kw)
    watch = lc.LauncherWatch(tmp_path / 'launcher', EXE, api_factory=lambda: api, identity=proc.identity,
                             thread_factory=SyncThread, accept=accept, log=logs.append)
    return watch, api, logs


def test_watch_writes_one_receipt_per_start(tmp_path):
    watch, api, logs = sync_watch(tmp_path, {1: launcher(title=RUNTIME_TITLE)})
    watch.start(100, 1.5, 'reference')
    watch.start(100, 1.5, 'reference')
    rows = watch.close()
    assert api.clicks == [11]
    assert [Path(row['path']).name for row in rows] == ['reference.json', 'reference-2.json']
    saved = json.loads((tmp_path / 'launcher' / 'reference.json').read_text(encoding='utf-8'))
    assert saved['result'] == 'clicked' and all('event' not in row for row in rows)
    assert logs[0].startswith('Launcher OK clicked') and 'manually' in logs[1]


def test_watch_records_exited_process_and_api_errors(tmp_path):
    watch, _, _ = sync_watch(tmp_path, {})
    watch.start(555, None, 'gone')
    watch.api_factory = lambda: (_ for _ in ()).throw(OSError('no desktop'))
    watch.start(100, 1.5, 'broken')
    gone, broken = (row['receipt'] for row in watch.close())
    assert gone['result'] == 'process_exited'
    assert broken['result'] == 'error' and 'no desktop' in broken['error']


def test_stopped_only_stops_that_pid(tmp_path):
    watch = lc.LauncherWatch(tmp_path / 'launcher', EXE, thread_factory=lambda **kw: SimpleNamespace(
        start=lambda: None, join=lambda t: None, is_alive=lambda: True))
    watch.start(100, 1.5, 'a')
    watch.start(200, 2.5, 'b')
    watch.stopped(200)
    assert [row['event'].is_set() for row in watch.rows] == [False, True]
    assert all(row['unfinished'] for row in watch.close(join_timeout=0))


def test_reference_game_starts_and_stops_watch_only_when_enabled(tmp_path, monkeypatch):
    calls = []

    class Recorder:
        def __init__(self, folder, exe, timeout):
            calls.append(('init', Path(folder).name, exe, timeout))

        def start(self, pid, create_time, stage):
            calls.append(('start', pid, create_time, stage))

        def stopped(self, pid):
            calls.append(('stopped', pid))

    monkeypatch.setattr(lc, 'LauncherWatch', Recorder)
    assert reference.ReferenceGame(dict(executable=EXE), tmp_path).launcher is None
    game = reference.ReferenceGame(dict(executable=EXE, launcher_click=True, startup_grace=5), tmp_path)
    process = SimpleNamespace(pid=4242, poll=lambda: 0)
    monkeypatch.setattr(reference.subprocess, 'Popen', lambda *a, **kw: process)
    monkeypatch.setattr(reference.psutil, 'Process', lambda pid: SimpleNamespace(create_time=lambda: 7.5))
    monkeypatch.setattr(game, 'state', lambda: dict(running=False))
    cfg = dict(executable=EXE, launcher_click=True, oracle_output=str(tmp_path / 'dumps'))
    game.cfg = cfg

    async def ping(**kw):
        raise RuntimeError('synthetic: no probe')
    monkeypatch.setattr(game, 'wait_ping', ping)
    with pytest.raises(RuntimeError):
        asyncio.run(game.start('reference'))
    asyncio.run(game.stop())
    assert calls == [('init', 'launcher', EXE, 5), ('start', 4242, 7.5, 'reference'), ('stopped', 4242)]


def test_reference_rejects_invalid_switch_before_any_transaction(tmp_path):
    cfg = dict(rekenshi_config='x', rekenshi_module='x', executable='x', working_directory='x',
               runtime=str(tmp_path / 'runtime'), launcher_click='yes')
    scenario = dict(schema_version='0.1', name='s', save='s', speed=1, repeat=1, actions=[],
                    checkpoints=[dict(at=0, name='initial')])
    with pytest.raises(ValueError, match='launcher_click'):
        asyncio.run(reference.run_original_reference(scenario, cfg, repeat=1))
    assert not (tmp_path / 'runtime').exists()


def test_watchdog_watches_each_start_and_meitou_refuses_switch(tmp_path, monkeypatch):
    from launcher.watchdog import Watchdog
    from launcher.meitou_watchdog import launch_config
    starts, stops = [], []
    monkeypatch.setattr(lc.LauncherWatch, 'start', lambda self, pid, created, stage: starts.append((pid, created, stage)))
    monkeypatch.setattr(lc.LauncherWatch, 'stopped', lambda self, pid: stops.append(pid))
    process = SimpleNamespace(pid=31, poll=lambda: None, kill=lambda: None, wait=lambda timeout: 0)
    cfg = dict(executable=EXE, runtime=str(tmp_path / 'runtime'), launcher_click=True)
    dog = Watchdog(cfg, spawn=lambda *a, **kw: process)
    dog.start()
    dog.stop()
    assert starts == [(31, None, 'watchdog')] and stops == [31]
    assert Watchdog(dict(cfg, launcher_click=False), spawn=lambda *a, **kw: process).launcher is None
    with pytest.raises(ValueError, match='launcher_click'):
        launch_config(dict(target='meitou', launcher_click=True, oracle_output=str(tmp_path)))
