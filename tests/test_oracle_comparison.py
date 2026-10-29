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


def campaign(folder, target, *, n=5):
    folder.mkdir()
    scenario = deepcopy(SCENARIO)
    scenario['repeat'] = n
    report = dict(target=target, status='completed', restoration=dict(verified=True),
                  scenario=scenario, repeat=n, source_fingerprint=FINGERPRINT, executions=[])
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
        for point in scenario['checkpoints']:
            snapshot = state()
            at = point['at']
            snapshot['clock'].update(elapsed_seconds=216000+at, hour=12+at/3600)
            snapshot['characters'][0]['position'][0] = (10 if target == 'meitou' else 0) + at
            if point['name'] == 'initial':
                execution['initial_clock'] = deepcopy(snapshot['clock'])
            output = folder / str(index) / (point['name'] + '.json')
            output.parent.mkdir(exist_ok=True)
            payload = canonical_bytes(snapshot)
            output.write_bytes(payload)
            published = json.loads(payload)
            capture = dict(name=point['name'], path=output.relative_to(folder).as_posix(),
                sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload), schema_version='0.2',
                requested_at=at, actual_at=at, overshoot_seconds=0, clock=deepcopy(published['clock']))
            if target == 'original':
                capture['reference_profile'] = proof()
            else:
                capture['provenance'] = deepcopy(execution['provenance'])
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
