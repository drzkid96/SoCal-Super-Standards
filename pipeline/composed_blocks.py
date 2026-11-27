"""Marking blocks composed from measured plan geometry or from published Caltrans word blocks.

Green bike crossing dashes (PM-BIKE-XING-GREEN-<width>): the Westwood signing and striping plan
draws its intersection bike crossings as 2 ft green dashes, one per lane width, with the bike lane
line segment on each edge, repeated every 8 ft along the path. One dash per lane width is published;
array it along the crossing path at 8 ft (ARRAYPATH).

Two-line word legends (PM-KEEP-CLEAR, PM-BUS-ONLY, PM-WAIT-HERE): the published Caltrans word blocks,
the first word nearest the approaching driver, 4 x the letter height between lines (CA MUTCD 3B.20,
the low-speed minimum).

All blocks: true size in feet, travel along +Y, base point at the bottom center, green field ACI 3
SOLID hatch, white geometry on layer 0 ByBlock.

  python3 pipeline/composed_blocks.py --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox

import plan_blocks
from sign_cells import r2000_document

ROUTE = 'markings/cad'
OUT = Path('public/downloads') / ROUTE
XING_WIDTHS = (5, 6, 6.5, 7, 8)       # lane widths drawn in the Westwood plan
DASH, REPEAT = 2.0, 8.0
LEGENDS = [('PM-KEEP-CLEAR', ('CT-A24E-KEEP', 'CT-A24E-CLEAR'), 'KEEP CLEAR'),
           ('PM-BUS-ONLY', ('CT-A24E-BUS', 'CT-A24E-ONLY'), 'BUS ONLY'),
           ('PM-WAIT-HERE', ('CT-A24D-WAIT', 'CT-A24D-HERE'), 'WAIT HERE')]


def width_tag(w):
    return f'{w:g}'.replace('.', 'P') + 'FT'


def crossing(doc, name, w):
    blk = doc.blocks.new(name, base_point=(0, 0))
    pts = [(-w / 2, 0), (w / 2, 0), (w / 2, DASH), (-w / 2, DASH)]
    hatch = blk.add_hatch(color=3, dxfattribs={'layer': '0'})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    blk.add_lwpolyline(pts, close=True, dxfattribs={'layer': '0', 'color': 3})
    for x in (-w / 2, w / 2):   # bike lane line segment on each edge
        blk.add_line((x, 0), (x, DASH), dxfattribs={'layer': '0', 'color': 0})


def readback(path, libredwg, tmp):
    out = Path(tmp) / (path.stem + '.dxf')
    subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(out), str(path)], check=True, capture_output=True)
    return ezdxf.readfile(out)


def legend(doc, name, words, libredwg, tmp):
    blk = doc.blocks.new(name, base_point=(0, 0))
    y = 0.0
    for code in words:
        src = readback(OUT / (code + '.dwg'), libredwg, tmp)
        insert = src.modelspace().query('INSERT').first
        part = src.blocks[insert.dxf.name]
        ext = bbox.extents(part)
        dx, dy = -(ext.extmin.x + ext.extmax.x) / 2, y - ext.extmin.y
        height = ext.size.y
        for e in part:
            copy = e.copy()
            copy.translate(dx, dy, 0)
            blk.add_foreign_entity(copy, copy=False)
        y += height * 5          # letter height plus 4 x letter height of space
    return height


def build(libredwg):
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for w in XING_WIDTHS:
            code = f'PM-BIKE-XING-GREEN-{width_tag(w)}'
            doc = r2000_document()
            crossing(doc, code, w)
            plan_blocks.write_static(doc, [code], OUT / (code + '.dwg'), libredwg, tmp)
            rows.append({'code': code, 'name': f'Green bike crossing dash, {w:g} ft bike lane; 2 ft dash, repeat every 8 ft · LA plan library (Westwood)',
                         'file': code + '.dwg', 'group': 'Bicycle markings', 'size': [w, DASH]})
        for code, words, text in LEGENDS:
            doc = r2000_document()
            h = legend(doc, code, words, libredwg, tmp)
            plan_blocks.write_static(doc, [code], OUT / (code + '.dwg'), libredwg, tmp)
            ext = bbox.extents(doc.blocks[code])
            rows.append({'code': code, 'name': f'{text}, two-line legend from Caltrans {words[0][3:7]} words, {4 * h:g} ft between lines',
                         'file': code + '.dwg', 'group': 'Words', 'size': [round(ext.size.x, 2), round(ext.size.y, 2)]})
    catalog = json.loads(plan_blocks.CATALOG.read_text())
    section = catalog[ROUTE]
    codes = {r['code'] for r in rows}
    section['blocks'] = [b for b in section['blocks'] if b['code'] not in codes] + rows
    plan_blocks.CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--libredwg', type=Path, required=True)
    print(len(build(ap.parse_args().libredwg)), 'composed blocks')
