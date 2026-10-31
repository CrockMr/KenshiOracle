"""Accept Kenshi's own launcher dialog once per owned kenshi_x64.exe start, from outside the game.

Opt-in (`launcher_click: true`). Only a visible top-level dialog (class
#32770) of the owned process, titled "Kenshi" (resource caption) or
"Kenshi 1.0.65 - x64 (Newland)" (caption observed at runtime), whose single
enabled "OK" button has control id 1003, is clicked. Any doubt (process
identity changed, several candidates, another dialog of that process, a
missing or duplicate OK button, timeout) refuses without clicking; the
launcher then stays open for a manual click. Nothing is injected into the
game: the only message sent is BM_CLICK to the verified button.
"""
import json
import ntpath
import os
from pathlib import Path
import sys
import threading
import time
from datetime import datetime, timezone

DIALOG_CLASS = '#32770'
LAUNCHER_TITLES = ('Kenshi', 'Kenshi 1.0.65 - x64 (Newland)')
OK_ID = 1003
OK_TEXT = 'OK'
BM_CLICK = 0x00F5


def enabled(cfg):
    """Return the validated `launcher_click` switch; absent means disabled."""
    value = cfg.get('launcher_click', False)
    if type(value) is not bool:
        raise ValueError('launcher_click must be true or false')
    return value


def _same_exe(a, b):
    return ntpath.normcase(ntpath.normpath(str(a))) == ntpath.normcase(ntpath.normpath(str(b)))


def _utc():
    return datetime.now(timezone.utc).isoformat()


def accept_launcher(api, identity, *, pid, create_time, exe, timeout=120.0, poll=0.2, close_wait=10.0,
                    now=time.monotonic, sleep=time.sleep, wall=_utc, stop=None):
    """Watch one owned process and click its launcher OK at most once; return a JSON-ready receipt."""
    start = now()
    receipt = dict(pid=pid, create_time=create_time, exe=str(exe), started_utc=wall(), timeout_seconds=timeout,
                   expected=dict(window_class=DIALOG_CLASS, titles=list(LAUNCHER_TITLES),
                                 button_id=OK_ID, button_text=OK_TEXT),
                   window=None, clicked_utc=None, result=None)

    def done(result, **extra):
        receipt.update(result=result, finished_utc=wall(), elapsed_seconds=round(now() - start, 3), **extra)
        return receipt

    while True:
        if stop is not None and stop.is_set():
            return done('stopped')
        current = identity(pid)
        if current is None:
            return done('process_exited')
        if current['create_time'] != create_time or not _same_exe(current['exe'], exe):
            return done('refused_process_mismatch', observed=current)
        dialogs = [h for h in api.top_windows()
                   if api.window_pid(h) == pid and api.is_visible(h) and api.class_name(h) == DIALOG_CLASS]
        if dialogs:
            seen = [dict(hwnd=hex(h), title=api.title(h)) for h in dialogs]
            if any(api.title(h) not in LAUNCHER_TITLES for h in dialogs):
                return done('refused_unexpected_dialog', dialogs=seen)
            if len(dialogs) > 1:
                return done('refused_ambiguous', dialogs=seen)
            hwnd = dialogs[0]
            buttons = [c for c in api.children(hwnd) if api.child_class(c) == 'Button' and api.child_id(c) == OK_ID]
            ok = [c for c in buttons if api.child_text(c) == OK_TEXT and api.child_visible(c) and api.child_enabled(c)]
            if len(buttons) != 1 or len(ok) != 1:
                return done('refused_no_ok_button', dialogs=seen,
                            buttons=[dict(hwnd=hex(c), text=api.child_text(c)) for c in buttons])
            button = ok[0]
            receipt['window'] = dict(hwnd=hex(hwnd), title=api.title(hwnd), button_hwnd=hex(button),
                                     button_id=OK_ID, button_text=OK_TEXT, **{'class': DIALOG_CLASS})
            receipt.update(clicked_utc=wall(), clicked_after_seconds=round(now() - start, 3))
            receipt['click_delivered'] = bool(api.click(button))
            # One click only: wait for the dialog to close, never click again.
            limit = now() + close_wait
            while api.is_window(hwnd) and now() < limit:
                sleep(poll)
            return done('clicked', window_closed_after_click=not api.is_window(hwnd))
        if now() - start >= timeout:
            return done('timeout_no_launcher')
        sleep(poll)


def auto_ok(receipt):
    """The verified OK button was clicked once and the launcher closed."""
    return (isinstance(receipt, dict) and receipt.get('result') == 'clicked'
            and receipt.get('click_delivered') is True and receipt.get('window_closed_after_click') is True)


def write_receipt(path, receipt):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return path


class Win32:
    """Minimal user32 binding: reads windows; the only message sent is BM_CLICK."""
    def __init__(self):
        if os.name != 'nt':
            raise OSError('launcher_click requires Windows')
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        # Explicit prototypes keep 64-bit handles intact. The offline tests use a fake api instead.
        HWND, BOOL = wintypes.HWND, wintypes.BOOL
        signatures = {
            'EnumWindows': ([self.proc, wintypes.LPARAM], BOOL),
            'EnumChildWindows': ([HWND, self.proc, wintypes.LPARAM], BOOL),
            'GetWindowThreadProcessId': ([HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            'IsWindowVisible': ([HWND], BOOL),
            'IsWindow': ([HWND], BOOL),
            'IsWindowEnabled': ([HWND], BOOL),
            'GetClassNameW': ([HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetWindowTextW': ([HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetDlgCtrlID': ([HWND], ctypes.c_int),
        }
        for name, (argtypes, restype) in signatures.items():
            function = getattr(self.user32, name)
            function.argtypes, function.restype = argtypes, restype
        self.user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                                    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        self.user32.SendMessageTimeoutW.restype = ctypes.c_size_t

    def _enum(self, parent=None):
        found = []
        callback = self.proc(lambda h, _: found.append(h) or True)
        if parent is None:
            self.user32.EnumWindows(callback, 0)
        else:
            self.user32.EnumChildWindows(parent, callback, 0)
        return found

    def top_windows(self):
        return self._enum()

    def children(self, hwnd):
        return self._enum(hwnd)

    def window_pid(self, hwnd):
        pid = self.wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(pid))
        return pid.value

    def is_visible(self, hwnd):
        return bool(self.user32.IsWindowVisible(hwnd))

    def is_window(self, hwnd):
        return bool(self.user32.IsWindow(hwnd))

    def class_name(self, hwnd):
        buffer = self.ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value

    def title(self, hwnd):
        buffer = self.ctypes.create_unicode_buffer(512)
        self.user32.GetWindowTextW(hwnd, buffer, 512)
        return buffer.value

    child_class, child_text, child_visible = class_name, title, is_visible

    def child_id(self, hwnd):
        return self.user32.GetDlgCtrlID(hwnd)

    def child_enabled(self, hwnd):
        return bool(self.user32.IsWindowEnabled(hwnd))

    def click(self, hwnd):
        result = self.ctypes.c_size_t()
        # SMTO_ABORTIFHUNG, 5 s: a hung launcher cannot block the watcher.
        return bool(self.user32.SendMessageTimeoutW(hwnd, BM_CLICK, 0, 0, 0x0002, 5000, self.ctypes.byref(result)))


def process_identity(pid):
    import psutil
    try:
        process = psutil.Process(pid)
        if not process.is_running():
            return None
        return dict(create_time=process.create_time(), exe=process.exe())
    except psutil.Error:
        return None


def _stderr(message):
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


class LauncherWatch:
    """One daemon accept_launcher thread per owned start; one JSON receipt per start in `folder`."""
    def __init__(self, folder, exe, *, timeout=120.0, api_factory=None, identity=None,
                 thread_factory=threading.Thread, event_factory=threading.Event, accept=None, log=_stderr):
        self.folder, self.exe, self.timeout = Path(folder), exe, timeout
        self.api_factory = api_factory or Win32
        self.identity = identity or process_identity
        self.thread_factory, self.event_factory = thread_factory, event_factory
        self.accept = accept or accept_launcher
        self.log = log
        self.rows, self.threads = [], []
        self.lock = threading.Lock()

    def _path(self, stage):
        used = {row['path'] for row in self.rows}
        path, n = self.folder / (stage + '.json'), 2
        while str(path) in used or path.exists():
            path, n = self.folder / (stage + '-' + str(n) + '.json'), n + 1
        return path

    def start(self, pid, create_time, stage):
        """Watch `pid`; `create_time=None` looks it up (an exited process records `process_exited`)."""
        with self.lock:
            if create_time is None:
                current = self.identity(pid)
                create_time = current['create_time'] if current else None
            event, path = self.event_factory(), self._path(stage)
            row = dict(stage=stage, pid=pid, create_time=create_time, path=str(path), receipt=None, event=event)
            self.rows.append(row)

        def work():
            if create_time is None:
                receipt = dict(pid=pid, create_time=None, exe=str(self.exe), window=None, clicked_utc=None,
                               result='process_exited')
            else:
                try:
                    receipt = self.accept(self.api_factory(), self.identity, pid=pid, create_time=create_time,
                                          exe=self.exe, timeout=self.timeout, stop=event)
                except Exception as exc:
                    receipt = dict(pid=pid, create_time=create_time, exe=str(self.exe), window=None,
                                   clicked_utc=None, result='error', error=type(exc).__name__ + ': ' + str(exc))
            try:
                write_receipt(path, receipt)
            except OSError as exc:
                row['write_error'] = str(exc)
            row['receipt'] = receipt
            if auto_ok(receipt):
                self.log('Launcher OK clicked for ' + stage + ' (pid ' + str(pid) + ')')
            else:
                self.log('Launcher not clicked for ' + stage + ': ' + str(receipt.get('result'))
                         + '; click OK manually if the launcher is still open')

        thread = self.thread_factory(target=work, daemon=True, name='launcher-click-' + stage)
        self.threads.append(thread)
        thread.start()
        return row

    def stopped(self, pid):
        for row in self.rows:
            if row['pid'] == pid:
                row['event'].set()

    def close(self, join_timeout=20.0):
        for row in self.rows:
            row['event'].set()
        for row, thread in zip(self.rows, self.threads):
            thread.join(join_timeout)
            if thread.is_alive():
                row['unfinished'] = True
        return self.receipts()

    def receipts(self):
        return [{key: value for key, value in row.items() if key != 'event'} for row in self.rows]
