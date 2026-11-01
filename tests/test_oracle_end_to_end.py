"""Runner to comparator, end to end, on original-like and Meitou-like synthetic probes.

The fakes never read or launch Kenshi. The original-like probe prepares native
saved origins and takes the squad-size facts from engine_facts; the Meitou-like
probe applies a seed before each load, reports settings.cfg squad-size facts and
a decimal rng_key. Both dump state 0.2. The fake has no RE_Kenshi reference
launcher, so the original campaign receives the comparator tests' structural
reference proof after the run.
"""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from fake_probe import FakeProbe
from oracle_comparison import compare_campaigns
from oracle_origins import read_saved_origins
from oracle_runner import OracleSession, execute_scenario
from test_oracle_comparison import proof
from test_oracle_origins import handle, record, write_source


SAVE = 'oracle-base-nature'
PLAYER = [66484, 7.25, -90000]
LINE = 'Squad size multiplier=1'
FACTS = dict(squad_size=dict(source='engine_facts', multiplier=1.0, line=LINE,
                             sha256=hashlib.sha256(LINE.encode('utf-8')).hexdigest(), path='settings.cfg'))
SCENARIO = Path(__file__).resolve().parents[1] / 'scenarios' / 'nature-bandit-ambush.json'


def person(identity, faction, squad, position):
    return dict(id=identity, name='Synthetic', race_id='fixture-race', faction_id=faction, squad_id=squad,
                position=list(position), state='alive',
                health=[dict(id='fixture-head:neither', current=60, stun=5, maximum=100)], order=None,
                identity_origin='saved', current_town_id=None, town_assignment=None, in_combat=False)


def initial_state(ids):
    player, bystander, squad = ids
    return dict(schema_version='0.2', clock=dict(day=2, hour=12, elapsed_seconds=216000, speed=0, paused=True),
                characters=[person(player, '204-gamedata.base', squad, PLAYER),
                            person(bystander, 'fixture-bystander', squad, [PLAYER[0] + 3000, 0, PLAYER[2]])],
                squads=[dict(id=squad, faction_id='204-gamedata.base', members=sorted([player, bystander]),
                             leader_id=player, identity_origin='saved', template_id=None, origin_town_id=None)],
                factions=[dict(id='204-gamedata.base', name='Player'), dict(id='fixture-bystander', name='B')],
                relations=[])


class EngineProbe(FakeProbe):
    """FakeProbe dumping state 0.2, as either target; spawned rows get the 0.2 fields."""
    def __init__(self, *args, target='original', **kwargs):
        super().__init__(*args, **kwargs)
        self.target = target
        self.seed = '999' if target == 'meitou' else None
        self.player_faction_id = '204-gamedata.base'
        self.extra_factions = {'200-gamedata.base': 'Dust Bandits'}
        self.squad_templates = {'3372-gamedata.base': ['3371-gamedata.base'] + ['1304-gamedata.base'] * 3}
        self.other_templates = {'3371-gamedata.base', '1304-gamedata.base'}
        if target == 'meitou':
            self.squad_size = dict(FACTS['squad_size'], source='settings.cfg')

    async def call(self, command, **params):
        if command == 'load_save' and 'seed' in params:
            if self.target != 'meitou':
                raise AssertionError('The original takes no seed')
            self.seed = params.pop('seed')
        result = await super().call(command, **params)
        if command in ('ping', 'heartbeat'):
            result.update(schema_version='0.2', supported_schema_versions=['0.1', '0.2'])
            if self.target == 'meitou':
                result.update(target='meitou', seed=self.seed, seed_applied_before_load=True,
                              seed_source='oracle_load_override')
        if command == 'setup_spawn_squad' and self.target == 'meitou':
            result = dict(result, rng_key=str(4000 + self._setup_serial))
        for row in self.state['characters']:
            for key, value in (('identity_origin', 'generated'), ('current_town_id', None),
                               ('town_assignment', None), ('in_combat', False)):
                row.setdefault(key, value)
        for row in self.state['squads']:
            for key, value in (('identity_origin', 'generated'), ('template_id', '3372-gamedata.base'),
                               ('origin_town_id', None)):
                row.setdefault(key, value)
        return result


def synthetic_save(root):
    records = [record(30, 'collection', instances=[(f'instance-{i}', [f'character-{i}']) for i in range(2)])]
    records += [record(36, f'character-{i}', int=handle(slot=i + 1, object_serial=1000 + i)) for i in range(2)]
    (root / 'saves').mkdir()
    write_source(root / 'saves', platoons={'synthetic.platoon': records}, name=SAVE)
    manifest = read_saved_origins(root / 'saves', SAVE)
    saved = [row['saved_id'] for row in manifest['characters'][:2]] + [manifest['squads'][0]['saved_id']]
    return saved, manifest['fingerprint']


async def campaign(root, target, scenario, saved, fingerprint, commit):
    if target == 'original':
        raw = ['char:player', 'char:bystander', 'squad:player']
        fake = EngineProbe(root / ('native-' + target), initial_state(raw), save_root=root / 'saves',
                           require_saved_origins=True, origin_aliases=dict(zip(saved, raw)), target=target)
    else:
        fake = EngineProbe(root / ('native-' + target), initial_state(saved), save_root=root / 'saves',
                           target=target)
    fake.build_commit = commit
    profile = root / ('engine-profile-' + target + '.json')
    profile.write_text(json.dumps(dict(profile_format='engine-profile-0.1', entries=[dict(
        target=target, save=SAVE, source_fingerprint=fingerprint, seed=None,
        player=dict(xz=[PLAYER[0], PLAYER[2]], y_before_settle=7.25, y_after_settle=7.25, decimals=3),
        evidence='synthetic')])), encoding='utf-8')
    cfg = dict(runtime=str(root / ('runtime-' + target)), runs=str(root / ('runs-' + target)),
               oracle_output=str(fake.output_directory), timeout=2, load_timeout=3, run_until_timeout=2,
               scenario_timeout=120, engine_profile=str(profile), base_seed=1000)
    await OracleSession(cfg, fake).load(SAVE, lock_edge=False, **({'seed': 999} if target == 'meitou' else {}))
    await fake.call('set_game_speed', speed=1, preserve_pause=True)
    facts = FACTS if target == 'original' and 'setup' in scenario else None
    result = await execute_scenario(scenario, cfg, client=fake, engine_facts=facts)
    path = Path(result['report'])
    report = json.loads(path.read_text(encoding='utf-8'))
    if target == 'original':
        report['reference_profile'] = proof(restored=True)
        for execution in report['executions']:
            execution['reference_profile'] = proof()
            for capture in execution['checkpoints']:
                capture['reference_profile'] = proof()
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return path, report


def run_both(tmp_path, scenario, commit='0123456789abcdef0123456789abcdef01234567'):
    saved, fingerprint = synthetic_save(tmp_path)
    if callable(scenario):
        scenario = scenario(saved)
    return {target: asyncio.run(campaign(tmp_path, target, scenario, saved, fingerprint, commit))
            for target in ('original', 'meitou')}


def scenario_01(saved):
    return dict(schema_version='0.1', name='synthetic-v01', save=SAVE, speed=1, repeat=2,
                actions=[dict(at=0, command='issue_order',
                              params=dict(type='move', character_id=saved[0], position=[1, 2, 3])),
                         dict(at=10, command='pause', params=dict(paused=True))],
                checkpoints=[dict(at=0, name='initial'), dict(at=3, name='t3'), dict(at=10, name='fin')])


def test_nature_bandit_ambush_runs_on_both_targets_and_compares(tmp_path):
    scenario = json.loads(SCENARIO.read_text(encoding='utf-8'))
    scenario['repeat'] = 2
    campaigns = run_both(tmp_path, scenario)
    for target, (_, report) in campaigns.items():
        assert report['status'] == 'completed' and report['restoration']['verified'] is True
        assert report['limitations'] == ['war flag not observable on ' + target]
        receipts = [execution['setup'] for execution in report['executions']]
        assert all(receipt['verdict'] == 'passed' and receipt['target'] == target for receipt in receipts)
        assert receipts[0]['alias_map'].keys() == receipts[1]['alias_map'].keys()
        assert receipts[0]['alias_map']['bandits'] != receipts[1]['alias_map']['bandits']
        keys = [row['rng_key'] for row in receipts[0]['members'] if row['alias'] != 'player']
        assert keys == ([None] * 4 if target == 'original' else ['4001'] * 4)
        assert receipts[0]['squad_size']['source'] == ('engine_facts' if target == 'original' else 'setup_info')
    seeds = [execution['provenance']['seed'] for execution in campaigns['meitou'][1]['executions']]
    assert seeds == ['1000', '1001']
    output = tmp_path / 'comparison'
    result = compare_campaigns(campaigns['original'][0], campaigns['meitou'][0], output, minimum_repetitions=2)
    comparison = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    findings = comparison['findings']
    assert findings and all(row['metric'].startswith('/scene/') for row in findings)
    assert result['classifications'] == {'stable_identical': len(findings)}
    metrics = {row['metric'] for row in findings}
    assert '/scene/intruders/count' in metrics
    assert any('200-gamedata.base' in metric and '204-gamedata.base' in metric for metric in metrics)
    assert 'original: war flag not observable on original' in comparison['limitations']
    assert 'meitou: war flag not observable on meitou' in comparison['limitations']
    text = (output / 'report.json').read_text(encoding='utf-8') + (output / 'report.md').read_text(encoding='utf-8')
    assert 'local:fake' not in text  # Spawned engine ids never reach the comparison.


@pytest.mark.parametrize('commit', [None, 'unknown'])
def test_scenario_01_campaigns_without_a_known_commit(tmp_path, commit):
    campaigns = run_both(tmp_path, scenario_01, commit=commit)
    for _, report in campaigns.values():
        assert report['status'] == 'completed' and report['build_commit'] == commit
        assert report['build_commit_known'] is False
    output = tmp_path / 'comparison'
    if commit == 'unknown':
        # Q10: the runner accepts an unknown commit, the comparator refuses it.
        with pytest.raises(ValueError, match='build commit is unknown'):
            compare_campaigns(campaigns['original'][0], campaigns['meitou'][0], output, minimum_repetitions=2)
        return
    compare_campaigns(campaigns['original'][0], campaigns['meitou'][0], output, minimum_repetitions=2)
    comparison = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    assert comparison['limitations'].count('build commit not recorded') == 1
    assert comparison['original']['build_commit'] is None and comparison['meitou']['build_commit'] is None
