"""Remove inventory and build notes from every generated page; keep titles, editions, dates and citations.

Runs at the end of prepare_reference over the generated docs. check_declutter.py guards the built site.
"""
import re
from pathlib import Path

COUNT = r'\d[\d,]*\s+(?:pages?|documents?|sheets?|drawings?|records?|entries|figures?|files?)'
SEP = r'\s*(?:&middot;|·)\s*'


def srcbar(m):
    inner = m[2]
    inner = re.sub(SEP + COUNT + r'(?=\s*(?:&middot;|·|$))', '', inner)
    inner = re.sub(r'^' + COUNT + SEP, '', inner)
    inner = re.sub(SEP + r'manual pages? \d+(?:\s*(?:&ndash;|–|-)\s*\d+)?', '', inner)
    return m[1] + inner + m[3]


def secmeta(m):
    inner = m[2]
    inner = re.sub(SEP + r'manual page \d+', '', inner)
    inner = re.sub(SEP + r'<a [^>]*>short link</a>', '', inner)
    inner = re.sub(r'^Section [^&·<]+(?:' + SEP + r'|$)', '', inner.strip())
    return (m[1] + inner + m[3] + '\n') if inner.strip() else ''


def clean(text):
    text = re.sub(r'(<div class="srcbar">)(.*?)(</div>)', srcbar, text, flags=re.S)
    text = re.sub(r'(<div class="secmeta">)(.*?)(</div>)\n?', secmeta, text, flags=re.S)
    text = re.sub(r'<p class="alsopub">.*?</p>\n?', '', text, flags=re.S)
    return text


def build(root):
    changed = 0
    for path in Path(root).rglob('*.md*'):
        text = path.read_text()
        new = clean(text)
        if new != text:
            path.write_text(new)
            changed += 1
    print(f'declutter: {changed} pages cleaned')
    return changed
