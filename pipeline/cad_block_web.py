"""Browser copies of the marking and signal blocks for the block cart's combined library.

For every block in data/reference/design-blocks.json: the drawing is read with ODA (dynamic blocks in their
saved state), the block is flattened (nested blocks exploded) and its entities written as AutoCAD 2000 DXF
group codes without handles or owners, gzip-compressed, to public/data/cad-block-entities/<code>.dxf.gz.
index.json holds route, name, group, insert layer, units, bounds, file and whether the original is dynamic
(the cart's AutoCAD script inserts the original file to keep its grips).

  python3 pipeline/cad_block_web.py
"""
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/data/cad-block-entities')
KEEP = {'LINE', 'LWPOLYLINE', 'ARC', 'CIRCLE', 'HATCH', 'ELLIPSE', 'SPLINE', 'TEXT', 'MTEXT', 'POLYLINE', 'SOLID'}


def oda(src, out):
    cmd = ['ODAFileConverter', str(src), str(out), 'ACAD2018', 'DXF', '0', '1', '*.dwg']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=3600)


def flat(entities, depth=0):
    for e in entities:
        if e.dxftype() == 'INSERT' and depth < 8:
            yield from flat(e.virtual_entities(), depth + 1)
        elif e.dxftype() in KEEP:
            yield e


def fragment(src_doc):
    insert = src_doc.modelspace().query('INSERT').first
    ents = list(flat(src_doc.blocks[insert.dxf.name]))
    doc = ezdxf.new('R2000', setup=False)
    doc.styles.new('ROMANS', dxfattribs={'font': 'romans.shx'})
    blk = doc.blocks.new('X')
    for e in ents:
        copy = e.copy()
        layer = e.dxf.get('layer', '0')
        copy.dxf.layer = 'NOPLOT' if layer.upper() in ('NOPLOT', 'DEFPOINTS') else (layer if layer[:2] in ('E-', 'P-', 'R-', 'A-') else '0')
        if copy.dxf.hasattr('true_color'):
            copy.dxf.discard('true_color')
        if copy.dxf.is_supported('style'):
            copy.dxf.style = 'ROMANS'
        blk.add_foreign_entity(copy, copy=False)
    buf = io.StringIO()
    doc.write(buf)
    text = buf.getvalue().split('\n')
    pairs = list(zip(text[0::2], text[1::2]))
    out, inside, take = [], False, False
    for code, value in pairs:
        code, value = code.strip(), value.rstrip('\r')
        if code == '0' and value == 'BLOCK':
            inside = False
        if code == '2' and not inside and value == 'X':
            inside = True
            take = False
            continue
        if not inside:
            continue
        if code == '0' and value == 'ENDBLK':
            break
        if code == '0':
            take = value in KEEP
        if not take or code in ('5', '330', '102', '360') or value in ('{ACAD_REACTORS', '}'):
            continue
        out.append(f'{code}\n{value}\n')
    ext = bbox.extents(ents)
    return ''.join(out), [ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y], len(ents)


def build():
    catalog = json.loads(CATALOG.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    with tempfile.TemporaryDirectory() as tmp:
        src, dxf = Path(tmp) / 'in', Path(tmp) / 'out'
        src.mkdir(), dxf.mkdir()
        rows = []
        for route, section in catalog.items():
            for r in section['blocks']:
                shutil.copy(Path('public/downloads') / route / r['file'], src / r['file'])
                rows.append((route, r))
        oda(src, dxf)
        for route, r in rows:
            doc = ezdxf.readfile(dxf / (Path(r['file']).stem + '.dxf'))
            text, bounds, count = fragment(doc)
            data = gzip.compress(text.encode('cp1252', 'replace'), compresslevel=8, mtime=0)
            (OUT / (r['code'] + '.dxf.gz')).write_bytes(data)
            insert = doc.modelspace().query('INSERT').first
            index[r['code']] = dict(route=route, name=r['name'], group=r['group'], file=f'{route}/{r["file"]}',
                                    layer=insert.dxf.layer, units='in' if r['code'].startswith('CT-ES') else 'ft',
                                    bounds=[round(v, 6) for v in bounds], entities=count, dynamic=bool(r.get('dynamic')),
                                    placement=r.get('placement', ''), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                    preview=f'block-previews/{route}/{Path(r["file"]).stem}.svg')
    for old in OUT.glob('*.dxf.gz'):
        if old.name[:-7] not in index:
            old.unlink()
    (OUT / 'index.json').write_text(json.dumps(index, separators=(',', ':'), sort_keys=True))
    return len(index)


if __name__ == '__main__':
    print(build(), 'block fragments in', OUT)
