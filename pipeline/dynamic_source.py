"""SSS-DYNAMIC-SOURCE.dwg: every dynamic family state in one drawing, ready for AutoCAD to build.

The drawing holds
- one block definition per state, named FAMILY$STATE (geometry on layer 0 ByLayer, NOPLOT frames kept),
  square to X and Y, with the family's shared base point at 0,0 (signs: the face bottom center);
- the family list as XRECORDs in the named dictionary SSS_DYNAMIC (F000, F001, ...), which
  SSS-DYNBUILD.lsp reads: label, units, grip radius, flip line and the ordered state blocks;
- a review sheet in model space: one row per family, every state in order with its name, plus an
  empty slot where the routine places the finished dynamic block for a side-by-side check.

The drawing opens zoomed to the sheet. Run SSSDYNBUILD in it, save, and upload the saved drawing.

  python3 pipeline/dynamic_source.py --libredwg <dir> [--libdxfrw <path>]
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox, path as ezpath
from ezdxf.addons import Importer

import cad_standard as std

FAMILIES = Path('data/reference/dynamic-families.json')
HYDRATED = Path('public/downloads/sign-blocks/manifest.json')
OUT = Path('public/downloads/cad-tools/SSS-DYNAMIC-SOURCE.dwg')
REVIEW = 'SSS-REVIEW'
UNITS = {'ft': 2, 'in': 1}
WRAP = 320.0         # ft, review sheet row length before a family wraps to a new line
SIGN_SCALE = 10.0     # sign rows on the review sheet are shown 10x so they read beside the markings


def oda(src, out, fmt):
    cmd = ['ODAFileConverter', str(src), str(out), 'ACAD2018', fmt, '0', '1', '*.dwg' if fmt == 'DXF' else '*.dxf']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=3600)


def state_paths(fams):
    by_id = {r['id']: 'sign-blocks/' + r['file'] for r in json.loads(HYDRATED.read_text())['records']}
    for f in fams:
        if f.get('kind') == 'array':
            continue
        for s in f['states']:
            s['path'] = Path('public/downloads') / (s['file'] if 'file' in s else by_id[s['id']])


def shape(blk, n=120):
    """Coarse picture of a block (occupancy grid over its extents) to find two states that draw the same face."""
    from ezdxf import disassemble
    ext = bbox.extents(drawn(blk))
    sx, sy = max(ext.size.x, 1e-9), max(ext.size.y, 1e-9)
    cells = set()
    for prim in disassemble.to_primitives(disassemble.recursive_decompose(drawn(blk))):
        try:
            pts = list(prim.vertices())
        except Exception:
            continue
        for a, b in zip(pts, pts[1:] or pts):
            for t in range(9):
                x = a.x + (b.x - a.x) * t / 8
                y = a.y + (b.y - a.y) * t / 8
                cells.add((min(n - 1, int((x - ext.extmin.x) / sx * n)), min(n - 1, int((y - ext.extmin.y) / sy * n))))
    from collections import Counter
    styles = Counter((e.dxftype(), e.dxf.get('linetype', 'BYLAYER').upper()) for e in blk)
    return round(sx / sy, 2), frozenset(cells), frozenset(styles.items())


def same(a, b):
    if abs(a[0] - b[0]) > 0.03:
        return False
    if a[2] != b[2]:
        return False      # same outline, different line style (an existing symbol is dashed)
    union = len(a[1] | b[1])
    return union and len(a[1] & b[1]) / union > 0.97


def rank(state):
    """Which of two identical states keeps its place: plain L and R names first, the bare code last."""
    name = state['state']
    return (0 if name[-1:] in 'LR' and '(' not in name else 1 if '(' in name else 2, name)


def drawn(blk):
    return [e for e in blk if e.dxf.get('layer') != std.NOPLOT] or list(blk)


def build(work):
    fams = json.loads(FAMILIES.read_text())['families']
    state_paths(fams)
    src_dir, dxf_dir = work / 'src', work / 'dxf'
    src_dir.mkdir(), dxf_dir.mkdir()
    keys = {}
    for f in fams:
        if f['kind'] == 'array':
            continue
        for s in f['states']:
            k = f's{len(keys):04d}'
            keys[k] = s
            s['key'] = k
            shutil.copy(s['path'], src_dir / f'{k}.dwg')
    oda(src_dir, dxf_dir, 'DXF')

    doc = ezdxf.new('R2018', setup=True)
    doc.units = 2
    doc.header['$INSUNITS'] = 2
    doc.header['$MEASUREMENT'] = 0
    doc.layers.new(std.NOPLOT, dxfattribs={'color': 8, 'plot': 0})
    doc.layers.new(REVIEW, dxfattribs={'color': 8, 'plot': 0})
    for f in fams:
        units = UNITS[f['units']]
        if f['kind'] == 'array':
            continue
        for s in f['states']:
            src = ezdxf.readfile(dxf_dir / f"{s['key']}.dxf")
            inner = src.modelspace().query('INSERT').first.dxf.name
            imp = Importer(src, doc)
            imp.import_block(inner, rename=True)
            imp.finalize()
            got = imp.imported_blocks.get(inner, inner) if hasattr(imp, 'imported_blocks') else inner
            if got not in doc.blocks:
                got = next(b.name for b in doc.blocks if b.name.startswith(inner))
            doc.blocks.rename_block(got, s['block'])
            blk = doc.blocks[s['block']]
            blk.block_record.dxf.units = units
            turn = std.axis_angle(blk)
            if turn:
                raise ValueError(f"{s['block']} is drawn off the X and Y axes; normalize it first")
            if f['route'] == 'signs/cad':     # signs: base point at the face bottom center (the post)
                ext = bbox.extents(drawn(blk))
                dx, dy = -(ext.extmin.x + ext.extmax.x) / 2, -ext.extmin.y
                for e in blk:
                    e.translate(dx, dy, 0)
            for e in blk:
                if e.dxf.get('layer') not in ('0', std.NOPLOT):
                    e.dxf.layer = '0'

    # the same face published under two names (R6-1(RT) and R6-1R, R2-1 and R2-1(50)) is one state
    dropped = []
    for f in fams:
        if f['route'] != 'signs/cad' or len(f['states']) < 2:
            continue      # signs only: the same face from two libraries; signal new and existing stay both
        keep = []
        for st in sorted(f['states'], key=rank):
            pic = shape(doc.blocks[st['block']])
            twin = next((k for k, p in keep if same(p, pic)), None)
            if twin:
                dropped.append(f"{st['block']} = {twin['block']}")
                doc.blocks.delete_block(st['block'], safe=False)
            else:
                keep.append((st, pic))
        order = [st['block'] for st in f['states']]
        f['states'] = sorted((st for st, _ in keep), key=lambda st: order.index(st['block']))
    fams = [f for f in fams if len(f['states']) > 1 or f['route'] != 'signs/cad']
    print(len(dropped), 'duplicate states dropped:', '; '.join(dropped))
    FAMILIES.write_text(json.dumps(dict(json.loads(FAMILIES.read_text()), families=[
        {k: v for k, v in f.items() if k not in ('path',)} | {'states': [{k: v for k, v in st.items() if k not in ('path', 'key')}
                                                                           for st in f['states']]} for f in fams]), indent=1) + '\n')

    # conditions (LADOT: proposed filled, existing outline, remove dashed outline) and array units
    for f in fams:
        f['expanded'] = expand(doc, f)

    # review sheet and manifest
    msp = doc.modelspace()
    root = doc.rootdict.add_new_dict('SSS_DYNAMIC')
    y, gap, inserts = 0.0, 6.0, 0
    for i, f in enumerate(fams):
        scale = SIGN_SCALE if f['units'] == 'in' else 1.0
        cells = [review_extents(doc, f, st) for st in f['expanded']]
        w = max(e[2] - e[0] for e in cells) * scale
        ymin = min(e[1] for e in cells) * scale
        ymax = max(e[3] for e in cells) * scale
        text = 1.0
        top = y
        msp.add_mtext(f"{f['name']}  ·  {f.get('description') or f['label']}  ·  {len(f['expanded'])} STATES"
                      + ('  ·  SHOWN 10X' if scale != 1 else ''),
                      dxfattribs={'layer': REVIEW, 'char_height': 1.6, 'insert': (0, top), 'attachment_point': 7})
        base_y = top - 2.6 - ymax
        step = max(w, 0.62 * text * max(len(st['name']) for st in f['expanded'])) + gap
        x, line_h = 0.0, ymax - ymin + 3.0
        for st, e in zip(f['expanded'], cells):
            if x and x + step > WRAP:
                x, base_y = 0.0, base_y - line_h - gap
            inserts += place_review(msp, f, st, (x - e[0] * scale, base_y), scale)
            msp.add_mtext(st['name'], dxfattribs={'layer': REVIEW, 'char_height': text, 'attachment_point': 1,
                                                  'insert': (x, base_y + ymin - 0.8)})
            x += step
        if x + step > WRAP:
            x, base_y = 0.0, base_y - line_h - gap
        else:
            x += gap
        slot = (x - min(e[0] for e in cells) * scale, base_y)
        msp.add_mtext('DYNAMIC BLOCK', dxfattribs={'layer': REVIEW, 'char_height': text, 'attachment_point': 1,
                                                   'insert': (x, base_y + ymin - 0.8)})
        length = float(f.get('length') or 0.0)
        end = (length, 0.0, 0.0) if f.get('axis', 'x') == 'x' else (0.0, length, 0.0)
        tags = [(1, f['name']), (2, f['label'][:250]), (70, UNITS[f['units']]), (40, float(f.get('radius') or 2.0)),
                (71, 1 if f.get('flip_x') is not None else 0), (10, (float(f.get('flip_x') or 0.0), 0.0, 0.0)),
                (11, (slot[0], slot[1], 0.0)), (41, scale), (72, 1 if f['kind'] == 'array' else 0), (12, end),
                (73, 0 if f.get('axis', 'x') == 'x' else 1), (13, (float(f.get('width') or 0.0), 0.0, 0.0)),
                (301, (f.get('description') or f['label'])[:250])]
        for st in f['expanded']:
            tags += [(300, st['name']), (3, st['block']), (4, st.get('lines') or ''), (42, float(st.get('spacing') or 0.0))]
        root.add_xrecord(f'F{i:03d}').reset(tags)
        y = base_y + ymin - 3.0 - gap
    msp.add_mtext('SSS DYNAMIC FAMILY SOURCE  ·  APPLOAD SSS-DYNBUILD.LSP, RUN SSSDYNTEST (ONE FAMILY) OR SSSDYNBUILD '
                  '(ALL), SAVE, UPLOAD THIS DRAWING', dxfattribs={'layer': REVIEW, 'char_height': 2.4,
                                                                 'insert': (0, 8.0), 'attachment_point': 7})
    std.zoom(doc, margin=0.02)
    out_dxf = work / 'out'
    out_dxf.mkdir()
    doc.saveas(out_dxf / 'SSS-DYNAMIC-SOURCE.dxf')
    return fams, doc, inserts


# ---- conditions and arrays ------------------------------------------------------------------------
COND_SUFFIX = {'PROPOSED': '', 'EXISTING': ' EXISTING', 'REMOVE': ' REMOVE'}
COND_TAG = {'PROPOSED': 'P', 'EXISTING': 'E', 'REMOVE': 'R'}


def outline_of(blk, mode):
    """Existing and removed versions of a filled marking (LADOT Drafting Standards p. 10): the outline only;
    removed draws it dashed. Field frames (NOPLOT) become the plotted outline of a colored field."""
    out = []
    has_outline = any(e.dxftype() in ('LWPOLYLINE', 'POLYLINE', 'LINE', 'ARC', 'CIRCLE', 'SPLINE')
                      and e.dxf.get('layer') != std.NOPLOT for e in blk)
    for e in blk:
        if e.dxftype() == 'HATCH':
            if has_outline:
                continue      # the drawn outline already traces the fill
            for path in ezpath.from_hatch(e):
                pts = [(v.x, v.y) for v in path.flattening(0.02)]
                if len(pts) > 2:
                    out.append(('LWPOLYLINE', pts))
        else:
            out.append(('COPY', e))
    return out


def derive(doc, src, name, mode, units):
    blk = doc.blocks.new(name, base_point=(0, 0))
    blk.block_record.dxf.units = units
    ltype = 'DASHED' if mode == 'REMOVE' else 'BYLAYER'
    lts = 1.0 if units == 2 else 1 / 12
    for kind, e in outline_of(doc.blocks[src], mode):
        if kind == 'LWPOLYLINE':
            ent = blk.add_lwpolyline(e, close=True, dxfattribs={'layer': '0'})
        else:
            ent = e.copy()
            blk.add_entity(ent)
            if ent.dxf.get('layer') == std.NOPLOT:
                ent.dxf.layer = '0'   # a field frame is the outline that plots
        if ent.dxf.is_supported('linetype'):
            ent.dxf.linetype = ltype
            if mode == 'REMOVE':
                ent.dxf.ltscale = lts
        if ent.dxf.is_supported('color'):
            ent.dxf.color = 256
        if ent.dxf.hasattr('true_color'):
            ent.dxf.discard('true_color')
    return name


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def unit_block(doc, name, variant, cond, width=None):
    """The repeating element (bar or dash) as a block; the build routine explodes it once so the array
    and width actions act on plain geometry. A green dash is a wide polyline so its width can stretch."""
    blk = doc.blocks.new(name, base_point=(0, 0))
    blk.block_record.dxf.units = 2
    dashed = {'linetype': 'DASHED', 'ltscale': 1.0} if cond == 'REMOVE' else {}
    for x0, y0, x1, y1 in variant['unit']:
        x1 = width if x1 is None else x1
        pts = rect(x0, y0, x1, y1)
        if variant.get('green'):
            if cond == 'PROPOSED':
                mid = (y0 + y1) / 2
                pl = blk.add_lwpolyline([(x0, mid), (x1, mid)], dxfattribs={'layer': '0', 'const_width': y1 - y0,
                                                                         'color': std.GREEN_ACI})
                pl.dxf.true_color = ezdxf.colors.rgb2int(std.GREEN)
            else:
                blk.add_lwpolyline(pts, close=True, dxfattribs={'layer': '0', **dashed})
        elif cond == 'PROPOSED':
            h = blk.add_hatch(dxfattribs={'layer': '0'})
            h.paths.add_polyline_path(pts, is_closed=True)
            blk.add_lwpolyline(pts, close=True, dxfattribs={'layer': '0'})
        else:
            blk.add_lwpolyline(pts, close=True, dxfattribs={'layer': '0', **dashed})
        if variant.get('edges'):      # the bike lane line segment on each edge of the dash
            for x in (x0, x1):
                blk.add_line((x, y0), (x, y1), dxfattribs={'layer': '0', **dashed})
    return name


def lines_block(doc, name, variant, cond, length):
    """Lines that run the full crosswalk length (basic and ladder): drawn as wide polylines so the
    stretch action moves their far ends; existing and removed versions are outlines."""
    blk = doc.blocks.new(name, base_point=(0, 0))
    blk.block_record.dxf.units = 2
    for x0, y0, _, y1 in variant['lines']:
        if cond == 'PROPOSED':
            mid = (y0 + y1) / 2
            blk.add_lwpolyline([(x0, mid), (length, mid)], dxfattribs={'layer': '0', 'const_width': y1 - y0})
        else:
            extra = {'linetype': 'DASHED', 'ltscale': 1.0} if cond == 'REMOVE' else {}
            blk.add_lwpolyline(rect(x0, y0, length, y1), close=True, dxfattribs={'layer': '0', **extra})
    return name


def expand(doc, f):
    """Visibility states of one block: its conditions (proposed, existing, remove) when it is a marking,
    otherwise its variants (sign directions, new and existing signal symbols)."""
    units = UNITS[f['units']]
    out = []
    if f['kind'] == 'array':
        st = f['states'][0]
        for c in f['conditions']:
            stem = f['name'] + '$' + c
            out.append(dict(name=c, spacing=st.get('spacing') or 0.0,
                            block=unit_block(doc, stem + '$U', st, c, f.get('width')) if st.get('unit') else '',
                            lines=lines_block(doc, stem + '$L', st, c, f['length']) if st.get('lines') else ''))
        return out
    if f.get('conditions'):
        st = f['states'][0]
        for c in f['conditions']:
            block = st['block'] if c == 'PROPOSED' else derive(doc, st['block'], f['name'] + '$' + c, c, units)
            out.append(dict(name=c, block=block))
        return out
    return [dict(name=st['state'], block=st['block']) for st in f['states']]


def review_extents(doc, f, st):
    if f['kind'] != 'array':
        e = bbox.extents(doc.blocks[st['block']])
        return e.extmin.x, e.extmin.y, e.extmax.x, e.extmax.y
    boxes = [bbox.extents(doc.blocks[n]) for n in (st['block'], st['lines']) if n]
    xs0 = min(b.extmin.x for b in boxes)
    ys0 = min(b.extmin.y for b in boxes)
    if f['axis'] == 'x':
        return xs0, ys0, max(f['length'], max(b.extmax.x for b in boxes)), max(b.extmax.y for b in boxes)
    return xs0, ys0, max(b.extmax.x for b in boxes) + 1.0, max(f['length'], max(b.extmax.y for b in boxes))


def place_review(msp, f, st, at, scale):
    """Review copy of one state: the block, or for an array state the unit repeated over the default length."""
    if f['kind'] != 'array':
        msp.add_blockref(st['block'], at, dxfattribs={'layer': '0', 'xscale': scale, 'yscale': scale})
        return 1
    n = 0
    if st['lines']:
        msp.add_blockref(st['lines'], at, dxfattribs={'layer': '0'})
        n += 1
    if st['block']:
        k = 0
        while k * st['spacing'] + st['spacing'] <= f['length'] + 1e-9:
            dx, dy = (k * st['spacing'], 0) if f['axis'] == 'x' else (0, k * st['spacing'])
            msp.add_blockref(st['block'], (at[0] + dx, at[1] + dy), dxfattribs={'layer': '0'})
            k += 1
            n += 1
    return n


def verify(dwg, fams, inserts, work, libredwg, libdxfrw):
    want = {n: None for f in fams for s in f['expanded'] for n in (s['block'], s.get('lines')) if n}
    for reader, cmd in (('libredwg', [str(libredwg / 'dwg2dxf'), '-y', '-o']), ('libdxfrw', None)):
        back = work / f'back.{reader}.dxf'
        if reader == 'libredwg':
            subprocess.run(cmd + [str(back), str(dwg)], check=True, capture_output=True)
        elif libdxfrw:
            subprocess.run([str(libdxfrw), str(dwg), '-o', str(back), '-y'], check=True, capture_output=True)
        else:
            continue
        doc = ezdxf.readfile(back)
        missing = [b for b in want if b not in doc.blocks or not len(doc.blocks[b])]
        if missing:
            raise ValueError(f'{reader}: {len(missing)} state blocks missing or empty, first {missing[0]}')
        n = sum(1 for e in doc.modelspace() if e.dxftype() == 'INSERT')
        if n != inserts:
            raise ValueError(f'{reader}: review sheet has {n} inserts, expected {inserts}')
        nfam = len(doc.rootdict['SSS_DYNAMIC']) if 'SSS_DYNAMIC' in doc.rootdict else -1
        if reader == 'libredwg' and nfam != len(fams):
            raise ValueError(f'{reader}: family list has {nfam} records, expected {len(fams)}')
        print(f'{reader}: {len(want)} state blocks, {n} review inserts read back')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--libredwg', type=Path, required=True)
    ap.add_argument('--libdxfrw', type=Path)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        fams, _, inserts = build(work)
        dwg_dir = work / 'dwg'
        dwg_dir.mkdir()
        oda(work / 'out', dwg_dir, 'DWG')
        dwg = dwg_dir / 'SSS-DYNAMIC-SOURCE.dwg'
        verify(dwg, fams, inserts, work, a.libredwg, a.libdxfrw)
        OUT.write_bytes(dwg.read_bytes())
        print(OUT, f'{OUT.stat().st_size / 1e6:.1f} MB,', len(fams), 'families,', sum(len(f['expanded']) for f in fams), 'visibility states')
