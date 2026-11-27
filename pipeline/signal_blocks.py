"""Caltrans 2026 electrical legend symbols (Standard Plans ES-1A, ES-1B, ES-1C) as plan-symbol blocks.

The ES-1 sheets place the Caltrans cell library (CTCELLIB, N = new, E = existing) cell by cell. cadkit
reads the DGN; each cell becomes one block at plotted size (one unit = one plotted inch; the sheet
model is 50 units to the inch, so its 0.14 in text is 7 units), base point at the Caltrans cell origin,
geometry on layer 0 ByBlock so the insert layer sets color. Insert at the drawing scale (x40 at
1" = 40'), like the sign cells. Unnamed cells (ES-1C detectors and pull boxes) are named from their
description and column. Each description is read from the sheet row beside the symbol.

  cadkit dump --json 2026__es-01b.dgn > es01b.json   (and es01a, es01c)
  python3 pipeline/signal_blocks.py --json es01a.json es01b.json es01c.json --libredwg <dir>
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

CATALOG = Path('data/reference/design-blocks.json')
ROUTE = 'signals/cad'
OUT = Path('public/downloads') / ROUTE
LIBRARY = 'SSS-SIGNAL-LIBRARY.dwg'
SOURCE = 'https://dot.ca.gov/programs/design/2026-ccs-standard-plans-and-standard-specifications/individual-standard-plans-in-dgn-format-2026-standards'
UNITS_PER_INCH = 50.0
SKIP = {'AHT', 'te'}                  # arrowheads of leader notes and text nodes
# rows whose description is drawn as a symbol or sits on another row
OVERRIDE = {
    'NSMS': 'vehicle signal head consisting of red, yellow and green sections (L, LG, PV, 8 and PHBF modify it)',
    'ESMS': 'vehicle signal head consisting of red, yellow and green sections (L, LG, PV, 8 and PHBF modify it)',
    'NTIII': 'service equipment enclosure Type III, door indicates front of enclosure',
    'ETIII': 'service equipment enclosure Type III, door indicates front of enclosure',
}
NOT_SYMBOLS = ('type of installation and pole height',)
GROUPS = [   # first match wins ("signal" contains "sign", so overhead signs are named exactly)
    ('Annotation', ('abandon', 'install pull', 'install conduit', 'install sign', 'connect', 'conduit to remain', 'foundation to be', 'no slip', 'photoelectric',
                    'relocate', 'remove and', 'splice', 'service disconnect', 'telephone service', 'to be removed',
                    'detector handhole', 'pedestrian barricade, type')),
    ('Overhead signs', ('single sign', 'double sign', 'sign mounted')),
    ('Poles and mast arms', ('mast arm', 'type 1 standard', 'type 15ts', 'type 21ts', 'type 15-fbs standard')),
    ('Lighting', ('luminaire', 'electrolier', 'lighting standard', 'structure')),
    ('Detection', ('detector', 'detection', 'sensor', 'radar')),
    ('Poles and mast arms', ('post', 'pole', 'barricade', 'standard')),
    ('Signal heads', ('signal head', 'flashing beacon')),
    ('Cabinets and conduit', ('',)),
]
SHORT = re.compile(r'^[A-Z0-9]{1,3}$|^(NEW|EXISTING|DESCRIPTION|SYMBOL|TYPE)$')


def texts(entities):
    out = []

    def walk(items):
        for e in items:
            k = e['kind']
            if k['type'] == 'text':
                out.append((k['position']['x'], k['position']['y'], k['value'].strip(), k.get('height', 0)))
            elif k['type'] == 'group' and k.get('group_kind') == 'text_node':
                walk(k.get('children', []))
    walk(entities)
    return [t for t in out if t[2]]


def points(kind):
    t = kind['type']
    if t == 'line':
        return [(kind['start']['x'], kind['start']['y']), (kind['end']['x'], kind['end']['y'])]
    if t == 'polyline':
        return [(v['position']['x'], v['position']['y']) for v in kind['vertices']]
    if t in ('circle', 'arc'):
        c, r = kind['center'], kind['radius']
        return [(c['x'] - r, c['y'] - r), (c['x'] + r, c['y'] + r)]
    if t == 'text':
        return [(kind['position']['x'], kind['position']['y'])]
    if t == 'group':
        return [p for ch in kind.get('children', []) for p in points(ch['kind'])]
    return []


def describe(cell, box, words):
    """The description entry on the cell's row: the description column is the nearest column of long
    text to the right; its lines group into entries by spacing, and the entry whose lines span the
    cell's height (or sit closest to it) is the one that describes it."""
    cy = (box[1] + box[3]) / 2
    right = [w for w in words if w[0] > box[2] + 4 and abs(w[1] - cy) < 20 and len(w[2]) > 3 and not SHORT.match(w[2])]
    if not right:
        return None
    x0 = min(w[0] for w in right)
    column = sorted((w for w in words if abs(w[0] - x0) < 3 and abs(w[1] - cy) < 60), key=lambda w: -w[1])
    entries, cur = [], []
    for w in column:
        if cur and cur[-1][1] - w[1] > 16:
            entries.append(cur)
            cur = []
        cur.append(w)
    if cur:
        entries.append(cur)

    def gap(entry):
        top, bottom = entry[0][1] + 5, entry[-1][1] - 5
        return 0 if bottom <= cy <= top else min(abs(cy - top), abs(cy - bottom))
    entry = min(entries, key=gap)
    return ' '.join(w[2] for w in entry) if gap(entry) < 12 else None


def lighting_type(box, words):
    """ES-1A lighting standards are labeled by type (15, 15D, 21 STRUCTURE) in a TYPE column."""
    cy = (box[1] + box[3]) / 2
    heads = [w for w in words if w[2] == 'TYPE' and w[1] > cy]
    for w in sorted((w for w in words if w[0] > box[2] + 4 and abs(w[1] - cy) < 6), key=lambda w: w[0]):
        if any(abs(h[0] - w[0]) < 15 for h in heads):
            return f'lighting standard Type {w[2]}'
    return None


def state_of(box, words):
    """NEW or EXISTING from the column header above the symbol; None for annotation and wiring symbols."""
    cx = (box[0] + box[2]) / 2
    heads = [w for w in words if w[2] in ('NEW', 'EXISTING', 'SYMBOL') and w[1] > box[3] and abs(w[0] - cx) < 45]
    if not heads:
        return None
    head = min(heads, key=lambda w: w[1] - box[3])
    return {'NEW': 'N', 'EXISTING': 'E'}.get(head[2])


def codes(text):
    """Sentence case loses Caltrans codes; put them back (Type 15D, Type III, NC, NO, 9A, 15-FBS, "L", "PV")."""
    text = re.sub(r'\b(type) ([0-9]+[a-z]*(?:-[a-z]+)?|[ivx]+|[a-z])\b', lambda m: 'Type ' + m.group(2).upper(), text)
    text = re.sub(r'\b(\d+[a-z]+|nc|iii|ts)\b', lambda m: m.group(1).upper(), text)
    text = re.sub(r'\bno contact\b', 'NO contact', text)
    return re.sub(r'"([a-z0-9]{1,4})"', lambda m: '"' + m.group(1).upper() + '"', text)


def slug(text):
    first = re.split(r'\.\s|\(|=|\bunless\b', text, flags=re.I)[0]   # the first clause names the symbol
    raw = re.sub(r'[^A-Z0-9]+', '-', first.upper()).strip('-').split('-')
    words = [w for i, w in enumerate(raw) if w not in ('A', 'AN', 'THE', 'OF') or (i and raw[i - 1] == 'TYPE')]
    while len(words) > 1 and len(words[-1]) == 1 and not words[-1].isdigit():
        words.pop()
    out = ''
    for w in words:   # whole words only, about 32 characters
        if out and len(out) + len(w) + 1 > 32:
            break
        out = f'{out}-{w}' if out else w
    return out


def add(block, kind, ox, oy):
    """Copy one DGN element into the block, moved to the cell origin and scaled to plotted inches."""
    s = 1 / UNITS_PER_INCH
    tr = lambda x, y: ((x - ox) * s, (y - oy) * s)
    t = kind['type']
    at = {'layer': '0', 'color': 0}
    if t == 'line':
        a, b = tr(kind['start']['x'], kind['start']['y']), tr(kind['end']['x'], kind['end']['y'])
        if math.dist(a, b) > 1e-6:   # the sheets carry a few zero-length lines
            block.add_line(a, b, dxfattribs=at)
    elif t == 'polyline':
        pts = []
        for v in kind['vertices']:
            p = tr(v['position']['x'], v['position']['y']) + (v.get('bulge', 0),)
            if not pts or math.dist(pts[-1][:2], p[:2]) > 1e-6:   # drop repeated vertices
                pts.append(p)
        if len(pts) < 2:
            return
        closed = len(pts) > 2 and math.dist(pts[0][:2], pts[-1][:2]) < 1e-6
        block.add_lwpolyline(pts[:-1] if closed else pts, format='xyb', close=closed, dxfattribs=at)
    elif t == 'circle':
        block.add_circle(tr(kind['center']['x'], kind['center']['y']), kind['radius'] * s, dxfattribs=at)
    elif t == 'arc':
        block.add_arc(tr(kind['center']['x'], kind['center']['y']), kind['radius'] * s,
                      math.degrees(kind['start_angle']), math.degrees(kind['end_angle']), dxfattribs=at)
    elif t == 'text':
        txt = block.add_text(kind['value'], height=kind.get('height', 7) * s,
                             dxfattribs=dict(at, style='ROMANS', rotation=math.degrees(kind.get('rotation', 0))))
        txt.set_placement(tr(kind['position']['x'], kind['position']['y']), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    elif t == 'group':
        for ch in kind.get('children', []):
            add(block, ch['kind'], ox, oy)


def build(dumps, libredwg):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, seen, named = [], set(), set()
    # named cells first on each sheet, so an unnamed fragment of the same symbol is left out
    for dump in dumps:
        data = json.loads(Path(dump).read_text())
        sheet = 'ES-' + re.search(r'es0?(\d+[a-z])', Path(dump).stem).group(1).upper()
        model = data['models'][0]['entities']
        words = texts(model)
        heads = {w[2]: w for w in words if w[2] in ('NEW', 'EXISTING')}
        for e in sorted(model, key=lambda e: e['kind'].get('name') is None):
            k = e['kind']
            if k['type'] != 'group' or k.get('group_kind') not in ('cell', 'complex_shape') or k.get('name') in SKIP:
                continue
            pts = points(k)
            if not pts:
                continue
            box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
            size = ((box[2] - box[0]) / UNITS_PER_INCH, (box[3] - box[1]) / UNITS_PER_INCH)
            if max(size) > 2.0 or min(size) < 0.02:
                continue   # sheet border, conduit line samples
            desc = OVERRIDE.get(k.get('name')) or describe(k, box, words) or lighting_type(box, words)
            if not desc or desc.lower().startswith(NOT_SYMBOLS):
                continue
            state = state_of(box, words)
            key = (sheet, state, desc)
            name = k.get('name')
            if not name:
                if key in named:
                    continue   # an unnamed piece of a symbol whose named cell is published
                name = (state + '-' if state else '') + slug(desc)
            else:
                named.add(key)
            code = f"CT-{sheet.replace('-', '')}-{name}"
            if code in seen:
                continue
            seen.add(code)
            origin = k.get('origin') or {'x': (box[0] + box[2]) / 2, 'y': (box[1] + box[3]) / 2}
            label = codes(desc.lower())
            if state and not label.startswith(('new ', 'existing ')):
                label = {'N': 'new ', 'E': 'existing '}[state] + label
            write(code, k, origin, libredwg)
            group = next(g for g, keys in GROUPS if any(key in desc.lower() for key in keys))
            rows.append({'code': code, 'name': f'{label[0].upper() + label[1:]} · Caltrans Std. Plan {sheet} (2026)', 'file': code + '.dwg',
                         'group': group,
                         'size': [round(size[0], 2), round(size[1], 2)],
                         'source': SOURCE, 'sheet': sheet})
    return rows


def write(code, kind, origin, libredwg):
    doc = r2000_document()
    doc.units = 1   # inches: one unit is one plotted inch
    doc.layers.new('P-SIGNAL', dxfattribs={'color': 7})
    block = doc.blocks.new(code, base_point=(0, 0))
    block.block_record.dxf.units = 1
    add(block, kind, origin['x'], origin['y'])
    doc.modelspace().add_blockref(code, (0, 0), dxfattribs={'layer': 'P-SIGNAL'})
    target = OUT / (code + '.dwg')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'c.dxf'
        doc.saveas(path)
        log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', target, path], capture_output=True, text=True, check=True)
        if re.search(r'warning|error', log.stdout + log.stderr, re.I):
            raise ValueError(code + ': ' + (log.stdout + log.stderr)[-300:])
        back = Path(tmp) / 'rt.dxf'
        subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', back, target], capture_output=True, check=True)
        read = ezdxf.readfile(back)
        if [e.dxftype() for e in read.modelspace()] != ['INSERT'] or len(read.blocks[code]) != len(block):
            raise ValueError(code + ': DWG read-back differs')


def library(rows, libredwg):
    """Every symbol in one drawing for the Blocks palette, by group, code under each (plotted inches)."""
    from ezdxf.addons import Importer
    lib = r2000_document()
    lib.units = 1
    for name in ('P-SIGNAL', 'P-SIGNAL-TEXT'):
        lib.layers.new(name, dxfattribs={'color': 3 if name == 'P-SIGNAL' else 7})
    msp, y = lib.modelspace(), 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for group in dict.fromkeys(g for g, _ in GROUPS):
            members = [r for r in rows if r['group'] == group]
            if not members:
                continue
            msp.add_text(group.upper(), height=0.2, dxfattribs={'layer': 'P-SIGNAL-TEXT', 'style': 'ROMANS', 'insert': (0, y)})
            y -= 0.6
            for n, r in enumerate(members):
                col, row = n % 8, n // 8
                dxf = Path(tmp) / (r['code'] + '.dxf')
                subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', dxf, OUT / r['file']], capture_output=True, check=True)
                imp = Importer(ezdxf.readfile(dxf), lib)
                imp.import_block(r['code'])
                imp.finalize()
                at = (col * 2.2 + 1.0, y - row * 1.6 - 0.6)
                msp.add_blockref(r['code'], at, dxfattribs={'layer': 'P-SIGNAL'})
                msp.add_text(r['code'].replace('CT-', ''), height=0.06, dxfattribs={'layer': 'P-SIGNAL-TEXT', 'style': 'ROMANS'}).set_placement(
                    (at[0], at[1] - 0.6), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            y -= ((len(members) - 1) // 8 + 1) * 1.6 + 0.8
        path = Path(tmp) / 'lib.dxf'
        lib.set_modelspace_vport(height=-y * 1.05, center=(9, y / 2))
        lib.saveas(path)
        target = OUT / LIBRARY
        log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', target, path], capture_output=True, text=True, check=True)
        if re.search(r'warning|error', log.stdout + log.stderr, re.I):
            raise ValueError('library: ' + (log.stdout + log.stderr)[-300:])


def publish(rows):
    """Replace this script's CT-ES rows and library entry; plan-library rows (plan_blocks.py) stay."""
    catalog = json.loads(CATALOG.read_text())
    section = catalog[ROUTE]
    others = [b for b in section['blocks'] if not b['code'].startswith('CT-ES')]
    section['blocks'] = rows + others
    order = list(dict.fromkeys(g for g, _ in GROUPS))
    section['groups'] = list(dict.fromkeys([g for g in order if any(r['group'] == g for r in section['blocks'])] + section['groups']))
    section['note'] = ('Caltrans 2026 electrical legend symbols (Standard Plans ES-1A, ES-1B and ES-1C) '
                       'at plotted size: one unit = one plotted inch, insert at the drawing scale (x40 at 1" = 40\'), base '
                       'point at the Caltrans cell origin. LA plan-library blocks (PM-, SG-, SN-, SV-) '
                       ' are in feet at plan size, insert at 1; most are dynamic with existing, proposed, '
                       'remove and abandon states on E-, P-, R- and A- layers. Every drawing opens as block inserts only, geometry on layer '
                       '0 ByBlock or its state layer.')
    entry = {'label': LIBRARY, 'path': f'downloads/{ROUTE}/{LIBRARY}',
             'note': 'every Caltrans ES-1 symbol in one drawing, for the Blocks palette (Libraries tab), DesignCenter or a tool palette'}
    section['downloads'] = [entry] + [d for d in section.get('downloads', []) if d['label'] != LIBRARY]
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', nargs='+', required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    rows = build(args.json, args.libredwg)
    library(rows, args.libredwg)
    publish(rows)
    for r in rows:
        print(r['group'], '|', r['code'], '|', r['name'].split(' · ')[0])
