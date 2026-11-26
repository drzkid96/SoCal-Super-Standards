"""Publish cropped plan examples under their treatment and sign references."""
import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from zipfile import ZipFile
from current_catalog import BASE
from cad_sign_catalog import CATALOG, DRAWINGS, designation_key, drawing_evidence, sign_destinations

def build(root, lookup):
    source=Path('data/reference/plan-examples')
    with ZipFile(source/'illustrations.zip') as archive:
        archive.extractall('public/figs/plan-examples')
    catalog=json.loads((source/'index.json').read_text())
    records=json.loads(CATALOG.read_text())
    signs=sign_destinations()
    groups=defaultdict(list)
    target=BASE+'/ladot/plan-reference/'
    intro='These examples come from signing and striping design sets. Check the cited manual and the adopting agency before carrying a treatment or a modified sign into a new design.'
    sections=['---','title: Signing and striping plan details','---','',intro,'']
    def figure(key,label):
        img=f'{BASE}/figs/plan-examples/{key}.webp'
        return f'<figure id="{key}"><a href="{img}"><img loading="lazy" src="{img}" alt="{escape(label)}"></a><figcaption>{escape(label)}</figcaption></figure>'
    def append(path,body):
        with path.open('a') as stream:stream.write('\n\n'+body+'\n')
    sections.extend(['Westwood also labels a proposed left-turn traffic-calming detail as pending. Its sheet supplies no installable geometry.',''])
    for key,(title,topic) in catalog['details'].items():
        groups[topic].append((key,title))
    provisions={row['num']:row for row in json.loads(Path('data/ca-mutcd/sections.json').read_text())}
    section_numbers=['9E.03','9E.11','3B.19','3B.27','9E.17','9E.07','9E.07','3H.06',
                     '2G.05','2G.05','9E.17','9E.06','3H.06','3B.19','3B.19','3B.27',
                     '3B.29','9E.07','9E.07','9E.07','2D.10']
    related=defaultdict(list)
    for topic,items in groups.items():
        label=topic.replace('-',' ').title()
        sections.extend(['## '+label,''])
        cards=[]
        for key,title in items:
            number=section_numbers[ord(key[-1])-ord('a')]
            provision=provisions[number]
            sections.append(figure(key,title))
            sections.append(f'[CA MUTCD § {number} · {provision["title"]}]({provision["url"]})')
            related[number].append(f'[{title}]({target}#{key})')
            cards.append(f'- [{title}]({target}#{key})')
            lookup.setdefault(title,[]).append([title,target+'#'+key])
        append(root/'topics'/(topic+'.md'),'## Signing and striping plan details\n\n'+'\n'.join(cards))
    for number,links in related.items():
        url=provisions[number]['url']
        chapter,anchor=url.split('#')
        path=root/(chapter.removeprefix(BASE+'/').rstrip('/')+'.md')
        body=path.read_text()
        start=body.find('id="'+anchor+'"')
        if start<0: raise ValueError('Missing manual section '+number)
        boundary=re.search(r'^<span id="[^"]+" class="anchor"></span>\s*$',body[start+len(anchor)+5:],re.M)
        stop=start+len(anchor)+5+boundary.start() if boundary else len(body)
        if stop<0:stop=len(body)
        example='\n\n**Related plan details** · '+' · '.join(links)+'\n\n'
        path.write_text(body[:stop]+example+body[stop:])
    sections.extend(['## Sign faces and variants','','The legend beneath each face reproduces its plan designation. A modified legend, time restriction, or arrow can differ from the catalog face.',''])
    def family(code):
        if code.startswith(('OM','W','SW')):return 'Warning signs and object markers'
        if code.startswith(('G','D','M','I-')):return 'Guide signs and route markers'
        if code.startswith(('S5','SR4')):return 'School signs'
        return 'Regulatory signs and plaques'
    faces=defaultdict(list)
    for key,label in catalog['signs'].items():
        faces[family(label)].append((key,label))
    for heading,items in sorted(faces.items()):
        sections.extend(['### '+heading,'','<div class="plan-faces">'])
        for key,label in sorted(items,key=lambda pair:pair[1]):
            url=signs[designation_key(label)]
            card=figure(key,label)
            card=card.replace('</figcaption>',f' · <a href="{url}">Sign record</a></figcaption>')
            sections.append(card)
            lookup.setdefault(label,[]).append([label+' · plan legend',target+'#'+key])
        sections.extend(['</div>',''])
    cad=json.loads((source/'cad.json').read_text())
    sections.extend(['## CAD detail sheets','','Detail letters are local to each drawing series. Use the treatment name and source series together.',''])
    cad_links=defaultdict(list)
    guides={
        'accessibility':'Trace the accessible route from the access aisle to the crossing. Compare approach-side, departure-side and midblock ramp layouts.',
        'bikeways':'Follow the bicycle path through each driveway and intersection. Identify where separation ends, what the markings communicate and how turning vehicles cross it.',
        'transit':'Trace the bus entry, boarding movement and departure. Compare the right-turn pocket and boarding-island variants with the stop location.',
        'striping-intersections':'Follow each vehicle and bicycle movement through the conflict point, then check the markings against the signal or yield control.',
        'speed-and-calming':'Check the device footprint, approach markings and installation details together.'
    }
    detail_signs=defaultdict(list)
    for record in records:
        for drawing in record['drawings']:
            for detail in drawing.get('details',[]):
                detail_signs[(drawing['source'],detail)].append(record)
    for series,edition in cad.items():
        name='Geometric design details' if series=='geo' else 'Urban corridor signing and striping details'
        sections.extend(['### '+name,''])
        for key,code,title,image in edition['rows']:
            title=title.capitalize().replace('Ada ','Accessible ').replace('ada parking','accessible parking').replace('Rpm','RPM')
            phrase=title.lower()
            topic=next((t for term,t in [('parking connecting','accessibility'),('accessible parking','accessibility'),('ada parking','accessibility'),('bus','transit'),('speed','speed-and-calming'),('intersection','striping-intersections'),('triangle','striping-intersections')] if term in phrase),'bikeways')
            label=f'{title} · {code}'
            sections.append(f'<p id="{key}"><strong>{escape(label)}</strong></p>')
            if detail_signs[series,key]:
                links=' · '.join(f'<a href="{r["url"]}">{escape(r["code"])}</a>' for r in detail_signs[series,key])
                sections.append('Sign callouts · '+links)
            lookup.setdefault(title,[]).append([name+' · '+label,target+'#'+key])
            cad_links[topic].append(f'- [{label}]({target}#{key})')
    for topic,cards in cad_links.items():
        append(root/'topics'/(topic+'.md'),'## CAD details for plan checking\n\n'+guides[topic]+'\n\n'+'\n'.join(cards))
    sections.extend(['<h2 id="cad-sign-callouts">CAD sign callouts</h2>','',
                     'Find the designation under its source drawing. Each record links the drawing evidence, available sign artwork, and any matching catalog layout.',''])
    if Path('public/data/cad-sign-evidence.json').is_file():
        sections.append(f'[Download CAD drawing inventory and entity evidence (JSON)]({BASE}/data/cad-sign-evidence.json)')
    for series,name in DRAWINGS.items():
        sections.extend(['### '+name,''])
        for record in records:
            drawing=next((d for d in record['drawings'] if d['source']==series),None)
            if not drawing:continue
            label=record['code']
            anchor=drawing['url'].split('#')[1]
            literal=' / '.join(drawing.get('labels',[])) or label
            sections.append(f'<p id="{anchor}"><a href="{record["url"]}">{escape(literal)}</a> · {escape(record["status"])}</p>')
            search_label=f'{literal} · {name} · CAD evidence'
            aliases=set(drawing.get('labels',[]))|{w['text'] for w in drawing.get('wording',[])}
            for alias in sorted(aliases):
                hits=lookup.setdefault(alias.upper(),[])
                if not any(url==drawing['url'] for _,url in hits):hits.append([search_label,drawing['url']])
            evidence=drawing_evidence(drawing)
            if evidence:sections.append(evidence)
            for key in drawing.get('details',[]):
                detail=next((r for r in cad[series]['rows'] if r[0]==key),None)
                if detail:sections.append(f'[Detail {detail[1]} · {detail[2]}](#{key})')
    path=root/'ladot/plan-reference.md'
    path.write_text('\n\n'.join(sections))
    for rel in ['ladot/index.md','details/index.md','signs/index.md']:
        if (root/rel).exists():append(root/rel,f'[Browse signing and striping details and sign variants]({target})')
