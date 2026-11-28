"""FHWA Standard Highway Signs 2024 (Releases 1-4) layout drawings for sign pages.

render(pdf): crops each sign's dimensioned drawing (the page above its size table) to public/figs/shs/.
section(slug, code, table, href): the sign page's layout section: drawing(s), size table, PDF link.
"""
from html import escape
from pathlib import Path
import json
import re

BASE = '/SoCal-Super-Standards'
OUT = Path('public/figs/shs')
FILE = '2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf'
DIGEST = 'b1a9091e78eeb8a3605cc1041ba403c34048d1a2182265f3027eb864c922b3ff'


def slug(code):
    return re.sub(r'[^a-z0-9\-]', '', code.lower().replace('(', '').replace(')', ''))


def sheets():
    """slug -> PDF page numbers, one per sheet, in order."""
    out = {}
    for rec in json.loads(Path('data/signs/shs.json').read_text()):
        if rec.get('source', '').endswith('Releases 1-4') and rec.get('pdf_page'):
            pages = out.setdefault(slug(rec['code'].split(',')[0].strip()), [])
            if rec['pdf_page'] not in pages:
                pages.append(rec['pdf_page'])
    return out


def table_top(page):
    """Top of the size table: the row of column letters A, B, C ..., else the table grid."""
    lines = {}
    for w in page.get_text('words'):
        lines.setdefault(round(w[3]), []).append(w)
    tops = []
    for ws in lines.values():
        t = [w[4] for w in sorted(ws, key=lambda w: w[0])]
        if len(t) >= 3 and t[0] == 'A' and t[1] == 'B' and all(re.fullmatch(r'[A-Z]{1,2}', x) for x in t):
            tops.append(min(w[1] for w in ws) - 8)
    if not tops:
        tops = [t.bbox[1] for t in page.find_tables().tables]
    return min(tops, default=page.rect.y1 - 60)


def clip(page):
    import pymupdf
    r, ty = page.rect, table_top(page)
    box = None
    for d in page.get_drawings():
        q = d['rect']
        if q.y0 > 40 and q.y1 <= ty - 2 and q.width < r.width * 0.98:
            box = q if box is None else box | q
    if box is None:
        return None
    for b in page.get_text('blocks'):
        q = pymupdf.Rect(b[:4])
        if q.y0 > 40 and q.y1 <= ty - 2 and q.intersects(box + (-30, -20, 30, 6)):
            box |= q
    return (box + (-8, -8, 8, 8)) & r


def name(s, i):
    return f'{s}.webp' if i == 1 else f'{s}-{i}.webp'


def render(pdf):
    import pymupdf
    from PIL import Image
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with pymupdf.open(pdf) as doc:
        for s, pages in sheets().items():
            for i, p in enumerate(pages, 1):
                target = OUT / name(s, i)
                if target.exists():
                    n += 1
                    continue
                page = doc[p - 1]
                box = clip(page)
                if box is None:
                    continue
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), clip=box, alpha=False)
                Image.frombytes('RGB', (pix.width, pix.height), pix.samples).save(target, 'WEBP', quality=80, method=4)
                n += 1
    return n


def section(s, code, table, href):
    """Layout section for a sign page, or None when no drawing was rendered."""
    figs = []
    i = 1
    while (OUT / name(s, i)).is_file():
        src = f'{BASE}/figs/shs/{name(s, i)}'
        figs.append(f'<a href="{src}"><img src="{src}" loading="lazy" alt="{escape(code)} dimensioned layout"></a>')
        i += 1
    if not figs:
        return None
    return ('## Sign layout\n\n<figure class="shs-fig">' + ''.join(figs) + '</figure>\n\n'
            + (table + '\n\n' if table else '')
            + f'<a href="{href}">FHWA Standard Highway Signs 2024 (PDF)</a>\n\n')
