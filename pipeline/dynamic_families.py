"""Dynamic block families: published variants merged into one dynamic block each, with visibility
states, rotation and flip X and Y about the shared base point.

The family list is computed from the catalogs (data/reference/dynamic-families.json records it).
AutoCAD writes the dynamic blocks: SSS-DYNBUILD.lsp (public/downloads/cad-tools) reads the manifest
CSV packed beside the state drawings in SSS-DYNBUILD.zip, builds every family in one run and writes
one DWG per family plus SSS-DYNAMIC-FAMILIES.dwg. Upload that folder to publish them.

Every state of a family shares the family's base point rule, so parameters and actions act the same
way in every state. Families never mix placement rules.

  python3 pipeline/dynamic_families.py            # write the family list
  build step: package(root) writes the zip once the sign blocks are hydrated (CI)
"""
import json
import re
import zipfile
from collections import OrderedDict
from pathlib import Path

CATALOG = Path('data/reference/design-blocks.json')
SIGNS = Path('data/reference/cad-block-downloads/manifest.json')
OUT = Path('data/reference/dynamic-families.json')
PACKAGE = Path('public/downloads/cad-tools/SSS-DYNBUILD.zip')
LISP = Path('public/downloads/cad-tools/SSS-DYNBUILD.lsp')
SIDE = re.compile(r'^(?P<base>.+?)(?:\s*\((?P<p>L|R|LT|RT)\)|(?<=\d)(?P<s>L|R))$')


LANE_MID = 5.5      # arrows mirror about the lane center, so a left arrow flips into the right arrow in place
# LADOT Drafting Standards for Striping and Signal Plans (2005) p. 10: every pavement marking is drawn
# three ways. Proposed is filled, existing is the outline only, removed is the outline dashed.
CONDITIONS = ('PROPOSED', 'EXISTING', 'REMOVE')
PAINT = ('PROPOSED', 'EXISTING')          # colored pavement is repainted over, never shown as removed
# Static blocks that repeat a published dynamic block with the same geometry: the dynamic one is kept.
SUPERSEDED = {'PM-BIKE-ARROW-LEFT-THRU': 'PM-BIKE-LEFT-THRU-ARROW-DYN',
              'PM-BIKE-LANE-SYMBOL-GREEN': 'PM-BIKE-LANE-GREEN-DYN',
              'SG-ELECTROLIER-E': 'SG-LUMINAIRE-ARM-DYN'}
# Marking blocks: short plain names; the standard they come from goes in the block description.
# (name, source code, description, flip line x)
MARKINGS = [
    ('SSS-ARROW-THRU', 'CT-A24A-TYPE-I-10FT', 'Through arrow, 10 ft (Caltrans A24A Type I)', None),
    ('SSS-ARROW-THRU-18', 'CT-A24A-TYPE-I-18FT', 'Through arrow, 18 ft (Caltrans A24A Type I)', None),
    ('SSS-ARROW-THRU-24', 'CT-A24A-TYPE-I-24FT', 'Through arrow, 24 ft (Caltrans A24A Type I)', None),
    ('SSS-ARROW-TURN', 'CT-A24A-TYPE-IV-L', 'Turn arrow; flip for a right turn (Caltrans A24A Type IV)', LANE_MID),
    ('SSS-ARROW-THRU-TURN', 'CT-A24A-TYPE-VII-L', 'Through and turn arrow; flip for through-right (Caltrans A24A Type VII)', LANE_MID),
    ('SSS-ARROW-THRU-LEFT-RIGHT', 'CT-A24A-TYPE-VIII', 'Through, left and right arrow (Caltrans A24A Type VIII)', None),
    ('SSS-ARROW-LANE-DROP', 'CT-A24A-TYPE-VI', 'Lane drop arrow; flip for the left lane (Caltrans A24A Type VI)', LANE_MID),
    ('SSS-BIKE-SYMBOL', 'CT-A24C-BIKE-SYMBOL', 'Bike lane symbol (Caltrans A24C)', None),
    ('SSS-BIKE-SYMBOL-RIDER', 'CT-A24C-BIKE-SYMBOL-PERSON', 'Bike lane symbol with rider (Caltrans A24C)', None),
    ('SSS-BIKE-ARROW', 'CT-A24A-BIKE-LANE-ARROW', 'Bike lane arrow (Caltrans A24A)', None),
    ('SSS-SHARROW', 'CT-A24C-SHARROW', 'Shared lane marking (Caltrans A24C)', None),
    ('SSS-ISA', 'CT-A24C-ISA', 'Accessible parking symbol (Caltrans A24C)', None),
    ('SSS-DIAMOND', 'CT-A24C-DIAMOND', 'Preferential lane diamond (Caltrans A24C)', None),
    ('SSS-RXR', 'CT-A24B-RXR', 'Railroad crossing marking (Caltrans A24B)', None),
    ('SSS-YIELD-TRIANGLE', 'PM-YIELD-LINE-TRIANGLE', 'Yield line triangle, 2 x 3 ft', None),
    ('SSS-LEFT-TURN-CALMING-3', 'PM-LEFT-TURN-CALMING-3FT', 'Left turn calming bump, 3 ft', None),
    ('SSS-LEFT-TURN-CALMING-10', 'PM-LEFT-TURN-CALMING-10FT', 'Left turn calming curb, 10 ft', None),
    ('SSS-LANE-DEFENDER-15', 'PM-LANE-DEFENDER-15FT', 'Lane defender, 15 ft', None),
    ('SSS-CROSSWALK-DIAGONAL', 'CT-A24F-DIAGONAL', 'Diagonal crosswalk, 45 degree bars (Caltrans A24F)', None),
    ('SSS-WORD-KEEP-CLEAR', 'PM-KEEP-CLEAR', 'KEEP CLEAR (Caltrans A24E words)', None),
    ('SSS-WORD-BUS-ONLY', 'PM-BUS-ONLY', 'BUS ONLY (Caltrans A24E words)', None),
    ('SSS-WORD-WAIT-HERE', 'PM-WAIT-HERE', 'WAIT HERE (Caltrans A24D words)', None),
]
# Array blocks: drawn by dynamic_source.py from these dimensions (Caltrans Std. Plan A24F; the LA
# plan crossing dash). Elements are (x0, y0, x1, y1) in feet. 'unit' repeats along the length grip at
# 'spacing'; 'lines' run the full length and stretch with it; 'width' adds a width grip.
ARRAYS = [
    dict(name='SSS-CROSSWALK-BASIC', description='Basic crosswalk, two 1 ft lines 6 ft apart (Caltrans A24F)',
         axis='x', length=40.0, lines=[(0, 0, None, 1), (0, 7, None, 8)]),
    dict(name='SSS-CROSSWALK-CONTINENTAL', description='Continental crosswalk, 1 ft bars at 2 ft centers, first bar one gap from the curb (Caltrans A24F)',
         axis='x', length=40.0, unit=[(1, 0, 2, 6)], spacing=2.0),
    dict(name='SSS-CROSSWALK-LADDER', description='Ladder crosswalk, 1 ft lines and bars (Caltrans A24F)',
         axis='x', length=40.0, lines=[(0, 0, None, 1), (0, 7, None, 8)], unit=[(1, 1, 2, 7)], spacing=2.0),
    dict(name='SSS-CROSSWALK-TRIPLE-FOUR', description='Triple four crosswalk, 2 x 4 ft blocks (Caltrans A24F)',
         axis='x', length=40.0, unit=[(2, 0, 4, 4), (2, 8, 4, 12)], spacing=4.0),
    dict(name='SSS-BIKE-XING-GREEN', description='Green bike crossing: 2 ft dash every 8 ft with the bike lane line on each edge; width grip 5 to 8 ft',
         axis='y', length=48.0, width=5.0, unit=[(0, 0, None, 2)], spacing=8.0, green=True, edges=True),
]
CROSSWALK_PLACE = ('Base at the curb corner on the near crosswalk edge; drag the length grip to the far curb. '
                   'Bars start one gap from the curb')
XING_PLACE = ('Base at the upstream corner on the bike lane line, where the crossing begins; the width grip sets '
              'the lane width, the length grip runs across the intersection. The first dash starts at the line')


def slug(text):
    return re.sub(r'[^A-Z0-9]+', '-', text.upper()).strip('-')


def marking_families(section):
    rows = {r['code']: r for r in section['blocks'] if not r.get('dynamic') and r['code'] not in SUPERSEDED}
    out = []
    for name, code, desc, flip in MARKINGS:
        if code not in rows:
            continue
        out.append(dict(name=name, route='markings/cad', label=desc, description=desc, kind='vis', units='ft',
                        flip_x=flip, radius=2.0, conditions=list(CONDITIONS), placement=rows[code].get('placement'),
                        states=[dict(state=name[4:], code=code, file=f"markings/cad/{rows[code]['file']}")]))
    for code, r in rows.items():      # every pavement word and numeral: its own small block
        if r['group'] in ('Words', 'Numerals') and code.startswith('CT-'):
            word = re.sub(r'^CT-A24[A-Z]-', '', code)
            name = 'SSS-' + ('NUMERAL-' + word.split('-')[-1] if r['group'] == 'Numerals' else 'WORD-' + word)
            desc = r['name'].split(' · ')[0] + f" (Caltrans {code[3:7]})"
            out.append(dict(name=name, route='markings/cad', label=desc, description=desc, kind='vis', units='ft',
                            flip_x=None, radius=2.0, conditions=list(CONDITIONS), placement=r.get('placement'),
                            states=[dict(state=name[4:], code=code, file=f"markings/cad/{r['file']}")]))
    for a in ARRAYS:
        green = a.get('green')
        out.append(dict(name=a['name'], route='markings/cad', label=a['description'], description=a['description'],
                        kind='array', units='ft', flip_x=None, radius=2.0,
                        conditions=list(PAINT if green else CONDITIONS),
                        placement=XING_PLACE if green else CROSSWALK_PLACE, axis=a['axis'], length=a['length'],
                        width=a.get('width'), states=[dict(state=a['name'][4:], **{k: a[k] for k in
                                                     ('unit', 'lines', 'spacing', 'green', 'edges', 'width') if k in a})]))
    return out


ES_PAIR = re.compile(r'^(CT-ES1[ABC])-(N|E)-?(.+)$')


def plain(label):
    """'New city electrolier (future)' -> 'CITY-ELECTROLIER-FUTURE': a short, plain block name."""
    text = re.sub(r'^(new|existing|proposed)\s+', '', label.split(' · ')[0], flags=re.I)
    text = re.sub(r'\([^)]*\)|,.*$|\bsee\b.*$', '', text, flags=re.I)   # drop notes: (survey), (future ...), see ...
    words, out = slug(text).split('-'), []
    for w in words:
        if len('-'.join(out + [w])) > 32:
            break
        out.append(w)
    return '-'.join(out)


def signal_families(section):
    """Caltrans ES-1 symbols come as new and existing pairs: one block, states PROPOSED and EXISTING.
    Every other static signal, lighting and survey symbol: its own block with a rotation grip."""
    rows = {r['code']: r for r in section['blocks'] if not r.get('dynamic') and r['code'] not in SUPERSEDED
            and not r['code'].startswith('SSS-')}
    pairs = OrderedDict()
    for c in rows:
        m = ES_PAIR.match(c)
        if m:
            pairs.setdefault((m[1], m[3]), {})[m[2]] = c
    out, used, names = [], set(), set()

    def unique(n):
        base, k = n, 2
        while n in names:
            n, k = f'{base}-{k}', k + 1
        names.add(n)
        return n
    for (sheet, item), sides in pairs.items():
        if set(sides) != {'N', 'E'}:
            continue
        used |= set(sides.values())
        r = rows[sides['N']]
        auto = plain(r['name'])
        name = 'SSS-' + RENAME.get(auto, auto)
        for k in (2, 3, 4):
            if name not in names:
                break
            name = 'SSS-' + RENAME.get(f'{auto}-{k}', f'{auto}-{k}')
        name = unique(name)
        desc = re.sub(r'^New\s+', '', r['name'].split(' · ')[0]).capitalize() + f' (Caltrans {sheet[3:]} {item})'
        out.append(dict(name=name, route='signals/cad', label=desc, description=desc, kind='vis', units='in',
                        flip_x=None, radius=0.15, conditions=None,
                        states=[dict(state=st, code=sides[k], file=f"signals/cad/{rows[sides[k]]['file']}")
                                for st, k in (('PROPOSED', 'N'), ('EXISTING', 'E'))]))
    # remaining Caltrans items whose descriptions say New ... and Existing ...: also one block
    by_label = OrderedDict()
    for c, r in rows.items():
        m = re.match(r'^(New|Existing)\s+(.+)$', r['name'].split(' · ')[0])
        if c.startswith('CT-ES') and c not in used and m:
            by_label.setdefault(m[2].lower(), {})[m[1][0]] = c
    for text, sides in by_label.items():
        if set(sides) != {'N', 'E'}:
            continue
        used |= set(sides.values())
        auto = plain(rows[sides['N']]['name'])
        name = unique('SSS-' + RENAME.get(auto, auto))
        desc = text.capitalize() + f" (Caltrans {sides['N'][3:7]})"
        out.append(dict(name=name, route='signals/cad', label=desc, description=desc, kind='vis', units='in',
                        flip_x=None, radius=0.15, conditions=None,
                        states=[dict(state=st, code=sides[k], file=f"signals/cad/{rows[sides[k]]['file']}")
                                for st, k in (('PROPOSED', 'N'), ('EXISTING', 'E'))]))
    for c, r in rows.items():
        if c in used:
            continue
        units = 'in' if c.startswith('CT-ES') else 'ft'
        auto = plain(r['name'])
        name = 'SSS-' + RENAME.get(auto, auto)
        if name in names:
            auto2 = f'{auto}-2'
            name = 'SSS-' + RENAME.get(auto2, auto2)
            if name in names:
                auto3 = f'{auto}-3'
                name = 'SSS-' + RENAME.get(auto3, auto3)
        name = unique(name)
        desc = r['name'].split(' · ')[0] + (f' (Caltrans {c[3:7]})' if c.startswith('CT-ES') else '')
        out.append(dict(name=name, route='signals/cad', label=desc, description=desc, kind='vis', units=units,
                        flip_x=None, radius=0.15 if units == 'in' else 1.0, conditions=None,
                        states=[dict(state=name[4:], code=c, file=f"signals/cad/{r['file']}")]))
    return out


# Plain names where the drawing's own description is a sentence (auto name -> short name)
RENAME = {
    'VEHICLE-SIGNAL-HEAD-CONSISTING': 'SIGNAL-HEAD-RYG', 'VEHICLE-SIGNAL-HEAD-CONSISTING-2': 'SIGNAL-HEAD-LEFT-ARROW',
    'VEHICLE-SIGNAL-HEAD-CONSISTING-3': 'SIGNAL-HEAD-RY-GREEN-ARROW', 'VEHICLE-SIGNAL-HEAD-WITH-ANGLE': 'SIGNAL-HEAD-ANGLE-VISOR',
    'PEDESTRIAN-SIGNAL-HEAD': 'PED-SIGNAL-HEAD',
    'TYPE-21TS-STANDARD-WITH-VEHICLE': 'STANDARD-TYPE-21TS', 'TYPE-15TS-STANDARD-WITH-VEHICLE': 'STANDARD-TYPE-15TS',
    'STANDARD-WITH-LUMINAIRE-AND': 'STANDARD-MAST-ARM-LUMINAIRE', 'STANDARD-WITH-A-SIGNAL-MAST-ARM': 'STANDARD-MAST-ARM',
    'TYPE-1-STANDARD-WITH-ATTACHED': 'STANDARD-TYPE-1', 'OPTICAL-DETECTOR-FOR-THE': 'OPTICAL-DETECTOR',
    'DETECTION-DEVICE-M-MICROWAVE': 'DETECTION-DEVICE', 'MICROWAVE-OR-VIDEO-DETECTION': 'DETECTION-ZONE',
    'TYPE-A-LOOP-DETECTOR-OUTLINE-OF': 'LOOP-TYPE-A', 'TYPE-B-LOOP-DETECTOR-OUTLINE-OF': 'LOOP-TYPE-B',
    'TYPE-C-LOOP-DETECTOR-OUTLINE-OF': 'LOOP-TYPE-C', 'TYPE-D-LOOP-DETECTOR-OUTLINE-OF': 'LOOP-TYPE-D',
    'TYPE-Q-LOOP-DETECTOR-OUTLINE-OF': 'LOOP-TYPE-Q', 'ROADWAY-SENSOR': 'ROADWAY-SENSOR',
    'FLASHING-BEACON-WITH-TYPES-9': 'FLASHING-BEACON-TYPE-9', 'FLASHING-BEACON-R-INDICATES-RED': 'FLASHING-BEACON',
    'FLASHING-BEACON-WITH-TYPE-15-FBS': 'FLASHING-BEACON-TYPE-15', 'CONDUIT-RISER-ATTACHED-TO-THE': 'CONDUIT-RISER',
    'SERVICE-EQUIPMENT-ENCLOSURE-TYPE': 'SERVICE-ENCLOSURE-TYPE-III', 'UTILITY-TRANSFORMER-GROUND': 'UTILITY-TRANSFORMER',
    'DOUBLE-POST': 'SIGN-STRUCTURE-DOUBLE-POST', 'DOUBLE-POST-2': 'SIGN-STRUCTURE-DOUBLE-POST-LIGHT',
    'SINGLE-POST': 'SIGN-STRUCTURE-BUTTERFLY-2-SIGNS', 'SINGLE-POST-2': 'SIGN-STRUCTURE-BUTTERFLY',
    'SINGLE-POST-3': 'SIGN-STRUCTURE-CANTILEVER-LIGHT', 'SINGLE-POST-4': 'SIGN-STRUCTURE-CANTILEVER',
    'SINGLE-SIGN-MOUNTED-ON-STRUCTURE': 'SIGN-ON-STRUCTURE',
    '15-STRUCTURE': 'LIGHTING-STRUCTURE-15', '15D-STRUCTURE': 'LIGHTING-STRUCTURE-15D',
    '21-STRUCTURE': 'LIGHTING-STRUCTURE-21', '21D-STRUCTURE': 'LIGHTING-STRUCTURE-21D',
    'NON-STANDARD-ELECTROLIER': 'ELECTROLIER-NON-STANDARD', 'ELECTROLIER-FOUNDATION': 'ELECTROLIER-FOUNDATION-FUTURE',
    'ABANDON-IF-APPLIED-TO-CONDUIT': 'ABANDON', 'EQUIPMENT-OR-MATERIAL-TO-BE': 'REMOVE-EQUIPMENT',
    'CONDUIT-TO-REMAIN-FOR-FUTURE-USE': 'CONDUIT-FUTURE-USE', 'CONNECT-NEW-AND-EXISTING-CONDUIT': 'CONDUIT-CONNECT',
    'INSTALL-PULL-BOX-IN-EXISTING': 'PULL-BOX-IN-CONDUIT', 'INSTALL-CONDUIT-INTO-EXISTING': 'CONDUIT-INTO-PULL-BOX',
    'SPLICE-NEW-TO-EXISTING': 'SPLICE', 'SOFFIT-OR-WALL-MOUNTED-LUMINAIRE': 'SOFFIT-LUMINAIRE-MODIFY',
    'SOFFIT-OR-WALL-MOUNTED-LUMINAIRE-2': 'SOFFIT-LUMINAIRE-REMAIN', 'CONTACTOR': 'CONTACTOR-NC', 'CONTACTOR-2': 'CONTACTOR-NO',
    'PEDESTRIAN-BARRICADE-2': 'PED-BARRICADE-AS-NOTED', 'PEDESTRIAN-BARRICADE': 'PED-BARRICADE',
    'NOTE-FLAG-WITH-ATTRIBUTE': 'NOTE-FLAG', 'BOXED-NOTE-WITH-ATTRIBUTE': 'NOTE-BOX',
    'STANDARD-NUMBER-CIRCLE-WITH': 'NOTE-STANDARD-NUMBER', 'POST-WITH-PUSH-BUTTON': 'PUSH-BUTTON-POST',
    'CONTROLLER-ASSEMBLY': 'CONTROLLER', 'INSTALL-SIGN-ON-SIGNAL-MAST-ARM': 'SIGN-ON-MAST-ARM',
}

DIRECTION = {'L': 'LEFT', 'R': 'RIGHT', '(LT)': 'LEFT TURN', '(RT)': 'RIGHT TURN'}


def side_name(code):
    """R3-5(R) and R3-5R are the same variant from two libraries: one state name per variant."""
    m = SIDE.match(code)
    if not m:
        return 'STANDARD'
    side = m['p'] or m['s']
    return DIRECTION.get(side if side in ('L', 'R') else f'({side})', 'STANDARD')


def prefer(rec):
    return ('unknown' in rec.get('sizeStatus', '').lower(), '[' in rec['file'], rec['file'])


def sign_families():
    if not SIGNS.exists():
        return []
    recs = json.loads(SIGNS.read_text())['records']
    groups = OrderedDict()
    for r in recs:
        m = SIDE.match(r['code'])
        base = re.sub(r'\s+', '', m['base']) if m else re.sub(r'\s+', '', r['code'])
        groups.setdefault(base, []).append(r)
    out = []
    for base, members in groups.items():
        if not any(SIDE.match(r['code']) for r in members):
            continue
        best = OrderedDict()
        for r in sorted(members, key=prefer):
            best.setdefault(side_name(r['code']), r)
        if len(best) < 2:
            continue
        states = sorted((dict(state=k, code=r['code'], id=r['id']) for k, r in best.items()),
                        key=lambda s: ['STANDARD', 'LEFT', 'RIGHT', 'LEFT TURN', 'RIGHT TURN'].index(s['state'])
                        if s['state'] in DIRECTION.values() or s['state'] == 'STANDARD' else 9)
        name = 'SSS-SIGN-' + slug(base)
        out.append(dict(name=name, route='signs/cad', label=f'{base} sign', description=f'{base} sign, every direction (FHWA SHS / CA MUTCD)',
                        kind='vis', units='in', flip_x=None, radius=0.25, conditions=None,
                        placement='Base at the sign face bottom center (the post)', states=states))
    speeds = OrderedDict()
    for r in sorted(recs, key=prefer):
        m = re.fullmatch(r'R2-1(?:\((\d+)\)|(\d\d))?', r['code'])
        if m:
            speeds.setdefault(int(m[1] or m[2] or 0), r)
    if len(speeds) > 1:
        out.append(dict(name='SSS-SIGN-R2-1-SPEED', route='signs/cad', label='R2-1 speed limit',
                        description='R2-1 speed limit, every posted speed (FHWA SHS / CA MUTCD)', kind='vis',
                        units='in', flip_x=None, radius=0.25, conditions=None,
                        placement='Base at the sign face bottom center (the post)',
                        states=[dict(state='BLANK' if v == 0 else f'{v} MPH', code=r['code'], id=r['id'])
                                for v, r in sorted(speeds.items())]))
    return out


def families():
    catalog = json.loads(CATALOG.read_text())
    fams = marking_families(catalog['markings/cad']) + signal_families(catalog['signals/cad']) + sign_families()
    for f in fams:
        f.setdefault('kind', 'vis')
        for s in f['states']:
            s['block'] = f['name'] + '$' + slug(s['state'])
    return fams


def write():
    fams = families()
    OUT.write_text(json.dumps(dict(
        note='Each family: one visibility state per variant (and per condition: proposed, existing, remove), a rotation '
             'about the shared base point; array families add a length grip. Lane arrows also flip about the lane center. '
             'Text, symbols and signs never flip, because a flip mirrors them.',
        families=fams), indent=1) + '\n')
    return fams


SOURCE = Path('public/downloads/cad-tools/SSS-DYNAMIC-SOURCE.dwg')
README = """SSS dynamic block build (v2)

1. Open SSS-DYNAMIC-SOURCE.dwg in AutoCAD (2018 or later).
2. APPLOAD SSS-DYNBUILD.lsp.
3. Run SSSDYNTEST (three sample families) or SSSDYNBUILD (every family).
4. Each family gets a PASS or FAIL line in SSS-DYNBUILD.log beside the drawing; the finished
   dynamic block is placed at the end of its row on the review sheet.
5. Save the drawing and send it back with the log.
"""


def package(root=None):
    """Zip the source drawing (built by dynamic_source.py), the build routine and the steps."""
    with zipfile.ZipFile(PACKAGE, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(SOURCE, SOURCE.name)
        z.write(LISP, LISP.name)
        z.writestr('README.txt', README.replace('\n', '\r\n'))
    return len(json.loads(OUT.read_text())['families'])


if __name__ == '__main__':
    fams = write()
    print(len(fams), 'families,', sum(len(f['states']) for f in fams), 'states')
