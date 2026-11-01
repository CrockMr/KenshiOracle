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
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.11.0'
TAG = 'v' + VERSION
OUTPUT = ROOT / 'dist' / TAG
# No 0.11.0 binary has been reviewed yet: packaging refuses until these are set.
DLL_HASHES = {
    'KenshiProbe.dll': None,
    'KenshiProbeBootstrap.dll': None,
}
MAIN_ZIP = 'KenshiProbe-' + TAG + '-win-x64.zip'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                    + '\n', encoding='utf-8', newline='\n')


def source_inputs() -> dict[str, str]:
    paths = [ROOT / 'LICENSE', ROOT / 'release' / 'prepare_release.py',
             ROOT / 'release' / 'INSTALL.txt', ROOT / 'release' / (TAG + '-notes.md')]
    for path in (ROOT / 'plugin').iterdir():
        if path.is_file() and (path.suffix in ('.cpp', '.h', '.vcxproj', '.cmd')
                               or path.name in ('build-v100.cmd', 'prepare_deps.py', 'RE_Kenshi.json')):
            paths.append(path)
    return {path.relative_to(ROOT).as_posix(): digest(path.read_bytes().replace(b'\r\n', b'\n'))
            for path in sorted(paths)}


def empty_mod() -> bytes:
    def text(value: str) -> bytes:
        encoded = value.encode('utf-8')
        return struct.pack('<i', len(encoded)) + encoded

    body = (struct.pack('<i', 1) + text('KenshiProbe contributors')
            + text('KenshiProbe ' + VERSION + ' plugin loader; no game data records.')
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


def privacy_check(data: bytes, name: str) -> None:
    """Reject machine paths in ordinary UTF-8/ASCII and UTF-16LE strings."""
    strings = [value.decode('utf-8', errors='replace')
               for value in re.findall(rb'[\x20-\x7e]{6,}', data)]
    strings += [value.decode('utf-16-le')
                for value in re.findall(rb'(?:[\x20-\x7e]\x00){6,}', data)]
    absolute = re.compile(r'(?<![A-Za-z0-9_])[A-Za-z]:[\\/]|[\\/]Users[\\/]|/home/')
    username = os.environ.get('USERNAME', '')
    for value in strings:
        if absolute.search(value):
            raise ValueError(name + ' contains an absolute machine-path string')
        if len(username) >= 4 and re.search(r'\b' + re.escape(username) + r'\b', value, re.I):
            raise ValueError(name + ' contains the current Windows account name')


def check_pe(data: bytes, name: str) -> dict:
    if data[:2] != b'MZ' or len(data) < 64:
        raise ValueError(name + ' is not a PE executable')
    offset = struct.unpack_from('<I', data, 60)[0]
    if data[offset:offset + 4] != b'PE\0\0' or struct.unpack_from('<H', data, offset + 4)[0] != 0x8664:
        raise ValueError(name + ' is not a Windows x64 PE executable')
    count = struct.unpack_from('<H', data, offset + 6)[0]
    optional_size = struct.unpack_from('<H', data, offset + 20)[0]
    optional = offset + 24
    if struct.unpack_from('<H', data, optional)[0] != 0x20b:
        raise ValueError(name + ' does not have a PE32+ optional header')
    debug_rva, debug_size = struct.unpack_from('<II', data, optional + 112 + 6 * 8)
    sections = optional + optional_size

    def file_offset(rva):
        for index in range(count):
            virtual_size, va, raw_size, pointer = struct.unpack_from('<IIII', data, sections + index * 40 + 8)
            if va <= rva < va + max(virtual_size, raw_size):
                return pointer + rva - va
        raise ValueError(name + ' has an unmapped debug RVA')

    pdb_paths = []
    for index in range(debug_size // 28):
        entry = file_offset(debug_rva) + index * 28
        kind, size, _, pointer = struct.unpack_from('<IIII', data, entry + 12)
        if kind == 2:
            if data[pointer:pointer + 4] != b'RSDS':
                raise ValueError(name + ' has an unsupported CodeView format')
            path = data[pointer + 24:pointer + size].split(b'\0', 1)[0].decode('utf-8')
            if path != Path(name).stem + '.pdb':
                raise ValueError(name + ' must use a neutral PDB basename')
            pdb_paths.append(path)
    privacy_check(data, name)
    if name == 'KenshiProbe.dll' and VERSION.encode('ascii') not in data:
        raise ValueError('Probe version is missing from the reviewed native binary')
    return dict(sha256=digest(data), bytes=len(data), architecture='x64',
                pdb_paths=pdb_paths, machine_paths_found=False, current_account_name_found=False)


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
    if not (ROOT / '.git').exists():
        raise ValueError('Source binding requires a repository root; refusing Git discovery in an ancestor')
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout.strip()
    if Path(top).resolve() != ROOT.resolve():
        raise ValueError('Source binding requires this export to be a repository root; refusing an ancestor repository')
    commit = subprocess.run(['git', 'rev-parse', '--verify', revision + '^{commit}'],
                            cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    manifest = json.loads((OUTPUT / 'source-manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        committed = subprocess.run(['git', 'show', commit + ':' + name], cwd=ROOT,
                                   check=True, capture_output=True).stdout
        if digest(committed.replace(b'\r\n', b'\n')) != expected:
            raise ValueError('Release input differs from corresponding source commit: ' + name)
    source_url = 'https://github.com/' + repository + '/tree/' + commit
    template = (ROOT / 'release' / (TAG + '-notes.md')).read_text(encoding='utf-8')
    notes = template.replace('{{SOURCE_URL}}', source_url).replace('](../docs/', '](' + source_url + '/docs/')
    (OUTPUT / 'release-notes.md').write_text(notes,
                                           encoding='utf-8', newline='\n')
    info = json.loads((OUTPUT / 'build-info.json').read_text(encoding='utf-8'))
    info.update(source_commit=commit, source_url=source_url, source_binding='verified_release_inputs')
    write_json(OUTPUT / 'build-info.json', info)
    write_checksums()
    print('Verified corresponding native sources: ' + source_url)


def write_checksums() -> None:
    names = [MAIN_ZIP, 'mods/KenshiProbe/KenshiProbe.dll', 'mods/KenshiProbe/KenshiProbeBootstrap.dll',
             'build-info.json', 'source-manifest.json', 'binary-audit.json',
             'installation-verification.json', 'release-notes.md']
    (OUTPUT / 'SHA256SUMS').write_text(''.join(digest((OUTPUT / name).read_bytes()) + '  ' + name + '\n'
                                             for name in sorted(names)), encoding='ascii')


def prepare() -> None:
    version_header = (ROOT / 'plugin' / 'Version.h').read_text(encoding='utf-8')
    if '#define KENSHI_PROBE_VERSION "' + VERSION + '"' not in version_header:
        raise ValueError('Packaging version and native Version.h differ')
    files = {
        'INSTALL.txt': (ROOT / 'release' / 'INSTALL.txt').read_bytes(),
        'LICENSE': (ROOT / 'LICENSE').read_bytes(),
        'mods/KenshiProbe/RE_Kenshi.json': (ROOT / 'plugin' / 'RE_Kenshi.json').read_bytes(),
        'mods/KenshiProbe/KenshiProbe.mod': empty_mod(),
    }
    binary_audit = {}
    for name, expected_hash in DLL_HASHES.items():
        data = (ROOT / 'plugin' / 'build' / 'Release' / name).read_bytes()
        if expected_hash is None:
            raise ValueError('No reviewed ' + TAG + ' hash is recorded for ' + name)
        if digest(data) != expected_hash:
            raise ValueError(name + ' does not match the reviewed ' + TAG + ' binary')
        binary_audit[name] = check_pe(data, name)
        files['mods/KenshiProbe/' + name] = data
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Stage only explicitly named output files, never the build/game directories.
    for name, data in files.items():
        path = OUTPUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_zip(OUTPUT / MAIN_ZIP, files)
    # /PDBALTPATH protects the DLL's reference, not paths inside a raw PDB.
    # Keep debugging symbols private rather than publishing source-machine paths.
    checksums = {**{name: digest(data) for name, data in files.items() if name.endswith('.dll')},
                 MAIN_ZIP: digest((OUTPUT / MAIN_ZIP).read_bytes())}
    manifest = dict(hash_algorithm='sha256', text_normalization='CRLF to LF', files=source_inputs())
    write_json(OUTPUT / 'source-manifest.json', manifest)
    write_json(OUTPUT / 'build-info.json', dict(version=TAG, configuration='Release', platform='x64',
               toolset='v100', binary_origin='reviewed release build; not rebuilt by packaging',
               source_commit=None, source_url=None, source_binding='pending_publication_commit',
               symbols_published=False, symbols_reason='raw PDBs may contain source-machine paths',
               sha256=checksums, mod_descriptor=inspect_mod(empty_mod())))
    template = (ROOT / 'release' / (TAG + '-notes.md')).read_text(encoding='utf-8')
    (OUTPUT / 'release-notes.md').write_text(template, encoding='utf-8', newline='\n')
    verification = verify_install(OUTPUT / MAIN_ZIP, files)
    write_json(OUTPUT / 'installation-verification.json', verification)
    for name, data in files.items():
        privacy_check(data, name)
    write_json(OUTPUT / 'binary-audit.json', dict(version=TAG, binaries=binary_audit,
               archive_members_checked=sorted(files), forbidden_machine_paths_found=False,
               raw_symbols_included=False))
    write_checksums()
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
