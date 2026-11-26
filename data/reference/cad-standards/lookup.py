"""Resolve published sign designations without guessing dimensions for project variants."""
from pathlib import Path
import gzip
import json
import re

FILE = Path(__file__).with_name('sign-standards.json')
if not FILE.is_file():
    FILE = FILE.with_suffix('.json.gz')

def read_index():
    if FILE.suffix=='.gz':
        with gzip.open(FILE,'rt',encoding='utf-8') as stream:
            return json.load(stream)
    return json.loads(FILE.read_text())
def key(label):
    text=str(label).strip().upper().translate(str.maketrans({'–':'-','—':'-','‑':'-','−':'-'}))
    text=re.sub(r'\(([^()]*)\)',lambda m:'CA' if m[1].strip()=='CA' else '-'+m[1].strip().replace(' ','-'),text)
    text=re.sub(r'[\s-]*\bMOD(?:IFIED)?\b[\s-]*','-MOD-',text)
    text=re.sub(r'(?<=[0-9A-Z])MOD(?=$|[ -])','-MOD',text)
    text=re.sub(r'-(LT|RT)(?=-|$)',lambda m:'-LEFT' if m[1]=='LT' else '-RIGHT',text)
    if re.fullmatch(r'(?:[A-Z]\.)+[A-Z]\.?',text):text=text.replace('.','')
    return re.sub(r'\s','',text).strip('-')

CA='https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/camutcd-2026-all.pdf'
SHS14='https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf'

# FHWA layout sheets name and draw both handed variants. Multi-sheet entries
# give the left and right layouts in that order. R9-3bP uses CA text authority.
HANDED_LAYOUTS = {
    'R3-5': (74, 74), 'R3-6': (83, 82), 'R3-7': (87, 86),
    'R6-1': (242, 241), 'R6-2': (243, 243), 'W1-1': (443, 443),
    'W1-2': (444, 444), 'W1-3': (445, 445), 'W1-4': (446, 446),
    'W1-6': (448, 448), 'W4-2': (484, 484), 'W9-1': (554, 554),
    'W16-7P': (647, 647), 'R9-11': (699, 699), 'R9-11A': (700, 700)
}
def variant_authority(label):
    speed = re.fullmatch(r'(R2-1|W13-1P)-([0-9]{1,2})', label)
    if speed:
        page = 41 if speed[1]=='R2-1' else 618
        return speed[1], {'type':'variable-numerals','source':SHS14+'#page='+str(page),
                          'evidence':'FHWA layout provides variable numeral spacing on a dimensioned base panel.'}
    match = re.fullmatch(r'(.+?)(?:-(LEFT|RIGHT)|-?([LR]))', label)
    if not match:
        return None, None
    base, full, short = match.groups()
    if base=='R9-3BP':
        return base, {'type':'directional-arrow','source':CA+'#page=213',
                      'evidence':'CA MUTCD Section 2B.57 paragraph 05 specifies that the arrow designates the direction of the crossing.'}
    if base not in HANDED_LAYOUTS:
        return None, None
    page = HANDED_LAYOUTS[base][0 if (full or short).startswith('L') else 1]
    return base, {'type':'handed-layout','source':SHS14+'#page='+str(page),
                  'evidence':'FHWA labels the handed variant on the dimensioned standard sign layout.'}

def variant_record(label,records):
    base,authority=variant_authority(key(label))
    b=records.get(base)
    if not b or not b['size']:
        return None
    return {'standardCode':b['code'],'status':'published-panel-variant','size':b['size'],'sizeBasis':b['sizeBasis'],
            'condition':b['condition'],'sizeNote':b.get('sizeNote'),'columns':b['columns'],'source':b['source'],'sizeRows':b['sizeRows'],
            'referenceFace':None,'familyReference':b['referenceFace'],'panelAuthorization':authority,
            'sizeProvenance':'published-variable-face','nominalBounds':b.get('nominalBounds'),'panelGeometry':b.get('panelGeometry'),
            'notes':'Variable speed legend or handed face. The published row sizes the base panel. Use the observed variant artwork.'}

def resolve(label, records):
    direct=records.get(key(label))
    if direct is not None:
        return direct
    return {'code':label,'cadDimensionEvidence':[],**(variant_record(label,records) or {
        'status':'modified-project-design' if 'MOD' in key(label) else 'unresolved-designation','standardCode':None,'size':None,'sizeBasis':None,
        'condition':None,'source':None,'columns':{},'referenceFace':None,'sizeRows':[],
        'nominalBounds':None,'panelGeometry':None,'sizeProvenance':None,
        'notes':'No exact published designation was located.'})}

def load():
    return read_index()['records']
