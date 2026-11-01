"""Own a cold original-game process and restore its reference-profile settings.

No process already running when this controller starts is stopped or adopted.
The profile journal remains recoverable if orchestration is interrupted.
"""
import asyncio
import base64
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import stat
import time
import uuid

import psutil

import launcher_clicker
from oracle_runner import OracleSession, execute_scenario, markdown_report, scenario_lock, write_json
from oracle_schema import validate_scenario
from probe import Client, ProbeError
from rekenshi_profile import ReKenshiProfile


SUPPORTED_REK_HASH = '58900f1678e4eef407fb19d12527fd8c1d3dbc5bc09903c088dc52a9134a04ee'
SQUAD_SIZE_KEY = b'squad size multiplier'
_DECIMAL = re.compile(rb'^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$')


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def settings_path(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise RuntimeError('Game-settings paths cannot contain links or reparse points')
    if path.exists() and not stat.S_ISREG(path.stat().st_mode):
        raise RuntimeError('Game-settings transaction requires a regular file')
    return path


def read_bounded(path, limit):
    with settings_path(path).open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise RuntimeError('Game-settings transaction file exceeds its size limit')
    return raw


def settings_target_hash(path):
    return hashlib.sha256(os.path.normcase(str(settings_path(path))).encode('utf-8')).hexdigest()


def preserve_game_settings(path, journal):
    """Persist rollback bytes before starting the game, including prior absence."""
    path, journal = settings_path(path), settings_path(journal)
    if journal.exists() and json.loads(read_bounded(journal, 2 * 1024 * 1024)).get('restore_required'):
        raise RuntimeError('An interrupted game-settings transaction requires restore-reference')
    raw = read_bounded(path, 1024 * 1024) if path.exists() else None
    record = dict(restore_required=True, existed=raw is not None,
                  bytes_base64=base64.b64encode(raw or b'').decode('ascii'),
                  sha256=hashlib.sha256(raw or b'').hexdigest(), target_sha256=settings_target_hash(path))
    temporary = journal.with_name(journal.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(record, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(journal)
    return raw


def squad_size_facts(raw):
    """Select the squad-size line from preserved settings bytes (docs/scene-setup.md).

    Exactly one matching line is required; none, several or an unparsable value raise.
    """
    lines = (raw or b'').split(b'\n')
    if lines[0].startswith(b'\xef\xbb\xbf'):
        lines[0] = lines[0][3:]
    matches = []
    for line in lines:
        if line.endswith(b'\r'):
            line = line[:-1]
        key, separator, value = line.partition(b'=')
        if separator and key.strip().lower() == SQUAD_SIZE_KEY:
            matches.append((line, value.strip()))
    if len(matches) != 1:
        raise RuntimeError('Preserved game settings need exactly one "Squad size multiplier=" line, found '
                           + str(len(matches)))
    line, value = matches[0]
    multiplier = float(value) if _DECIMAL.fullmatch(value) else None
    if multiplier is None or not math.isfinite(multiplier):
        raise RuntimeError('Preserved "Squad size multiplier=" line has no finite decimal value')
    try:
        text = line.decode('utf-8')
    except UnicodeError as exc:
        raise RuntimeError('Preserved "Squad size multiplier=" line is not UTF-8') from exc
    return dict(source='settings.cfg', multiplier=multiplier, line=text,
                sha256=hashlib.sha256(line).hexdigest(), path='settings.cfg')


def restore_game_settings(path, journal, process_state):
    def require_stopped():
        observed = process_state()
        if type(observed) is not dict or observed.get('running') is not False:
            raise RuntimeError('Game-settings restoration requires a verified stopped game')
    require_stopped()
    path, journal = settings_path(path), settings_path(journal)
    if not journal.exists():
        raise RuntimeError('Expected game-settings recovery journal is missing')
    record = json.loads(read_bounded(journal, 2 * 1024 * 1024))
    raw = base64.b64decode(record['bytes_base64'], validate=True)
    if (type(record['existed']) is not bool or len(raw) > 1024 * 1024
            or (not record['existed'] and raw)
            or record.get('target_sha256') != settings_target_hash(path)
            or hashlib.sha256(raw).hexdigest() != record['sha256']):
        raise RuntimeError('Game-settings recovery bytes are damaged')
    if record['existed']:
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            require_stopped()
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
        if path.read_bytes() != raw:
            raise RuntimeError('Game settings did not restore exactly')
    elif path.exists():
        require_stopped()
        path.unlink()
    record['restore_required'] = False
    write_json(journal, record)
    return True


class ReferenceGame:
    """Independent OS ownership observations, bound to a single Popen handle."""
    def __init__(self, cfg, output):
        self.cfg, self.output = cfg, Path(output)
        self.process = None
        self.identity = None
        self.instance = None
        self.client = Client(cfg.get('port', 47800), cfg.get('timeout', 10))
        # Opt-in external click of the launcher OK; without it the user clicks OK.
        self.launcher = (launcher_clicker.LauncherWatch(self.output / 'launcher', cfg['executable'],
                                                        timeout=cfg.get('startup_grace', 180))
                         if launcher_clicker.enabled(cfg) else None)

    def state(self):
        games = [p for p in psutil.process_iter(['name'])
                 if (p.info['name'] or '').lower().startswith('kenshi')
                 and (p.info['name'] or '').lower().endswith('.exe')]
        alive = self.process is not None and self.process.poll() is None
        if not games:
            if alive:
                raise RuntimeError('Owned game is alive but absent from the process inventory')
            return dict(running=False, owned=False)
        if (not alive or len(games) != 1 or games[0].pid != self.process.pid
                or games[0].create_time() != self.identity):
            return dict(running=True, owned=False)
        if Path(games[0].exe()).resolve() != Path(self.cfg['executable']).resolve():
            raise RuntimeError('Owned executable identity changed')
        return dict(running=True, owned=True, pid=self.process.pid,
                    instance_id=self.instance, started_at=self.identity)

    async def start(self, label):
        if self.state()['running']:
            raise RuntimeError('Close Kenshi before starting an original reference run')
        environment = dict(os.environ, KENSHI_PROBE_PORT=str(self.client.port),
                           KENSHI_ORACLE_OUTPUT=self.cfg['oracle_output'])
        Path(self.cfg['oracle_output']).mkdir(parents=True, exist_ok=True)
        with (self.output / (label + '.stdout.log')).open('wb') as stdout, \
                (self.output / (label + '.stderr.log')).open('wb') as stderr:
            self.process = subprocess.Popen(
                [self.cfg['executable'], *self.cfg.get('arguments', [])],
                cwd=self.cfg.get('working_directory'), env=environment,
                stdout=stdout, stderr=stderr)
        self.identity = psutil.Process(self.process.pid).create_time()
        self.instance = None
        if self.launcher is not None:
            self.launcher.start(self.process.pid, self.identity, label)
        ping = await self.wait_ping()
        if ping.get('process_id') != self.process.pid or not ping.get('instance_id'):
            raise RuntimeError('Probe is not the newly launched owned game')
        self.instance = ping['instance_id']
        if ping.get('game_version') not in ('1.0.65', '1.0.65 Steam'):
            raise RuntimeError('Original reference requires the observed Kenshi 1.0.65 build')
        if ping.get('rekenshi_settings_available') is not True:
            raise RuntimeError('Install the phase 2 probe with runtime RE_Kenshi verification')
        return ping

    async def wait_ping(self, *, ready=False):
        deadline = time.monotonic() + self.cfg.get('startup_grace', 180)
        last_error = None
        while time.monotonic() < deadline:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('Owned game exited during startup/load')
            try:
                ping = await self.client.call('ping')
                if (ping.get('process_id') == self.process.pid
                        and (not ready or (ping.get('world_ready') is True and ping.get('paused') is True))):
                    return ping
            except Exception as exc:
                last_error = exc
            await asyncio.sleep(1)
        raise RuntimeError('Owned game startup/load timed out: ' + str(last_error))

    async def stop(self):
        if self.launcher is not None and self.process is not None:
            self.launcher.stopped(self.process.pid)
        if self.process is None or self.process.poll() is not None:
            return
        observed = self.state()
        if not observed.get('owned'):
            raise RuntimeError('Game ownership cannot be verified; refusing termination')
        self.process.terminate()
        await asyncio.to_thread(self.process.wait, 30)
        self.instance = None

    async def settings_evidence(self):
        deadline = time.monotonic() + self.cfg.get('startup_grace', 180)
        while True:
            try:
                return await self.client.call('get_rekenshi_settings')
            except ProbeError as exc:
                if 'rekenshi_settings_unavailable' not in str(exc) or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(1)


async def run_original_reference(scenario, cfg, repeat=None):
    """Run with verified settings, then cold-verify the restored player profile."""
    validate_scenario(scenario)
    repetitions = scenario.get('repeat', 1) if repeat is None else repeat
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError('repeat must be an integer from 1 to 100')
    controls = None
    if cfg.get('reference_controls'):
        control_document = json.loads(Path(cfg['reference_controls']).read_text(encoding='utf-8'))
        if control_document.get('save') != scenario['save'] or control_document.get('restore_required') is not False:
            raise ValueError('Reference controls must belong to this save and a completed restoration')
        controls = control_document['controls']
    for key in ('rekenshi_config', 'rekenshi_module', 'executable', 'working_directory'):
        if not cfg.get(key):
            raise ValueError('Original reference configuration requires ' + key)
    launcher_clicker.enabled(cfg)
    module = Path(cfg['rekenshi_module']).resolve()
    if Path(cfg['rekenshi_config']).resolve() != (Path(cfg['working_directory']) / 'RE_Kenshi.ini').resolve():
        raise ValueError('The RE_Kenshi profile must belong to this game working directory')
    if file_hash(module) != SUPPORTED_REK_HASH:
        raise ValueError('RE_Kenshi DLL is not the audited 0.3.5 build')
    runtime = Path(cfg['runtime'])
    journal = runtime / 'rekenshi-profile.json'
    output = runtime / 'reference-lifecycle' / uuid.uuid4().hex
    output.mkdir(parents=True)
    game = ReferenceGame(cfg, output)
    profile = ReKenshiProfile(cfg['rekenshi_config'], journal, process_state=game.state,
        metadata=dict(kenshi_version='1.0.65', rekenshi_version='0.3.5',
                      rekenshi_sha256=SUPPORTED_REK_HASH, executable_sha256=file_hash(cfg['executable'])))
    lifecycle = dict(completed=False, initial_game_running=False, output=str(output))
    result = None
    captured = False
    settings = Path(cfg['working_directory']) / 'settings.cfg'
    settings_journal = runtime / 'reference-game-settings.json'
    settings_captured = False
    engine_facts = None

    def module_evidence(evidence, _expected):
        if Path(evidence.get('module_path', '')).resolve() != module or file_hash(module) != SUPPORTED_REK_HASH:
            raise RuntimeError('Runtime RE_Kenshi module does not match the audited file')
        return evidence

    with scenario_lock(runtime / 'reference-process'):
        if game.state()['running']:
            raise RuntimeError('Close Kenshi before applying the original reference profile')
        if journal.exists() and json.loads(journal.read_text(encoding='utf-8')).get('restore_required'):
            raise RuntimeError('An interrupted reference run requires restore-reference first')
        try:
            preserved = preserve_game_settings(settings, settings_journal)
            settings_captured = True
            if scenario.get('setup') is not None:
                # Scene setup needs the multiplier line the original reads; fail before launch.
                engine_facts = dict(squad_size=squad_size_facts(preserved))
                lifecycle['engine_facts'] = engine_facts
            profile.capture()
            captured = True
            profile.prepare()
            lifecycle['reference_start'] = await game.start('reference')
            evidence = await game.settings_evidence()
            profile.verify_effective(evidence, validator=module_evidence)
            lifecycle['initial_effective'] = profile.provenance()
            # A single mutation is issued. During cold asset loading only read-only
            # pings are retried; an uncertain load command is never replayed.
            lifecycle['cold_load'] = await game.client.call('load_save', name=scenario['save'],
                                                          lock_edge=False, pause_on_ready=True)
            await game.wait_ping(ready=True)
            setup = OracleSession(cfg, game.client)
            lifecycle['prepared_load'] = await setup.load(scenario['save'], lock_edge=False)
            await setup.call('set_game_speed', speed=1, preserve_pause=True)
            if controls is not None:
                lifecycle['camera_preparation'] = await setup.restore_controls(controls)
            result = await execute_scenario(scenario, cfg, repeat=repeat, client=game.client,
                                            reference_profile=profile,
                                            **({} if engine_facts is None else dict(engine_facts=engine_facts)))
        except BaseException as exc:
            lifecycle['error'] = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            cleanup_errors = []
            try:
                await game.stop()
                if captured:
                    profile.restore()
                    lifecycle['restoration_start'] = await game.start('restoration')
                    evidence = await game.settings_evidence()
                    profile.verify_restored_effective(evidence, validator=module_evidence)
            except BaseException as exc:
                cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
            finally:
                try:
                    await game.stop()
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
                try:
                    if captured:
                        # RE_Kenshi may rewrite the INI on initialization. The
                        # profile journal checks exact restoration after shutdown.
                        profile.restore(reapply=True)
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
                try:
                    if settings_captured:
                        lifecycle['game_settings_restored'] = restore_game_settings(
                            settings, settings_journal, game.state)
                except BaseException as exc:
                    cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
            if captured:
                lifecycle['reference_profile'] = profile.provenance()
            if getattr(game, 'launcher', None) is not None:
                # Receipts only: a refused or absent click never fails the run.
                lifecycle['launcher_click'] = await asyncio.to_thread(game.launcher.close)
            lifecycle['cleanup_errors'] = cleanup_errors
            lifecycle['owned_game_stopped'] = game.process is None or game.process.poll() is not None
            lifecycle['completed'] = result is not None and not cleanup_errors
            if settings_captured and lifecycle.get('game_settings_restored') is not True:
                lifecycle['completed'] = False
            write_json(output / 'report.json', lifecycle)
            if result:
                report_path = Path(result['report'])
                report = json.loads(report_path.read_text(encoding='utf-8'))
                report['reference_profile'] = deepcopy(lifecycle.get('reference_profile'))
                report['reference_lifecycle'] = str(output / 'report.json')
                if cleanup_errors:
                    report['status'] = 'failed'
                    report['reference_restoration_errors'] = cleanup_errors
                write_json(report_path, report)
                if 'scenario' in report:
                    (report_path.parent / 'report.md').write_text(markdown_report(report), encoding='utf-8')
            if cleanup_errors:
                raise RuntimeError('Reference-profile restoration failed; inspect ' + str(output / 'report.json'))
    return dict(result, reference_restored=True, reference_report=str(output / 'report.json'))


def restore_original_reference(cfg):
    """Recover exact profile bytes after a crash; requires every game stopped."""
    runtime = Path(cfg['runtime'])
    with scenario_lock(runtime / 'reference-process'):
        game = ReferenceGame(cfg, runtime)
        profile = ReKenshiProfile(cfg['rekenshi_config'], runtime / 'rekenshi-profile.json',
                                 process_state=game.state)
        result = profile.restore(reapply=True)
        result['game_settings_restored'] = restore_game_settings(
            Path(cfg['working_directory']) / 'settings.cfg', runtime / 'reference-game-settings.json', game.state)
        result['recovery_scope'] = 'files_only; runtime verification is separate'
        return result
