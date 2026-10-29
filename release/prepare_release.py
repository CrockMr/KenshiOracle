"""Package reviewed v100 binaries locally; never contact or modify a game/GitHub.

Only Python's standard library is used. The generated mod is an original empty
FCS type-17 descriptor, not a copy of any game or SDK asset. Header facts:
https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/docs/formats/fcs-mod.md
The length is the header BODY size, as confirmed by that revision's FcsReader
and FcsWriter; no executable was inspected to implement this writer.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'dist' / 'v0.9.5'
TAG = 'v0.9.5'
DLL_HASHES = {
    'KenshiProbe.dll': '75739c8e64e17f3a78f482132c9be659aac7d55db7b3151b907b51944af5b580',
    'KenshiProbeBootstrap.dll': '75fa8f5e6cea013cb1e011eb8b3adee662827408056b5dca8c4a0b5a7c4a3a6a',
}
MAIN_ZIP = 'KenshiProbe-v0.9.5-win-x64.zip'
SYMBOLS_ZIP = 'KenshiProbe-v0.9.5-symbols.zip'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                    + '\n', encoding='utf-8', newline='\n')


def source_inputs() -> dict[str, str]:
    paths = [ROOT / 'LICENSE']
    for path in (ROOT / 'plugin').iterdir():
        if path.is_file() and (path.suffix in ('.cpp', '.h', '.vcxproj')
                               or path.name in ('build-v100.cmd', 'prepare_deps.py', 'RE_Kenshi.json')):
            paths.append(path)
    return {path.relative_to(ROOT).as_posix(): digest(path.read_bytes().replace(b'\r\n', b'\n'))
            for path in sorted(paths)}


def empty_mod() -> bytes:
    def text(value: str) -> bytes:
        encoded = value.encode('utf-8')
        return struct.pack('<i', len(encoded)) + encoded

    body = (struct.pack('<i', 1) + text('KenshiProbe contributors')
            + text('KenshiProbe 0.9.5 plugin loader; no game data records.')
            + text('') + text('') + struct.pack('<IIBB', 1, 0, 0, 0))
    return struct.pack('<ii', 17, len(body)) + body + struct.pack('<ii', 1, 0)


def inspect_mod(data: bytes) -> dict:
    stream = io.BytesIO(data)

    def integer() -> int:
        raw = stream.read(4)
        if len(raw) != 4:
            raise ValueError('Truncated generated mod')
        return struct.unpack('<i', raw)[0]

    def text() -> str:
        count = integer()
        if not 0 <= count <= 4096:
            raise ValueError('Invalid generated mod string size')
        raw = stream.read(count)
        if len(raw) != count:
            raise ValueError('Truncated generated mod string')
        return raw.decode('utf-8')

    kind, header_length = integer(), integer()
    header_end = stream.tell() + header_length
    version = integer()
    author, description, dependencies, references = [text() for _ in range(4)]
    bookkeeping = stream.read(10)
    if (kind != 17 or version != 1 or dependencies or references
            or bookkeeping != struct.pack('<IIBB', 1, 0, 0, 0)
            or stream.tell() != header_end):
        raise ValueError('Generated mod does not have the expected empty type-17 header')
    next_id, records = integer(), integer()
    if next_id != 1 or records != 0 or stream.read():
        raise ValueError('Generated mod unexpectedly contains game records or trailing data')
    return dict(file_type=kind, version=version, header_bytes=header_length,
                author=author, description=description, record_count=records,
                bytes=len(data), sha256=digest(data))


def check_pe(data: bytes, name: str) -> None:
    if data[:2] != b'MZ' or len(data) < 64:
        raise ValueError(name + ' is not a PE executable')
    offset = struct.unpack_from('<I', data, 60)[0]
    if data[offset:offset + 4] != b'PE\0\0' or struct.unpack_from('<H', data, offset + 4)[0] != 0x8664:
        raise ValueError(name + ' is not a Windows x64 PE executable')


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)


def snapshot(folder: Path) -> dict:
    return {path.relative_to(folder).as_posix():
            ('directory' if path.is_dir() else digest(path.read_bytes()))
            for path in sorted(folder.rglob('*'))}


def remove_test_tree(path: Path, sandbox: Path) -> None:
    path = path.resolve()
    sandbox = sandbox.resolve()
    if path == sandbox or not path.is_relative_to(sandbox):
        raise ValueError('Refusing removal outside the synthetic installation sandbox')
    if path.exists():
        shutil.rmtree(path)


def verify_install(archive_path: Path, expected: dict[str, bytes]) -> dict:
    runtime = ROOT / 'runtime' / 'publication'
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='release-install-', dir=runtime) as temporary:
        sandbox = Path(temporary).resolve()
        mods = sandbox / 'test-game' / 'mods'
        existing = mods / 'KenshiProbe'
        existing.mkdir(parents=True)
        (existing / 'RE_Kenshi.json').write_bytes(b'{"original":"fixture"}\n')
        (existing / 'KenshiProbe.dll').write_bytes(b'synthetic previous DLL, never executed')
        (existing / 'keep.txt').write_bytes(b'preserve unrelated local file\r\n')
        (mods / 'UnrelatedMod').mkdir()
        (mods / 'UnrelatedMod' / 'keep.txt').write_bytes(b'unrelated mod\n')
        before = snapshot(mods)
        backup = sandbox / 'backup-KenshiProbe'
        shutil.copytree(existing, backup)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError('Archive member list differs from the explicit package allowlist')
            for name in names:
                target = (sandbox / 'test-game' / name).resolve()
                if not target.is_relative_to(sandbox / 'test-game'):
                    raise ValueError('Unsafe archive member')
                data = archive.read(name)
                if data != expected[name]:
                    raise ValueError('Archive content mismatch: ' + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        manifest = json.loads((existing / 'RE_Kenshi.json').read_bytes())
        if manifest != {'PreloadPlugins': ['KenshiProbeBootstrap.dll'], 'Plugins': ['KenshiProbe.dll']}:
            raise ValueError('Unexpected plugin manifest')
        for name in manifest['PreloadPlugins'] + manifest['Plugins']:
            if digest((existing / name).read_bytes()) != DLL_HASHES[name]:
                raise ValueError('Installed DLL hash mismatch')
        descriptor = inspect_mod((existing / 'KenshiProbe.mod').read_bytes())
        if (existing / 'auto_launch.enabled').exists():
            raise ValueError('Package must not activate the optional bootstrap')
        remove_test_tree(existing, sandbox)
        shutil.copytree(backup, existing)
        restored = snapshot(mods) == before
        if not restored:
            raise ValueError('Synthetic mod tree was not exactly restored')
        return dict(archive_members=sorted(expected), extraction_verified=True,
                    manifest_targets_verified=True, mod_descriptor=descriptor,
                    synthetic_previous_installation_restored=restored,
                    real_game_modified=False, runtime_loading_tested=False)


def bind_source(repository: str, revision: str) -> None:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('--repository must be OWNER/REPOSITORY')
    commit = subprocess.run(['git', 'rev-parse', '--verify', revision + '^{commit}'],
                            cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    manifest = json.loads((OUTPUT / 'source-manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        committed = subprocess.run(['git', 'show', commit + ':' + name], cwd=ROOT,
                                   check=True, capture_output=True).stdout
        if digest(committed.replace(b'\r\n', b'\n')) != expected:
            raise ValueError('Release input differs from corresponding source commit: ' + name)
    source_url = 'https://github.com/' + repository + '/tree/' + commit
    template = (ROOT / 'release' / 'v0.9.5-notes.md').read_text(encoding='utf-8')
    (OUTPUT / 'release-notes.md').write_text(template.replace('{{SOURCE_URL}}', source_url),
                                           encoding='utf-8', newline='\n')
    info = json.loads((OUTPUT / 'build-info.json').read_text(encoding='utf-8'))
    info.update(source_commit=commit, source_url=source_url, source_binding='verified_native_inputs')
    write_json(OUTPUT / 'build-info.json', info)
    print('Verified corresponding native sources: ' + source_url)


def prepare() -> None:
    files = {
        'INSTALL.txt': (ROOT / 'release' / 'INSTALL.txt').read_bytes(),
        'LICENSE': (ROOT / 'LICENSE').read_bytes(),
        'mods/KenshiProbe/RE_Kenshi.json': (ROOT / 'plugin' / 'RE_Kenshi.json').read_bytes(),
        'mods/KenshiProbe/KenshiProbe.mod': empty_mod(),
    }
    for name, expected_hash in DLL_HASHES.items():
        data = (ROOT / 'plugin' / 'build' / 'Release' / name).read_bytes()
        if digest(data) != expected_hash:
            raise ValueError(name + ' does not match the reviewed phase 1 binary')
        check_pe(data, name)
        files['mods/KenshiProbe/' + name] = data
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Stage only explicitly named output files, never the build/game directories.
    for name, data in files.items():
        path = OUTPUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_zip(OUTPUT / MAIN_ZIP, files)
    symbols = (ROOT / 'plugin' / 'build' / 'Release' / 'KenshiProbe.pdb').read_bytes()
    if digest(symbols) != '51fa54bc8c0e96daa80b7dc3d6bb831d126a419d89f050899bbf0286af4aadfe':
        raise ValueError('PDB does not match the reviewed phase 1 symbols')
    write_zip(OUTPUT / SYMBOLS_ZIP, {'KenshiProbe.pdb': symbols})
    checksums = {**{name: digest(data) for name, data in files.items() if name.endswith('.dll')},
                 MAIN_ZIP: digest((OUTPUT / MAIN_ZIP).read_bytes()),
                 SYMBOLS_ZIP: digest((OUTPUT / SYMBOLS_ZIP).read_bytes())}
    (OUTPUT / 'SHA256SUMS').write_text(''.join(value + '  ' + name + '\n'
                                     for name, value in sorted(checksums.items())), encoding='ascii')
    manifest = dict(hash_algorithm='sha256', text_normalization='CRLF to LF', files=source_inputs())
    write_json(OUTPUT / 'source-manifest.json', manifest)
    write_json(OUTPUT / 'build-info.json', dict(version=TAG, configuration='Release', platform='x64',
               toolset='v100', binary_origin='reviewed phase 1 delivery; not rebuilt by packaging',
               source_commit=None, source_url=None, source_binding='pending_publication_commit',
               sha256=checksums, mod_descriptor=inspect_mod(empty_mod())))
    template = (ROOT / 'release' / 'v0.9.5-notes.md').read_text(encoding='utf-8')
    (OUTPUT / 'release-notes.md').write_text(template, encoding='utf-8', newline='\n')
    verification = verify_install(OUTPUT / MAIN_ZIP, files)
    write_json(OUTPUT / 'installation-verification.json', verification)
    print('Prepared ' + str(OUTPUT))
    print('Main archive SHA-256: ' + checksums[MAIN_ZIP])
    print('Synthetic installation and exact restoration verified; source URL needs binding.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind-source', action='store_true')
    parser.add_argument('--repository', help='GitHub OWNER/REPOSITORY; no network call is made')
    parser.add_argument('--source-commit', help='Local reviewed commit matching all native inputs')
    args = parser.parse_args()
    if args.bind_source:
        if not args.repository or not args.source_commit:
            parser.error('--bind-source requires --repository and --source-commit')
        bind_source(args.repository, args.source_commit)
    elif args.repository or args.source_commit:
        parser.error('Use --bind-source to bind an existing package to a reviewed commit')
    else:
        prepare()


if __name__ == '__main__':
    main()
