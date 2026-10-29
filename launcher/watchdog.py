import argparse
import asyncio
import json
import os
import shutil
import stat
import subprocess
import time
import msvcrt
import sys
from datetime import datetime, timezone
from pathlib import Path
from probe import Client, ProbeError, config


def warn(message):
    # Diagnostics cannot become another reason to stop supervision when the
    # archive or status filesystem is already failing.
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


class Watchdog:
    def __init__(self, cfg, spawn=subprocess.Popen, clock=time.monotonic, wall_clock=time.time):
        self.cfg, self.spawn, self.clock = cfg, spawn, clock
        self.wall_clock = wall_clock
        self.process = None
        self.started = self.last_progress = clock()
        self.frame = None
        self.heartbeat = None
        self.awaiting_gameplay = False
        self.loading_since = None
        self.autoload_requested = False
        self.autoload_error = None
        self.restart_ack = None
        self.reason = None
        self.publication_failures = 0
        self.publication_error = None
        self.archive_path = None
        self.archive_errors = []
        self.restart_request_error = None
        self.restart_request_failures = 0
        self.runtime = Path(cfg['runtime'])
        self.runtime.mkdir(parents=True, exist_ok=True)

    def publish(self):
        state = dict(running=self.process is not None and self.process.poll() is None,
                     pid=self.process.pid if self.process else None, updated_at=time.time(),
                     heartbeat=self.heartbeat, frame=self.frame, restart_ack=self.restart_ack,
                     reason=self.reason, awaiting_gameplay=self.awaiting_gameplay,
                     loading=self.loading_since is not None, autoload_requested=self.autoload_requested,
                     autoload_error=self.autoload_error,
                     state_publication_failures=self.publication_failures,
                     archive_path=self.archive_path, archive_errors=self.archive_errors,
                     restart_request_error=self.restart_request_error,
                     restart_request_failures=self.restart_request_failures)
        temp = self.runtime / 'state.tmp'
        for attempt in range(4):
            try:
                temp.write_text(json.dumps(state), encoding='utf-8')
                temp.replace(self.runtime / 'state.json')
                self.publication_error = None
                return True
            except OSError as exc:
                # A Windows reader/AV may briefly deny replacement. Status loss
                # must not unwind run() and kill the otherwise healthy game.
                if isinstance(exc, PermissionError) and attempt < 3:
                    time.sleep(.025)
                    continue
                self.publication_failures += 1
                message = str(exc)
                if message != self.publication_error:
                    warn('Watchdog state publication failed; supervision continues: '+message)
                self.publication_error = message
                return False

    def expired(self):
        deadline = self.cfg.get('session_until')
        return deadline is not None and self.wall_clock() >= deadline

    def start(self):
        exe = Path(self.cfg['executable'])
        environment = dict(os.environ)
        environment['KENSHI_PROBE_PORT'] = str(self.cfg.get('port', 47800))
        if self.cfg.get('oracle_output'):
            output = Path(self.cfg['oracle_output']).resolve()
            output.mkdir(parents=True, exist_ok=True)
            environment['KENSHI_ORACLE_OUTPUT'] = str(output)
        self.process = self.spawn([str(exe), *self.cfg.get('arguments', [])],
                                  cwd=self.cfg.get('working_directory', str(exe.parent)),
                                  env=environment)
        self.started = self.last_progress = self.clock()
        self.frame = self.heartbeat = None
        self.awaiting_gameplay = False
        self.loading_since = None
        self.autoload_requested = False
        self.autoload_error = None
        self.publish()

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)

    def archive(self, reason):
        target = Path(self.cfg['crashes']) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        self.archive_path = str(target)
        self.archive_errors = []

        def failed(operation, path, exc):
            self.archive_errors.append(dict(operation=operation, path=str(path), message=str(exc)))
            warn('Watchdog crash archive failed ('+operation+', '+str(path)+'): '+str(exc))

        # Evidence collection is best effort: a locked log or disappearing dump
        # must not prevent restarting the owned game. Keep any successful copies
        # and expose failures in state.json as well as stderr, without I/O retries.
        try:
            target.mkdir(parents=True)
        except OSError as exc:
            failed('create_directory', target, exc)
            return
        try:
            (target / 'reason.txt').write_text(reason, encoding='utf-8')
        except OSError as exc:
            failed('write_reason', target / 'reason.txt', exc)
        log = Path(self.cfg['log'])
        try:
            log_status = log.stat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            failed('stat_log', log, exc)
        else:
            try:
                if stat.S_ISREG(log_status.st_mode):
                    shutil.copy2(log, target / log.name)
            except OSError as exc:
                failed('copy_log', log, exc)
        dump_directory = Path(self.cfg['dump_directory'])
        try:
            for dump in dump_directory.iterdir():
                if dump.suffix.lower() != '.dmp':
                    continue
                try:
                    recent = dump.stat().st_mtime >= time.time() - (self.clock() - self.started) - 5
                except OSError as exc:
                    failed('stat_dump', dump, exc)
                    continue
                if not recent:
                    continue
                try:
                    shutil.copy2(dump, target / dump.name)
                except OSError as exc:
                    failed('copy_dump', dump, exc)
        except OSError as exc:
            failed('list_dumps', dump_directory, exc)

    def failure(self):
        if self.process.poll() is not None:
            return 'process_exit'
        if self.clock() - self.started < self.cfg.get('startup_grace', 120):
            return None
        if self.loading_since is not None and self.clock() - self.loading_since < self.cfg.get('loading_timeout', 120):
            return None
        if not self.awaiting_gameplay and self.clock() - self.last_progress > self.cfg.get('heartbeat_timeout', 30):
            return 'heartbeat_timeout'

    def _restart_request_failed(self, operation, exc):
        self.restart_request_failures += 1
        self.restart_request_error = dict(operation=operation,
            path=str(self.runtime/'restart.request'), message=str(exc))
        warn('Watchdog restart request failed ('+operation+'): '+str(exc))

    def _read_restart_request(self):
        request = self.runtime/'restart.request'
        try:
            if not request.exists():
                self.restart_request_error = None
                return None
            # MCP sends a UUID token, never a command. Bound even a corrupt or
            # concurrently written file, and do not turn read errors into exits.
            with request.open('rb') as stream:
                data = stream.read(129)
            token = data.decode('ascii')
            if not 1 <= len(data) <= 128 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError('restart token must contain 1..128 printable ASCII bytes without spaces')
        except (OSError, UnicodeError, ValueError) as exc:
            self._restart_request_failed('read_request', exc)
            return None
        self.restart_request_error = None
        return token

    def _consume_restart_request(self, token):
        # Another MCP caller may already have published a newer token. Consume
        # only the token we just acknowledged; leave a different request intact.
        if self._read_restart_request() != token:
            return False
        try:
            (self.runtime/'restart.request').unlink()
        except OSError as exc:
            self._restart_request_failed('consume_request', exc)
            return False
        self.restart_request_error = None
        return True

    async def step(self):
        if self.expired():
            return
        try:
            result = await Client(self.cfg.get('port', 47800), min(1, self.cfg.get('timeout', 10))).call('heartbeat')
            frame = result.get('service_frame') or result['frame']
            if result.get('loading'):
                if self.loading_since is None:
                    self.loading_since = self.clock()
            else:
                self.loading_since = None
            if not self.expired() and self.cfg.get('startup_save') and not self.autoload_requested and result.get('service_frame') and not result.get('loading'):
                self.autoload_requested = True
                try:
                    await Client(self.cfg.get('port', 47800), self.cfg.get('timeout', 10)).call('load_save', name=self.cfg['startup_save'])
                    self.loading_since = self.clock()
                except ProbeError as exc:
                    # A timed-out mutation may have started: never retry it automatically.
                    self.autoload_error = str(exc)
            # A responsive plugin with no main-loop tick yet is at the launcher/menu.
            self.awaiting_gameplay = frame == 0
            if frame != self.frame:
                self.frame = frame
                self.last_progress = self.clock()
                self.heartbeat = dict(received_at=time.time(), timestamp_ms=result.get('service_timestamp_ms') or result['timestamp_ms'],
                                      game_frame=result['frame'], source='render' if result.get('service_frame') else 'game')
        except (ProbeError, KeyError):
            self.awaiting_gameplay = False
        token = self._read_restart_request()
        if token is not None and token == self.restart_ack:
            # A failed unlink must not turn one request into an endless restart
            # loop. Retry consumption once per step while still checking health.
            self._consume_restart_request(token)
            token = None
        reason = 'requested' if token else self.failure()
        if self.expired():
            return
        if reason:
            self.stop()
            self.archive(reason)
            self.reason = reason
            self.publish()
            await asyncio.sleep(self.cfg.get('restart_delay', 5))
            if self.expired():
                self.publish()
                return
            self.start()
            if token:
                self.restart_ack = token
                self._consume_restart_request(token)
        self.publish()

    async def run(self):
        if self.expired():
            self.reason = 'session_deadline'
            self.publish()
            return
        self.start()
        try:
            while not self.expired():
                await self.step()
                await asyncio.sleep(1)
        finally:
            if self.expired():
                self.reason = 'session_deadline'
            self.stop()
            self.publish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    args = parser.parse_args()
    cfg = config(args.config)
    runtime = Path(cfg['runtime'])
    runtime.mkdir(parents=True, exist_ok=True)
    # Keep this file handle open for the process lifetime. Windows releases the lock on exit.
    with (runtime / 'watchdog.lock').open('a+b') as ownership:
        ownership.seek(0)
        if not ownership.read(1):
            ownership.write(b'0')
            ownership.flush()
        ownership.seek(0)
        try:
            msvcrt.locking(ownership.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit('Un chien de garde utilise déjà ce dossier runtime')
        asyncio.run(Watchdog(cfg).run())
