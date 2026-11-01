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
