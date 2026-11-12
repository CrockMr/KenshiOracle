"""Check the published MeitouClient patch series against its manifest and the native probe.

This test only reads files in this repository. It never applies the patches,
builds MeitouClient or contacts Kenshi.
"""
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / 'integrations' / 'meitou'
ADDED_VERSION = re.compile(r'^\+\s*internal const string AdapterVersion = "([^"]+)";$', re.MULTILINE)
NATIVE_VERSION = re.compile(r'^#define KENSHI_PROBE_VERSION "([^"]+)"$', re.MULTILINE)


def manifest():
    return json.loads((SERIES / 'series.json').read_text(encoding='utf-8'))


def test_series_files_match_the_recorded_hashes_and_sizes():
    patches = manifest()['patches']
    assert [entry['file'] for entry in patches] == sorted(path.name for path in SERIES.glob('*.patch'))
    for entry in patches:
        data = (SERIES / entry['file']).read_bytes()
        assert b'\r' not in data, entry['file']
        assert len(data) == entry['bytes'], entry['file']
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], entry['file']


def test_series_adapter_version_equals_the_native_probe_version():
    # The last AdapterVersion the series adds, in application order, is what a patched build reports as plugin_version.
    versions = [version for entry in manifest()['patches']
                for version in ADDED_VERSION.findall((SERIES / entry['file']).read_text(encoding='utf-8'))]
    assert versions, 'no patch defines OracleProtocol.AdapterVersion'
    native = NATIVE_VERSION.findall((ROOT / 'plugin' / 'Version.h').read_text(encoding='utf-8'))
    assert len(native) == 1
    assert versions[-1] == native[0]


def test_upstream_review_is_recorded_and_repeated_in_the_series_readme():
    # docs/maintenance.md: the last upstream commit reviewed is recorded here and said in plain words in the README.
    review = manifest()['upstream_review']
    readme = (SERIES / 'README.md').read_text(encoding='utf-8')
    assert '<a id="upstream-drift"></a>' in readme
    for key, count in (('head_seen', 'commits_after_base'), ('last_application_check', 'commits_after_base'),
                       ('previous_base', 'commits_before_base'), ('findings_builds', 'commits_before_base')):
        entry = review[key]
        assert re.fullmatch(r'[0-9a-f]{40}', entry['commit']) and entry['commit'] in readme, key
        assert type(entry[count]) is int and entry[count] >= 0, key
        word = 'after' if count == 'commits_after_base' else 'before'
        assert f'{entry[count]} commits {word}' in readme, key
    check = review['last_application_check']
    assert type(check['applies']) is bool
    if not check['applies']:
        assert check['first_conflict']['patch'] in {entry['file'] for entry in manifest()['patches']}
        assert all(name in readme for name in check['first_conflict']['files'])
    assert review['head_seen']['commits_after_base'] >= check['commits_after_base']
    # Seen at the base itself: the head and the base are one commit.
    if review['head_seen']['commits_after_base'] == 0:
        assert review['head_seen']['commit'] == manifest()['upstream_base']
    # The base and the tip the README names are the manifest's.
    assert manifest()['upstream_base'] in readme and manifest()['fork_tip'] in readme
    assert all(entry['source_commit'] in readme for entry in manifest()['patches'])
