"""Details shown when a marking or signal block is opened: base point, visibility states and
filled area per color, read from each published DWG.

Visibility states come from the DWG's dynamic-block data (LibreDWG dwgread JSON). Geometry comes from
the same DWG converted by ODA File Converter, so entity handles match the state lists. Area is the
filled (hatch and solid) area of what shows in each state, in square drawing units, per plotted color.

  python3 pipeline/block_info.py   (needs ODAFileConverter, LibreDWG dwgread, xvfb-run when headless)
writes data/reference/block-info.json, read by design_blocks.py.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox, path as zpath
from shapely.geometry import Polygon
from shapely.ops import unary_union

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('data/reference/block-info.json')
DWGREAD = Path(os.environ.get('DWGREAD', Path.home() / '.cache/dxf-to-dwg/libredwg/_b/dwgread'))
UNITS = {1: 'in', 2: 'ft', 4: 'mm', 6: 'm', 21: 'ft'}
ACI = {1: ('Red', '#d71920'), 2: ('Yellow', '#f2c500'), 3: ('Green', '#3c9002'), 4: ('Cyan', '#00a7c8'),
       5: ('Blue', '#1f4fd1'), 6: ('Magenta', '#b0158f'), 7: ('White', '#ffffff'), 8: ('Gray', '#808080'),
       9: ('Light gray', '#c0c0c0'), 30: ('Orange', '#f28c00')}
NAMED = [(n, h) for n, h in ACI.values()] + [('Black', '#000000'), ('Dark gray', '#404040')]


def rgb(hexcode):
    return tuple(int(hexcode[i:i + 2], 16) for i in (1, 3, 5))


def color_name(value):
    """(name, hex) for an ACI number or an (r, g, b) true color."""
    if isinstance(value, tuple):
        hexcode = '#%02x%02x%02x' % value
        name = min(NAMED, key=lambda nh: sum((a - b) ** 2 for a, b in zip(rgb(nh[1]), value)))[0]
        return name, hexcode
    if value in ACI:
        return ACI[value]
    return color_name(tuple(ezdxf.colors.aci2rgb(value)))


def resolve(e, doc, parent):
    """Plotted color of an entity: true color, else ACI with ByBlock and ByLayer followed."""
    if e.dxf.hasattr('true_color'):
        return ezdxf.colors.int2rgb(e.dxf.true_color)
    c = e.dxf.get('color', 256)
    if c == 0:
        return parent
    if c == 256:
        layer = e.dxf.get('layer', '0')
        if layer == '0':
            return parent
        lay = doc.layers.get(layer) if layer in doc.layers else None
        if lay is None:
            return 7
        return ezdxf.colors.int2rgb(lay.dxf.true_color) if lay.dxf.hasattr('true_color') else abs(lay.dxf.color)
    return c


def polygons(e):
    t = e.dxftype()
    if t == 'HATCH':
        rings = []
        for p in zpath.from_hatch(e):
            pts = [(v.x, v.y) for v in p.flattening(0.01)]
            if len(pts) >= 3:
                rings.append(Polygon(pts).buffer(0))
        shape = None
        for r in rings:                      # even-odd: holes cut, islands fill
            shape = r if shape is None else shape.symmetric_difference(r)
        return shape
    if t in ('SOLID', 'TRACE'):
        v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx3, e.dxf.vtx2]
        return Polygon([(p.x, p.y) for p in v]).buffer(0)
    return None


def walk(entities, doc, parent, out):
    for e in entities:
        if e.dxf.get('layer', '').upper() in ('NOPLOT', 'DEFPOINTS'):
            continue
        if e.dxftype() == 'INSERT':
            walk(e.virtual_entities(), doc, resolve(e, doc, parent), out)
            continue
        shape = polygons(e)
        if shape is not None and not shape.is_empty:
            out.setdefault(resolve(e, doc, parent), []).append(shape)


def areas(entities, doc, parent):
    shapes = {}
    walk(entities, doc, parent, shapes)
    rows = []
    for color, items in shapes.items():
        a = unary_union(items).area
        if a >= 0.005:
            name, hexcode = color_name(color)
            rows.append([name, hexcode, round(a, 2)])
    return sorted(rows, key=lambda r: -r[2])


def states_of(dwg):
    """[(state name, set of entity handles)] from the DWG's visibility parameter, or []."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'a.json'
        subprocess.run([str(DWGREAD), '-O', 'JSON', '-o', str(out), str(dwg)], capture_output=True, timeout=300)
        if not out.is_file():
            return []
        data = json.loads(out.read_text(errors='ignore'))
    for o in data.get('OBJECTS', []):
        if o.get('object') == 'BLOCKVISIBILITYPARAMETER' and o.get('states'):
            return [(s['name'], {'%X' % b[-1] for b in s.get('blocks', [])}) for s in o['states']]
    return []


def where(ext, size, unit):
    """Plain words for where the insertion point sits on the block."""
    x0, y0, x1, y1 = ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y
    tol = 0.03 * size
    def axis(lo, hi, names):
        if abs(lo) <= tol:
            return names[0], 0
        if abs(hi) <= tol:
            return names[2], 0
        if abs((lo + hi) / 2) <= tol:
            return names[1], 0
        if lo < 0 < hi:
            return names[1], 0
        return (names[0], lo) if lo > 0 else (names[2], hi)
    xs, dx = axis(x0, x1, ('left', 'center', 'right'))
    ys, dy = axis(y0, y1, ('bottom', 'middle', 'top'))
    inside_x = x0 - tol <= 0 <= x1 + tol
    inside_y = y0 - tol <= 0 <= y1 + tol
    words = {('bottom', 'center'): 'Bottom center', ('top', 'center'): 'Top center', ('middle', 'center'): 'Center',
             ('bottom', 'left'): 'Lower left corner', ('bottom', 'right'): 'Lower right corner',
             ('top', 'left'): 'Upper left corner', ('top', 'right'): 'Upper right corner',
             ('middle', 'left'): 'Left edge, middle', ('middle', 'right'): 'Right edge, middle'}
    if inside_x and inside_y:
        return words[(ys, xs)]
    num = lambda v: f'{abs(v):.2f}'.rstrip('0').rstrip('.')
    parts = []
    if not inside_y:
        parts.append(f'{num(dy)} {unit} {"below the bottom" if dy > 0 else "above the top"}')
    else:
        parts.append({'bottom': 'level with the bottom', 'top': 'level with the top', 'middle': 'level with the middle'}[ys])
    if not inside_x:
        parts.append(f'{num(dx)} {unit} {"left of the left edge" if dx > 0 else "right of the right edge"}')
    else:
        parts.append({'left': 'on the left edge', 'right': 'on the right edge', 'center': 'centered'}[xs])
    return 'Off the block: ' + ', '.join(parts)


def info(dxf, dwg):
    doc = ezdxf.readfile(dxf)
    unit = UNITS.get(doc.header.get('$INSUNITS', 0), 'units')
    ins = [e for e in doc.modelspace() if e.dxftype() == 'INSERT']
    if not ins:
        return None
    top = ins[0]
    block = doc.blocks[top.dxf.name]
    parent = resolve(top, doc, 7)
    states = states_of(dwg)
    everything = list(block)
    if states:
        listed = set().union(*(h for _, h in states))
        always = [e for e in everything if e.dxf.handle not in listed]
        views = [(name, always + [e for e in everything if e.dxf.handle in hs]) for name, hs in states]
    else:
        views = [('', everything)]
    rows = []
    for name, ents in views:
        a = areas(ents, doc, parent)
        rows.append({'state': name, 'area': a})
    same = all(r['area'] == rows[0]['area'] for r in rows)
    # base point words from the first state (the drawing extents of what shows)
    first = views[0][1]
    ext = bbox.extents(e for e in first if e.dxf.get('layer', '').upper() not in ('NOPLOT', 'DEFPOINTS'))
    if not ext.has_data:
        ext = bbox.extents(everything)
    size = max(ext.size.x, ext.size.y, 1e-6)
    out = {'unit': unit, 'base': where(ext, size, unit), 'size': [round(ext.size.x, 3), round(ext.size.y, 3)],
           'states': [n for n, _ in states]}
    if same:
        out['area'] = rows[0]['area']
    else:
        out['areaByState'] = [[r['state'], r['area']] for r in rows]
    return out


def build():
    catalog = json.loads(CATALOG.read_text())
    result = {}
    with tempfile.TemporaryDirectory() as tmp:
        src, dxf = Path(tmp) / 'in', Path(tmp) / 'out'
        src.mkdir(), dxf.mkdir()
        rows = []
        for route, collection in catalog.items():
            for row in collection['blocks']:
                dwg = Path('public/downloads') / route / row['file']
                shutil.copy(dwg, src / row['file'])
                rows.append((route, row, dwg))
        cmd = ['ODAFileConverter', str(src), str(dxf), 'ACAD2018', 'DXF', '0', '1', '*.dwg']
        if shutil.which('xvfb-run'):
            cmd = ['xvfb-run', '-a'] + cmd
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
        for route, row, dwg in rows:
            item = info(dxf / (Path(row['file']).stem + '.dxf'), dwg)
            if item:
                result[row['code']] = item
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    return len(result)


if __name__ == '__main__':
    print(build(), 'blocks described in', OUT)
