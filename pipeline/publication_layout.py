"""Build publication-level sheet indexes and organize design topic entry points."""
import json
import re
from html import escape
from pathlib import Path
from current_catalog import BASE
from regional_reader import slug


def build(root):
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
        rows = []
        for page in doc['pages']:
            chapter = page['chapter']
            name = chapters.get(chapter, '')
            if re.fullmatch(r'Pages? [\d–-]+', name, re.I):
                name = ''
            rows.append(dict(page=page['page'], title=page['title'], chapter=name,
                             path=key+'/'+chapter, codes=page.get('drawings_orig', []),
                             drawings=drawings.get(page['page'], []), image=page.get('image'),
                             terms=' '.join(page.get('keywords', []))))
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
        topics = list(dict.fromkeys(t for row in doc['pages'] for t in row.get('topics', [])))
        scope = ', '.join(t.replace('-', ' ') for t in topics[:4])
        overview = f'Indexed subjects include {escape(scope)}.' if scope else ''
        reader = (f'<section class="publication" data-publication="{key}"><p class="pub-intro">'
                  f'{overview} Browse {len(rows)} pages in source order.</p>'
                  f'<noscript><a href="{BASE}/{first["path"]}/#p{first["page"]}">Open the first source page</a></noscript></section>')
        # Keep existing section IDs and meaningful links outside the generated chapter and thumbnail lists.
        extra = source_text[marker.end():]
        extra = re.sub(r'<h2>Chapters</h2><ul class="chlist">.*?</ul>|<h2>Every drawing and figure page</h2><div class="thumbgrid">.*?</div>', '', extra, flags=re.S)
        index.write_text(header+'\n'+marker.group()+reader+
                         f'<div class="book-reader" data-book="{key}" hidden></div>\n'+extra+'\n'+'\n'.join(filters))
        for chapter in doc['chapters']:
            file = root/key/(chapter['slug']+'.md')
            if file.exists():
                content = file.read_text()
                file.write_text(content.replace('class="book-reader"',f'data-parent-page="{chapter["first"]}" class="book-reader"',1))

    groups = json.loads(Path('data/topics.json').read_text())
    index = root/'topics/index.md'
    text = index.read_text()
    text = re.sub(r'<div class="vis-strip">.*?</div>', '', text, flags=re.S)
    start = text.index('Each topic page')
    end = text.index('<h2>', start)
    index.write_text(text[:start]+'Choose the street element you are reviewing. Each topic connects design tasks, governing guidance, and agency drawings.\n\n<div class="topic-directory">\n'+text[end:].replace('<h2>', '<section><h2>',1).replace('</div><h2>', '</div></section><section><h2>').replace('</div>\n<h2>', '</div></section>\n<section><h2>')+'</section></div>')
    for group in groups:
        for topic in group['topics']:
            file = root/'topics'/(topic['slug']+'.md')
            parts = re.split(r'^## (.+)$', file.read_text(), flags=re.M)
            sections = dict(zip(parts[1::2],parts[2::2]))
            order = ['Governing sections and agency guidance','Facility types and applications','Drawings by agency','Signing and striping plan details','CAD details for plan checking','NACTO design guidance','Local project examples']
            headings = [h for h in order if h in sections]+[h for h in sections if h not in order]
            quick = {'Governing sections and agency guidance':'Check the governing text','Facility types and applications':'Compare treatments','Drawings by agency':'Find agency sheets','Local project examples':'See local examples'}
            nav = '<nav class="topic-outline" aria-label="Browse this topic">'+''.join(f'<a href="#{slug(h)}">{quick[h]}</a>' for h in headings if h in quick)+'</nav>'
            intro = re.sub(r'\[Governing sections\].*?\[Drawings by agency\]\([^)]*\)',nav,parts[0])
            application = sections.get('Facility types and applications', '')
            treatments = re.split(r'^### (.+)$', application, flags=re.M)
            if len(treatments)>1:
                links = []
                for i in range(1,len(treatments),2):
                    heading = treatments[i].strip()
                    anchor = 'treatment-'+str((i+1)//2)
                    links.append(f'<a href="#{anchor}">{escape(heading)}</a>')
                    treatments[i] = f'<span id="{anchor}" class="anchor"></span>\n\n### '+heading+'\n'
                sections['Facility types and applications'] = ('<nav class="treatment-index" aria-label="Treatment index">'+''.join(links)+'</nav>\n\n'+''.join(treatments))
            file.write_text(intro+''.join('## '+h+'\n'+sections[h].strip('\n')+'\n\n' for h in headings))
