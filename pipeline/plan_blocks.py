"""Plan-library blocks from LA plan sets: dynamic and static, cleaned, merged and named to one standard.

Sources (an LA corridor plan set): the signing and striping plan (pavement markings), the
traffic signal plan (signal equipment, detection, lighting, sign posts, site items) and the
topographic survey (existing-feature symbols). ODA File Converter writes each source as DXF, where
every dynamic block object is an ACAD_PROXY_OBJECT that keeps its bytes and the handles it owns. The
drawing is cut to the chosen definitions, cleaned, renamed, and ODA writes it back: AutoCAD 2018 when
the file holds dynamic data (ODA restores the proxies as native objects only in the source version),
AutoCAD 2000 otherwise.

Names:  CT-<sheet>-<item>  official Caltrans geometry (other pipelines)
        PM- pavement markings, SG- signals, SN- signs, SV- survey and site features, from plan sets;
        -DYN marks a dynamic block; sub-blocks are <prefix>-SUB-<item>.
Layers inside blocks: 0 ByBlock; existing / proposed / remove / abandon states on E-, P-, R-, A-
        plus PMARK, SIGNAL, SIGN or SITE (P- layers white); non-plotting geometry on Defpoints.
Merging: identical definitions (geometry, nested blocks and dynamic data) across sources publish once,
        under the first source's name; a same-named block that differs keeps the first source's.

Checks: each kept dynamic block's proxies come back with identical class and bytes; LibreDWG decodes
native evaluation graphs with no proxies; every file opens as block references only.

  python3 pipeline/plan_blocks.py --source westwood-ss=<S&S DWG> --source westwood-ts=<signal DWG>
                                  --source westwood-survey=<survey DWG> --libredwg <dir>
"""
import argparse
import collections
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox

CATALOG = Path('data/reference/design-blocks.json')
REF_CODES = (340, 350, 360)

# source -> rows of (source block, standard name, label, group)
SOURCES = {
    'westwood-ss': [
        ('YIELDLL', 'PM-YIELD-LINE-DYN', 'Yield line; linear grip sets the length, triangles repeat', 'Dynamic blocks'),
        ('THRU & LEFT ARROW', 'PM-THRU-LEFT-ARROW-DYN', 'Through and left arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('Base$0$ss-p-pmark', 'PM-ARROW-SET-DYN', 'Arrow set; visibility picks the arrow, five flip grips', 'Dynamic blocks'),
        ('Bike-NoPerson-Arrow', 'PM-BIKE-LANE-GREEN-DYN', 'Green bike lane panel, 7 x 25 ft, bike symbol and arrow; rotation', 'Dynamic blocks'),
        ('BIKE-LEFT-THRU-ARROW', 'PM-BIKE-LEFT-THRU-ARROW-DYN', 'Bike left and through arrow; rotation', 'Dynamic blocks'),
        ('AA-BIKE', 'PM-BIKE-LANE-GREEN-5FT-DYN', 'Green bike lane panels, 5 x 50 ft, two bike symbols and arrows', 'Dynamic blocks'),
        ("10' Left Turn Calming", 'PM-LEFT-TURN-CALMING-10FT', 'Left turn calming curb, 10 ft', 'Raised elements'),
        ("3' Left Turn Calming", 'PM-LEFT-TURN-CALMING-3FT', 'Left turn calming bump, 3 ft', 'Raised elements'),
        ('Curb-Stop', 'PM-CURB-STOP-DYN', 'Curb stop (wheel stop), 6 ft', 'Raised elements'),
    ],
    'westwood-ts': [
        ('LEFT ARROW', 'PM-LEFT-ARROW-DYN', 'Left turn arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('RIGHT ARROW', 'PM-RIGHT-ARROW-DYN', 'Right turn arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('LEFT RIGHT ARROW', 'PM-LEFT-RIGHT-ARROW-DYN', 'Left and right arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('THRU ARROW', 'PM-THRU-ARROW-DYN', 'Through arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('THRU & LEFT ARROW', 'PM-THRU-LEFT-ARROW-DYN', 'Through and left arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('THRU & RIGHT ARROW', 'PM-THRU-RIGHT-ARROW-DYN', 'Through and right arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ('MERGE ARROW', 'PM-MERGE-ARROW-DYN', 'Lane reduction (merge) arrow; existing, remove and proposed states', 'Dynamic blocks'),
        ("15' WIDE LANE DEFENDER", 'PM-LANE-DEFENDER-15FT', 'Lane defender, 15 ft', 'Raised elements'),
        ('STANDARD', 'SG-STANDARD-DYN', 'Signal standard', 'Poles and mast arms'),
        ('STANDARD T3', 'SG-STANDARD-T3-DYN', 'Signal standard, T3', 'Poles and mast arms'),
        ('STANDARD T5', 'SG-STANDARD-T5-DYN', 'Signal standard, T5', 'Poles and mast arms'),
        ('PUSH BUTTON STANDARD', 'SG-PUSH-BUTTON-POST-DYN', 'Push button post', 'Poles and mast arms'),
        ('PED PUSH BUTTON', 'SG-PED-PUSH-BUTTON-DYN', 'Pedestrian push button', 'Poles and mast arms'),
        ('VEHICLE HEAD - STANDARD', 'SG-VEHICLE-HEAD-RYG-DYN', 'Vehicle signal head, red, yellow and green', 'Signal heads'),
        ('VEHICLE HEAD - RYG ARROWS', 'SG-VEHICLE-HEAD-RYG-ARROWS-DYN', 'Vehicle signal head, red, yellow and green arrows', 'Signal heads'),
        ('VEHICLE HEAD - R_YG ARROWS', 'SG-VEHICLE-HEAD-R-YG-ARROWS-DYN', 'Vehicle signal head, red ball with yellow and green arrows', 'Signal heads'),
        ('VEHICLE HEAD - GN UP ARROW', 'SG-VEHICLE-HEAD-GREEN-UP-ARROW-DYN', 'Vehicle signal head with green up arrow', 'Signal heads'),
        ('YG ARROWS', 'SG-YG-ARROW-SECTIONS-DYN', 'Yellow and green arrow sections', 'Signal heads'),
        ('GREEN ARROW', 'SG-GREEN-ARROW-SECTION-DYN', 'Green arrow section', 'Signal heads'),
        ('RYG LOUVERED', 'SG-RYG-LOUVERED-DYN', 'Louvered red, yellow and green head', 'Signal heads'),
        ('LONG VISOR', 'SG-LONG-VISOR-DYN', 'Long visor', 'Signal heads'),
        ('BEVEL VISOR', 'SG-BEVEL-VISOR-DYN', 'Bevel visor', 'Signal heads'),
        ('PEDESTRIAN HEAD', 'SG-PED-HEAD-DYN', 'Pedestrian signal head', 'Signal heads'),
        ('FLASHING BEACON', 'SG-FLASHING-BEACON-DYN', 'Flashing beacon', 'Signal heads'),
        ('6\' LOOP', 'SG-LOOP-6FT-DYN', 'Loop detector, 6 ft round', 'Detection'),
        ('6\' LOOP PAIR', 'SG-LOOP-6FT-PAIR-DYN', 'Loop detectors, 6 ft round pair', 'Detection'),
        ('6\' OCTAGON LOOP', 'SG-LOOP-6FT-OCTAGON-DYN', 'Loop detector, 6 ft octagon', 'Detection'),
        ('6\' OCTAGON LOOP PAIR', 'SG-LOOP-6FT-OCTAGON-PAIR-DYN', 'Loop detectors, 6 ft octagon pair', 'Detection'),
        ('6\' NON BIKE LOOP PAIR', 'SG-LOOP-6FT-NON-BIKE-PAIR-DYN', 'Loop detectors, 6 ft pair, not bicycle', 'Detection'),
        ('6\' COMBO BIKE LOOP', 'SG-LOOP-6FT-COMBO-BIKE-DYN', 'Loop detector, 6 ft combination bicycle', 'Detection'),
        ('3\' BIKE LOOP', 'SG-LOOP-3FT-BIKE-DYN', 'Bicycle loop detector, 3 ft', 'Detection'),
        ('3\' BIKE LOOP PAIR', 'SG-LOOP-3FT-BIKE-PAIR-DYN', 'Bicycle loop detectors, 3 ft pair', 'Detection'),
        ('8\'x6\' OCTAGONAL LOOP', 'SG-LOOP-8X6FT-OCTAGON-DYN', 'Loop detector, 8 x 6 ft octagon', 'Detection'),
        ('TRANSIT LOOP', 'SG-LOOP-TRANSIT-DYN', 'Transit loop detector', 'Detection'),
        ('VIDEO CAMERA', 'SG-VIDEO-CAMERA-DYN', 'Video camera', 'Detection'),
        ('VIDEO CAMERA DETECTOR', 'SG-VIDEO-DETECTOR-DYN', 'Video detection camera', 'Detection'),
        ('OVERHEAD DETECTOR', 'SG-OVERHEAD-DETECTOR-DYN', 'Overhead detector', 'Detection'),
        ('OPTICAL DETECTOR', 'SG-OPTICAL-DETECTOR-DYN', 'Optical (emergency vehicle) detector', 'Detection'),
        ('PHOTO ENFORCEMENT CAMERA', 'SG-PHOTO-ENFORCEMENT-CAMERA-DYN', 'Photo enforcement camera', 'Detection'),
        ('SIGNAL CONTROLLER', 'SG-CONTROLLER-DYN', 'Controller cabinet', 'Cabinets and conduit'),
        ('COMMUNICATION CABINET', 'SG-COMMUNICATION-CABINET-DYN', 'Communication cabinet', 'Cabinets and conduit'),
        ('VIDEO CAMERA CABINET', 'SG-VIDEO-CAMERA-CABINET-DYN', 'Video camera cabinet', 'Cabinets and conduit'),
        ('FIBER SPLICE VAULT', 'SG-FIBER-SPLICE-VAULT-DYN', 'Fiber splice vault', 'Cabinets and conduit'),
        ('PULLBOX 2', 'SG-PULL-BOX-2-DYN', 'Pull box, symbol 2', 'Cabinets and conduit'),
        ('PULLBOX 3', 'SG-PULL-BOX-3-DYN', 'Pull box, symbol 3', 'Cabinets and conduit'),
        ('CNDBRK', 'SG-CONDUIT-BREAK', 'Conduit break', 'Cabinets and conduit'),
        ('LUMINAIRE', 'SG-LUMINAIRE-DYN', 'Luminaire', 'Lighting'),
        ('LUMINAIRE W-ARM', 'SG-LUMINAIRE-ARM-DYN', 'Luminaire with arm', 'Lighting'),
        ('LUMINAIRE-NO-ARM', 'SG-LUMINAIRE-NO-ARM-E', 'Existing luminaire without arm', 'Lighting'),
        # ELECT-E (existing electrolier) repeats SG-LUMINAIRE-ARM-DYN and is not published
        ('FLAG', 'SG-NOTE-FLAG', 'Note flag with attribute', 'Annotation'),
        ('BOXNOTE', 'SG-NOTE-BOX', 'Boxed note with attribute', 'Annotation'),
        ('SL', 'SG-NOTE-STANDARD-NUMBER', 'Standard number circle with attribute', 'Annotation'),
        ('TRAFFIC SIGN & POST', 'SN-SIGN-POST-DYN', 'Sign and post', 'Sign posts'),
        ('TRAFFIC SIGN', 'SN-SIGN-DYN', 'Sign (face line)', 'Sign posts'),
        ('POWER POLE', 'SV-POWER-POLE-DYN', 'Power pole', 'Existing and site features'),
        ('POWER POLE - GUY ANCHOR', 'SV-POWER-POLE-GUY-ANCHOR-DYN', 'Power pole with guy anchor', 'Existing and site features'),
        ('FIRE HYDRANT', 'SV-FIRE-HYDRANT-DYN', 'Fire hydrant', 'Existing and site features'),
        ('VALVE', 'SV-VALVE-DYN', 'Valve', 'Existing and site features'),
        ('METER', 'SV-METER-DYN', 'Meter', 'Existing and site features'),
        ('MAIL BOX', 'SV-MAILBOX-DYN', 'Mailbox', 'Existing and site features'),
        ('BUS BENCH', 'SV-BUS-BENCH-DYN', 'Bus bench', 'Existing and site features'),
        ('NEWS STAND', 'SV-NEWS-RACK-DYN', 'News rack', 'Existing and site features'),
        ('BIKE RACK', 'SV-BIKE-RACK-DYN', 'Bike rack', 'Existing and site features'),
        ('PALM', 'SV-PALM-TREE-DYN', 'Palm tree', 'Existing and site features'),
        ('TREE-E', 'SV-TREE-E', 'Existing tree', 'Existing and site features'),
    ],
    'westwood-survey': [
        ('WV', 'SV-WATER-VALVE', 'Water valve (survey)', 'Survey symbols'),
        ('GV', 'SV-GAS-VALVE', 'Gas valve (survey)', 'Survey symbols'),
        ('ICV', 'SV-IRRIGATION-CONTROL-VALVE', 'Irrigation control valve (survey)', 'Survey symbols'),
        ('PIV', 'SV-POST-INDICATOR-VALVE', 'Post indicator valve (survey)', 'Survey symbols'),
        ('BFV', 'SV-BACKFLOW-PREVENTER-DYN', 'Backflow preventer (survey)', 'Survey symbols'),
        ('WM', 'SV-WATER-METER-DYN', 'Water meter (survey)', 'Survey symbols'),
        ('GM', 'SV-GAS-METER-DYN', 'Gas meter (survey)', 'Survey symbols'),
        ('PM', 'SV-PARKING-METER-DYN', 'Parking meter (survey)', 'Survey symbols'),
        ('MH', 'SV-MANHOLE-DYN', 'Manhole (survey)', 'Survey symbols'),
        ('MHD', 'SV-MANHOLE-STORM-DRAIN', 'Storm drain manhole (survey)', 'Survey symbols'),
        ('MHSS', 'SV-MANHOLE-SEWER', 'Sanitary sewer manhole (survey)', 'Survey symbols'),
        ('MHE', 'SV-MANHOLE-ELECTRIC', 'Electric manhole (survey)', 'Survey symbols'),
        ('MHT', 'SV-MANHOLE-TELEPHONE', 'Telephone manhole (survey)', 'Survey symbols'),
        ('MHW', 'SV-MANHOLE-WATER', 'Water manhole (survey)', 'Survey symbols'),
        ('MHU', 'SV-MANHOLE-UNKNOWN', 'Unknown manhole (survey)', 'Survey symbols'),
        ('SCO', 'SV-SEWER-CLEANOUT', 'Sewer cleanout (survey)', 'Survey symbols'),
        ('MW', 'SV-MONITORING-WELL', 'Monitoring well (survey)', 'Survey symbols'),
        ('WELL', 'SV-WELL', 'Well (survey)', 'Survey symbols'),
        ('VENT', 'SV-VENT', 'Vent (survey)', 'Survey symbols'),
        ('E-OUTLET', 'SV-ELECTRIC-OUTLET', 'Electric outlet (survey)', 'Survey symbols'),
        ('PP (FULL)', 'SV-UTILITY-POLE-DYN', 'Utility pole (survey)', 'Survey symbols'),
        ('GUY WIRE', 'SV-GUY-WIRE-DYN', 'Guy wire (survey)', 'Survey symbols'),
        ('POLE', 'SV-POLE-DYN', 'Pole (survey)', 'Survey symbols'),
        ('LT (FULL)', 'SV-LIGHT-POLE-DYN', 'Light pole (survey)', 'Survey symbols'),
        ('SL (FULL)', 'SV-STREET-LIGHT-DYN', 'Street light (survey)', 'Survey symbols'),
        ('TRAFF_L_BASE', 'SV-TRAFFIC-SIGNAL-BASE', 'Traffic signal pole base (survey)', 'Survey symbols'),
        ('RRSIGN', 'SV-RAILROAD-SIGN', 'Railroad crossing sign (survey)', 'Survey symbols'),
        ('SIGN1', 'SV-SIGN-DYN', 'Sign (survey)', 'Survey symbols'),
        ('TREE', 'SV-TREE-DYN', 'Tree (survey)', 'Survey symbols'),
        ('TREE-PALM', 'SV-TREE-PALM', 'Palm tree (survey)', 'Survey symbols'),
        ('TREE-PINE', 'SV-TREE-PINE-DYN', 'Pine tree (survey)', 'Survey symbols'),
        ('TREE-STUMP', 'SV-TREE-STUMP-DYN', 'Tree stump (survey)', 'Survey symbols'),
        ('BUSH1', 'SV-SHRUB-DYN', 'Shrub (survey)', 'Survey symbols'),
        ('SIGNAL STANDARD NUMBER', 'SG-NOTE-STANDARD-NUMBER', 'Standard number circle with attribute', 'Annotation'),
    ],
}
# fixed sub-block names already published
SUBS = {'BIKE LANE ARROW': 'PM-DYN-SUB-BIKE-ARROW', 'BIKE-SYM2': 'PM-DYN-SUB-BIKE-SYMBOL'}
# where each discipline publishes and its insert layer
FAMILIES = {'PM': ('markings/cad', 'P-PMARK'), 'SG': ('signals/cad', 'P-SIGNAL'), 'SN': ('signals/cad', 'P-SIGN'),
            'SV': ('signals/cad', 'E-SITE')}
# one library per source drawing: a library cannot mix dynamic data from two drawings outside AutoCAD
LIBRARIES = {'westwood-ss': 'SSS-STRIPING-PLAN-LIBRARY.dwg', 'westwood-ts': 'SSS-SIGNAL-PLAN-LIBRARY.dwg',
             'westwood-survey': 'SSS-SURVEY-LIBRARY.dwg'}
LIBRARY_ROUTE = {'westwood-ss': 'markings/cad', 'westwood-ts': 'signals/cad', 'westwood-survey': 'signals/cad'}
STATE = {'SIGEQ': 'SIGNAL', 'SIGCOND': 'SIGNAL', 'SIGCIVIL': 'SITE', 'SIGN': 'SIGN', 'STRP-PVMTXT': 'PMARK',
         'STRP-PVM': 'PMARK', 'PMARK': 'PMARK', 'REMOVE': 'SIGN', 'REMOVE-STRP-PVMTXT': 'PMARK'}
TO_ZERO = {'BASE', '1', 'STRP', 'FP-RAISED-ELEMENT', 'FP-RAISED-ELEMENT-FRZ', 'Z-TEXT-FRZ', 'PSTRP', 'P-STRP-SOLID', 'SUBSTR', 'E-SIGTXT', 'E-SIGTEXT', '$0$E-SIGTXT', '$1$E-SIGTXT',
           'T-NOTES', 'T-TYPE', 'T-ATTRIB', 'B-TEXT', '_E-TRAF-POSTS', '_E-TRAF-SYM', 'V-TREE-TR', 'V-UTLS-TL',
           'V-TOPO-MISC-CRACK', 'V-ANNO-TREE DIAM'}
NO_PLOT = {'FP-NOPLOT', '_FP-NOPLOT', 'FP-NO-PLOT', '__AA-WORKING-01', 'FP-Noplot', 'FP-NOPLOT-EH', 'FP-NOPLOT-ND'}
GREEN = {'_P-STRP-GREEN', 'FP-GREEN-BIKE-LANE'}
ALIASES = {'_E-STRP-RETAIN': 'E-PMARK', '_LADOT-P-SIGN-SYM': 'P-SIGN'}
GROUP_OF = {}     # standard name -> page group, filled by build() for library sheets
LINETYPES = {'Base$0$R-Solid': ('PMARK-REMOVE', 'Removed marking  __ __ __')}


def layer_for(name):
    """(layer, color or None) for a layer inside a kept block."""
    up = name.upper()
    if name == 'Defpoints' or re.match(r'^[EPRA]-(SIGNAL|SITE|SIGN|PMARK)$', name):
        return name, None   # already standard (a second pass over a cut library)
    if up in NO_PLOT:
        return 'Defpoints', None
    if name in GREEN:
        return '0', 3
    if name in ALIASES:
        return ALIASES[name], None
    if name == '0' or name in TO_ZERO:
        return '0', None
    m = re.match(r'^_?([EPRA])-(.+)$', name)
    if m and m.group(2) in STATE:
        return f'{m.group(1)}-{STATE[m.group(2)]}', None
    raise ValueError('unmapped layer ' + name)


def oda(src, out_dir, fmt, version='ACAD2018'):
    """Convert one file with ODA File Converter (audit on). Returns the output path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(src, Path(tmp) / Path(src).name)
        cmd = ['ODAFileConverter', tmp, str(out_dir), version, fmt, '0', '1']
        if shutil.which('xvfb-run'):
            cmd = ['xvfb-run', '-a'] + cmd
        subprocess.run(cmd, capture_output=True, timeout=900, check=True)
    out = out_dir / (Path(src).stem + '.' + fmt.lower())
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


def is_dynamic(doc, block):
    br = doc.blocks[block].block_record
    return br.has_extension_dict and 'ACAD_ENHANCEDBLOCK' in br.get_extension_dict()


def graph_of(doc, block):
    if not is_dynamic(doc, block):
        return set()
    return owned(doc, [doc.blocks[block].block_record.get_extension_dict().dictionary.dxf.handle])


def class_names(doc):
    return [c.dxf.name for c in doc.classes.classes.values()]


def signature(doc, handles):
    """Class name and bytes of every proxy among the handles, in a comparable form (by name: the class
    table is compacted, so positions change)."""
    names, out = class_names(doc), collections.Counter()
    for h in handles:
        o = doc.entitydb.get(h)
        if o is None or o.dxftype() != 'ACAD_PROXY_OBJECT':
            continue
        sub = o.xtags.get_subclass('AcDbProxyObject')
        data = b''.join(t.value for t in sub if t.code == 310)
        pos = sub.get_first_value(91) - 500
        out[(names[pos] if 0 <= pos < len(names) else pos, data, len(refs(o)))] += 1
    return out


def compact_classes(doc):
    """Keep only the classes something in the drawing uses and renumber the proxies' class references
    (a proxy names its class by position: 500 + index). A survey brings about 730 classes."""
    from ezdxf.lldxf.types import DXFTag
    entries = list(doc.classes.classes.items())
    used = {o.dxftype() for o in doc.objects if o.is_alive} | {e.dxftype() for b in doc.blocks for e in b}
    proxies = [o for o in doc.objects if o.is_alive and o.dxftype() == 'ACAD_PROXY_OBJECT']
    for o in proxies:
        pos = o.xtags.get_subclass('AcDbProxyObject').get_first_value(91) - 500
        if 0 <= pos < len(entries):
            used.add(entries[pos][1].dxf.name)
    kept = [(k, c) for k, c in entries if c.dxf.name in used]
    index = {c.dxf.name: i for i, (_, c) in enumerate(kept)}
    for o in proxies:
        sub = o.xtags.get_subclass('AcDbProxyObject')
        for i, tag in enumerate(sub):
            if tag.code == 91 and 0 <= tag.value - 500 < len(entries):
                sub[i] = DXFTag(91, 500 + index[entries[tag.value - 500][1].dxf.name])
                break
    doc.classes.classes = dict(kept)


def nested(doc, names):
    """Every block the given blocks insert, at any depth."""
    out, stack = set(), list(names)
    while stack:
        for i in doc.blocks[stack.pop()].query('INSERT'):
            if i.dxf.name not in out:
                out.add(i.dxf.name)
                stack.append(i.dxf.name)
    return out


def sub_name(parent, name):
    if re.match(r'^[A-Z]{2}-(DYN-)?SUB-', name):
        return name   # already standard (a second pass over a cut library)
    return SUBS.get(name) or f"{parent.split('-')[0]}-SUB-{re.sub(r'[^A-Z0-9]+', '-', name.upper()).strip('-')}"


def fingerprint(doc, name, _seen=None):
    """Geometry, nested blocks and dynamic data of a cleaned definition, as one hash."""
    h = hashlib.sha256()
    for e in doc.blocks[name]:
        attrs = {k: v for k, v in e.dxf.all_existing_dxf_attribs().items() if k not in ('handle', 'owner', 'name')}
        h.update(e.dxftype().encode())
        for k in sorted(attrs):
            v = attrs[k]
            v = tuple(round(x, 4) for x in v) if hasattr(v, '__iter__') and not isinstance(v, str) else (round(v, 4) if isinstance(v, float) else v)
            h.update(f'{k}={v};'.encode())
        if e.dxftype() == 'LWPOLYLINE':
            h.update(str([tuple(round(x, 4) for x in p) for p in e.get_points()]).encode())
        if e.dxftype() == 'HATCH':
            for p in e.paths:
                h.update(str([tuple(round(x, 4) for x in v[:2]) for v in getattr(p, 'vertices', [])]).encode())
        if e.dxftype() == 'INSERT':
            h.update(fingerprint(doc, e.dxf.name).encode())
    for (cls, data, n), count in sorted(signature(doc, graph_of(doc, name)).items(), key=lambda x: (x[0][0], x[0][1])):
        h.update(f'{cls}:{n}:{count}:'.encode() + hashlib.sha256(data).digest())
    return h.hexdigest()


def rebase(doc, name):
    """A static block drawn in place at state plane coordinates gets its base point at the bottom center."""
    ext = bbox.extents(doc.blocks[name])
    if ext.has_data and max(abs(v) for v in (*ext.extmin.xy, *ext.extmax.xy)) > 10000:
        dx, dy = -(ext.extmin.x + ext.extmax.x) / 2, -ext.extmin.y
        for e in doc.blocks[name]:
            e.translate(dx, dy, 0)


def tidy(doc):
    """Drop repeated consecutive LWPOLYLINE vertices inside static blocks (drafting leftovers).
    Dynamic blocks and their sub-blocks are left alone: their actions may point at vertices."""
    hold = set()
    for blk in doc.blocks:
        if not blk.is_any_layout and is_dynamic(doc, blk.name):
            hold |= nested(doc, [blk.name]) | {blk.name}
    for blk in doc.blocks:
        if blk.name in hold or blk.name.startswith('*'):
            continue
        for e in list(blk):
            if e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points('xyseb'))
                keep = [q for i, q in enumerate(pts) if i == 0 or (round(q[0], 6), round(q[1], 6)) != (round(pts[i - 1][0], 6), round(pts[i - 1][1], 6))]
                if e.closed and len(keep) > 1 and (round(keep[0][0], 6), round(keep[0][1], 6)) == (round(keep[-1][0], 6), round(keep[-1][1], 6)):
                    keep.pop()
                if len(keep) < 2:
                    blk.delete_entity(e)   # a polyline collapsed to one point draws nothing
                elif len(keep) != len(pts):
                    e.set_points(keep, 'xyseb')


def cut(src_dxf, keep, dst_dxf, insert_layer=None):
    """Write a DXF holding only the kept blocks (source name -> standard name), cleaned and renamed,
    with their sub-blocks. Returns the dynamic data of each kept block, by standard name."""
    doc = ezdxf.readfile(src_dxf)
    subs = nested(doc, keep) - set(keep)   # a kept block nested in another keeps its own name
    parent_of = {}
    for k in keep:
        for sub in nested(doc, [k]):
            parent_of.setdefault(sub, keep[k])
    before = {keep[k]: signature(doc, graph_of(doc, k)) for k in keep}
    for space in doc.layouts:
        for e in list(space):
            space.delete_entity(e)
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
    # a block library carries no project location: drop the survey's geolocation (GEODATA)
    for br in doc.block_records:
        if br.has_extension_dict and 'ACAD_GEOGRAPHICDATA' in br.get_extension_dict():
            br.get_extension_dict().discard('ACAD_GEOGRAPHICDATA')
    for o in [o for o in doc.objects if o.is_alive and o.dxftype() == 'GEODATA']:
        doc.objects.delete_entity(o)   # a GEODATA kept as a proxy is unreachable now and goes with the other proxies
    # empty nested blocks: drop them and the inserts that place them, unless the dynamic data points at an insert
    for sub in [n for n in subs if not len(doc.blocks[n])]:
        for name in list(keep) + list(subs):
            for e in list(doc.blocks[name].query('INSERT')):
                if e.dxf.name == sub and e.dxf.handle not in pinned:
                    doc.blocks[name].delete_entity(e)
        if not any(e.dxf.name == sub for n in list(keep) + list(subs) if n != sub for e in doc.blocks[n].query('INSERT')):
            doc.blocks.delete_block(sub, safe=False)
            subs.discard(sub)
    root = doc.rootdict
    for key in list(root.keys()):
        if key == 'Root' or key.upper().startswith(('AEC', 'AECC', 'CIVIL', 'ACAD_CIP', 'MAP', 'AUTODESK_MAP', 'DM', 'IRD',
                                                       'ACAD_ASSOC', 'SVY_', 'TS_', 'PE5.', 'ADE_', 'ASE_', 'ESRI_', '{')):
            root.discard(key)
    setups = root.get('ACAD_PLOTSETTINGS')
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
    # clean the kept geometry
    if 'Defpoints' not in doc.layers:
        doc.layers.new('Defpoints', dxfattribs={'color': 7, 'plot': 0})
    sources = {}
    for name in list(keep) + sorted(subs):
        block = doc.blocks[name]
        block.block_record.dxf.units = 2
        for e in block:
            if not e.dxf.is_supported('layer'):
                continue
            old = e.dxf.get('layer', '0')
            new, color = layer_for(old)
            if new not in doc.layers:
                sources[new] = old
                src = doc.layers.get(old) if old in doc.layers else None
                linetype = src.dxf.linetype if src else 'Continuous'
                if linetype in LINETYPES:
                    lt, desc = LINETYPES[linetype]
                    if lt not in doc.linetypes:
                        pattern = [t.value for t in doc.linetypes.get(linetype).pattern_tags.tags if t.code in (40, 49)]
                        doc.linetypes.add(lt, pattern=pattern, description=desc)
                    linetype = lt
                if linetype not in doc.linetypes:
                    linetype = 'Continuous'
                doc.layers.new(new, dxfattribs={'color': 7 if new.startswith('P-') or not src else src.dxf.color,
                                                'linetype': linetype, 'lineweight': src.dxf.get('lineweight', -3) if src else -3})
            e.dxf.layer = new
            if color is not None and e.dxf.get('color', 256) == 256:
                e.dxf.color = color
            elif new == '0' and e.dxf.get('color', 256) == 256:
                e.dxf.color = 0
            if e.dxftype() == 'INSERT' and e.dxf.name in keep:
                e.dxf.name = keep[e.dxf.name]
            elif e.dxftype() == 'INSERT' and e.dxf.name in subs:
                e.dxf.name = sub_name(parent_of[e.dxf.name], e.dxf.name)
    for sub in sorted(subs):
        if sub_name(parent_of[sub], sub) != sub:
            doc.blocks.rename_block(sub, sub_name(parent_of[sub], sub))
    for old, new in keep.items():
        if old != new:
            doc.blocks.rename_block(old, new)
    used = {e.dxf.layer for b in doc.blocks for e in b if e.dxf.is_supported('layer')} | {'0', 'Defpoints'}
    for layer in list(doc.layers):
        if layer.dxf.name not in used:
            doc.layers.remove(layer.dxf.name)
    style_used = {'Standard', 'ROMANS'} | {ds.dxf.get('dimtxsty', 'Standard') for ds in doc.dimstyles}
    lt_used = {'ByBlock', 'ByLayer', 'Continuous'} | {l.dxf.linetype for l in doc.layers}
    for b in doc.blocks:
        for e in b:
            if e.dxf.is_supported('style'):
                style_used.add(e.dxf.get('style', 'Standard'))
            if e.dxf.is_supported('linetype'):
                lt_used.add(e.dxf.get('linetype', 'ByLayer'))
    for st in list(doc.styles):
        if st.dxf.name and st.dxf.name not in style_used and st.dxf.handle not in pinned and not st.is_shape_file:
            doc.styles.remove(st.dxf.name)
    for lt in list(doc.linetypes):
        if lt.dxf.name not in lt_used and lt.dxf.handle not in pinned:
            doc.linetypes.remove(lt.dxf.name)
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
    compact_classes(doc)
    tidy(doc)
    for name in keep.values():
        if not is_dynamic(doc, name):
            rebase(doc, name)
    if insert_layer:
        layout(doc, list(keep.values()))
    doc.units = 2
    doc.header['$INSUNITS'] = 2
    doc.saveas(dst_dxf)
    return before


def insert_layer_of(name):
    return FAMILIES[name.split('-')[0]][1]


def layout(doc, names, insert_layer=None):
    """One reference of each block on its family's layer; a one-block file inserts at 0,0. Names under
    each in ROMANS."""
    if 'ROMANS' not in doc.styles:
        doc.styles.new('ROMANS', dxfattribs={'font': 'romans.shx'})
    for lay in {insert_layer_of(n) for n in names}:
        for layer, color in ((lay, 7 if lay.startswith('P-') else 8), (lay + '-TEXT', 7)):
            if layer not in doc.layers:
                doc.layers.new(layer, dxfattribs={'color': color})
    msp = doc.modelspace()
    if len(names) == 1:
        name = names[0]
        ext = bbox.extents(doc.blocks[name])
        msp.add_blockref(name, (0, 0), dxfattribs={'layer': insert_layer_of(name)})
        msp.add_mtext(name, dxfattribs={'layer': insert_layer_of(name) + '-TEXT', 'style': 'ROMANS', 'char_height': 0.6,
                                        'insert': ((ext.extmin.x + ext.extmax.x) / 2, ext.extmin.y - 1.0),
                                        'attachment_point': 2})
        return
    # a library: each page group in its own area, one 24 x 36 sheet per group
    from block_libraries import sheet
    groups = list(dict.fromkeys(GROUP_OF.get(n, 'Blocks') for n in names))
    old_sheets = [n for n in doc.layouts.names() if n != 'Model']
    for gi, group in enumerate(groups):
        x0, x, y, row_h, right = gi * 5000.0, 0.0, 0.0, 0.0, 0.0
        msp.add_mtext(group.upper(), dxfattribs={'layer': insert_layer_of(names[0]) + '-TEXT', 'style': 'ROMANS',
                                                 'char_height': 2.0, 'insert': (x0, 3.0), 'attachment_point': 7})
        for name in [n for n in names if GROUP_OF.get(n, 'Blocks') == group]:
            ext = bbox.extents(doc.blocks[name])
            w, h = ext.extmax.x - ext.extmin.x, ext.extmax.y - ext.extmin.y
            if x > 0 and x + w > 120:
                x, y, row_h = 0.0, y - row_h - 6, 0.0
            msp.add_blockref(name, (x0 + x - ext.extmin.x, y - ext.extmax.y), dxfattribs={'layer': insert_layer_of(name)})
            msp.add_mtext(name, dxfattribs={'layer': insert_layer_of(name) + '-TEXT', 'style': 'ROMANS', 'char_height': 0.6,
                                            'insert': (x0 + x + w / 2, y - h - 1.0), 'attachment_point': 2})
            x += max(w, len(name) * 0.6) + 6
            right = max(right, x)
            row_h = max(row_h, h + 2)
        sheet(doc, f'{gi + 1:02d} {group}', (x0 - 3, y - row_h - 3, x0 + right, 6.0), 'ft',
              'SSS LA PLAN LIBRARY', group)
    for n in old_sheets:     # the source drawing's own sheets do not belong in a block library
        doc.layouts.delete(n)

def write(lib_dxf, names, target, libredwg, work, expect):
    """Cut one or more already-standard blocks from a source library DXF into a published DWG."""
    work.mkdir(parents=True, exist_ok=True)
    dxf = work / (target.stem + '.dxf')
    cut(lib_dxf, {n: n for n in names}, dxf, insert_layer=True)
    doc = ezdxf.readfile(dxf)
    dynamic = any(is_dynamic(doc, n) for n in names)
    if not dynamic:   # a static block needs none of the plan's tables: a fresh AutoCAD 2000 drawing
        return write_static(doc, names, target, libredwg, work)
    dwg = oda(dxf, work, 'DWG', 'ACAD2018')
    back = ezdxf.readfile(oda(dwg, work / 'rt', 'DXF', 'ACAD2018'))
    for n in names:
        after = signature(back, graph_of(back, n))
        if after != expect[n]:
            raise ValueError(f'{target.name}: {n} dynamic data changed ({sum(expect[n].values())} -> {sum(after.values())})')
    if [e.dxftype() for e in back.modelspace() if e.dxftype() != 'MTEXT'] != ['INSERT'] * len(names):
        raise ValueError(f'{target.name}: model space is not block references only')
    native = work / 'native.dxf'
    subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', native, dwg], capture_output=True)
    text = native.read_text(errors='ignore')
    graphs = text.count('\nACAD_EVALUATION_GRAPH\n') - 1
    if dynamic and (graphs < 1 or '\nACAD_PROXY_OBJECT\n' in text):
        raise ValueError(f'{target.name}: {graphs} native graphs or proxies left')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(dwg, target)
    return dynamic


def write_static(src, names, target, libredwg, work):
    """Static blocks: copied into a clean R2000 drawing (sign_cells.r2000_document) and encoded with
    LibreDWG, read back before publishing, like every other static SSS block."""
    from ezdxf.addons import Importer
    from sign_cells import r2000_document
    doc = r2000_document()
    doc.units = 2
    imp = Importer(src, doc)
    imp.import_tables('layers')
    imp.import_tables('linetypes')
    for n in names:
        imp.import_block(n)
    imp.finalize()
    for n in names:
        doc.blocks[n].block_record.dxf.units = 2
        tidy(doc)
        rebase(doc, n)
    layout(doc, names)
    doc.header['$INSUNITS'] = 2
    for layer in list(doc.layers):
        if layer.dxf.name not in {e.dxf.layer for b in doc.blocks for e in b if e.dxf.is_supported('layer')} | \
                {e.dxf.layer for e in doc.modelspace()} | {'0', 'Defpoints'}:
            doc.layers.remove(layer.dxf.name)
    dxf = work / 'static.dxf'
    tidy(doc)
    doc.saveas(dxf)
    log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', work / 'static.dwg', dxf], capture_output=True, text=True)
    if log.returncode or re.search(r'warning|error', log.stdout + log.stderr, re.I):
        raise ValueError(f'{target.name}: encoder reported ' + (log.stdout + log.stderr)[-300:])
    back = work / 'static-rt.dxf'
    subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', back, work / 'static.dwg'], capture_output=True, check=True)
    read = ezdxf.readfile(back)
    if [e.dxftype() for e in read.modelspace() if e.dxftype() != 'MTEXT'] != ['INSERT'] * len(names) or \
            any(len(read.blocks[n]) != len(doc.blocks[n]) for n in names):
        raise ValueError(f'{target.name}: static read-back differs')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(work / 'static.dwg', target)
    return False


def build(paths, libredwg):
    report = {'merged': [], 'kept_first': [], 'files': 0}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        libs, expect, rows, prints, owner = {}, {}, {}, {}, {}
        for source, entries in SOURCES.items():
            src = oda(paths[source], tmp / source, 'DXF')
            keep = {}
            doc = ezdxf.readfile(src)
            for old, new, label, group in entries:
                if old not in doc.blocks:
                    raise ValueError(f'{source}: no block {old}')
                keep[old] = new
            del doc
            lib = tmp / f'{source}-lib.dxf'
            expect_src = cut(src, keep, lib)
            ldoc = ezdxf.readfile(lib)
            for old, new, label, group in entries:
                fp = fingerprint(ldoc, new)
                if new in rows:
                    report['merged' if prints[new] == fp else 'kept_first'].append(f'{source}:{old} -> {new}')
                    continue
                twin = next((n for n, f in prints.items() if f == fp), None)
                if twin:
                    report['merged'].append(f'{source}:{old} = {twin}')
                    continue
                prints[new] = fp
                owner[new] = source
                expect[new] = expect_src[new]
                rows[new] = {'code': new, 'label': label, 'group': group, 'source': source}
                GROUP_OF[new] = group
            libs[source] = lib
        # one file per block, then one library per source drawing
        for name, row in rows.items():
            route = FAMILIES[name.split('-')[0]][0]
            target = Path('public/downloads') / route / (name + '.dwg')
            row['dynamic'] = write(libs[owner[name]], [name], target, libredwg, tmp / 'w' / name, expect)
            row['route'] = route
            row['library'] = LIBRARIES[owner[name]]
            report['files'] += 1
        for source, library in LIBRARIES.items():
            members = [n for n in rows if owner[n] == source]
            target = Path('public/downloads') / LIBRARY_ROUTE[source] / library
            write(libs[source], members, target, libredwg, tmp / 'lib' / source, expect)
    return rows, report


def publish(rows):
    catalog = json.loads(CATALOG.read_text())
    for route in {r['route'] for r in rows.values()}:
        section = catalog[route]
        family = [r for r in rows.values() if r['route'] == route]
        codes = {r['code'] for r in family}
        section['blocks'] = [b for b in section['blocks'] if b['code'] not in codes] + [
            {'code': r['code'], 'name': f"{r['label']} · {'dynamic · ' if r['dynamic'] else ''}LA plan library",
             'file': r['code'] + '.dwg', 'group': r['group'], **({'dynamic': 'Dynamic block'} if r['dynamic'] else {})}
            for r in family]
        for r in family:
            if r['group'] not in section['groups']:
                section['groups'].append(r['group'])
        downloads = [d for d in section.get('downloads', []) if d['label'] != 'SSS-PMARK-DYNAMIC.dwg'
                     and d['label'] not in LIBRARIES.values()]
        for source, library in LIBRARIES.items():
            if any(r['library'] == library for r in family):
                downloads.append({'label': library, 'path': f'downloads/{LIBRARY_ROUTE[source]}/{library}',
                                  'note': {'westwood-ss': 'every block from the LA signing and striping plan library in one drawing',
                                           'westwood-ts': 'every block from the LA traffic signal plan library in one drawing (signals, arrows, sign posts, site items)',
                                           'westwood-survey': 'every survey symbol in one drawing'}[source] + ', grips and visibility states intact'})
        section['downloads'] = downloads
    CATALOG.write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', action='append', required=True, help='name=path')
    parser.add_argument('--libredwg', type=Path, required=True)
    args = parser.parse_args()
    paths = dict(s.split('=', 1) for s in args.source)
    rows, report = build(paths, args.libredwg)
    publish(rows)
    print(json.dumps(report, indent=1))
    print(len(rows), 'blocks')
