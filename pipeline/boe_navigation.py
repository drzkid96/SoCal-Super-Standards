"""Index the headings and parent links present in the imported BOE manual."""
import re
from pathlib import Path
from lxml import html

from current_catalog import BASE, PUBLIC, read, save

MANUAL = BASE + '/boe/street-design/'
SECTION = re.compile(r'^E\s*\d+(?:\.\d+)*\b', re.I)


def build(root, lookup):
    pages = {}
    for entry in read(PUBLIC / 'boe-sections.json'):
        url = entry['url']
        path = root / (url.removeprefix(BASE + '/').strip('/') + '.md')
        source = path.read_text()
        front, delimiter, body = source.partition('\n---\n')
        document = html.fragment_fromstring(body, create_parent='div')
        parents = document.xpath('.//nav[@class="boe-crumb"]/a/@href')
        parent = next((p for p in reversed(parents) if p != MANUAL), MANUAL)
        used = set(document.xpath('.//*[@id]/@id')) | {'_top'}
        headings = []

        for heading in document.xpath('.//h2 | .//h3 | .//h4 | .//h5 | .//h6'):
            label = ' '.join(heading.text_content().split())
            if not label:
                continue
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
                heading.set('id', anchor)
            headings.append({'depth': int(heading.tag[1]), 'slug': anchor, 'text': label})
            if code:
                hits = lookup.setdefault(code[0].upper(), [])
                hit = ['LA BOE ' + label, url + '#' + anchor]
                if hit not in hits:
                    hits.append(hit)
        # The city supplies HTML. A blank line in a quoted alt attribute can otherwise
        # end a Markdown HTML block halfway through an image and swallow later headings.
        markup = html.tostring(document, encoding='unicode', with_tail=False)
        markup = markup.replace('\r', '&#13;').replace('\n', '&#10;')
        path.write_text(front + delimiter + '\n' + markup + '\n')
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
