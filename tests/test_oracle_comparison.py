"""Campaign certification and local reports from synthetic, canonical snapshots only."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from oracle_comparison import (aggregate_metrics, compare_campaigns, load_campaign,
                               reference_proof, snapshot_metrics)
from oracle_schema import canonical_bytes
from original_reference import SUPPORTED_REK_HASH
from rekenshi_profile import KNOWN_DEVIATIONS, REQUESTED_SETTINGS, ReKenshiProfileError
from test_oracle_compare import FIRST, state


FINGERPRINT = 'sha256:' + 'a' * 64
SCENARIO = dict(schema_version='0.1', name='synthetic-comparison', save='Synthetic save',
                speed=1, repeat=5, actions=[],
                checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])


def proof(*, restored=False):
    """Structurally certified test fixture, never evidence about an actual executable."""
    exports = {symbol: dict(symbol=symbol, export_rva=4096 + index*32, disk_file_offset=1024 + index*32,
        checked_bytes=16, disk_prefix_hex='90'*16, memory_prefix_hex='90'*16,
        unmodified=True, relocation_overlap=False, comparison='identical')
        for index, symbol in enumerate(('rand', 'srand'))}
    evidence = dict(settings=deepcopy(REQUESTED_SETTINGS), verification_method='rekenshi_0_3_5_ui_and_crt_exports',
        evidence_source='runtime_ui', process_id=42, instance_id='synthetic-instance', crt_exports=exports,
        crt_exports_unmodified=True, crt_exports_modified=False, runtime_settings_consistent=True,
        effective_fix_rng_disabled=True, rng_hook_owner_verified=False)
    return dict(profile='kenshi-1.0.65-rekenshi-0.3.5-rng-off-custom-speeds-off',
        transaction_id='synthetic-transaction', state='restored' if restored else 'verified',
        restore_required=not restored,
        metadata=dict(kenshi_version='1.0.65', rekenshi_version='0.3.5',
                      rekenshi_sha256=SUPPORTED_REK_HASH, executable_sha256='b'*64),
        before=dict(settings=dict.fromkeys(REQUESTED_SETTINGS, True), sha256='c'*64),
        requested=deepcopy(REQUESTED_SETTINGS), prepared_sha256='d'*64, verification_failure=None,
        effective=dict(verified_at=1002, process=dict(running=True, owned=True, pid=42,
                       instance_id='synthetic-instance', started_at=1001), evidence=evidence),
        restoration=dict(file_verified=restored, runtime_verified=restored),
        known_deviations=deepcopy(KNOWN_DEVIATIONS))


def campaign(folder, target, *, n=5, scenario=None, snapshot=None, receipt=None, commit=None):
    """Synthetic campaign; ``snapshot``, ``receipt`` and ``commit`` shape 0.11 scene-setup reports."""
    folder.mkdir()
    scenario = deepcopy(SCENARIO if scenario is None else scenario)
    scenario['repeat'] = n
    report = dict(target=target, status='completed', restoration=dict(verified=True),
                  scenario=scenario, repeat=n, source_fingerprint=FINGERPRINT, executions=[])
    if commit is not None:
        report.update(report_format='0.1', scenario_schema=scenario['schema_version'], state_schema='0.2',
                      build_commit=commit, build_commit_known=commit != 'unknown',
                      limitations=['commit unknown'] if commit == 'unknown' else [])
    if target == 'original':
        report['reference_profile'] = proof(restored=True)
    for index in range(1, n+1):
        execution = dict(execution=index, status='completed', checkpoints=[],
                         load=dict(source_manifest=dict(prepared=True, save_name=scenario['save'],
                                   source_fingerprint=FINGERPRINT, count=3), ready={}))
        if target == 'original':
            execution['reference_profile'] = proof()
        else:
            execution['provenance'] = dict(target='meitou', seed=str(1000+index),
                seed_source='oracle_load_override', seed_applied_before_load=True)
            execution['load']['ready'] = deepcopy(execution['provenance'])
        if receipt is not None:
            execution['setup'] = receipt(target, index, scenario)
        for point in scenario['checkpoints']:
            values = state() if snapshot is None else snapshot(target, index, point)
            at = point['at']
            values['clock'].update(elapsed_seconds=216000+at, hour=12+at/3600)
            if snapshot is None:
                values['characters'][0]['position'][0] = (10 if target == 'meitou' else 0) + at
            if point['name'] == 'initial':
                execution['initial_clock'] = deepcopy(values['clock'])
            output = folder / str(index) / (point['name'] + '.json')
            output.parent.mkdir(exist_ok=True)
            payload = canonical_bytes(values)
            output.write_bytes(payload)
            published = json.loads(payload)
            capture = dict(name=point['name'], path=output.relative_to(folder).as_posix(),
                sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload), schema_version='0.2',
                requested_at=at, actual_at=at, overshoot_seconds=0, clock=deepcopy(published['clock']))
            if target == 'original':
                capture['reference_profile'] = proof()
            else:
                capture['provenance'] = deepcopy(execution['provenance'])
            if receipt is not None:
                capture['setup'] = dict(setup_hash=execution['setup']['setup_hash'],
                    alias_map=deepcopy(execution['setup']['alias_map']),
                    census=dict(count=4, truncated=False, alive_count=4, dead_count=0,
                                unconscious_count=0, player_count=1))
            execution['checkpoints'].append(capture)
        report['executions'].append(execution)
    save_report(folder, report)
    return report


def save_report(folder, report):
    (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')


@pytest.fixture
def campaigns(tmp_path):
    original, meitou = tmp_path/'original', tmp_path/'meitou'
    left, right = campaign(original, 'original'), campaign(meitou, 'meitou')
    output = tmp_path/'comparisons'/'report'
    return original, meitou, left, right, output


def test_complete_five_by_five_comparison_writes_relative_equivalent_reports_and_english_drafts(campaigns):
    original, meitou, left, right, output = campaigns
    result = compare_campaigns(original, meitou, output)
    assert result['original_n'] == result['meitou_n'] == 5
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    markdown = (output/'report.md').read_text(encoding='utf-8')
    assert report['source_fingerprint'] == FINGERPRINT
    assert report['original']['n'] == report['meitou']['n'] == 5
    assert report['meitou']['seeds'] == [str(value) for value in range(1001, 1006)]
    assert report['findings'][0]['classification'] == 'stable_divergent'
    metric = next(row for row in report['findings'] if row['metric'] == f'/characters/{FIRST}/position/0')
    assert metric['classification'] == 'stable_divergent'
    for row in metric['original']['observations']:
        assert row['snapshot'].startswith('../../original/')
        assert (output/row['snapshot']).resolve().is_relative_to(original)
    assert '../../original/' in markdown and 'Original N = 5' in markdown
    assert str(output.parent.parent) not in json.dumps(report)
    drafts = list((output/'issues').glob('*.md'))
    assert drafts
    text = drafts[0].read_text(encoding='utf-8')
    assert 'Local draft for review. No issue has been published.' in text
    assert 'Original N=5; Meitou N=5' in text
    assert '../../../original/' in text
    assert all(row['classification'] != 'known_deviation' for row in report['findings'])


@pytest.mark.parametrize('scope', ['report', 'execution', 'capture'])
def test_original_reference_provenance_required_at_every_scope(campaigns, scope):
    original, meitou, report, _, output = campaigns
    owner = (report if scope == 'report' else report['executions'][0] if scope == 'execution'
             else report['executions'][0]['checkpoints'][0])
    del owner['reference_profile']
    save_report(original, report)
    with pytest.raises(ValueError, match='provenance'):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


@pytest.mark.parametrize('flag', list(REQUESTED_SETTINGS))
def test_each_reference_simulation_override_must_be_verified_false(campaigns, flag):
    original, meitou, report, _, output = campaigns
    report['executions'][0]['checkpoints'][0]['reference_profile']['effective']['evidence']['settings'][flag] = True
    save_report(original, report)
    with pytest.raises(ReKenshiProfileError):
        compare_campaigns(original, meitou, output)


def test_original_reference_requires_independent_crt_bytes_and_audited_build(campaigns):
    original, meitou, report, _, output = campaigns
    report['reference_profile']['metadata']['rekenshi_sha256'] = 'f'*64
    save_report(original, report)
    with pytest.raises(ValueError, match='audited'):
        compare_campaigns(original, meitou, output)
    report['reference_profile'] = proof(restored=True)
    del report['reference_profile']['effective']['evidence']['crt_exports']['rand']
    save_report(original, report)
    with pytest.raises(ReKenshiProfileError, match='exports'):
        compare_campaigns(original, meitou, output)


def test_player_profile_and_controls_restoration_are_part_of_acceptance(campaigns):
    original, meitou, report, _, output = campaigns
    report['reference_profile']['restoration']['runtime_verified'] = False
    save_report(original, report)
    with pytest.raises(ValueError, match='restoration'):
        compare_campaigns(original, meitou, output)
    report['reference_profile'] = proof(restored=True)
    report['restoration']['verified'] = False
    save_report(original, report)
    with pytest.raises(ValueError, match='controls'):
        compare_campaigns(original, meitou, output)


@pytest.mark.parametrize('leading_zero', [False, True])
def test_meitou_repetitions_require_distinct_numeric_seeds(campaigns, leading_zero):
    original, meitou, _, report, output = campaigns
    seed = ('0' if leading_zero else '') + report['executions'][0]['provenance']['seed']
    second = report['executions'][1]
    second['provenance']['seed'] = seed
    second['load']['ready']['seed'] = seed
    for capture in second['checkpoints']:
        capture['provenance']['seed'] = seed
    save_report(meitou, report)
    with pytest.raises(ValueError, match='seed'):
        compare_campaigns(original, meitou, output)


@pytest.mark.parametrize('mutation', ['unknown', 'after_load', 'capture_mismatch'])
def test_meitou_seed_provenance_is_known_before_loading_and_consistent_per_capture(campaigns, mutation):
    original, meitou, _, report, output = campaigns
    execution = report['executions'][0]
    if mutation == 'unknown':
        execution['provenance']['seed'] = None
    elif mutation == 'after_load':
        execution['provenance']['seed_applied_before_load'] = False
    else:
        execution['checkpoints'][0]['provenance']['seed'] = '999'
    save_report(meitou, report)
    with pytest.raises(ValueError, match='seed'):
        compare_campaigns(original, meitou, output)


def test_different_source_fingerprint_between_targets_or_repetitions_is_rejected(campaigns):
    original, meitou, _, report, output = campaigns
    report['source_fingerprint'] = 'sha256:' + 'b'*64
    for execution in report['executions']:
        execution['load']['source_manifest']['source_fingerprint'] = report['source_fingerprint']
    save_report(meitou, report)
    with pytest.raises(ValueError, match='fingerprint'):
        compare_campaigns(original, meitou, output)
    report['source_fingerprint'] = FINGERPRINT
    save_report(meitou, report)
    with pytest.raises(ValueError, match='starting save'):
        compare_campaigns(original, meitou, output)


@pytest.mark.parametrize('mutation', ['wrong_hash', 'noncanonical', 'different_schema', 'external'])
def test_snapshot_hash_schema_canonical_bytes_and_physical_containment_are_checked(campaigns, mutation):
    original, meitou, report, _, output = campaigns
    capture = report['executions'][0]['checkpoints'][0]
    file = original/capture['path']
    if mutation == 'wrong_hash':
        capture['sha256'] = '0'*64
    elif mutation == 'noncanonical':
        file.write_bytes(file.read_bytes() + b' ')
    elif mutation == 'different_schema':
        snapshot = state()
        snapshot['schema_version'] = '0.1'
        for character in snapshot['characters']:
            for key in ('identity_origin', 'current_town_id', 'town_assignment', 'in_combat'):
                del character[key]
        for squad in snapshot['squads']:
            for key in ('identity_origin', 'template_id', 'origin_town_id'):
                del squad[key]
        file.write_bytes(canonical_bytes(snapshot))
        capture['sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
    else:
        destination = original.parent/'outside.json'
        destination.write_bytes(file.read_bytes())
        capture['path'] = '../outside.json'
    save_report(original, report)
    with pytest.raises(ValueError):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


def test_minimum_n_and_unique_complete_executions_are_required(campaigns):
    original, meitou, report, _, output = campaigns
    report['executions'][1]['execution'] = 1
    save_report(original, report)
    with pytest.raises(ValueError, match='repetitions'):
        compare_campaigns(original, meitou, output)


def test_below_five_requires_explicit_minimum_and_remains_visible(tmp_path):
    original, meitou = tmp_path/'original', tmp_path/'meitou'
    campaign(original, 'original', n=4)
    campaign(meitou, 'meitou', n=4)
    with pytest.raises(ValueError, match='minimum'):
        compare_campaigns(original, meitou, tmp_path/'rejected')
    compare_campaigns(original, meitou, tmp_path/'accepted', minimum_repetitions=4)
    report = json.loads((tmp_path/'accepted'/'report.json').read_text(encoding='utf-8'))
    assert report['original']['n'] == report['meitou']['n'] == 4
    assert all(row['warnings'] for row in report['findings'])


def test_group_metrics_use_factions_and_templates_not_generated_identity_correspondence():
    baseline = state()
    for row in baseline['characters']:
        row.update(identity_origin=None)
    later = deepcopy(baseline)
    later['characters'][0]['state'] = 'dead'
    values = snapshot_metrics(later, baseline)
    prefix = '/population/by_faction/fixture-faction'
    assert values[prefix+'/loaded'] == 2
    assert values[prefix+'/alive'] == 1 and values[prefix+'/dead'] == 1
    assert values[prefix+'/unpaired'] == 2
    assert values['/population/by_squad_template/fixture-faction/fixture-template/loaded_members'] == 2
    assert values['/population/by_town/coverage'] is None
    missing = deepcopy(later)
    missing['characters'].pop(0)
    values = snapshot_metrics(missing, baseline)
    assert values['/combat/starting_cohort/fixture-faction/survivors'] is None
    assert values['/combat/starting_cohort/fixture-faction/dead'] is None
    assert values['/combat/starting_cohort/fixture-faction/missing'] == 1


def test_directional_relation_change_is_measured_against_each_own_initial_checkpoint():
    baseline = state()
    baseline['factions'].append(dict(id='other-faction', name='Other synthetic faction'))
    baseline['relations'] = [dict(source_id='fixture-faction', target_id='other-faction', value=2),
                             dict(source_id='other-faction', target_id='fixture-faction', value=7)]
    later = deepcopy(baseline)
    later['relations'][0]['value'] = -3
    values = snapshot_metrics(later, baseline)
    assert values['/relations/fixture-faction/other-faction/change_from_first_checkpoint'] == -5
    assert values['/relations/other-faction/fixture-faction/change_from_first_checkpoint'] == 0
    later['relations'][0]['value'] = None
    assert snapshot_metrics(later, baseline)['/relations/fixture-faction/other-faction/change_from_first_checkpoint'] is None


@pytest.mark.parametrize('scope,key,value', [
    ('ready', 'seed', '999'), ('ready', 'target', 'original'),
    ('ready', 'seed_source', 'unknown'), ('ready', 'seed_applied_before_load', False),
    ('capture', 'target', 'original'), ('capture', 'seed_source', 'unknown'),
    ('capture', 'seed_applied_before_load', False)])
def test_ready_and_capture_bind_all_seed_provenance_fields_to_the_execution(campaigns, scope, key, value):
    original, meitou, _, report, output = campaigns
    execution = report['executions'][0]
    owner = execution['load']['ready'] if scope == 'ready' else execution['checkpoints'][0]['provenance']
    owner[key] = value
    save_report(meitou, report)
    with pytest.raises(ValueError, match='seed|provenance'):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


@pytest.mark.parametrize('mutation', ['missing_initial_clock', 'actual_at', 'overshoot',
                                    'before_requested', 'capture_clock', 'snapshot_elapsed'])
def test_checkpoint_temporal_metadata_is_bound_to_canonical_clock_and_execution_origin(campaigns, mutation):
    original, meitou, report, _, output = campaigns
    execution = report['executions'][0]
    capture = execution['checkpoints'][1]
    if mutation == 'missing_initial_clock':
        del execution['initial_clock']
    elif mutation == 'actual_at':
        capture['actual_at'] += 1
    elif mutation == 'overshoot':
        capture['overshoot_seconds'] = 1
    elif mutation == 'before_requested':
        capture.update(actual_at=1, overshoot_seconds=-1)
    elif mutation == 'capture_clock':
        capture['clock']['elapsed_seconds'] += 1
    else:
        file = original/capture['path']
        snapshot = json.loads(file.read_bytes())
        snapshot['clock']['elapsed_seconds'] += 1
        payload = canonical_bytes(snapshot)
        file.write_bytes(payload)
        capture.update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
    save_report(original, report)
    with pytest.raises(ValueError):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


def test_snapshot_size_is_bounded_before_any_unbounded_read(campaigns, monkeypatch):
    original, meitou, report, _, output = campaigns
    source = original/report['executions'][0]['checkpoints'][0]['path']
    stat, read_bytes = Path.stat, Path.read_bytes
    def oversized(path, *args, **kwargs):
        result = stat(path, *args, **kwargs)
        if path == source:
            result = os.stat_result((*result[:6], 64*1024*1024+1, *result[7:]))
        return result
    def reject_unbounded(path):
        if path == source:
            raise AssertionError('Unbounded snapshot read occurred before its size limit')
        return read_bytes(path)
    monkeypatch.setattr(Path, 'stat', oversized)
    monkeypatch.setattr(Path, 'read_bytes', reject_unbounded)
    with pytest.raises(ValueError, match='size|limit|large'):
        compare_campaigns(original, meitou, output)


def test_unknown_squad_template_coverage_does_not_certify_partial_group_counts():
    baseline = state()
    baseline['squads'].append(dict(id='local:unproven', faction_id='fixture-faction', members=[],
        leader_id=None, identity_origin=None, template_id=None, origin_town_id=None))
    values = snapshot_metrics(baseline, baseline)
    prefix = '/population/by_squad_template/fixture-faction/fixture-template'
    assert values[prefix+'/squads'] is None
    assert values[prefix+'/loaded_members'] is None


def test_absent_template_group_is_zero_only_with_complete_known_squad_coverage():
    original = state()
    meitou = deepcopy(original)
    meitou['squads'].clear()
    for character in meitou['characters']:
        character['squad_id'] = None
    left = [dict(repetition=1, snapshot='original/1/initial.json', state=original)]
    right = [dict(repetition=1, snapshot='meitou/1/initial.json', state=meitou)]
    findings = aggregate_metrics(left, right, {1: original}, {1: meitou})
    prefix = '/population/by_squad_template/fixture-faction/fixture-template'
    finding = next(row for row in findings if row['metric'] == prefix+'/squads')
    assert finding['classification'] == 'stable_divergent'
    assert finding['original']['values'] == [1] and finding['meitou']['values'] == [0]
    meitou['squads'].append(dict(id='local:unproven', faction_id='fixture-faction', members=[],
        leader_id=None, identity_origin=None, template_id=None, origin_town_id=None))
    findings = aggregate_metrics(left, right, {1: original}, {1: meitou})
    finding = next(row for row in findings if row['metric'] == prefix+'/squads')
    assert finding['classification'] == 'not_comparable'
    assert finding['meitou']['values'] == [None]


# Scene scope (scenario-0.2 with a setup block, docs/scene-setup.md). The
# receipts follow the W7 receipt format; every id and record is synthetic.

PLAYER, BYSTANDER = 'hand:1:7:101:1:1001', 'hand:1:7:101:2:1002'
PLAYER_SQUAD, BYSTANDER_SQUAD = 'hand:34:7:101:0:0', 'hand:34:7:101:0:1'
COMMITS = dict(original='a'*40, meitou='b'*40)
# Spawned ids differ between engines; members are matched only by (alias, template).
SPAWNED = dict(original=(['hand:1:9:300:1:%d' % k for k in (1, 2, 3)], 'hand:34:9:300:0:0'),
               meitou=(['local:spawn-%d' % k for k in (7, 8, 9)], 'local:squad-4'))
TEMPLATES = ['leader.base', 'grunt.base', 'grunt.base']
PAIR = ('enemy-faction', 'player-faction')
SETUP_SCENARIO = dict(
    schema_version='scenario-0.2', name='synthetic-scene', save='Synthetic save', speed=1, repeat=5,
    setup=dict(
        preflight=dict(scene_center=[0, 0], scene_radius=1500, squad_size_multiplier=1,
                       player_faction_id='player-faction', expect_absent_factions_in_scene=['enemy-faction']),
        moves=[],
        spawns=[dict(alias='raiders', squad_template='squad-template.base', count=3,
                     faction_id='enemy-faction', at=dict(offset_from_player=[30, 0]),
                     expected_templates={'leader.base': 1, 'grunt.base': 2})],
        settle=dict(sim_seconds=1), heal='all_scene_characters',
        relations=[dict(a='enemy-faction', b='player-faction', a_to_b=-60, b_to_a=-60)]),
    actions=[dict(at=0, command='issue_order',
                  params=dict(type='attack', squad_alias='raiders', target_alias='player'))],
    checkpoints=[dict(at=0, name='initial'), dict(at=2, name='later')])


def contract_hash(setup):
    """The receipt rule of docs/scene-setup.md, written independently of oracle_scope."""
    return hashlib.sha256(json.dumps(setup, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def spawned(target, index):
    members, squad = SPAWNED[target]
    return [member.replace('spawn-', f'spawn-{index}-') for member in members], squad


def alias_map(target, index):
    members, squad = spawned(target, index)
    return {'player': PLAYER, 'raiders': squad, 'raiders/leader.base/1': members[0],
            'raiders/grunt.base/1': members[1], 'raiders/grunt.base/2': members[2]}


def receipt_steps(aliases):
    """One synthetic step per S0..S6 command, in order, in the receipt step shape."""
    census = ('setup_area_census', dict(center=[0, 0, 0], radius=1500, limit=100))
    commands = [('S0', 'get_clock', {}), ('S0', 'setup_info', {}), ('S0', *census),
                ('S2', 'setup_spawn_squad', dict(template_id='squad-template.base', faction_id='enemy-faction',
                                                 position=[30, 0, 0], max_count=3)),
                ('S2', *census), ('S3', 'set_game_speed', dict(speed=1, preserve_pause=True)),
                ('S3', 'get_clock', {}), ('S3', 'run_until', dict(elapsed_seconds=216033)),
                ('S3b', 'dump_state', dict(path='setup/S3b.json'))]
    commands += [('S5', 'setup_heal', dict(character_id=aliases[alias])) for alias in aliases if alias != 'raiders']
    commands += [('S5', 'dump_state', dict(path='setup/S5.json')),
                 ('S4', 'setup_set_relation', dict(source_id=PAIR[0], target_id=PAIR[1], value=-60)),
                 ('S4', 'setup_set_relation', dict(source_id=PAIR[1], target_id=PAIR[0], value=-60)),
                 ('S6', 'dump_state', dict(path='setup/S6.json')), ('S6', *census)]
    return [dict(step=step, request=dict(command=command, params=params), reply={}, read_back={},
                 verdict='passed') for step, command, params in commands]


def receipt(target, index, scenario):
    aliases = alias_map(target, index)
    members = [dict(alias=alias, id=aliases[alias], template_id=alias.split('/')[1] if '/' in alias else None,
                    faction_id='player-faction' if alias == 'player' else 'enemy-faction',
                    part_max={'fixture-head:neither': 100 + index if target == 'original' else 100},
                    blood_before=80, blood_after=100, rng_key=None if target == 'original' else str(index))
               for alias in aliases if alias != 'raiders']
    return dict(receipt_format='scene-setup-0.1', target=target, setup_hash=contract_hash(scenario['setup']),
                build_commit=COMMITS[target], build_commit_known=True, alias_map=aliases, steps=receipt_steps(aliases),
                dumps={name: dict(path=f'setup/{name}.json', sha256='0'*64) for name in ('S3b', 'S5', 'S6')},
                members=members, squad_size=dict(source='setup_info', multiplier=1,
                    line='Squad size multiplier=1', sha256='1'*64, path='settings.cfg'),
                settle=dict(sim_seconds=1, calendar_seconds_requested=33, start_seconds=216000,
                            end_seconds=216033, calendar_seconds_run=33, player_before=[0, 0, 0],
                            player_after=[0, 0, 0], pin=dict(xz=[0, 0], y_before_settle=0, y_after_settle=0,
                                                              decimals=3),
                            observed=dict(xz=[0, 0], y_before_settle=0, y_after_settle=0),
                            delta=dict(xz=[0, 0], y_before_settle=0, y_after_settle=0)),
                limitations=[],
                verdict='passed', failure=None)


def person(identity, faction, squad, position, origin='saved'):
    return dict(id=identity, name='Synthetic ' + identity[-4:], race_id='fixture-race', faction_id=faction,
                squad_id=squad, position=list(position), state='alive',
                health=[dict(id='fixture-head:neither', current=100, stun=0, maximum=100)], order=None,
                identity_origin=origin, current_town_id=None, town_assignment=None, in_combat=False)


def scene_state(target, index, point, tweak=None):
    members, squad = spawned(target, index)
    order = list(range(3)) if target == 'original' else [2, 0, 1]  # Engine order is irrelevant.
    characters = [person(PLAYER, 'player-faction', PLAYER_SQUAD, [0, 0, 0]),
                  person(BYSTANDER, 'bystander-faction', BYSTANDER_SQUAD, [5000, 0, 0])]
    characters += [person(members[k], 'enemy-faction', squad, [30, 0, k], origin='generated') for k in order]
    value = dict(schema_version='0.2', clock=dict(day=2, hour=12, elapsed_seconds=216000, speed=0, paused=True),
        characters=characters,
        squads=[dict(id=PLAYER_SQUAD, faction_id='player-faction', members=[PLAYER], leader_id=PLAYER,
                     identity_origin='saved', template_id=None, origin_town_id=None),
                dict(id=BYSTANDER_SQUAD, faction_id='bystander-faction', members=[BYSTANDER], leader_id=BYSTANDER,
                     identity_origin='saved', template_id='bystander-template', origin_town_id=None),
                dict(id=squad, faction_id='enemy-faction', members=sorted(members), leader_id=members[0],
                     identity_origin='generated', template_id='squad-template.base', origin_town_id=None)],
        factions=[dict(id=faction, name='Synthetic ' + faction)
                  for faction in ('bystander-faction', 'enemy-faction', 'player-faction')],
        relations=[dict(source_id='enemy-faction', target_id='player-faction', value=-60),
                   dict(source_id='player-faction', target_id='enemy-faction', value=-60),
                   dict(source_id='bystander-faction', target_id='player-faction', value=10)])
    if tweak is not None:
        tweak(target, index, point, value)
    return value


def by_alias(value, target, index, alias):
    identity = alias_map(target, index)[alias]
    return next(row for row in value['characters'] if row['id'] == identity)


def scene_campaigns(tmp_path, tweak=None, commits=COMMITS):
    original, meitou = tmp_path/'original', tmp_path/'meitou'
    builder = lambda target, index, point: scene_state(target, index, point, tweak)
    left = campaign(original, 'original', scenario=SETUP_SCENARIO, snapshot=builder, receipt=receipt,
                    commit=commits['original'])
    right = campaign(meitou, 'meitou', scenario=SETUP_SCENARIO, snapshot=builder, receipt=receipt,
                     commit=commits['meitou'])
    return original, meitou, left, right, tmp_path/'comparisons'/'scene'


def scene_report(original, meitou, output):
    compare_campaigns(original, meitou, output)
    return json.loads((output/'report.json').read_text(encoding='utf-8'))


def rows_by_metric(rows, checkpoint='later'):
    return {row['metric']: row for row in rows if row['checkpoint'] == checkpoint}


def values(row, target):
    return [observation['value'] for observation in row[target]]


def test_scene_scope_classifies_only_scene_metrics_and_records_the_rest(tmp_path):
    original, meitou, _, _, output = scene_campaigns(tmp_path)
    report = scene_report(original, meitou, output)
    findings = report['findings']
    assert findings and all(row['metric'].startswith('/scene/')
                            and not row['metric'].startswith('/scene/outcome/') for row in findings)
    assert all(row['classification'] == 'stable_identical' for row in findings)
    assert report['scene_outcome'] and all(row['metric'].startswith('/scene/outcome/') for row in report['scene_outcome'])
    assert report['background_metrics'] and all(row['metric'].startswith('/background/')
                                                for row in report['background_metrics'])
    assert any('outcome and background metrics are not classified' in text for text in report['limitations'])
    assert 'build commit not recorded' not in report['limitations']
    assert report['original']['build_commit'] == 'a'*40 and report['meitou']['build_commit'] == 'b'*40
    assert report['scene_scope']['relation_pairs'] == [list(PAIR), list(reversed(PAIR))]
    for target in ('original', 'meitou'):
        facts = report['setup_members'][target]
        assert [row['repetition'] for row in facts] == [1, 2, 3, 4, 5]
        assert {row['alias'] for row in facts[0]['members']} == {
            'player', 'raiders/leader.base/1', 'raiders/grunt.base/1', 'raiders/grunt.base/2'}
        assert all('id' not in row and 'part_max' in row for fact in facts for row in fact['members'])
    assert [row['members'][0]['part_max'] for row in report['setup_members']['original']] == [
        {'fixture-head:neither': 100 + index} for index in range(1, 6)]
    metrics = [row['metric'] for group in ('findings', 'scene_outcome', 'background_metrics') for row in report[group]]
    for target in ('original', 'meitou'):
        for index in range(1, 6):
            members, squad = spawned(target, index)
            assert not any(identity in metric for identity in [*members, squad] for metric in metrics)
    assert all(PLAYER not in metric for metric in metrics)
    assert '/scene/outcome/characters/alias:player/position/0' in rows_by_metric(report['scene_outcome'])
    for checkpoint in ('initial', 'later'):
        squad = rows_by_metric(findings, checkpoint)['/scene/squads/raiders/present']
        assert squad['classification'] == 'stable_identical' and squad['original']['values'] == [True]*5
    summary = (output/'report.md').read_text(encoding='utf-8')
    assert '## Scene outcome and setup facts' in summary
    assert '| initial | /scene/outcome/cohort/player/dead | 1: 0; 2: 0; 3: 0; 4: 0; 5: 0 |' in summary
    assert '| original | 3 | player | 103 |' in summary and '| meitou | 3 | player | 100 |' in summary
    drafts = list((output/'issues').glob('*.md'))
    assert not drafts


def test_spawn_squad_absence_is_a_classified_presence_difference(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            squad = alias_map(target, index)['raiders']
            value['squads'] = [row for row in value['squads'] if row['id'] != squad]
            for row in value['characters']:
                if row['squad_id'] == squad:
                    row['squad_id'] = None
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    finding = rows_by_metric(report['findings'])['/scene/squads/raiders/present']
    assert finding['classification'] == 'stable_divergent'
    assert finding['original']['values'] == [True]*5 and finding['meitou']['values'] == [False]*5
    initial = rows_by_metric(report['findings'], 'initial')['/scene/squads/raiders/present']
    assert initial['classification'] == 'stable_identical'


def test_aliased_ids_in_values_are_replaced_by_their_alias_label(tmp_path):
    def tweak(target, index, point, value):
        leader = alias_map(target, index)['raiders/leader.base/1']
        by_alias(value, target, index, 'player')['order'] = dict(type='attack', target_id=leader, position=None)
        bystander = next(row for row in value['characters'] if row['id'] == BYSTANDER)
        bystander['order'] = dict(type='attack', target_id=PLAYER, position=None)
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    for checkpoint in ('initial', 'later'):
        target = rows_by_metric(report['scene_outcome'], checkpoint)[
            '/scene/outcome/characters/alias:player/order/target_id']
        assert values(target, 'original') == values(target, 'meitou') == ['alias:raiders/leader.base']*5
        other = rows_by_metric(report['background_metrics'], checkpoint)[
            '/background/characters/' + BYSTANDER.replace('/', '~1') + '/order/target_id']
        assert values(other, 'original') == values(other, 'meitou') == ['alias:player']*5
    text = (output/'report.json').read_text(encoding='utf-8')
    for target in ('original', 'meitou'):
        for index in range(1, 6):
            members, squad = spawned(target, index)
            assert not any(json.dumps(identity) in text for identity in [*members, squad])


def test_unknown_position_outside_the_cohorts_makes_the_intruder_count_not_comparable(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            next(row for row in value['characters'] if row['id'] == BYSTANDER)['position'] = None
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    intruders = rows_by_metric(report['findings'])['/scene/intruders/count']
    assert intruders['classification'] == 'not_comparable'
    assert intruders['original']['values'] == [0]*5 and intruders['meitou']['values'] == [None]*5


def test_setup_hash_rule_matches_the_contract_on_the_shipped_scenario():
    from oracle_scope import setup_hash
    scenario = json.loads((Path(__file__).resolve().parents[1]/'scenarios'/'nature-bandit-ambush.json')
                          .read_text(encoding='utf-8'))
    assert setup_hash(scenario['setup']) == contract_hash(scenario['setup'])
    assert setup_hash(SETUP_SCENARIO['setup']) == contract_hash(SETUP_SCENARIO['setup'])


@pytest.mark.parametrize('mutation', ['unbound_alias', 'missing_alias', 'duplicate_alias', 'spawn_alias'])
def test_receipt_members_must_cover_every_bound_character_alias_once(tmp_path, mutation):
    original, meitou, _, report, output = scene_campaigns(tmp_path)
    members = report['executions'][2]['setup']['members']
    if mutation == 'unbound_alias':
        members[0]['alias'] = 'raiders/grunt.base/9'
    elif mutation == 'missing_alias':
        members.pop()
    elif mutation == 'duplicate_alias':
        members.append(deepcopy(members[0]))
    else:
        members[-1]['alias'] = 'raiders'
    save_report(meitou, report)
    with pytest.raises(ValueError, match='member facts'):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


def test_only_the_declared_relation_pair_is_classified(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            value['relations'][2]['value'] = -90
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    relations = sorted(row['metric'] for row in report['findings'] if '/relations/' in row['metric'])
    assert relations == ['/scene/relations/enemy-faction/player-faction/value'] * 2 + [
        '/scene/relations/player-faction/enemy-faction/value'] * 2
    background = rows_by_metric(report['background_metrics'])
    other = background['/background/relations/bystander-faction/player-faction/value']
    assert values(other, 'original') == [10]*5 and values(other, 'meitou') == [-90]*5
    assert not any(row['metric'].startswith('/background/relations/' + PAIR[0] + '/' + PAIR[1])
                   or row['metric'].startswith('/background/relations/' + PAIR[1] + '/' + PAIR[0])
                   for row in report['background_metrics'])


def test_pair_relation_difference_is_classified(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            value['relations'][0]['value'] = -30
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    finding = rows_by_metric(report['findings'])['/scene/relations/enemy-faction/player-faction/value']
    assert finding['classification'] == 'stable_divergent'


def test_background_difference_gives_no_finding(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            bystander = next(row for row in value['characters'] if row['id'] == BYSTANDER)
            bystander.update(state='dead', position=[6000, 0, 0])
            value['characters'].append(person('local:far-%d' % index, 'bystander-faction', None, [9000, 0, 0],
                                              origin='generated'))
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    assert all(row['classification'] == 'stable_identical' for row in report['findings'])
    background = rows_by_metric(report['background_metrics'])
    position = background['/background/characters/' + BYSTANDER.replace('/', '~1') + '/position/0']
    assert values(position, 'original') == [5000]*5 and values(position, 'meitou') == [6000]*5
    total = background['/background/population/loaded/total']
    assert values(total, 'original') == [5]*5 and values(total, 'meitou') == [6]*5
    assert all('classification' not in row for row in report['background_metrics'])


def test_intruder_inside_the_scene_radius_is_compared(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            value['characters'].append(person('local:intruder-%d' % index, 'bystander-faction', None,
                                              [900, 0, -900], origin='generated'))
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    findings = rows_by_metric(report['findings'])
    intruders = findings['/scene/intruders/count']
    assert intruders['classification'] == 'stable_divergent'
    assert intruders['original']['values'] == [0]*5 and intruders['meitou']['values'] == [1]*5
    assert rows_by_metric(report['findings'], 'initial')['/scene/intruders/count']['classification'] == 'stable_identical'
    assert list((output/'issues').glob('*.md'))


def test_members_are_grouped_by_alias_and_template_not_paired(tmp_path):
    def tweak(target, index, point, value):
        if point['name'] == 'later':
            # A different grunt dies on each engine; the (alias, template) aggregate is equal.
            alias = 'raiders/grunt.base/1' if target == 'original' else 'raiders/grunt.base/2'
            by_alias(value, target, index, alias)['state'] = 'dead'
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    findings = rows_by_metric(report['findings'])
    assert {metric for metric in findings if metric.startswith('/scene/cohort/')} == {
        '/scene/cohort/' + cohort + '/' + field
        for cohort in ('player', 'raiders/grunt.base', 'raiders/leader.base')
        for field in ('missing', 'present', 'size')}
    assert findings['/scene/cohort/raiders/grunt.base/present']['original']['values'] == [2]*5
    assert all(row['classification'] == 'stable_identical' for row in report['findings'])
    dead = rows_by_metric(report['scene_outcome'])['/scene/outcome/cohort/raiders/grunt.base/dead']
    assert values(dead, 'original') == values(dead, 'meitou') == [1]*5
    metrics = [row['metric'] for group in ('findings', 'scene_outcome', 'background_metrics') for row in report[group]]
    assert not any('/grunt.base/1' in metric or '/grunt.base/2' in metric or '/leader.base/1' in metric
                   for metric in metrics)


def test_missing_member_is_a_classified_presence_difference(tmp_path):
    def tweak(target, index, point, value):
        if target == 'meitou' and point['name'] == 'later':
            identity = alias_map(target, index)['raiders/leader.base/1']
            value['characters'] = [row for row in value['characters'] if row['id'] != identity]
            for squad in value['squads']:
                if identity in squad['members']:
                    squad['members'].remove(identity)
                    squad['leader_id'] = None
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    findings = rows_by_metric(report['findings'])
    assert findings['/scene/cohort/raiders/leader.base/missing']['classification'] == 'stable_divergent'
    assert findings['/scene/cohort/raiders/leader.base/missing']['meitou']['values'] == [1]*5


def test_fight_outcome_is_reported_per_repetition_and_never_classified(tmp_path):
    def tweak(target, index, point, value):
        if point['name'] != 'later':
            return
        if target == 'meitou':
            by_alias(value, target, index, 'raiders/leader.base/1')['state'] = 'dead'
            player = by_alias(value, target, index, 'player')
            player.update(state='unconscious', in_combat=True)
            player['health'][0]['current'] = 10
        elif index % 2:
            by_alias(value, target, index, 'raiders/grunt.base/2')['in_combat'] = True
    original, meitou, _, _, output = scene_campaigns(tmp_path, tweak)
    report = scene_report(original, meitou, output)
    assert all(row['classification'] == 'stable_identical' for row in report['findings'])
    assert not any('/outcome/' in row['metric'] for row in report['findings'])
    outcome = rows_by_metric(report['scene_outcome'])
    leader = outcome['/scene/outcome/cohort/raiders/leader.base/dead']
    assert values(leader, 'original') == [0]*5 and values(leader, 'meitou') == [1]*5
    assert [row['repetition'] for row in leader['original']] == [1, 2, 3, 4, 5]
    assert all(row['snapshot'].startswith('../../original/') for row in leader['original'])
    health = outcome['/scene/outcome/cohort/player/health/current_total']
    assert values(health, 'original') == [100]*5 and values(health, 'meitou') == [10]*5
    state_row = outcome['/scene/outcome/characters/alias:player/state']
    assert values(state_row, 'meitou') == ['unconscious']*5
    engagement = rows_by_metric(report['scene_outcome'], 'whole_scenario')
    grunts = engagement['/scene/outcome/engagement/raiders/grunt.base/engagement_observed']
    assert values(grunts, 'original') == [True, False, True, False, True]
    assert values(grunts, 'meitou') == [False]*5
    player = engagement['/scene/outcome/engagement/player/engagement_observed']
    assert values(player, 'meitou') == [True]*5
    background = rows_by_metric(report['background_metrics'], 'whole_scenario')
    assert set(background) >= {'/background/combat/engagement_by_faction/bystander-faction/engagement_observed'}
    assert not any(metric.startswith(('/background/combat/engagement_by_faction/enemy-faction',
                                      '/background/combat/engagement_by_faction/player-faction'))
                   for metric in background)
    assert not any(metric.startswith('/background/trajectory/saved_squad/' + PLAYER_SQUAD) for metric in background)


@pytest.mark.parametrize('mutation', ['receipt_hash', 'scenario_setup', 'capture_hash'])
def test_setup_hash_mismatch_is_rejected(tmp_path, mutation):
    original, meitou, report, _, output = scene_campaigns(tmp_path)
    execution = report['executions'][2]
    if mutation == 'receipt_hash':
        execution['setup']['setup_hash'] = 'f'*64
    elif mutation == 'scenario_setup':
        # The scenario still validates, but no longer matches what the receipt hashed.
        report['scenario']['setup']['relations'][0]['b_to_a'] = -61
    else:
        execution['checkpoints'][1]['setup']['setup_hash'] = 'f'*64
    save_report(original, report)
    with pytest.raises(ValueError, match='hash'):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


@pytest.mark.parametrize('mutation', ['capture_id', 'capture_missing', 'undeclared_alias',
                                    'missing_alias', 'player_forms', 'duplicate_member'])
def test_alias_map_mismatch_is_rejected(tmp_path, mutation):
    original, meitou, _, report, output = scene_campaigns(tmp_path)
    execution = report['executions'][1]
    aliases = execution['setup']['alias_map']
    if mutation == 'capture_id':
        execution['checkpoints'][0]['setup']['alias_map']['raiders/grunt.base/1'] = 'local:other'
    elif mutation == 'capture_missing':
        del execution['checkpoints'][1]['setup']
    elif mutation == 'undeclared_alias':
        aliases['raiders/grunt.base/3'] = 'local:extra'
    elif mutation == 'missing_alias':
        del aliases['raiders/grunt.base/2']
    elif mutation == 'player_forms':
        aliases['player/1'] = aliases.pop('player')
    else:
        aliases['raiders/grunt.base/2'] = aliases['raiders/grunt.base/1']
    if mutation not in ('capture_id', 'capture_missing'):
        for capture in execution['checkpoints']:
            capture['setup']['alias_map'] = deepcopy(aliases)
    save_report(meitou, report)
    with pytest.raises(ValueError, match='alias'):
        compare_campaigns(original, meitou, output)
    assert not output.exists()


def test_alias_set_must_be_the_same_in_every_repetition(tmp_path):
    original, meitou, report, _, output = scene_campaigns(tmp_path)
    execution = report['executions'][3]
    aliases = execution['setup']['alias_map']
    aliases['player/1'] = aliases.pop('player')
    aliases['player/2'] = BYSTANDER
    for member in execution['setup']['members']:
        if member['alias'] == 'player':
            member['alias'] = 'player/1'
            second = dict(member, alias='player/2', id=BYSTANDER)
    execution['setup']['members'].append(second)  # A complete receipt: one row per character alias.
    for capture in execution['checkpoints']:
        capture['setup']['alias_map'] = deepcopy(aliases)
    save_report(original, report)
    with pytest.raises(ValueError, match='alias sets differ'):
        compare_campaigns(original, meitou, output)


@pytest.mark.parametrize('mutation', ['verdict', 'failure', 'receipt_absent', 'format', 'target'])
def test_setup_must_have_passed_in_every_repetition(tmp_path, mutation):
    original, meitou, report, _, output = scene_campaigns(tmp_path)
    execution = report['executions'][4]
    if mutation == 'verdict':
        execution['setup']['verdict'] = 'failed'
    elif mutation == 'failure':
        execution['setup']['failure'] = dict(step='S5', message='heal not full')
    elif mutation == 'receipt_absent':
        del execution['setup']
    elif mutation == 'format':
        execution['setup']['receipt_format'] = 'scene-setup-0.2'
    else:
        execution['setup']['target'] = 'meitou'
    save_report(original, report)
    with pytest.raises(ValueError, match='setup'):
        compare_campaigns(original, meitou, output)


@pytest.mark.parametrize('scenario', ['0.1', 'scenario-0.2'])
def test_unknown_build_commit_is_rejected(tmp_path, scenario):
    if scenario == '0.1':
        original, meitou = tmp_path/'original', tmp_path/'meitou'
        campaign(original, 'original', commit='unknown')
        campaign(meitou, 'meitou', commit='c'*40)
    else:
        original, meitou, report, _, _ = scene_campaigns(tmp_path)
        report.update(build_commit='unknown', build_commit_known=False, limitations=['commit unknown'])
        for execution in report['executions']:
            execution['setup'].update(build_commit='unknown', build_commit_known=False)
        save_report(original, report)
    with pytest.raises(ValueError, match='build commit is unknown'):
        compare_campaigns(original, meitou, tmp_path/'output')
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('mutation', ['receipt_commit', 'receipt_known', 'receipt_missing', 'inconsistent',
                                    'malformed'])
def test_build_commit_must_be_known_and_unchanged_between_repetitions(tmp_path, mutation):
    original, meitou, _, report, output = scene_campaigns(tmp_path)
    if mutation == 'receipt_commit':
        report['executions'][3]['setup']['build_commit'] = 'c'*40
    elif mutation == 'receipt_known':
        report['executions'][3]['setup'].update(build_commit='unknown', build_commit_known=False)
    elif mutation == 'receipt_missing':
        del report['executions'][3]['setup']['build_commit']
    elif mutation == 'inconsistent':
        report['build_commit_known'] = False
    else:
        report['build_commit'] = 'B'*40
    save_report(meitou, report)
    with pytest.raises(ValueError, match='build commit'):
        compare_campaigns(original, meitou, output)


def test_pre_011_report_is_refused_for_scenario_02(tmp_path):
    original, meitou, report, _, output = scene_campaigns(tmp_path)
    for key in ('build_commit', 'build_commit_known'):
        del report[key]
    save_report(original, report)
    with pytest.raises(ValueError, match='build_commit'):
        compare_campaigns(original, meitou, output)


def test_scenario_01_campaigns_still_compare_with_or_without_a_recorded_commit(tmp_path):
    old, new = tmp_path/'old', tmp_path/'new'
    old.mkdir()
    new.mkdir()
    campaign(old/'original', 'original')
    campaign(old/'meitou', 'meitou')
    campaign(new/'original', 'original', commit='c'*40)
    campaign(new/'meitou', 'meitou', commit='d'*40)
    reports = {}
    for folder in (old, new):
        compare_campaigns(folder/'original', folder/'meitou', folder/'output')
        reports[folder.name] = json.loads((folder/'output'/'report.json').read_text(encoding='utf-8'))
    assert 'build commit not recorded' in reports['old']['limitations']
    assert 'build commit not recorded' not in reports['new']['limitations']
    assert reports['old']['original']['build_commit'] is None
    assert reports['new']['meitou']['build_commit'] == 'd'*40
    for report in reports.values():
        assert 'background_metrics' not in report and 'scene_outcome' not in report
    for folder in (old, new):
        assert '## Scene outcome' not in (folder/'output'/'report.md').read_text(encoding='utf-8')
        metric = next(row for row in report['findings'] if row['metric'] == f'/characters/{FIRST}/position/0')
        assert metric['classification'] == 'stable_divergent'
    strip = lambda report: [(row['checkpoint'], row['metric'], row['classification']) for row in report['findings']]
    assert strip(reports['old']) == strip(reports['new'])


def runner_shape_without_commit(folder, target, scenario=None):
    """A report as the 0.11 runner writes it when the probe reports no build_commit."""
    report = campaign(folder, target, scenario=scenario)
    report.update(report_format='0.1', scenario_schema=report['scenario']['schema_version'], state_schema='0.2',
                  build_commit=None, build_commit_known=False, limitations=['build commit not recorded'])
    for execution in report['executions']:
        execution['load']['ready']['build_commit'] = None
    save_report(folder, report)
    return report


def test_scenario_01_report_written_by_the_runner_without_a_commit_stays_comparable(tmp_path):
    runner_shape_without_commit(tmp_path/'original', 'original')
    runner_shape_without_commit(tmp_path/'meitou', 'meitou')
    compare_campaigns(tmp_path/'original', tmp_path/'meitou', tmp_path/'output')
    report = json.loads((tmp_path/'output'/'report.json').read_text(encoding='utf-8'))
    assert 'build commit not recorded' in report['limitations']
    assert report['original']['build_commit'] is None and report['meitou']['build_commit'] is None


@pytest.mark.parametrize('mutation', ['known_true', 'no_limitation', 'execution_commit'])
def test_scenario_01_null_commit_needs_consistent_evidence(tmp_path, mutation):
    report = runner_shape_without_commit(tmp_path/'original', 'original')
    campaign(tmp_path/'meitou', 'meitou', commit='d'*40)
    if mutation == 'known_true':
        report['build_commit_known'] = True
    elif mutation == 'no_limitation':
        report['limitations'] = []
    else:
        report['executions'][2]['load']['ready']['build_commit'] = 'e'*40
    save_report(tmp_path/'original', report)
    with pytest.raises(ValueError, match='build commit'):
        compare_campaigns(tmp_path/'original', tmp_path/'meitou', tmp_path/'output')


def test_null_commit_is_refused_for_scenario_02(tmp_path):
    original, meitou, report, _, output = scene_campaigns(tmp_path)
    report.update(build_commit=None, build_commit_known=False, limitations=['build commit not recorded'])
    save_report(original, report)
    with pytest.raises(ValueError, match='build_commit'):
        compare_campaigns(original, meitou, output)


def test_campaign_limitations_are_carried_into_the_comparison_by_target(tmp_path):
    original, meitou, left, right, output = scene_campaigns(tmp_path)
    left['limitations'] = ['war flag not observable on original']
    right['limitations'] = ['war flag not observable on meitou', 'build commit not recorded']
    save_report(original, left)
    save_report(meitou, right)
    report = scene_report(original, meitou, output)
    carried = [text for text in report['limitations'] if text.startswith(('original: ', 'meitou: '))]
    assert carried == ['original: war flag not observable on original', 'meitou: war flag not observable on meitou']
    left['limitations'] = 'war flag not observable on original'
    save_report(original, left)
    with pytest.raises(ValueError, match='limitations'):
        compare_campaigns(original, meitou, tmp_path/'second')
