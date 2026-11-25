"""Add verified references to rendered article text without modifying anchors, code, or navigation."""
from collections import defaultdict
from html import escape, unescape
from pathlib import Path
import json
import re
import sys
from urllib.parse import urlsplit

BASE='/SoCal-Super-Standards'
DIST=Path(sys.argv[1]) if len(sys.argv)>1 else Path('dist')
def read(path):return json.loads(Path(path).read_text())

official={}
sources=Path('src/content/docs/sources/index.md').read_text()
for title,url in re.findall(r'\[([^\]]{4,110})\]\((https?://[^\s)]+)\)',sources):
    if len(title.split())>=2 and title.lower() not in ('official page','official source','publisher website'):
        official[title]=url
official.update({
'CA MUTCD 2026':BASE+'/ca-mutcd/',
'California MUTCD 2026':BASE+'/ca-mutcd/',
'MUTCD 11th Edition with Revision 1':BASE+'/mutcd/',
'Standard Highway Signs':'https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/index.htm',
'TTCP Review & Submission Requirements':'https://www.santamonica.gov/media/Document%20Library/Process%20Explainers/How%20to%20Submit%20a%20Temporary%20Traffic%20Control%20Plan/TTCP%20Review%20%26%20Submission%20Requirements.pdf',
'Traffic Control Plan Supplement':'https://www.santamonica.gov/media/Document%20Library/Process%20Explainers/How%20to%20Obtain%20a%20Roadway%20Closure%20Permit/Traffic%20Control%20Plan%20Supplement%202022.pdf',
'Plan Check Checklist — Offsite Improvements':'https://www.santamonica.gov/media/Public%20Works/Engineering%20%26%20Street%20Services/Land%20Development/Offsite%20Improvements/Checklist%20-%20Off-site%20%20%28Rev%206-27-23%29.pdf',
'City Curb Ramp Memo':'https://www.santamonica.gov/media/Public%20Works/Engineering%20%26%20Street%20Services/Standard%20Details%20and%20Specifications/Memorandum_CurbRampDesign%20s%20%281%29.pdf',
'LADOT MPP 531':BASE+'/ladot/mpp-531/',
'LADOT MPP 521':BASE+'/ladot/mpp-521/',
'SMMC 9.28.120':'https://ecode360.com/45330882',
'Caltrans Encroachment Permits Manual':'https://dot.ca.gov/programs/traffic-operations/ep/ep-manual',
'Steel Trench Plating Guidelines':'https://dot.ca.gov/programs/traffic-operations/ep/ep-manual',
'LA BOE Street Design Manual':BASE+'/boe/street-design/',
})
targets={k.casefold():v for k,v in official.items()}
candidates=defaultdict(set)
for s in read('data/signs/signs.json'):
    candidates[s['code'].upper()].add(BASE+'/signs/'+s['slug']+'/')
for s in read(DIST/'data/details.json'):
    if s['type']=='Standard drawing' and re.fullmatch(r'[A-Z][A-Z\d .-]*\d[A-Z\d.-]*',s['num']):
        candidates[s['num'].upper()].add(s['url'])
for k,v in candidates.items():
    if len(v)==1:targets[k.casefold()]=next(iter(v))
deletion_notice=read('data/ca_deleted_signs.json')['source']
for code in read('data/ca_deleted_signs.json')['codes']:
    targets[code.casefold()]=deletion_notice
# Use only uniquely resolved BOE sections, including the numbered article headings.
boe = defaultdict(set)
for key, entries in read(DIST/'data/lookup.json').items():
    if re.fullmatch(r'E\s*\d+(?:\.\d+)*',key,re.I):
        boe[key.casefold()].update(url for _,url in entries if url.startswith(BASE+'/boe/street-design/'))
for key, urls in boe.items():
    if len(urls)==1: targets[key]=next(iter(urls))
sections={edition:{x['num'].upper():x['url'] for x in read(f'data/{edition}/sections.json')} for edition in ('mutcd','ca-mutcd')}
figures={edition:{} for edition in sections}
for row in read(DIST/'data/details.json'):
    if row['type'] in ('Figure','Table'):
        edition='mutcd' if row['src']=='Federal MUTCD' else 'ca-mutcd'
        figures[edition][row['type'].lower(),row['num'].upper().replace(' ','')]=row['url']
titles='|'.join(re.escape(k) for k in sorted(targets,key=len,reverse=True))
pattern=re.compile(r'(?<![\w/-])(?:(?P<web>https?://[^\s<>\x22\x27]+)|(?P<kind>Figure|Table)\s+(?P<fid>\d[A-Z]-\d+(?:\s*\(CA\))?)|(?P<section>(?:(?:CA|California|Federal) MUTCD\s+)?(?:Section\s+|§\s*)(?P<num>\d[A-Z]\.\d+(?:\(CA\))?))|'+titles+r')(?![\w/-]|\.\d)',re.I)
tag_split=re.compile(r'(<!--.*?-->|</?[A-Za-z][^>]*>)',re.S)
void={'br','hr','img','input','source','col','meta','link','wbr','area','embed','track'}
exclude={'math','annotation','a','button','nav','code','pre','script','style','svg','textarea','select','del','summary','h1','h2','h3','h4','h5','h6'}
from inline_examples import Artwork, BLOCKED
artwork = Artwork(DIST)
counts=defaultdict(int)
for page in DIST.rglob('*.html'):
    if page.relative_to(DIST).parts[0] == 'regions':continue
    raw=page.read_text(); start=re.search(r'<div\b[^>]*class="sl-markdown-content"[^>]*>',raw)
    if not start:continue
    # Astro closes the content wrapper before the pagination. Consume only that balanced div.
    end=start.end(); depth=1
    for marker in re.finditer(r'</?div\b[^>]*>',raw[start.end():]):
        depth+=-1 if marker[0].startswith('</') else 1
        if depth==0:
            end=start.end()+marker.start();break
    body=raw[start.end():end]
    route=BASE+'/'+page.relative_to(DIST).as_posix().removesuffix('index.html')
    seen=set(); stack=[]; result=[]
    illustrated = set()
    paragraph_start = None
    family = page.relative_to(DIST).parts[0]
    reading = family not in {'keywords','search','sources','signs'} and 'class="inline-examples"' not in body
    for token in tag_split.split(body):
        if token.startswith('<'):
            tag=re.match(r'</?([\w-]+)',token)
            if tag:
                name=tag[1].lower()
                if name == 'h2' and not token.startswith('</'):
                    illustrated.clear()
                if reading and name == 'p' and not BLOCKED.intersection(stack):
                    if token.startswith('</') and paragraph_start is not None:
                        result.append(token)
                        paragraph = ''.join(result[paragraph_start:])
                        preview = '' if 'boe-figure-ref' in paragraph else artwork.paragraph(paragraph, route, illustrated)
                        if preview:
                            result.append(preview)
                            counts['inline examples'] += preview.count('<img ')
                        paragraph_start = None
                        if name in stack:del stack[len(stack)-1-stack[::-1].index(name):]
                        continue
                    if not token.startswith('</') and not re.search(r'class="(?:detail-description|boe-source|srcbar)',token):
                        paragraph_start = len(result)
                if token.startswith('</'):
                    if name in stack:del stack[len(stack)-1-stack[::-1].index(name):]
                elif name not in void and not token.endswith('/>'):stack.append(name)
            result.append(token);continue
        if not token.strip() or exclude.intersection(stack):
            result.append(token);continue
        value=unescape(token); last=0; chunks=[]
        for match in pattern.finditer(value):
            phrase=match[0]; url=targets.get(phrase.casefold())
            lastchar=match.end()
            if match['web']:
                phrase=phrase.rstrip('.,;:!?]')
                if phrase.endswith(')') and phrase.count(')')>phrase.count('('):phrase=phrase[:-1]
                if not urlsplit(phrase).hostname:continue
                lastchar=match.start()+len(phrase)
                url=phrase
            if match['kind']:
                edition='mutcd' if '/mutcd/' in route else 'ca-mutcd' if '/ca-mutcd/' in route else None
                if edition:url=figures[edition].get((match['kind'].lower(),match['fid'].upper().replace(' ','')))
            if match['section']:
                edition='mutcd' if 'federal' in phrase.lower() or ('/mutcd/' in route and not re.search('CA|California',phrase)) else 'ca-mutcd'
                url=sections[edition].get(match['num'].upper())
                if not phrase.lower().startswith(('ca ','california ','federal ')) and not any(x in route for x in ('/ca-mutcd/','/mutcd/')):continue
            if not url or url==route:continue
            if not chunks and not last:seen.clear()
            if url in seen:continue
            seen.add(url);counts['external' if url.startswith('https:') else 'internal']+=1
            chunks.extend((escape(value[last:match.start()],quote=False),f'<a class="source-ref" href="{escape(url,quote=True)}">{escape(phrase,quote=False)}</a>'))
            last=lastchar
        result.append(''.join(chunks)+escape(value[last:],quote=False) if last else token)
    updated=''.join(result)
    if updated!=body:page.write_text(raw[:start.end()]+updated+raw[end:])
print('Added article references:',dict(counts))
