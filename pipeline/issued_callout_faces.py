"""Associate plan designations with exact publisher foils or retained historic specifications."""
import argparse
from contextlib import chdir
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

import pymupdf
from PIL import Image

from cad_sign_catalog import collect, designation_key, drawing_records

SITE = Path(__file__).resolve().parents[1]
ASSETS = SITE / 'data/reference/cad-standards/callout-faces'
FHWA = ('https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/'
        '2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf')
TEXT_EVIDENCE = {'text','mtext','multileader','external image definition','attribute','attribute definition'}

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def slug(key):
    return re.sub('[^a-z0-9-]','-',key.casefold()).strip('-')

def polygon(items):
    pieces=[]
    previous=None
    def pair(p):
        return f'{p.x:.4f} {p.y:.4f}'
    for item in items:
        kind=item[0]
        if kind=='re':
            if previous is not None:pieces.append('Z')
            rect=item[1]
            points=[rect.tl,rect.tr,rect.br,rect.bl]
            if len(item)>2 and item[2]<0:points.reverse()
            pieces.append('M'+'L'.join(pair(point) for point in points)+'Z')
            previous=None
            continue
        if kind not in ('l','c'):
            raise ValueError(f'Unexpected publisher artwork primitive {kind}')
        if item[1]!=previous:
            if previous is not None:pieces.append('Z')
            pieces.append('M'+pair(item[1]))
        pieces.append(('L' if kind=='l' else 'C')+' '.join(pair(p) for p in item[2:]))
        previous=item[-1]
    if previous is not None:pieces.append('Z')
    return ' '.join(pieces)

def extract(pdf, recipes):
    """Only re-run against the cited, checksum-matched government publication."""
    with pymupdf.open(pdf) as doc:
        for r in recipes:
            page=doc[r['page']-1]
            assert r['foil'].casefold() in page.get_text().casefold(),r
            paths=[p for p in page.get_drawings() if r['first']<=p['seqno']<=r['last']]
            assert paths and all(p['type']=='f' for p in paths),r
            rect=paths[0]['rect']
            width=1200
            height=width*rect.height/rect.width
            out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{rect.x0:.5f} {rect.y0:.5f} {rect.width:.5f} {rect.height:.5f}" width="{width}" height="{height:.5f}">']
            for p in paths:
                # Orange and yellow blank fields plot white. Neutral dark legend ink plots black.
                color='black' if max(p['fill'])<.5 else 'white'
                fill_rule='evenodd' if p['even_odd'] else 'nonzero'
                out.append(f'<path fill="{color}" fill-rule="{fill_rule}" d="{polygon(p["items"])}"/>')
            out.append('</svg>')
            (ASSETS/(slug(r['key'])+'.svg')).write_text('\n'.join(out)+'\n')

def render_mask(asset, mask):
    if asset.suffix=='.svg':
        with pymupdf.open(asset) as doc:
            p=doc[0]
            k=1200/max(p.rect.width,p.rect.height)
            pix=p.get_pixmap(matrix=pymupdf.Matrix(k,k),alpha=False)
            img=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    else:
        img=Image.open(asset)
    img.convert('L').point(lambda value:0 if value<128 else 255).save(mask)

def original_observations():
    by_key=defaultdict(dict)
    for d in drawing_records():
        code=d['designation']
        for e in d.get('evidence',[]):
            if e.get('kind') not in TEXT_EVIDENCE or not e.get('handle'):continue
            h=e['handle']
            by_key[designation_key(code)][d['source'],h]={
                'id':f"callout-{d['source']}-{h.lower()}",'code':code,
                'sourceDrawing':d['source'],'sourceHandle':h,'space':e.get('space',''),
                'rawLabel':e.get('label',code),'evidenceKind':e['kind'],
                'relationship':'Plan designation; sign face supplied by issuer'}
    return {key:list(obs.values()) for key,obs in by_key.items()}

def build(inputs, out):
    estimated=read(ASSETS/'fhwa-variants.json')
    with chdir(SITE):
        plans={p['key']:p for p in collect()}
        observations=original_observations()
    official=read(inputs/'official-faces.json')
    existing={designation_key(r['code']):r for r in official}
    source_families=read(ASSETS/'publication-sources.json')
    supplement=[]
    # Enrich originals in place by ID. The geometry stays with its recorded issuer.
    for key,r in existing.items():
        if key not in plans:continue
        obs=observations.get(key,[])
        if obs:supplement.append({'id':r['id'],'drawing':'official-standard','code':r['code'],'sourceObservations':obs})
    historic=read(ASSETS/'historic-faces.json') if (ASSETS/'historic-faces.json').exists() else []
    for r in estimated+historic:
        plan=plans[r['key']]
        source=source_families[r.get('publication','fhwa-2024')]
        url=source['url']+f"#page={r['page']}"
        asset=ASSETS/r.get('asset',slug(r['key'])+'.svg')
        if not asset.is_file():raise FileNotFoundError(asset)
        mask=out/(slug(r['key'])+'.png')
        render_mask(asset,mask)
        dimensions=[v*(math.sqrt(2) if r.get('diamond') else 1) for v in r['size']]
        basis=('published diamond side lengths; upright bounding box in inches' if r.get('diamond') else 'published overall panel width and height in inches')
        historic_note=(' Historical artwork. '+r['status'] if r.get('status') else '')
        obs=observations.get(r['key'],[])
        assert obs,(r['key'],'missing original drawing observation')
        supplement.append({'id':'official-callout-'+slug(r['key']),'drawing':'official-standard','code':plan['code'],
            'outlineMask':str(mask.resolve()),'sourceUrl':url,'referenceTitle':source['title'],
            'referenceSha256':source['sha256'],'sourceKind':'historic issuer face for plan callout' if r.get('status') else 'issued handed face for plan callout',
            'notes':f"The source plan names {plan['code']}. The publisher illustrates {r['foil']}; the downloadable drawing reproduces that face."+historic_note,
            'publisherPlateSize':dimensions,'publisherSizeBasis':basis,
            'publisherPlateSource':{'publisher':source['publisher'],'url':url,'page':r['page'],'reference':r['foil']},
            'publisherPlateCondition':r.get('condition','Published reference face'),'sourceObservations':obs,
            'aliases':[r['foil']],'historicalLegend':bool(r.get('status')),
            **{k:r[k] for k in ('withdrawalSource','secondarySource','secondarySourceSha256') if r.get(k)}})
    (inputs/'official-callout-faces.json').write_text(json.dumps(supplement,indent=1,ensure_ascii=False)+'\n')
    print(f'{len(estimated)+len(historic)} source-matched new faces; {len(supplement)-len(estimated)-len(historic)} issued records linked to original drawing observations.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',type=Path)
    parser.add_argument('output_masks',type=Path)
    parser.add_argument('--extract-fhwa-pdf',type=Path)
    args=parser.parse_args()
    if args.extract_fhwa_pdf:
        spec=read(ASSETS/'publication-sources.json')['fhwa-2024']
        if sha(args.extract_fhwa_pdf)!=spec['sha256']:raise ValueError('FHWA publication checksum changed')
        extract(args.extract_fhwa_pdf,read(ASSETS/'fhwa-variants.json'))
    args.output_masks.mkdir(exist_ok=True,parents=True)
    build(args.inputs,args.output_masks)

if __name__=='__main__':main()
