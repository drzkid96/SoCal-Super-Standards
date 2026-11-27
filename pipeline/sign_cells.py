"""Sign blocks in sign-legend table cells: one block entity and one MTEXT code per drawing.

Every published sign drawing holds exactly two model-space entities:
  1. an INSERT of the sign block at 0,0, the lower-left corner of its table cell;
  2. an MTEXT with the sign code, bottom-center justified under the face.
The block's base point is the cell corner, and its face is scaled to fit the cell.
Cell, face and caption sizes come from the measured LADOT plan sign legend
(data/reference/ladot-legend-layout.json), in plotted inches.

Build locally (needs the pinned LibreDWG dxf2dwg and dwg2dxf, and LibreCAD libdxfrw as the second reader):
  python3 pipeline/sign_cells.py build --libredwg <dir> --libdxfrw <libdxfrw dwg2dxf>
The build writes data/reference/sign-cells.zip. Publishing only reads that pack.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

PACK = Path('data/reference/sign-cells.zip')
LAYOUT = json.loads(Path('data/reference/ladot-legend-layout.json').read_text())
FIT = LAYOUT['fitting']
CELL_W, CELL_H = LAYOUT['cellWidth'], LAYOUT['cellHeight']
FACE_W, FACE_H = FIT['maxFaceWidth'], FIT['maxFaceHeight']
ART_X, ART_Y = FIT['artCenterFromLowerLeft']
CODE_Y, CODE_H = FIT['captionBaseline'], FIT['captionHeight']
CODE_MAX_W = CELL_W - 0.065
ROMANS_ADVANCE = 0.84  # mean advance of romans.shx capitals and digits, as a share of text height
LAYERS = {'P-SIGN': 7, 'P-SIGN-TEXT': 7, 'P-SIGN-TABL': 8, 'P-SIGN-TITL': 7}
STYLES = {'ROMANS': 'romans.shx', 'ARIAL': 'arial.ttf'}
HEADER = '0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n9\n$INSUNITS\n70\n1\n0\nENDSEC\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def code_text(code):
    return ' '.join(code.split())


def code_height(code):
    return round(min(CODE_H, CODE_MAX_W / (ROMANS_ADVANCE * max(len(code), 1))), 4)


def fit(bounds):
    """Scale and offset that place native face bounds inside the cell."""
    x0, y0, x1, y1 = bounds
    s = min(FACE_W / (x1 - x0), FACE_H / (y1 - y0))
    return s, ART_X - s * (x0 + x1) / 2, ART_Y - s * (y0 + y1) / 2


def parse_fragment(text):
    """Read the native entity fragment the browser legend writer also uses."""
    from ezdxf import recover
    pairs = text.strip().split('\n')
    out, handle = [], 0x100
    for i in range(0, len(pairs) - 1, 2):
        out += [pairs[i], pairs[i + 1]]
        if pairs[i].strip() == '0':
            handle += 1
            out += ['5', format(handle, 'X')]
    dxf = HEADER + '0\nSECTION\n2\nENTITIES\n' + '\n'.join(out) + '\n0\nENDSEC\n0\nEOF\n'
    doc, _ = recover.read(io.BytesIO(dxf.encode()))
    return doc


def r2000_document():
    """An AutoCAD 2000 drawing with ROMANS and ARIAL styles and the sign layers."""
    import ezdxf
    doc = ezdxf.new('R2000', setup=False)
    doc.units = 1
    doc.header['$MEASUREMENT'] = 0
    doc.header['$LUNITS'] = 2
    doc.header['$LUPREC'] = 4
    doc.header['$TEXTSTYLE'] = 'ROMANS'
    doc.header['$DIMSTYLE'] = 'Standard'  # ezdxf names ISO-25, which a drawing without that style cannot resolve
    for name, font in STYLES.items():
        doc.styles.new(name, dxfattribs={'font': font, 'width': 1.0})
    for name, color in LAYERS.items():
        doc.layers.new(name, dxfattribs={'color': color})
    return doc


def cell_document(name, code, fragment, bounds):
    from ezdxf.math import Matrix44
    doc = r2000_document()
    block = doc.blocks.new(name, base_point=(0, 0))
    block.block_record.dxf.units = 1
    s, dx, dy = fit(bounds)
    m = Matrix44.chain(Matrix44.scale(s, s, s), Matrix44.translate(dx, dy, 0))
    source = parse_fragment(fragment)
    for entity in source.modelspace():
        copy = entity.copy()
        if copy.dxftype() == 'LWPOLYLINE':   # repeated vertices in the source faces
            pts = list(copy.get_points('xyseb'))
            kept = [p for i, p in enumerate(pts) if i == 0 or abs(p[0] - pts[i - 1][0]) > 1e-9 or abs(p[1] - pts[i - 1][1]) > 1e-9]
            if len(kept) < 2:
                continue
            if len(kept) != len(pts):
                copy.set_points(kept, format='xyseb')
        copy.transform(m)
        if copy.dxftype() == 'LINE' and (copy.dxf.start - copy.dxf.end).magnitude < 1e-6:
            continue   # zero-length lines in the source faces (checked at plotted size)
        copy.dxf.layer = '0'
        copy.dxf.color = 0  # BYBLOCK: the face follows the INSERT layer and color
        block.add_entity(copy)
    model = doc.modelspace()
    model.add_blockref(name, (0, 0), dxfattribs={'layer': 'P-SIGN'})
    text = model.add_mtext(code_text(code).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}'), dxfattribs={'layer': 'P-SIGN-TEXT', 'style': 'ROMANS', 'char_height': code_height(code_text(code)),
                                             'insert': (ART_X, CODE_Y), 'attachment_point': 8, 'width': 0})
    text.dxf.attachment_point = 8
    doc.set_modelspace_vport(height=CELL_H * 1.15, center=(CELL_W / 2, CELL_H / 2))
    doc.header['$EXTMIN'] = (0, 0, 0)
    doc.header['$EXTMAX'] = (CELL_W, CELL_H, 0)
    return doc


def check(path, name, code, entities, ascii_only=False):
    """Both open-source readers must see one INSERT, one MTEXT and the full block."""
    import ezdxf
    d = ezdxf.readfile(path)
    model = [e.dxftype() for e in d.modelspace()]
    if model != ['INSERT', 'MTEXT']:
        raise ValueError(f'{name}: model space holds {model}')
    ins, mt = list(d.modelspace())
    if ins.dxf.name != name or abs(ins.dxf.insert.x) > 1e-9 or abs(ins.dxf.insert.y) > 1e-9:
        raise ValueError(f'{name}: block reference is not at the cell corner')
    shown = re.sub(r'\\U\+([0-9A-Fa-f]{4})', lambda m: chr(int(m[1], 16)), mt.plain_text())
    expected = code_text(code)
    if ascii_only:  # libdxfrw reads the stored \\U+ escape with a code page, so compare the ASCII text
        shown, expected = (re.sub(r'[^ -~]', '', v) for v in (shown, expected))
    if shown != expected or mt.dxf.style.upper() != 'ROMANS':
        raise ValueError(f'{name}: code text differs')
    if len(d.blocks[name]) != entities:
        raise ValueError(f'{name}: block holds {len(d.blocks[name])} of {entities} entities')
    if d.header.get('$INSUNITS') != 1:
        raise ValueError(f'{name}: units are not inches')
    bad = {o.dxftype() for o in d.objects} & {'MATERIAL', 'MLEADERSTYLE', 'VISUALSTYLE', 'TABLESTYLE', 'SCALE'}
    return sorted(bad)


def sources():
    """Every published record with its native face fragment and bounds."""
    import speed_faces
    rows = []
    manifest = json.loads(Path('data/reference/cad-block-downloads/manifest.json').read_text())
    folder = Path('public/data/cad-sign-entities')
    index = json.loads((folder / 'index.json').read_text())
    index = index.get('records', index)
    with zipfile.ZipFile(speed_faces.PACK) as speeds:
        meta = json.loads(speeds.read('metadata.json'))
        speed_geometry = {n: (gzip.decompress(speeds.read(f'{n}.dxf.gz')).decode(), meta[str(n)]['bounds']) for n in range(15, 60, 5)}
    for rec in manifest['records']:
        n = speed_faces.value(rec)
        if n:
            text, bounds = speed_geometry[n]
        else:
            entry = index[rec['id']]
            text, bounds = gzip.decompress((folder / (rec['id'] + '.dxf.gz')).read_bytes()).decode(), entry['bounds']
        rows.append((rec, text, bounds))
    for pack in (Path('data/reference/plan-face-blocks.zip'), Path('data/reference/additional-sign-blocks.zip')):
        with zipfile.ZipFile(pack) as archive:
            geometry = json.loads(archive.read('geometry.json'))
            for rec in json.loads(archive.read('records.json')):
                n = speed_faces.value(rec)
                if n:
                    text, bounds = speed_geometry[n]
                else:
                    text = gzip.decompress(archive.read('geometry/' + rec['id'] + '.dxf.gz')).decode()
                    bounds = geometry[rec['id']]['bounds']
                rows.append((rec, text, bounds))
    return rows


def build(libredwg: Path, libdxfrw: Path | None = None, dest=PACK):
    import ezdxf  # noqa: F401
    rows = sources()
    records, warnings = {}, set()
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(dest.with_suffix('.tmp'), 'w', zipfile.ZIP_DEFLATED) as out:
        tmp = Path(tmp)
        for rec, text, bounds in rows:
            data, record, found = encode(rec, text, bounds, tmp, libredwg, libdxfrw)
            warnings.update(found)
            info = zipfile.ZipInfo('dwg/' + rec['id'] + '.dwg', (1980, 1, 1, 0, 0, 0))
            out.writestr(info, data, zipfile.ZIP_DEFLATED, compresslevel=9)
            records[rec['id']] = record
        spec = spec_of(libdxfrw, warnings)
        out.writestr(zipfile.ZipInfo('records.json', (1980, 1, 1, 0, 0, 0)), json.dumps({'spec': spec, 'records': records}, indent=1))
    dest.with_suffix('.tmp').replace(dest)
    return spec, len(records)


def refresh(ids, libredwg: Path, libdxfrw: Path | None = None, dest=PACK):
    """Re-encode only the given records; every other member is copied unchanged."""
    rows = {rec['id']: (rec, text, bounds) for rec, text, bounds in sources()}
    with zipfile.ZipFile(dest) as old:
        index = json.loads(old.read('records.json'))
        members = {n: old.read(n) for n in old.namelist() if n != 'records.json'}
    with tempfile.TemporaryDirectory() as tmp:
        for key in ids:
            data, record, _ = encode(*rows[key], Path(tmp), libredwg, libdxfrw)
            members['dwg/' + key + '.dwg'] = data
            index['records'][key] = record
    with zipfile.ZipFile(dest.with_suffix('.tmp'), 'w', zipfile.ZIP_DEFLATED) as out:
        for n, data in members.items():
            out.writestr(zipfile.ZipInfo(n, (1980, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED, compresslevel=9)
        out.writestr(zipfile.ZipInfo('records.json', (1980, 1, 1, 0, 0, 0)), json.dumps(index, indent=1))
    dest.with_suffix('.tmp').replace(dest)


def encode(rec, text, bounds, tmp, libredwg, libdxfrw):
    """One sign cell: DXF, DWG (R2000), both readers checked."""
    warnings = set()
    name = rec['blockName']
    code = rec['code']
    doc = cell_document(name, code, text, bounds)
    entities = len(doc.blocks[name])
    dxf, dwg, rt = tmp / 'cell.dxf', tmp / 'cell.dwg', tmp / 'rt.dxf'
    doc.saveas(dxf)
    for f in (dwg, rt):
        f.unlink(missing_ok=True)
    log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', dwg, dxf], check=True, capture_output=True, timeout=120, text=True)
    if re.search(r'warning|error', log.stdout + log.stderr, re.I):
        raise ValueError(f'{name}: encoder reported ' + (log.stdout + log.stderr).strip()[-300:])
    subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', rt, dwg], check=True, capture_output=True, timeout=120)
    data = dwg.read_bytes()
    if data[:6] != b'AC1015':
        raise ValueError(f'{name}: not an AutoCAD 2000 drawing')
    check(dxf, name, code, entities)
    warnings.update(check(rt, name, code, entities))
    if libdxfrw:
        rw = tmp / 'rw.dxf'
        rw.unlink(missing_ok=True)
        subprocess.run([libdxfrw, dwg, '-o', rw, '-v2000', '-y'], check=True, capture_output=True, timeout=120)
        check(rw, name, code, entities, ascii_only=True)
    record = {'code': code, 'blockName': name, 'bytes': len(data), 'sha256': sha(data),
              'entities': entities, 'codeHeight': code_height(code)}
    return data, record, warnings


def spec_of(libdxfrw, warnings):
    """The cell specification recorded with the archive."""
    spec = {'units': 'inches on the plotted sheet', 'cell': [CELL_W, CELL_H], 'insertionPoint': 'lower-left cell corner',
            'faceFit': [FACE_W, FACE_H], 'faceCenter': [ART_X, ART_Y], 'code': {'entity': 'MTEXT', 'style': 'ROMANS (romans.shx)',
            'attachment': 'bottom center', 'baseline': CODE_Y, 'height': CODE_H, 'maxWidth': CODE_MAX_W},
            'layers': LAYERS, 'styles': STYLES, 'source': 'data/reference/ladot-legend-layout.json',
            'encoder': 'LibreDWG dxf2dwg R2000', 'readers': ['LibreDWG dwg2dxf'] + (['LibreCAD libdxfrw'] if libdxfrw else []),
            'encoderAddedObjects': sorted(warnings)}
    return spec


_cache = None


def cells():
    """Pack records and bytes keyed by sign record id, read once per build."""
    global _cache
    if _cache is None:
        _cache = ({}, None)
        if PACK.is_file():
            with zipfile.ZipFile(PACK) as archive:
                meta = json.loads(archive.read('records.json'))
                files = {i: archive.read('dwg/' + i + '.dwg') for i in meta['records']}
            for i, row in meta['records'].items():
                if sha(files[i]) != row['sha256']:
                    raise ValueError('Sign cell pack changed for ' + i)
            _cache = ({i: (files[i], row) for i, row in meta['records'].items()}, meta['spec'])
    return _cache


def apply(rec, data):
    """Return the cell drawing for a record and record its size and checksum."""
    table, spec = cells()
    hit = table.get(rec['id'])
    if not hit:
        return data
    dwg, row = hit
    if row['code'] != rec['code'] or row['blockName'] != rec['blockName']:
        raise ValueError('Sign cell pack does not match ' + rec['id'])
    rec.update(bytes=len(dwg), sha256=sha(dwg), format='table cell', cell=spec['cell'],
               insertionPoint=spec['insertionPoint'], codeText='MTEXT ROMANS')
    return dwg


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--libredwg', type=Path, required=True, help='folder with dxf2dwg and dwg2dxf')
    b.add_argument('--libdxfrw', type=Path, help='LibreCAD dwg2dxf, the independent reader')
    args = parser.parse_args()
    print(build(args.libredwg, args.libdxfrw))
