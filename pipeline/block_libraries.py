"""Library drawings: every static block of a family in one DWG, laid out by group in model space, with
one 24 x 36 in sheet layout (ARCH D, the Westwood TS-1 sheet size) per group.

Each sheet has a border, a title block line and one viewport on its group at the largest standard
scale that fits. Blocks keep the published definitions (layer 0 ByLayer, NOPLOT frames, base points).
Encoded as AutoCAD 2018 with ODA File Converter; read back by LibreDWG and libdxfrw.

  python3 pipeline/block_libraries.py --libredwg <dir> --libdxfrw <libdxfrw dwg2dxf>
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

from cad_normalize import new_document, oda, SKIP
import cad_standard as std

CATALOG = Path('data/reference/design-blocks.json')
SHEET = (36.0, 24.0)          # in, ARCH D landscape
MARGIN = 0.75                 # in
TITLE_H = 1.25                # in, title strip at the bottom
FEET_SCALES = [1, 2, 4, 5, 8, 10, 20, 40, 50, 100]          # 1 in = N ft
INCH_SCALES = [0.25, 0.5, 1, 2, 4, 8]                       # 1 in = N plotted in (signals are drawn in plotted inches)

LIBRARIES = [
    {'file': 'SSS-PMARK-LIBRARY.dwg', 'route': 'markings/cad', 'units': 'ft', 'layer': 'P-PMARK',
     'title': 'SSS PAVEMENT MARKING BLOCKS', 'pick': lambda r: not r.get('dynamic')},
    {'file': 'SSS-SIGNAL-LIBRARY.dwg', 'route': 'signals/cad', 'units': 'in', 'layer': 'P-SIGNAL',
     'title': 'SSS CALTRANS ELECTRICAL SYMBOLS (ES-1A TO ES-1C)', 'pick': lambda r: r['code'].startswith('CT-ES')},
]


def sheet(doc, name, region, units, title, group):
    (x0, y0, x1, y1) = region
    w, h = SHEET[0] - 2 * MARGIN, SHEET[1] - 2 * MARGIN - TITLE_H
    span = max((x1 - x0) / w, (y1 - y0) / h)            # drawing units per paper inch needed
    scales = FEET_SCALES if units == 'ft' else INCH_SCALES
    n = next((s for s in scales if s >= span), scales[-1] if span <= scales[-1] else span)
    lay = doc.layouts.new(name[:255])
    lay.page_setup(size=SHEET, margins=(0, 0, 0, 0), units='inch')
    for layer in ('G-SHEET', 'G-SHEET-TEXT'):
        if layer not in doc.layers:
            doc.layers.new(layer, dxfattribs={'color': 7})
    lay.add_lwpolyline([(MARGIN, MARGIN), (SHEET[0] - MARGIN, MARGIN), (SHEET[0] - MARGIN, SHEET[1] - MARGIN),
                        (MARGIN, SHEET[1] - MARGIN)], close=True, dxfattribs={'layer': 'G-SHEET'})
    lay.add_line((MARGIN, MARGIN + TITLE_H), (SHEET[0] - MARGIN, MARGIN + TITLE_H), dxfattribs={'layer': 'G-SHEET'})
    scale_text = f'1" = {n:g}\'' if units == 'ft' else f'{1 / n:g}:1 PLOTTED SIZE' if n <= 1 else f'1" = {n:g}" PLOTTED'
    lay.add_text(f'{title}  ·  {group.upper()}', height=0.3,
                 dxfattribs={'layer': 'G-SHEET-TEXT', 'style': 'ROMANS'}).set_placement(
        (MARGIN + 0.3, MARGIN + TITLE_H / 2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)
    lay.add_text(f'SCALE {scale_text}   ·   SOCAL SUPER STANDARDS', height=0.18,
                 dxfattribs={'layer': 'G-SHEET-TEXT', 'style': 'ROMANS'}).set_placement(
        (SHEET[0] - MARGIN - 0.3, MARGIN + TITLE_H / 2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_RIGHT)
    cx, cy = SHEET[0] / 2, MARGIN + TITLE_H + h / 2
    lay.add_viewport(center=(cx, cy), size=(w, h), view_center_point=((x0 + x1) / 2, (y0 + y1) / 2), view_height=h * n)
    return n


def build_library(spec, libredwg, libdxfrw, work):
    catalog = json.loads(CATALOG.read_text())
    section = catalog[spec['route']]
    rows = [r for r in section['blocks'] if spec['pick'](r) and r['file'] != spec['file']]
    doc = new_document()
    doc.units = 2 if spec['units'] == 'ft' else 1
    doc.header['$INSUNITS'] = doc.units
    for name, color in ((spec['layer'], 7), (spec['layer'] + '-TEXT', 7)):
        doc.layers.new(name, dxfattribs={'color': color})
    if std.NOPLOT not in doc.layers:
        doc.layers.new(std.NOPLOT, dxfattribs={'color': 8, 'plot': 0})
    msp = doc.modelspace()
    unit = 1.0 if spec['units'] == 'ft' else 0.1       # label and gap scale
    gap, text = 4 * unit, 1.0 * unit
    regions, expect = [], 0
    spacing = 5000 * unit           # each group in its own area, so a sheet viewport never shows another group
    for group in section['groups']:
        members = [r for r in rows if r['group'] == group]
        if not members:
            continue
        x0 = len(regions) * spacing
        y = top = 0.0
        msp.add_text(group.upper(), height=2 * text, dxfattribs={'layer': spec['layer'] + '-TEXT', 'style': 'ROMANS',
                                                                'insert': (x0, y - 2 * text)})
        y -= 3 * text + gap
        x, row_h, right = 0.0, 0.0, 0.0
        width = 120 * unit if spec['units'] == 'ft' else 7.5
        for r in members:
            src_dxf = work / (r['code'] + '.dxf')
            src_dxf.unlink(missing_ok=True)
            subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(src_dxf), str(Path('public/downloads') / spec['route'] / r['file'])],
                           capture_output=True, check=True)
            src = ezdxf.readfile(src_dxf)
            name = src.modelspace().query('INSERT').first.dxf.name
            imp = Importer(src, doc)
            imp.import_block(name)
            imp.finalize()
            expect += sum(1 for e in doc.blocks[name] if e.dxftype() not in SKIP)
            ext = bbox.extents([e for e in doc.blocks[name] if e.dxf.layer != std.NOPLOT] or list(doc.blocks[name]))
            w, h = ext.size.x, ext.size.y
            if x and x + w > width:
                x, y, row_h = 0.0, y - row_h - gap - 2 * text, 0.0
            at = (x0 + x - ext.extmin.x, y - ext.extmax.y)
            msp.add_blockref(name, at, dxfattribs={'layer': spec['layer']})
            label = r['code'].replace('CT-', '')
            msp.add_text(label, height=0.6 * text, dxfattribs={'layer': spec['layer'] + '-TEXT', 'style': 'ROMANS'}).set_placement(
                (x0 + x + w / 2, y - h - 0.5 * text), align=ezdxf.enums.TextEntityAlignment.TOP_CENTER)
            x += max(w, len(label) * 0.6 * text) + gap
            right = max(right, x)
            row_h = max(row_h, h + 1.5 * text)
        y -= row_h + gap
        regions.append((group, (x0 - gap / 2, y, x0 + right, top + gap / 2)))
    for i, (group, region) in enumerate(regions, 1):
        sheet(doc, f'{i:02d} {group}', region, spec['units'], spec['title'], group)
    for layout in list(doc.layouts):
        if layout.name == 'Layout1' and len(regions):
            doc.layouts.delete('Layout1')
    stage, out = work / 'lib-in', work / 'lib-out'
    stage.mkdir(exist_ok=True), out.mkdir(exist_ok=True)
    stem = Path(spec['file']).stem
    doc.saveas(stage / (stem + '.dxf'))
    oda(stage, out)
    dwg = out / (stem + '.dwg')
    names = {r['code'] for r in rows}
    for reader in ('libredwg', 'libdxfrw'):
        back = work / f'{stem}.{reader}.dxf'
        back.unlink(missing_ok=True)
        if reader == 'libredwg':
            subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(back), str(dwg)], capture_output=True, check=True)
        elif libdxfrw:
            subprocess.run([str(libdxfrw), str(dwg), '-o', str(back), '-y'], capture_output=True, check=True)
        else:
            continue
        read = ezdxf.readfile(back)
        found = {b.name for b in read.blocks if not b.is_any_layout}
        if names - found:
            raise ValueError(f'{stem}: {reader} read-back is missing {sorted(names - found)[:5]}')
        got = sum(1 for n in names for e in read.blocks[n] if e.dxftype() not in SKIP)
        if got != expect:
            raise ValueError(f'{stem}: {reader} read-back has {got} block entities, expected {expect}')
        if reader == 'libredwg' and len([l for l in read.layouts if l.name != 'Model']) != len(regions):
            raise ValueError(f'{stem}: sheet layouts missing after read-back')
    target = Path('public/downloads') / spec['route'] / spec['file']
    target.write_bytes(dwg.read_bytes())
    return len(rows), len(regions)


def build(libredwg, libdxfrw=None):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for spec in LIBRARIES:
            work = Path(tmp) / Path(spec['file']).stem
            work.mkdir()
            out.append((spec['file'], *build_library(spec, libredwg, libdxfrw, work)))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--libredwg', type=Path, required=True)
    ap.add_argument('--libdxfrw', type=Path)
    a = ap.parse_args()
    for f, n, s in build(a.libredwg, a.libdxfrw):
        print(f'{f}: {n} blocks, {s} sheets')
