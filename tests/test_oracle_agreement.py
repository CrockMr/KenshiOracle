"""Agreement between runs: counts on synthetic run directories, rules as data, the CLI and the MCP tool. No game."""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from oracle_agreement import (RULES_FORMAT, agreement, append_ledger, ledger_rows, load_run, render_text,
                              validate_rules, write_outputs)
from oracle_compare import field_family
from oracle_live import compare_states
from oracle_schema import canonical_bytes
from test_oracle_compare import FIRST, SECOND
from test_oracle_schema_05 import goal, state_05

ROOT = Path(__file__).resolve().parents[1]
THIRD = 'hand:1:7:101:3:1003'
FINGERPRINT = 'sha256:' + '1' * 64
SQUAD = 'hand:34:7:101:0:0'
LATE_SQUAD = 'hand:34:7:102:0:0'
CHECKPOINTS = ('initial', 't00060', 't00120')


def snapshot(goals, *, present=(FIRST, SECOND), late_squad=()):
    """A valid 0.5 state where each character of ``goals`` holds that goal type (None = unknown)."""
    value = state_05()
    template = value['characters'][0]
    rows = []
    for identity in present:
        row = deepcopy(template)
        row.update(id=identity, name='Name ' + identity[-4:], identity_origin='saved',
                   goal=None if goals.get(identity) is None else goal(goals[identity]),
                   squad_id=LATE_SQUAD if identity in late_squad else SQUAD)
        rows.append(row)
    value['characters'] = rows
    squad = value['squads'][0]
    squad.update(id=SQUAD, members=[i for i in present if i not in late_squad], template_id='gate-template',
                 leader_id=None, identity_origin='saved')
    if late_squad:
        other = deepcopy(squad)
        other.update(id=LATE_SQUAD, members=list(late_squad), template_id='late-template')
        value['squads'].append(other)
    return value


def write_run(root, target, repetitions, *, commit='a' * 40, fingerprint=FINGERPRINT, names=CHECKPOINTS,
              relative_paths=False):
    """``repetitions``: one {checkpoint name: state} mapping per repetition. Returns the report path."""
    root.mkdir(parents=True)
    executions = []
    for number, states in enumerate(repetitions, 1):
        captures = []
        for name, value in states.items():
            payload = canonical_bytes(value)
            path = root / str(number) / (name + '.json')
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(payload)
            captures.append(dict(name=name, path=f'{number}/{name}.json' if relative_paths else str(path),
                                 sha256=hashlib.sha256(payload).hexdigest()))
        executions.append(dict(execution=number, status='completed', checkpoints=captures,
                               provenance=dict(seed=str(number - 1)) if target == 'meitou' else None))
    report = dict(target=target, status='completed', build_commit=commit, source_fingerprint=fingerprint,
                  state_schema='0.5', repeat=len(repetitions), executions=executions, variability=dict(large=True),
                  scenario=dict(name='fixture-hold', save='fixture-save',
                                checkpoints=[dict(name=name, at=index * 60) for index, name in enumerate(names)]))
    (root / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    return root / 'report.json'


def steady(first='guard', second='patrol'):
    return {name: snapshot({FIRST: first, SECOND: second}) for name in CHECKPOINTS}


def detail(result, index=0, field='goal/type'):
    return next(row for row in result['comparisons'][index]['details'] if row['field'] == field)


def rules_file(tmp_path, *classes):
    path = tmp_path / 'rules.json'
    path.write_text(json.dumps(dict(format=RULES_FORMAT, classes=list(classes))), encoding='utf-8')
    return path


def klass(name, when, field='goal/type'):
    return dict(name=name, field=field, reason='Documented cause.', evidence='docs/example.md', when=when)


def test_counts_pairs_with_a_value_on_both_sides_and_those_that_are_equal(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    other = steady()
    other['t00060'] = snapshot({FIRST: 'guard', SECOND: 'sleep'})
    other['t00120'] = snapshot({FIRST: 'guard', SECOND: None})
    result = agreement(reference, [write_run(tmp_path / 'b', 'meitou', [other])])
    row = detail(result)
    assert (row['comparable'], row['equal'], row['agreement']) == (5, 4, 80.0)
    assert (row['kept_comparable'], row['kept_agreement'], row['set_aside']) == (5, 80.0, 0)
    assert row['differences'] == [dict(reference='patrol', candidate='sleep', pairs=1, examples=[dict(
        id=SECOND, name='Name 1002', squad_template='gate-template', checkpoint='t00060',
        reference_repetition=1, candidate_repetition=1)])]
    fields = {entry['field']: entry for entry in result['comparisons'][0]['fields']}
    assert fields['goal/type']['one_sided_unknown'] == 1
    assert fields['name']['agreement'] == 100.0
    assert result['comparisons'][0]['characters'] == dict(paired=6, only_reference=0, only_candidate=0)
    assert result['comparisons'][0]['same_engine'] is False


def test_checkpoints_are_matched_by_name_and_a_missing_one_is_reported_not_shifted(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [
        dict(initial=snapshot({FIRST: 'one', SECOND: 'one'}), t00060=snapshot({FIRST: 'two', SECOND: 'two'}),
             t00120=snapshot({FIRST: 'three', SECOND: 'three'}))])
    # The other run lists its captures in another order and has no middle checkpoint.
    shifted = write_run(tmp_path / 'b', 'meitou', [
        dict(t00120=snapshot({FIRST: 'three', SECOND: 'three'}), initial=snapshot({FIRST: 'one', SECOND: 'one'}))])
    result = agreement(reference, [shifted])
    row = detail(result)
    assert (row['comparable'], row['equal']) == (4, 4)
    comparison = result['comparisons'][0]
    assert comparison['checkpoints_compared'] == 2
    assert comparison['missing_checkpoints'] == [dict(checkpoint='t00060', reference_repetition=1,
                                                     candidate_repetition=1, missing='candidate')]
    assert any('lacks checkpoints: t00060' in text for text in comparison['candidate']['warnings'])
    assert '1 checkpoint(s) missing' in render_text(result)


def test_a_run_of_the_reference_engine_is_the_noise_floor_and_its_absence_is_stated(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    noisy = steady()
    noisy['t00120'] = snapshot({FIRST: 'guard', SECOND: 'sleep'})
    second = write_run(tmp_path / 'b', 'original', [noisy])
    meitou = write_run(tmp_path / 'c', 'meitou', [steady()])
    alone = agreement(reference, [meitou])
    assert alone['noise_floor']['goal/type'] == dict(measured=False, comparisons=0, agreement=None,
                                                     kept_agreement=None)
    assert 'noise floor: NOT MEASURED' in render_text(alone)
    assert any('Noise floor not measured' in note for note in alone['notes'])
    both = agreement(reference, [second, meitou])
    assert [c['same_engine'] for c in both['comparisons']] == [True, False]
    assert both['noise_floor']['goal/type'] == dict(measured=True, comparisons=1, agreement=83.3,
                                                    kept_agreement=83.3)
    assert detail(both, 1)['agreement'] == 100.0
    text = render_text(both)
    assert 'same engine: noise floor' in text and 'NOT MEASURED' not in text
    assert [c['label'] for c in both['comparisons']] == ['b', 'c']


def test_several_reference_repetitions_are_compared_with_each_other_and_every_pair_is_pooled(tmp_path):
    drift = steady()
    drift['t00060'] = snapshot({FIRST: 'guard', SECOND: 'sleep'})
    reference = write_run(tmp_path / 'a', 'original', [steady(), drift])
    result = agreement(reference, [write_run(tmp_path / 'b', 'meitou', [steady(), steady()])])
    own, other = result['comparisons']
    assert own['label'] == 'reference repetitions against each other' and own['same_engine'] is True
    assert own['repetition_pairs'] == 1 and other['repetition_pairs'] == 4
    assert (detail(result, 0)['comparable'], detail(result, 0)['equal']) == (6, 5)
    assert (detail(result, 1)['comparable'], detail(result, 1)['equal']) == (24, 22)
    assert [(p['reference_repetition'], p['candidate_repetition'], p['equal'])
            for p in detail(result, 1)['repetition_pairs']] == [(1, 1, 6), (1, 2, 6), (2, 1, 5), (2, 2, 5)]
    assert result['noise_floor']['goal/type']['measured'] is True
    assert other['candidate']['seeds'] == {'1': '0', '2': '1'}
    assert all(row['candidate']['run'] == 'b' for row in ledger_rows(result))


def test_a_class_sets_aside_only_differing_pairs_of_its_squad_template_and_value_pair(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady('post_in', 'post_in')])
    other = steady('post_in', 'post_in')
    other['t00060'] = snapshot({FIRST: 'post_out', SECOND: 'sleep'})
    candidate = write_run(tmp_path / 'b', 'meitou', [other])
    gate = klass('gate', dict(squad_template=['gate-template'], values=[['post_out', 'post_in']]))
    result = agreement(reference, [candidate], rules_path=rules_file(tmp_path, gate))
    row = detail(result)
    assert (row['comparable'], row['equal'], row['set_aside'], row['kept_comparable']) == (6, 4, 1, 5)
    assert (row['agreement'], row['kept_agreement']) == (66.7, 80.0)
    assert row['classes'] == [dict(name='gate', pairs=1)]
    assert [(d['reference'], d['candidate']) for d in row['differences']] == [('post_in', 'sleep')]
    assert result['rules']['classes'][0]['evidence'] == 'docs/example.md'
    elsewhere = klass('gate', dict(squad_template=['another-template'], values=[['post_out', 'post_in']]))
    assert detail(agreement(reference, [candidate], rules_path=rules_file(tmp_path, elsewhere)))['set_aside'] == 0


def test_related_absent_holds_while_the_reference_keeps_the_value_without_a_break(tmp_path):
    # SECOND's related character THIRD is away at the first checkpoint only.
    reference = write_run(tmp_path / 'a', 'original', [dict(
        initial=snapshot({FIRST: 'work', SECOND: 'cage'}),
        t00060=snapshot({FIRST: 'work', SECOND: 'cage', THIRD: 'watch'}, present=(FIRST, SECOND, THIRD)),
        t00120=snapshot({FIRST: 'work', SECOND: 'mine', THIRD: 'watch'}, present=(FIRST, SECOND, THIRD)))])
    everyone = (FIRST, SECOND, THIRD)
    candidate = write_run(tmp_path / 'b', 'meitou', [dict(
        initial=snapshot({FIRST: 'work', SECOND: 'mine', THIRD: 'watch'}, present=everyone),
        t00060=snapshot({FIRST: 'work', SECOND: 'mine', THIRD: 'watch'}, present=everyone),
        t00120=snapshot({FIRST: 'work', SECOND: 'work', THIRD: 'watch'}, present=everyone))])
    related = dict(related={SECOND: THIRD})
    plain = agreement(reference, [candidate], rules_path=rules_file(tmp_path, klass('late', dict(
        related_absent=related))))
    assert detail(plain)['classes'] == [dict(name='late', pairs=1)]
    held = agreement(reference, [candidate], rules_path=rules_file(tmp_path, klass('late', dict(
        related_absent=dict(related, held_value='cage')))))
    row = detail(held)
    # initial (owner away) and t00060 (still caged) are explained; t00120 (left the cage) is not.
    assert row['classes'] == [dict(name='late', pairs=2)]
    assert [(d['reference'], d['candidate'], d['examples'][0]['checkpoint']) for d in row['differences']] == [
        ('mine', 'work', 't00120')]
    assert held['comparisons'][0]['characters'] == dict(paired=8, only_reference=0, only_candidate=1)


def test_squad_absent_at_first_checkpoint_and_class_order(tmp_path):
    late = dict(present=(FIRST, SECOND, THIRD), late_squad=(THIRD,))
    reference = write_run(tmp_path / 'a', 'original', [dict(
        initial=snapshot({FIRST: 'work', SECOND: 'work'}),
        t00060=snapshot({FIRST: 'gather', SECOND: 'work', THIRD: 'gather'}, **late),
        t00120=snapshot({FIRST: 'work', SECOND: 'work', THIRD: 'gather'}, **late))])
    candidate = write_run(tmp_path / 'b', 'meitou', [dict(
        initial=snapshot({FIRST: 'work', SECOND: 'work', THIRD: 'work'}, **late),
        t00060=snapshot({FIRST: 'work', SECOND: 'work', THIRD: 'work'}, **late),
        t00120=snapshot({FIRST: 'work', SECOND: 'work', THIRD: 'gather'}, **late))])
    gatherer = klass('late-gatherer', dict(reference_value=['gather'], candidate_value_not=['gather'],
                                           squad_absent_at_first_checkpoint=True))
    broad = klass('any-gather', dict(reference_value=['gather']))
    result = agreement(reference, [candidate], rules_path=rules_file(tmp_path, gatherer, broad))
    # THIRD's squad loads late: its pair goes to the first class; FIRST's squad was there from the start.
    assert detail(result)['classes'] == [dict(name='late-gatherer', pairs=1), dict(name='any-gather', pairs=1)]
    swapped = agreement(reference, [candidate], rules_path=rules_file(tmp_path, broad, gatherer))
    assert detail(swapped)['classes'] == [dict(name='any-gather', pairs=2), dict(name='late-gatherer', pairs=0)]
    text = render_text(swapped)
    assert 'any-gather: 2 in b' in text and 'late-gatherer: 0 in b' in text


def test_a_class_is_counted_on_the_same_engine_run_too(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady('post_in', 'post_in')])
    second = steady('post_in', 'post_in')
    second['initial'] = snapshot({FIRST: 'post_out', SECOND: 'post_in'})
    runs = [write_run(tmp_path / 'b', 'original', [second]),
            write_run(tmp_path / 'c', 'meitou', [steady('post_out', 'post_in')])]
    gate = klass('gate', dict(values=[['post_in', 'post_out']]))
    result = agreement(reference, runs, rules_path=rules_file(tmp_path, gate))
    assert [detail(result, index)['classes'][0]['pairs'] for index in (0, 1)] == [1, 3]
    assert result['noise_floor']['goal/type'] == dict(measured=True, comparisons=1, agreement=83.3,
                                                      kept_agreement=100.0)
    assert "A class with 0 pairs in a same-engine run" in render_text(result)


@pytest.mark.parametrize('change', [
    lambda r: r.update(format='agreement-rules-9'),
    lambda r: r.update(extra=1),
    lambda r: r.update(classes=[]),
    lambda r: r['classes'][0].pop('evidence'),
    lambda r: r['classes'][0].update(reason='  '),
    lambda r: r['classes'].append(deepcopy(r['classes'][0])),
    lambda r: r['classes'][0].update(when={}),
    lambda r: r['classes'][0].update(when=dict(unknown_predicate=True)),
    lambda r: r['classes'][0].update(when=dict(values=[['only-one']])),
    lambda r: r['classes'][0].update(when=dict(values=[['same', 'same']])),
    lambda r: r['classes'][0].update(when=dict(squad_template='gate-template')),
    lambda r: r['classes'][0].update(when=dict(related_absent=dict(held_value='cage'))),
    lambda r: r['classes'][0].update(when=dict(related_absent=dict(related={}))),
    lambda r: r['classes'][0].update(when=dict(squad_absent_at_first_checkpoint=False)),
])
def test_invalid_rules_are_refused(change):
    rules = dict(format=RULES_FORMAT, classes=[klass('gate', dict(values=[['a', 'b']]))])
    assert validate_rules(deepcopy(rules)) == rules
    change(rules)
    with pytest.raises(ValueError):
        validate_rules(rules)


def test_the_example_rules_file_is_valid():
    validate_rules(json.loads((ROOT / 'scenarios' / 'agreement-rules' / 'example.json').read_text(encoding='utf-8')))


def test_a_changed_snapshot_or_another_experiment_is_refused(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    changed = write_run(tmp_path / 'b', 'meitou', [steady()])
    target = changed.parent / '1' / 'initial.json'
    target.write_bytes(target.read_bytes() + b' ')
    with pytest.raises(ValueError, match='differs from the hash recorded'):
        agreement(reference, [changed])
    other_save = write_run(tmp_path / 'c', 'meitou', [steady()], fingerprint='sha256:' + '2' * 64)
    with pytest.raises(ValueError, match='save fingerprint differs'):
        agreement(reference, [other_save])
    other_points = write_run(tmp_path / 'd', 'meitou', [dict(initial=steady()['initial'])], names=('initial',))
    with pytest.raises(ValueError, match='checkpoint list differs'):
        agreement(reference, [other_points])
    failed = json.loads(reference.read_text(encoding='utf-8'))
    failed['executions'][0]['status'] = 'failed'
    reference.write_text(json.dumps(failed), encoding='utf-8')
    with pytest.raises(ValueError, match='no completed repetition'):
        load_run(reference)


def test_a_moved_run_directory_is_read_by_its_layout(tmp_path):
    write_run(tmp_path / 'a', 'original', [steady()])
    (tmp_path / 'a').rename(tmp_path / 'moved')  # the report still records the old absolute paths
    run = load_run(tmp_path / 'moved')
    assert sorted(run['repetitions'][1]) == sorted(CHECKPOINTS)
    relative = load_run(write_run(tmp_path / 'r', 'original', [steady()], relative_paths=True))
    assert relative['run'] == 'r' and 'relations' not in relative['repetitions'][1]['initial']


@pytest.mark.parametrize('options', [dict(top=0), dict(top=True), dict(fields='goal'), dict(detail_fields=['']),
                                     dict(position_tolerance=-1), dict(number_tolerance=float('nan'))])
def test_invalid_options_are_refused(tmp_path, options):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    with pytest.raises(ValueError):
        agreement(reference, [reference], **options)


def test_field_filter_tolerances_and_families(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    moved = steady()
    for value in moved.values():
        value['characters'][0]['position'][0] += 0.5
    candidate = write_run(tmp_path / 'b', 'meitou', [moved])
    result = agreement(reference, [candidate], fields=['position'])
    fields = {row['field']: row for row in result['comparisons'][0]['fields']}
    assert set(fields) == {'position/0', 'position/1', 'position/2', 'goal/type'}  # the detail field stays
    assert fields['position/0']['agreement'] == 50.0
    loose = agreement(reference, [candidate], fields=['position'], position_tolerance=1.0)
    assert next(r for r in loose['comparisons'][0]['fields'] if r['field'] == 'position/0')['agreement'] == 100.0
    assert field_family('health/fixture-head:neither/current') == 'health/*/current'
    assert field_family('stats/dodge') == 'stats/*' and field_family('goal/type') == 'goal/type'


def test_outputs_and_ledger_are_written_once(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    result = agreement(reference, [write_run(tmp_path / 'b', 'meitou', [steady()], commit='b' * 40)])
    written = write_outputs(result, tmp_path / 'out')
    assert json.loads(Path(written['json']).read_text(encoding='utf-8'))['format'] == 'agreement-0.1'
    assert Path(written['text']).read_text(encoding='utf-8') == render_text(result)
    ledger = tmp_path / 'trend' / 'ledger.jsonl'
    assert append_ledger(ledger, result) == 1 and append_ledger(ledger, result) == 0
    row = json.loads(ledger.read_text(encoding='utf-8'))
    assert (row['candidate']['build_commit'], row['field'], row['equal'], row['comparable']) == (
        'b' * 40, 'goal/type', 6, 6)


def test_live_comparison_reports_per_field_counts():
    original = snapshot({FIRST: 'guard', SECOND: 'patrol'})
    meitou = snapshot({FIRST: 'guard', SECOND: 'sleep'})
    counts = {row['field']: row for row in compare_states(original, meitou)['field_agreement']}
    assert counts['goal/type'] == dict(field='goal/type', comparable=2, equal=1)
    assert counts['health/*/current'] == dict(field='health/*/current', comparable=4, equal=4)


def cli(tmp_path, *arguments):
    return subprocess.run([sys.executable, '-m', 'launcher', 'agree', *map(str, arguments)], cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1',
                 KENSHI_PROBE_CONFIG=str(tmp_path / 'deliberately-absent-game-config.json')),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def test_actual_cli_prints_text_or_json_and_needs_no_game_config(tmp_path):
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    other = write_run(tmp_path / 'b', 'meitou', [steady('guard', 'sleep')])
    text = cli(tmp_path, reference.parent, other)
    assert text.returncode == 0, text.stderr
    assert '3/6  50.0%' in text.stdout and 'patrol -> sleep' in text.stdout
    as_json = cli(tmp_path, reference, other, '--json', '--output', tmp_path / 'out', '--ledger',
                  tmp_path / 'ledger.jsonl', '--detail', 'goal/type', '--field', 'goal', '--top', '5')
    assert as_json.returncode == 0, as_json.stderr
    result = json.loads(as_json.stdout)
    assert result['ledger_rows_added'] == 1 and Path(result['written']['text']).is_file()
    assert detail(result)['agreement'] == 50.0
    refused = cli(tmp_path, reference, tmp_path / 'absent')
    assert refused.returncode == 1 and refused.stdout == ''


def test_mcp_tool_returns_counts_and_text(tmp_path):
    import server
    reference = write_run(tmp_path / 'a', 'original', [steady()])
    other = write_run(tmp_path / 'b', 'meitou', [steady()])
    result = asyncio.run(server.agreement(str(reference), [str(other)]))
    assert detail(result)['agreement'] == 100.0 and result['text'].startswith('Agreement of paired saved characters')
