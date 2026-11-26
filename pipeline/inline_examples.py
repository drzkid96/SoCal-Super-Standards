"""Compact source artwork for references in rendered reading paragraphs."""
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re

from lxml import html
from PIL import Image
from current_catalog import BASE, read
from visual_types import GROUPS, applies_to_route

MANUALS = {'mutcd': 'Federal MUTCD', 'ca-mutcd': 'CA MUTCD 2026'}
NUMBER = r'\d[A-Z]-\d+(?:\s*\(CA\))?'
CITATION = re.compile(r'\b(Figure|Table)s?\s+(' + NUMBER + r')(?![\w-])', re.I)
CONTINUATION = re.compile(r'\s*(?:,\s*(?:and\s+)?|and\s+)(' + NUMBER + r')(?![\w-])', re.I)
# Only distinctive terms warrant an illustrative example without an explicit citation.
APPLICATIONS = [
    (r'\bpedestrian push ?buttons?\b', 'Figure 4I-3'),
    (r'\bcrossbuck assembl(?:y|ies)\b', 'Figure 8B-3'),
    (r'\bcommunity wayfinding\b', 'Figure 2D-30'),
    (r'\btwo-way left-turn lanes?\b', 'Figure 3B-7'),
    (r'\blane.reduction transitions?\b', 'Figure 3B-14'),
    (r'\bdo not block intersection markings?\b', 'Figure 3B-24'),
    (r'\bschool area signs?\b', 'Figure 7B-1'),
]
FIELD_PHOTOS = [
    (r'\btwo.way (?:separated (?:bikeway|bike lane)|cycle track)s?', 2,
     'Two-way separated bikeway in Redondo Beach', 'redondo-two-way'),
    (r'\b(?:green.{0,35}driveway|driveway.{0,35}green)', 5,
     'Green bikeway markings across a Los Angeles driveway', 'la-green-driveway'),
]

BLOCKED = {'figure','figcaption','nav','details','table','del','button','pre','code','aside','header','footer'}


@dataclass(frozen=True)
class Example:
    source: str
    number: str
    title: str
    url: str
    image: str


class Artwork:
    def __init__(self, dist):
        self.dist = dist
        self.urls = {}
        self.numbers = {}
        self.thumbs = {}
        for row in read(dist/'data/details.json'):
            kind = row['type']
            art = row.get('full') or row.get('img')
            if not art or kind not in {'Figure','Table','Standard drawing','Line type','Marking','Agency sheet'}:
                continue
            number = (kind + ' ' if kind in {'Figure','Table'} else '') + row['num']
            record = Example(row['src'], number, row['title'], row['url'], art)
            self.urls[record.url] = record
            if kind in {'Figure','Table'}:
                self.numbers[row['src'], number] = record
        # Drawing references name a sheet within a set. Show its native page, including
        # cases such as S-481.0 sheet 3 whose diagram differs from the first sheet.
        for manual in ('mpp-531','mpp-521','red-book'):
            publication=dist/'data/publications/ladot'/(manual+'.json')
            if not publication.is_file():continue
            for row in read(publication):
                for code,position,count in row.get('drawings',[]):
                    slug=re.sub(r'[^a-z0-9]+','-',code.lower()).strip('-')
                    route=f'{BASE}/details/ladot/{manual}-{slug}/'
                    parent=self.urls.get(route)
                    if parent and row.get('image'):
                        url=route+f'#sheet-{position}'
                        label=code+(f' · sheet {position} of {count}' if count>1 else '')
                        self.urls[url]=Example(parent.source,label,parent.title,url,row['image'])
        retired = set(read('data/ca_deleted_signs.json')['codes'])
        for sign in read('data/signs/signs.json'):
            if sign['code'] in retired or not sign.get('svg'):
                continue
            url = f"{BASE}/signs/{sign['slug']}/"
            self.urls[url] = Example(sign['source'], sign['code'], sign['name'], url, BASE + sign['svg'])
        self.applications = [(re.compile(term, re.I), self.numbers['CA MUTCD 2026', key]) for term,key in APPLICATIONS]

        scoped = {(row.source, row.number): row for row in self.urls.values()}
        for group in ('speed-and-calming','accessibility','temporary-traffic-control','transit','striping-intersections'):
            for _, pattern, agency, code, _ in GROUPS[group]:
                record = scoped.get((agency, code))
                if record:
                    self.applications.append((re.compile(r'\b(?:'+pattern+r')\b', re.I), record))
        for pattern, n, title, slug in FIELD_PHOTOS:
            src = f'{BASE}/figs/projects/{slug}.webp'
            photo = Example('Caltrans DIB 89-02', f'Photo {n}', title,
                            f'{BASE}/bulletins/caltrans-dib-89-02/#photo-{n}', src)
            self.applications.insert(0, (re.compile(pattern, re.I), photo))

    def thumbnail(self, src):
        if src in self.thumbs:
            return self.thumbs[src]
        if not src.startswith(BASE+'/'):
            return None
        relative = Path(src.removeprefix(BASE+'/'))
        original = self.dist/relative
        if not original.is_file():
            return None
        url = src
        if relative.suffix.lower() != '.svg':
            target = Path('inline-art')/relative.with_suffix('.webp')
            out = self.dist/target
            out.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(original) as img:
                img.thumbnail((224,176), Image.Resampling.LANCZOS)
                img.save(out, 'WEBP', quality=83)
            url = BASE+'/'+target.as_posix()
        self.thumbs[src] = url
        return url

    def paragraph(self, markup, route, seen):
        group = route.removeprefix(BASE+'/').split('/')[0]
        if not any(token in markup.lower() for token in ('href=', 'figure', 'table')) and group in MANUALS:
            return ''
        paragraph = html.fragment_fromstring(markup)
        for removed in paragraph.xpath('.//del | .//sup | .//code | .//math'):
            removed.drop_tree()
        wording = ' '.join(paragraph.text_content().split())
        found = []
        edition = MANUALS.get(group)
        if edition:
            for m in CITATION.finditer(wording):
                cited_edition = edition
                qualifier = re.search(r'(Federal MUTCD|FHWA MUTCD|CA MUTCD|California MUTCD)(?: 2026)?[, ·:]*$', wording[:m.start()], re.I)
                if qualifier:
                    cited_edition = MANUALS['mutcd' if qualifier[1].lower().startswith(('federal','fhwa')) else 'ca-mutcd']
                kind = m[1].title()+' '
                end = m.end()
                found.append(self.numbers.get((cited_edition, kind+m[2].upper().replace(' ',''))))
                while follow := CONTINUATION.match(wording, end):
                    found.append(self.numbers.get((cited_edition, kind+follow[1].upper().replace(' ',''))))
                    end = follow.end()
        for href in paragraph.xpath('.//a/@href'):
            found.append(self.urls.get(route+href if href.startswith('#') else href))
        supplemental = not any(found) and not edition and len(wording.split()) >= 12
        if supplemental:
            found = [record for term,record in self.applications
                     if applies_to_route(record.source,group) and term.search(wording)]
        cards = []
        for record in found:
            if not record or record.url == route or record.url in seen:
                continue
            if '/details/ladot/' in route and record.url.partition('#')[0] == route:
                continue
            src = self.thumbnail(record.image)
            if not src:
                continue
            seen.add(record.url)
            credit = ('Example · ' if supplemental else '')+record.source+' · '+record.number
            cards.append(f'<a href="{escape(record.url)}"><img loading="lazy" decoding="async" src="{escape(src)}" alt=""><span><small>{escape(credit)}</small>{escape(record.title)}</span></a>')
            if len(cards) >= 3:
                break
        return '<div class="inline-examples" data-pagefind-ignore>'+''.join(cards)+'</div>' if cards else ''
