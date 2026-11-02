"""Root-cause groups, per-finding tests and group drafts (synthetic findings only)."""
from copy import deepcopy
import json

from oracle_compare import classify_metric
from oracle_comparison import write_reports
from oracle_triage import FORMAT_VERSION, disagreeing, entity, triage
import oracle_report

SQUAD = 'hand:34:7:101:0:0'
CHARACTER = 'hand:1:7:101:1:1001'
# Names sort against time on purpose: 'zero' is the earliest checkpoint, 'alpha' the latest.
CHECKPOINTS = [dict(name='zero', at=0), dict(name='mid', at=60), dict(name='alpha', at=600)]


def rows(values, target):
    return [dict(repetition=index, snapshot=f'../../{target}/{index}/state.json', value=value)
            for index, value in enumerate(values, 1)]


def finding(metric, checkpoint, original, meitou, tolerance=0.0, known=False):
    rule = dict(metric=metric, id='known', source='https://example.test/known', explanation='Reviewed example.',
                evidence='evidence/known.json') if known else None
    result = classify_metric(metric, rows(original, 'original'), rows(meitou, 'meitou'), tolerance=tolerance,
                             known_deviation=rule)
    result['checkpoint'] = checkpoint
    return result


def report(findings, **extra):
    return dict(format_version='0.2', scenario=dict(name='triage-fixture', save='Fixture save',
                checkpoints=deepcopy(CHECKPOINTS)), state_schema='0.4', source_fingerprint='sha256:' + 'a' * 64,
                original=dict(n=5, build_commit='a' * 40),
                meitou=dict(n=5, seeds=['11', '12', '13', '14', '15'], build_commit=None,
                            repetition_seeds={str(index): str(10 + index) for index in range(1, 6)}),
                findings=findings, limitations=[], reference_deviations=[], **extra)


STABLE, SHIFTED = [1] * 5, [2] * 5


def test_entities_follow_faction_squad_scene_and_family_paths():
    squads = {CHARACTER: 'hand:34:9:9:0:0'}
    assert entity('/population/by_faction/F~1x/alive') == 'faction:F~1x'
    assert entity('/population/by_squad_template/F/T/squads') == 'faction:F'
    assert entity('/combat/starting_cohort/F/survivors') == 'faction:F'
    assert entity('/population/by_faction/coverage') == 'family:/population/by_faction'
    assert entity(f'/characters/{CHARACTER}/position/0') == 'squad:' + SQUAD  # handle container part
    assert entity(f'/characters/{CHARACTER}/position/0', squads) == 'squad:hand:34:9:9:0:0'  # recorded squad_id
    assert entity(f'/squads/{SQUAD}/money') == entity(f'/trajectory/saved_squad/{SQUAD}/final_position/x') == 'squad:' + SQUAD
    assert entity('/scene/intruders/count') == 'scene'
    assert entity('/population/loaded/total') == 'family:/population/loaded'
    assert entity('/combat/engagement_by_faction/F/engagement_observed') == 'family:/combat/engagement_by_faction'


def test_disagreeing_set_uses_the_tolerance_and_the_widened_original_range():
    assert disagreeing(finding('/m', 'zero', STABLE, [1, 1.05, 2, 1, 0], tolerance=0.1)) == [3, 5]
    assert disagreeing(finding('/m', 'zero', [1, 2, 3, 4, 5], [0.95, 3, 5.2, 6, 1], tolerance=0.1)) == [3, 4]
    assert disagreeing(finding('/m', 'zero', ['a'] * 5, ['a', 'b', 'a', 'a', 'a'])) == [2]
    assert disagreeing(finding('/m', 'zero', ['a', 'b', 'a', 'b', 'a'], ['c', 'a', 'b', 'a', 'a'])) == [1]


def test_divergent_findings_get_tests_and_others_none():
    value = report([finding('/a/b/c', 'zero', STABLE, SHIFTED), finding('/a/b/d', 'zero', STABLE, STABLE),
                    finding('/a/b/e', 'zero', [1, 2, 3, 4, 5], [0, 1, 2, 3, 6]),
                    finding('/a/b/f', 'zero', STABLE, SHIFTED, known=True)])
    triage(value)
    divergent, identical, variable, known = value['findings']
    assert divergent['test']['p_value'] == 2 / 252 and divergent['strength'] == 'strong'
    assert 'test' not in identical and 'strength' not in identical and identical['group'] is None
    assert variable['test']['test'] == 'permutation' and variable['strength'] == 'weak'
    assert known['classification'] == 'known_deviation' and known['strength'] == 'strong' and known['group']
    assert value['format_version'] == FORMAT_VERSION == '0.3'


def test_one_metric_merges_across_checkpoints_in_time_order_with_its_onset():
    metric = f'/characters/{CHARACTER}/position/0'
    value = report([finding(metric, name, STABLE, SHIFTED) for name in ('alpha', 'zero', 'mid')]
                   + [finding('/population/loaded/total', 'mid', STABLE, SHIFTED)])
    groups = triage(value)
    assert len(groups) == 2
    character = next(group for group in groups if group['entity'] == 'squad:' + SQUAD)
    assert character['size'] == 1 and character['members'][0]['checkpoints'] == ['zero', 'mid', 'alpha']
    assert character['onset'] == 'load' and character['first_checkpoint'] == dict(name='zero', at=0)
    loaded = next(group for group in groups if group['entity'] == 'family:/population/loaded')
    assert loaded['onset'] == 'simulation' and loaded['first_checkpoint'] == dict(name='mid', at=60)
    assert all(row['group'] == character['id'] for row in value['findings'] if row['metric'] == metric)


def test_group_key_separates_entity_disagreeing_set_and_onset_and_absorbs_subsets():
    value = report([
        finding('/population/by_faction/F/alive', 'zero', STABLE, SHIFTED),
        finding('/combat/starting_cohort/F/size_at_start', 'zero', STABLE, SHIFTED),
        finding('/population/by_faction/F/dead', 'zero', STABLE, [1, 2, 1, 1, 2]),   # subset {2, 5}: joins
        finding('/population/by_faction/G/alive', 'zero', STABLE, SHIFTED),           # other entity
        finding('/population/by_faction/F/loaded', 'mid', STABLE, SHIFTED),           # simulation onset
        finding('/population/by_faction/F/unpaired', 'alpha', STABLE, SHIFTED),       # same simulation key
    ])
    groups = triage(value)
    keys = sorted((group['entity'], group['onset'], group['size']) for group in groups)
    assert keys == [('faction:F', 'load', 3), ('faction:F', 'simulation', 2), ('faction:G', 'load', 1)]
    load = next(group for group in groups if group['key'] == dict(entity='faction:F', disagreeing_repetitions=[1, 2, 3, 4, 5],
                                                                  onset='load'))
    subset = next(member for member in load['members'] if member['metric'].endswith('/dead'))
    assert subset['disagreeing_repetitions'] == [2, 5]
    simulation = next(group for group in groups if group['onset'] == 'simulation')
    assert simulation['first_checkpoint']['name'] == 'mid'


def test_whole_scenario_trace_joins_its_squad_or_else_its_family():
    value = report([
        finding(f'/characters/{CHARACTER}/position/0', 'mid', STABLE, SHIFTED),
        finding(f'/trajectory/saved_squad/{SQUAD}/final_position/x', 'whole_scenario', STABLE, SHIFTED),
        finding('/trajectory/saved_squad/hand:34:8:8:0:0/final_position/x', 'whole_scenario', STABLE, SHIFTED),
        finding('/trajectory/saved_squad/hand:34:9:9:0:0/final_position/x', 'whole_scenario', STABLE, SHIFTED),
    ])
    groups = triage(value)
    squad = next(group for group in groups if group['entity'] == 'squad:' + SQUAD)
    assert squad['size'] == 2 and squad['first_checkpoint']['name'] == 'mid'
    family = next(group for group in groups if group['entity'] == 'family:/trajectory/saved_squad')
    assert family['size'] == 2 and family['onset'] == 'simulation'
    assert family['first_checkpoint'] == dict(name='whole_scenario', at=None)


def test_one_field_repeated_across_squad_groups_merges_without_being_explained():
    # Characters of three squads (handle containers 7, 8, 9) differ only in height at load; a fourth squad also
    # moved in X, so it keeps its own group, and a lone single-field squad at simulation is not merged.
    height = [finding(f'/characters/hand:1:{c}:101:1:{c}00{i}/position/1', 'zero', STABLE, reps)
              for c, reps in ((7, SHIFTED), (8, SHIFTED), (9, [1, 1, 2, 1, 2])) for i in (1, 2)]
    value = report(height + [
        finding('/characters/hand:1:6:101:1:6001/position/1', 'zero', STABLE, SHIFTED),
        finding('/characters/hand:1:6:101:1:6001/position/0', 'zero', STABLE, SHIFTED),
        finding('/characters/hand:1:5:101:1:5001/position/2', 'mid', STABLE, SHIFTED),
    ])
    groups = triage(value)
    merged = next(group for group in groups if group['entity'] == 'field:/characters/*/position/1')
    assert merged['size'] == 6 and merged['onset'] == 'load' and merged['disagreeing_repetitions'] == [1, 2, 3, 4, 5]
    assert merged['strength'] == 'strong' and merged['drafted'] is True
    assert all(row['classification'] == 'stable_divergent' for row in value['findings'] if row['group'] == merged['id'])
    entities = sorted(group['entity'] for group in groups)
    assert entities == ['field:/characters/*/position/1', 'squad:hand:34:5:101:0:0', 'squad:hand:34:6:101:0:0']
    assert triage(deepcopy(value)) == groups


def test_order_strong_first_then_size_times_disagreeing_then_load_with_stable_ids():
    findings = [
        finding('/population/by_faction/W/alive', 'zero', [1, 2, 3, 4, 5], [0, 1, 2, 3, 6]),  # weak
        finding('/family/a/x', 'zero', STABLE, [2, 1, 1, 1, 1]),                              # 1 x 1, but p 1/5
        finding('/population/by_faction/S/alive', 'mid', STABLE, SHIFTED),                    # 1 x 5 simulation
        finding('/population/by_faction/L/alive', 'zero', STABLE, SHIFTED),                   # 1 x 5 load
        finding('/population/by_faction/B/alive', 'zero', STABLE, SHIFTED),                   # 2 x 5
        finding('/population/by_faction/B/dead', 'zero', STABLE, SHIFTED),
    ]
    first = triage(report(deepcopy(findings)))
    assert [group['entity'] for group in first] == ['faction:B', 'faction:L', 'faction:S', 'faction:W', 'family:/family/a']
    assert [group['strength'] for group in first] == ['strong'] * 3 + ['weak'] * 2
    assert [group['id'][:4] for group in first] == ['g001', 'g002', 'g003', 'g004', 'g005']
    second = triage(report(list(reversed(deepcopy(findings)))))
    assert [group['id'] for group in second] == [group['id'] for group in first]
    assert first[0]['headline']['metric'] == '/population/by_faction/B/alive'  # equal p, then metric


def test_headline_is_the_member_with_the_lowest_p_over_its_checkpoints():
    value = report([finding('/population/by_faction/F/b', 'zero', STABLE, [2, 2, 2, 1, 1]),
                    finding('/population/by_faction/F/b', 'mid', STABLE, SHIFTED),
                    finding('/population/by_faction/F/a', 'zero', STABLE, [2, 2, 2, 2, 1])])
    group, = triage(value)
    assert group['headline'] == dict(metric='/population/by_faction/F/b', checkpoint='mid', p_value=2 / 252)
    assert group['onset'] == 'load' and group['disagreeing_repetitions'] == [1, 2, 3, 4]
    assert group['first_checkpoint']['name'] == 'zero' and group['p_value'] == 2 / 252


def test_only_strong_groups_are_drafted_and_weak_or_known_groups_are_listed(tmp_path):
    value = report([finding('/population/by_faction/S/alive', 'zero', STABLE, SHIFTED),
                    finding('/scene/intruders/count', 'mid', [0] * 5, [0, 0, 11, 0, 8]),
                    finding('/population/by_faction/K/alive', 'zero', STABLE, SHIFTED, known=True)])
    write_reports(value, tmp_path/'output')
    strong, weak, known = value['groups']
    assert (strong['drafted'], weak['drafted'], known['drafted']) == (True, False, False)
    assert weak['entity'] == 'scene' and weak['strength'] == 'weak' and weak['p_value'] > 0.01
    assert known['known_deviation'] is True and known['strength'] == 'strong'
    issues = sorted(path.name for path in (tmp_path/'output'/'issues').glob('*.md'))
    assert issues == sorted(['README.md', strong['id'] + '.md'])
    index = (tmp_path/'output'/'issues'/'README.md').read_text(encoding='utf-8')
    summary = (tmp_path/'output'/'report.md').read_text(encoding='utf-8')
    for text in (index, summary):
        assert '3 root-cause groups: 1 strong (drafted), 1 weak (listed, not drafted), 1 known deviations' in text
        assert weak['id'] in text and '/scene/intruders/count' in text and known['id'] in text
    assert '[Draft](issues/' + strong['id'] + '.md)' in summary and '[Draft](' + strong['id'] + '.md)' in index
    assert value['summary']['drafts'] == 1 and value['summary']['weak_groups'] == 1
    saved = json.loads((tmp_path/'output'/'report.json').read_bytes())
    assert saved['groups'] == value['groups'] and saved['format_version'] == '0.3'


def test_draft_header_names_provenance_test_table_members_and_reproduction(tmp_path, monkeypatch):
    monkeypatch.setattr(oracle_report, 'DRAFT_MEMBERS', 2)
    metric = '/population/by_faction/F/alive'
    value = report([finding(metric, 'mid', STABLE, [2, 2, 1, 2, 1]), finding(metric, 'alpha', STABLE, SHIFTED)]
                   + [finding(f'/population/by_faction/F/m{index}', 'mid', STABLE, [2, 2, 1, 2, 1])
                      for index in range(3)])
    write_reports(value, tmp_path/'output')
    group, = value['groups']
    text = (tmp_path/'output'/'issues'/(group['id'] + '.md')).read_text(encoding='utf-8')
    for term in ('# triage-fixture: faction:F, /population/by\\_faction/F/alive and 3 related metrics',
                 'Local draft for review. No issue has been published.',
                 '- Scenario: triage-fixture', '- Save: Fixture save; start-save fingerprint `sha256:' + 'a' * 64 + '`',
                 '- Build commits: original `' + 'a' * 40 + '`; MeitouClient build commit not recorded',
                 '- State schema: 0.4', '- Original N=5; Meitou N=5.',
                 '- Meitou seeds per repetition: 1: 11; 2: 12; 3: 13; 4: 14; 5: 15.',
                 '- Group key: entity faction:F; disagreeing Meitou repetitions [1,2,4]; onset simulation',
                 '- First divergent checkpoint: mid (at 60 s)',
                 'at alpha, stable divergent; two-sided permutation test (number), p = 0.007937, '
                 'minimum attainable p = 0.007937, exact over 252 splits',
                 '| Original | 1 | none | 1 | reference | [snapshot](../../../original/1/state.json) |',
                 '| MeitouClient | 3 | 13 | 2 | yes | [snapshot](../../../meitou/3/state.json) |',
                 '## Member metrics (4)', 'and 2 more; the complete list is in the [JSON report](../report.json)',
                 'Reproduce: load save Fixture save in MeitouClient with seed 11 (repetition 1) and compare '
                 'checkpoint mid (at 60 s) with the original reference.'):
        assert term in text, term
    assert len(group['members']) == 4 and group['members'][0]['checkpoints'] == ['mid', 'alpha']


def test_findings_preview_and_detail_pages_are_chronological(tmp_path):
    value = report([finding('/b', 'alpha', STABLE, SHIFTED), finding('/a', 'alpha', STABLE, SHIFTED),
                    finding('/c', 'zero', STABLE, SHIFTED), finding('/d', 'whole_scenario', STABLE, SHIFTED),
                    finding('/e', 'mid', STABLE, SHIFTED)])
    write_reports(value, tmp_path/'output')
    page = (tmp_path/'output'/value['details_catalog']['pages'][0]['path']).read_text(encoding='utf-8')
    summary = (tmp_path/'output'/'report.md').read_text(encoding='utf-8')
    expected = ['| zero | /c |', '| mid | /e |', '| alpha | /a |', '| alpha | /b |', '| whole\\_scenario | /d |']
    for text in (page, summary.split('## First stable divergent findings')[1]):
        positions = [text.index(row) for row in expected]
        assert positions == sorted(positions)
