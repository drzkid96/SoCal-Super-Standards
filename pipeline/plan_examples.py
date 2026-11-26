"""Publish cropped plan examples under their treatment and sign references."""
import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from zipfile import ZipFile
from current_catalog import BASE
from cad_sign_catalog import CATALOG, DRAWINGS, designation_key, sign_destinations

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
    finder=[]
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
            finder.append((label,title,key))
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
            finder.append((heading,label,key))
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
            label=f'{title} · Detail {code}'
            finder.append((name,label,key))
            sections.append(f'<p id="{key}"><strong>{escape(label)}</strong></p>')
            if detail_signs[series,key]:
                links=' · '.join(f'<a href="{r["url"]}">{escape(r["code"])}</a>' for r in detail_signs[series,key])
                sections.append('Sign callouts · '+links)
            lookup.setdefault(title,[]).append([name+' · '+label,target+'#'+key])
            cad_links[topic].append(f'- [{label}]({target}#{key})')
    for topic,cards in cad_links.items():
        append(root/'topics'/(topic+'.md'),'## CAD details for plan checking\n\n'+guides[topic]+'\n\n'+'\n'.join(cards))
    aliases=[]
    for series,name in DRAWINGS.items():
        for record in records:
            drawing=next((d for d in record['drawings'] if d['source']==series),None)
            if not drawing:continue
            anchor=drawing['url'].split('#')[1]
            label=' / '.join(drawing.get('labels',[])) or record['code']
            aliases.append(f'<div id="{escape(anchor)}" class="plan-source-alias"><b>{escape(label)}</b> · {escape(name)} · <a href="{record["url"]}">View sign and artwork</a></div>')
            for alias in set(drawing.get('labels',[]))|{w['text'] for w in drawing.get('wording',[])}:
                hits=lookup.setdefault(alias.upper(),[])
                if not any(url==record['url'] for _,url in hits):hits.append([label+' · '+name,record['url']])
    options=defaultdict(list)
    for label,title,key in finder:options[label].append(f'<option value="{key}">{escape(title)}</option>')
    picker=''.join(f'<optgroup label="{escape(label,quote=True)}">{"".join(entries)}</optgroup>' for label,entries in options.items())
    nav=f'<label class="plan-finder" hidden>Find a treatment, sign or detail <select><option value="">Choose a detail</option>{picker}</select></label>'
    layout=[];section_open=False
    for part in sections:
        if part.startswith('## '):
            if section_open:layout.append('</details>')
            section_open=True
            name=part[3:]
            layout.append(f'<details class="plan-group" id="{re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")}"><summary>{escape(name)}</summary>')
        else:layout.append(part)
    if section_open:layout.append('</details>')
    samples=[]
    for key in ('detail-a','detail-d','detail-s'):
        title=catalog['details'][key][0]
        samples.append(f'<a href="#{key}"><img src="{BASE}/figs/plan-examples/{key}.webp" alt="" loading="lazy"><span>{escape(title)}</span></a>')
    layout.insert(layout.index(intro)+1,nav+'<nav class="plan-featured" aria-label="Example treatments">'+''.join(samples)+'</nav>')
    layout.append(f'<div id="cad-sign-callouts"><a href="{BASE}/signs/cad/">Browse CAD sign drawings</a></div>')
    layout.extend(aliases)
    path=root/'ladot/plan-reference.md'
    path.write_text('\n\n'.join(layout))
    for rel in ['ladot/index.md','details/index.md','signs/index.md']:
        if (root/rel).exists():append(root/rel,f'[Browse signing and striping details and sign variants]({target})')
