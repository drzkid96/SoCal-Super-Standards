"""Check table coverage, source/edition provenance and physical dimension regression cases."""
from collections import Counter
from pathlib import Path
import json
from math import dist, isclose

from lookup import key, resolve, read_index

OUT=Path(__file__).resolve().parent
SITE=OUT.parents[2] if OUT.parent.name=='reference' else OUT.parents[1]/'site'
CAD_DIR=SITE.parent/'cad-working'
index=read_index()
all_rows=index['tableRows']
records=index['records']

# The 32 sign-size tables listed in the 2026 manual's contents, pp. 51–53.
table_base='2B-1 2C-1 2D-1 2E-1 2F-1 2G-1 2H-1 2I-1 2N-1 6G-1 6H-1 6I-1 7B-1 8B-1 9A-1'.split()
appendix_base='2B-1 2C-1 2D-1 2E-1 2F-1 2G-1 2H-1 2I-1 2J-101 2K-101 2M-101 6G-1 6H-1 6I-1 7B-1 8B-1 9A-1'.split()
expected_ca=set(table_base)|{t+'(CA)' for t in appendix_base}
assert {r['table'] for r in all_rows.values() if r['publisher']=='Caltrans'}==expected_ca
assert {r['table'] for r in all_rows.values() if r['publisher']=='FHWA'}==set(table_base)
assert all(r['columns'] and r['url'].endswith('#page='+str(r['page'])) for r in all_rows.values())
for code,r in records.items():
    assert all(i in all_rows for i in r['sizeRows']),code
    if r['size']:
        assert min(r['size'])>0 and len(r['size']) in (2,3),code
        assert r['source']['publisher']=='Caltrans' and len(r['sizeRows'])>0,code
        assert 'MOD' not in code,code
    if r.get('panelAuthorization'):
        assert r['status']=='published-panel-variant' and r['sizeProvenance']=='published-variable-face'
        assert r.get('referenceFace') is None and r['panelAuthorization']['source'].startswith('https://')
    if r['status'] in ('modified-project-design','retired-in-california','federal-size-only'):
        assert not r['size'] and not r['nominalBounds']
    face=r.get('referenceFace')
    if face and face.get('asset'):
        assert (SITE/'public'/face['asset'].lstrip('/')).is_file(),code
    geom=r.get('panelGeometry') or {}
    vertices=geom.get('verticesInches')
    if vertices:
        assert vertices[0]==vertices[-1],code
        width,height=r['nominalBounds']
        assert max(p[0] for p in vertices)==width and max(p[1] for p in vertices)==height,code
        sides=[dist(a,b) for a,b in zip(vertices,vertices[1:])]
        if r['sizeBasis']=='triangle-sides':
            assert all(isclose(a,b,abs_tol=.00015) for a,b in zip(sorted(sides),sorted(r['size']))),code
        if r['sizeBasis']=='diamond-side-lengths':
            assert all(isclose(a,r['size'][0],abs_tol=.00015) for a in sides),code

def check(code,size,bounds):
    r=records[key(code)]
    assert (r['size'],r['nominalBounds'])==(size,bounds),(code,r)
check('R1-1',[30,30],[30,30])
assert records['R1-1']['columns']['Conventional Road Multi-Lane']=='36 x 36'
check('R1-2',[36,36,36],[36,31.1769])
check('W14-3',[48,48,36],[44.4972,36])
check('W11-2',[30,30],[42.4264,42.4264])
check('W10-1',[36,36],[36,36])
check('R99C(CA)',[12,24],[12,24])
for face in json.loads((SITE/'data/signs/signs.json').read_text()):
    if face.get('artworkSource')=='caltrans-specification':
        actual=records[key(face['code'])]['referenceFace']
        assert actual['type']=='caltrans-specification-face' and actual['source']==face['sourceUrl'] and actual['asset']==face['svg']
assert records[key('R111(CA)')]['source']['table']=='6G-1(CA)'
assert records[key('SC3(CA)')]['source']['table']=='6I-1(CA)'
assert records[key('G96AP(CA)')]['source']['table']=='8B-1(CA)'
assert records['S1-1']['source']['table']=='7B-1'
for k,outer in [('SW24-2(CA)','36 x 54'),('SW24-3(CA)','36 x 36')]:
    sign=records[key(k)]
    assert sign['size'] is None and sign['faceSizeOptions']['options']==[[30,42],[36,48],[48,60]]
    row=all_rows[sign['assemblySizeRows'][0]]
    assert row['dimensionScope']=='assembly' and row['columns']['Conventional Road']==outer
assert records[key('SR4-1(CA)')]['size']==[36,72]
assert records[key('SW24-1(CA)')]['size']==[36,48]
assert records['R10-3']['size']==[9,12]
assert records['W11-2']['sizeNote']['source'].endswith('#page=381')
assert records['I20-1']['size'] is None and records['I20-1']['sizeNote']['requiresProjectSelection']
assert records['D5-1']['size'] is None and records['D5-1']['sizeRows']
assert records['R10-16']['size'] is None and records['R10-16']['status']=='federal-size-only'
assert set(v['dimensions'][1] for v in records['CAL-ITRA']['cadDimensionEvidence'])=={18,36}
assert resolve('R2-1-45',records)['panelAuthorization']['type']=='variable-numerals'
assert resolve('R2-1-45 (MOD)',records)['size'] is None
assert resolve('unidentified project sign',records)['referenceFace'] is None
for row in json.loads((SITE/'data/reference/plan-examples/3346-sign-records.json').read_text()):
    assert key(row['designation']) in records,row['designation']
for file in (CAD_DIR/'block-inputs').glob('*.json'):
    for row in json.loads(file.read_text()):
        if isinstance(row,dict) and row.get('code'):
            assert key(row['code']) in records,(file.name,row['code'])
print(f'{len(records)} designations; {len(all_rows)} rows; {sum(bool(r["size"]) for r in records.values())} selected sizes')
print(dict(Counter(r['publisher'] for r in all_rows.values())))
print(dict(Counter(r['status'] for r in records.values())))
