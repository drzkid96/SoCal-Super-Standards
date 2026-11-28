"""Landing pages: one CAD hub with shared tabs, and the pavement marking landing laid out for lookup.

Runs last in prepare_reference.py, after every generator has written its cards, so the pages are arranged
from what was actually built.
"""
import re
from html import escape
from pathlib import Path

BASE = '/SoCal-Super-Standards'
CAD_TABS = [('cad', 'CAD home'), ('signs/cad', 'Sign blocks'), ('markings/cad', 'Pavement marking blocks'),
            ('signals/cad', 'Signal and survey blocks'), ('cad', 'Templates and tools', 'tools')]


def cad_tabs(current):
    """Tab strip shared by every CAD page; current is the route ('cad', 'signs/cad', ...)."""
    links = []
    for item in CAD_TABS:
        route, label = item[0], item[1]
        anchor = '#' + item[2] if len(item) > 2 else ''
        here = route == current and not anchor
        links.append(f'<a href="{BASE}/{route}/{anchor}"' + (' aria-current="page"' if here else '') + f'>{escape(label)}</a>')
    return '<nav class="cad-tabs" aria-label="CAD">' + ''.join(links) + '</nav>'


def add_cad_tabs(root):
    """Put the CAD tabs at the top of each block library page (the hub carries its own)."""
    for route in ('signs/cad', 'markings/cad', 'signals/cad'):
        page = root / route / 'index.md'
        if not page.is_file():
            continue
        text = page.read_text()
        if 'class="cad-tabs"' in text:
            continue
        head, sep, body = text.partition('\n---\n')
        page.write_text(head + sep + '\n' + cad_tabs(route) + '\n' + body)


CATEGORY_LABELS = {
    'cat-lines': 'Striping details', 'cat-arrows': 'Arrows', 'cat-words': 'Words and symbols',
    'cat-crosswalks': 'Crosswalks', 'cat-applications': 'Lane-use examples', 'cat-bike': 'Bicycle markings',
    'cat-color': 'Colored pavement', 'cat-curb': 'Curb paint', 'cat-local': 'Local agency standards',
}


def markings_landing(root):
    """Lead with search and a picture for every category; cards carry only their own facts."""
    page = root / 'markings/index.md'
    text = page.read_text()
    head, sep, body = text.partition('\n---\n')
    first = body.find('<section class="mcat-sec">')
    if first < 0 or 'class="mtiles"' in body:
        return
    sections = body[first:]
    # reading notes written for single detail pages repeat on every card here; the card keeps its own lines
    sections = re.sub(r'<p class="detail-description">.*?</p>', '', sections, flags=re.S)
    tiles, total = [], 0
    for m in re.finditer(r'<section class="mcat-sec"><h2 id="([^"]+)">(.*?)</h2>(.*?)</section>', sections, re.S):
        cid, inner = m[1], m[3]
        count = inner.count('class="mcard')
        if not count:
            continue
        total += count
        img = re.search(r'<img[^>]+src="([^"]+)"', inner)
        label = CATEGORY_LABELS.get(cid, re.sub(r'<[^>]+>', '', m[2]))
        pic = (f'<img src="{img[1]}" alt="" loading="lazy">' if img else
               '<i class="mtile-curb" aria-hidden="true"></i>' if cid == 'cat-curb' else '')
        tiles.append(f'<a class="mtile" href="#{cid}">{pic}<strong>{escape(label)}</strong><span>{count}</span></a>')
    top = f"""
<div class="sfilter mfilter"><input id="mq" type="search" placeholder="Filter: Detail 22, Type IV arrow, two-way left-turn, bike lane line, red curb" aria-label="Filter markings"><span id="mcount" class="scount">{total} markings</span><details class="mview"><summary>View</summary></details></div>

<nav class="mtiles" aria-label="Marking categories">{''.join(tiles)}</nav>

<nav class="landing-actions" aria-label="Related tools"><a href="{BASE}/markings/cad/">DWG blocks</a><a href="{BASE}/markings/cad/?edit=pavetext">Pavement text block</a><a href="{BASE}/markings/line-types/">Line type database</a><a href="{BASE}/ladot/curb-paint/">LADOT curb paint</a></nav>

"""
    # figure links that only reach the chapter go to the figure itself (check_links.py proves the anchor)
    sections = re.sub(r'href="(' + BASE + r'/ca-mutcd/\w+/)">((?:CA MUTCD )?Figure (\d[A-Z]-\d+)(\(CA\))?)</a>',
                      lambda m: f'href="{m[1]}#fig-{m[3].lower()}{"ca" if m[4] else ""}">{m[2]}</a>', sections)
    # section headings carry the same short names as the tiles
    sections = re.sub(r'(<section class="mcat-sec"><h2 id="([^"]+)">)(.*?)(</h2>)',
                      lambda m: m[1] + escape(CATEGORY_LABELS.get(m[2], m[3])) + m[4] if m[2] in CATEGORY_LABELS else m[0], sections)
    script = body[body.find('<script>', first):] if '<script>' in body[first:] else ''
    if script:
        sections = sections[:sections.find('<script>')]
    page.write_text(head + sep + top + sections.rstrip() + '\n\n' + script)


SIGN_GROUPS = [('regulatory', 'Regulatory'), ('warning', 'Warning'), ('school', 'School'),
               ('ttc', 'Temporary traffic control'), ('guide', 'Guide'), ('local', 'Local callouts')]


def signs_landing(root):
    """Jump links to each sign group and the DWG library, under the chart's search."""
    page = root / 'signs/index.md'
    text = page.read_text()
    if 'class="landing-actions sign-jumps"' in text:
        return
    end = text.find('<h2 id="regulatory"')
    if end < 0:
        return
    groups = [(k, n) for k, n in SIGN_GROUPS if f'<h2 id="{k}"' in text]
    nav = ('<nav class="landing-actions sign-jumps" aria-label="Sign groups">'
           + ''.join(f'<a href="#{k}">{escape(n)}</a>' for k, n in groups)
           + f'<a class="to-cad" href="{BASE}/signs/cad/">Sign blocks (DWG)</a></nav>')
    page.write_text(text[:end] + '\n' + nav + '\n' + text[end:])


SECURE = re.compile(r'href="http://((?:mutcd\.fhwa\.dot\.gov|onlinepubs\.trb\.org|www\.metro\.net|www\.arb\.ca\.gov'
                    r'|www\.aqmd\.gov|www\.dot\.ca\.gov|www\.chp\.ca\.gov)[^"]*)"')


MD_SECURE = re.compile(r'\]\(http://(mutcd\.fhwa\.dot\.gov|onlinepubs\.trb\.org|www\.metro\.net|www\.arb\.ca\.gov'
                       r'|www\.aqmd\.gov|www\.dot\.ca\.gov|www\.chp\.ca\.gov)')


def secure_links(root):
    """Hosts that serve HTTPS are linked over HTTPS (the printed address shown on the page is left as printed)."""
    for page in root.rglob('*.md'):
        text = page.read_text()
        if 'http://' in text:
            new = SECURE.sub(r'href="https://\1"', text)
            new = MD_SECURE.sub(r'](https://\1', new)
            if new != text:
                page.write_text(new)


def build(root):
    root = Path(root)
    secure_links(root)
    from inline_lists import build as inline_lists
    inline_lists(root)
    add_cad_tabs(root)
    markings_landing(root)
    signs_landing(root)
