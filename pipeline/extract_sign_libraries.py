"""Extract literal sign specimens from the two CAD libraries without exploding source drawings.

Rebuild from the normalized DXFs with:
  python pipeline/extract_sign_libraries.py <cad-working>
The MUTCD chart cells are resolved by extract_mutcd_library_faces.py.
"""
import argparse
import json
import re
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import ezdxf
from ezdxf import bbox

FP = 'fp-signs'
MUTCD = 'mutcd-standard-signs'
CHART_COMPONENTS = set('Airplane Arrwsym Baricade Bikesym Buslines Bussym Dntwlksy Dsignarr Farmmach Flagrsym Handicap Manwalk Nosymbol Pedbike Pedsymbl Schsymbl Stopflap Tm_max Trucksym Typek Flagger Bike-rr Litter'.upper().split())
CODE = re.compile(r'(?:CAL-[A-Z0-9-]+|NLU-[0-9]+|(?:[A-Z]{1,3}[0-9]+[A-Z]*|OM)[A-Z0-9-]*(?:\s*\([^)]*\))*|(?:SIGN SP-[0-9]+)|W3 - SPECIAL|\*?NWZ-2|CUSTOM CITYWIDE NO PARKING SIGN|NEIGHBORHOOD WATCH)(?:\s*)$', re.I)
IGNORE_LABEL = {'T1', '3C', '2C', '1C', '4C', '99W'}
PANEL_SKIP = {'DIMENSION', 'POINT', 'VIEWPORT', 'ATTDEF', 'OLE2FRAME'}
ROOT = Path(__file__).resolve().parents[1]


def save(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False)+'\n')


def bounds_of(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def bounds(e, cache):
    ext = bbox.extents([e], fast=True, cache=cache)
    if ext.has_data:
        return [round(n,4) for n in (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)]


def literal(entity):
    return (entity.plain_text() if entity.dxftype()=='MTEXT' else entity.dxf.text).strip()


def area(b):
    return (b[2]-b[0])*(b[3]-b[1])


def inside(inner, outer, tol=0.005):
    return inner[0]>=outer[0]-tol and inner[1]>=outer[1]-tol and inner[2]<=outer[2]+tol and inner[3]<=outer[3]+tol


def center(b):
    return (b[0]+b[2])/2, (b[1]+b[3])/2


def matches_label(raw):
    s = raw.replace('%%U','').replace('S.H.S. ', '').splitlines()[0].strip()
    if s.startswith('NEIGHBORHOOD WATCH '):
        s = 'NEIGHBORHOOD WATCH'
    return s if CODE.fullmatch(s) and s.upper() not in IGNORE_LABEL else None


class Library:
    def __init__(self, work, key):
        self.key=key
        source=work/'all-sources'/f'{key}.dxf'
        self.doc=ezdxf.readfile(source)
        self.model=self.doc.modelspace()
        self.name=self.model.block_record.dxf.name
        cache_file=work/f'{key}-extents.json'
        fingerprint=sha256(source.read_bytes()).hexdigest()
        checksum=cache_file.with_suffix('.sha256')
        if cache_file.is_file() and checksum.is_file() and checksum.read_text()==fingerprint:
            self.extents=json.loads(cache_file.read_text())
        else:
            cache=bbox.Cache()
            self.extents={block.name:{e.dxf.handle:bounds(e,cache) for e in block} for block in self.doc.blocks}
            save(cache_file, self.extents)
            checksum.write_text(fingerprint)
        self.boxes=self.extents[self.name]
        self.entities={e.dxf.handle:e for e in self.model}
        self.texts={h:literal(e) for h,e in self.entities.items() if e.dxftype() in ('TEXT','MTEXT')}
        self.labels={}
        self.omissions=[]
        self.faces=[]
        self.references=[]
        self.suppressed=set()

    def parts(self, handles, box):
        result=[]
        for h in handles:
            e=self.entities[h]
            if e.dxf.layer.casefold()=='fp-noplot' or (h in self.labels and h!='1B53B') or h in self.suppressed or e.dxftype() in PANEL_SKIP or not self.boxes[h]:
                continue
            b=self.boxes[h]
            if inside(b,box):
                result.append(h)
            elif h in self.texts:
                # Text dimensions from substituted SHX metrics sometimes overrun a sign.
                mid=center(b)
                point=e.dxf.insert
                if inside([point.x,point.y,point.x,point.y],box) or (inside([*mid,*mid],box) and inside([b[0],b[1],b[0],b[3]],box)):
                    result.append(h)
        return result

    def panel(self, code, label, hs, kind, physical=None, note=None, ident=None, boundary=None):
        if not hs: return
        raw_box=bounds_of([self.boxes[h] for h in hs if self.boxes[h]])
        primary=ident or label or hs[0]
        target=dict(id=f'{self.key}-{primary.lower()}',drawing=self.key,code=code,
                    block=self.name,recordHandle=self.model.block_record_handle,
                    blockHandle=self.doc.blocks.get(self.name).block.dxf.handle,space='Model',use='placed',sourceKind='source-window',
                    entities=hs,bbox=raw_box,labelHandle=label or primary,handle=primary)
        if physical:target['physicalBounds']=physical
        if boundary:target['boundaryHandle']=boundary
        if note:target['note']=note
        self.faces.append(target)
        self.references.append((code,dict(kind=kind,handle=label or primary,space='Model',use='layout',
                                          label=self.texts.get(label,code),artwork=target['id'])))

    def chart(self):
        # The upper and lower chart segments have different row origins and variable-width guide cells.
        # Its actual CAD ruling determines horizontal cell limits, including the wide D-series panels.
        verticals=[]
        for h,b in self.boxes.items():
            if b and self.entities[h].dxftype()=='LINE' and abs(b[2]-b[0])<0.001 and b[3]-b[1]>=74.9:
                verticals.append(b)
        cells=defaultdict(list)
        for h,raw in self.texts.items():
            e=self.entities[h]
            x,y = e.dxf.insert.x, e.dxf.insert.y
            b=self.boxes[h]
            baseline=next((yy for yy in [185.4-i*75 for i in range(7)]+[810.4-i*75 for i in range(7)] if abs(y-yy)<.07),None)
            if b is not None and baseline is not None and e.dxf.layer=='0' and -925<x<1650:
                self.labels[h]=raw
                cuts=sorted({round(q[0],3) for q in verticals if q[1]<baseline+30<q[3]})
                mid=center(b)[0]
                left=[v for v in cuts if v<mid]
                right=[v for v in cuts if v>mid]
                if not left or not right:continue
                a=left[-1];c=right[0]
                if c-a>240:continue
                cells[(a,round(baseline-3,2),c,round(baseline+72,2))].append(h)
        for h,raw in self.texts.items():
            code=matches_label(raw)
            if code:self.labels[h]=code
        for box,labels in cells.items():
            labels.sort(key=lambda h:center(self.boxes[h])[0])
            for idx,h in enumerate(labels):
                code=self.labels[h]
                if code.upper() in CHART_COMPONENTS:
                    self.omissions.append(dict(handle=h,label=code,reason='Graphic component specimen in symbol chart'))
                    continue
                left,below,right,above=box
                if len(labels)>1:
                    mid=center(self.boxes[h])[0]
                    if idx:left=(center(self.boxes[labels[idx-1]])[0]+mid)/2
                    if idx+1<len(labels):right=(center(self.boxes[labels[idx+1]])[0]+mid)/2
                hs=self.parts(self.entities, [left+.015,below+8.1,right-.015,above-.015])
                if not hs:
                    self.omissions.append(dict(handle=h,label=code,reason='No separable face inside ruled cell'))
                    continue
                graphics=[self.boxes[k] for k in hs if k not in self.texts]
                if not graphics:
                    self.omissions.append(dict(handle=h,label=code,reason='Text-only stencil specimen with no board outline'))
                    continue
                physical=bounds_of(graphics)
                hs=self.parts(hs,physical)
                self.panel(code,h,hs,'ruled library chart specimen',physical)
        return set(h for hs in cells.values() for h in hs)

# Specific modelspace locations with atypical leaders, groups or names collected during chart review.
# These are source-coordinate windows. The four embedded OLE pictures never enter the vector exporter.
OLE = {'1B17A':'1B179','1B2CF':'1B2CE','1B2F6':'1B2F5','1B46D':'1B46C'}
OVERRIDE_LABELS={'1B2CF':'EXCEPT BUSES (CUSTOM)','145B2':'R61 (SPECIAL)','1BAB7':'W4-2(MOD)'}
# Source font substitutions can place text bounding boxes several units beyond the actual board.
# Physical boundaries remain the linework bounds; the text remains attached to its original board.
WINDOWS = {
    '1B35A':(2572,-413,2791,-300),'1B387':(2797,-412,3015.5,-333),'1B379':(3022,-412,3195,-333),
    '1B3C0':(2581,-589,2800,-473),'1B3E2':(2806,-586.5,2996,-542),'1C539':(3677,-413,3896,-300),
    '161E4':(1460.9,899.8,1486,908.93),'16113':(1935,752,1957,793.2),'166ED':(973,-16.6,1007.2,26.4),
    '166F4':(973,-36.4,1007.2,-16.6),'1B8B3':(1526,-440,1546,-416),'1B17B':(2645,43.5,2714.2,113.2),
    '1B17C':(2717,43.3,2786.4,113),'15E0C':(350.1,-410.8,381.2,-379.8),'15E0D':(350.1,-359.8,381.2,-328.8),'15E0E':(296,-411,329,-379),
}
# Two labels intentionally reference the same native face (S.H.S. citation and underscored example);
# the unnumbered neighborhood watch face itself repeats its title internally.
REFERENCE_ONLY={'15E1B':'Source specification label beside R10-12 specimen','1B53B':'Wording inside the Neighborhood Watch sign face',
                **{h:'Native ASM region recovered separately from the original DWG in R2018 format' for h in ('14260','14262','14269','15CEB','15CEF','15CF5')}}
NAMED_MODEL={'14264':'14263','15CF1':'15CF0','142EF':'142EE','145B2':'145B1','1464C':'1464B',
             '146E5':'1472A','1506C':'15225','14FF2':'14FF1','15E16':'15E15','15E18':'15E17',
             '15E19':'15E1A','161BC':'161BB','1B71A':'1BA81','1BAB7':'1BAFB'}


def frames(lib):
    """Candidate perimeters from closed entities and connected native LINE/ARC endpoints."""
    first={}
    groups={}
    def root(h):
        while h!=groups[h]:
            groups[h]=groups[groups[h]]
            h=groups[h]
        return h
    def join(a,b):
        a=root(a);b=root(b)
        if a!=b:groups[b]=a
    candidates=[]
    for h,e in lib.entities.items():
        b=lib.boxes[h]
        if not b or e.dxftype() in PANEL_SKIP or h in lib.texts:continue
        typ=e.dxftype()
        if typ in ('LWPOLYLINE','POLYLINE','CIRCLE','INSERT','HATCH','SOLID'):
            if area(b)>12:candidates.append((b,h))
        if typ not in ('LINE','ARC'):continue
        if max(b[2]-b[0],b[3]-b[1])>240:continue
        try:
            points=(e.dxf.start,e.dxf.end) if typ=='LINE' else (e.start_point,e.end_point)
        except (AttributeError,ValueError):continue
        groups[h]=h
        for v in points:
            p=(round(v.x,3),round(v.y,3))
            if p in first:join(h,first[p])
            else:first[p]=h
    sets=defaultdict(list)
    for h in groups:sets[root(h)].append(h)
    for hh in sets.values():
        if len(hh)<3:continue
        b=bounds_of([lib.boxes[h] for h in hh])
        if area(b)>12:candidates.append((b,hh[0]))
    return candidates


def supplemental(lib, handled):
    lib.labels.update(OVERRIDE_LABELS)
    refs,chosen=[],{}
    borders=frames(lib)
    for h,code in lib.labels.items():
        if h in handled:continue
        e=lib.entities[h]
        raw=lib.texts[h]
        if h in OLE or h in REFERENCE_ONLY:
            note=REFERENCE_ONLY.get(h,'Embedded bitmap recovered from native OLE source')
            evidence=dict(kind='printed library specimen label',handle=h,use='layout',space='Model',label=raw)
            if h in OLE:evidence.update(embeddedHandle=OLE[h],artwork=f'fp-signs-ole-{OLE[h].lower()}')
            lib.references.append((code,evidence));lib.omissions.append(dict(handle=h,label=code,reason=note));continue
        if h in NAMED_MODEL:
            hs=[NAMED_MODEL[h]];b=lib.boxes[hs[0]]
        elif h in WINDOWS:
            b=WINDOWS[h];hs=lib.parts(lib.entities,b)
        else:
            txt=lib.boxes[h]
            x,y=center(txt);y=txt[3]
            opts=[]
            for b,bh in borders:
                a,f,c,t=b;w=c-a;ht=t-f
                if w<8 or ht<4 or w>165 or ht>130 or w/ht>8 or ht/w>4:continue
                dx=abs((a+c)/2-x);gap=f-y
                if dx>max(16,w*.46) or gap<-3 or gap>57:continue
                # Prefer the outer perimeter, allowing fragments only when surrounded by its contour.
                score=dx*.8+max(0,gap) - min(w,100)*.07 -min(ht,90)*.04
                opts.append((score,-area(b),b,bh))
            if not opts:
                lib.references.append((code,dict(kind='printed library specimen label',handle=h,use='layout',space='Model',label=raw)))
                lib.omissions.append(dict(handle=h,label=code,reason='Review source location for separable face'));continue
            _,_,b,bh=min(opts)
            # The wireframe border may be split into separate corner arcs & orthogonal segments.
            containing=[(q,handle) for q,handle in borders if inside(b,q,.001) and
                        q[2]-q[0]<(b[2]-b[0])*1.24 and q[3]-q[1]<(b[3]-b[1])*1.24]
            if containing:b,bh=max(containing,key=lambda v:area(v[0]))
            hs=lib.parts(lib.entities,[b[0]-.1,b[1]-.1,b[2]+.1,b[3]+.1])
        if not hs:continue
        # Duplicate source placements at identical coordinates appear several times in this drawing.
        # Preserve each evidence handle and emit one geometry candidate per repeated specimen.
        token=(code.upper(),tuple(round(v,1) for v in b))
        if token in chosen:
            lib.references.append((code,dict(kind='repeated library chart placement',handle=h,space='Model',use='layout',label=raw,artwork=chosen[token])))
            continue
        geometry=[lib.boxes[k] for k in hs if k not in lib.texts]
        physical=bounds_of(geometry) if geometry else list(b)
        lib.panel(code,h,hs,'supplemental library specimen',physical)
        if m:=re.search(r'(\d+)\s*["″]\s*[xX×]\s*(\d+)\s*["″]',raw):
            # A signed source size belongs to the illustrated whole panel. The five wayfinding
            # mockups show multiple separate destination slats and their labels specify a single slat.
            if 'MOD ' in code and code.startswith('D1-'):
                lib.faces[-1]['note']='Multi-destination source specimen. Its printed nominal size applies to the called-out sign panel.'
            else:
                nominal=[int(m[1]),int(m[2])]
                diamond=bool(re.match(r'W(?:4-|9-|11-|74)|C23$',code,re.I)) and nominal[0]==nominal[1]
                upright=[n*2**.5 for n in nominal] if diamond else nominal
                ratio=(physical[2]-physical[0])/(physical[3]-physical[1])
                src=f'FP sign library printed label {h}: {m.group(0)}'
                if abs(ratio/(upright[0]/upright[1])-1)<.15:
                    lib.faces[-1].update(verifiedSize=nominal,sizeReference=src+(' (diamond side length)' if diamond else ''))
                else:
                    lib.faces[-1]['note']=src+'. Printed aspect ratio differs from the illustrated board.'
        chosen[token]=lib.faces[-1]['id']
        refs.append((h,code,hs,b))
    return refs

# Names are not inferred from word fragments: these anonymous definitions were inspected in isolation
# and checked against the exact adjoining label in the model insertion when one exists.
BLOCK_FACES={
    FP:{'NWZ_2':'*NWZ-2', 'R61-MOD3':'R61-MOD3', 'A$C70F70E8E':'R4-3','A$C459638C6':'W2-6',
       'A$C5AFE7381':'R73-5(CA)','R73-SP':'R73-SP','R73-6-MOD3':'R73-6-MOD3','A$C229F36A1':'W16-13',
       'R73-6-MOD':'R73-6-MOD','R73-6-MOD2':'R73-6-MOD2','R34-2':'R34-2',
       'A$C2A865726':'M4-11','M7-1':'M7-1','M4-6':'M4-6','A$C1ACF20B1':'R5-1','A$C40213BE9':'S1-1',
       'SR4-1':'SR4-1','W4-2(MOD)':'W4-2(MOD)','SR60-3':'SR60-3'},
    MUTCD:{'W9-2R':'W9-2R','M5-1':'M5-1'}}
PARTS = {
    'BIKESYM':'Bicycle pictogram','BICYCLEX':'Bicycle wayfinding pictogram',
    '1BLANK':'Blank diamond backing','SPEED':'Speed panel backing used by several populated specimens',
    'ARROW':'Arrow glyph','sharrow':'Shared-lane marking','HCAP-SYM':'Accessibility pictogram',
    'A$C355E1179':'Nested roundabout arrow','A$C66A331F5':'Combined left/U-turn arrow inside the R61-7(CA)(MOD) panel','A$C6BC632B1':'Nested lane arrow',
    'A$C663A269D':'Stead Boulevard destination and directional arrow inside destination sign',
    'A$C39763526':'Straight-ahead arrow inside Malibu wayfinding sign','A$C0E055B48':'Left arrow inside Malibu wayfinding sign',
    'A$C13955EE0':'Diagonal arrow inside W16-7pL panel'}


def blocks(lib, existing):
    d=lib.doc;instances=defaultdict(list);audit=[]
    for block in d.blocks:
        for e in block.query('INSERT'):
            instances[e.dxf.name.casefold()].append(dict(handle=e.dxf.handle,space=block.name,
                    use=('layout' if block.is_any_layout else 'nested definition')))
    for block in d.blocks:
        n=block.name;b=block.block.dxf.handle;rec=block.block_record_handle
        placed=instances[n.casefold()]
        row=dict(name=n,handle=b,recordHandle=rec,entities=len(block),instances=placed)
        if n in BLOCK_FACES[lib.key]:
            code=BLOCK_FACES[lib.key][n]
            same=next((r for r in existing if r['code'].upper()==code.upper() and
                      (r.get('definition')==n or r.get('entities')==[p['handle'] for p in placed])),None)
            rid=same['id'] if same else f'{lib.key}-block-{b.lower()}'
            row.update(classification='sign face',designation=code,candidate=rid)
            if not same:
                ext=lib.extents[n]; bs=[v for h,v in ext.items() if v and d.entitydb[h].dxftype() not in ('TEXT','MTEXT')]
                lib.faces.append(dict(id=rid,drawing=lib.key,code=code,block=n,recordHandle=rec,blockHandle=b,
                                      space=n,use='placed' if placed else 'definition',sourceKind='block',handle=b,
                                      physicalBounds=bounds_of(bs),bbox=bounds_of([v for v in ext.values() if v])))
            lib.references.append((code,dict(kind='sign block definition',handle=b,space=n,block=n,
                                           use='nested definition' if placed else 'unplaced definition',label=n,artwork=rid)))
            for p in placed:lib.references.append((code,dict(kind='sign library block insertion',handle=p['handle'],space=p['space'],
                                                use=p['use'],label=n,block=n,definitionHandle=b,artwork=rid)))
        elif n=='41-0335':
            row.update(classification='two-panel source sign drawing',designations=['41-0335 & 41-0336'])
            component_faces=[]
            for code,box,skip in [('41-0335',[6.9,20.5,39.9,53.6],{'16751','167A4','167A5'}),('41-0336',[11.5,7.6,34.3,18.2],set())]:
                hs=[h for h,v in lib.extents[n].items() if v and h not in skip and inside(v,box,.03)]
                bs=[lib.extents[n][h] for h in hs if d.entitydb[h].dxftype() not in ('TEXT','MTEXT')]
                idx=f'{lib.key}-block-{code}'
                part='vehicle warning sign' if code=='41-0335' else 'SLIPPERY WHEN WET plaque'
                code='41-0335 & 41-0336'
                lib.faces.append(dict(id=idx,drawing=lib.key,code=code,block=n,entities=hs,recordHandle=rec,blockHandle=b,
                                    handle='167A5',space=n,use='placed',sourceKind='source-window',physicalBounds=bounds_of(bs),
                                    note=f'{part} in the two-panel source detail labeled 41-0335 & 41-0336. The printed label identifies the assembly.'))
                component_faces.append(lib.faces[-1])
                lib.references.append((code,dict(kind='labeled two-panel library assembly',handle='167A5',space=n,
                                      block=n,use='nested definition',label='41-0335&41-0336',artwork=idx)))
            assembly_id='fp-signs-assembly-41-0335-41-0336'
            parts=[dict(role=role,entities=face['entities']) for role,face in
                   zip(('Vehicle warning panel','SLIPPERY WHEN WET plaque'),component_faces)]
            lib.faces.append(dict(id=assembly_id,drawing=lib.key,code=code,block=n,
                                  entities=[h for p in parts for h in p['entities']],
                                  recordHandle=rec,blockHandle=b,handle='167A5',space=n,use='placed',
                                  sourceKind='source assembly',assembly=True,componentHandles=parts,
                                  physicalBounds=bounds_of([f['physicalBounds'] for f in component_faces]),
                                  note='Complete two-panel assembly, with the original vertical separation and horizontal alignment. '
                                       'The printed compound designation identifies both panels together; '
                                       'the source does not give a measured assembly width or height.'))
            row.update(candidate=assembly_id,componentCandidates=[f['id'] for f in component_faces])
            lib.references.append((code,dict(kind='complete two-panel library assembly',handle='167A5',space=n,
                                             block=n,use='nested definition',label='41-0335&41-0336',artwork=assembly_id)))
        elif block.is_any_layout:row.update(classification='layout container')
        elif n in PARTS:row.update(classification='component inside source artwork',description=PARTS[n])
        elif n.startswith('*X'):row.update(classification='component inside source artwork',description='Anonymous shape groups inherited by their chart panel')
        elif n.startswith('*U'):row.update(classification='annotation symbol definition',description='Pushpin glyph, verified from its isolated geometry')
        elif n.startswith('*D'):row.update(classification='dimension annotation')
        elif n.startswith('AUDIT_'):row.update(classification='source region component',description='Native ASM perimeter recovered with an R2018 DXF export')
        elif n in ('signalandlighting','Sign and Strip FP','Signal FP'):row.update(classification='empty or reference-only supporting block')
        else:raise ValueError(f'Unreviewed block {n}')
        audit.append(row)
    return audit


def as_observations(lib, extra):
    refs=list(lib.references)
    for r in extra:
        h=r.get('labelHandle') or r['handle']
        for dup in r.get('duplicatePlacements',[]):
            refs.append((r['code'],dict(kind='repeated library specimen',handle=dup,space='Model',use='layout',label=r['code'],artwork=r['id'])))
        refs.append((r['code'],dict(kind='library chart specimen' if r.get('labelHandle') else 'unnumbered library specimen',
                                 handle=h,label=lib.texts.get(h,r['code']),space='Model',use='layout',artwork=r['id'])))
    records={}
    for code,ref in refs:
        item=records.setdefault(code.upper(),dict(source=lib.key,designation=code,evidence=[]))
        if ref not in item['evidence']:item['evidence'].append(ref)
        if match:=re.search(r'(?:[ (\-]+MOD(?:IFIED)?\s*\d*\)?)|(?:[ (\-]+SPECIAL\)?)',code,flags=re.I):
            base=code[:match.start()].strip()
            if base:item.update(base=base,variant='modified')
    return list(records.values())


def main():
    from cad_ole_faces import extract as embedded_faces
    from fp_chart_repairs import prepare as plot_chart_repairs
    from fp_destination_panels import prepare as plot_destinations
    from cad_library_regions import extract as region_faces
    from extract_fp_extra_faces import extract as extra_faces, source_sizes
    from extract_mutcd_library_faces import extract as mutcd_faces
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('work',type=Path)
    work=cli.parse_args().work
    out=work/'block-inputs';records=[];audits=[]
    for key,filename in [(FP,'-FP_Signs.dwg'),(MUTCD,'MUTCD-StandardSigns.dwg')]:
        lib=Library(work,key)
        if key==FP:
            uncoded,repairs,review=extra_faces(work)
            save(out/'fp-uncoded.json',uncoded);save(work/'fp-parent-repairs.json',repairs)
            save(work/'fp-unlabelled-audit.json',review)
            replacements={r['id']:r for r in repairs}
            grid=lib.chart()
            original=len(lib.faces)
            supplemental(lib,grid)
            missing=set(replacements)-{r['id'] for r in lib.faces}
            if missing:raise ValueError(f'Missing reviewed chart locations: {missing}')
            lib.faces=[replacements.get(r['id'],r) for r in lib.faces]
            plot_chart_repairs(lib,lib.faces[:original],work)
            plot_destinations(lib,lib.faces[original:],work)
            save(out/'fp-grid.json',lib.faces[:original]);save(out/'fp-supplemental.json',lib.faces[original:])
            attrs=source_sizes(lib.doc,work);save(work/'fp-source-size-attributes.json',attrs)
            by_id={r['id']:r for r in lib.faces}
            for a in attrs:
                dest=by_id[a['id']]
                dest.update(verifiedSize=[a['width'],a['height']],sizeReference=f'FP SIZE attribute {a["attributeHandle"]}, {a["literal"]} ({a["rawOrder"]})')
                lib.references.append((a['code'],dict(kind='source SIZE attribute',handle=a['attributeHandle'],space='Model',use='layout',label=a['literal'],artwork=a['id'])))
            save(out/'fp-grid.json',lib.faces[:original])
            restored={r.get('labelHandle') for r in uncoded}
            lib.omissions=[o for o in lib.omissions if o['handle'] not in restored]
            embedded=embedded_faces(lib,work,OLE);save(out/'fp-embedded.json',embedded)
            regions=region_faces(work);save(out/'fp-regions.json',regions)
            extra=embedded+uncoded+regions
        else:
            extra,review=mutcd_faces(work/'all-sources'/f'{key}.dxf')
            save(out/'mutcd-library.json',extra);save(work/'mutcd-library-audit.json',review)
        num=len(lib.faces);audit=blocks(lib,lib.faces+extra)
        named=lib.faces[num:]
        if key==FP:
            save(out/'fp-confirmed-assembly.json',[face for face in named if face.get('assembly')])
            named=[face for face in named if not face.get('assembly')]
        save(out/f'{key}-named.json',named)
        observations=as_observations(lib,extra);records+=observations
        dwg=work.parent/'cad-inputs'/filename
        audits.append(dict(source=key,file=filename,sha256=sha256(dwg.read_bytes()).hexdigest(),
                          sourceRecords=len(observations),blocks=audit,chartNotes=lib.omissions))
    target=ROOT/'data/reference/plan-examples'
    save(target/'sign-library-records.json',records);save(target/'sign-library-blocks.json',audits)
    print([(a['source'],a['sourceRecords'],len(a['blocks'])) for a in audits])


if __name__=='__main__':
    main()
