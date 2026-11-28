"""Pavement marking DWG blocks taken from a signing and striping plan drawing.

Plan sets often hold marking blocks drawn at a display scale and inserted at a fraction of it.
Each block here is flattened (nested blocks and insert scales baked in) to true size in feet,
rebased so the base point is the bottom center (top center for yield line triangles, which sit on the line), and checked against
its stated size before it is published.

Build locally (the plan drawing stays outside the repository):
  python3 pipeline/plan_marking_blocks.py --dxf plan.dxf --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44

from sign_cells import r2000_document

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/downloads/markings/cad')
SOURCE_LABEL = 'LA signing and striping plan library'
# code, source block, scale (x, y) that gives true size, base point rule, group, name, check (axis, feet, tolerance)
SHAPES = [
    ('PM-YIELD-LINE-TRIANGLE', 'YIELDLL', (1, 1), 'top', 'Words and symbols', 'Yield line triangle, 2 ft base x 3 ft', ('y', 3.0, 0.02)),
    ('PM-BIKE-SYMBOL', 'BIKE-SYM2', (0.7308, 2.4118), 'bottom', 'Bicycle markings', 'Bicycle symbol, 6 ft long', ('y', 6.0, 0.1)),
    ('PM-BIKE-ARROW', 'BIKE LANE ARROW', (10.5362, 10.5362), 'bottom', 'Bicycle markings', 'Bike lane arrow', None),
    # ('PM-BIKE-ARROW-LEFT-THRU', 'BIKE-LEFT-THRU-ARROW', (1, 1), 'bottom', 'Bicycle markings', 'Bike lane left and through arrow', None),  # repeats a published dynamic block, not published
    # ('PM-BIKE-LANE-SYMBOL-GREEN', 'Bike-NoPerson-Arrow', (1, 1), 'bottom', 'Bicycle markings',  # repeats a published dynamic block, not published
    # 'Bike lane symbol and arrow on green, 7 x 25 ft', ('y', 25.0, 0.05)),
]
SKIP_LAYERS = re.compile(r'NOPLOT|WORKING', re.I)


def flatten(doc, name, sx, sy):
    """Virtual entities of the block at its true-size scale, nested blocks expanded."""
    msp = doc.modelspace()
    ref = msp.add_blockref(name, (0, 0), dxfattribs={'xscale': sx, 'yscale': sy})
    out = []

    def walk(entity):
        for v in entity.virtual_entities():
            if v.dxftype() == 'INSERT':
                walk(v)
            elif not SKIP_LAYERS.search(v.dxf.layer):
                out.append(v)
    walk(ref)
    msp.delete_entity(ref)
    # Green fills first, so the white symbol on top stays visible in draw order.
    return sorted(out, key=lambda e: 'GREEN' not in e.dxf.layer.upper())


def build(dxf, libredwg):
    from ezdxf import recover
    source, _ = recover.readfile(dxf)
    catalog = json.loads(CATALOG.read_text())
    rows = [r for r in catalog['markings/cad']['blocks'] if not r['code'].startswith('PM-')]
    OUT.mkdir(parents=True, exist_ok=True)
    for code, name, (sx, sy), base, group, label, check in SHAPES:
        parts = flatten(source, name, sx, sy)
        ext = bbox.extents(parts)
        size = (ext.extmax.x - ext.extmin.x, ext.extmax.y - ext.extmin.y)
        if check:
            axis, feet, tol = check
            measured = size[0] if axis == 'x' else size[1]
            if abs(measured - feet) > tol:
                raise ValueError(f'{code}: measured {measured:.3f} ft, expected {feet} ft')
        cx = (ext.extmin.x + ext.extmax.x) / 2
        cy = {'bottom': ext.extmin.y, 'top': ext.extmax.y}.get(base, (ext.extmin.y + ext.extmax.y) / 2)  # top: yield triangles sit on the yield line
        move = Matrix44.translate(-cx, -cy, 0)
        doc = r2000_document()
        doc.units = 2
        doc.styles.new('PVMT-ROMANS', dxfattribs={'font': 'romans.shx', 'width': 0.2})
        doc.layers.new('P-PMARK', dxfattribs={'color': 7})
        block = doc.blocks.new(code, base_point=(0, 0))
        block.block_record.dxf.units = 2
        for entity in parts:
            copy = entity.copy()
            copy.transform(move)
            green = 'GREEN' in entity.dxf.layer.upper()
            copy.dxf.layer = '0'
            copy.dxf.color = 3 if green else 0
            if copy.dxftype() in ('TEXT', 'MTEXT'):
                copy.dxf.style = 'PVMT-ROMANS'
            block.add_entity(copy)
        doc.modelspace().add_blockref(code, (0, 0), dxfattribs={'layer': 'P-PMARK'})
        doc.set_modelspace_vport(height=max(size) * 1.3, center=(0, size[1] / 2 if base == 'bottom' else -size[1] / 2 if base == 'top' else 0))
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
        rows.append({'code': code, 'name': f'{label} · {SOURCE_LABEL}', 'file': code + '.dwg', 'group': group,
                     'size': [round(size[0], 2), round(size[1], 2)], 'source': SOURCE_LABEL})
        print(code, f'{size[0]:.2f} x {size[1]:.2f} ft', len(block), 'entities')
    catalog['markings/cad']['blocks'] = rows
    for group in ('Bicycle markings',):
        if group not in catalog['markings/cad']['groups']:
            catalog['markings/cad']['groups'].insert(2, group)
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dxf', required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    build(args.dxf, args.libredwg)
