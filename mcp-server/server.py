import asyncio
import json
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
from oracle_identity import validate_saved_handles, validate_origin_fingerprint, validate_origin_token

mcp = FastMCP('KenshiProbe')


def settings():
    return config(os.environ.get('KENSHI_PROBE_CONFIG', 'config.json'))


async def call(command, **params):
    c = settings()
    return await Client(c.get('port', 47800), c.get('timeout', 10)).call(command, **params)


@mcp.tool()
async def heartbeat() -> dict:
    """Lit le dernier battement publié, même au menu ; frame=0 avant la première partie."""
    return await call('heartbeat')


@mcp.tool()
async def ping() -> dict:
    """Vérifie la réponse du thread principal et renvoie les versions."""
    return await call('ping')


@mcp.tool()
async def get_frame_stats(n: int = 300, detail: str = 'aggregates') -> dict:
    """Durées des N dernières frames et agrégats des systèmes. detail='aggregates' omet explicitement les lignes individuelles pour préserver la fenêtre ; full les conserve."""
    if type(n) is not int or not 1 <= n <= 3600:
        raise ValueError('n doit être entre 1 et 3600')
    if type(detail) is not str or detail not in ('full','aggregates'):
        raise ValueError('detail doit être full ou aggregates')
    return await call('get_frame_stats', n=n, detail=detail)


@mcp.tool()
async def pause(paused: bool = True) -> dict:
    """Active ou désactive la pause via GameWorld sur le thread principal."""
    return await call('pause', paused=paused)


@mcp.tool()
async def set_game_speed(speed: float = 1, preserve_pause: bool = False) -> dict:
    """Règle la vitesse entre 0 et 5 ; preserve_pause exige une vitesse positive et conserve la pause dans la même commande native. Par défaut applique le comportement SDK, qui retire la pause pour une vitesse positive. Relire l'état renvoyé."""
    if not 0 <= speed <= 5:
        raise ValueError('speed doit être entre 0 et 5')
    if not isinstance(preserve_pause, bool):
        raise ValueError('preserve_pause doit être booléen')
    if preserve_pause and speed == 0:
        raise ValueError('preserve_pause exige une vitesse strictement positive ; utiliser pause pour zéro')
    if preserve_pause:
        return await call('set_game_speed', speed=speed, preserve_pause=True)
    return await call('set_game_speed', speed=speed)


@mcp.tool()
async def list_characters(limit: int = 100, details: bool = False) -> dict:
    """Lit au maximum 500 personnages chargés ; details limite à 100 et ajoute modèles, factions et ennemis parmi au plus 16 factions des lignes renvoyées."""
    if not 1 <= limit <= 500:
        raise ValueError('limit doit être entre 1 et 500')
    if not isinstance(details, bool) or (details and limit > 100):
        raise ValueError('details doit être booléen ; au plus 100 lignes détaillées')
    return await call('list_characters', limit=limit, details=details)


@mcp.tool()
async def get_scene_state(thread_details: bool = False) -> dict:
    """Lit caméra, pause, vitesse, populations et bataille. thread_details ajoute en pause les rôles SDK avec identités Windows vérifiées, si disponibles."""
    if not isinstance(thread_details,bool):
        raise ValueError('thread_details doit être booléen')
    return await call('get_scene_state',thread_details=thread_details)


@mcp.tool()
async def set_camera_free(enabled: bool, lock_edge: bool = False, release_edge: bool = False) -> dict:
    """Règle le mode libre de caméra sur la copie en pause, notamment pour restaurer son état après un essai."""
    if not all(isinstance(v,bool) for v in (enabled,lock_edge,release_edge)) or (lock_edge and release_edge):
        raise ValueError('enabled doit être booléen')
    if release_edge:
        return await call('set_camera_free',enabled=enabled,lock_edge=False,release_edge=True)
    return await call('set_camera_free', enabled=enabled, lock_edge=lock_edge)


@mcp.tool()
async def list_towns(limit: int = 100, name_filter: str = '') -> dict:
    """Inventorie les villes définies et leurs positions ; leur présence ne garantit pas des habitants chargés."""
    if not 1 <= limit <= 500 or len(name_filter.encode('utf-8')) > 128:
        raise ValueError('limit doit être entre 1 et 500 et le filtre limité à 128 octets')
    return await call('list_towns', limit=limit, name_filter=name_filter)


@mcp.tool()
async def focus_town(name: str) -> dict:
    """Déplace la caméra vers une ville au nom unique sur la copie en pause ; restaurer le mode libre initial avant de recharger. Le moteur peut limiter le déplacement."""
    if not name or len(name.encode('utf-8')) > 128:
        raise ValueError('Nom de ville invalide')
    return await call('focus_town', name=name)


@mcp.tool()
async def prepare_town_scene(name: str) -> dict:
    """Sur KenshiProbe_test chargé via la sonde et en pause, déplace jusqu'à 32 personnages joueur groupés vers une ville unique. Recharger la copie après l'essai."""
    if not name or len(name.encode('utf-8')) > 128:
        raise ValueError('Nom de ville invalide')
    return await call('prepare_town_scene', name=name)


@mcp.tool()
async def prepare_battle_scene(template_id: str, pairs: int = 1, faction_name: str = '',
                               opponent_template_id: str = '', opponent_faction_name: str = '') -> dict:
    """Sur KenshiProbe_test en pause, crée 1..20 paires de PNJ chargés. Préciser la faction si le modèle est ambigu. Un modèle adverse optionnel exige des factions déjà mutuellement ennemies. Recharger après l'essai ; prepared ne prouve pas des coups portés."""
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
    """Planifie une nouvelle sauvegarde de scénario de combat en pause ; nom KenshiProbe_test_scene_ suivi de 1..40 caractères ASCII sûrs. Tout écrasement est refusé. Attendre la fin de l'écriture avant chargement ; suivi restaurable dans la même session du plugin."""
    if not isinstance(name, str) or re.fullmatch(r'KenshiProbe_test_scene_[A-Za-z0-9_-]{1,40}', name) is None:
        raise ValueError('Nom de snapshot de test invalide')
    return await call('save_scene_snapshot', name=name)


@mcp.tool()
async def load_save(name: str, lock_edge: bool = False, wait: bool = True) -> dict:
    """Recharge une sauvegarde par nom et attend sa disponibilité en pause (load_timeout, 120 s par défaut). wait=False retourne seulement l'acceptation ; aucune mutation incertaine n'est réessayée."""
    if not name or len(name.encode('utf-8')) > 128 or name in ('.', '..') or any(c in name for c in '/\\:\r\n\0'):
        raise ValueError('Nom de sauvegarde invalide')
    if type(lock_edge) is not bool or type(wait) is not bool:
        raise ValueError('lock_edge et wait doivent être booléens')
    if not wait:
        return await call('load_save', name=name, lock_edge=lock_edge, pause_on_ready=True)
    loaded = await OracleSession(settings()).load(name, lock_edge=lock_edge)
    return dict(loaded['accepted'], ready=loaded['ready'])


@mcp.tool()
async def get_clock() -> dict:
    """Horloge du schéma 0.1 : jour zéro-indexé, heure, secondes calendaires absolues de jeu, vitesse effective (zéro en pause) et pause."""
    return await call('get_clock')


@mcp.tool()
async def resolve_saved_handles(ids: list[str]) -> dict:
    """Résout 1..128 identifiants complets sauvegardés vers les personnages ou escouades actuellement chargés, via l'API publique du moteur. Exige la pause. Ne rapproche jamais les noms ni les seules composantes index/serial."""
    validate_saved_handles(ids)
    return await call('resolve_saved_handles', ids=ids)


@mcp.tool()
async def begin_saved_origins(save_name: str, source_fingerprint: str, count: int) -> dict:
    """Commence un manifeste d'identités de la sauvegarde rechargée, sans publier de contexte partiel. Normalement préparé automatiquement par load_save(wait=True)."""
    from oracle_runner import save_name as validate_save_name
    validate_save_name(save_name)
    validate_origin_fingerprint(source_fingerprint)
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError('count must be an integer from 0 to 100000')
    return await call('begin_saved_origins', save_name=save_name, source_fingerprint=source_fingerprint, count=count)


@mcp.tool()
async def add_saved_origins(token: str, ids: list[str]) -> dict:
    """Ajoute un lot de 1..128 poignées complètes au manifeste en attente. Un lot invalide ne publie aucune identité."""
    validate_origin_token(token)
    validate_saved_handles(ids)
    return await call('add_saved_origins', token=token, ids=ids)


@mcp.tool()
async def commit_saved_origins(token: str) -> dict:
    """Publie atomiquement le manifeste complet ; dump_state résout ses identités via le moteur, sans rapprochement par nom."""
    validate_origin_token(token)
    return await call('commit_saved_origins', token=token)


@mcp.tool()
async def dump_state() -> dict:
    """Capture en pause tous les personnages chargés, escouades et relations ; valide le schéma 0.1, écrit une photo canonique et renvoie chemin/empreinte. Aucune sauvegarde du jeu n'est créée."""
    _, record = await OracleSession(settings()).dump()
    return record


@mcp.tool()
async def run_until(target_seconds: float, timeout_seconds: float = 120) -> dict:
    """Avance jusqu'à l'instant absolu de l'horloge du jeu, puis met en pause au premier franchissement. Renvoie l'instant réellement atteint ; le délai est en secondes réelles. Le heartbeat reste disponible."""
    return await OracleSession(settings()).until(target_seconds, timeout_seconds)


@mcp.tool()
async def run_until_status(operation_id: str) -> dict:
    """Lit sans attente l'état de l'opération native run_until identifiée."""
    if not operation_id or len(operation_id) > 128:
        raise ValueError('Identifiant d’opération invalide')
    return await call('run_until_status', operation_id=operation_id)


@mcp.tool()
async def cancel_run_until(operation_id: str) -> dict:
    """Annule l'avance native identifiée et remet le jeu en pause."""
    if not operation_id or len(operation_id) > 128:
        raise ValueError('Identifiant d’opération invalide')
    return await call('cancel_run_until', operation_id=operation_id)


@mcp.tool()
async def issue_order(type: str, character_id: str = '', squad_id: str = '',
                      position: list[float] | None = None, target_id: str = '') -> dict:
    """Donne un ordre move (position x,y,z) ou attack (target_id) à un personnage OU une escouade. Utiliser les identifiants opaques de dump_state ; aucune téléportation."""
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
    return await call('issue_order', **params)


@mcp.tool()
async def prepare_scene_control(camera_center: list[float], camera_orientation: list[float],
                                camera_zoom: float, free_camera: bool, edge_scrolling: bool,
                                speed: float, paused: bool, camera_follow_id: str | None = None) -> dict:
    """Prépare en pause une restitution caméra, maintient le défilement verrouillé et renvoie un token. Attendre une pose stable avant commit_scene_control ; restore_scene_control orchestre ces étapes automatiquement."""
    params = dict(camera_center=camera_center, camera_orientation=camera_orientation,
                  camera_zoom=camera_zoom, free_camera=free_camera, edge_scrolling=edge_scrolling,
                  speed=speed, paused=paused, camera_follow_id=camera_follow_id)
    restoration_reference(params)
    return await call('prepare_scene_control', **params)


@mcp.tool()
async def commit_scene_control(token: str) -> dict:
    """Corrige le centre depuis la pose suivie stabilisée puis libère les contrôles préparés. Le token est lié à cette instance et à ce monde ; relire les contrôles après commit."""
    validate_origin_token(token)
    return await call('commit_scene_control', token=token)


@mcp.tool()
async def restore_scene_control(camera_center: list[float], camera_orientation: list[float],
                                camera_zoom: float, free_camera: bool, edge_scrolling: bool,
                                speed: float, paused: bool, camera_follow_id: str | None = None) -> dict:
    """Restaure caméra et temps par préparation, observation stable en pause, correction puis vérification après libération. Quaternion [w,x,y,z]. Une reprise demandée intervient après vérification de la pose en pause."""
    result = await OracleSession(settings()).restore_controls(params=dict(
        camera_center=camera_center, camera_orientation=camera_orientation, camera_zoom=camera_zoom,
        free_camera=free_camera, edge_scrolling=edge_scrolling,
        speed=speed, paused=paused, camera_follow_id=camera_follow_id))
    return {**result['response'], **result['scene'], **result}


@mcp.tool()
async def run_scenario(path: str, repeat: int | None = None) -> dict:
    """Exécute un fichier JSON de scénario validé, avec rechargement avant chaque répétition, photos validées et rapport stable/variable dans runs. Prérequis : précharger exactement la sauvegarde du scénario, mettre en pause et établir une vitesse connue ; les contrôles capturés doivent provenir de cette même sauvegarde. Vérifie leur restitution après l'essai et conserve un verrou de récupération en cas d'échec. repeat remplace le nombre du fichier (1..100)."""
    return await run_scenario_file(path, settings(), repeat=repeat)


@mcp.tool()
async def restore_scenario(save: str | None = None) -> dict:
    """Restaure les contrôles consignés après un scénario interrompu ou un crash. Par défaut recharge la sauvegarde du registre ; save permet de nommer explicitement la sauvegarde dont proviennent les contrôles capturés. Le registre reste en attente jusqu'à vérification stricte, puis trace recovery_save. Ne reprend pas l'exécution invalide ; attendre un monde prêt après relance du watchdog."""
    return await restore_interrupted_scenario(settings(), save=save)


@mcp.tool()
async def game_status() -> dict:
    """État du processus surveillé et dernier battement constaté par le watchdog."""
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
    """Demande au watchdog actif de redémarrer son propre processus Kenshi."""
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
    """Retourne les dernières lignes du journal configuré (1 à 2000)."""
    if not 1 <= lines <= 2000:
        raise ValueError('lines doit être entre 1 et 2000')
    with Path(settings()['log']).open(encoding='utf-8', errors='replace') as f:
        return ''.join(deque(f, maxlen=lines))


if __name__ == '__main__':
    mcp.run(transport='stdio')
