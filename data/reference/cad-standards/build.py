"""Compile the reviewed Caltrans/FHWA dimension tables and sign-art crosswalk.

Run from the workspace containing site/ and cad-working/. The input snapshots
are produced by extract_tables.py. Source PDF pages and original cell wording
are retained even when there is no single conventional-road dimension.
"""
from collections import defaultdict
from math import sqrt
from pathlib import Path
import argparse
import re,json,gzip
import numpy as np
import pymupdf
from PIL import Image
from scipy import ndimage
from lookup import key, variant_record
OUT=Path(__file__).resolve().parent
IN_REPO=OUT.parent.name=='reference'
SITE=OUT.parents[2] if IN_REPO else OUT.parents[1]/'site'
CA='https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/camutcd-2026-all.pdf'
SPEC='https://dot.ca.gov/programs/safety-programs/sign-specs'
FED='https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/'
SHS='https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/'
SHS14=SHS+'pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf'
load=lambda p:json.loads(Path(p).read_text())
def save(path,data):
    encoded=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    path.write_bytes(gzip.compress(encoded,mtime=0) if path.suffix=='.gz' else encoded)
def split_codes(designation):
    text=re.sub(r'\s*\(CA\)', '(CA)',designation.upper()).strip()
    if re.fullmatch(r'[A-Z]+\d+-[A-Z0-9]+ SERIES',text):return [text]
    # California strikes individual cells/parts of compounds in blue. The
    # group prefix of these two reviewed rows belongs to its surviving suffixes.
    if text=='R7 ,2, , ,5, ,10, ,108':return ['R7-2','R7-5','R7-10','R7-108']
    if text=='R10 3,':return ['R10-3']
    # Table 2N-1 prints EM-1a. Its own footnote and Section 2N.03 say EM1-1a.
    text=text.replace('EM1-1, EM-1A, EM1-2','EM1-1, EM1-1A, EM1-2')
    text=text.replace(' & ',', ')
    if '/' in text:return []
    if re.fullmatch(r'OM3-L,C,R',text):return ['OM3-L','OM3-C','OM3-R']
    text=re.sub(r'(?<=\))\s+(?=[A-Z]+\d)',' , ',text)
    codes=[];prefix=''
    for v in text.split(','):
        part=v.strip().replace(' ','')
        if re.fullmatch(r'[A-Z]{1,6}\d+[A-Z]*(?:-[A-Z0-9]+){0,2}(?:\([SU]\))?(?:\(CA\))?',part):
            codes.append(part);prefix=part.split('-')[0]+'-'
        elif prefix and re.fullmatch(r'-?\d+[A-Z]*(?:\(CA\))?',part):codes.append(prefix+part.lstrip('-'))
    return codes

def conditions(page):
    table=page['table'];chapter=re.match(r'\d+[A-Z]',table)[0]
    return {'6G':'temporary-traffic-control','6H':'temporary-traffic-control','6I':'temporary-traffic-control',
            '7B':'school-area','8B':'grade-crossing','9A':'bicycle-facility','2E':'freeway-guide',
            '2F':'toll-facility','2G':'preferential-managed-lanes','2N':'emergency-management'}.get(chapter,'general-roadway')

def parse_dimensions(cell):
    s=cell.strip().replace('×','x')
    dia=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:dia\.?|diameter)\s*\**',s,re.I)
    if dia:return [float(dia[1])]*2,'diameter'
    if not re.fullmatch(r'\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?){1,2}\s*\**',s,re.I):return None,None
    values=[float(v)for v in re.findall(r'\d+(?:\.\d+)?',s)]
    if len(values)==3:return values,'triangle-sides'
    return values,'published-pair'

def norm_heading(v):
    if v=='Conventional Road Single Multi-Lane Lane':
        # Rev. 1 Chapter 2C, PDF p7, combines two header labels in the first cell.
        return 'Conventional Road Single Lane'
    return re.sub(r'(?<=\D)\d+(?:,\d+)*$','',v).replace('Multi- Lane','Multi-Lane').strip()
def nominal(row):
    for col in ('Conventional Road Single Lane','Conventional Road','Conventional Road (Minimum)','Roadway'):
        if col in row['columns']:
            size,basis=parse_dimensions(row['columns'][col])
            if size:return size,basis,col
    return None,None,None

def face_shape(file):
    try:
        if file.suffix=='.svg':
            with pymupdf.open(file) as d:
                p=d[0];pix=p.get_pixmap(matrix=pymupdf.Matrix(90/p.rect.width,90/p.rect.height),alpha=True)
            mask=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,4)[:,:,3]>190
        else:
            with Image.open(file) as im:
                rgb=np.asarray(im.convert('RGB').resize((90,90)))
            mask=ndimage.binary_fill_holes(np.min(rgb,axis=2)<160)
        yy,xx=np.where(mask)
        if not len(yy):return None
        mask=mask[yy.min():yy.max()+1,xx.min():xx.max()+1]
        y,x=np.meshgrid(np.linspace(-1,1,len(mask)),np.linspace(-1,1,len(mask[0])),indexing='ij')
        shapes={'diamond':abs(x)+abs(y)<=1,'circle':x*x+y*y<=1,'octagon':abs(x)+abs(y)<=2**.5,'rectangle':np.ones_like(x,dtype=bool)}
        fits=sorted(((np.count_nonzero(mask&pattern)/np.count_nonzero(mask|pattern),name)for name,pattern in shapes.items()),reverse=True)
        if fits[0][1]=='diamond' and fits[0][0]>.865 and fits[0][0]-fits[1][0]>.095:return 'diamond'
        if fits[0][0]>.93 and fits[0][0]-fits[1][0]>.024:return fits[0][1]
    except (ValueError,RuntimeError,OSError):return None

# These table-specific markers change how a designer may use a numeric entry.
# Other markers stay with original cells and link to their complete tables.
CA_CELL_NOTES = {
    ('2B-1','*'): (293, 'Bicycle facility minimums are governed by Table 9A-1.', False),
    ('2C-1','*'): (381, 'Diamond warnings facing multilane conventional traffic have a 36-inch minimum under Section 2C.03.', False),
    ('2C-1','**'): (381, 'A rectangular 72-inch version is permitted at freeway ramps.', False),
    ('2D-1','*'): (485, 'The CA source marks this illustrated guide panel with an asterisk. Verify its legend and layout before choosing a size.', True),
    ('2H-1','*'): (736, 'This is a maximum. Reduce the sign and acknowledgment logo as appropriate for shorter legends.', True),
    ('2H-1','**'): (736, 'The typical illustrated size changes with the number of legend lines.', True),
    ('2I-1','*'): (771, 'The illustrated size covers the named rest, parking, picnic, scenic, or visitor information legend. An alternate legend changes the panel size.', True),
    ('2I-1','**'): (771, 'The illustrated sign has four service lines. Adjust its panel for the displayed legend.', True),
    ('2I-1','***'): (771, 'See the 18- and 24-inch SHS symbol layouts and Alternative Fuels Corridor installation in Section 2H.14.', False)
}
def cell_note(row,col):
    if not row or not col or row['publisher']!='Caltrans':
        return None
    mark=re.search(r'(\*+)\s*$',row['columns'][col])
    match=CA_CELL_NOTES.get((row['table'],mark[1])) if mark else None
    if match:
        return {'marker':mark[1],'guidance':match[1],'source':CA+'#page='+str(match[0]),'requiresProjectSelection':match[2]}
    return None

def select(rows):
    eligible=[r for r in rows if nominal(r)[0]]
    if not eligible:return None
    # California's adoption controls California source attribution, even when the federal edition differs.
    eligible=[r for r in eligible if r['publisher']=='Caltrans'] if any(r['publisher']=='Caltrans'for r in rows) else eligible
    if not eligible:return None
    priorities={'general-roadway':0,'school-area':1,'grade-crossing':1,'preferential-managed-lanes':1,'bicycle-facility':2,'toll-facility':2,'temporary-traffic-control':3}
    ranked=[(priorities.get(r['application'],5),r)for r in eligible];best=min(a for a,r in ranked)
    choices=[r for a,r in ranked if a==best]
    if len({tuple(nominal(r)[0])for r in choices})!=1:return None
    return choices[0]

def nominal_geometry(record):
    size = record['size']
    basis = record['sizeBasis']
    if not size:
        return None, None
    code = record['standardCode']
    vertices = None
    if basis=='triangle-sides' and len(set(size))==1 and code=='R1-2':
        width,height = size[0],size[0]*sqrt(3)/2
        vertices = [[0,height],[width,height],[width/2,0],[0,height]]
        kind = 'downward-equilateral-triangle'
    elif basis=='triangle-sides' and size[0]==size[1] and code=='W14-3':
        height = size[2]
        width = sqrt(size[0]**2 - (height/2)**2)
        vertices = [[0,0],[0,height],[width,height/2],[0,0]]
        kind = 'right-pointing-isosceles-pennant'
    elif basis=='diamond-side-lengths' and size[0]==size[1]:
        width = height = size[0]*sqrt(2)
        vertices = [[width/2,0],[width,height/2],[width/2,height],[0,height/2],[width/2,0]]
        kind = 'diamond'
    elif basis in ('width-height','diameter'):
        width,height = size[:2]
        kind = 'circle' if basis=='diameter' else (record.get('referenceFace') or record.get('familyReference') or {}).get('outline')
        if kind=='rectangle':
            vertices=[[0,0],[width,0],[width,height],[0,height],[0,0]]
    else:
        return None, None
    geom = None
    if vertices:
        geom={'type':kind,'verticesInches':[[round(x,4),round(y,4)] for x,y in vertices]}
    elif kind=='circle':
        geom={'type':'circle','diameterInches':width}
    return [round(width,4),round(height,4)],geom

def read_observations(cad_dir):
    printed=defaultdict(list)
    observed={r['key']:r['code'] for r in load(SITE/'public/data/plan-signs.json')}
    for row in load(SITE/'data/reference/plan-examples/3346-sign-records.json'):
        label = row['designation']
        observed[key(label)] = label
    attr_file = cad_dir/'fp-source-size-attributes.json'
    for row in load(attr_file) if attr_file.is_file() else []:
        label = row['code']
        k = key(label)
        observed[k] = label
        printed[k].append({'type':'individual-cad-size-attribute',
                           'dimensions':[row['width'],row['height']],
                           'drawing':'FP_SIGNS','candidate':row['id'],'labelHandle':row['labelHandle'],
                           'evidence':{'attributeHandle':row['attributeHandle'],'rawText':row['literal'],'rawOrder':row['rawOrder']}})
    for file in sorted((cad_dir/'block-inputs').glob('*.json')):
        if not isinstance(data:=load(file),list):continue
        for r in data:
            if not isinstance(r,dict) or not r.get('code'):continue
            k=key(r['code']);observed[k]=r['code']
            if r.get('sizeInches') and r.get('sizeEvidence'):
                item={'type':'project-printed-dimension','dimensions':r['sizeInches'],'drawing':r.get('drawing'),'faceHandle':r.get('handle'),'evidence':r['sizeEvidence']}
                if item not in printed[k]:printed[k].append(item)
    for file in sorted((cad_dir/'3346-review').glob('*candidates.json')):
        for r in load(file):
            if r.get('label'):observed[key(r['label'])]=' '.join(r['label'].split())
    return {'labels':observed,'dimensionEvidence':printed}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    default_output=OUT/('sign-standards.json.gz' if IN_REPO else 'sign-standards.json')
    parser.add_argument('--output',type=Path,default=default_output)
    parser.add_argument('--cad-dir',type=Path,default=None if IN_REPO else OUT.parent,
                        help='Refresh CAD observations from this working directory.')
    args=parser.parse_args()
    catalog=defaultdict(list);raws={};labels={};faces={};specs={}
    with gzip.open(OUT/'sources/official-size-table-rows.json.gz','rt') as stream:source_pages=json.load(stream)
    last_pages={}
    for pg in source_pages:
        field=pg['source'],pg['table']
        last_pages[field]=max(last_pages.get(field,0),pg['n'])
    for pg in source_pages:
        cal=pg['source'].endswith('source.pdf')
        if cal and pg['n']==66:continue  # An example of editorial markup in Chapter 1A.
        url=(CA if cal else FED+Path(pg['source']).name)+'#page='+str(pg['n'])
        for idx, raw in enumerate(pg['rows']):
            designation=next((v for h,v in raw.items() if 'Designation' in h),'')
            if not designation or designation.lower()=='sign designation':continue
            label=next((v for h,v in raw.items()if h in ('Sign or Plaque','Sign','Plaque','Assembly','Sign or Assembly','Object Marker')),'')
            columns={norm_heading(h):v for h,v in raw.items()if any(x in h.lower()for x in ('road','lane','way','minimum','oversized','street','size'))}
            if not columns:continue
            row={'publisher':'Caltrans' if cal else 'FHWA','table':pg['table'],'title':pg['title'],'page':pg['n'],'url':url,
                 'tableEndUrl':url.rsplit('=',1)[0]+'='+str(last_pages[pg['source'],pg['table']]),
                 'dimensionScope':'assembly' if pg['table']=='7B-1(CA)' else 'published-table-row',
                 'application':conditions(pg),'designation':designation,'label':label,'section':raw.get('Section',''),'columns':columns}
            rid=('ca' if cal else Path(pg['source']).stem)+'-'+str(pg['n'])+'-'+pg['head'][0].lower().split()[0]+'-'+str(idx+1) if pg['head'][0].strip() else ('ca' if cal else Path(pg['source']).stem)+'-'+str(pg['n'])+'-'+str(idx+1)
            if rid in raws:rid+='-'+str(len(raws))
            raws[rid]=row
            for c in split_codes(designation):
                k=key(c);catalog[k].append(rid);labels.setdefault(k,c)
    for designation,url in load(OUT/'sources/caltrans-specifications.json'):
        k=key(designation);specs[k]=url;labels.setdefault(k,designation)
    for r in load(SITE/'data/signs/signs.json'):
        k=key(r['code']);asset=r.get('svg')
        if not asset:continue
        file=SITE/'public'/asset.lstrip('/')
        if not file.exists():continue
        if r.get('artworkSource')=='caltrans-specification':
            src=r['sourceUrl']
            if src!=specs.get(k):
                raise ValueError(f'Issued face must use the cataloged Caltrans specification: {k}')
            kind='caltrans-specification-face'
        elif r['source'].startswith('CA MUTCD 2026'):
            src=CA+'#page='+str(r['pdf_page'])
            kind='source-figure-crop'
        elif r['source'].startswith('FHWA SHS 2024'):
            src=SHS14+'#page='+str(r['pdf_page'])
            kind='published-face-vector'
        else:
            continue
        faces[k]={'asset':asset,'type':kind,'source':src,'reference':r['source'],'outline':face_shape(file)}
        labels.setdefault(k,r['code'])
    for r in load(SITE/'data/reference/fhwa-layouts-5-6.json'):
        k=key(r['code']);labels.setdefault(k,r['code'])
        if r.get('pages'):
            page=r['pages'][0];src=SHS+'pdf/'+r['file']+'#page='+str(page)
            if k in faces:faces[k]['laterLayout']=src
            else:faces[k]={'type':'dimensioned-layout-sheet','source':src,'asset':None,'outline':None}
    # Current fabrication sheets explicitly dimension A and B for these
    # parking panels, or dimension the side for the two TTC diamonds.
    sheet_shapes={'R26-SCA':'rectangle','R26A-SCA':'rectangle','R28-SCA':'rectangle',
                  'C30CA':'diamond','C30ACA':'diamond'}
    for k,url in specs.items():
        if k in faces:faces[k]['specification']=url
        else:faces[k]={'type':'caltrans-specification-sheet','source':url,'asset':None,'outline':None}
        if k in sheet_shapes:
            faces[k]['outline']=sheet_shapes[k]
            faces[k]['outlineSource']=url
    reviewed_options=defaultdict(list)
    for candidate,option in load(SITE/'data/reference/plan-examples/verified-publisher-panel-sizes.json').items():
        normalized=key(option['code'])
        item={field:option[field] for field in ('size','sizeBasis','nominalBounds','source','condition','applicationSource') if field in option}
        if item not in reviewed_options[normalized]:reviewed_options[normalized].append(item)
    archival=load(OUT/'sources/archival-caltrans-options.json')
    # These two illustrated post-mounted designs are named by the publisher and
    # share the R3-11 series' CA MUTCD table row. Other public appearances of the
    # series can require a different legend and therefore remain independent.
    for designation in ('R3-11','R3-11A'):
        if not catalog.get(designation) and designation in reviewed_options:
            catalog[designation]=catalog[key('R3-11 series')].copy()
    school_faces=load(OUT/'sources/caltrans-school-faces.json')
    retired={key(k)for k in load(SITE/'data/ca_deleted_signs.json')['codes']}
    observation_file=OUT/'sources/cad-observations.json.gz'
    if args.cad_dir:
        observations=read_observations(args.cad_dir)
        save(observation_file,observations)
    else:
        with gzip.open(observation_file,'rt') as stream:
            observations=json.load(stream)
    observed,printed=observations['labels'],observations['dimensionEvidence']
    records={}
    for k in sorted(set(labels)|set(observed)|set(catalog)):
        code=labels.get(k)or observed[k];ids=catalog.get(k,[]);rows=[raws[i]for i in ids]
        row=select(rows);face=faces.get(k);sz,basis,col=nominal(row) if row else (None,None,None)
        size_note=cell_note(row,col)
        note='';shape=(face or {}).get('outline')
        if sz and basis=='published-pair':
            basis={'rectangle':'width-height','diamond':'diamond-side-lengths','circle':'diameter','octagon':'width-height'}.get(shape,'published-width-height-verify-outline')
            if k=='S1-1':basis='width-height'
            if k=='R1-1':basis='width-height'
        if basis=='triangle-sides':
            note='Three nominal panel-side lengths in the printed order. They are not its upright bounding width and height.'
        if sz and basis=='published-width-height-verify-outline' and sz[0]!=sz[1] and face and face.get('asset'):
            # Confirm that the artwork's upright proportions match the table width/height.
            file=SITE/'public'/face['asset'].lstrip('/')
            if file.suffix=='.svg':
                with pymupdf.open(file) as doc:ratio=doc[0].rect.width/doc[0].rect.height
            else:
                with Image.open(file) as im:ratio=im.width/im.height
            if abs(ratio/(sz[0]/sz[1])-1)<.07:basis='width-height'
        face_sizes=school_faces.get(k)
        if row and row['dimensionScope']=='assembly' and sz:
            if face_sizes and sz in face_sizes['options']:
                note='The assembly dimension for this application matches an A × B size on the issued sign-face specification.'
            else:
                note='The California MUTCD row sizes the complete school assembly. The exact sign-face specification lists separate A × B options without roadway-class assignments.'
                sz=basis=col=None
        for option in reviewed_options.get(k,[]):
            if sz==option['size'] and option.get('applicationSource','').startswith(CA+'#page=') and option['sizeBasis']=='width-height' and basis=='published-width-height-verify-outline':
                basis='width-height'
        if k in retired:
            sz=basis=col=None;status='retired-in-california';note='Listed in the Caltrans deleted sign register.'
        elif 'MOD' in k and k not in catalog:
            sz=basis=col=None;status='modified-project-design';note='The modified face has no confirmed published size.'
        elif row and row['publisher']=='FHWA':
            status='federal-size-only';note='The federal table is available in sizeRows. Confirm California applicability before choosing a plotted size.';sz=basis=col=None
        elif size_note and size_note['requiresProjectSelection']:
            status='requires-size-selection';sz=basis=col=None;note=size_note['guidance']
        elif sz:status='published-conditional-size' if row['application']!='general-roadway' else 'published-conventional-size'
        elif ids:
            status='requires-size-selection'
            if not note:note='Consult the application, speed, legend, or other column in the cited source rows.'
        elif face:status='published-reference-only';note='Published face or detail located; no single conventional dimension was established.'
        else:status='unresolved-designation';note='No exact published designation was located.'
        records[k]={'cadDimensionEvidence':printed.get(k,[]),'code':code,'standardCode':labels.get(k),'status':status,'size':sz,'sizeBasis':basis,'condition':(row['application']+' / '+col) if sz else None,
                    'columns':row['columns'] if row else {},'source':{p:row[p] for p in ('publisher','table','page','url','designation','section')} if row else None,
                    'sizeRows':ids,'referenceFace':face,'sizeNote':size_note,'notes':note or None}
        if k in reviewed_options:
            records[k]['reviewedPanelOptions']=reviewed_options[k]
        if k in archival:
            records[k]['archivalSizeOptions']=archival[k]
        if face_sizes:
            records[k]['faceSizeOptions']=face_sizes
        assembly_ids=[i for i in ids if raws[i]['dimensionScope']=='assembly']
        if assembly_ids:
            records[k]['assemblySizeRows']=assembly_ids
    # Legend-variable and handed faces listed here share a published panel size. The
    # parent face is separately labeled for visual comparison, never identical artwork.
    for k in sorted(observed):
        r=records[k]
        if r['status']!='unresolved-designation':continue
        variant=variant_record(k,records)
        if variant:
            r.update(variant)
    for r in records.values():
        r['nominalBounds'],r['panelGeometry']=nominal_geometry(r)
        r['sizeProvenance']=('published-variable-face' if r['status']=='published-panel-variant' else 'published-exact') if r['size'] else None
    out={'units':'in','version':1,
         'sizePolicy':'size contains nominal published dimensions for the named application; consult the complete source row and footnotes. CAD drawing dimensions are recorded separately and never override the authority table.',
         'boundsPolicy':'nominalBounds are ideal unrounded panel extents. Diamond side lengths differ from the rotated bounding box. Coordinates use +x right, +y up and close the ideal unrounded polygon. Source corner radii and artwork registration control final CAD. A null bound requires separate outline verification.',
         'selectionPolicy':'General California conventional single-lane/roadway is preferred. Conditional records require the recorded school, grade-crossing, temporary-control, or bicycle application. A federal-only or withdrawn row gives no selected California size.',
         'modPolicy':'A source-specific printed dimension, CAD size attribute for the exact specimen, or a separately documented calibrated panel in the original drawing can establish a modified sign CAD size. Preserve aspect ratio. Never assign a base-family standard size to a MOD; resolve conflicting observations manually.',
'records':records,'tableRows':raws,'sources':{'californiaMUTCD':CA,'californiaSpecifications':SPEC,'fhwaSigns':SHS+'index.htm','californiaDeletedSignList':load(SITE/'data/ca_deleted_signs.json')['source']}}
    save(args.output,out)
    print(len(records),'designations;',len(raws),'published source rows;',sum(bool(r['size'])for r in records.values()),'with a selected size;',len(faces),'face/layout references')
if __name__=='__main__':main()
