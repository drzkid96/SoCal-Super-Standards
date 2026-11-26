"""Supply exact native DXF primitives to the browser sign-legend writer."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile

SOURCE = Path('data/reference/cad-sign-entities.zip')
PUBLIC = Path('public/data/cad-sign-entities')
PART_BYTES = 7 * 1024 * 1024
TYPES = {'HATCH', 'LINE', 'LWPOLYLINE', 'SPLINE'}
ID = re.compile(r'[a-zA-Z0-9_-]+\Z')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_parts(source=SOURCE):
    return tuple(sorted(source.parent.glob(source.name + '.[0-9][0-9][0-9]')))


def write_parts(archive, source=SOURCE):
    """Preserve the exact ZIP byte stream in ordered repository transport files."""
    published = []
    with archive.open('rb') as stream:
        while chunk := stream.read(PART_BYTES):
            path = source.with_name(f'{source.name}.{len(published)+1:03d}')
            temp = path.with_suffix(path.suffix+'.tmp')
            temp.write_bytes(chunk)
            os.replace(temp, path)
            published.append(path)
    for old in source_parts(source):
        if old not in published:
            old.unlink()
    return published


def open_archive(source):
    parts = source_parts(source)
    if not parts:
        return zipfile.ZipFile(source)
    for number, part in enumerate(parts, 1):
        if part.name != f'{source.name}.{number:03d}':
            raise ValueError('Missing browser CAD geometry archive part')
    return zipfile.ZipFile(io.BytesIO(b''.join(part.read_bytes() for part in parts)))


def write_member(bundle, name, payload, compression):
    member = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    member.compress_type = compression
    member.external_attr = 0o100644 << 16
    bundle.writestr(member, payload)


def native_sections(path, by_name):
    """Stream exact group-code/value records from the independently reopened master."""
    # R2000 DXF has the code page of the master, not UTF-8. Our exported
    # geometry consists of numeric fields and known ASCII class/layer names.
    name, kind = None, None
    blob = bytearray()
    count = 0
    with path.open(encoding='cp1252') as source:
        for raw in source:
            code = int(raw)
            value = next(source).strip()
            if code == 0:
                kind = value
                if kind == 'ENDBLK':
                    if name in by_name:
                        yield by_name[name], bytes(blob), count
                    name = None
                    blob.clear()
                    count = 0
                elif kind == 'BLOCK':
                    name = None
                elif name in by_name:
                    if kind not in TYPES:
                        raise ValueError(f'Unexpected {kind} in {name}')
                    count += 1
            if kind == 'BLOCK' and code == 2:
                name = value
            if name not in by_name or kind == 'BLOCK':
                continue
            # Every destination document allocates its own handles and owners.
            # Reject other cross-document dependencies rather than pruning them.
            if code in {5, 330}:
                continue
            if code in {102, 105, 1005} or 320 <= code <= 369 or 390 <= code <= 399:
                raise ValueError(f'Cross-document DXF tag {code} in {name}')
            if (code == 8 and value != '0') or (code == 62 and int(value) != 7):
                raise ValueError(f'Non-monochrome layer or entity in {name}')
            blob.extend(f'{code}\n{value}\n'.encode('ascii'))


def native_bounds(master, records):
    import ezdxf
    from ezdxf import bbox
    drawing = ezdxf.readfile(master)
    # Read actual drawn extents because a rounded sign can stop short of
    # its nominal panel boundary. Use the measured extent for chart fitting.
    bounds = {}
    for row in records:
        ext = bbox.extents(drawing.blocks[row['masterBlockName']], fast=False)
        if not ext.has_data:
            raise ValueError(f'No native extents for {row["id"]}')
        bounds[row['id']] = [ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y]
    return bounds


def build(master, manifest, target=SOURCE, bounds_file=None):
    source = json.loads(manifest.read_text())
    records = source['records']
    by_name = {r['masterBlockName']:r for r in records}
    if len(by_name) != len(records):
        raise ValueError('Duplicate block definitions')
    boxes = json.loads(bounds_file.read_text()) if bounds_file else native_bounds(master, records)
    index = {}
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.tmp')
    with zipfile.ZipFile(temp, 'w') as bundle:
        for row, payload, count in native_sections(master, by_name):
            key = row['id']
            if not ID.fullmatch(key) or key in index or count != row['entityCount']:
                raise ValueError(f'Unexpected native block in master: {key} ({count})')
            bounds = [round(float(v),8) for v in boxes[key]]
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                raise ValueError(f'Invalid source extents for {key}')
            compressed = gzip.compress(payload, compresslevel=8, mtime=0)
            if gzip.decompress(compressed) != payload:
                raise ValueError(f'Gzip round-trip failed: {key}')
            write_member(bundle, key+'.dxf.gz',compressed,zipfile.ZIP_STORED)
            index[key] = dict(name=row['masterBlockName'],bytes=len(compressed),
                              sha256=digest(compressed),entities=count,bounds=bounds)
        if len(index) != len(records):
            raise ValueError('Incomplete master block library')
        data = json.dumps(index,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        write_member(bundle, 'index.json', data, zipfile.ZIP_DEFLATED)
    write_parts(temp, target)
    temp.unlink()


def hydrate(source=SOURCE, target=PUBLIC):
    """Acquire no CAD runtime or remote data during site builds."""
    target.mkdir(parents=True, exist_ok=True)
    with open_archive(source) as bundle:
        index_bytes = bundle.read('index.json')
        index = json.loads(index_bytes)
        expected = {key+'.dxf.gz' for key in index} | {'index.json'}
        if set(bundle.namelist()) != expected:
            raise ValueError('Incomplete browser CAD primitives package')
        for key, record in index.items():
            if not ID.fullmatch(key): raise ValueError('Invalid CAD key')
            name = key+'.dxf.gz'
            payload = bundle.read(name)
            if len(payload) != record['bytes'] or digest(payload) != record['sha256']:
                raise ValueError(f'Corrupt browser CAD primitives for {key}')
            (target/name).write_bytes(payload)
        for old in target.glob('*.dxf.gz'):
            if old.name not in expected: old.unlink()
        (target/'index.json').write_bytes(index_bytes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master', type=Path, help='Reopened DXF from the actual release master DWG')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--bounds', type=Path, help='Cached extents calculated from this exact master')
    args = parser.parse_args()
    if args.master: build(args.master, args.manifest, bounds_file=args.bounds)
    hydrate()
