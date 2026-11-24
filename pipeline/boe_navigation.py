"""Index the headings and parent links present in the imported BOE manual."""
import re
from html import escape
from pathlib import Path
from lxml import html

from current_catalog import BASE, PUBLIC, read, save

MANUAL = BASE + '/boe/street-design/'
HEADING = re.compile(r'<h([2-6])\b([^>]*)>(.*?)</h\1\s*>', re.I | re.S)
SECTION = re.compile(r'^E\s*\d+(?:\.\d+)*\b', re.I)


def build(root, lookup):
    pages = {}
    for entry in read(PUBLIC / 'boe-sections.json'):
        url = entry['url']
        path = root / (url.removeprefix(BASE + '/').strip('/') + '.md')
        source = path.read_text()
        document = html.fragment_fromstring(source.split('---', 2)[2], create_parent='article')
        parents = document.xpath('.//nav[@class="boe-crumb"]/a/@href')
        parent = next((p for p in reversed(parents) if p != MANUAL), MANUAL)
        used = set(document.xpath('.//*[@id]/@id')) | {'_top'}
        headings = []

        def index_heading(match):
            heading = html.fragment_fromstring(match[0])
            label = ' '.join(heading.text_content().split())
            if not label:
                return match[0]
            code = SECTION.match(label)
            anchor = heading.get('id')
            if not anchor:
                stem = re.sub(r'[^a-z0-9]+', '-', (code[0] if code else label).lower()).strip('-') or 'section'
                anchor = stem
                suffix = 2
                while anchor in used:
                    anchor = f'{stem}-{suffix}'
                    suffix += 1
                used.add(anchor)
            headings.append({'depth': int(match[1]), 'slug': anchor, 'text': label})
            if code:
                hits = lookup.setdefault(code[0].upper(), [])
                hit = ['LA BOE ' + label, url + '#' + anchor]
                if hit not in hits:
                    hits.append(hit)
            return match[0] if heading.get('id') else f'<h{match[1]}{match[2]} id="{escape(anchor, quote=True)}">{match[3]}</h{match[1]}>'

        rewritten = HEADING.sub(index_heading, source)
        if rewritten != source:
            path.write_text(rewritten)
        pages[url] = {'label': entry['title'], 'parent': parent, 'headings': headings}
    for url in pages:
        ancestors = {url}
        parent = pages[url]['parent']
        while parent != MANUAL:
            if parent not in pages or parent in ancestors:
                raise ValueError(f'Invalid BOE hierarchy at {url}: {parent}')
            ancestors.add(parent)
            parent = pages[parent]['parent']
    save(Path('.standards/boe-navigation.json'), pages)
