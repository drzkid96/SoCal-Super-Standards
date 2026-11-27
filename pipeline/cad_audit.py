"""Hygiene audit of every published DWG: python3 pipeline/cad_audit.py --libredwg <dir> [--json out.json]

Reads each file back with LibreDWG and checks the SSS conventions:
  - version: AC1015 (AutoCAD 2000); dynamic blocks and plan libraries AC1032 (2018)
  - model space holds block inserts only (signs: one insert plus its MTEXT code; libraries: many)
  - each single-block file: block name = file name, insert at 0,0
  - insert layer in the family's set; block geometry on layer 0 or Defpoints (dynamic state layers allowed)
  - header: dimension style and text style exist, units set
  - geometry: no zero-length lines or polylines, no repeated vertices, no empty blocks
  - names: letters, digits and hyphens, no spaces in file or folder names
"""
import argparse
import collections
import concurrent.futures as cf
import json
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf

ROOT = Path('public/downloads')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]$')   # sign codes keep their case (W4-2l)
INSERT_LAYERS = {'P-PMARK', 'P-STRP', 'E-SITE', 'E-SITE-TEXT', 'P-SIGN-TEXT', 'P-SIGN', 'P-SIGNAL', 'P-SIGNAL-TEXT', 'P-PMARK-TEXT', 'P-SIGN-TEXT', 'P-SIGN-TABL', 'P-SIGN-TITL'}
BLOCK_LAYERS = {'0', 'Defpoints'} | {f'{s}-{d}' for s in 'EPRA' for d in ('PMARK', 'SIGNAL', 'SITE', 'SIGN')}
LIBRARIES = {'SSS-PMARK-LIBRARY', 'SSS-SIGNAL-LIBRARY', 'SSS-STRIPING-PLAN-LIBRARY', 'SSS-SIGNAL-PLAN-LIBRARY',
             'SSS-SURVEY-LIBRARY', 'MASTER'}
DYNAMIC_LIBRARIES = {'SSS-STRIPING-PLAN-LIBRARY', 'SSS-SIGNAL-PLAN-LIBRARY', 'SSS-SURVEY-LIBRARY'}


def audit(path, libredwg):
    issues = []
    rel = path.relative_to(ROOT)
    for part in rel.parts:
        if ' ' in part:
            issues.append('space in path')
            break
    version = path.read_bytes()[:6].decode('ascii', 'replace')
    dynamic = path.stem.endswith('-DYN') or path.stem in DYNAMIC_LIBRARIES
    if version != ('AC1032' if dynamic else 'AC1015'):
        issues.append(f'version {version}')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'a.dxf'
        subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', out, path], capture_output=True)
        try:
            doc = ezdxf.readfile(out)
        except Exception as ex:
            return str(rel), [f'unreadable: {ex}'[:120]]
    msp = list(doc.modelspace())
    types = collections.Counter(e.dxftype() for e in msp)
    inserts = [e for e in msp if e.dxftype() == 'INSERT']
    library = path.stem.upper() in LIBRARIES
    if not library:
        extra = set(types) - {'INSERT', 'MTEXT'}
        if extra or len(inserts) != 1:
            issues.append(f'model space {dict(types)}')
        if inserts:
            ins = inserts[0]
            # sign blocks keep their source names (they match the master and legend exports)
            if ins.dxf.name.upper() != path.stem.upper() and 'sign-blocks' not in str(rel):
                issues.append(f'block {ins.dxf.name} != file')
            if any(abs(v) > 1e-9 for v in ins.dxf.insert) and 'sign-blocks' not in str(rel):
                issues.append('insert not at 0,0')
    for ins in inserts:
        if ins.dxf.layer not in INSERT_LAYERS:
            issues.append(f'insert layer {ins.dxf.layer}')
            break
    if not NAME.match(path.stem) and path.stem != 'master':
        issues.append('file name form')
    if doc.header.get('$DIMSTYLE', 'Standard') not in doc.dimstyles:
        issues.append('header dimstyle missing')
    if doc.header.get('$TEXTSTYLE', 'Standard') not in doc.styles:
        issues.append('header text style missing')
    if doc.header.get('$INSUNITS', 0) == 0:
        issues.append('units unset')
    for block in doc.blocks:
        if block.is_any_layout or block.name.startswith(('*', '_')):
            continue
        ents = list(block)
        if not ents:
            issues.append(f'empty block {block.name}')
        for e in ents:
            if e.dxf.layer not in BLOCK_LAYERS:
                issues.append(f'block layer {e.dxf.layer}')
                break
        for e in ents:
            t = e.dxftype()
            if t == 'LINE' and (e.dxf.start - e.dxf.end).magnitude < 1e-6:
                issues.append('zero-length line')
                break
            if t == 'LWPOLYLINE':
                pts = [tuple(round(v, 6) for v in p[:2]) for p in e.get_points()]
                if any(a == b for a, b in zip(pts, pts[1:])):
                    issues.append('repeated vertex')
                    break
    return str(rel), sorted(set(issues))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--libredwg', type=Path, required=True)
    parser.add_argument('--json')
    args = parser.parse_args()
    files = sorted(ROOT.rglob('*.dwg'))
    results = {}
    with cf.ThreadPoolExecutor(8) as pool:
        for rel, issues in pool.map(lambda p: audit(p, args.libredwg), files):
            results[rel] = issues
    tally = collections.Counter(i.split(' ')[0] if i.startswith(('block', 'insert', 'model', 'version', 'unreadable')) else i
                                for v in results.values() for i in v)
    bad = {k: v for k, v in results.items() if v}
    print(f'{len(files)} files, {len(bad)} with issues')
    for issue, n in tally.most_common():
        print(f'  {n:5d}  {issue}')
    by_family = collections.Counter(k.split('/')[0] + '/' + k.split('/')[1] for k in bad)
    print(dict(by_family))
    if args.json:
        Path(args.json).write_text(json.dumps(bad, indent=1))
