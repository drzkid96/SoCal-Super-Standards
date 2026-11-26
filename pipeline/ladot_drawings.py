"""Restore LADOT's native drawing order and page ownership from the issued manuals."""
from collections import defaultdict
from hashlib import sha256
from html import escape, unescape
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re

from current_catalog import BASE, read, save


# The third physical page is explicitly titled "Supplement to S-440.0".
SHEET_LABELS = {('mpp-531','S-440.0',1):'Sheet 1 of 2',
                ('mpp-531','S-440.0',2):'Sheet 2 of 2',
                ('mpp-531','S-440.0',3):'Supplement to S-440.0'}
CROSSWALK = ['Signing and pavement markings','Red curb for sight distance',
             'Red curb with a curb extension','Centerline widening at intersections']


def sheet_label(key,code,n,count):
    return SHEET_LABELS.get((key,code,n),f'Sheet {n} of {count}')


def slug(code):
    return re.sub(r'[^a-z0-9]+', '-', code.lower()).strip('-')


def source_pdf(key, edition):
    import pymupdf
    from time import sleep
    cache = Path('.ladot-sources') / (key+'.pdf')
    public = Path('public/ladot-publications') / cache.name
    for path in (cache, public):
        if path.exists() and sha256(path.read_bytes()).hexdigest() == edition['sha256']:
            data = path.read_bytes()
            break
    else:
        for attempt in range(3):
            try:
                req = Request(edition['url'], headers={'User-Agent':'SoCalStandards publication reader'})
                with urlopen(req, timeout=65) as response:
                    data = response.read()
                if sha256(data).hexdigest() != edition['sha256']:
                    raise ValueError('LADOT publisher edition changed: '+key)
                break
            except OSError:
                if attempt==2:raise
                sleep(2 ** attempt)
    for path in (cache, public):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or sha256(path.read_bytes()).hexdigest() != edition['sha256']:
            path.write_bytes(data)
    return pymupdf.open(stream=data, filetype='pdf')


def ownership(key, pdf, doc, edition):
    """MPP bookmarks identify publisher boundaries; the Red Book prints its index on pp. 5–7."""
    owners = {}
    if key == 'red-book':
        for page in list(pdf)[4:7]:
            for line in page.get_text().splitlines():
                entry = re.search(r'S[- ](\d+(?:\.\d+)*(?:[A-Z])?)\s*[. …]+\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$', line)
                if entry:
                    for number in range(int(entry[2])+7,int(entry[3] or entry[2])+8):
                        if number in owners:raise ValueError('Overlapping Red Book index rows')
                        owners[number]='S-'+entry[1]
    else:
        current = None
        starts = {}
        for level,title,page in pdf.get_toc():
            match = re.match(r'S-(\d+(?:[-.]\d+){0,2})',title)
            if level == 1 and page > 0 and match:
                code=match[1].replace('-','.')
                starts[page]='S-'+code+('' if '.' in code else '.0')
        for page in range(edition['firstDrawing'],len(pdf)+1):
            current=starts.get(page,current)
            owners[page]=current
    assert len(pdf)==edition['count']
    assert set(owners)==set(range(edition['firstDrawing'],len(pdf)+1)), (key, sorted(set(range(edition['firstDrawing'],len(pdf)+1))-set(owners)))
    groups=defaultdict(list)
    for page,code in sorted(owners.items()):
        assert doc['pages'][page-1]['drawings'][0]==code,(key,page,code)
        groups[code].append(page)
    return groups


def scan(key, number):
    return f'{BASE}/figs/ladot/{key}/p{number:04d}.webp'


def create_missing_scan(key, number, pdf):
    from PIL import Image
    target=Path('public')/scan(key,number).removeprefix(BASE+'/')
    if not target.exists():
        page=pdf[number-1]
        image=page.get_pixmap(dpi=150, alpha=False)
        output=Image.frombytes('RGB',(image.width,image.height),image.samples)
        output.save(target,format='WebP',quality=88,method=4)
    thumb=Path('public/thumbs')/target.relative_to('public')
    if not thumb.exists():
        with Image.open(target) as preview:
            preview.thumbnail((360,360),Image.Resampling.LANCZOS)
            thumb.parent.mkdir(parents=True,exist_ok=True)
            preview.save(thumb,format='WebP',quality=78)


def native_route(key,code):
    return f'{BASE}/details/ladot/{key}-{slug(code)}/'


def prepare(root, details, look):
    editions=read('data/reference/ladot-editions.json')
    inventory={}
    previews=read("public/data/previews.json")
    index=read("public/data/ladot-index.json")
    for key,edition in editions.items():
        doc=read('data/docs/ladot__'+key+'.json')
        pdf=source_pdf(key,edition)
        groups=ownership(key,pdf,doc,edition)
        chapter_text={}
        inventory[key]={}
        by_url={r['url']:r for r in details}
        for code,numbers in groups.items():
            href=native_route(key,code)
            file=root/(href.removeprefix(BASE+'/').strip('/')+'.md')
            old=file.read_text() if file.exists() else ''
            meta=doc.get('drawing_titles',{}).get(code,{})
            first=doc['pages'][numbers[0]-1]
            cleaned=first.get('clean') or {}
            title=meta.get('title') or cleaned.get('title') or first['title'] or code
            # Remove per-sheet qualifiers from the title of the entire drawing set.
            title=re.sub(r'\s*\((?:Standard Drawing )?S-[^)]*\)|\s*\(Sheet [^)]+\)|,?\s+Sheet [\w-]+ of \d+.*$','',title,flags=re.I).strip(' :,.')
            title=title or code
            fixed=(code,title,numbers,href)
            inventory[key][code]=fixed
            existing_notes={}
            for item in re.finditer(r'<figure class="dfig"><a href="[^"]*/p(\d+)\.webp".*?</figure>\s*(<details class="ocr">.*?</details>)',old,re.S):
                # Match only notes immediately following this particular image.
                near=old[item.start():item.start(2)]
                pages=re.findall(r'<figure class="dfig"><a href="[^"]*/p(\d+)\.webp"',near)
                existing_notes[int(pages[-1])]=item[2]
            date=meta.get('date')
            sheets=f'{len(numbers)} sheet'+('s' if len(numbers)>1 else '')
            if (key,code,3) in SHEET_LABELS:sheets='2 sheets and 1 supplement'
            native=f'{BASE}/ladot-publications/{key}.pdf'
            body=['---','title: '+json.dumps(code+' '+title),'description: '+json.dumps(f'{doc["short"]} drawing {code}. {title}. {sheets}.'),'tableOfContents: false','---','',
                  f'<div class="dwg-head" data-native-pdf="{native}" data-native-pages="{",".join(map(str,numbers))}"><div><span class="dwg-num">{code}</span><span class="dwg-src">{escape(doc["short"])} · {escape(doc["edition"])}</span></div><div class="dwg-facts"><span>{sheets}</span><span>PDF '+('page '+str(numbers[0]) if len(numbers)==1 else f'pages {numbers[0]}–{numbers[-1]}')+'</span>'+ (f'<span>Dated {escape(date)}</span>' if date else '')+'</div></div>','',
                  f'<a class="drawing-open" href="#sheet-1">View drawing</a> · <a href="{BASE}/ladot/{key}/">Browse {escape(doc["short"])}</a>', '', '## Sheets' if len(numbers)>1 else '## Sheet','']
            row=by_url.get(href,{})
            if not row:
                row.update(src=doc['short'],sg='LADOT',type='Standard drawing',num=code,url=href,topics=first.get('topics',[]))
                details.append(row)
            row.update(title=title,sheets=len(numbers),full=scan(key,numbers[0]),img=first.get('image') or scan(key,numbers[0]))
            thumb=row['img'].replace('/figs/','/thumbs/figs/')
            if (Path('public')/thumb.removeprefix(BASE+'/')).exists():row['img']=thumb
            if row.get('sum','').lower().startswith('sheet ') or not old or 'class="dupnote"' in old:row['sum']=''
            for alias in (code,code.removesuffix('.0'),doc['short']+' '+code):
                hits=look.setdefault(alias.upper(),[])
                if not any(hit[1].split('#')[0]==href for hit in hits):hits.append([f'{doc["short"]} {code} {title}',href])
            for order,number in enumerate(numbers,1):
                p=doc['pages'][number-1]
                create_missing_scan(key,number,pdf)
                image=scan(key,number)
                role=sheet_label(key,code,order,len(numbers))
                subject=' · '+CROSSWALK[order-1] if (key,code)==('mpp-531','S-481.0') else ''
                if len(numbers)>1:body.extend([f'### {role}{subject} (page {number})',''])
                cap=f'{doc["short"]} {code}, '+(role if role.startswith('Supplement') else f'sheet {order}')+'.' 
                body.append(f'<figure class="dfig"><a href="{image}"><img loading="lazy" src="{image}" alt="{escape(code)} sheet {order}"></a><figcaption>{escape(cap)} <a href="{BASE}/ladot/{key}/#p{number}">Open in the document</a>.</figcaption></figure>')
                notes=existing_notes.get(number)
                if not notes:
                    path=root/('ladot/'+key)/(p['chapter']+'.md')
                    if path not in chapter_text:chapter_text[path]=path.read_text()
                    source=chapter_text[path].split(f'id="p{number}" class="anchor">',1)[-1].split('class="anchor">',1)[0]
                    match=re.search(r'<details class="ocr">.*?</details>',source,re.S)
                    if match:notes=match[0]
                if notes:body.append(notes)
                body.append('')
            signs=re.search(r'<h2>Signs on this drawing</h2><div class="tsigns">.*?</div>',old,re.S)
            if signs:body.append(signs[0])
            view=href.removeprefix(BASE)
            for pos,page in enumerate(numbers,1):
                image=scan(key,page).removeprefix(BASE).replace('/figs/','/thumbs/figs/')
                previews[view+f'#sheet-{pos}']={'t':f'{code} {title} · Sheet {pos} of {len(numbers)}','i':[image]}
            previews[view]={'t':f'{code} {title}','i':previews[view+'#sheet-1']['i']}
            row['img']=BASE+previews[view]['i'][0]
            file.write_text('\n'.join(body)+'\n')
        owned={page:(code,title,href,pos) for code,title,pages,href in inventory[key].values() for pos,page in enumerate(pages,1)}
        for record in index:
            if record.get('doc')!=doc['short']:continue
            page=record['page']
            refs=doc['pages'][page-1].get('drawings_orig',[])
            record['drawingReferences']=refs
            record['drawings']=[owned[page][0]] if page in owned else []
            if page in owned:
                code,title,href,pos=owned[page]
                record['title']=code+' · '+title
                record['drawingURL']=href+f'#sheet-{pos}'
        pdf.close()
    save('public/data/previews.json',previews)
    save('public/data/ladot-index.json',index)
    link_references(root,inventory,editions)
    return inventory


def source_title(page,owned,drawing):
    if not drawing:
        return page['title'] or 'Source page '+str(page['page'])
    code,order,count=drawing[0]
    return code+' · '+owned[code][1]


def index_rows(groups):
    return ''.join(
        f'<li><a href="{href}#sheet-1"><strong>{escape(code)}</strong> {escape(title)}</a>'
        f'<small>{len(pages)} sheet'+('s' if len(pages)>1 else '')+
        f' · PDF {pages[0]}'+(f'–{pages[-1]}' if len(pages)>1 else '')+'</small></li>'
        for code,title,pages,href in groups)


def manual_index(key,doc,groups,edition,reader):
    rows=index_rows(groups.values())
    tables=''.join(f'<a id="{slug(name)}" href="#p{page}" data-pdf-page="{page}">{name} · {escape(title)}</a>' for name,(page,title) in edition['tables'].items())
    pdf=f'{BASE}/ladot-publications/{key}.pdf'
    fallback=''.join(f'<p id="p{page}"><a href="{pdf}#page={page}">Open {escape(doc["short"])} PDF page {page}</a></p>' for page in range(1,len(doc['pages'])+1))
    table_pages=' '.join(slug(name)+'='+str(row[0]) for name,row in edition['tables'].items())
    reader=reader.replace('data-publication=',f'data-table-pages="{table_pages}" data-native-pdf="{pdf}" data-publisher-pdf-url="{edition["url"]}" data-publication=',1)

    return (f'<section class="ladot-drawing-index" data-drawing-index><h2>Find a standard drawing</h2>'
            f'<input type="search" aria-label="Filter drawings" placeholder="Drawing number or title" hidden>'
            f'<p class="drawing-count" role="status">{len(groups)} drawings</p><ul>{rows}</ul><button type="button" data-expand-drawings hidden>Show all {len(groups)} drawings</button></section>'
            f'<div class="ladot-page-targets" data-pagefind-ignore>{fallback}</div><details class="ladot-manual-pages"><summary>Read {escape(doc["short"])} by page</summary>{reader}</details>'
            f'<div class="ladot-source-links">{tables}<a href="{pdf}" download="LADOT_{key.upper()}.pdf">Download original manual PDF</a>'
            f'<a href="{edition["url"]}">LADOT publisher copy</a></div>')


def agency_index(root,sets):
    path=root/'ladot/index.md'
    text=path.read_text()
    # Replace the former cross-reference table containing policy-page mentions.
    if '## Standard drawing index' not in text:return
    before,after=text.split('## Standard drawing index',1)
    tail=re.sub(r'^.*?</table>','',after,count=1,flags=re.S)
    tail=re.sub(r'<script>.*?</script>','',tail,flags=re.S)
    tables=''.join(f'<details><summary>{name} · {len(sets[key])} drawings</summary><ul>{index_rows(sets[key].values())}</ul></details>'
                   for key,name in [('mpp-531','MPP 531 · Striping, channelization and signing'),('mpp-521','MPP 521 · Signal design'),('red-book','Red Book · Signal construction')])
    before=re.sub(r'(href="[^"]*/details/ladot/[^"#]+/)"',r'\1#sheet-1"',before)
    path.write_text(before+'<h2>Standard drawings by manual</h2><div class="ladot-agency-sets">'+tables+'</div>'+tail)


def link_references(root,inventory,editions):
    """Link printed references in their own publication before sitewide citation matching."""
    all_codes=defaultdict(list)
    for key,entries in inventory.items():
        for code in entries:all_codes[code].append(key)
    protected=re.compile(r'(<a\b[^>]*>.*?</a>|<h[1-6]\b[^>]*>.*?</h[1-6]>|<code\b[^>]*>.*?</code>|<[^>]+>|!?\[[^\]]*\]\([^\n]+?\))',re.S)
    code_ref=re.compile(r'(?<![\w-])(?P<code>S-\d+(?:\.\d+)*[A-Z]?)(?:[ ,]*(?:\(\s*)?sheet\s+(?P<sheet>\d+)(?:\s+of\s+\d+)?\)?)?(?![\w-]|\.\d)',re.I)
    for file in (root/'ladot').rglob('*.md'):
        path=file.relative_to(root/'ladot').parts
        key=path[0] if path[0] in inventory else None
        if not key and file.stem not in ('curb-paint','marked-crosswalks'):continue
        if file.name=='index.md':continue
        raw=file.read_text()
        prefix,front,body=raw.split('---',2)
        if key:
            native={page:(code,href,pos) for code,title,pages,href in inventory[key].values() for pos,page in enumerate(pages,1)}
            def meta(m):
                page=int(m[2])
                codes=re.findall(r'S-\d+(?:\.\d+)*[A-Z]?',unescape(re.sub('<[^>]+>','',m[3])))
                current=native.get(page)
                links=[]
                if current:
                    code,href,pos=current
                    links.append(f'Drawing <a href="{href}#sheet-{pos}">{code} · View drawing</a>')
                refs=[]
                for code in dict.fromkeys(codes):
                    if current and code==current[0]:continue
                    owner=key if code in inventory[key] else next(iter(all_codes.get(code,[])),None)
                    if owner:refs.append(f'<a href="{native_route(owner,code)}#sheet-1">{code}</a>')
                if refs:links.append('Cited drawings: '+', '.join(refs))
                return m[1]+' &middot; '.join(links)
            body=re.sub(r'(<span id="p(\d+)" class="anchor"></span>\s*###?[^\n]*\s*<div class="pmeta">)Drawings: (.*?)(?= &middot;|</div>)',meta,body,flags=re.S)
        fragments=protected.split(body)
        for i in range(0,len(fragments),2):
            def drawing(match):
                code=match['code'].upper()
                target=key if code in inventory.get(key,{}) else next((k for k in ('mpp-531','mpp-521','red-book') if k in all_codes[code]),None)
                if not target:return match[0]
                num=int(match['sheet'] or 1)
                if not 1<=num<=len(inventory[target][code][2]):return match[0]
                return f'<a href="{native_route(target,code)}#sheet-{num}">{match[0]}</a>'
            text=code_ref.sub(drawing,fragments[i])
            if key:
                for name,(page,title) in editions[key]['tables'].items():
                    text=re.sub(r'(?<!\w)'+name+r'(?![\w.-])',lambda m:f'<a href="{BASE}/ladot/{key}/#p{page}">{m[0]}</a>',text,flags=re.I)
            legacy=editions.get(key,{}).get('legacyFigures')
            if legacy:
                def figure(m):
                    page=legacy['pages'].get(m[1].upper().replace(' ',''))
                    if not page:return m[0]
                    return f'<a href="{legacy["url"]}#page={page}" title="{legacy["publication"]}, PDF page {page}">{m[0]}</a>'
                text=re.sub(r'\bFigure\s+(3[AB]-\d+(?:\s*\(CA\))?)(?!\d)',figure,text,flags=re.I)
            fragments[i]=text
        file.write_text(prefix+'---'+front+'---'+''.join(fragments))
