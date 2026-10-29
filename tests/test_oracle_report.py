"""Readable pagination preserves every computed finding and local evidence link."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

import pytest

from oracle_compare import classify_metric
from oracle_comparison import write_reports
import oracle_report as renderer


def observations(values, target):
    return [dict(repetition=index, snapshot=f'../../{target}/{index}/initial.json', value=value)
            for index, value in enumerate(values, 1)]


def finding(index, classification):
    values = dict(stable_divergent=([1]*5, [2]*5), stable_identical=([1]*5, [1]*5),
        variable_outside_range=([1, 2, 3, 4, 5], [0, 1, 2, 3, 6]),
        variable_compatible=([1, 2, 3, 4, 5], [2]*5), not_comparable=([1]*5, [None]*5),
        known_deviation=([1]*5, [2]*5))
    left, right = values[classification]
    metric = f'/metric/{classification.replace("_", "-")}/{index:04d}'
    rule = dict(metric=metric, id='explicit-known', source='https://example.test/source',
                explanation='Specific, independently reviewed example.', evidence='evidence/reproduction.json')
    result = classify_metric(metric, observations(left, 'original'), observations(right, 'meitou'),
        tolerance=.000001, known_deviation=rule if classification == 'known_deviation' else None)
    result['checkpoint'] = 'initial'
    return result


def report(counts=None):
    counts = counts or dict(stable_divergent=205, stable_identical=3, variable_outside_range=101,
                           known_deviation=1, variable_compatible=1, not_comparable=1)
    return dict(format_version='0.2', scenario=dict(name='render-fixture'), original=dict(n=5), meitou=dict(n=5),
        findings=[finding(index, classification) for classification, count in counts.items() for index in range(count)],
        limitations=['Sparse observations do not establish exact duration.'], reference_deviations=[])


def data_rows(text):
    return [line for line in text.splitlines() if line.startswith('| initial |')]


def test_main_is_a_short_summary_and_detail_pages_cover_each_nonidentical_finding_once(tmp_path):
    value = report()
    before = deepcopy(value['findings'])
    write_reports(value, tmp_path/'output')
    output = tmp_path/'output'
    main = (output/'report.md').read_text(encoding='utf-8')
    catalog = value['details_catalog']
    assert len(data_rows(main)) == 20
    assert 'details/index.md' in main and 'Complete JSON report' in main
    assert value['summary'] == dict(original_n=5, meitou_n=5, findings=312,
        classifications=dict(stable_divergent=205, stable_identical=3, variable_outside_range=101,
                             known_deviation=1, variable_compatible=1, not_comparable=1),
        drafts=205, detail_findings=309, detail_pages=8, preview_findings=20)
    assert catalog['page_size'] == 100 and catalog['page_count'] == 8
    assert value['findings'] == before
    assert sum(page['finding_count'] for page in catalog['pages']) == 309
    rendered = []
    for index, page in enumerate(catalog['pages']):
        text = (output/page['path']).read_text(encoding='utf-8')
        rows = data_rows(text)
        assert len(rows) == page['finding_count'] <= 100
        assert '[Summary](../report.md)' in text and '[Index](index.md)' in text
        assert ('[Previous]' in text) == (index > 0)
        assert ('[Next]' in text) == (index + 1 < catalog['page_count'])
        rendered.extend(rows)
    assert len(rendered) == len(set(rendered)) == 309
    assert [page['finding_count'] for page in catalog['pages'][:3]] == [100, 100, 5]
    assert [page['classification'] for page in catalog['pages']] == [
        'stable_divergent']*3 + ['variable_outside_range']*2 + ['known_deviation', 'variable_compatible', 'not_comparable']
    assert len(list((output/'issues').glob('*.md'))) == 205
    assert json.loads((output/'report.json').read_bytes())['findings'] == before


def test_detail_statistics_and_photos_use_the_page_directory_for_relative_links(tmp_path):
    value = report(dict(stable_divergent=1))
    value['findings'][0]['additional_snapshots'] = ['../../extra/later.json']
    output = tmp_path/'output'
    write_reports(value, output)
    path = output/value['details_catalog']['pages'][0]['path']
    text = path.read_text(encoding='utf-8')
    for term in ('Original N = 5', 'MeitouClient N = 5', 'Available N 5/5', 'range [1, 1]',
                 'median 1', 'Outside range', 'Tolerance', '"absolute":1e-06'):
        assert term in text
    links = re.findall(r'\[snapshot \d+\]\(([^)]+)\)', text)
    assert len(links) == 11
    assert '../../../original/1/initial.json' in links
    assert '../../../extra/later.json' in links
    for link in links:
        assert (path.parent/unquote(link)).resolve() == (output/unquote(link[3:])).resolve()
    first = value['findings'][0]
    digest = hashlib.sha256((first['checkpoint']+':'+first['metric']).encode()).hexdigest()[:16]
    issue = (output/'issues'/(digest+'.md')).read_text(encoding='utf-8')
    assert 'Local draft for review. No issue has been published.' in issue
    assert 'Photos: ' in issue and '../../../original/1/initial.json' in issue
    assert 'Original N=5; Meitou N=5' in issue


def test_compact_json_is_streamed_and_retains_full_machine_findings(tmp_path, monkeypatch):
    value = report(dict(stable_divergent=1, stable_identical=1))
    dumps, dump = renderer.json.dumps, renderer.json.dump
    streamed = []
    def forbid_whole_report_dumps(obj, *args, **kwargs):
        assert obj is not value, 'The complete report must be streamed'
        return dumps(obj, *args, **kwargs)
    def observe_dump(obj, handle, **kwargs):
        streamed.append((obj is value, kwargs))
        return dump(obj, handle, **kwargs)
    monkeypatch.setattr(renderer.json, 'dumps', forbid_whole_report_dumps)
    monkeypatch.setattr(renderer.json, 'dump', observe_dump)
    write_reports(value, tmp_path/'output')
    payload = (tmp_path/'output'/'report.json').read_bytes()
    assert len(payload.splitlines()) == 1
    assert b'"summary":{' in payload and b'"findings":[' in payload
    assert json.loads(payload) == value
    assert streamed == [(True, dict(ensure_ascii=False, allow_nan=False, separators=(',', ':')))]


def test_rewrite_reformats_only_owned_named_artifacts_without_reclassifying_or_touching_photos(tmp_path, monkeypatch):
    value = report(dict(stable_divergent=2, not_comparable=1))
    output = tmp_path/'output'
    write_reports(value, output)
    extra = output/'reviewer-notes.md'
    extra.write_bytes(b'Keep these notes unchanged.\n')
    snapshot = tmp_path/'photo.json'
    snapshot.write_bytes(b'{"synthetic":"untouched"}\n')
    findings = deepcopy(value['findings'])
    issues = {path.name: path.read_bytes() for path in (output/'issues').glob('*.md')}
    with pytest.raises(FileExistsError):
        write_reports(value, output)
    import oracle_comparison
    def reject_reclassification(*args, **kwargs):
        raise AssertionError('Formatting must not reclassify snapshots')
    monkeypatch.setattr(oracle_comparison, 'classify_metric', reject_reclassification)
    monkeypatch.setattr(oracle_comparison, 'saved_metrics', reject_reclassification)
    write_reports(value, output, rewrite=True)
    assert value['findings'] == findings
    assert issues == {path.name: path.read_bytes() for path in (output/'issues').glob('*.md')}
    assert extra.read_bytes() == b'Keep these notes unchanged.\n'
    assert snapshot.read_bytes() == b'{"synthetic":"untouched"}\n'
    assert not list(output.rglob('.oracle-report-*.tmp'))


def test_long_detail_values_split_before_the_page_target_without_omitting_values(tmp_path):
    value = report(dict(stable_divergent=10))
    for finding in value['findings']:
        left, right = ['A'*4000]*5, [str(index)+'B'*4000 for index in range(5)]
        finding['original'].update(values=left, min=None, max=None, median=None)
        finding['meitou'].update(values=right, min=None, max=None, median=None)
    write_reports(value, tmp_path/'output')
    pages = value['details_catalog']['pages']
    assert len(pages) > 1
    assert sum(page['finding_count'] for page in pages) == 10
    for page in pages:
        text = (tmp_path/'output'/page['path']).read_text(encoding='utf-8')
        assert 'A'*4000 in text and '4'+'B'*4000 in text
        assert len(text.encode('utf-8')) <= renderer.TARGET_PAGE_BYTES


@pytest.mark.parametrize('rewrite', [None, 1, 'yes'])
def test_rewrite_requires_explicit_boolean_and_an_existing_report(tmp_path, rewrite):
    with pytest.raises(ValueError, match='boolean'):
        write_reports(report(dict(stable_divergent=1)), tmp_path/'output', rewrite=rewrite)
    assert not (tmp_path/'output').exists()


def test_rewrite_does_not_adopt_an_unrelated_existing_directory(tmp_path):
    output = tmp_path/'unrelated'; output.mkdir()
    (output/'notes.txt').write_text('Keep me', encoding='utf-8')
    with pytest.raises(ValueError, match='existing comparison'):
        write_reports(report(dict(stable_divergent=1)), output, rewrite=True)
    assert list(output.iterdir()) == [output/'notes.txt']


def test_zero_strong_differences_still_has_six_counts_and_a_complete_json_link(tmp_path):
    value = report(dict(stable_identical=2))
    write_reports(value, tmp_path/'output')
    text = (tmp_path/'output'/'report.md').read_text(encoding='utf-8')
    assert len(data_rows(text)) == 0
    assert value['summary']['drafts'] == value['summary']['detail_pages'] == 0
    assert len(value['summary']['classifications']) == 6
    assert '(report.json)' in text and '(details/index.md)' in text
