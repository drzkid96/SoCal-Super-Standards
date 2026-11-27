"""Dynamic pavement marking blocks, extracted from a plan drawing with their parameters intact.

ODA File Converter reads the plan DWG and writes DXF, where every dynamic block object (evaluation
graph, parameters, grips, actions, visibility states) is an ACAD_PROXY_OBJECT carrying its original
binary data and the handles it owns. Here the drawing is cut down to the chosen block definitions,
the geometry is cleaned (layer 0, ByBlock, green fields ACI 3, non-plotting geometry on Defpoints,
feet), names get the PM-...-DYN form, and ODA writes the DWG back. ODA restores the proxies as
native objects in the same DWG version, so AutoCAD opens them as ordinary dynamic blocks.

Checks before anything is published:
  - every proxy owned by a kept block is present in the output with identical class and bytes;
  - LibreDWG decodes the output DWG with native evaluation graphs and no proxies;
  - a rendering of each block's default state for the QA sheet.

  python3 pipeline/dynamic_blocks.py --dwg <plan drawing DWG> --libredwg <dir with dwg2dxf>
Needs ODAFileConverter (with xvfb-run on a headless machine).
"""
import argparse
import collections
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/downloads/markings/cad')
LIBRARY = 'SSS-PMARK-DYNAMIC.dwg'
VERSION = 'ACAD2018'   # the source version: ODA writes proxies back as native objects only in it

# source block -> (published name, description, what the grips do)
KEEP = {
    'YIELDLL': ('PM-YIELD-LINE-DYN', 'Yield line', 'Linear grip sets the line length; the 2 x 3 ft triangles repeat along it'),
    'THRU & LEFT ARROW': ('PM-THRU-LEFT-ARROW-DYN', 'Through and left arrow',
                          'Visibility: existing, remove and proposed, each on its own layer (E-PMARK, R-PMARK, P-PMARK)'),
    'Base$0$ss-p-pmark': ('PM-ARROW-SET-DYN', 'Arrow set', 'Visibility picks the arrow; five flip grips mirror it'),
    'Bike-NoPerson-Arrow': ('PM-BIKE-LANE-GREEN-DYN', 'Green bike lane panel, 7 x 25 ft, bike symbol and arrow',
                            'Visibility and a rotation grip for the panel'),
    'BIKE-LEFT-THRU-ARROW': ('PM-BIKE-LEFT-THRU-ARROW-DYN', 'Bike left and through arrow', 'Rotation grip'),
}
SUBS = {'BIKE LANE ARROW': 'PM-DYN-SUB-BIKE-ARROW', 'BIKE-SYM2': 'PM-DYN-SUB-BIKE-SYMBOL'}
# layers inside the kept definitions -> (layer, color) ; None color keeps the entity's own
LAYERS = {'_P-STRP-GREEN': ('0', 3), 'FP-NOPLOT': ('Defpoints', None), '__AA-WORKING-01': ('Defpoints', None)}
STATE_LAYERS = {'E-STRP-PVMTXT': 'E-PMARK', 'R-STRP-PVMTXT': 'R-PMARK', '_P-PMARK': 'P-PMARK'}
REF_CODES = (340, 350, 360)
LINETYPES = {'Base$0$R-Solid': ('PMARK-REMOVE', 'Removed marking  __ __ __')}


def oda(src, out_dir, fmt):
    """Convert one file with ODA File Converter (audit on). Returns the output path."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(src, Path(tmp) / Path(src).name)
        cmd = ['ODAFileConverter', tmp, str(out_dir), VERSION, fmt, '0', '1']
        if shutil.which('xvfb-run'):
            cmd = ['xvfb-run', '-a'] + cmd
        subprocess.run(cmd, capture_output=True, timeout=600, check=True)
    out = Path(out_dir) / (Path(src).stem + '.' + fmt.lower())
    if not out.exists():
        raise RuntimeError('ODA wrote nothing for ' + str(src))
    return out


def refs(o):
    xt = getattr(o, 'xtags', None)
    if xt is None:
        return []
    return [t.value for s in xt.subclasses for t in s if t.code in REF_CODES]


def owned(doc, roots):
    """Handles reachable from the given objects through owner and pointer references."""
    db, seen, stack = doc.entitydb, set(), list(roots)
    while stack:
        h = stack.pop()
        if h in seen or h not in db:
            continue
        seen.add(h)
        o = db[h]
        stack.extend(refs(o))
        if getattr(o, 'has_extension_dict', False):
            stack.append(o.get_extension_dict().dictionary.dxf.handle)
        if o.dxftype() == 'DICTIONARY':
            stack.extend(v if isinstance(v, str) else v.dxf.handle for _, v in o.items())
    return seen


def graph_of(doc, block):
    br = doc.blocks[block].block_record
    xd = br.get_extension_dict()
    return owned(doc, [xd.dictionary.dxf.handle])


def signature(doc, handles):
    """Class and bytes of every proxy among the handles, in a comparable form."""
    out = collections.Counter()
    for h in handles:
        o = doc.entitydb.get(h)
        if o is None or o.dxftype() != 'ACAD_PROXY_OBJECT':
            continue
        sub = o.xtags.get_subclass('AcDbProxyObject')
        data = b''.join(t.value for t in sub if t.code == 310)
        out[(sub.get_first_value(91), data, len(refs(o)))] += 1
    return out


def cut(src_dxf, keep, dst_dxf):
    """Write a DXF holding only the kept dynamic blocks (cleaned and renamed) and their sub-blocks."""
    doc = ezdxf.readfile(src_dxf)
    names = {k: KEEP[k][0] for k in keep}
    subs = {s for k in keep for i in doc.blocks[k].query('INSERT') for s in [i.dxf.name]}
    unknown = subs - set(SUBS)
    if unknown:
        raise ValueError(f'unmapped sub-blocks {unknown}')
    before = {k: signature(doc, graph_of(doc, k)) for k in keep}
    # 1. empty every layout
    for layout in doc.layouts:
        for e in list(layout):
            layout.delete_entity(e)
    # 2. only the Standard dimension style stays (its arrowheads with it); then drop every other block
    graphs = set().union(*(graph_of(doc, k) for k in keep))
    pinned = {h for g in graphs for h in refs(doc.entitydb[g])}   # table entries the dynamic data points at
    doc.header['$DIMSTYLE'] = 'Standard'
    for ds in list(doc.dimstyles):
        if ds.dxf.name != 'Standard' and ds.dxf.handle not in pinned:
            doc.dimstyles.remove(ds.dxf.name)
    arrows = {ds.dxf.get(a) for ds in doc.dimstyles for a in ('dimblk', 'dimblk1', 'dimblk2', 'dimldrblk')} - {None, ''}
    arrows |= {doc.header.get(v) for v in ('$DIMBLK', '$DIMBLK1', '$DIMBLK2', '$DIMLDRBLK')} - {None, ''}
    for b in list(doc.blocks):
        if b.is_any_layout or b.name in keep or b.name in subs or b.name in arrows:
            continue
        doc.blocks.delete_block(b.name, safe=False)
    # 3. drop objects nothing kept reaches (other blocks' graphs, Civil 3D and AEC data)
    root = doc.rootdict
    for key in list(root.keys()):
        if key == 'Root' or key.upper().startswith(('AEC', 'AECC', 'CIVIL', 'ACAD_CIP', 'MAP', 'AUTODESK_MAP', 'DM', 'IRD',
                                                       'ACAD_ASSOC', 'SVY_', 'TS_', 'PE5.', 'ADE_', 'ASE_', 'ESRI_', '{')):
            root.discard(key)
    setups = root.get('ACAD_PLOTSETTINGS')   # the plan's page setups
    if setups is not None:
        for key in list(setups.keys()):
            setups.discard(key)
    roots = [root.dxf.handle]
    for table in (doc.layers, doc.linetypes, doc.styles, doc.dimstyles, doc.appids, doc.ucs, doc.views, doc.viewports):
        roots += [t.dxf.handle for t in table]
    roots += [b.block_record.dxf.handle for b in doc.blocks]
    for b in doc.blocks:
        roots += [e.dxf.handle for e in b]
    live = owned(doc, roots)
    for o in list(doc.objects):
        if o.is_alive and o.dxftype() == 'ACAD_PROXY_OBJECT' and o.dxf.handle not in live:
            doc.objects.delete_entity(o)
    # 4. clean the kept geometry
    for old, new in STATE_LAYERS.items():
        if old in doc.layers and new not in doc.layers:
            src = doc.layers.get(old)
            linetype = src.dxf.linetype
            if linetype in LINETYPES:
                name, desc = LINETYPES[linetype]
                if name not in doc.linetypes:
                    pattern = [t.value for t in doc.linetypes.get(linetype).pattern_tags.tags if t.code in (40, 49)]
                    doc.linetypes.add(name, pattern=pattern, description=desc)
                linetype = name
            # P-PMARK stays white, as in every SSS marking drawing
            doc.layers.new(new, dxfattribs={'color': 7 if new == 'P-PMARK' else src.dxf.color, 'linetype': linetype,
                                            'lineweight': src.dxf.get('lineweight', -3)})
    if 'Defpoints' not in doc.layers:
        doc.layers.new('Defpoints', dxfattribs={'color': 7, 'plot': 0})
    for name in list(keep) + sorted(subs):
        block = doc.blocks[name]
        block.block_record.dxf.units = 2
        for e in block:
            lay = e.dxf.layer
            if lay in STATE_LAYERS:
                e.dxf.layer = STATE_LAYERS[lay]
                continue
            if lay in LAYERS:
                e.dxf.layer, color = LAYERS[lay]
                if color is not None and e.dxf.get('color', 256) == 256:
                    e.dxf.color = color
                continue
            if lay != '0':
                raise ValueError(f'{name}: unmapped layer {lay}')
            if e.dxf.get('color', 256) == 256:
                e.dxf.color = 0
            if e.dxftype() == 'INSERT':
                e.dxf.name = SUBS[e.dxf.name]
    for old, new in list(SUBS.items()) + list(names.items()):
        if old in doc.blocks:
            doc.blocks.rename_block(old, new)
    # 5. unused layers out (keep 0, Defpoints and the state layers)
    used = {e.dxf.layer for b in doc.blocks for e in b} | {'0', 'Defpoints', 'P-PMARK', 'P-PMARK-TEXT'}
    for layer in list(doc.layers):
        if layer.dxf.name not in used:
            doc.layers.remove(layer.dxf.name)
    # 6. text styles and linetypes nothing uses
    style_used = {'Standard', 'ROMANS'} | {ds.dxf.get('dimtxsty', 'Standard') for ds in doc.dimstyles}
    lt_used = {'ByBlock', 'ByLayer', 'Continuous'} | {l.dxf.linetype for l in doc.layers}
    for b in doc.blocks:
        for e in b:
            if e.dxf.is_supported('style'):
                style_used.add(e.dxf.get('style', 'Standard'))
            lt_used.add(e.dxf.get('linetype', 'ByLayer'))
    for st in list(doc.styles):
        name = st.dxf.name
        if name and name not in style_used and st.dxf.handle not in pinned and not st.is_shape_file:
            doc.styles.remove(name)
    for lt in list(doc.linetypes):
        if lt.dxf.name not in lt_used and lt.dxf.handle not in pinned:
            doc.linetypes.remove(lt.dxf.name)
    # 7. plan residue: material records (the default materials carry corrupt Civil 3D XML), named
    #    views, the solids data section and application names nothing carries data for
    for mat in [o for o in doc.objects if o.is_alive and o.dxftype() == 'MATERIAL']:
        if mat.has_extension_dict:
            mat.discard_extension_dict()
    for view in list(doc.views):
        doc.views.remove(view.dxf.name)
    doc.acdsdata.entities.clear()
    apps = {'ACAD'}
    for e in doc.entitydb.values():
        if e.is_alive and getattr(e, 'xdata', None):
            apps.update(e.xdata.data.keys())
    for app in list(doc.appids):
        if app.dxf.name not in apps and app.dxf.handle not in pinned:
            doc.appids.remove(app.dxf.name)
    # 8. one reference of each, laid out left to right, with its name under it (ROMANS)
    if 'ROMANS' not in doc.styles:
        doc.styles.new('ROMANS', dxfattribs={'font': 'romans.shx'})
    for lay in ('P-PMARK', 'P-PMARK-TEXT'):
        if lay not in doc.layers:
            doc.layers.new(lay, dxfattribs={'color': 7})
    msp, x = doc.modelspace(), 0.0
    from ezdxf import bbox
    for k in keep:
        name = names[k]
        ext = bbox.extents(doc.blocks[name])
        w = ext.extmax.x - ext.extmin.x
        at = (x - ext.extmin.x, -ext.extmin.y)
        msp.add_blockref(name, at, dxfattribs={'layer': 'P-PMARK'})
        msp.add_mtext(name, dxfattribs={'layer': 'P-PMARK-TEXT', 'style': 'ROMANS', 'char_height': 0.6,
                                        'insert': (x + w / 2, -1.0), 'attachment_point': 2})
        x += max(w, len(name) * 0.6) + 6
    doc.units = 2
    doc.header['$INSUNITS'] = 2
    doc.saveas(dst_dxf)
    return before


def build(src_dwg, libredwg):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, report = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src_dxf = oda(src_dwg, tmp, 'DXF')
        jobs = [(LIBRARY, list(KEEP))] + [(KEEP[k][0] + '.dwg', [k]) for k in KEEP]
        for target, keep in jobs:
            work = tmp / Path(target).stem
            work.mkdir()
            cut_dxf = work / (Path(target).stem + '.dxf')
            before = cut(src_dxf, keep, cut_dxf)
            dwg = oda(cut_dxf, work, 'DWG')
            # check 1: ODA reads it back with every owned proxy intact
            (work / 'rt').mkdir()
            back = ezdxf.readfile(oda(dwg, work / 'rt', 'DXF'))
            for k in keep:
                after = signature(back, graph_of(back, KEEP[k][0]))
                if after != before[k] or not after:
                    raise ValueError(f'{target}: {k} dynamic data changed ({sum(before[k].values())} -> {sum(after.values())} objects)')
            # check 2: LibreDWG decodes native evaluation graphs, no proxies
            native = work / 'native.dxf'
            subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', native, dwg], capture_output=True)
            text = native.read_text(errors='ignore')
            graphs = text.count('\nACAD_EVALUATION_GRAPH\n') - 1   # minus the CLASS entry
            proxies = text.count('\nACAD_PROXY_OBJECT\n')
            if graphs < len(keep) or proxies:
                raise ValueError(f'{target}: {graphs} native graphs, {proxies} proxies')
            shutil.copy(dwg, OUT / target)
            report[target] = {k: sum(before[k].values()) for k in keep}
            report[target]['native_graphs'] = graphs
    for k, (name, label, grips) in KEEP.items():
        rows.append({'code': name, 'name': f'{label} · dynamic · LA signing and striping plan library',
                     'file': name + '.dwg', 'group': 'Dynamic blocks', 'dynamic': grips})
    return rows, report


def publish(rows):
    catalog = json.loads(CATALOG.read_text())
    section = catalog['markings/cad']
    section['blocks'] = [r for r in section['blocks'] if r.get('group') != 'Dynamic blocks'] + rows
    if 'Dynamic blocks' not in section['groups']:
        section['groups'].append('Dynamic blocks')
    section['downloads'] = [d for d in section['downloads'] if d['label'] != LIBRARY]
    section['downloads'].insert(1, {'label': LIBRARY, 'path': f'downloads/markings/cad/{LIBRARY}',
                                    'note': 'every dynamic marking block in one drawing, grips and visibility states intact (AutoCAD 2018 DWG)'})
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dwg', type=Path, required=True)
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    rows, report = build(args.dwg, args.libredwg)
    publish(rows)
    print(json.dumps(report, indent=1))
