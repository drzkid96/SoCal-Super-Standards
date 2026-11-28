"""Lettered and numbered runs printed inside one paragraph ("limited to: A.Bicycle lanes ..., B.Extensions ...")
become real lists, as the source documents set them.

A run starts right after a colon with A. (or 1.), continues B., C. ... (2., 3. ...) in order and needs two
items or more. Markers inside tags, abbreviations (U.S., No.) and section numbers (9E.01) never qualify.
"""
import re
from pathlib import Path

PARA = re.compile(r'(<p\b[^>]*>)(.*?)(</p>)', re.S)
LETTER = re.compile(r'(?:(?<=[\s:;,>(])|^)([A-Z])\.\s?(?=[A-Z0-9“"(\'])')
NUMBER = re.compile(r'(?:(?<=[\s:;,>(])|^)(\d{1,2})\.\s?(?=[A-Z“"(\'])')
JOINER = re.compile(r'(?:\s*,?\s*(?:and|or)\s*|\s*[,;]\s*)$')


def outside_tags(html, pos):
    return html.rfind('<', 0, pos) <= html.rfind('>', 0, pos)


def split_run(body, rx, first, nxt):
    marks = [m for m in rx.finditer(body) if outside_tags(body, m.start())]
    for i, m in enumerate(marks):
        if m[1] != first or not body[:m.start()].rstrip().endswith(':'):
            continue
        run, want = [m], nxt(first)
        for n in marks[i + 1:]:
            if n[1] == want:
                run.append(n)
                want = nxt(want)
        if len(run) < 2:
            continue
        intro = body[:run[0].start()].rstrip()
        items = []
        for k, mark in enumerate(run):
            end = run[k + 1].start() if k + 1 < len(run) else len(body)
            items.append(JOINER.sub('', body[mark.end():end].strip()) if k + 1 < len(run) else body[mark.end():end].strip())
        return intro, items
    return None


def nested(item):
    """A numbered run inside a lettered item becomes a list inside that item."""
    found = split_run(item, NUMBER, '1', lambda c: str(int(c) + 1))
    if not found:
        return item
    intro, items = found
    return intro + '<ol class="ilist" type="1">' + ''.join(f'<li>{x}</li>' for x in items) + '</ol>'


def listify(html):
    def one(m):
        open_tag, body, close = m.groups()
        for rx, first, nxt, kind in ((LETTER, 'A', lambda c: chr(ord(c) + 1), 'A'),
                                     (NUMBER, '1', lambda c: str(int(c) + 1), '1')):
            found = split_run(body, rx, first, nxt)
            if found:
                intro, items = found
                lis = ''.join(f'<li>{nested(x) if kind == "A" else x}</li>' for x in items)
                return f'{open_tag}{intro}{close}<ol class="ilist" type="{kind}">{lis}</ol>'
        return m[0]
    return PARA.sub(one, html)


# compound words broken across a PDF line keep a stray space ("right- turn"); "pre- and post-" stays
BROKEN = re.compile(r'\b([A-Za-z]{2,})- (?!(?:and|or|to|through|nor)\b)([a-z]{2,})\b')


def build(root):
    changed = 0
    for page in Path(root).rglob('*.md'):
        text = page.read_text()
        new = BROKEN.sub(r'\1-\2', text)
        if ':' in new and '<p' in new:
            new = listify(new)
        if new != text:
            page.write_text(new)
            changed += 1
    return changed


if __name__ == '__main__':
    sample = ('<p id="x"><a class="pn" href="#">02</a> If used, green-colored pavement shall be limited to: '
              'A.Bicycle lanes (see Sections 9E.01, 9E.06), B.Extensions of bicycle lanes (see <a href="#">Section 9E.03</a>), '
              'and F.As a background.</p>')
    print(listify(sample))
