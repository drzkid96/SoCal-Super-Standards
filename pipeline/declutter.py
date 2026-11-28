"""Remove inventory, review and build notes from every page; keep titles, editions, dates and citations.

What counts as a development note (never shown to readers): page or record counts, how a page was made
(OCR, extracted, traced, digest), when or how it was checked or verified, internal status labels,
panels and tools named as if the reader knows them, empty metadata blocks, topic tags, and page
numbers of a source manual next to a section that already links to it. The source, its edition and
its date stay.

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
    inner = re.sub(SEP + r'<span class="badge muted">no CA counterpart found</span>', '', inner)
    inner = re.sub(r'^Section [^&·<]+(?:' + SEP + r'|$)', '', inner.strip())
    return (m[1] + inner + m[3] + '\n') if inner.strip() else ''


def clean(text):
    text = re.sub(r'(<div class="srcbar">)(.*?)(</div>)', srcbar, text, flags=re.S)
    text = re.sub(r'(<div class="secmeta">)(.*?)(</div>)\n?', secmeta, text, flags=re.S)
    text = re.sub(r'<p class="alsopub">.*?</p>\n?', '', text, flags=re.S)
    text = re.sub(SEP + r'manual pages? \d+(?:\s*(?:&ndash;|–|-)\s*\d+)?', '', text)
    text = re.sub(r'(<span id="kcount">)[^<]*(</span>)', r'\1\2', text)
    text = re.sub(r"'\d+ index entries[^']*'", "''", text)
    text = re.sub(r'\nEvery page of every [^\n]*\n', '\n', text)
    # topic tags under each page heading, internal status labels, empty metadata blocks
    text = re.sub(r'<div class="pmeta">[^<]*</div>\n?', '', text)
    text = re.sub(r'<span class="status-pill[^"]*">[^<]*</span>\s*', '', text)
    text = re.sub(r'<div class="bul-meta">\s*</div>\n?', '', text)
    # counts: catalog group counts, the homepage coverage strip
    text = re.sub(r'\s*<span class="count">\d[\d,]*</span>', '', text)
    text = re.sub(r'<div class="home-stats"[^>]*>.*?</div>\n?', '', text, flags=re.S)
    # how a page was made or checked
    text = re.sub(r'\s*Full document, page by page, with drawings, OCR text and linked signs\.', '', text)
    text = re.sub(r'Plain-language digest with section references, checked against the official copy on [^.]*\.\s*', '', text)
    text = re.sub(r'Cross-agency comparison checked against primary official sources on [^:]*:\s*', 'Sources: ', text)
    text = re.sub(r'\s*Values checked [A-Z][a-z]+ \d{1,2}, \d{4}\.', '', text)
    text = re.sub(r'(?m)^Checked [A-Z][a-z]+ \d{1,2}, \d{4}\.\s*', '', text)
    text = re.sub(r'\s*\((?:last )?(?:checked|verified) [A-Z][a-z]+ \d{1,2}, \d{4}\)', '', text)
    text = re.sub(r' This page lists the ones in effect as of ([A-Z][a-z]+ \d{1,2}, \d{4})\. Each digest gives the scope, '
                  r'the key values and the section numbers, with a link to the official copy\.', '', text)
    text = re.sub(r'\s*\(older sheets citing [^)]*flagged in (?:the )?Checks panel\)', '', text)
    # sign size notes: the source table, without its manual page and an empty row label
    text = re.sub(r'(From CA MUTCD 2026 Table [^ (<]+) \(page \d+\), row: ?\.', r'\1.', text)
    text = re.sub(r'(From CA MUTCD 2026 Table [^ (<]+) \(page \d+\), row: ([^.<]+)\.', r'\1, row \2.', text)
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
