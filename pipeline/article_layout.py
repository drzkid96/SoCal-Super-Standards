"""Organize editorial reference pages around the guidance and its underlying source."""
import json
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from current_catalog import BASE

GALLERY = re.compile(r'<div class="(?:type-gallery|mgrid|mfig-grid)">.*?</div>', re.S)
FIGURE = re.compile(r'<figure\b[^>]*>.*?</figure>', re.S)
HEADING = re.compile(r'^## (.+)$', re.M)
META = re.compile(r'<div class="bul-meta">\s*(?:<div>.*?</div>\s*)+</div>', re.S)
GUIDES = {
    'nacto-urban-street': ('Compare lane widths, corner geometry and crossing treatments with the California standards for the project street.',
        'Lane width', 'https://nacto.org/publication/urban-street-design-guide/street-design-elements/lane-width/',
        'Curb extensions', 'https://nacto.org/publication/urban-street-design-guide/street-design-elements/curb-extensions/'),
    'nacto-urban-bikeway': ('Compare bicycle facility types, separation and intersection treatments with California design guidance.',
        'Bikeway design controls', 'https://nacto.org/publication/urban-bikeway-design-guide/designing-bikeways-for-all-ages-and-abilities/design-controls-for-bicycle-facilities/',
        'Protected bike lanes', 'https://nacto.org/publication/urban-bikeway-design-guide/designing-bikeways-for-all-ages-and-abilities/protected-bike-lanes/'),
    'cpbs-plts': ('Use the four pedestrian traffic stress levels to assess walking routes. Score street segments and crossings separately.',
        'Read the July 2025 PLTS study', 'https://rosap.ntl.bts.gov/view/dot/93236'),
}

def figure_targets(details):
    candidates = defaultdict(set)
    for item in details:
        if item.get('img') and item.get('url') and item.get('type') != 'Bulletin':
            candidates[item['img'].replace('/thumbs/', '/')].add(item['url'])
    targets = {url: next(iter(routes)) for url, routes in candidates.items() if len(routes) == 1}
    for source in Path('data/docs').glob('*__*.json'):
        for page in json.loads(source.read_text()).get('pages', []):
            if page.get('image') and page.get('url'):
                targets.setdefault(page['image'], page['url'])
    for sign in json.loads(Path('data/signs/signs.json').read_text()):
        if sign.get('svg'):
            targets[BASE + sign['svg']] = f'{BASE}/signs/{sign["slug"]}/'
    # A bulletin cover thumbnail can illustrate other publications. Anchor
    # extracted publisher art to its own numbered figure in the source bulletin.
    for directory in ('bulletins/dib-82-06','bulletins/dib-89-02','bulletins/dib-94','caltrans/hdm-ch1000'):
        owner = 'caltrans-' + directory.split('/')[-1]
        for image in Path('public/figs', directory).glob('*.webp'):
            targets[f'{BASE}/figs/{directory}/{image.name}'] = f'{BASE}/bulletins/{owner}/#figure-{image.stem}'
    return targets


def guide_intro(text, slug):
    if slug not in GUIDES:
        return text
    summary, *references = GUIDES[slug]
    text = re.sub(r'(?m)^description: .*$', lambda _: 'description: "' + summary + '"', text, count=1)
    old = re.search(r'<div class="note-box">.*?</div>', text, re.S)
    if not old:
        return text
    anchors = ' · '.join(f'<a href="{url}">{label}</a>' for label, url in zip(references[::2], references[1::2]))
    return text[:old.start()] + f'<p class="article-purpose">{summary}</p>\n\n<p class="article-sources">{anchors}</p>' + text[old.end():]


def organize(text, slug, targets, stats):
    text = guide_intro(text, slug)
    meta = META.search(text)
    if meta and 'class="article-source-line"' not in text:
        block = meta[0].replace('https://dot.ca.gov/programs/design/design-information-bulletins-dibs',
            'https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib82-06-a11y.pdf') if slug == 'caltrans-dib-82-06' else meta[0]
        block = block.replace('https://www.dgs.ca.gov/BSC/Codes','https://www.dgs.ca.gov/DSA/Resources/Access-Compliance-Reference-Materials').replace('California Building Standards Commission official copy','California DSA accessibility publications')
        link = re.search(r'<a href="([^"]+)">([^<]+)</a>', block)
        label = 'Read the publisher PDF' if link and '.pdf' in link[1].lower() else 'Publisher reference'
        source = f'<a href="{link[1]}">{label}</a>' if link else ''
        text = text[:meta.start()] + '<div class="article-source-line">' + source + '<details><summary>Edition and policy status</summary>' + block + '</details></div>' + text[meta.end():]
        stats['bulletin source panels'] += 1
    if slug == 'ladot-lpi-2021':
        text = text.replace('No Turn on Red — R10-11 / R10-15 Pairing','R10-15 turning vehicles yield to pedestrians').replace('>No Turn on Red</span>', '>Turning movements</span>').replace('>R10-11 / R10-15 Pairing</strong>', '>R10-15 · Yield to pedestrians</strong>')
    headers = list(HEADING.finditer(text))
    if not headers:
        return text
    lead = text[:headers[0].start()]
    sections = []
    seen = set()
    for i, heading in enumerate(headers):
        title = heading[1]
        body = text[heading.end():headers[i+1].start() if i+1<len(headers) else None]
        if title.startswith('Official Caltrans'):
            def publisher_figure(f):
                img = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', f[0])
                target = targets.get(img[1].replace('/thumbs/', '/'), '') if img else ''
                if target.startswith(f'{BASE}/bulletins/{slug}/#figure-'):
                    source_image = img[1].replace('/thumbs/', '/')
                    restored = re.sub(r'(<a href=")[^"]+(">)', lambda a: a[1]+source_image+a[2], f[0], count=1)
                    if ' id="figure-' not in restored:
                        restored = restored.replace('<figure ', f'<figure id="{target.split("#")[1]}" ', 1)
                    return restored
                return f[0]
            body = FIGURE.sub(publisher_figure, body)
        # Repeated thumbnail galleries at the end often reused the very same
        # sheets as earlier illustrated facility types. Keep every unique figure.
        def gallery(match):
            def figure(f):
                image = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', f[0])
                if not image:
                    return f[0]
                src = image[1].replace('/thumbs/', '/')
                if title == 'Visual Reference' and src in seen:
                    stats['redundant figures removed'] += 1
                    return ''
                seen.add(src)
                href = re.search(r'<a href="([^"]+)">\s*<img', f[0])
                if href and not title.startswith('Official Caltrans') and targets.get(src) and targets[src] != href[1]:
                    stats['source reader links'] += 1
                    return f[0].replace(href[0], '<a href="' + escape(targets[src], quote=True) + '"><img', 1)
                return f[0]
            out = FIGURE.sub(figure, match[0])
            return out if '<figure' in out else ''
        body = GALLERY.sub(gallery, body)
        # Keep the existing Markdown table/list uninterrupted; move introductory
        # galleries after that complete first unit of guidance.
        first = re.match(r'(?s)^(?:\s|<!--.*?-->)*?(?=<div class="(?:type-gallery|mgrid|mfig-grid)">)', body)
        if first:
            position = first.end()
            pending = []
            while m := GALLERY.match(body, position):
                pending.append(m[0])
                position = re.match(r'\s*', body[m.end():]).end() + m.end()
            rest = body[position:]
            if pending and rest.strip() and not rest.lstrip().startswith(('<!--','<section class="xidx')):
                split = re.split(r'\n\s*\n', rest.strip(), maxsplit=1)
                body = '\n\n' + split[0] + '\n\n' + '\n\n'.join(pending) + '\n\n' + (split[1] if len(split)>1 else '') + '\n\n'
                stats['sections reordered'] += 1
        if title == 'Visual Reference' and not body.strip():
            body = '\n\n<span id="visual-reference"></span>\n\n'
            sections.append(('', body)); continue
        sections.append((title, body))
    # Preserve anchors and all photos; enter the decision table or chapter
    # navigator before full treatments and project photography.
    early = {'Local project examples', 'NACTO design guidance', 'Bikeway Facility Classes & Selection (Visual Guide)'}
    leading = []
    while sections and sections[0][0] in early:
        leading.append(sections.pop(0))
    if leading:
        sections[1:1] = leading
        stats['articles with guidance before gallery'] += 1
    return lead + ''.join(('## ' + title if title else '') + body for title, body in sections)


def build(root, details):
    stats = Counter()
    targets = figure_targets(details)
    for family in ('guides','bulletins'):
        for page in (root/family).glob('*.md'):
            if page.stem == 'index':
                continue
            original = page.read_text()
            revised = organize(original, page.stem, targets, stats)
            if revised != original:
                page.write_text(revised)
                stats['articles updated'] += 1
    print('Editorial articles:', dict(stats))
    return stats
