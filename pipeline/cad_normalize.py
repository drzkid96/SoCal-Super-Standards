"""Apply the SSS CAD standard (cad_standard.py) to every published static marking and signal block.

For each AutoCAD 2000 block drawing listed in data/reference/design-blocks.json:
- geometry on layer 0 with color, linetype and lineweight ByLayer (state layers E-, P-, R-, A- kept);
  Defpoints and non-plotting helpers move to NOPLOT (plot off);
- green and red field hatches get the guidance RGB color (and index fallback) and a NOPLOT frame;
  their old plotting outlines move to NOPLOT;
- markings get their placement base point (cad_standard.placement); the rule is written to the catalog;
- the drawing is rewritten (one insert at 0,0 on the family layer, code label under it) as AutoCAD 2018
  (true color needs 2004 or later; 2018 matches the dynamic blocks and the Westwood sources), encoded with
  ODA File Converter in one batch and read back by LibreDWG and libdxfrw before it replaces the published file.
Idempotent. Dynamic files (with ACAD_ENHANCEDBLOCK data) are left to the dynamic build.

  python3 pipeline/cad_normalize.py --libredwg <dir> --libdxfrw <libdxfrw dwg2dxf> [--only CODE ...]
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox, path as ezpath
from ezdxf.addons import Importer

import cad_standard as std
import shutil

from sign_cells import STYLES

CATALOG = Path('data/reference/design-blocks.json')
STATE = re.compile(r'^[EPRA]-(SIGNAL|SITE|SIGN|PMARK)$')
FIELD_ACI = {3: (std.GREEN, std.GREEN_ACI), std.GREEN_ACI: (std.GREEN, std.GREEN_ACI),
             std.RED_ACI: (std.RED, std.RED_ACI)}
GREENISH = {3, std.GREEN_ACI}
SKIP = {'ATTDEF'}   # libdxfrw does not read attribute definitions; checked by LibreDWG's own count


def rgb_of(e):
    tc = e.dxf.get('true_color')
    return ezdxf.colors.int2rgb(tc) if tc is not None else None


def is_field(e):
    """A colored background field: green or red pavement, or the blue ISA field."""
    rgb = rgb_of(e)
    return e.dxftype() == 'HATCH' and (e.dxf.get('color') in (3, 5, std.GREEN_ACI, std.RED_ACI)
                                       or rgb in (std.GREEN, std.RED))


def frame_points(hatch):
    loops = []
    for p in ezpath.from_hatch(hatch):
        pts = [(v.x, v.y) for v in p.flattening(0.01)]
        if len(pts) > 2:
            loops.append(pts)
    return loops


def normalize_block(doc, blk):
    for e in list(blk):
        layer = e.dxf.get('layer', '0')
        if layer.upper() in ('DEFPOINTS', std.NOPLOT):
            e.dxf.layer = std.NOPLOT
        elif not STATE.match(layer):
            e.dxf.layer = '0'
        if e.dxf.is_supported('lineweight'):
            e.dxf.lineweight = -1
        if e.dxf.is_supported('linetype') and e.dxf.get('linetype', 'BYLAYER').upper() in ('BYBLOCK', 'CONTINUOUS'):
            e.dxf.linetype = 'BYLAYER'
        color = e.dxf.get('color', 256)
        if e.dxf.layer == std.NOPLOT:
            e.dxf.color = 256
            continue
        if e.dxftype() == 'HATCH' and color in FIELD_ACI:
            rgb, aci = FIELD_ACI[color]
            e.dxf.color = aci
            e.dxf.true_color = ezdxf.colors.rgb2int(rgb)
        elif e.dxftype() != 'HATCH' and color in GREENISH:
            e.dxf.layer = std.NOPLOT    # a field's outline: keep it for selection, never plot it
            e.dxf.color = 256
            if e.dxf.hasattr('true_color'):
                e.dxf.discard('true_color')
        elif color in (0, 7):
            e.dxf.color = 256
    have = set()
    for f in [e for e in blk if e.dxf.layer == std.NOPLOT and e.dxftype() == 'LWPOLYLINE']:
        b = bbox.extents([f])
        key = tuple(round(v, 3) for v in (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
        if key in have:
            blk.delete_entity(f)        # one frame per field is enough
        else:
            have.add(key)
    for h in [e for e in blk if is_field(e)]:
        for loop in frame_points(h):
            xs, ys = [p[0] for p in loop], [p[1] for p in loop]
            key = tuple(round(v, 3) for v in (min(xs), min(ys), max(xs), max(ys)))
            if key not in have:
                blk.add_lwpolyline(loop, close=True, dxfattribs={'layer': std.NOPLOT, 'color': 256})
                have.add(key)


def rebase(blk, rule):
    (xmode, xval), (ymode, yval), _ = rule
    ext = bbox.extents([e for e in blk if e.dxf.get('layer') != std.NOPLOT] or list(blk))
    if xmode == 'center':
        dx = xval - (ext.extmin.x + ext.extmax.x) / 2
    elif xmode == 'min':
        dx = xval - ext.extmin.x
    else:       # 'shaft': the arrow tail's middle goes to the lane center
        dx = xval - shaft_of(blk)
    dy = (yval - ext.extmax.y) if ymode == 'top' else (yval - ext.extmin.y)
    if abs(dx) > 1e-9 or abs(dy) > 1e-9:
        for e in blk:
            e.translate(dx, dy, 0)
    return dx, dy


def shaft_of(blk):
    """The arrow shaft center: the midpoint of the narrowest vertical run at the tail (lowest 10 percent)."""
    ext = bbox.extents(list(blk))
    low = ext.extmin.y + 0.1 * (ext.extmax.y - ext.extmin.y)
    xs = []
    for e in blk:
        if e.dxftype() == 'LWPOLYLINE':
            xs += [p[0] for p in e.get_points('xy') if p[1] <= low + 1e-6]
    return (min(xs) + max(xs)) / 2 if xs else (ext.extmin.x + ext.extmax.x) / 2


def new_document():
    doc = ezdxf.new('R2018', setup=False)
    doc.header['$MEASUREMENT'] = 0
    doc.header['$TEXTSTYLE'] = 'ROMANS'
    doc.header['$DIMSTYLE'] = 'Standard'
    for name, font in STYLES.items():
        if name not in doc.styles:
            doc.styles.new(name, dxfattribs={'font': font, 'width': 1.0})
    return doc


def prepare(src, name, dxf_out, rule):
    """Normalized DXF for one block drawing; returns (block names, entity count, insert layer)."""
    insert = src.modelspace().query('INSERT').first
    label = src.modelspace().query('MTEXT').first
    doc = new_document()
    doc.units = src.units or 2
    doc.header['$INSUNITS'] = src.header.get('$INSUNITS', 2)
    for key in ('$MEASUREMENT', '$LUNITS', '$LUPREC'):
        if key in src.header:
            doc.header[key] = src.header[key]
    imp = Importer(src, doc)
    imp.import_tables('linetypes')
    imp.import_block(name)
    imp.finalize()
    if std.NOPLOT not in doc.layers:
        doc.layers.new(std.NOPLOT, dxfattribs={'color': 8, 'plot': 0})
    else:
        doc.layers.get(std.NOPLOT).dxf.plot = 0
    seen = set()

    def walk(n):
        if n in seen:
            return
        seen.add(n)
        normalize_block(doc, doc.blocks[n])
        for e in doc.blocks[n].query('INSERT'):
            walk(e.dxf.name)
    walk(name)
    moved = rebase(doc.blocks[name], rule) if rule else (0, 0)
    ins_layer = insert.dxf.layer
    for lay, color in ((ins_layer, src.layers.get(ins_layer).dxf.color if ins_layer in src.layers else 7),
                       (ins_layer + '-TEXT', 7)):
        if lay not in doc.layers:
            doc.layers.new(lay, dxfattribs={'color': abs(color)})
    for layer in list(doc.layers):
        n = layer.dxf.name
        if n not in ('0', 'Defpoints', std.NOPLOT, ins_layer, ins_layer + '-TEXT') and not any(
                e.dxf.get('layer') == n for b in doc.blocks for e in b):
            doc.layers.remove(n)
    msp = doc.modelspace()
    msp.add_blockref(name, (0, 0), dxfattribs={'layer': ins_layer})
    ext = bbox.extents(doc.blocks[name])
    height = label.dxf.char_height if label else max(0.1, 0.06 * max(ext.size.x, ext.size.y))
    msp.add_mtext(name, dxfattribs={'layer': ins_layer + '-TEXT', 'style': 'ROMANS', 'char_height': height,
                                    'insert': ((ext.extmin.x + ext.extmax.x) / 2, ext.extmin.y - height),
                                    'attachment_point': 2})
    doc.saveas(dxf_out)
    return seen, sum(1 for n in seen for e in doc.blocks[n] if e.dxftype() not in SKIP), moved


def oda(src_dir, out_dir):
    cmd = ['ODAFileConverter', str(src_dir), str(out_dir), 'ACAD2018', 'DWG', '0', '1', '*.dxf']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=3600)


def verify(dwg, seen, count, work, libredwg, libdxfrw):
    for reader in ('libredwg', 'libdxfrw'):
        back = work / f'{dwg.stem}.{reader}.dxf'
        back.unlink(missing_ok=True)
        if reader == 'libredwg':
            subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(back), str(dwg)], capture_output=True, check=True)
        elif libdxfrw:
            subprocess.run([str(libdxfrw), str(dwg), '-o', str(back), '-y'], capture_output=True, check=True)
        else:
            continue
        read = ezdxf.readfile(back)
        if sorted(e.dxftype() for e in read.modelspace()) != ['INSERT', 'MTEXT']:
            raise ValueError(f'{dwg.stem}: {reader} read-back model space differs')
        got = sum(1 for n in seen if n in read.blocks for e in read.blocks[n] if e.dxftype() not in SKIP)
        if got != count:
            raise ValueError(f'{dwg.stem}: {reader} read-back has {got} block entities, expected {count}')


def build(libredwg, libdxfrw=None, only=()):
    catalog = json.loads(CATALOG.read_text())
    done = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        stage, out = work / 'dxf', work / 'dwg'
        stage.mkdir(), out.mkdir()
        jobs = []
        for route, section in catalog.items():
            for row in section['blocks']:
                if only and row['code'] not in only:
                    continue
                path = Path('public/downloads') / route / row['file']
                src_dxf = work / 'src.dxf'
                src_dxf.unlink(missing_ok=True)
                subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(src_dxf), str(path)], capture_output=True, check=True)
                src = ezdxf.readfile(src_dxf)
                name = src.modelspace().query('INSERT').first.dxf.name
                br = src.blocks[name].block_record
                if br.has_extension_dict and 'ACAD_ENHANCEDBLOCK' in br.get_extension_dict():
                    continue    # dynamic: built by the dynamic block routine
                rule = std.placement(row['code'], row['group']) if route == 'markings/cad' else None
                seen, count, _ = prepare(src, name, stage / (path.stem + '.dxf'), rule)
                jobs.append((path, seen, count))
                if rule:
                    row['placement'] = rule[2]
                else:
                    row.pop('placement', None)
        oda(stage, out)
        for path, seen, count in jobs:
            dwg = out / (path.stem + '.dwg')
            verify(dwg, seen, count, work, libredwg, libdxfrw)
            path.write_bytes(dwg.read_bytes())
            done += 1
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')
    return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--libredwg', type=Path, required=True)
    ap.add_argument('--libdxfrw', type=Path)
    ap.add_argument('--only', nargs='*', default=())
    a = ap.parse_args()
    print(build(a.libredwg, a.libdxfrw, set(a.only)), 'blocks normalized')
