"""Open every published drawing zoomed to its content, without touching anything else.

For drawings the normalizer leaves alone (dynamic blocks from the Westwood and Caltrans sources),
this pass reads the DWG with ODA File Converter, sets only the active model space view and the header
extents (cad_standard.zoom), and writes it back as AutoCAD 2018. The result must read back with the
same entities in every block and the same dynamic block data, or the original is kept.

  python3 pipeline/cad_view.py [--check] FILE.dwg ...     # --check lists drawings that open zoomed out
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox

import cad_standard as std


def oda(src, out, fmt):
    cmd = ['ODAFileConverter', str(src), str(out), 'ACAD2018', fmt, '0', '1', '*.dwg' if fmt == 'DXF' else '*.dxf']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=3600)


def zoomed(doc):
    vp = doc.viewports.get('*Active')
    ext = bbox.extents(doc.modelspace())
    if not vp or not ext.has_data:
        return False
    v = vp[0].dxf
    inside = ext.extmin.x - 1 <= v.center.x <= ext.extmax.x + 1 and ext.extmin.y - 1 <= v.center.y <= ext.extmax.y + 1
    return inside and v.height <= 4 * max(ext.size.y, ext.size.x / 1.6) + 0.5


def content(doc):
    """What must not change: entities per block and the dynamic block data objects."""
    c = Counter()
    for b in doc.blocks:
        if b.name.upper().startswith(('*MODEL', '*PAPER')):
            continue
        for e in b:
            c[(b.name, e.dxftype())] += 1
    for e in doc.modelspace():
        c[('*MODEL', e.dxftype())] += 1
    for o in doc.objects:
        if o.dxftype() == 'DICTIONARY':
            owner = doc.entitydb.get(o.dxf.owner)
            if not len(o) or (owner is not None and owner.dxftype() == 'VPORT'):
                continue    # empty dictionaries, and the old view's own dictionary, go with the new view
        c[('OBJECT', o.dxftype())] += 1
    return c


def run(files, check=False):
    files = [Path(f) for f in files]
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        src, dxf, dwg, back = (t / n for n in ('src', 'dxf', 'dwg', 'back'))
        for d in (src, dxf, dwg, back):
            d.mkdir()
        keys = {}
        for i, f in enumerate(files):
            keys[f'f{i:05d}'] = f
            shutil.copy(f, src / f'f{i:05d}.dwg')
        oda(src, dxf, 'DXF')
        todo, before = [], {}
        for k, f in keys.items():
            doc = ezdxf.readfile(dxf / f'{k}.dxf')
            if zoomed(doc):
                continue
            if check:
                print('zoomed out:', f)
                continue
            before[k] = content(doc)
            std.zoom(doc)
            doc.saveas(dxf / f'{k}.dxf')
            todo.append(k)
        if check or not todo:
            return 0
        for p in dxf.iterdir():
            if p.stem not in todo:
                p.unlink()
        oda(dxf, dwg, 'DWG')
        for k in todo:
            shutil.copy(dwg / f'{k}.dwg', back / f'{k}.dwg')
        out = t / 'backdxf'
        out.mkdir()
        oda(back, out, 'DXF')
        done = 0
        for k in todo:
            doc = ezdxf.readfile(out / f'{k}.dxf')
            if content(doc) != before[k] or not zoomed(doc):
                print('kept original (read-back differs):', keys[k], file=sys.stderr)
                continue
            keys[k].write_bytes((dwg / f'{k}.dwg').read_bytes())
            done += 1
        return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    print(run(a.files, a.check), 'drawings now open zoomed to the block')
