"""Connect observed drawing designations to sign records, layouts, and source evidence."""
import json
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from current_catalog import BASE, PUBLIC, read, save

SOURCE = Path('data/reference/plan-examples')
PLAN = BASE + '/ladot/plan-reference/'
DRAWINGS = {'geo': 'Geometric design details', 'pico': 'Pico Boulevard signing and striping details'}
LIBRARIES = {
    'fp-signs': ('FP Signs library', '-FP_Signs.dwg'),
    'mutcd-standard-signs': ('MUTCD Standard Signs drawing library', 'MUTCD-StandardSigns.dwg'),
    '3346-title-details': ('3346 title and details', '3346-SS-TITLE_DETAILS.dwg'),
    '3346-signs-1-13': ('3346 signing sheets 1–13', '3346-SIGNS_1-13.dwg'),
    '3346-signs-14-15': ('3346 signing sheets 14–15', '3346-SIGNS_14-15.dwg'),
}
CATALOG = PUBLIC/'plan-signs.json'


def source_name(source):
    return LIBRARIES[source][0] if source in LIBRARIES else DRAWINGS[source]


def source_route(source):
    return BASE+'/signs/cad/sources/'+source+'/' if source in LIBRARIES else PLAN


def designation_key(raw):
    """Preserve meaningful hyphens and suffixes, including CA, direction, and MOD."""
    key = raw.strip().upper().replace('–', '-').replace('—', '-').replace('−', '-')
    def qualifier(match):
        word=' '.join(match[1].split())
        return 'CA' if word=='CA' else '-'+word.replace(' ','-')
    key=re.sub(r'\(([^()]*)\)',qualifier,key)
    key=re.sub(r'[\s-]*\bMOD(?:IFIED)?\b[\s-]*','-MOD-',key)
    key=re.sub(r'(?<=[0-9A-Z])MOD(?=$|[ -])','-MOD',key)
    key=re.sub(r'-(LT|RT)(?=-|$)',lambda m:'-LEFT' if m[1]=='LT' else '-RIGHT',key)
    if re.fullmatch(r'(?:[A-Z]\.)+[A-Z]\.?',key):key=key.replace('.','')
    return re.sub(r'\s','',key).strip('-')


def slug(key):
    return re.sub('[^a-z0-9-]+', '-', key.lower()).strip('-')


def callout_id(drawing, code):
    return 'cad-'+drawing+'-'+slug(designation_key(code))


def drawing_records():
    file = SOURCE/'cad-signs.json'
    rows = read(file) if file.is_file() else [
        dict(designation=code,source=drawing) for drawing,edition in read(SOURCE/'cad.json').items() for code in edition['signs']]
    for extra in ('sign-library-records.json','3346-sign-records.json'):
        if (SOURCE/extra).exists():
            rows.extend(read(SOURCE/extra))
    return rows


def drawing_audit():
    rows=read(SOURCE/'cad-signs-audit.json')
    for name in ('sign-library-blocks.json','3346-sign-audit.json'):
        if (SOURCE/name).exists():
            rows.extend(read(SOURCE/name))
    return rows


def sign_destinations():
    return {designation_key(alias):r['url'] for r in read(CATALOG) for alias in r['aliases']}


def base_key(key, known):
    if '-MOD' in key:
        return key.split('-MOD')[0]
    for pattern in [r'-(LEFT|RIGHT|SYMBOL)$',r'-(\d+(?:FT\d*|K)?)$']:
        match = re.search(pattern,key)
        if match and key[:match.start()] in known:
            return key[:match.start()]
    return key


def category(key):
    if key.startswith(('W','SW','OM')):return 'warning'
    if re.match(r'S[1-5]-',key):return 'school'
    if key.startswith(('D','G','M','I','SG')):return 'guide'
    if key.startswith(('CW','C')):return 'ttc'
    return 'regulatory'


def collect():
    official = {designation_key(k):v for k,v in read(PUBLIC/'signs-index.json').items()}
    notice = read(PUBLIC/'retired.json')
    withdrawn = {designation_key(k):v for k,v in notice['codes'].items()}
    audit={item['source']:item for item in drawing_audit()}
    detail_titles={key:code+' · '+title for edition in read(SOURCE/'cad.json').values() for key,code,title,_ in edition['rows']}
    entries, declared = {}, {}
    def record(raw):
        key = designation_key(raw)
        row = entries.setdefault(key,dict(key=key,code=raw,aliases=[],drawings={},faces=[],art=[]))
        if raw not in row['aliases']:row['aliases'].append(raw)
        return row
    for item,label in read(SOURCE/'index.json')['signs'].items():
        record(label)['faces'].append(dict(id=item,image='/figs/plan-examples/'+item+'.webp',label=label,url=PLAN+'#'+item))
    for observation in drawing_records():
        raw = observation['designation']
        row = record(raw)
        source = observation['source']
        drawing=row['drawings'].setdefault(source,dict(source=source,name=source_name(source),file=audit.get(source,{}).get('file',''),
                            url=source_route(source)+'#'+callout_id(source,raw),labels=[],evidence={},details=[]))
        if raw not in drawing['labels']:drawing['labels'].append(raw)
        if observation.get('kind'):row['kind']=observation['kind']
        wording=drawing.setdefault('wording',{})
        for evidence in observation.get('evidence',[]):
            if observation.get('kind')=='uncoded local sign callout':
                literal=evidence['label']
                wording.setdefault(literal,dict(text=literal,count=0,handle=evidence['handle']))['count']+=1
                if literal not in row['aliases']:row['aliases'].append(literal)
            group=(evidence['use'],evidence['kind'])
            bucket=drawing['evidence'].setdefault(group,dict(use=group[0],kind=group[1],count=0,handles=[],layouts=set()))
            bucket['count']+=1
            if len(bucket['handles'])<4:bucket['handles'].append(evidence['handle'])
            if evidence['use']=='layout':bucket['layouts'].add(evidence['space'])
            bucket['layouts'].update(evidence.get('layouts',[]))
        for detail in observation.get('detailIDs',[]):
            if detail not in drawing['details']:drawing['details'].append(detail)
        for alias in observation.get('aliases',[]):
            if alias not in row['aliases']:row['aliases'].append(alias)
        if observation.get('base'):declared[row['key']]=designation_key(observation['base'])
        if not row['faces'] or '-MOD' in row['key']:row['code']=raw
    art_file = SOURCE/'cad-sign-art.json'
    if art_file.is_file():
        for asset in read(art_file):
            key = designation_key(asset['code'])
            if key not in entries:record(asset['code'])
            row = entries[key]
            row['art'].append(asset)
            source = asset['drawing']
            row['drawings'].setdefault(source,dict(source=source,name=source_name(source),url=source_route(source)+'#'+callout_id(source,asset['code'])))
    known = set(official)|set(withdrawn)|set(entries)
    routes = {}
    for key,row in entries.items():
        base = declared.get(key) or base_key(key,known)
        row['base'] = base
        row['modified'] = bool(re.search(r'(?:^|-)MOD(?:-|$)',key))
        row['official'] = official.get(key)
        row['baseOfficial'] = official.get(base) if base!=key else None
        row['withdrawal'] = notice['source'] if key in withdrawn else ''
        row['baseWithdrawal'] = notice['source'] if base!=key and base in withdrawn else ''
        row['category'] = 'local' if row.get('kind') or key.startswith('SS') or not re.match(r'^(?:[A-Z]+-?\d|OM)',key) else category(key)
        row['status'] = ('Withdrawn in California' if row['withdrawal'] else 'Catalog sign' if row['official']
                         else 'Modified plan designation' if row['modified'] else 'Plan variant' if base!=key else 'Plan designation')
        if row['official']:row['code'] = row['official']['code']
        elif row['modified'] and '-MOD' in key:
            row['code'] = re.sub(r'-mod(?=$|-)', ' (MOD)', row['code'], flags=re.I)
        if row['code'] not in row['aliases']:row['aliases'].append(row['code'])
        if row['official']:url = row['official']['url']
        elif row['baseOfficial']:url = row['baseOfficial']['url']+'#plan-'+slug(key)
        else:
            parent = base if base!=key and base in entries else key
            url = BASE+'/signs/plan-'+slug(parent)+'/'
            if parent!=key:url+='#plan-'+slug(key)
        if url in routes and routes[url]!=key:raise ValueError(f'Conflicting plan sign route: {url}')
        routes[url]=key
        row['url']=url
        row['drawings']=list(row['drawings'].values())
        for drawing in row['drawings']:
            drawing['detailTitles']={k:detail_titles[k] for k in drawing.get('details',[])}
            drawing['wording']=sorted(drawing.get('wording',{}).values(),key=lambda g:(-g['count'],g['text']))
            evidence=drawing.get('evidence',{})
            drawing['evidence']=sorted(evidence.values(),key=lambda g:(g['use']!='layout',g['use'],g['kind']))
            for group in drawing['evidence']:group['layouts']=sorted(group['layouts'])
            uses=Counter({g['use']:0 for g in drawing['evidence']})
            for group in drawing['evidence']:uses[group['use']]+=group['count']
            drawing['uses']=dict(uses)
    return sorted(entries.values(),key=lambda r:r['key'])


def drawing_summary(drawing):
    uses=drawing['uses']
    direct=uses.get('layout',0);nested=uses.get('nested definition',0)
    unplaced=uses.get('unplaced definition',0)+uses.get('unplaced external image definition',0)
    parts=[]
    if direct:parts.append(str(direct)+' direct layout record'+('s' if direct!=1 else ''))
    if nested:parts.append(str(nested)+' nested record'+('s' if nested!=1 else '')+' used in layouts')
    if unplaced:parts.append(str(unplaced)+' unplaced definition record'+('s' if unplaced!=1 else ''))
    return ' · '.join(parts) or f'{sum(uses.values())} evidence records'


def drawing_evidence(drawing):
    if not drawing['evidence']:return ''
    lines=[]
    for group in drawing['evidence']:
        samples=', '.join(group['handles'])
        if group['count']>len(group['handles']):samples+=' …'
        context=group['use']+(' · '+', '.join(group['layouts']) if group['layouts'] else '')
        lines.append(f'<tr><td>{escape(group["kind"])}</td><td>{escape(context)}</td><td>{group["count"]}</td><td><code>{escape(samples)}</code></td></tr>')
    file=escape(drawing.get('file',''))
    return ('<details><summary>Drawing evidence · '+escape(drawing_summary(drawing))+'</summary><p><code>'+file+
            '</code></p><table><thead><tr><th>Entity</th><th>Drawing context</th><th>Records</th><th>Example handles</th></tr></thead><tbody>'+
            ''.join(lines)+'</tbody></table></details>')


def figures(row):
    images=[]
    for asset in row['art']:
        source=source_name(asset['drawing'])
        caption=asset['code']+' · '+source+' · '+asset['space']+' · handle '+asset['handle']
        url=next(d['url'] for d in row['drawings'] if d['source']==asset['drawing'])
        images.append((asset['image'],caption,url,asset.get('note',''),asset.get('width'),asset.get('height')))
    for item in row['faces']:
        images.append((item['image'],'Plan legend · '+item['label'],item['url'],'',None,None))
    if not images:return ''
    cards=[]
    for image,label,source,note,w,h in images:
        img=escape(BASE+image,quote=True)
        size=f' width="{int(w)}" height="{int(h)}"' if w and h else ''
        annotation=' · '+escape(note) if note else ''
        cards.append(f'<figure class="mfig"><a href="{img}"><img src="{img}" loading="lazy" alt="{escape(label,quote=True)}"{size}></a><figcaption><a href="{escape(source)}">{escape(label)}</a>{annotation}</figcaption></figure>')
    return '<div class="mfig-grid">'+''.join(cards)+'</div>'


def observed_section(rows):
    out=['## Recorded in drawings and plan legends','']
    for row in rows:
        title=escape(row['code'])
        out.extend([f'<h3 id="plan-{slug(row["key"])}">{title}</h3>',''])
        if row['withdrawal']:
            out.append(f'Caltrans lists this designation as [withdrawn in California]({row["withdrawal"]}). The records below document its appearance in the source drawings.')
        elif row['baseWithdrawal']:
            out.append(f'Caltrans lists the base designation as [withdrawn in California]({row["baseWithdrawal"]}). The drawing uses the variant shown here.')
        elif row['modified']:
            out.append('The drawing identifies a modified sign. Use the recorded legend and drawing context to identify the modification.')
        elif not row['official'] and not row['baseOfficial']:
            out.append('The source uses this designation. An issued standard layout for this exact code has not been identified in the catalog.')
        elif not row['official']:
            out.append('This designation records the configuration shown in the source plan.')
        if row['baseOfficial']:
            ref=row['baseOfficial']
            out.append(f'Base layout · <a href="{escape(ref["url"])}">{escape(ref["code"])}</a> · {escape(ref["descriptor"])}.')
        for drawing in row['drawings']:
            label=escape(drawing['name']);summary=drawing_summary(drawing)
            out.append(f'<a href="{escape(drawing["url"])}">{label}</a>'+(' · '+escape(summary) if summary else ''))
            if drawing.get('details'):
                context=[f'<a href="{PLAN}#{escape(key)}">{escape(title)}</a>' for key,title in drawing['detailTitles'].items()]
                out.append('Detail callouts · '+' · '.join(context))
            wording=drawing['wording']
            if wording and (len(wording)>1 or wording[0]['text'].upper()!=row['code'].upper()):
                lines=''.join(f'<tr><td>{escape(w["text"])}</td><td>{w["count"]}</td><td><code>{escape(w["handle"])}</code></td></tr>' for w in wording)
                out.append('<h4>Wording in the drawing</h4><table><thead><tr><th>Recorded legend</th><th>Records</th><th>Example handle</th></tr></thead><tbody>'+lines+'</tbody></table>')
        art=figures(row)
        if art:out.append(art)
        if not art and not row['official']:out.append('The drawing record identifies the code. No sign face is available for this designation.')
        out.append('')
    return '\n\n'.join(out)


def update_chart(path,rows):
    page=path.read_text()
    groups=defaultdict(list)
    adjacent=defaultdict(list)
    series=defaultdict(list)
    markup={}
    for row in rows:
        aliases=escape('|'.join(row['aliases']),quote=True)
        attrs=f' data-aliases="{aliases}" data-cad="{int(bool(row["drawings"]))}" data-plan="{int(bool(row["faces"]))}" data-mod="{int(row["modified"])}"'
        if row['official']:
            markup[row['official']['url']]=attrs
            continue
        code=escape(row['code'],quote=True); label=escape(row['status']);cat=row['category']
        images=row['art'] or row['faces']
        thumb=''
        if images:
            asset=escape(BASE+images[0]['image'],quote=True)
            thumb=f'<span class="simg"><img loading="lazy" src="{asset}" alt=""></span>'
        aliases=' '.join(row['aliases'])
        descriptor=(row['baseOfficial'] or {}).get('descriptor','')
        searchable=escape((aliases+' '+row['status']+' '+descriptor).lower(),quote=True)
        card=f'<a class="scard" href="{escape(row["url"])}" data-code="{code}" data-name="{searchable}" data-cat="{cat}" data-ca="plan"{attrs}>{thumb}<span class="scode">{code}</span><span class="sname">{label}</span></a>'
        prefix=re.match(r'([a-z]+\d*)',row['key'].lower())
        family='om' if row['key'].startswith('OM') else prefix[1] if prefix else ''
        if row['baseOfficial']:
            adjacent[row['baseOfficial']['url']].append(card)
        elif family and f'id="series-{family}"' in page:
            series[family].append(card)
        else:
            groups[cat].append(card)
    def annotate(match):
        tag,body=match.groups()
        href=re.search(r'href="([^"]+)"',tag)
        if not href:return match[0]
        return tag[:-1]+markup.get(href[1],'')+'>'+body+''.join(adjacent.pop(href[1],[]))
    page=re.sub(r'(<a class="scard"[^>]*>)(.*?</a>)',annotate,page,flags=re.S)
    if adjacent:raise ValueError(f'Missing base sign cards {list(adjacent)}')
    for family,cards in series.items():
        series_start=page.index(f'<h3 id="series-{family}">')
        end=page.index('</div></div>',series_start)
        page=page[:end]+''.join(cards)+page[end:]
    # Release 5/6 cards were appended by the publisher import. Restore their category order.
    fhwa=defaultdict(list)
    def move_release(match):
        fhwa[match[1]].append(match[0])
        return ''
    page=re.sub(r'<div class="sseries" data-cat="(regulatory|guide)"><h3>FHWA [^<]+</h3><div class="sgrid">.*?</div></div>',move_release,page,flags=re.S)
    for cat in dict.fromkeys([*groups,*fhwa]):
        cards=groups[cat]
        section=f'<div class="sseries" data-cat="{cat}"><h3>Drawing designations</h3><div class="sgrid">{"".join(cards)}</div></div>'
        section=''.join(fhwa[cat])+(section if cards else '')
        group=re.search(r'<h2 id="'+cat+r'"[^>]*>.*?</h2>',page)
        if not group and cat=='local':
            pos=page.rfind('<script>')
            if pos<0:raise ValueError('Sign chart script missing')
            page=page[:pos]+'<h2 id="local" class="sgroup">Local callouts and assemblies <span class="count">0</span></h2>'+section+'\n'+page[pos:]
        if group:
            end=re.search(r'<h2 id="[^"]+" class="sgroup"|<script',page[group.end():])
            pos=group.end()+end.start() if end else len(page)
            page=page[:pos]+section+'\n'+page[pos:]
    facets=re.search(r'<div class="sbtns">.*?</div>',page,re.S)[0]
    if groups.get('local'):facets=facets.replace('</div>','<button data-f="local">Local callouts</button></div>')
    controls=f"""
<link rel="stylesheet" href="{BASE}/js/sign-catalog.css">
<div class="sfilter sign-chart-tools" id="sfilter" hidden>
  <input type="search" id="sq" aria-label="Search sign codes and names" placeholder="Search by designation or name" autocomplete="off">
  <details id="sign-filter-options"><summary>Filters</summary><div class="sign-chart-options">
    {facets}
    <label>Records <select id="sorigin"><option value="">All records</option><option value="cad">Seen in CAD</option><option value="plan">Plan legend faces</option><option value="mod">Modified designs</option></select></label>
    <label><input type="checkbox" id="sca"> Identified for use in California</label>
    <small>Sources · <a href="https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/index.htm">FHWA layouts</a> · <a href="{BASE}/ca-mutcd/">CA MUTCD</a> · <a href="https://dot.ca.gov/programs/safety-programs/sign-specs/updates">Caltrans sign updates</a></small>
  </div></details>
  <span id="scount" class="scount" role="status"></span>
</div>
<noscript><nav aria-label="Sign categories"><a href="#regulatory">Regulatory</a> · <a href="#warning">Warning</a> · <a href="#school">School</a> · <a href="#ttc">Temporary traffic control</a> · <a href="#guide">Guide</a> · <a href="#local">Local callouts</a></nav></noscript>
"""
    a=page.index('<div class="srcbar">')
    b=page.index('<h2 id="regulatory"',a)
    page=page[:a]+controls+'\n'+page[b:]
    page=re.sub(r'<script>\s*\(\(\) => \{\s*const q = document.getElementById\(\'sq\'\).*?</script>',
                f'<script defer src="{BASE}/js/sign-catalog.js"></script>',page,count=1,flags=re.S)
    # Recompute headings after publisher withdrawals, later releases, and observed variants.
    def recount(m):
        heading,content=m.groups()
        return re.sub(r'(<span class="count">)\d+(</span>)',lambda h:h[1]+str(content.count('class="scard"'))+h[2],heading)+content
    page=re.sub(r'(<h2 id="[^"]+" class="sgroup">.*?</h2>)(.*?)(?=<h2 id="[^"]+" class="sgroup"|<script)',recount,page,flags=re.S)
    path.write_text(page)


def library_source_pages(root,rows,lookup):
    for source,(name,file) in LIBRARIES.items():
        group=[(r,d) for r in rows for d in r['drawings'] if d['source']==source]
        if not group:continue
        url=source_route(source)
        content=['---','title: '+json.dumps(name+' · drawing inventory'),'tableOfContents: false','---','',
                 f'<link rel="stylesheet" href="{BASE}/js/cad-downloads.css">',
                 f'<p><code>{escape(file)}</code> · {len(group):,} sign designations</p>',
                 '<p>Follow a designation to its sign reference. Expand the drawing evidence for entity handles and drawing context.</p>',
                 '<p><a href="'+BASE+'/data/cad-sign-evidence.json" download>Download the complete drawing evidence (JSON)</a></p>',
                 '<div class="cad-source-inventory">']
        for row,d in group:
            title=escape(row['code'])
            content.append(f'<section id="{callout_id(source,row["key"])}"><strong><a href="{escape(row["url"])}">{title}</a></strong>'+
                           drawing_evidence(d)+'</section>')
        content.append('</div>')
        path=root/'signs/cad/sources'/(source+'.md');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\n'.join(content[:4])+'\n\n'+'\n\n'.join(content[5:])+'\n')
        lookup.setdefault(name.upper(),[]).append([name+' · drawing evidence',url])


def build(root,lookup):
    rows=collect()
    evidence=SOURCE/'cad-signs.json';audit=SOURCE/'cad-signs-audit.json'
    if evidence.is_file() and audit.is_file():
        save(PUBLIC/'cad-sign-evidence.json',dict(drawings=drawing_audit(),records=drawing_records()))
    groups=defaultdict(list)
    for row in rows:
        group=row['url'].split('#')[0];groups[group].append(row)
        label=row['code']+' · '+(row['official']['descriptor'] if row['official'] else row['status'])
        for alias in row['aliases']:
            hits=lookup.setdefault(alias.upper(),[])
            if not any(url==row['url'] for _,url in hits):hits.insert(0,[label,row['url']])
    for url,items in groups.items():
        page=root/(url.removeprefix(BASE+'/').rstrip('/')+'.md')
        if not page.exists():
            head=next(r for r in items if '#' not in r['url'])
            page.write_text('---\ntitle: '+json.dumps(head['code']+' · '+head['status'])+'\ntableOfContents: false\n---\n')
        with page.open('a') as f:f.write('\n\n'+observed_section(sorted(items,key=lambda r:(not bool(r['official']),r['key'])))+'\n')
    library_source_pages(root,rows,lookup)
    save(CATALOG, rows)
    update_chart(root/'signs/index.md',rows)
    from cad_block_package import SOURCE as DOWNLOADS
    if (DOWNLOADS/'release.json').is_file():
        from cad_download_pages import build as build_download_pages
        build_download_pages(root,lookup)
    return rows
