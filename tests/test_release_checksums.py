"""SHA256SUMS must be checkable by `sha256sum -c` on every platform."""
import hashlib
import importlib.util
from pathlib import Path


def load_packager():
    path = Path(__file__).resolve().parent.parent / 'release' / 'prepare_release.py'
    spec = importlib.util.spec_from_file_location('prepare_release_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sha256sums_uses_lf_line_endings_and_gnu_format(tmp_path, monkeypatch):
    packager = load_packager()
    monkeypatch.setattr(packager, 'OUTPUT', tmp_path)
    names = [packager.MAIN_ZIP, 'mods/KenshiProbe/KenshiProbe.dll',
             'mods/KenshiProbe/KenshiProbeBootstrap.dll', 'build-info.json',
             'source-manifest.json', 'binary-audit.json',
             'installation-verification.json', 'release-notes.md']
    for index, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture %d\n' % index)

    packager.write_checksums()

    data = (tmp_path / 'SHA256SUMS').read_bytes()
    assert b'\r' not in data
    lines = data.decode('ascii').split('\n')
    assert lines[-1] == ''
    entries = [line.split('  ', 1) for line in lines[:-1]]
    assert [name for _, name in entries] == sorted(names)
    for value, name in entries:
        assert value == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
