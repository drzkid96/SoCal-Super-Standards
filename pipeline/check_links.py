"""Check local document, asset and fragment destinations after the Pages build."""
import json
import re
from collections import defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

root = Path('dist')
base = '/SoCal-Super-Standards/'
origin = 'https://drzkid96.github.io'
pages = sorted(root.rglob('*.html'))
if not pages: raise SystemExit('Build the site before checking links.')
ids, refs = {}, defaultdict(set)
for path in pages:
    source = base + path.relative_to(root).as_posix().removesuffix('index.html')
    body = path.read_text()
    ids[source] = set(unescape(v) for v in re.findall(r'\s(?:id|name)="([^"]+)"', body))
    for url in set(re.findall(r'\s(?:href|src)="([^"]+)"', body)):
        if url.startswith(('https:', 'http:')) and not url.startswith(origin+base):continue
        full = urlsplit(urljoin(origin+source, unescape(url)))
        if full.netloc == 'drzkid96.github.io' and full.path.startswith(base):
            refs[(unquote(full.path),unquote(full.fragment))].add(source)
for name in ('details','lookup','checks','previews'):
    for url in set(re.findall(r'"('+base+r'[^"]*)"',(root/f'data/{name}.json').read_text())):
        u=urlsplit(url);refs[(unquote(u.path),unquote(u.fragment))].add('data/'+name)
bad=[]
for (url,anchor),sources in refs.items():
    dest=root/url.removeprefix(base)
    route=url.removesuffix('index.html')
    if route not in ids:route=route.rstrip('/')+'/'
    if not dest.is_file() and not (root/(str(dest.relative_to(root)).rstrip('/')+'.html')).is_file() and route not in ids or (anchor and route in ids and anchor not in ids[route] and not anchor.startswith(':~:text=')):
        bad.append((url+'#'+anchor,sorted(sources)[0]))
for target,source in bad[:50]: print(target,'from',source)
print(f'{len(pages)} HTML pages, {len(bad)} missing destinations')
raise SystemExit(bool(bad))
