"""Build compact, static illustrations at the paragraph that cites the original."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from lxml import etree, html
from PIL import Image, ImageOps
from current_catalog import BASE, read
from visual_types import make_visuals

END = re.compile(r'</(p|li)\s*>', re.I)
NUMBER = r'\d{1,2}[A-Z]-\d+(?:[A-Za-z])?(?:\s*\(CA\))?'
MENTION = re.compile(r'\b(?:(Federal MUTCD|FHWA(?: MUTCD)?|CA MUTCD(?: 2026)?|California MUTCD)\s*[,·:–-]?\s+)?'
                     r'(Figures?|Tables?)\s+('+NUMBER+r')', re.I)
CONTINUATION = re.compile(r'\s*(,?\s*(?:and|or|through|to)\s+|,\s*|[–—])('+NUMBER+r')(?![\w-])', re.I)
EXCLUDED = {'nav','aside','figure','figcaption','table','summary','script','style','button','del','code','pre','math'}
SKIP_CLASS = {'sec-toc','topic-list','topic-records','sgrid','thumbgrid','mgrid','rsign-grid',
              'mfig-grid','quick-lookup','sheet-source-actions','boe-source','boe-crumb','secmeta',
              'boe-group','detail-description','ref-previews'}


@dataclass(frozen=True)
class Art:
    target: str
    full: str
    label: str
    title: str


def preview_card(art, thumb, example=''):
    target, full, label, title = (escape(x, quote=True) for x in
                                  (art.target, art.full, art.label, art.title))
    name = escape(example, quote=True) if example else title
    return (f'<div class="ref-card"><a class="ref-image" href="{full}" aria-label="Enlarge {label} — {name}">'
            f'<img loading="lazy" decoding="async" src="{escape(thumb, quote=True)}" alt="{label} — {name}"></a>'
            f'<a class="ref-label" href="{target}">{label}</a>'
            + (f'<span>{"Example · " if example else ""}{name}</span>' if name and name != label else '')
            + '</div>')


class ReferencePreviews:
    def __init__(self, dist):
        self.dist = dist
        self.by_url = {}
        self.aliases = defaultdict(dict)
        self.manual = {}
        self.groups = []
        self.counts = Counter()
        self.families = Counter()
        self.missing = Counter()
        details = read(dist/'data/details.json')
        rows = {}
        for row in details:
            kind = row['type']
            target = row['url']
            full = (row.get('full') or row.get('img') or '').replace('/thumbs/figs/', '/figs/')
            if (not full.startswith(BASE+'/') or self.local(full).suffix.lower() not in ('.webp','.png','.jpeg','.jpg','.gif','.svg')
                    or not self.local(full).is_file()):
                continue
            if '#' not in target and not target.startswith(BASE+'/details/'):
                continue
            label = (kind+' '+row['num'] if kind in ('Figure','Table') else row['src']+' · '+row['num'])
            art = Art(target, full, label, row['title'])
            rows[target] = art
            self.by_url[target] = art
            if kind in ('Figure','Table'):
                edition = 'mutcd' if row['src']=='Federal MUTCD' else 'ca-mutcd'
                self.manual[edition,kind,row['num'].upper()] = art
                for alias in (full,row.get('original')):
                    if alias:
                        self.aliases[alias][label.upper()] = art
        groups, _ = make_visuals(details)
        for values in groups.values():
            self.groups.append([(title, regex, rows[row['url']]) for title, regex, row, _ in values
                                if row['url'] in rows])
        for sign in read(dist/'data/signs-index.json').values():
            image = sign.get('svg','')
            if image.startswith(BASE+'/') and self.local(image).is_file():
                self.by_url[sign['url']] = Art(sign['url'],image,sign['code'],sign.get('descriptor',''))
        # BOE has no drawing catalog. Match only IDs attached to actual artwork in the compiled manual.
        remote = set()
        for page in (dist/'boe/street-design').rglob('index.html'):
            if 'boe-figure-' not in page.read_text():
                continue
            doc = html.parse(str(page))
            route = BASE+'/'+page.relative_to(dist).as_posix().removesuffix('index.html')
            for node in doc.xpath('//*[starts-with(@id,"boe-figure-")]'):
                imgs = [node] if node.tag=='img' else node.xpath('.//img[@src]')
                if not imgs:
                    continue
                image = imgs[0]
                src = image.get('src')
                caption = ' '.join(node.xpath('./figcaption//text()')).split(' · ',1)[0].strip()
                if not caption.startswith('Figure E '):
                    from boe_references import FILENAME
                    match = FILENAME.search(unquote(urlsplit(src).path).split('/')[-1].replace('_',' '))
                    caption = 'Figure E '+match[1].upper() if match else 'BOE figure'
                target = route+'#'+node.get('id')
                self.by_url[target] = Art(target,src,caption,(image.get('alt') or '').strip())
                if urlsplit(src).hostname=='completestreetdesignmanual.engineering.lacity.gov':
                    remote.add(src)
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.remote = dict(zip(sorted(remote),pool.map(self.city_thumbnail,sorted(remote))))
        self.counts['BOE images cached locally'] = sum(src!=thumb for src,thumb in self.remote.items())

    def local(self, url):
        return self.dist/unquote(urlsplit(url).path.removeprefix(BASE+'/'))

    @staticmethod
    def shrink(source, path):
        with Image.open(source) as im:
            thumb = ImageOps.exif_transpose(im)
            thumb.thumbnail((520,400),Image.Resampling.LANCZOS)
            path.parent.mkdir(parents=True,exist_ok=True)
            thumb.save(path,'WEBP',quality=86,method=4)

    def city_thumbnail(self, src):
        # Keep the official URL as the full-size target and the fallback on offline builds.
        key = sha256(src.encode()).hexdigest()[:24]+'.webp'
        cache = Path('.boe-cache/figure-thumbs')/key
        path = self.dist/'reference-thumbs'/key
        try:
            if not cache.is_file():
                req = Request(src,headers={'User-Agent':'SoCal Super Standards figure previews'})
                with urlopen(req,timeout=8) as response:
                    data = response.read(16*1024*1024+1)
                if len(data)>16*1024*1024:
                    return src
                self.shrink(BytesIO(data),cache)
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(cache.read_bytes())
            return BASE+'/reference-thumbs/'+key
        except (OSError,ValueError,Image.DecompressionBombError):
            return src

    @lru_cache(maxsize=None)
    def thumbnail(self, src):
        if src in self.remote:
            return self.remote[src]
        if not src.startswith(BASE+'/'):
            return src
        original = self.local(src)
        if original.suffix.lower()=='.svg':
            return src
        small = BASE+'/thumbs/'+src.removeprefix(BASE+'/')
        if self.local(small).is_file():
            return small
        target = 'reference-thumbs/'+sha256(src.encode()).hexdigest()[:24]+'.webp'
        self.shrink(original,self.dist/target)
        return BASE+'/'+target

    def mentioned(self, text, edition):
        """Match figure lists and bounded numeric ranges in their own publisher edition."""
        for m in MENTION.finditer(text):
            ed = ('mutcd' if m[1].lower().startswith(('federal','fhwa')) else 'ca-mutcd') if m[1] else edition
            if not ed:
                continue
            kind = m[2].lower().rstrip('s').title()
            num = ''.join(m[3].upper().split())
            numbers = [num]
            end = m.end()
            while match := CONTINUATION.match(text,end):
                end = match.end()
                next_num = ''.join(match[2].upper().split())
                if match[1].strip(' ,').lower() in ('through','to','–','—'):
                    a = re.fullmatch(r'(.+-)(\d+)(\(CA\))?',numbers[-1])
                    b = re.fullmatch(r'(.+-)(\d+)(\(CA\))?',next_num)
                    if a and b and (a[1],a[3])==(b[1],b[3]) and 0<int(b[2])-int(a[2])<=80:
                        numbers.extend(a[1]+str(n)+(a[3] or '') for n in range(int(a[2])+1,int(b[2])))
                numbers.append(next_num)
            for n in numbers:
                art = self.manual.get((ed,kind,n))
                if art:
                    yield art
                else:
                    self.missing[ed+' '+kind+' '+n] += 1

    def enhance(self, body, route):
        self.counts['articles examined'] += 1
        if not END.search(body):
            return body
        # Annotate a temporary parse with closing-tag offsets, then splice into the original
        # bytes. This preserves Astro markup, MathML, footnotes and the publisher's lists.
        def mark(m):
            return m[0]+f'<!--ref-at-{m.start()}-->'
        doc = html.fragment_fromstring(END.sub(mark,body),create_parent='div')
        changes = {}
        family = route.removeprefix(BASE+'/').split('/')[0]
        edition = family if family in ('ca-mutcd','mutcd') else None
        seen_types = set()
        section = ''
        for el in doc.iter():
            if el.tag in ('h2','h3','h4','h5','h6'):
                seen_types.clear()
                section = el.text_content()
                continue
            if el.tag not in ('p','li'):
                continue
            marker = el.getnext()
            if not isinstance(marker,etree._Comment) or not marker.text.startswith('ref-at-'):
                continue
            if el.xpath('.//img|./p|./ul|./ol') or any(
                    n.tag in EXCLUDED or SKIP_CLASS.intersection(n.get('class','').split())
                    for n in (el,*el.iterancestors())):
                continue
            prose = ' '.join(''.join(el.xpath('.//text()[not(ancestor::del or ancestor::code or ancestor::sup or ancestor::math)]')).split())
            links = el.xpath('.//a[@href][not(ancestor::del or ancestor::sup or ancestor::code)]')
            # A bare menu entry is not a discussion of the item.
            if el.tag=='li' and links and not ''.join(el.xpath('.//text()[not(ancestor::a)]')).strip(' \n·—–,.;:'):
                continue
            cards = {}
            for link in links:
                if link.get('class')=='pn':
                    continue
                target = urljoin(route,link.get('href'))
                art = self.by_url.get(target)
                if not art:
                    matches = self.aliases.get(target,{})
                    label = ' '.join(link.text_content().upper().split()).replace('FIGURES ','FIGURE ').replace('TABLES ','TABLE ')
                    art = matches.get(label)
                if art and art.target!=route:
                    cards[art.target] = (art,'')
            for art in self.mentioned(prose,edition):
                cards.setdefault(art.target,(art,''))
            # Explain a facility where it is introduced or compared. Exact citations take
            # precedence over a representative example from a different agency.
            if not cards and family not in ('signs','details','keywords','markings') and len(prose)>30:
                for group in self.groups:
                    matches = [(title,rx,art) for title,rx,art in group if rx.search(prose)]
                    for title,rx,art in matches:
                        if art.target in seen_types or (len(matches)<2 and not rx.search(section)):
                            continue
                        if title.startswith('Class ') and not re.search(r'bik|bicycl|cycl|shared.use path',section+' '+prose,re.I):
                            continue
                        cards.setdefault(art.target,(art,title))
                        seen_types.add(art.target)
            if not cards:
                continue
            offset = int(marker.text.removeprefix('ref-at-'))
            if el.tag=='p':
                offset += len('</p>')
            changes[offset] = '<div class="ref-previews" data-pagefind-ignore="">' + ''.join(
                preview_card(a,self.thumbnail(a.full),example) for a,example in cards.values())+'</div>'
            self.counts['paragraphs or list items illustrated'] += 1
            self.counts['preview cards'] += len(cards)
        if not changes:
            return body
        self.families[family] += 1
        pieces = []
        last = 0
        for offset,markup in sorted(changes.items()):
            pieces.extend((body[last:offset],markup))
            last = offset
        return ''.join(pieces)+body[last:]
