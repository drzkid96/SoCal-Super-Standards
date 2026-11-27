"""Pavement marking DWG blocks traced from the Caltrans 2026 Standard Plans (vector PDF).

Each figure is matched by the width, height and area (A = ft2) printed with it on the sheet,
and is published only when all three agree. Blocks are true size in feet, drawn as a SOLID
hatch plus its outline on layer 0 (BYBLOCK), with the base point at the bottom center
(the middle of an arrow's tail, or the middle of a word's or symbol's bottom edge). (L) figures also get a mirrored (R).

Build locally:
  python3 pipeline/marking_blocks.py --pdf 2026-standard-plans.pdf --libredwg <dir with dxf2dwg and dwg2dxf>
The run also writes data/reference/marking-blocks-report.json: every figure, matched or not.
"""
import argparse
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from shapely.geometry import LinearRing, Point, Polygon

from cad_blocks.plan_outlines import figures
from sign_cells import r2000_document

CATALOG = Path('data/reference/design-blocks.json')
REPORT = Path('data/reference/marking-blocks-report.json')
OUT = Path('public/downloads/markings/cad')
SOURCE = 'https://dot.ca.gov/-/media/dot-media/programs/design/documents/2026-standard-plans_locked-final-a11y.pdf'


def FT_IN(f, i=0):
    return f + i / 12


# sheet: (page index, outline stroke width, [(code, name, group, width ft, height ft, area ft2, mirror)])
# Entries follow the sheet's reading order, which breaks ties between figures of equal size and area.
SHEETS = {
    'A24A': (44, 0.48, [
        ('TYPE-I-10FT', 'Type I arrow, 10 ft', 'Arrows', 3.5, 10, 14, False),
        ('TYPE-I-24FT', 'Type I arrow, 24 ft', 'Arrows', 3.5, 24, 31, False),
        ('TYPE-IV-L', 'Type IV (L) arrow', 'Arrows', 6, 8, 15, True),
        ('TYPE-VI', 'Type VI arrow, right lane drop', 'Arrows', 5.5, 19, 42, True),
        ('TYPE-VIII', 'Type VIII arrow', 'Arrows', 9, 15, 36, False),
        ('TYPE-I-18FT', 'Type I arrow, 18 ft', 'Arrows', 3.5, 18, 25, False),
        ('BIKE-LANE-ARROW', 'Bike lane arrow', 'Bicycle markings', 1.75, 5, 3.5, False),
        ('TYPE-V', 'Type V arrow', 'Arrows', None, 24, 33, False),
        ('TYPE-VII-L', 'Type VII (L) arrow', 'Arrows', 7.25, 13, 27, True),
    ]),
    'A24B': (45, 0.48, [
        ('RXR', 'Railroad crossing symbol', 'Words and symbols', 8, None, 70, False),
        ('TYPE-II-B', 'Type II (B) arrow', 'Arrows', 10, 24, 59, False),
        ('TYPE-II-L', 'Type II (L) arrow', 'Arrows', 7, 24, 45, True),
        ('TYPE-III-B', 'Type III (B) arrow', 'Arrows', 11, 24, 73, False),
        ('TYPE-III-L', 'Type III (L) arrow', 'Arrows', 6, 24, 42, True),
    ]),
    'A24C': (46, 0.72, [
        ('BIKE-SYMBOL', 'Bike lane symbol without person', 'Bicycle markings', FT_IN(3, 4), 6, 7, False),
        ('BIKE-SYMBOL-PERSON', 'Bike lane symbol with person', 'Bicycle markings', FT_IN(3, 4), 6.5, 7, False),
        ('DIAMOND', 'Diamond symbol', 'Words and symbols', FT_IN(3, 3), 12, 11, False),
        ('SHARROW', 'Shared roadway bicycle marking', 'Bicycle markings', FT_IN(3, 3), 9.25, 11.5, False),
    ]),
    'A24D': (47, 0.72, [
        ('RUNAWAY', 'RUNAWAY', 'Words', FT_IN(11, 4), 8, 43, False), ('VEHICLES', 'VEHICLES', 'Words', 12, 8, 42, False),
        ('YIELD', 'YIELD', 'Words', 7, 8, 24, False), ('SCHOOL', 'SCHOOL', 'Words', FT_IN(9, 8), 8, 35, False),
        ('WAIT', 'WAIT', 'Words', FT_IN(5, 4), 8, 19, False), ('SLOW', 'SLOW', 'Words', FT_IN(6, 4), 8, 23, False),
        ('AHEAD', 'AHEAD', 'Words', 8, 8, 31, False), ('TURN', 'TURN', 'Words', FT_IN(6, 4), 8, 24, False),
        ('HERE', 'HERE', 'Words', FT_IN(6, 4), 8, 26, False), ('XING', 'XING', 'Words', FT_IN(5, 4), 8, 21, False),
        ('SIGNAL', 'SIGNAL', 'Words', FT_IN(8, 8), 8, 32, False), ('LEFT', 'LEFT', 'Words', FT_IN(6, 4), 8, 19, False),
        ('RIGHT', 'RIGHT', 'Words', 7, 8, 26, False), ('STOP', 'STOP', 'Words', FT_IN(6, 4), 8, 22, False),
        ('PED', 'PED', 'Words', FT_IN(4, 8), 8, 18, False), ('COMPACT', 'COMPACT, 4 ft letters', 'Words', FT_IN(5, 8), 4, 10, False),
        ('BIKE-4FT', 'BIKE, 4 ft letters', 'Words', FT_IN(2, 8), 4, 5, False), ('LANE-4FT', 'LANE, 4 ft letters', 'Words', FT_IN(3, 2), 4, 6, False),
    ]),
    'A24E': (48, 0.48, [
        ('LANE', 'LANE', 'Words', FT_IN(6, 4), 8, 24, False), ('CLEAR', 'CLEAR', 'Words', 8, 8, 27, False),
        ('BIKE', 'BIKE', 'Words', FT_IN(5, 4), 8, 21, False), ('ONLY', 'ONLY', 'Words', 6, 8, 22, False),
        ('NO', 'NO', 'Words', 3, 8, 14, False), ('KEEP', 'KEEP', 'Words', FT_IN(6, 4), 8, 24, False),
        ('BUS', 'BUS', 'Words', FT_IN(4, 8), 8, 20, False), ('FWY', 'FWY', 'Words', FT_IN(4, 8), 8, 16, False),
        ('EXPRS', 'EXPRS', 'Words', 8, 8, 30, False), ('TRAIL', 'TRAIL', 'Words', 7, 8, 23, False),
        ('HOV', 'HOV', 'Words', FT_IN(4, 8), 8, 18, False), ('NORTH', 'NORTH', 'Words', 8, 8, 31, False),
        ('SOUTH', 'SOUTH', 'Words', 8, 8, 29, False), ('EAST', 'EAST', 'Words', FT_IN(6, 4), 8, 22, False),
        ('WEST', 'WEST', 'Words', FT_IN(6, 4), 8, 24, False),
    ]),
}
SIZE_TOL = 0.06   # ft
AREA_TOL = 0.10   # share of the printed area (Caltrans rounds it and measures to the outline centerline)


def shape_of(fig):
    """Even-odd union of the closed loops, in feet; open strokes (dashed separators) are left out."""
    loops = [pts for pts, closed, _ in fig['loops'] if closed and len(pts) > 3]
    region = None
    for p in sorted((Polygon(pts).buffer(0) for pts in loops), key=lambda p: -p.area):
        if p.area > 1e-4:
            region = p if region is None else region.symmetric_difference(p)
    return region, loops


def matches(fig, width, height, area):
    w, h = fig['size']
    if width is not None and abs(w - width) > SIZE_TOL:
        return False
    if height is not None and abs(h - height) > SIZE_TOL:
        return False
    if area is not None:
        region, _ = shape_of(fig)
        if region is None or abs(region.area - area) > max(AREA_TOL * area, 0.6):
            return False
    return True


def base_point(loops, tail):
    """Bottom center. Arrows use the middle of the lowest edge (the tail), which sits off the box
    center on turn arrows; words and symbols use the middle of the box's bottom edge."""
    pts = [p for loop in loops for p in loop]
    y0 = min(p[1] for p in pts)
    xs = [p[0] for p in pts if p[1] - y0 < 0.02] if tail else [p[0] for p in pts]
    return ((min(xs) + max(xs)) / 2, y0)


def write_block(code, loops, libredwg, mirror=False, tail=False):
    bx, by = base_point(loops, tail)
    sign = -1 if mirror else 1
    rings = [[(sign * (x - bx), y - by) for x, y in loop] for loop in loops]
    # Wind outer boundaries counterclockwise and holes clockwise (by nesting depth), so every
    # program fills counters and wheel rings correctly, whatever its fill rule.
    polys = [Polygon(r) for r in rings]
    oriented = []
    for i, ring in enumerate(rings):
        depth = sum(1 for j, q in enumerate(polys) if j != i and q.is_valid and q.contains(Point(ring[0])))
        ccw = LinearRing(ring).is_ccw
        oriented.append(ring if ccw == (depth % 2 == 0) else ring[::-1])
    rings = oriented
    doc = r2000_document()
    doc.units = 2
    doc.layers.new('P-PMARK', dxfattribs={'color': 7})
    block = doc.blocks.new(code, base_point=(0, 0))
    block.block_record.dxf.units = 2
    hatch = block.add_hatch(color=0, dxfattribs={'layer': '0'})
    hatch.dxf.hatch_style = 0  # normal: nested loops alternate, so letter counters stay open
    for ring in rings:
        clean = [p for i, p in enumerate(ring) if i == 0 or math.dist(p, ring[i - 1]) > 1e-4]
        hatch.paths.add_polyline_path(clean, is_closed=True)
        block.add_lwpolyline(clean, close=True, dxfattribs={'layer': '0', 'color': 0})
    doc.modelspace().add_blockref(code, (0, 0), dxfattribs={'layer': 'P-PMARK'})
    ys = [p[1] for r in rings for p in r]
    doc.set_modelspace_vport(height=max(ys) * 1.25, center=(0, max(ys) / 2))
    target = OUT / (code + '.dwg')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'm.dxf'
        doc.saveas(path)
        log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', target, path], capture_output=True, text=True, check=True)
        if re.search(r'warning|error', log.stdout + log.stderr, re.I):
            raise ValueError(code + ': ' + (log.stdout + log.stderr)[-300:])
        back = Path(tmp) / 'rt.dxf'
        subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', back, target], capture_output=True, check=True)
        read = ezdxf.readfile(back)
        if [e.dxftype() for e in read.modelspace()] != ['INSERT'] or len(read.blocks[code]) != len(block):
            raise ValueError(code + ': DWG read-back differs')
    return rings


def build(pdf, libredwg):
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    keep = [r for r in catalog['markings/cad']['blocks'] if not r['code'].startswith('CT-')]
    rows, report, shapes = [], {}, {}
    for sheet, (page, width, entries) in SHEETS.items():
        figs = figures(pdf, page, width)
        used = set()
        report[sheet] = {'figures': [], 'entries': {}}
        for f in figs:
            region, _ = shape_of(f)
            report[sheet]['figures'].append({'size': f['size'], 'grid_ft': round(f['grid_ft'], 4), 'area': round(region.area, 2) if region else None})
        for code, name, group, w, h, a, mirror in entries:
            hit = next((i for i, f in enumerate(figs) if i not in used and matches(f, w, h, a)), None)
            report[sheet]['entries'][code] = hit
            if hit is None:
                continue
            used.add(hit)
            fig = figs[hit]
            region, loops = shape_of(fig)
            variants = [(f'CT-{sheet}-{code}', name, False)]
            if mirror:
                variants.append((f'CT-{sheet}-{code[:-2]}-R' if code.endswith('-L') else f'CT-{sheet}-{code}-MIRROR',
                                 name.replace('(L)', '(R)') if '(L)' in name else name + ', mirrored for the left lane', True))
            for full, label, flip in variants:
                shapes[full] = write_block(full, loops, libredwg, mirror=flip, tail='ARROW' in full or 'TYPE-' in full)
                rows.append({'code': full, 'name': f'{label} · Caltrans Std. Plan {sheet} (2026)', 'file': full + '.dwg',
                             'group': group, 'size': [round(fig['size'][0], 2), round(fig['size'][1], 2)],
                             'area': round(region.area, 1), 'source': SOURCE, 'sheet': sheet})
    groups = ['Arrows', 'Words', 'Words and symbols', 'Bicycle markings']
    catalog['markings/cad']['groups'] = groups + [g for g in catalog['markings/cad']['groups'] if g not in groups]
    catalog['markings/cad']['blocks'] = rows + keep
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    REPORT.write_text(json.dumps(report, indent=1) + '\n')
    return rows, report, shapes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    rows, report, _ = build(args.pdf, args.libredwg)
    for sheet, r in report.items():
        print(sheet, 'matched', sum(v is not None for v in r['entries'].values()), 'of', len(r['entries']),
              'missing', [k for k, v in r['entries'].items() if v is None])
