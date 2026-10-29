"""Bounded Markdown pages and a compact streamed JSON comparison artifact."""
from collections import Counter, defaultdict
import hashlib
import html
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote


CLASS_ORDER = ('stable_divergent', 'stable_identical', 'variable_outside_range',
               'known_deviation', 'variable_compatible', 'not_comparable')
LABELS = dict(stable_identical='Stable identical', stable_divergent='Stable divergent',
              variable_compatible='Variable compatible', variable_outside_range='Variable outside range',
              known_deviation='Known deviation', not_comparable='Not comparable')
PAGE_SIZE = 100
PREVIEW_SIZE = 20
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


def _issue(report, finding):
    # Keep the existing English draft text and hash-based filenames unchanged.
    return ['# ' + report['scenario']['name'] + ': stable difference in ' + finding['metric'], '',
        'Local draft for review. No issue has been published.', '',
        f"Checkpoint: {finding['checkpoint']}. Original N={report['original']['n']}; Meitou N={report['meitou']['n']}.", '',
        'The original value is identical across all observed repetitions; at least one Meitou value differs '
        'beyond the declared numerical tolerance. This is a priority discrepancy, not proof of its cause.', '',
        'Original: ' + '; '.join(_unique(finding['original'])), '',
        'Meitou: ' + '; '.join(_unique(finding['meitou'])), '',
        'Tolerance: ' + _json(finding['tolerance']), '',
        'Meitou observations outside the original reference: ' + str(finding['meitou'].get('outside_count')), '',
        'Photos: ' + _photos(finding, '../'), '',
        'Reproduce using the same scenario/save fingerprint, verified reference settings and the recorded Meitou seeds.']


def _plan(findings):
    grouped = defaultdict(list)
    for finding in findings:
        if finding['classification'] not in CLASS_ORDER:
            raise ValueError('Unknown comparison classification')
        if finding['classification'] != 'stable_identical':
            grouped[finding['classification']].append(finding)
    plan = []
    for classification in CLASS_ORDER:
        ordered = sorted(grouped[classification], key=lambda finding: (finding['checkpoint'], finding['metric']))
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
    counts = Counter(finding['classification'] for finding in findings)
    plan = _plan(findings)
    strong = sorted((finding for finding in findings if finding['classification'] == 'stable_divergent'),
                    key=lambda finding: (finding['checkpoint'], finding['metric']))
    report['summary'] = dict(original_n=report['original']['n'], meitou_n=report['meitou']['n'],
        findings=len(findings), classifications={name: counts[name] for name in CLASS_ORDER},
        drafts=len(strong), detail_findings=sum(metadata['finding_count'] for metadata, _ in plan),
        detail_pages=len(plan), preview_findings=min(PREVIEW_SIZE, len(strong)))
    report['details_catalog'] = dict(index='details/index.md', page_size=PAGE_SIZE,
        target_page_bytes=TARGET_PAGE_BYTES, page_count=len(plan),
        findings=report['summary']['detail_findings'], pages=[metadata for metadata, _ in plan])
    pages_by_class = defaultdict(list)
    for metadata, _ in plan:
        pages_by_class[metadata['classification']].append(metadata)
    common = [f"Original N = {report['original']['n']}, MeitouClient N = {report['meitou']['n']}.", '',
        'Descriptive statistics: observed ranges, medians and repetitions outside the range. '
        'No significance test or evidence of generalization is claimed.', '',
        'Stable classes use the exact original observations. Numerical equality between engines '
        'may depend on the published tolerance; `comparison_exact` distinguishes this case.', '']
    rows = ['# Comparison: ' + _cell(report['scenario']['name']), '', *common,
        f"{len(findings)} metrics; {len(strong)} local English issue drafts; {len(plan)} detail pages.", '',
        '[All details](details/index.md) · [Complete JSON report](report.json)', '',
        '| Class | Count | Details |', '| --- | ---: | --- |']
    for classification in CLASS_ORDER:
        pages = pages_by_class[classification]
        link = '[Open](' + pages[0]['path'] + ')' if pages else '[JSON](report.json)' if counts[classification] else '—'
        rows.append('| ' + LABELS[classification] + ' | ' + str(counts[classification]) + ' | ' + link + ' |')
    rows += ['', 'NPCs without a proven saved origin are compared only in groups. '
        'A disappearance never proves a death. Towns without a shared placement identity remain not comparable.', '',
        '## First strong discrepancies', '',
        'Preview limited to 20 strong discrepancies; the detail pages retain all other discrepancies and unknown coverage.', '',
        *_table_header()]
    rows += [_finding_row(finding) for finding in strong[:PREVIEW_SIZE]]
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
    for finding in strong:
        digest = hashlib.sha256((finding['checkpoint'] + ':' + finding['metric']).encode()).hexdigest()[:16]
        _text(output/'issues'/(digest + '.md'), _issue(report, finding))
    def dump(handle):
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        handle.write('\n')
    _atomic_text(output/'report.json', dump)
