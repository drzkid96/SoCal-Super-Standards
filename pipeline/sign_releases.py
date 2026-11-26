"""Prepare FHWA Release 5 and 6 sign pages from the official release table and verified PDF bookmarks."""
from collections import defaultdict
from html import escape
from pathlib import Path
import json
import re

BASE = '/SoCal-Super-Standards'
FHWA = 'https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/'
CATALOG = Path('data/reference/fhwa-layouts-5-6.json')


def prepare(root, lookup):
    rows = json.loads(CATALOG.read_text())
    cards = defaultdict(list)
    for row in rows:
        code, name = row['code'], row['name']
        release, pages = row['release'], row['pages']
        slug = re.sub('[^a-z0-9-]+', '-', code.lower()).strip('-')
        url = f'{BASE}/signs/{slug}/'
        path = root / 'signs' / (slug+'.md')
        if path.exists():
            raise ValueError(f'FHWA layout conflicts with existing sign page: {code}')
        source = FHWA+'pdf/'+row['file']
        lines = ['---', 'title: '+json.dumps(code+' '+name), 'tableOfContents: false', '---', '',
                 f'FHWA Standard Highway Signs, 2024 Edition · Release {release} · Issued {row["date"]}.', '']
        thumb = ''
        if pages:
            lines.append(f'[Open the official dimensioned drawing]({source}#page={pages[0]})')
            figures = []
            for i, page in enumerate(pages,1):
                img = f'/figs/fhwa-shs/{row["file"][:-4]}-{page}.webp'
                label = f'{escape(code)} · Sheet {i} of {len(pages)}'
                if Path('public'+img).is_file():
                    if not thumb:
                        from PIL import Image
                        preview = img.replace('/fhwa-shs/', '/fhwa-shs/chart/')
                        target = Path('public'+preview)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with Image.open('public'+img) as sheet:
                            sheet.thumbnail((400, 320))
                            sheet.save(target, 'WEBP', quality=82)
                        thumb = f'<span class="simg"><img loading="lazy" decoding="async" src="{BASE}{preview}" alt=""></span>'
                    figures.append(f'<figure class="mfig"><span id="sheet-{i}"></span><a href="{BASE}{img}"><img src="{BASE}{img}" loading="lazy" alt="{label}, FHWA dimensioned layout"></a><figcaption>{label} · <a href="{source}#page={page}">Official PDF page {page}</a></figcaption></figure>')
                elif len(pages)>1:
                    lines.append(f'- [Sheet {i}]({source}#page={page})')
            if figures:lines.extend(['','<div class="mfig-grid">'+''.join(figures)+'</div>'])
        else:
            lines.append('FHWA lists this designation in the release table. The individual layout page has not been confirmed.')
            lines.append(f'[Find {escape(code)} in the official release index]({FHWA}index.htm)')
        lines.extend(['','[California MUTCD sign provisions]('+BASE+'/ca-mutcd/) · [FHWA release history]('+FHWA+'index.htm)',''])
        path.write_text('\n'.join(lines))
        category = 'regulatory' if code.startswith('R') else 'guide'
        lookup.setdefault(code.upper(),[]).insert(0,[f'{code} {name} · FHWA Release {release}',url])
        cards[category].append(f'<a class="scard" data-cat="{category}" data-ca="unverified" data-code="{escape(code)}" data-name="{escape(name.lower())}" href="{url}">{thumb}<span class="scode">{escape(code)}</span><span class="sname">{escape(name)}</span></a>')
    index = root/'signs/index.md'
    new = ''.join(f'<div class="sseries" data-cat="{k}"><h3>FHWA {k} layouts · Releases 5 and 6</h3><div class="sgrid">{"".join(v)}</div></div>' for k,v in cards.items())
    index.write_text(index.read_text().replace('<script>', new+'\n\n<script>',1))
