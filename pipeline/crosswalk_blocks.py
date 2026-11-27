"""Caltrans 2026 Standard Plan A24F crosswalks, from the official DGN.

The sheet's second model ("Untitled Design") holds the crosswalk figures in US survey feet at the
example dimensions Caltrans drew; bar width (1 to 2 ft) and spacing (1 to 5 ft) vary by Notes 1 and
2, so the blocks show the plan's example. cadkit reads the DGN; each bar and longitudinal line is a
closed face of the drawn lines (break-line ends closed straight), and written like the other marking blocks (SOLID hatch plus
outline on layer 0 ByBlock, one INSERT on P-PMARK, base point at the bottom center).

  cadkit dump --json 2026_a24f.dgn > a24f.json
  python3 pipeline/crosswalk_blocks.py --json a24f.json --libredwg <dir>
"""
import argparse
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

from marking_blocks import CATALOG, rings_of, write_block

SOURCE = 'https://dot.ca.gov/programs/design/2026-ccs-standard-plans-and-standard-specifications/individual-standard-plans-in-dgn-format-2026-standards'
LAYER = 'tcd_PVMT-MARKING'
# figures in reading order of the sheet, by the lower-left corner of their box in the DGN (ft)
FIGURES = [
    ('CT-A24F-CONTINENTAL', 'Continental crosswalk, 1 ft bars at 1 ft spacing, 6 ft', (-811.7, 492.2), (21.0, 6.0), None),
    ('CT-A24F-TRIPLE-FOUR', 'Triple four crosswalk, 2 x 4 ft blocks', (-812.5, 470.1), (22.0, 12.0), None),
    ('CT-A24F-LADDER', 'Ladder crosswalk, 1 ft lines and bars, 6 ft between lines', (-812.3, 454.5), (23.17, 8.0), 1.0),
    ('CT-A24F-DIAGONAL', 'Diagonal crosswalk, 45 degree bars, 6 ft between lines', (-812.3, 438.5), (23.17, 8.0), 1.0),
    ('CT-A24F-BASIC', 'Basic crosswalk, two 1 ft lines 6 ft apart', (-764.8, 454.5), (23.17, 8.0), None),
]
TOL = 0.06


def segments(entities):
    out = []
    for e in entities:
        k = e['kind']
        if k['type'] == 'group':
            if k.get('name') == 'BRKLN':   # break-line symbols mark a cut, not paint
                continue
            out += segments(k.get('children', []))
        elif k['type'] == 'line' and e['layer'] == LAYER:
            out.append([(k['start']['x'], k['start']['y']), (k['end']['x'], k['end']['y'])])
    return out


def faces(segs, frame):
    """Closed faces of the drawn lines inside a figure's box, its ends closed where break-line
    symbols cut the longitudinal lines."""
    lines = [LineString(sg) for sg in segs if LineString(sg).within(frame.buffer(0.01))]
    xs = [c[0] for line in lines for c in line.coords]
    x0, x1 = min(xs), max(xs)
    y0, y1 = frame.bounds[1], frame.bounds[3]
    lines += [LineString([(x0, y0), (x0, y1)]), LineString([(x1, y0), (x1, y1)])]
    lines += bridges([list(line.coords) for line in lines], x0, x1)
    return [f for f in polygonize(unary_union(lines)) if f.area < 0.5 * frame.area]


def bridges(segs, x0, x1, reach=0.8):
    """Close the gaps the sheet leaves for labels (the 45 degree note cuts a diagonal bar) and the
    ends that stop short of a figure's edge: join collinear segments whose ends are within `reach`,
    and run an end within 0.1 ft of the figure's edge out to it."""
    out = []
    unit = []
    for (ax, ay), (bx, by) in segs:
        n = math.hypot(bx - ax, by - ay) or 1
        unit.append(((bx - ax) / n, (by - ay) / n))
    for i, (p, q) in enumerate(segs):
        for end, other in ((p, q), (q, p)):
            if 0 < abs(end[0] - x0) <= 0.1 or 0 < abs(end[0] - x1) <= 0.1:
                edge = x0 if abs(end[0] - x0) <= 0.1 else x1
                ux, uy = unit[i]
                if abs(ux) > 1e-6:
                    t = (edge - end[0]) / ux
                    out.append(LineString([end, (edge, end[1] + t * uy)]))
        for j in range(i + 1, len(segs)):
            if abs(unit[i][0] * unit[j][1] - unit[i][1] * unit[j][0]) > 0.02:
                continue
            for a in (p, q):
                for b in segs[j]:
                    gap = math.dist(a, b)
                    if 0.01 < gap <= reach:
                        dx, dy = (b[0] - a[0]) / gap, (b[1] - a[1]) / gap
                        if abs(dx * unit[i][1] - dy * unit[i][0]) < 0.02:
                            out.append(LineString([a, b]))
    return out


def build(dump, libredwg):
    model = json.loads(Path(dump).read_text())['models'][1]
    segs = segments(model['entities'])
    rows = []
    for code, name, (x0, y0), (w, h), band in FIGURES:
        frame = box(x0 - 0.2, y0 - 0.2, x0 + w + 0.2, y0 + h + 0.2)
        inside = faces(segs, frame)
        if band:
            # Longitudinal lines are drawn by their outer edge only; the inner edge is where the bars
            # end. Each band runs the full length from the outer edge to the bar ends.
            bx0, by0, bx1, by1 = unary_union(inside).bounds
            edges = [ls.coords[0][1] for ls in map(LineString, segs) if ls.within(frame.buffer(0.01))
                     and abs(ls.coords[0][1] - ls.coords[1][1]) < 1e-6 and ls.length > 15]
            top, bottom = max(edges), min(edges)
            if abs((top - by1) - band) > TOL or abs((by0 - bottom) - band) > TOL:
                raise ValueError(f'{code}: bands {top - by1:.2f} and {by0 - bottom:.2f} ft, expected {band}')
            xs = [c[0] for ls in map(LineString, segs) if ls.within(frame.buffer(0.01)) for c in ls.coords]
            inside += [box(min(xs), by1, max(xs), top), box(min(xs), bottom, max(xs), by0)]
        region = unary_union(inside)
        bx = region.bounds
        size = (bx[2] - bx[0], bx[3] - bx[1])
        if abs(size[0] - w) > TOL or abs(size[1] - h) > TOL:
            raise ValueError(f'{code}: traced {size[0]:.2f} x {size[1]:.2f}, expected {w} x {h}')
        write_block(code, rings_of(region), libredwg)
        rows.append({'code': code, 'name': f'{name} · Caltrans Std. Plan A24F (2026)', 'file': code + '.dwg',
                     'group': 'Crosswalks', 'size': [round(size[0], 2), round(size[1], 2)],
                     'area': round(region.area, 1), 'source': SOURCE, 'sheet': 'A24F'})
        print(code, f'{size[0]:.2f} x {size[1]:.2f} ft', f'{len(inside)} pieces', f'{region.area:.1f} ft2')
    catalog = json.loads(CATALOG.read_text())
    section = catalog['markings/cad']
    section['blocks'] = [r for r in section['blocks'] if not r['code'].startswith('CT-A24F-')] + rows
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    build(args.json, args.libredwg)
