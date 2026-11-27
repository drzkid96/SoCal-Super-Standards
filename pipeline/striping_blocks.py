"""Caltrans striping details as DWG blocks and an AutoCAD linetype file.

Every detail in the SSS striping database (pipeline/striping_db.py, read from the 2026 Standard
Plans A20 sheets) becomes:
  - a true-size block, CT-DET-<n>, drawn along +X for one full repeat of all its lines and markers,
    base point at the start of the reference line (y = 0); stripes are SOLID hatches in their
    marking color (yellow ACI 2, white ACI 7, black contrast ACI 250), markers are 4 in squares;
  - one linetype per broken line in SSS-CALTRANS-STRIPING.lin (feet), for drawing long runs.

  python3 pipeline/striping_blocks.py --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf

from sign_cells import r2000_document
from striping_db import D, MARKERS

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/downloads/markings/cad')
LIN = Path('public/downloads/cad-tools/SSS-CALTRANS-STRIPING.lin')
COLOR = {'Y': 2, 'W': 7, 'K': 250}
MARKER = {'Y2': 2, 'Y1': 2, 'C1': 7, 'RC': 1, 'RY': 1}
MARKER_SIZE = 4 / 12


def repeat(rows):
    """Length that holds a whole number of every pattern and marker spacing (at least 24 ft)."""
    spans = [round(sum(r['pat'][:2])) for r in rows if r.get('pat')] + [round(r['every']) for r in rows if 'every' in r]
    length = 1
    for s in spans:
        length = length * s // math.gcd(length, s)
    return max(length, 24) if spans else 24


def rect(x0, x1, yc, w):
    return [(x0, yc - w / 2), (x1, yc - w / 2), (x1, yc + w / 2), (x0, yc + w / 2)]


def pieces(rec, length):
    """(color, rectangle) pairs in feet for one repeat."""
    out = []
    for r in rec['rows']:
        yc = -(r['y'] + r.get('w', 4) / 2) / 12  # rows are measured in inches from the reference edge, downward
        if 't' in r:
            x = r['phase'] % r['every']
            while x < length - 1e-9:
                out.append((MARKER[r['t']], rect(x - MARKER_SIZE / 2, x + MARKER_SIZE / 2, yc, MARKER_SIZE)))
                x += r['every']
            continue
        w = r['w'] / 12
        if not r['pat']:
            out.append((COLOR[r['c']], rect(0, length, yc, w)))
            continue
        on, off, phase = r['pat']
        x = phase - (on + off) * math.ceil(phase / (on + off) + 1)
        while x < length:
            a, b = max(0.0, x), min(length, x + on)
            if b - a > 1e-6:
                out.append((COLOR[r['c']], rect(a, b, yc, w)))
            x += on + off
    return out


def write_block(code, parts, length, libredwg):
    doc = r2000_document()
    doc.units = 2
    doc.layers.new('P-STRP', dxfattribs={'color': 7})
    block = doc.blocks.new(code, base_point=(0, 0))
    block.block_record.dxf.units = 2
    for color, pts in parts:
        hatch = block.add_hatch(color=color, dxfattribs={'layer': '0'})
        hatch.paths.add_polyline_path(pts, is_closed=True)
    doc.modelspace().add_blockref(code, (0, 0), dxfattribs={'layer': 'P-STRP'})
    doc.set_modelspace_vport(height=length * 0.3, center=(length / 2, 0))
    target = OUT / (code + '.dwg')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 's.dxf'
        doc.saveas(path)
        log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', target, path], capture_output=True, text=True, check=True)
        if re.search(r'warning|error', log.stdout + log.stderr, re.I):
            raise ValueError(code + ': ' + (log.stdout + log.stderr)[-300:])
        back = Path(tmp) / 'rt.dxf'
        subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', back, target], capture_output=True, check=True)
        read = ezdxf.readfile(back)
        if [e.dxftype() for e in read.modelspace()] != ['INSERT'] or len(read.blocks[code]) != len(parts):
            raise ValueError(code + ': DWG read-back differs')


def linetypes():
    """AutoCAD .lin entries (feet) for each broken stripe; a pattern that starts with a gap keeps its phase."""
    lines = [';; Caltrans 2026 striping details as AutoCAD linetypes. Units: feet (set LTSCALE 1 in feet drawings).',
             ';; Source: SoCal Super Standards striping database, from Caltrans 2026 Standard Plans A20.']
    for rec in D:
        for n, r in enumerate(x for x in rec.get('rows') or [] if x.get('pat')):
            on, off, phase = r['pat']
            name = f"CT-DET-{rec['d']}" + (f'-{n + 1}' if sum(1 for x in rec.get('rows') or [] if x.get('pat')) > 1 else '')
            desc = f"Caltrans Det {rec['d']}: {on:g} ft stripe, {off:g} ft gap"
            lines.append(f'*{name},{desc[:47]}')
            lines.append(f'A,{on:g},-{off:g}')
    return '\n'.join(lines) + '\n'


def build(libredwg):
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    rows = [r for r in catalog['markings/cad']['blocks'] if not r['code'].startswith('CT-DET-')]
    added = []
    for rec in D:
        if not rec.get('rows'):
            continue  # ramp channelizing and lane drop details carry no line rows yet
        code = 'CT-DET-' + re.sub(r'[^A-Z0-9]+', '-', rec['d'].upper())
        length = repeat(rec['rows'])
        parts = pieces(rec, length)
        write_block(code, parts, length, libredwg)
        width = max(abs(p[1]) for _, pts in parts for p in pts) * 2
        name = f"Detail {rec['d']} · {rec['fn']}, {rec['sub'].lower()} · {rec['type'].lower()}" + (f" · {rec['speed']}" if rec.get('speed') else '')
        added.append({'code': code, 'name': name, 'file': code + '.dwg', 'group': 'Striping patterns',
                      'size': [length, round(width, 2)], 'source': 'Caltrans 2026 Standard Plans A20 (SSS striping database)', 'sheet': 'A20'})
    order = lambda r: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', r['code'])]
    catalog['markings/cad']['blocks'] = rows + sorted(added, key=order)
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    LIN.parent.mkdir(parents=True, exist_ok=True)
    LIN.write_text(linetypes())
    return added


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--libredwg', type=Path, required=True)
    print(len(build(parser.parse_args().libredwg)), 'striping details')
