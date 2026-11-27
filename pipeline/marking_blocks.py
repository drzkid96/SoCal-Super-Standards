"""Pavement marking DWG blocks traced from the Caltrans 2026 Standard Plans PDF.

Each block is drawn at true size in feet from the plan's own 1-ft grid, and is published
only when its measured length and width match the dimensions printed with it.
Base point: center of the arrow's tail, with the arrow pointing +Y.

Build locally:
  python3 pipeline/marking_blocks.py --pdf 2026-standard-plans.pdf --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf

from cad_blocks.plan_outlines import run as outlines
from sign_cells import r2000_document

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/downloads/markings/cad')
SOURCE = 'https://dot.ca.gov/-/media/dot-media/programs/design/documents/2026-standard-plans_locked-final-a11y.pdf'
# Sheet, outline stroke width, and the arrows printed there with their published length and width in feet.
SHEETS = {
    'A24A': {'page': 44, 'width': 0.48, 'shapes': [
        ('CT-A24A-TYPE-I-10FT', 'Type I arrow, 10 ft', 10.0, 3.5),
        ('CT-A24A-TYPE-I-18FT', 'Type I arrow, 18 ft', 18.0, 3.5),
        ('CT-A24A-TYPE-I-24FT', 'Type I arrow, 24 ft', 24.0, 3.5),
    ]},
}


def to_feet(loop, box, step):
    """Unrotated sheet points to feet, arrow pointing +Y, base point at the tail center."""
    x0, y0, x1, y1 = box
    return [((p[1] - (y0 + y1) / 2) / step, (p[0] - x0) / step) for p in loop]


def build(pdf, libredwg):
    catalog = json.loads(CATALOG.read_text())
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for sheet, spec in SHEETS.items():
        found = outlines(pdf, spec['page'], {spec['width']})
        for code, name, length, width in spec['shapes']:
            label = f"{int(length)}'-0\""
            match = [r for r in found if r['step'] and label in r['label'] and all(c for _, c in r['loops'])]
            if len(match) != 1:
                raise ValueError(f'{code}: expected one closed outline labeled {label}, found {len(match)}')
            r = match[0]
            x0, y0, x1, y1 = r['box']
            measured = ((x1 - x0) / r['step'], (y1 - y0) / r['step'])
            if abs(measured[0] - length) > 0.05 or abs(measured[1] - width) > 0.05:
                raise ValueError(f'{code}: measured {measured} ft, plan states {length} x {width} ft')
            doc = r2000_document()
            doc.units = 2
            doc.layers.new('P-PMARK', dxfattribs={'color': 7})
            block = doc.blocks.new(code, base_point=(0, 0))
            block.block_record.dxf.units = 2
            hatch = block.add_hatch(color=0, dxfattribs={'layer': '0'})
            for loop, _ in r['loops']:
                pts = to_feet(loop, r['box'], r['step'])
                hatch.paths.add_polyline_path(pts, is_closed=True)
                block.add_lwpolyline(pts, close=True, dxfattribs={'layer': '0', 'color': 0})
            doc.modelspace().add_blockref(code, (0, 0), dxfattribs={'layer': 'P-PMARK'})
            doc.set_modelspace_vport(height=length * 1.2, center=(0, length / 2))
            with tempfile.TemporaryDirectory() as tmp:
                dxf = Path(tmp) / 'm.dxf'
                doc.saveas(dxf)
                log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', OUT / (code + '.dwg'), dxf],
                                     capture_output=True, text=True, check=True)
                if re.search(r'warning|error', log.stdout + log.stderr, re.I):
                    raise ValueError(code + ': ' + log.stdout + log.stderr)
                rt = Path(tmp) / 'rt.dxf'
                subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', rt, OUT / (code + '.dwg')], capture_output=True, check=True)
                back = ezdxf.readfile(rt)
                if [e.dxftype() for e in back.modelspace()] != ['INSERT'] or len(back.blocks[code]) != 2 * len(r['loops']):
                    raise ValueError(code + ': DWG read-back differs')
            rows.append({'code': code, 'name': f'{name} · Caltrans Std. Plan {sheet} (2026)', 'file': code + '.dwg',
                         'group': 'Arrows', 'size': [width, length], 'source': SOURCE, 'sheet': sheet})
    catalog['markings/cad']['blocks'] = rows
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    for row in build(args.pdf, args.libredwg):
        print(row['code'], row['size'])
