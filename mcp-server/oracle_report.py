"""Bounded Markdown pages and a compact streamed JSON comparison artifact."""
from collections import Counter, defaultdict
import html
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote

from oracle_triage import checkpoint_times, chronological, disagreeing, triage


CLASS_ORDER = ('stable_divergent', 'stable_identical', 'variable_outside_range',
               'known_deviation', 'variable_compatible', 'not_comparable')
LABELS = dict(stable_identical='Stable identical', stable_divergent='Stable divergent',
              variable_compatible='Variable compatible', variable_outside_range='Variable outside range',
              known_deviation='Known deviation', not_comparable='Not comparable')
PAGE_SIZE = 100
PREVIEW_SIZE = 20
DRAFT_MEMBERS = 20
TARGET_PAGE_BYTES = 200 * 1024


def _json(value):
    return html.escape(json.dumps(value, ensure_ascii=False, separators=(',', ':')), quote=False).replace('|', '\\|').replace('\n', ' ')


def _cell(value):
    text = html.escape(str(value), quote=False).replace('\r', ' ').replace('\n', ' ')
    for character in ('\\', '|', '[', ']', '*', '_', '`'):
        text = text.replace(character, '\\' + character)
    return text


def _unique(summary):
    return list(dict.fromkeys(_json(value) for value in summary.get('values', [])))


def _summary(summary):
    result = f"Available N {summary['comparable_n']}/{summary['n']}"
    if summary.get('min') is not None:
        result += '; range [' + _json(summary['min']) + ', ' + _json(summary['max'])
        result += '], median ' + _json(summary['median'])
    else:
        result += '; ' + '; '.join(_unique(summary))
    return result


def _photos(finding, prefix=''):
    paths = sorted({row['snapshot'] for target in ('original', 'meitou')
                    for row in finding[target].get('observations', []) if row.get('snapshot')}
                   | set(finding.get('additional_snapshots', [])))
    return ', '.join('[snapshot ' + str(index) + '](' + quote(prefix + path, safe='/.-_') + ')'
                     for index, path in enumerate(paths, 1))


def _table_header():
    return ['| Checkpoint | Field or metric | Class | Original | MeitouClient | Outside range | Tolerance | Snapshots |',
            '| --- | --- | --- | --- | --- | ---: | --- | --- |']


def _finding_row(finding, prefix=''):
    return '| ' + ' | '.join((_cell(finding['checkpoint']), _cell(finding['metric']), LABELS[finding['classification']],
        _summary(finding['original']), _summary(finding['meitou']), _json(finding['meitou'].get('outside_count')),
        _json(finding['tolerance']), _photos(finding, prefix))) + ' |'


def _atomic_text(path, write):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', dir=path.parent,
                                         prefix='.oracle-report-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            write(handle)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _text(path, rows):
    _atomic_text(path, lambda handle: handle.write('\n'.join(rows) + '\n'))


def _directory(path):
    path.mkdir(exist_ok=True)
    info = path.lstat()
    if not path.is_dir() or path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Report artifact directories must not be links or reparse points')


def _link(path, prefix=''):
    return quote(prefix + path, safe='/.-_')


def _seeds(report):
    """{repetition: Meitou seed}; a report without the map pairs its seeds in execution order."""
    recorded = report['meitou'].get('repetition_seeds')
    if recorded is not None:
        return {int(key): value for key, value in recorded.items()}
    return {index: seed for index, seed in enumerate(report['meitou'].get('seeds') or [], 1)}


def _commit(report, target):
    commit = report[target].get('build_commit')
    return '`' + commit + '`' if commit else 'build commit not recorded'


def _p(value):
    return 'none' if value is None else f'{value:.4g}'


def _at(checkpoint):
    return checkpoint['name'] + (' (whole scenario)' if checkpoint['at'] is None else f" (at {_json(checkpoint['at'])} s)")


def _test_text(test):
    if not test or test.get('p_value') is None:
        return 'not testable (missing, null or mixed values)'
    mode = ('exact over ' if test['exact'] else 'sampled over ') + f"{test['splits']} splits"
    return (f"two-sided permutation test ({test['kind']}), p = {_p(test['p_value'])}, minimum attainable p = "
            f"{_p(test['minimum_p_value'])}, {mode}")


def _issue(report, group, finding):
    """English draft of one strong group; links are relative to issues/."""
    seeds, scenario = _seeds(report), report['scenario']
    fingerprint = report.get('source_fingerprint')
    disagree = set(disagreeing(finding))
    first = group['first_checkpoint']
    reproduce = group['disagreeing_repetitions'][0] if group['disagreeing_repetitions'] else None
    save = _cell(scenario.get('save', 'not recorded'))
    rows = ['# ' + _cell(scenario['name']) + ': ' + _cell(group['entity']) + ', ' + _cell(group['headline']['metric'])
            + (f" and {group['size'] - 1} related metrics" if group['size'] > 1 else ''), '',
        'Local draft for review. No issue has been published.', '',
        f"Group {group['id']}: {group['size']} metrics, {group['onset']} onset. This is a priority discrepancy, "
        'not proof of its cause.', '',
        '- Scenario: ' + _cell(scenario['name']),
        '- Save: ' + save + '; start-save fingerprint ' + ('`' + str(fingerprint) + '`' if fingerprint else 'not recorded'),
        '- Build commits: original ' + _commit(report, 'original') + '; MeitouClient ' + _commit(report, 'meitou'),
        '- State schema: ' + _cell(report.get('state_schema') or 'not recorded'),
        f"- Original N={report['original']['n']}; Meitou N={report['meitou']['n']}.",
        '- Meitou seeds per repetition: ' + ('; '.join(f'{key}: {value}' for key, value in sorted(seeds.items()))
                                             or 'not recorded') + '. The original takes no seed.',
        '- Group key: entity ' + _cell(group['entity']) + '; disagreeing Meitou repetitions '
        + _json(group['disagreeing_repetitions']) + '; onset ' + group['onset'],
        '- First divergent checkpoint: ' + _cell(_at(first)),
        '- Headline: ' + _cell(group['headline']['metric']) + ' at ' + _cell(finding['checkpoint']) + ', '
        + LABELS[finding['base_classification']].lower() + '; ' + _test_text(finding.get('test')) + '.', '',
        '## Headline observations', '',
        '| Engine | Repetition | Seed | Value | Disagrees | Snapshot |', '| --- | ---: | --- | --- | --- | --- |']
    for target, label in (('original', 'Original'), ('meitou', 'MeitouClient')):
        for row in finding[target]['observations']:
            seed = seeds.get(row['repetition'], 'not recorded') if target == 'meitou' else 'none'
            flag = ('yes' if row['repetition'] in disagree else 'no') if target == 'meitou' else 'reference'
            rows.append(f"| {label} | {row['repetition']} | {seed} | {_json(row['value'])} | {flag} | "
                        f"[snapshot]({_link(row['snapshot'], '../')}) |")
    rows += ['', 'Tolerance: ' + _json(finding['tolerance']), '',
        'Meitou observations outside the original reference: ' + str(finding['meitou'].get('outside_count')), '',
        *([f"This whole-scenario metric also uses {len(finding['additional_snapshots'])} snapshots of every "
           'checkpoint, listed in the [JSON report](../report.json).', '']
          if finding.get('additional_snapshots') else []),
        f"## Member metrics ({group['size']})", '',
        '| Metric | Checkpoints | Class | Disagreeing | p |', '| --- | --- | --- | --- | ---: |']
    for member in group['members'][:DRAFT_MEMBERS]:
        rows.append('| ' + _cell(member['metric']) + ' | ' + _cell(', '.join(member['checkpoints'])) + ' | '
                    + LABELS[member['classification']] + ' | ' + _json(member['disagreeing_repetitions']) + ' | '
                    + _p(member['p_value']) + ' |')
    if group['size'] > DRAFT_MEMBERS:
        rows += ['', f"and {group['size'] - DRAFT_MEMBERS} more; the complete list is in the "
                     '[JSON report](../report.json) under `groups`.']
    rows += ['', 'Reproduce: load save ' + save
             + (f' in MeitouClient with seed {seeds.get(reproduce, "not recorded")} (repetition {reproduce})'
                if reproduce is not None else ' in MeitouClient')
             + (' and compare the whole scenario' if first['at'] is None else ' and compare checkpoint ' + _cell(_at(first)))
             + ' with the original reference.']
    return rows


def _group_rows(groups, link):
    rows = ['| Group | Entity | Onset | First checkpoint | Size | Disagreeing | p | Headline |' + (' Draft |' if link is not None else ''),
            '| --- | --- | --- | --- | ---: | --- | ---: | --- |' + (' --- |' if link is not None else '')]
    for group in groups:
        rows.append('| ' + ' | '.join((group['id'], _cell(group['entity']), group['onset'],
            _cell(group['first_checkpoint']['name']), str(group['size']), _json(group['disagreeing_repetitions']),
            _p(group['p_value']), _cell(group['headline']['metric']))) + ' |'
            + (' [Draft](' + link + group['id'] + '.md) |' if link is not None else ''))
    return rows


def _group_sections(groups, link, limit=None):
    """Strong (drafted), weak and known-deviation group tables; ``link`` is the drafts' folder prefix."""
    strong = [group for group in groups if group['drafted']]
    weak = [group for group in groups if not group['drafted'] and not group['known_deviation']]
    known = [group for group in groups if group['known_deviation']]
    rows = [f"{len(groups)} root-cause groups: {len(strong)} strong (drafted), {len(weak)} weak "
            f"(listed, not drafted), {len(known)} known deviations (listed, not drafted). A group is strong when "
            'its headline p-value is below 0.01.', '']
    for title, chosen, drafts in (('Strong groups (drafted)', strong, link), ('Weak groups (not drafted)', weak, None),
                                  ('Known deviations (grouped, not drafted)', known, None)):
        if not chosen:
            continue
        rows += ['### ' + title, '', *_group_rows(chosen[:limit], drafts)]
        if limit is not None and len(chosen) > limit:
            rows += ['', f'{len(chosen) - limit} further groups are listed in the issue index and report.json.']
        rows.append('')
    return rows


def _plan(findings, order):
    grouped = defaultdict(list)
    for finding in findings:
        if finding['classification'] not in CLASS_ORDER:
            raise ValueError('Unknown comparison classification')
        if finding['classification'] != 'stable_identical':
            grouped[finding['classification']].append(finding)
    plan = []
    for classification in CLASS_ORDER:
        ordered = sorted(grouped[classification], key=order)
        chunks, chunk, size = [], [], 0
        for finding in ordered:
            row_bytes = len(_finding_row(finding, '../').encode('utf-8')) + 1
            if chunk and (len(chunk) >= PAGE_SIZE or size + row_bytes > TARGET_PAGE_BYTES - 4096):
                chunks.append(chunk)
                chunk, size = [], 0
            chunk.append(finding)
            size += row_bytes
        if chunk:
            chunks.append(chunk)
        start = 1
        for index, chunk in enumerate(chunks, 1):
            name = classification.replace('_', '-') + f'-{index:04d}.md'
            metadata = dict(path='details/' + name, classification=classification,
                page=index, pages_in_class=len(chunks), finding_count=len(chunk),
                first_in_class=start, last_in_class=start + len(chunk) - 1)
            plan.append((metadata, chunk))
            start += len(chunk)
    return plan


def _repetition_values(rows):
    return '; '.join(str(row['repetition']) + ': ' + _json(row['value']) for row in rows)


def _scene_rows(report):
    """Unclassified scene facts of a scene-scope report (none without a setup)."""
    if 'scene_scope' not in report:
        return []
    outcome, background = report['scene_outcome'], report['background_metrics']
    cohorts = [row for row in outcome if row['metric'].startswith('/scene/outcome/cohort/')]
    rows = ['', '## Scene outcome and setup facts', '',
        f"{len(outcome)} outcome metrics and {len(background)} background metrics are recorded in the "
        '[complete JSON report](report.json) and never classified. '
        'Values are listed per repetition; there is no verdict on the fight outcome.', '',
        f'Cohort outcome (preview limited to {PAGE_SIZE} rows):', '',
        '| Checkpoint | Metric | Original | MeitouClient |', '| --- | --- | --- | --- |']
    rows += ['| ' + _cell(row['checkpoint']) + ' | ' + _cell(row['metric']) + ' | '
             + _repetition_values(row['original']) + ' | ' + _repetition_values(row['meitou']) + ' |'
             for row in cohorts[:PAGE_SIZE]]
    rows += ['', 'Health maxima per repetition (sum of the part maxima in the setup receipt):', '',
        '| Engine | Repetition | Alias | Part maxima total |', '| --- | ---: | --- | ---: |']
    facts = [(target, fact['repetition'], member) for target in ('original', 'meitou')
             for fact in report['setup_members'][target] for member in fact['members']]
    for target, repetition, member in facts[:PAGE_SIZE]:
        maxima = list((member.get('part_max') or {}).values())
        total = sum(maxima) if maxima and all(type(value) in (int, float) for value in maxima) else None
        rows.append('| ' + target + ' | ' + str(repetition) + ' | ' + _cell(member.get('alias')) + ' | '
                    + _json(total) + ' |')
    if len(facts) > PAGE_SIZE:
        rows += ['', f'{len(facts) - PAGE_SIZE} further member rows are in the complete JSON report.']
    return rows + _nearest_squad_rows(report)


NEAREST_SQUAD = '/background/nearest_squad/'


def _nearest_squad_cell(distance_rows, faction_rows):
    names = {row['repetition']: row['value'] for row in faction_rows}
    cells = []
    for row in distance_rows:
        value = row['value']
        text = 'null' if value is None else str(round(value))
        if names.get(row['repetition']) is not None:
            text += ' ' + _cell(names[row['repetition']])
        cells.append(str(row['repetition']) + ': ' + text)
    return '; '.join(cells)


def _nearest_squad_rows(report):
    """Background table: distance to the nearest squad outside the scene, never classified."""
    rows = {(row['checkpoint'], row['metric']): row for row in report['background_metrics']
            if row['metric'].startswith(NEAREST_SQUAD)}
    order = [point['name'] for point in sorted(report['scenario']['checkpoints'], key=lambda point: point['at'])]
    lines = ['', '## Background: nearest squad outside the scene', '',
        'X/Z distance in world units from the nearest player character to the nearest member of the nearest squad, '
        "excluding the spawn alias squads and every player character's squad, with that squad's faction. Recorded "
        'per repetition as `/background/nearest_squad/` metrics; never classified and never a finding.', '',
        '| Checkpoint | Original | MeitouClient |', '| --- | --- | --- |']
    for name in order:
        distance = rows.get((name, NEAREST_SQUAD + 'distance'))
        faction = rows.get((name, NEAREST_SQUAD + 'faction_name'))
        if distance is None:
            continue
        lines.append('| ' + _cell(name) + ' | '
                     + ' | '.join(_nearest_squad_cell(distance[target], faction[target] if faction else [])
                                  for target in ('original', 'meitou')) + ' |')
    return lines


def render_reports(report, output, *, rewrite=False):
    """Render computed findings; rewrite changes only named local artifact files.

    Stable-identical findings remain complete in JSON. Every other finding has
    a detail page with at most 100 rows (and a 200 KiB target when rows permit).
    Existing unrelated files are preserved; no findings or snapshot is changed.
    """
    if type(rewrite) is not bool:
        raise ValueError('rewrite must be boolean')
    output = Path(output)
    if rewrite:
        if not output.is_dir() or not (output/'report.json').is_file() or not (output/'report.md').is_file():
            raise ValueError('rewrite requires an existing comparison report artifact')
    else:
        output.mkdir(parents=True, exist_ok=False)
    _directory(output)
    _directory(output/'issues')
    _directory(output/'details')
    findings = report['findings']
    # Groups are recomputed from the computed findings (pure, deterministic); nothing is reclassified.
    groups = triage(report)
    order = chronological(checkpoint_times(report, findings))
    counts = Counter(finding['classification'] for finding in findings)
    plan = _plan(findings, order)
    strong = sorted((finding for finding in findings if finding['classification'] == 'stable_divergent'), key=order)
    drafted = [group for group in groups if group['drafted']]
    report['summary'] = dict(original_n=report['original']['n'], meitou_n=report['meitou']['n'],
        findings=len(findings), classifications={name: counts[name] for name in CLASS_ORDER},
        groups=len(groups), strong_groups=len(drafted),
        weak_groups=sum(not group['drafted'] and not group['known_deviation'] for group in groups),
        known_deviation_groups=sum(group['known_deviation'] for group in groups),
        drafts=len(drafted), detail_findings=sum(metadata['finding_count'] for metadata, _ in plan),
        detail_pages=len(plan), preview_findings=min(PREVIEW_SIZE, len(strong)))
    report['details_catalog'] = dict(index='details/index.md', page_size=PAGE_SIZE,
        target_page_bytes=TARGET_PAGE_BYTES, page_count=len(plan),
        findings=report['summary']['detail_findings'], pages=[metadata for metadata, _ in plan])
    pages_by_class = defaultdict(list)
    for metadata, _ in plan:
        pages_by_class[metadata['classification']].append(metadata)
    common = [f"Original N = {report['original']['n']}, MeitouClient N = {report['meitou']['n']}.", '',
        'Descriptive statistics: observed ranges, medians and repetitions outside the range. '
        'Divergent findings carry an exact permutation test; it qualifies one metric, not a cause, '
        'and no evidence of generalization is claimed.', '',
        'Stable classes use the exact original observations. Numerical equality between engines '
        'may depend on the published tolerance; `comparison_exact` distinguishes this case.', '']
    rows = ['# Comparison: ' + _cell(report['scenario']['name']), '', *common,
        f"{len(findings)} metrics; {len(groups)} root-cause groups; {len(drafted)} local English issue drafts; "
        f"{len(plan)} detail pages.", '',
        '[All details](details/index.md) · [Issue drafts](issues/README.md) · [Complete JSON report](report.json)', '',
        '| Class | Count | Details |', '| --- | ---: | --- |']
    for classification in CLASS_ORDER:
        pages = pages_by_class[classification]
        link = '[Open](' + pages[0]['path'] + ')' if pages else '[JSON](report.json)' if counts[classification] else '—'
        rows.append('| ' + LABELS[classification] + ' | ' + str(counts[classification]) + ' | ' + link + ' |')
    rows += ['', 'NPCs without a proven saved origin are compared only in groups. '
        'A disappearance never proves a death. Towns without a shared placement identity remain not comparable.', '',
        '## Root-cause groups', '', *_group_sections(groups, 'issues/', PAGE_SIZE),
        '## First stable divergent findings', '',
        'Preview limited to the 20 earliest stable divergent findings; the detail pages retain all other '
        'discrepancies and unknown coverage.', '',
        *_table_header()]
    rows += [_finding_row(finding) for finding in strong[:PREVIEW_SIZE]]
    rows += _scene_rows(report)
    rows += ['', '## Limitations', '', *['- ' + text for text in report['limitations']], '',
        '## RE_Kenshi context', '',
        'The recorded permanent deviations provide context. None automatically reclassifies the differences above.', '']
    rows += ['- ' + _cell(row['id']) + ': ' + _cell(row['description']) + ' ([source](' + quote(row['source'], safe=':/#?=&.-_') + ')).'
             for row in report.get('reference_deviations', [])]
    _text(output/'report.md', rows)
    index_rows = ['# Comparison details', '', '[Back to summary](../report.md)', '', *common,
        'Each page contains at most 100 metrics. Stable-identical values remain in the complete JSON report.', '']
    for classification in CLASS_ORDER:
        pages = pages_by_class[classification]
        if not pages:
            continue
        index_rows += ['## ' + LABELS[classification], '',
            '| Page | Metrics within this class | Count |', '| --- | --- | ---: |']
        index_rows += ['| [' + str(metadata['page']) + '](' + Path(metadata['path']).name + ') | '
            + str(metadata['first_in_class']) + '–' + str(metadata['last_in_class']) + ' | '
            + str(metadata['finding_count']) + ' |' for metadata in pages]
        index_rows.append('')
    _text(output/'details'/'index.md', index_rows)
    for index, (metadata, page_findings) in enumerate(plan):
        navigation = ['[Summary](../report.md)', '[Index](index.md)']
        if index:
            navigation.append('[Previous](' + Path(plan[index-1][0]['path']).name + ')')
        if index+1 < len(plan):
            navigation.append('[Next](' + Path(plan[index+1][0]['path']).name + ')')
        nav = ' · '.join(navigation)
        rows = ['# ' + LABELS[metadata['classification']] + f" — page {metadata['page']}/{metadata['pages_in_class']}", '',
                nav, '', *common, *_table_header()]
        rows += [_finding_row(finding, '../') for finding in page_findings]
        rows += ['', nav]
        _text(output/metadata['path'], rows)
    indexed = {(finding['metric'], finding['checkpoint']): finding for finding in findings}
    _text(output/'issues'/'README.md', ['# Issue drafts: ' + _cell(report['scenario']['name']), '',
        'Local drafts for review. No issue has been published. One draft per strong root-cause group; weak '
        'groups and known deviations are listed here only.', '', '[Back to summary](../report.md)', '',
        *_group_sections(groups, '')])
    for group in drafted:
        headline = indexed[(group['headline']['metric'], group['headline']['checkpoint'])]
        _text(output/'issues'/(group['id'] + '.md'), _issue(report, group, headline))
    def dump(handle):
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        handle.write('\n')
    _atomic_text(output/'report.json', dump)
