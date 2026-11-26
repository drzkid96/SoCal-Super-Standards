"""Apply publisher withdrawals before rendering, linking, and indexing the reference."""
import json
import re
from html import escape
from pathlib import Path

BASE = '/SoCal-Super-Standards'
PUBLIC = Path('public/data')
STATUS = '/bulletins/standards-status/#deleted-california-signs'


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def route_map(deletions):
    old = '/caltrans/standard-plans-2018/'
    current = '/caltrans/standard-plans-2026/'
    routes = {old: current, old+'01-pages-1-6/': current, '/signs/retired/': STATUS, '/ladot/mpp-details/':'/ladot/mpp-531/'}
    details = read('data/catalog/details.json')
    for row in details:
        url = row['url'].removeprefix(BASE)
        if row['src'] == 'Caltrans Std. Plans 2018':
            routes[url] = url.replace('2018-', '2026-')
    # These undated Supplemental Guide reprints have a dated master in MPP 531.
    for code in ('s-481-0', 's-525-0'):
        routes['/details/ladot/supp-street-design-guide-'+code+'/'] = '/details/ladot/mpp-531-'+code+'/'
    for sign in read('data/signs/signs.json'):
        if sign['code'] in deletions['codes']:
            routes['/signs/'+sign['slug']+'/'] = STATUS
    return routes


def prepare(root, lookup, deletions):
    routes = route_map(deletions)
    stale = {BASE+key for key in routes}
    old_paths = re.compile('|'.join(re.escape(u) for u in sorted(stale, key=len, reverse=True)) + r'(?:#[\w.-]+)?')
    notice = deletions['source']

    def update_link(match):
        return BASE + routes[match[0].split('#')[0].removeprefix(BASE)]

    for path in routes:
        file = root / (path.strip('/')+'.md')
        index = root / path.strip('/') / 'index.md'
        file.unlink(missing_ok=True)
        index.unlink(missing_ok=True)

    for key, hits in list(lookup.items()):
        live = [r for r in hits if r[1].split('#')[0] not in stale]
        if live:
            lookup[key] = live
        else:
            del lookup[key]

    details = [r for r in read('data/catalog/details.json') if r['url'].split('#')[0] not in stale]
    for row in details:
        if row.get('also'):
            row['also'] = [r for r in row['also'] if r.get('url','').split('#')[0] not in stale and r.get('src') != 'Caltrans Std. Plans 2018']
    save(PUBLIC/'details.json', details)
    for name in ('previews', 'checks'):
        path = PUBLIC/(name+'.json')
        data = json.loads(path.read_text().replace('deleted-ca-signs-list-v1-0--a11y','deleted-ca-signs-list-v1-0-a11y'))
        for key, value in list(data.items()):
            if key.removeprefix(BASE).split('#')[0] in routes:
                del data[key]
            elif name == 'checks':
                for item in value:
                    item['links'] = [link for link in item['links'] if link[1].split('#')[0] not in stale]
                data[key] = [item for item in value if item['links'] or 'also appears' not in item['title']]
        save(path, data)
    preview_path = PUBLIC/'previews.json'
    previews = read(preview_path)
    for key,item in list(previews.items()):
        images = [img for img in item.get('i',[]) if '/redraw/' not in img and ('/vibes/' not in img or img.endswith('/vibes/la-county-map.webp'))]
        if key.startswith('/caltrans/la28-supplement/'):
            images = [img for img in images if not img.endswith('/vibes/la-county-map.webp')]
        item['i'] = [img.replace('/thumbs/figs/vibes/la-county-map.webp','/figs/county/la-county-planning-small.webp') for img in images]
        if not item['i']:del previews[key]
    save(preview_path, previews)
    signs = read(PUBLIC/'signs-index.json')
    for key in list(signs):
        if signs[key]['code'] in deletions['codes']:
            del signs[key]
    for row in read('data/reference/fhwa-layouts-5-6.json'):
        code = row['code']
        slug = re.sub('[^a-z0-9-]+','-',code.lower()).strip('-')
        signs[code.upper()] = dict(code=code, descriptor=row['name'], url=f'{BASE}/signs/{slug}/', ca='unverified')
    save(PUBLIC/'signs-index.json', {k.upper():v for k,v in signs.items()})
    save(Path('.standards/redirects.json'), routes)

    for path in root.rglob('*'):
        if path.suffix not in ('.md','.mdx'):
            continue
        text = original = path.read_text()
        if path == root/'markings/index.md':
            text=text.replace('203 markings','117 MUTCD markings')

            text=re.sub(r'<div class="mcard"[^>]*><a class="mimg" href="[^"]*std-plans-2018-[^"]*">.*?<div class="msrc">.*?</div></div></div>','',text)
        if path == root/'signs/index.md':
            text=text.replace('1,472 distinct',f'{len({v["url"] for v in signs.values()}):,} distinct')
            text=text.replace('href="'+BASE+'/signs/retired/">Retired California codes','href="https://dot.ca.gov/programs/safety-programs/sign-specs/updates">Caltrans sign updates')
            text = re.sub(r'<a class="scard"[^>]*>.*?</a>', lambda m: '' if any('href="'+u+'"' in m[0] for u in stale) else m[0], text)
        if any(u in text for u in stale):
            # Drop links to older editions from related-drawing suggestions.
            text = re.sub(r'<a class="xchip"[^>]*>.*?</a>', lambda m: '' if 'std-plans-2018-' in m[0] else m[0], text)
            text = old_paths.sub(update_link, text)
        if text != original:
            path.write_text(text)
    save(PUBLIC/'retired.json', deletions)
    return details
