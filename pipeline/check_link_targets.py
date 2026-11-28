"""Check that internal links land where their text says (run after the Pages build).

A link whose text names a sign code, section, figure, table, detail or drawing number has to reach a page,
or a fragment on that page, that names the same thing. Exits 1 and lists the first mismatches when any
link lands elsewhere.

  python3 pipeline/check_link_targets.py [--all]
"""
import re
import sys
from collections import defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path('dist')
BASE = '/SoCal-Super-Standards/'
ORIGIN = 'https://drzkid96.github.io'
# pages whose lists are drawn by script (the checker reads the HTML only), and indexes whose link text quotes a figure
SCRIPTED = {BASE + 'bulletins/standards-status/'}
QUOTING = {BASE + 'keywords/'}
TAG = re.compile(r'<[^>]+>')
LINK = re.compile(r'<a\s[^>]*?href="([^"#][^"]*|#[^"]+)"[^>]*>(.*?)</a>', re.S)
# identifiers a reader would expect to find at the destination
PATTERNS = [
    ('section', re.compile(r'\b(?:Section\s+)?(\d[A-Z]\.\d{2,3})\b')),
    ('figure', re.compile(r'\bFigure\s+(\d[A-Z]-\d+(?:\s?\(CA\))?)', re.I)),
    ('table', re.compile(r'\bTable\s+(\d[A-Z]-\d+(?:\s?\(CA\))?)', re.I)),
    ('detail', re.compile(r'\bDetail\s+(\d{1,2}[A-Z]?)\b')),
    ('sign', re.compile(r'\b((?:[RWMSDEGIOK]|SW|OM|EM|SC|SG|SR|SM)\d{1,3}[A-Z]?(?:-\d{1,3})?[A-Za-z]{0,2}\(CA\)|(?:[RWMDEIO]|SW|OM|EM|SC|SG)\d{1,2}-\d{1,2}[A-Za-z]{0,2})(?![\w-])')),
    ('drawing', re.compile(r'\b([ABST]-?\d{3}\.\d)\b')),
]


def norm(s):
    return re.sub(r'[\s ]+', '', unescape(s)).upper()


def text_of(html):
    return re.sub(r'\s+', ' ', unescape(TAG.sub(' ', html))).strip()


def fragment_text(body, anchor):
    """Text of the element carrying the id, plus the heading or block that follows it."""
    m = re.search(r'\sid="' + re.escape(anchor) + r'"', body)
    if not m:
        return ''
    start = body.rfind('<', 0, m.start())
    return text_of(body[start:start + 4000])


def main(show_all=False):
    pages = sorted(ROOT.rglob('*.html'))
    if not pages:
        raise SystemExit('Build the site before checking link targets.')
    bodies, titles = {}, {}
    for p in pages:
        route = BASE + p.relative_to(ROOT).as_posix().removesuffix('index.html')
        body = p.read_text(errors='ignore')
        bodies[route] = body
        t = re.search(r'<title>(.*?)</title>', body, re.S)
        h = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S)
        titles[route] = text_of((t.group(1) if t else '') + ' ' + (h.group(1) if h else ''))
    bad = defaultdict(set)
    for route, body in bodies.items():
        if route in QUOTING:
            continue
        main_part = body.split('<main', 1)[-1]
        for href, inner in LINK.findall(main_part):
            label = text_of(inner)
            if not label or len(label) > 120:
                continue
            full = urlsplit(urljoin(ORIGIN + route, unescape(href)))
            if full.netloc != 'drzkid96.github.io' or not full.path.startswith(BASE):
                continue
            dest = unquote(full.path)
            if dest.endswith('.html'):
                dest = dest.removesuffix('index.html')
            if dest not in bodies or dest in SCRIPTED:
                continue          # check_links.py reports missing pages
            wants = [norm(m.group(1)) for _, rx in PATTERNS for m in rx.finditer(label)]
            if not wants:
                continue
            where = norm(titles[dest])
            frag = unquote(full.fragment)
            if frag and not frag.startswith(':~:'):
                where += norm(fragment_text(bodies[dest], frag))
            else:
                where += norm(text_of(bodies[dest].split('<main', 1)[-1][:30000]))
            if not any(w in where for w in wants):
                bad[(label, dest + ('#' + full.fragment if full.fragment else ''))].add(route)
    items = sorted(bad.items(), key=lambda kv: -len(kv[1]))
    for (label, dest), srcs in (items if show_all else items[:60]):
        print(f'{label!r} -> {dest}  ({len(srcs)} pages, e.g. {sorted(srcs)[0]})')
    print(f'{len(pages)} pages, {len(items)} links whose destination does not name what the link says')
    return bool(items)


if __name__ == '__main__':
    raise SystemExit(main('--all' in sys.argv))
