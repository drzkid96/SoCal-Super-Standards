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
import csv
import io
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


def marking_families(section):
    rows = {r['code']: r for r in section['blocks'] if not r.get('dynamic')}

    def pick(test):
        return [c for c in rows if test(c, rows[c])]
    fams = OrderedDict()
    fams['PM-LANE-ARROW-DYN'] = ('Lane-use arrow, every Caltrans A24A/A24B type',
                                 pick(lambda c, r: r['group'] == 'Arrows'))
    fams['PM-WORD-DYN'] = ('Pavement word, every Caltrans A24D/A24E word', pick(
        lambda c, r: r['group'] == 'Words' and c.startswith('CT-') and c != 'CT-A24D-STOP'))
    fams['PM-NUMERAL-DYN'] = ('Numeral 0 to 5, Caltrans A24C', pick(lambda c, r: r['group'] == 'Numerals'))
    fams['PM-LEGEND-DYN'] = ('Two-line legend (KEEP CLEAR, BUS ONLY, WAIT HERE)',
                             pick(lambda c, r: c in ('PM-KEEP-CLEAR', 'PM-BUS-ONLY', 'PM-WAIT-HERE')))
    fams['PM-BIKE-XING-GREEN-DYN'] = ('Green bike crossing dash, 5 to 8 ft bike lane',
                                      pick(lambda c, r: c.startswith('PM-BIKE-XING-GREEN')))
    fams['PM-BIKE-LANE-MARKING-DYN'] = ('Bike lane symbol or arrow, Caltrans and LA plan versions', pick(
        lambda c, r: r['group'] == 'Bicycle markings' and not c.startswith('PM-BIKE-XING') and c not in
        ('CT-A24C-SHARROW', 'PM-BIKE-LANE-SYMBOL-GREEN')))
    fams['PM-CROSSWALK-DYN'] = ('Crosswalk, every Caltrans A24F type', pick(lambda c, r: r['group'] == 'Crosswalks'))
    fams['PM-RAISED-ELEMENT-DYN'] = ('Left turn calming 3 or 10 ft', pick(lambda c, r: c.startswith('PM-LEFT-TURN-CALMING')))
    return [dict(name=n, route='markings/cad', label=l, states=[dict(state=s.replace('CT-', '').replace('PM-', ''), code=s,
                                                                   file=f'markings/cad/{rows[s]["file"]}') for s in codes])
            for n, (l, codes) in fams.items() if len(codes) > 1]


def sign_families():
    if not SIGNS.exists():
        return []
    recs = json.loads(SIGNS.read_text())['records']
    groups = OrderedDict()
    for r in recs:
        m = SIDE.match(r['code'])
        base = m['base'].strip() if m else r['code']
        groups.setdefault(base, []).append(r)
    speed = [r for r in recs if re.fullmatch(r'R2-1(\(\d+\))?', r['code'])]
    out = []
    for base, members in groups.items():
        sides = [r for r in members if SIDE.match(r['code'])]
        if not sides or len({r['code'] for r in members}) < 2:
            continue
        seen, states = set(), []
        for r in members:
            if r['code'] in seen:
                continue
            seen.add(r['code'])
            states.append(dict(state=r['code'], code=r['code'], id=r['id']))
        name = 'SN-' + re.sub(r'[^A-Z0-9]+', '-', base.upper()).strip('-') + '-DYN'
        out.append(dict(name=name, route='signs/cad', label=f'{base} sign, left and right versions', states=states))
    first = OrderedDict((r['code'], r) for r in reversed(speed))
    speed = sorted(first.values(), key=lambda r: int(re.sub(r'\D', '', r['code'][4:]) or 0))
    if len(speed) > 1:
        out.append(dict(name='SN-R2-1-SPEED-DYN', route='signs/cad', label='R2-1 speed limit, every posted speed',
                        states=[dict(state=r['code'], code=r['code'], id=r['id']) for r in speed]))
    return out


def families():
    catalog = json.loads(CATALOG.read_text())
    return marking_families(catalog['markings/cad']) + sign_families()


def write():
    fams = families()
    OUT.write_text(json.dumps(dict(
        note='Each family: visibility states (one per variant), rotation, flip X and flip Y about the shared base point.',
        families=fams), indent=1) + '\n')
    return fams


def manifest_csv(fams):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\r\n')
    w.writerow(['family', 'state', 'file', 'label'])
    for f in fams:
        for s in f['states']:
            w.writerow([f['name'], s['state'], s['file'].replace('/', '\\'), f['label']])
    return buf.getvalue()


def package(root=None):
    """Zip the build routine, the manifest and every state drawing (run after sign blocks hydrate)."""
    fams = json.loads(OUT.read_text())['families']
    downloads = Path('public/downloads')
    hydrated = downloads / 'sign-blocks/manifest.json'      # sign files get their published paths at hydrate
    by_id = {r['id']: 'sign-blocks/' + r['file'] for r in json.loads(hydrated.read_text())['records']} if hydrated.exists() else {}
    for f in fams:
        for s in f['states']:
            if 'id' in s:
                if s['id'] not in by_id:
                    raise ValueError(f'sign block {s["id"]} is not published')
                s['file'] = by_id[s['id']]
    with zipfile.ZipFile(PACKAGE, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(LISP, LISP.name)
        z.writestr('SSS-DYNBUILD-MANIFEST.csv', manifest_csv(fams))
        z.writestr('README.txt', 'Unzip, open a new drawing (feet), APPLOAD SSS-DYNBUILD.lsp, run SSSDYNBUILD and pick '
                   'SSS-DYNBUILD-MANIFEST.csv. Run SSSDYNTEST first to build one family as a check.\r\n'
                   'Output: the OUT folder beside the manifest, one DWG per family. Upload that folder to SSS.\r\n')
        done = set()
        for f in fams:
            for s in f['states']:
                src = downloads / s['file']
                if s['file'] in done:
                    continue
                if not src.is_file():
                    raise ValueError(f'missing state drawing {src}')
                z.write(src, s['file'])
                done.add(s['file'])
    return len(fams)


if __name__ == '__main__':
    fams = write()
    print(len(fams), 'families,', sum(len(f['states']) for f in fams), 'states')
