"""Reproduce the local, lazy-loaded PDF and OCR assets used by the plan importer."""
from hashlib import sha256
from pathlib import Path, PurePosixPath
from stat import S_IFREG, S_IFMT
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'public/vendor'
ARCHIVE = ROOT / 'data/reference/sign-import-runtime.zip'
DIRECTORIES = ('pdfjs-5.6.205', 'sign-ocr-7.0.0')


def packaged_path(name):
    path = PurePosixPath(name)
    if (path.is_absolute() or '\\' in name or ':' in name or
            not path.parts or path.parts[0] not in DIRECTORIES or
            any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError(f'Invalid sign importer asset path: {name}')
    dest = VENDOR.joinpath(*path.parts)
    if not dest.resolve().is_relative_to(VENDOR.resolve()):
        raise ValueError('Sign importer asset resolves outside the vendor directory')
    return dest


def encode(out, name, data):
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.external_attr = (S_IFREG | 0o644) << 16
    out.writestr(entry, data, compress_type=ZIP_DEFLATED, compresslevel=8)


def pack():
    digests = {}
    files = sorted(p for directory in DIRECTORIES for p in (VENDOR/directory).rglob('*') if p.is_file())
    with ZipFile(ARCHIVE.with_suffix('.tmp'), 'w') as archive:
        for path in files:
            name = path.relative_to(VENDOR).as_posix()
            packaged_path(name)
            data = path.read_bytes()
            digests[name] = sha256(data).hexdigest()
            encode(archive, name, data)
        encode(archive, 'SHA256.json', json.dumps(digests, indent=1, sort_keys=True).encode())
    ARCHIVE.with_suffix('.tmp').replace(ARCHIVE)


def hydrate():
    with ZipFile(ARCHIVE) as archive:
        digests = json.loads(archive.read('SHA256.json'))
        if set(archive.namelist()) != set(digests) | {'SHA256.json'} or len(archive.namelist()) != len(digests) + 1:
            raise ValueError('Sign importer runtime file inventory differs')
        for name, expected in digests.items():
            info = archive.getinfo(name)
            if S_IFMT(info.external_attr >> 16) not in (0, S_IFREG):
                raise ValueError(f'Expected a regular asset file: {name}')
            path = packaged_path(name)
            if path.is_file() and sha256(path.read_bytes()).hexdigest() == expected:
                continue
            data = archive.read(info)
            if sha256(data).hexdigest() != expected:
                raise ValueError(f'Sign importer runtime checksum failed: {name}')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return len(digests)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', action='store_true', help='Rebuild the archive from the local, licensed vendor files')
    args = parser.parse_args()
    if args.pack:
        pack()
    print(f'{hydrate()} verified local PDF and OCR assets')
