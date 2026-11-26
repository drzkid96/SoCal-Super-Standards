"""Build publication-level sheet indexes and organize design topic entry points."""
import json
import re
from html import escape
from pathlib import Path
from current_catalog import BASE
from regional_reader import slug
from publication_purpose import PURPOSE


def build(root, ladot_sets=None):
    from ladot_drawings import manual_index, source_title, agency_index, SHEET_LABELS
    ladot_sets = ladot_sets or {}
    editions=json.loads(Path("data/reference/ladot-editions.json").read_text())
    sets = {}
    for detail in (root/'details').rglob('*.md'):
        body = detail.read_text()
        code = re.search(r'<span class="dwg-num">([^<]+)</span>', body)
        if not code:
            continue
        images = re.findall(r'<figure (?:id="sheet-\d+" )?class="dfig"><a href="[^"]*/figs/([^"]+?)/p(\d+)\.webp"', body)
        if images and len({book for book, page in images}) == 1:
            sets[(images[0][0],code[1])] = [int(page) for book,page in images]
    for source in Path('data/docs').glob('*.json'):
        doc = json.loads(source.read_text())
        if not isinstance(doc, dict) or not doc.get('pages'):
            continue
        key = doc['slug']
        index = root / key / 'index.md'
        if not index.exists():
            continue
        chapters = {c['slug']: c['title'] for c in doc['chapters']}
        drawings = {}
        for (publication, code), sheets in sets.items():
            if publication == key:
                for position, page in enumerate(sheets, 1):
                    drawings.setdefault(page, []).append([code, position, len(sheets)])
        manual=key.split('/')[-1] if key.startswith('ladot/') else ''
        owned=ladot_sets.get(manual,{})
        rows = []
        for page in doc['pages']:
            chapter = page['chapter']
            name = chapters.get(chapter, '')
            if re.fullmatch(r'Pages? [\d–-]+', name, re.I):
                name = ''
            drawing=drawings.get(page['page'], [])
            label=source_title(page,owned,drawing) if owned else page['title']
            rows.append(dict(page=page['page'], title=label, chapter=name,
                             path=key+'/'+chapter, codes=page.get('drawings_orig', []),
                             drawings=drawings.get(page['page'], []), image=(f'{BASE}/figs/{key}/p{page["page"]:04d}.webp' if drawing and owned else page.get('image')),
                             terms=' '.join(page.get('keywords', []))))
            if owned and drawing:
                c,pos,_=drawing[0]
                if (manual,c,pos) in SHEET_LABELS:rows[-1]['sheetLabel']=SHEET_LABELS[manual,c,pos]
        out = Path('public/data/publications') / (key+'.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
        source_text = index.read_text()
        marker = re.search(r'<div class="srcbar">.*?</div>', source_text, re.S)
        if not marker:
            continue
        filters = re.findall(r'<span hidden data-pagefind-filter="[^"]+"></span>', source_text)
        header = source_text.split('\n---\n', 1)[0]+'\n---\n'
        first = rows[0]
        overview = PURPOSE.get(key, doc['title'])
        steps = ''
        if key == 'fhwa/step-uncontrolled-crossings':
            pages={row['page']:row['path'] for row in rows}
            shortcuts=((15,'Inventory a site'),(22,'Select a countermeasure'),(31,'Monitor outcomes'))
            steps=' '+' · '.join(f'<a id="p{page}" href="{BASE}/{pages[page]}/#p{page}" data-reader-shortcut="{page}">{label}</a>'
                                for page,label in shortcuts)+'.'
        reader = (f'<section class="publication" data-publication="{key}"><p class="pub-intro">'
                  f'{escape(overview)}{steps}</p>'
                  f'<noscript><a href="{BASE}/{first["path"]}/#p{first["page"]}">Open the first source page</a></noscript></section>')
        # Keep existing section IDs and meaningful links outside the generated chapter and thumbnail lists.
        extra = source_text[marker.end():]
        extra = re.sub(r'<h2>Chapters</h2><ul class="chlist">.*?</ul>|<h2>Every drawing and figure page</h2><div class="thumbgrid">.*?</div>', '', extra, flags=re.S)
        if owned:
            extra=''
            reader=manual_index(manual,doc,owned,editions[manual],reader)
        index.write_text(header+'\n'+marker.group()+reader+
                         f'<div class="book-reader" data-book="{key}" hidden></div>\n'+extra+'\n'+'\n'.join(filters))
        for chapter in doc['chapters']:
            file = root/key/(chapter['slug']+'.md')
            if file.exists():
                content = file.read_text()
                file.write_text(content.replace('class="book-reader"',f'data-parent-page="{chapter["first"]}" class="book-reader"',1))

    if ladot_sets:agency_index(root,ladot_sets)

    from browse_hubs import directory_pages, treatments
    groups = directory_pages(root)
    for group in groups:
        for topic in group['topics']:
            file = root/'topics'/(topic['slug']+'.md')
            parts = re.split(r'^## (.+)$', file.read_text(), flags=re.M)
            sections = dict(zip(parts[1::2],parts[2::2]))
            order = ['Governing sections and agency guidance','Facility types and applications','Drawings by agency','Signing and striping plan details','CAD details for plan checking','NACTO design guidance','Local project examples']
            headings = [h for h in order if h in sections]+[h for h in sections if h not in order]
            # The design-task links open the actual governing sources. The site header already
            # provides section navigation; keep a single navigation row in the article.
            intro = re.sub(r'\[Governing sections\].*?\[Drawings by agency\]\([^)]*\)', '', parts[0])
            if 'Facility types and applications' in sections:
                sections['Facility types and applications']=treatments(sections['Facility types and applications'])
            for name in ('Governing sections and agency guidance','Drawings by agency'):
                if name in sections:
                    content=sections[name]
                    sections[name]=re.sub(r'(?:<details class="topic-list">.*?</details>\s*)+',lambda m:'<div class="topic-reference-index">'+m[0].strip()+'</div>\n\n',content,flags=re.S)
            for name in ('Signing and striping plan details','CAD details for plan checking'):
                if name not in sections:continue
                content=sections[name]
                rows=re.findall(r'^- \[([^\]]+)\]\(([^)]+)\)\s*$',content,re.M)
                if not rows:continue
                remaining=re.sub(r'^- \[[^\]]+\]\([^)]+\)\s*$','',content,flags=re.M).strip()
                links=[f'<a href="{escape(url,quote=True)}">{escape(label)}</a>' for label,url in rows]
                def grid(items):return '<div class="topic-plan-links">'+''.join(items)+'</div>'
                sections[name]=remaining+'\n\n'+grid(links[:4])
                if len(links)>4:
                    sections[name]+=f'<details class="remaining-plan-links"><summary>{len(links)-4} more details from this set</summary>'+grid(links[4:])+'</details>'
            file.write_text(intro+''.join('## '+h+'\n'+sections[h].strip('\n')+'\n\n' for h in headings))
