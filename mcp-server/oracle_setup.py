"""Runner scene-setup block for scenario-0.2 (docs/scene-setup.md, Runner steps).

The block runs after the speed preparation and before the origin clock read, so
checkpoint 0 is the verified post-setup world. It executes spawn, settle, heal,
relations, whatever the key order in the scenario. Every command goes once:
a failure raises ScenarioError with no retry, after writing a failed receipt,
and the runner's normal restoration reloads the save.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from oracle_engine_profile import EngineProfileError, check_player, configured_profile, resolve_repetitions
from oracle_identity import validate_origin_fingerprint
from oracle_origins import SavedOriginError, read_saved_origins
from oracle_runner import ScenarioError, write_json
from probe import ProbeError


RECEIPT_FORMAT = 'scene-setup-0.1'
CAPABILITY = 'scene_setup'
SETTLE_CALENDAR_SECONDS = 33
CENSUS_LIMIT = 100
COMMIT_UNKNOWN = 'commit unknown'
COMMIT_NOT_RECORDED = 'build commit not recorded'
_COMMIT = re.compile(r'[0-9a-f]{40}')
_SQUAD_SIZE_KEY = b'squad size multiplier'
_DECIMAL = re.compile(rb'[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
_HOSTILE_AT = -60


class SetupFailure(ScenarioError):
    """A scene-setup check failed; the receipt names the step."""


def setup_hash(setup):
    """Lowercase SHA-256 of the canonical setup block, as the comparator recomputes it."""
    text = json.dumps(setup, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def build_commit(ping, limitations, *, required=False):
    """Return (build_commit, build_commit_known) from a ping and add its limitation.

    "unknown" is accepted with the limitation "commit unknown" (Q10); a missing
    value is accepted only without a setup, as "build commit not recorded".
    """
    commit = ping.get('build_commit')
    if commit is None and not required:
        if COMMIT_NOT_RECORDED not in limitations:
            limitations.append(COMMIT_NOT_RECORDED)
        return None, False
    if commit == 'unknown':
        if COMMIT_UNKNOWN not in limitations:
            limitations.append(COMMIT_UNKNOWN)
        return commit, False
    if type(commit) is not str or not _COMMIT.fullmatch(commit):
        raise ScenarioError('Probe reported no valid build_commit; scene setup needs probe 0.11.0')
    return commit, True


def float32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _position(value):
    return type(value) is list and len(value) == 3 and all(_number(v) for v in value)


def _line_multiplier(line):
    """Parse one settings.cfg line by the contract's selection rule; None if it does not match."""
    if type(line) is not str:
        return None
    raw = line.encode('utf-8')
    key, separator, value = raw.partition(b'=')
    value = value.strip()
    if not separator or key.strip().lower() != _SQUAD_SIZE_KEY or not _DECIMAL.fullmatch(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def alias_ids(alias_map):
    """Map each aliased id to its "alias:<name>" key for variability and comparison."""
    return {identity: 'alias:' + alias for alias, identity in (alias_map or {}).items()}


def resolve_aliases(params, alias_map):
    """Substitute issue_order alias keys with ids; an alias not in alias_map raises."""
    resolved = dict(params)
    for key, target in (('character_alias', 'character_id'), ('squad_alias', 'squad_id'),
                        ('target_alias', 'target_id')):
        if key not in resolved:
            continue
        alias = resolved.pop(key)
        if alias not in alias_map:
            raise ScenarioError(f'Alias {alias!r} is not bound by the scene setup')
        # A squad alias names a spawn; character aliases name a player or a member.
        if (key == 'squad_alias') != ('/' not in alias and alias != 'player'):
            raise ScenarioError(f'Alias {alias!r} does not name a {key.split("_")[0]}')
        resolved[target] = alias_map[alias]
    return resolved


async def prepare_setup(session, scenario, cfg, ping, fingerprint, seeds, engine_facts):
    """Checks before the restoration guard is armed; returns one profile entry per repetition."""
    capabilities = ping.get('capabilities')
    if type(capabilities) is not list or CAPABILITY not in capabilities:
        raise ScenarioError('Probe lacks capability scene_setup; this scenario needs probe 0.11.0')
    target = ping.get('target', 'original')
    if target == 'original':
        facts = (engine_facts or {}).get('squad_size') if isinstance(engine_facts, dict) else None
        if not isinstance(facts, dict) or facts.get('source') != 'engine_facts':
            raise ScenarioError('Scene setup on the original needs engine_facts from the reference launcher')
        if fingerprint is None:
            raise ScenarioError('Scene setup needs the save source fingerprint of prepared saved origins')
    else:
        # MeitouClient prepares no native context; fingerprint the same source as its loads.
        try:
            manifest = await asyncio.to_thread(read_saved_origins, session.source_root(ping), scenario['save'])
        except SavedOriginError as exc:
            raise ScenarioError('Saved identity source '+exc.code+': '+str(exc)) from exc
        fingerprint = validate_origin_fingerprint(manifest['fingerprint'])
    try:
        profile = configured_profile(cfg)
        entries = resolve_repetitions(profile, target, scenario['save'], fingerprint, seeds)
    except EngineProfileError as exc:
        raise ScenarioError('Engine profile: ' + str(exc)) from exc
    return fingerprint, entries


class _Block:
    def __init__(self, session, scenario, folder, profile, facts):
        self.session = session
        self.setup = scenario['setup']
        self.scenario = scenario
        self.folder = Path(folder)
        self.profile = profile
        self.facts = facts
        self.step = 'S0'
        self.steps = []
        self.alias_map = {}
        self.limitations = []
        self.epoch = None
        self.instance = None
        self.target = None
        preflight = self.setup['preflight']
        self.center = [float(preflight['scene_center'][0]), 0.0, float(preflight['scene_center'][1])]
        self.radius = preflight['scene_radius']

    def fail(self, message):
        raise SetupFailure(message)

    async def command(self, command, params=None, call=None):
        params = {} if params is None else params
        record = dict(step=self.step, request=dict(command=command, params=deepcopy(params)),
                      reply=None, read_back={}, verdict='failed')
        self.steps.append(record)
        reply = await (call() if call is not None else self.session.call(command, **params))
        record['reply'] = reply
        if not isinstance(reply, dict):
            self.fail(command + ' returned no object')
        return record

    @staticmethod
    def passed(record, **read_back):
        record['read_back'].update(read_back)
        record['verdict'] = 'passed'
        return record['reply']

    async def guard(self, *, mutated, mutation=False):
        """Ping and setup_info around every step (docs/scene-setup.md, Runner steps)."""
        record = await self.command('ping', call=self.session.ping)
        ping = record['reply']
        if self.instance is None:
            self.instance = ping.get('instance_id')
        if ping.get('instance_id') != self.instance:
            self.fail('probe instance changed during scene setup')
        if ping.get('world_ready') is not True or ping.get('paused') is not True:
            self.fail('world is not ready and paused')
        if ping.get('world_mutated') is not mutated:
            self.fail(f'world_mutated is {ping.get("world_mutated")!r}, expected {mutated!r}')
        if self.target == 'original' and ping.get('saved_origins_prepared') is not True:
            self.fail('saved origins are not prepared')
        self.passed(record)
        record = await self.command('setup_info')
        gate = record['reply'].get('gate')
        if not isinstance(gate, dict) or gate.get('open') is not True:
            self.fail('scene-setup gate is not open')
        if gate.get('allow_setup') is not True or gate.get('probe_loaded_save') != self.scenario['save']:
            self.fail('scene-setup gate does not belong to this allow_setup load of the scenario save')
        if self.epoch is None:
            self.epoch = gate.get('epoch')
        if type(gate.get('epoch')) is not int or gate.get('epoch') != self.epoch:
            self.fail('scene-setup epoch changed')
        if record['reply'].get('world_mutated') is not mutated:
            self.fail('setup_info world_mutated differs from the expected value')
        if mutation and gate.get('mutation_refusal') is not None:
            self.fail('mutation refused: ' + json.dumps(gate['mutation_refusal'], sort_keys=True))
        return self.passed(record)

    async def census(self):
        record = await self.command('setup_area_census', dict(center=list(self.center), radius=self.radius,
                                                              limit=CENSUS_LIMIT))
        reply = record['reply']
        rows = reply.get('characters')
        if type(rows) is not list or reply.get('truncated') is not False or reply.get('count') != len(rows):
            self.fail('census is truncated or inconsistent')
        for row in rows:
            if (not isinstance(row, dict) or type(row.get('id')) is not str or not _position(row.get('position'))
                    or type(row.get('dead')) is not bool or type(row.get('unconscious')) is not bool):
                self.fail('census row is malformed')
        if len({row['id'] for row in rows}) != len(rows):
            self.fail('census repeats a character id')
        return record

    def mutation_reply(self, reply):
        if reply.get('saved') is not False or reply.get('world_mutated') is not True:
            self.fail('mutation reply is not saved:false and world_mutated:true')

    async def dump(self, name):
        path = self.folder / 'setup' / (name + '.json')
        holder = {}

        async def call():
            holder['state'], record = await self.session.dump(path)
            return record
        record = await self.command('dump_state', dict(destination='setup/' + name + '.json'), call)
        reply = record['reply']
        self.passed(record, sha256=reply['sha256'])
        return holder['state'], dict(path='setup/' + name + '.json', sha256=reply['sha256'])

    # Steps -----------------------------------------------------------------

    async def s0(self):
        self.step = 'S0'
        await self.guard(mutated=False)
        clock = await self.command('get_clock')
        self.passed(clock)
        record = await self.command('setup_info')
        info = record['reply']
        if info.get('autosave_enabled') is not False or info.get('autosave_configured') is not False:
            self.fail('autosave is enabled or unreadable; scene setup is refused')
        self.squad_size = self.squad_size_facts(info)
        self.passed(record, squad_size=self.squad_size)
        record = await self.census()
        rows = record['reply']['characters']
        preflight = self.setup['preflight']
        absent = set(preflight['expect_absent_factions_in_scene'])
        intruders = sorted(row['id'] for row in rows if row.get('faction_id') in absent)
        if intruders:
            self.fail('expected-absent faction present in the scene: ' + ', '.join(intruders))
        players = sorted((row for row in rows if row.get('is_player') is True), key=lambda row: row['id'].encode('utf-8'))
        if record['reply'].get('player_count') != len(players) or not players:
            self.fail('no player character in the scene census')
        if any(row.get('faction_id') != preflight['player_faction_id'] for row in players):
            self.fail('a player character is not in player_faction_id')
        if len(players) == 1:
            self.alias_map['player'] = players[0]['id']
        else:
            for index, row in enumerate(players, 1):
                self.alias_map[f'player/{index}'] = row['id']
        self.players = players
        self.rows = {row['id']: row for row in rows}
        if len(players) != 1:
            # offset_from_player and the pinned height both name the single player.
            self.fail('scene setup needs exactly one player character in the scene, found ' + str(len(players)))
        self.player_before = list(players[0]['position'])
        try:
            pin = check_player(self.profile, self.player_before, 'before_settle')
        except EngineProfileError as exc:
            self.fail('player pin before settle: ' + str(exc))
        self.passed(record, players=[row['id'] for row in players], pin_before_settle=pin)

    def squad_size_facts(self, info):
        multiplier = self.setup['preflight']['squad_size_multiplier']
        if self.target == 'original':
            facts = deepcopy((self.facts or {}).get('squad_size'))
            source = 'engine_facts'
        else:
            facts = deepcopy(info.get('squad_size'))
            source = 'setup_info'
            if not isinstance(facts, dict) or facts.get('source') != 'settings.cfg':
                self.fail('setup_info squad_size does not come from settings.cfg')
        if not isinstance(facts, dict) or type(facts.get('sha256')) is not str:
            self.fail('squad size facts are missing')
        line = facts.get('line')
        parsed = _line_multiplier(line)
        if (parsed is None or parsed != facts.get('multiplier')
                or hashlib.sha256(line.encode('utf-8')).hexdigest() != facts['sha256']):
            self.fail('squad size line, hash and multiplier disagree')
        if facts['multiplier'] != multiplier:
            self.fail(f'squad size multiplier {facts["multiplier"]!r} differs from {multiplier!r}')
        return dict(source=source, multiplier=facts['multiplier'], line=line, sha256=facts['sha256'],
                    path=facts.get('path', 'settings.cfg'))

    async def s2(self):
        self.step = 'S2'
        self.members = []
        mutated = False
        for spawn in self.setup['spawns']:
            dx, dz = spawn['at']['offset_from_player']
            x, y, z = self.player_before
            position = [x + dx, y, z + dz]
            if math.hypot(position[0] - self.center[0], position[2] - self.center[2]) > self.radius:
                self.fail(f'spawn point of {spawn["alias"]} lies outside scene_radius')
            await self.guard(mutated=mutated, mutation=True)
            before = await self.census()
            self.passed(before)
            known = {row['id'] for row in before['reply']['characters']}
            record = await self.command('setup_spawn_squad', dict(
                template_id=spawn['squad_template'], faction_id=spawn['faction_id'],
                position=position, max_count=spawn['count']))
            mutated = True
            reply = record['reply']
            self.mutation_reply(reply)
            squad, members = reply.get('returned_squad_id'), reply.get('returned_members')
            if type(squad) is not str or not squad or type(members) is not list:
                self.fail(f'spawn {spawn["alias"]} returned no squad')
            if not len(members) == spawn['count'] == reply.get('new_loaded_count'):
                self.fail(f'spawn {spawn["alias"]} returned {len(members)} members, '
                          f'{reply.get("new_loaded_count")!r} new, expected {spawn["count"]}')
            if reply.get('new_loaded_truncated') is not False:
                self.fail('spawn new_loaded list is truncated')
            for member in members:
                if (not isinstance(member, dict) or type(member.get('id')) is not str
                        or member.get('squad_id') != squad or member.get('faction_id') != spawn['faction_id']
                        or member.get('dead') is not False or member.get('unconscious') is not False
                        or not isinstance(member.get('medical'), dict)):
                    self.fail(f'spawn {spawn["alias"]} member differs from the requested squad, faction or state')
            templates = {}
            for member in members:
                templates[member.get('template_id')] = templates.get(member.get('template_id'), 0) + 1
            if templates != spawn['expected_templates']:
                self.fail('template plan differs: ' + json.dumps(templates, sort_keys=True))
            self.passed(record, templates=templates)
            await self.guard(mutated=True)
            after = await self.census()
            rows = after['reply']['characters']
            new = {row['id']: row for row in rows if row['id'] not in known}
            if set(new) != {member['id'] for member in members} or after['reply']['count'] != len(known) + len(members):
                self.fail(f'census does not show exactly the {spawn["count"]} new characters of {spawn["alias"]}')
            if any(row.get('squad_id') != squad or row.get('faction_id') != spawn['faction_id']
                   or row['dead'] or row['unconscious'] for row in new.values()):
                self.fail(f'census rows of {spawn["alias"]} differ from the spawn reply')
            self.alias_map[spawn['alias']] = squad
            seen = {}
            for member in members:
                seen[member['template_id']] = seen.get(member['template_id'], 0) + 1
                alias = f'{spawn["alias"]}/{member["template_id"]}/{seen[member["template_id"]]}'
                self.alias_map[alias] = member['id']
                self.members.append(dict(alias=alias, id=member['id'], template_id=member['template_id'],
                                         faction_id=member['faction_id'], rng_key=reply.get('rng_key')))
            self.passed(after, new=sorted(new))
        if len(set(self.alias_map.values())) != len(self.alias_map):
            self.fail('two aliases bind the same id')

    async def s3(self):
        self.step = 'S3'
        await self.guard(mutated=True)
        record = await self.command('set_game_speed', dict(speed=1, preserve_pause=True))
        self.passed(record)
        record = await self.command('get_clock')
        start = record['reply'].get('elapsed_seconds')
        if not _number(start) or record['reply'].get('paused') is not True:
            self.fail('settle start clock is not a paused finite time')
        self.passed(record)
        target = start + SETTLE_CALENDAR_SECONDS
        timeout = self.session.cfg.get('run_until_timeout', 120)
        record = await self.command('run_until', dict(target_seconds=target, timeout_seconds=timeout),
                                    lambda: self.session.until(target, timeout))
        end = record['reply'].get('clock', {}).get('elapsed_seconds')
        if not _number(end):
            self.fail('settle completion has no finite clock')
        self.passed(record)
        await self.guard(mutated=True)
        census = await self.census()
        player = next((row for row in census['reply']['characters'] if row['id'] == self.alias_map['player']), None)
        if player is None:
            self.fail('player left the scene during the settle')
        try:
            pin = check_player(self.profile, list(player['position']), 'after_settle', before=self.player_before)
        except EngineProfileError as exc:
            self.fail('player pin after settle: ' + str(exc))
        self.passed(census, pin_after_settle=pin)
        self.settle = dict(sim_seconds=self.setup['settle']['sim_seconds'],
                           calendar_seconds_requested=SETTLE_CALENDAR_SECONDS,
                           start_seconds=start, end_seconds=end, calendar_seconds_run=end - start,
                           player_before=self.player_before, player_after=list(player['position']),
                           pin=pin['pin'], observed=pin['observed'], delta=pin['delta'])

    def heal_targets(self):
        players = [dict(alias=alias, id=identity, template_id=self.rows[identity].get('template_id'),
                        faction_id=self.rows[identity].get('faction_id'), rng_key=None)
                   for alias, identity in self.alias_map.items()
                   if alias == 'player' or alias.startswith('player/')]
        return players + self.members

    async def s3b(self):
        self.step = 'S3b'
        await self.guard(mutated=True)
        state, self.dumps['S3b'] = await self.dump('S3b')
        characters = {row['id']: row for row in state['characters']}
        for target in self.heal_targets():
            row = characters.get(target['id'])
            if row is None:
                self.fail(f'{target["alias"]} is missing from the S3b dump')
            if row['state'] == 'dead':
                self.fail(f'{target["alias"]} is dead before heal')
            if row['state'] == 'unconscious':
                self.fail('unconscious before heal: ' + target['alias'])
        return state

    async def s5(self, s3b):
        self.step = 'S5'
        self.healed = []
        for target in self.heal_targets():
            await self.guard(mutated=True, mutation=True)
            record = await self.command('setup_heal', dict(character_id=target['id']))
            reply = record['reply']
            self.mutation_reply(reply)
            after, before = reply.get('after'), reply.get('before')
            if not isinstance(after, dict) or not isinstance(before, dict):
                self.fail(f'heal of {target["alias"]} returned no medical state')
            parts = after.get('parts')
            if type(parts) is not list or not parts:
                self.fail(f'heal of {target["alias"]} returned no parts')
            for part in parts:
                if (not isinstance(part, dict) or not _number(part.get('max')) or part.get('flesh') != part['max']
                        or part.get('stun') != 0):
                    self.fail(f'heal not full: {target["alias"]} part {part.get("id") if isinstance(part, dict) else part!r}')
            if after.get('dead') is not False or after.get('unconscious') is not False:
                self.fail(f'heal not full: {target["alias"]} is dead or unconscious')
            self.healed.append(dict(target, part_max={part['id']: part['max'] for part in parts},
                                    blood_before=before.get('blood'), blood_after=after.get('blood')))
            self.passed(record)
        await self.guard(mutated=True)
        state, self.dumps['S5'] = await self.dump('S5')
        if relation_cells(state) != relation_cells(s3b):
            self.fail('heal moved a relation: S5 relations differ from S3b')
        return state

    async def s4(self):
        self.step = 'S4'
        self.war_unobservable = False
        for relation in self.setup['relations']:
            a, b = relation['a'], relation['b']
            pair = {(a, b), (b, a)}
            final = None
            for source, target, value in ((a, b, relation['a_to_b']), (b, a, relation['b_to_a'])):
                await self.guard(mutated=True, mutation=True)
                record = await self.command('setup_set_relation', dict(source_id=source, target_id=target,
                                                                       value=value))
                reply = record['reply']
                self.mutation_reply(reply)
                changes = reply.get('changes')
                if type(changes) is not list or reply.get('changes_truncated') is not False:
                    self.fail('relation changes are missing or truncated')
                cells = {(row.get('source_id'), row.get('target_id')) for row in changes if isinstance(row, dict)}
                if len(cells) != len(changes) or not cells <= pair or reply.get('changed_cells') != len(changes):
                    self.fail(f'relation set {source}->{target} changed a cell outside the pair')
                for key in ('source_to_target', 'target_to_source'):
                    side = reply.get(key)
                    if (not isinstance(side, dict) or not isinstance(side.get('before'), dict)
                            or not isinstance(side.get('after'), dict)):
                        self.fail('relation reply has no ' + key)
                    old, new = side['before'].get('at_war'), side['after'].get('at_war')
                    if old is None or new is None:
                        self.war_unobservable = True
                    elif old != new:
                        self.fail(f'relation set {source}->{target} changed the war flag ({key})')
                self.passed(record, changed_cells=reply.get('changed_cells'))
                final = reply
            # The last call was (b, a): source_to_target is b->a, target_to_source is a->b.
            reads = {(b, a): final['source_to_target']['after'], (a, b): final['target_to_source']['after']}
            for (source, target), value in (((a, b), relation['a_to_b']), ((b, a), relation['b_to_a'])):
                read = reads[(source, target)]
                if read.get('relation') != float32(value):
                    self.fail(f'relation {source}->{target} reads {read.get("relation")!r}, expected {value}')
                if type(read.get('is_enemy')) is not bool or (value <= _HOSTILE_AT and read['is_enemy'] is not True):
                    self.fail(f'relation {source}->{target} at {value} does not read hostile')
            self.steps[-1]['read_back'].update(is_enemy={f'{s}->{t}': reads[(s, t)]['is_enemy'] for s, t in reads})
        if self.war_unobservable:
            self.limitations.append('war flag not observable on ' + self.target)

    async def s6(self, s5):
        self.step = 'S6'
        await self.guard(mutated=True)
        state, self.dumps['S6'] = await self.dump('S6')
        pairs = {cell for relation in self.setup['relations']
                 for cell in ((relation['a'], relation['b']), (relation['b'], relation['a']))}
        before, after = relation_cells(s5), relation_cells(state)
        moved = {cell for cell in set(before) | set(after) if before.get(cell) != after.get(cell)} - pairs
        if moved:
            self.fail('relations outside the pair moved: ' + json.dumps(sorted(moved)))
        for relation in self.setup['relations']:
            for cell, value in (((relation['a'], relation['b']), relation['a_to_b']),
                                ((relation['b'], relation['a']), relation['b_to_a'])):
                if after.get(cell) != float32(value):
                    self.fail(f'S6 dump reads relation {cell[0]}->{cell[1]} as {after.get(cell)!r}, expected {value}')
        census = await self.census()
        rows = {row['id']: row for row in census['reply']['characters']}
        for alias, identity in self.alias_map.items():
            if identity in rows:
                if rows[identity]['dead'] or rows[identity]['unconscious']:
                    self.fail(f'{alias} is dead or unconscious after setup')
            elif not any(row.get('squad_id') == identity for row in rows.values()):
                self.fail(f'{alias} is not in the final census')
        self.passed(census)
        if self.scenario['speed'] != 1:
            record = await self.command('set_game_speed', dict(speed=self.scenario['speed'], preserve_pause=True))
            self.passed(record)
        await self.guard(mutated=True)


def relation_cells(state):
    return {(row['source_id'], row['target_id']): row['value'] for row in state['relations']}


async def run_setup_block(session, scenario, folder, execution, profile, facts):
    """Run S0..S6 once and return the passed receipt; on failure record it and raise.

    profile is this repetition's engine-profile entry, facts the original's engine_facts.
    """
    block = _Block(session, scenario, folder, profile, facts)
    (Path(folder) / 'setup').mkdir(parents=True, exist_ok=True)
    receipt = dict(receipt_format=RECEIPT_FORMAT, target=None, setup_hash=setup_hash(scenario['setup']),
                   build_commit=None, build_commit_known=False, alias_map=block.alias_map, steps=block.steps,
                   dumps={}, members=[], squad_size=None, settle=None, limitations=block.limitations,
                   verdict='failed', failure=None)
    block.dumps = receipt['dumps']
    execution['setup'] = receipt
    try:
        ping = await session.ping()
        block.target = receipt['target'] = ping.get('target', 'original')
        receipt['build_commit'], receipt['build_commit_known'] = build_commit(ping, block.limitations,
                                                                              required=True)
        await block.s0()
        receipt['squad_size'] = block.squad_size
        await block.s2()
        await block.s3()
        receipt['settle'] = block.settle
        s3b = await block.s3b()
        s5 = await block.s5(s3b)
        receipt['members'] = block.healed
        await block.s4()
        await block.s6(s5)
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ProbeError, EngineProfileError)) else type(exc).__name__ + ': ' + str(exc)
        receipt.update(squad_size=getattr(block, 'squad_size', None), settle=getattr(block, 'settle', None),
                       members=getattr(block, 'healed', []), failure=dict(step=block.step, message=message))
        write_json(Path(folder) / 'setup' / 'setup.json', receipt)
        raise ScenarioError(f'Scene setup {block.step} failed: {message}') from exc
    receipt['verdict'] = 'passed'
    write_json(Path(folder) / 'setup' / 'setup.json', receipt)
    return receipt
