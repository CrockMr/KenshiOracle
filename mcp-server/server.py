
from research_support import enable_research
enable_research()
import asyncio
import json
import math
import os
import re
import time
import uuid
from collections import deque
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from probe import Client, ProbeError, config, read_runtime_state
from oracle_runner import OracleSession, run_scenario_file, restore_interrupted_scenario, restoration_reference
from oracle_schema import validate_scenario
from oracle_targets import target_config
from oracle_identity import validate_saved_handles, validate_origin_fingerprint, validate_origin_token

mcp = FastMCP('KenshiProbe')


def settings():
    return config(os.environ.get('KENSHI_PROBE_CONFIG', 'config.json'))


def target_settings(target='original'):
    return dict(target_config(settings(), target), target=target)


async def call(command, _target='original', **params):
    c = target_settings(_target)
    return await Client(c.get('port', 47800), c.get('timeout', 10)).call(command, **params)


async def target_call(command, target, **params):
    if target == 'original':
        return await call(command, **params)
    return await call(command, _target=target, **params)


@mcp.tool()
async def heartbeat(target: str = 'original') -> dict:
    """Read the latest published heartbeat, including at the menu; frame=0 before the first game."""
    return await target_call('heartbeat', target)


@mcp.tool()
async def ping(target: str = 'original') -> dict:
    """Check that the main thread responds and return version information."""
    return await target_call('ping', target)


@mcp.tool()
async def get_frame_stats(n: int = 300, detail: str = 'aggregates') -> dict:
    """Durations of the last N frames and system aggregates. detail='aggregates' explicitly omits individual rows to preserve the observation window; full retains them."""
    if type(n) is not int or not 1 <= n <= 3600:
        raise ValueError('n doit être entre 1 et 3600')
    if type(detail) is not str or detail not in ('full','aggregates'):
        raise ValueError('detail doit être full ou aggregates')
    return await call('get_frame_stats', n=n, detail=detail)


@mcp.tool()
async def pause(paused: bool = True, target: str = 'original') -> dict:
    """Enable or disable pause through GameWorld on the main thread."""
    return await target_call('pause', target, paused=paused)


@mcp.tool()
async def set_game_speed(speed: float = 1, preserve_pause: bool = False, target: str = 'original') -> dict:
    """Set speed from 0 to 5. preserve_pause requires a positive speed and retains pause in the same native command. The default follows SDK behavior, which unpauses for a positive speed. Reread the returned state."""
    if not 0 <= speed <= 5:
        raise ValueError('speed doit être entre 0 et 5')
    if not isinstance(preserve_pause, bool):
        raise ValueError('preserve_pause doit être booléen')
    if preserve_pause and speed == 0:
        raise ValueError('preserve_pause exige une vitesse strictement positive ; utiliser pause pour zéro')
    if preserve_pause:
        return await target_call('set_game_speed', target, speed=speed, preserve_pause=True)
    return await target_call('set_game_speed', target, speed=speed)


@mcp.tool()
async def list_characters(limit: int = 100, details: bool = False) -> dict:
    """Read at most 500 loaded characters. details limits the result to 100 and adds templates, factions and enemies among at most 16 factions represented in the returned rows."""
    if not 1 <= limit <= 500:
        raise ValueError('limit doit être entre 1 et 500')
    if not isinstance(details, bool) or (details and limit > 100):
        raise ValueError('details doit être booléen ; au plus 100 lignes détaillées')
    return await call('list_characters', limit=limit, details=details)


@mcp.tool()
async def get_scene_state(thread_details: bool = False, target: str = 'original') -> dict:
    """Read camera, pause, speed, populations and battle state. While paused, thread_details adds SDK thread roles with verified Windows identities when available."""
    if not isinstance(thread_details,bool):
        raise ValueError('thread_details doit être booléen')
    return await target_call('get_scene_state', target, thread_details=thread_details)


@mcp.tool()
async def set_camera_free(enabled: bool, lock_edge: bool = False, release_edge: bool = False,
                          target: str = 'original') -> dict:
    """Set free-camera mode on the paused test copy, including when restoring its state after an experiment."""
    if not all(isinstance(v,bool) for v in (enabled,lock_edge,release_edge)) or (lock_edge and release_edge):
        raise ValueError('enabled doit être booléen')
    if release_edge:
        return await target_call('set_camera_free', target, enabled=enabled, lock_edge=False, release_edge=True)
    return await target_call('set_camera_free', target, enabled=enabled, lock_edge=lock_edge)


@mcp.tool()
async def list_towns(limit: int = 100, name_filter: str = '') -> dict:
    """List defined towns and their positions; a listed town does not guarantee loaded residents."""
    if not 1 <= limit <= 500 or len(name_filter.encode('utf-8')) > 128:
        raise ValueError('limit doit être entre 1 et 500 et le filtre limité à 128 octets')
    return await call('list_towns', limit=limit, name_filter=name_filter)


@mcp.tool()
async def focus_town(name: str) -> dict:
    """Move the camera to a uniquely named town on the paused copy; restore the initial free-camera mode before reloading. The engine may clamp the move."""
    if not name or len(name.encode('utf-8')) > 128:
        raise ValueError('Nom de ville invalide')
    return await call('focus_town', name=name)


@mcp.tool()
async def prepare_town_scene(name: str) -> dict:
    """On KenshiProbe_test loaded through the probe and paused, move up to 32 grouped player characters to one uniquely identified town. Reload the copy after the experiment."""
    if not name or len(name.encode('utf-8')) > 128:
        raise ValueError('Nom de ville invalide')
    return await call('prepare_town_scene', name=name)


@mcp.tool()
async def prepare_battle_scene(template_id: str, pairs: int = 1, faction_name: str = '',
                               opponent_template_id: str = '', opponent_faction_name: str = '') -> dict:
    """On paused KenshiProbe_test, create 1..20 pairs of loaded NPCs. Specify the faction if the template is ambiguous. An optional opposing template requires already mutually hostile factions. Reload afterward; prepared does not prove hits occurred."""
    if not template_id or len(template_id.encode('utf-8')) > 128:
        raise ValueError('Identifiant de modèle invalide')
    if isinstance(pairs, bool) or not isinstance(pairs, int) or not 1 <= pairs <= 20:
        raise ValueError('pairs doit être entier entre 1 et 20')
    for value in (faction_name, opponent_template_id, opponent_faction_name):
        if not isinstance(value, str) or len(value.encode('utf-8')) > 128 or '\0' in value:
            raise ValueError('Faction ou modèle adverse invalide')
    if opponent_faction_name and not opponent_template_id:
        raise ValueError('Le modèle adverse est requis avec sa faction')
    return await call('prepare_battle_scene', template_id=template_id, pairs=pairs,
                      faction_name=faction_name, opponent_template_id=opponent_template_id,
                      opponent_faction_name=opponent_faction_name)


@mcp.tool()
async def save_scene_snapshot(name: str) -> dict:
    """Schedule a new battle-scenario save while paused; use KenshiProbe_test_scene_ followed by 1..40 safe ASCII characters. Overwriting is refused. Wait for writing to finish before loading; its progress can be tracked within the same plugin session."""
    if not isinstance(name, str) or re.fullmatch(r'KenshiProbe_test_scene_[A-Za-z0-9_-]{1,40}', name) is None:
        raise ValueError('Nom de snapshot de test invalide')
    return await call('save_scene_snapshot', name=name)


def setup_string(value, key, limit=128):
    if type(value) is not str or not value or len(value.encode('utf-8')) > limit or '\0' in value:
        raise ValueError('invalid string: ' + key)
    return value


def setup_number(value, key, low, high, integer=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('invalid number: ' + key)
    if integer and value != int(value):
        raise ValueError(key + ' must be an integer')
    if not low <= value <= high:
        raise ValueError('invalid number: ' + key)
    return value


def setup_position(value, key):
    if type(value) is not list or len(value) != 3 or any(type(v) not in (int, float) for v in value):
        raise ValueError(key + ' must have three numbers')
    if any(not math.isfinite(v) or abs(v) > 1e7 for v in value):
        raise ValueError('invalid position coordinate')
    return value


@mcp.tool()
async def setup_info(target: str = 'original') -> dict:
    """Read the scene-setup gate (docs/scene-setup.md), current and probe-loaded save, world_mutated, autosave state and squad-size facts. Needs only a ready world; changes nothing."""
    return await target_call('setup_info', target)


@mcp.tool()
async def setup_area_census(center: list[float], radius: float, limit: int = 100,
                            target: str = 'original') -> dict:
    """List loaded characters within radius 0.1..20000 (horizontal X/Z) of center [x,y,z], nearest first, at most limit 1..100, with counts over every match. Read-only; requires a probe load_save with allow_setup=True."""
    setup_position(center, 'center')
    setup_number(radius, 'radius', 0.1, 20000)
    setup_number(limit, 'limit', 1, 100, integer=True)
    return await target_call('setup_area_census', target, center=center, radius=radius, limit=limit)


@mcp.tool()
async def setup_spawn_squad(template_id: str, faction_id: str, position: list[float], max_count: int,
                            permanent: bool = False, target: str = 'original') -> dict:
    """Spawn one squad from a SQUAD_TEMPLATE record into an exact non-player faction, within 2000 units (X/Z) of a player character, 1..16 members. Paused world, autosave off and a probe load_save with allow_setup=True required; never saves. Reload the save afterward."""
    setup_string(template_id, 'template_id')
    setup_string(faction_id, 'faction_id')
    setup_position(position, 'position')
    setup_number(max_count, 'max_count', 1, 16, integer=True)
    if type(permanent) is not bool:
        raise ValueError('invalid boolean: permanent')
    params = dict(template_id=template_id, faction_id=faction_id, position=position, max_count=max_count)
    if permanent:
        params['permanent'] = True
    return await target_call('setup_spawn_squad', target, **params)


@mcp.tool()
async def setup_set_relation(source_id: str, target_id: str, value: float, target: str = 'original') -> dict:
    """Set one direction of a faction relation (-100..100) and return both directions before/after plus the matrix diff. The war flag is never written. Same gate as setup_spawn_squad."""
    setup_string(source_id, 'source_id')
    setup_string(target_id, 'target_id')
    setup_number(value, 'value', -100, 100)
    return await target_call('setup_set_relation', target, source_id=source_id, target_id=target_id, value=value)


@mcp.tool()
async def setup_heal(character_id: str, target: str = 'original') -> dict:
    """Fully heal one loaded, living character by its dump_state identity and return its medical state before and after. Same gate as setup_spawn_squad."""
    setup_string(character_id, 'character_id', 200)
    return await target_call('setup_heal', target, character_id=character_id)


def with_setup_opt_in(send):
    """Add allow_setup to the load request only; other session calls are unchanged.

    Relies on OracleSession.load sending load_save through self.call; replace it with
    an allow_setup argument once OracleSession.load accepts one.
    """
    async def call_with_opt_in(command, **params):
        if command == 'load_save':
            params['allow_setup'] = True
        return await send(command, **params)
    return call_with_opt_in


@mcp.tool()
async def load_save(name: str, lock_edge: bool = False, wait: bool = True,
                    target: str = 'original', seed: str | None = None, allow_setup: bool = False) -> dict:
    """Reload a save by name and wait until it is ready and paused (load_timeout, default 120 s). wait=False returns acceptance only; an uncertain mutation is never retried. allow_setup=True enables the setup_* commands for this load only."""
    if not name or len(name.encode('utf-8')) > 128 or name in ('.', '..') or any(c in name for c in '/\\:\r\n\0'):
        raise ValueError('Nom de sauvegarde invalide')
    if type(lock_edge) is not bool or type(wait) is not bool:
        raise ValueError('lock_edge et wait doivent être booléens')
    if type(allow_setup) is not bool:
        raise ValueError('allow_setup must be boolean')
    if not wait:
        if seed is not None:
            raise ValueError('A seeded load requires wait=True for effective-seed verification')
        params = dict(name=name, lock_edge=lock_edge, pause_on_ready=True)
        if allow_setup:
            params['allow_setup'] = True
        accepted = await target_call('load_save', target, **params)
        if allow_setup and accepted.get('allow_setup') is not True:
            raise ProbeError('Probe did not accept allow_setup; update the probe')
        return accepted
    session = OracleSession(target_settings(target))
    if allow_setup:
        session.call = with_setup_opt_in(session.call)
    loaded = await session.load(name, lock_edge=lock_edge, seed=seed)
    # A missing echo is detected only after the load: the save is loaded, but the
    # gate is not known to be open, so the tool raises instead of returning.
    if allow_setup and loaded['accepted'].get('allow_setup') is not True:
        raise ProbeError('Probe did not accept allow_setup; update the probe')
    return dict(loaded['accepted'], ready=loaded['ready'])


@mcp.tool()
async def get_clock(target: str = 'original') -> dict:
    """Shared clock: zero-based day, hour, absolute world-calendar seconds, effective speed (zero while paused) and pause state."""
    return await target_call('get_clock', target)


@mcp.tool()
async def resolve_saved_handles(ids: list[str]) -> dict:
    """Resolve 1..128 complete saved identities to currently loaded characters or squads through the public engine API. Requires pause. Never match by name or by index/serial components alone."""
    validate_saved_handles(ids)
    return await call('resolve_saved_handles', ids=ids)


@mcp.tool()
async def begin_saved_origins(save_name: str, source_fingerprint: str, count: int) -> dict:
    """Begin an identity manifest for the reloaded save without publishing a partial context. Normally prepared automatically by load_save(wait=True)."""
    from oracle_runner import save_name as validate_save_name
    validate_save_name(save_name)
    validate_origin_fingerprint(source_fingerprint)
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError('count must be an integer from 0 to 100000')
    return await call('begin_saved_origins', save_name=save_name, source_fingerprint=source_fingerprint, count=count)


@mcp.tool()
async def add_saved_origins(token: str, ids: list[str]) -> dict:
    """Add 1..128 complete handles to the pending manifest. An invalid batch publishes no identities."""
    validate_origin_token(token)
    validate_saved_handles(ids)
    return await call('add_saved_origins', token=token, ids=ids)


@mcp.tool()
async def commit_saved_origins(token: str) -> dict:
    """Atomically publish the complete manifest; dump_state resolves its identities through the engine, without name matching."""
    validate_origin_token(token)
    return await call('commit_saved_origins', token=token)


@mcp.tool()
async def dump_state(target: str = 'original') -> dict:
    """Capture covered loaded characters, squads and relations while paused; validate the negotiated schema, write a canonical snapshot and return its path/hash. No game save is created."""
    _, record = await OracleSession(target_settings(target)).dump()
    return record


@mcp.tool()
async def run_until(target_seconds: float, timeout_seconds: float = 120, target: str = 'original') -> dict:
    """Advance to an absolute game-clock time, then pause at its first crossing. Return the time actually reached; the timeout is in real seconds. The heartbeat remains available."""
    return await OracleSession(target_settings(target)).until(target_seconds, timeout_seconds)


@mcp.tool()
async def run_until_status(operation_id: str, target: str = 'original') -> dict:
    """Read the status of the identified native run_until operation without waiting for completion."""
    if not operation_id or len(operation_id) > 128:
        raise ValueError('Identifiant d’opération invalide')
    return await target_call('run_until_status', target, operation_id=operation_id)


@mcp.tool()
async def cancel_run_until(operation_id: str, target: str = 'original') -> dict:
    """Cancel the identified native advance and pause the game."""
    if not operation_id or len(operation_id) > 128:
        raise ValueError('Identifiant d’opération invalide')
    return await target_call('cancel_run_until', target, operation_id=operation_id)


@mcp.tool()
async def issue_order(type: str, character_id: str = '', squad_id: str = '',
                      position: list[float] | None = None, target_id: str = '', target: str = 'original') -> dict:
    """Issue move (position x,y,z) or attack (target_id) to one character OR one squad. Use opaque dump_state identities; no teleportation."""
    params = dict(type=type)
    if character_id:
        params['character_id'] = character_id
    if squad_id:
        params['squad_id'] = squad_id
    if position is not None:
        params['position'] = position
    if target_id:
        params['target_id'] = target_id
    validate_scenario(dict(schema_version='0.1', name='validate-order', save='validation', speed=1,
                           repeat=1, actions=[dict(at=0, command='issue_order', params=params)],
                           checkpoints=[dict(at=0, name='validation')]))
    return await target_call('issue_order', target, **params)


@mcp.tool()
async def prepare_scene_control(camera_center: list[float], camera_orientation: list[float],
                                camera_zoom: float, free_camera: bool, edge_scrolling: bool,
                                speed: float, paused: bool, camera_follow_id: str | None = None,
                                target: str = 'original') -> dict:
    """Prepare camera restoration while paused, keep edge scrolling locked and return a token. Wait for a stable pose before commit_scene_control; restore_scene_control orchestrates these steps automatically."""
    params = dict(camera_center=camera_center, camera_orientation=camera_orientation,
                  camera_zoom=camera_zoom, free_camera=free_camera, edge_scrolling=edge_scrolling,
                  speed=speed, paused=paused, camera_follow_id=camera_follow_id)
    restoration_reference(params)
    return await target_call('prepare_scene_control', target, **params)


@mcp.tool()
async def commit_scene_control(token: str, target: str = 'original') -> dict:
    """Correct the center from the settled followed pose, then release the prepared controls. The token belongs to this instance and world; reread the controls after commit."""
    validate_origin_token(token)
    return await target_call('commit_scene_control', target, token=token)


@mcp.tool()
async def restore_scene_control(camera_center: list[float], camera_orientation: list[float],
                                camera_zoom: float, free_camera: bool, edge_scrolling: bool,
                                speed: float, paused: bool, camera_follow_id: str | None = None,
                                target: str = 'original') -> dict:
    """Restore camera and time controls through preparation, stable paused observation, correction and post-release verification. Quaternion order is [w,x,y,z]. A requested resume occurs after verifying the paused pose."""
    result = await OracleSession(target_settings(target)).restore_controls(params=dict(
        camera_center=camera_center, camera_orientation=camera_orientation, camera_zoom=camera_zoom,
        free_camera=free_camera, edge_scrolling=edge_scrolling,
        speed=speed, paused=paused, camera_follow_id=camera_follow_id))
    return {**result['response'], **result['scene'], **result}


@mcp.tool()
async def run_scenario(path: str, repeat: int | None = None, target: str = 'original') -> dict:
    """Run a validated scenario JSON, reloading before each repetition, validating snapshots and writing a stable/variable report under runs. Preload exactly the scenario save, pause and establish a known speed; captured controls must belong to that save. Verify restoration afterward and retain a recovery guard on failure. repeat overrides the file count (1..100)."""
    cfg = target_settings(target)
    if target == 'original' and cfg.get('rekenshi_config'):
        from original_reference import run_original_reference
        from oracle_schema import load_scenario
        return await run_original_reference(load_scenario(path), cfg, repeat=repeat)
    return await run_scenario_file(path, cfg, repeat=repeat)


@mcp.tool()
async def restore_scenario(save: str | None = None, target: str = 'original') -> dict:
    """Restore recorded controls after an interrupted scenario or crash. By default reload the recorded save; save explicitly names the save that owns the captured controls. Keep the record pending until strict verification, then record recovery_save. Do not resume the invalid execution; wait for a ready world after watchdog restart."""
    return await restore_interrupted_scenario(target_settings(target), save=save)


@mcp.tool()
async def compare_scenarios(original_report: str, meitou_report: str, output: str,
                            minimum_repetitions: int = 5, position_tolerance: float = 0.000001,
                            number_tolerance: float = 0.0, arrival_radius: float = 5.0) -> dict:
    """Compare completed campaigns with verified provenance, the same scenario/save and at least five repetitions by default. Write local report.md, report.json and English drafts under issues; publish nothing. Numerical tolerances are separate from observed variability."""
    from oracle_comparison import compare_campaigns
    return await asyncio.to_thread(compare_campaigns, original_report, meitou_report, output,
        minimum_repetitions=minimum_repetitions, tolerances=dict(position=position_tolerance, number=number_tolerance),
        arrival_radius=arrival_radius)


@mcp.tool()
async def game_status() -> dict:
    """Return the supervised original-game process state and the latest heartbeat observed by its watchdog."""
    p = Path(settings()['runtime']) / 'state.json'
    if not p.exists():
        return dict(running=False, watchdog='absent')
    state = await read_runtime_state(p)
    state['watchdog_stale'] = time.time() - state['updated_at'] > 5
    if state['watchdog_stale']:
        state['running'] = None
    return state


@mcp.tool()
async def restart_game() -> dict:
    """Ask the active watchdog to restart the Kenshi process it owns."""
    state = await game_status()
    if state.get('watchdog_stale', True):
        raise ProbeError('Chien de garde absent ou périmé')
    p = Path(settings()['runtime']) / 'restart.request'
    token = uuid.uuid4().hex
    p.write_text(token, encoding='ascii')
    deadline = time.monotonic() + settings().get('timeout', 10)
    while time.monotonic() < deadline:
        state = await game_status()
        if state.get('restart_ack') == token:
            return state
        await asyncio.sleep(.1)
    raise ProbeError('Le chien de garde ne confirme pas le redémarrage')


@mcp.tool()
async def read_log(lines: int = 100) -> str:
    """Return the last 1..2000 lines of the configured log."""
    if not 1 <= lines <= 2000:
        raise ValueError('lines doit être entre 1 et 2000')
    with Path(settings()['log']).open(encoding='utf-8', errors='replace') as f:
        return ''.join(deque(f, maxlen=lines))


if __name__ == '__main__':
    mcp.run(transport='stdio')
