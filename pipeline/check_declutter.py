"""Fail when inventory or build notes reappear in the visible text of the built site."""
import re
import sys
from pathlib import Path

from lxml import html

BANNED = [r'\bmanual pages? \d', r'\bshort link\b', r'Also published as', r'sheet\(s\)', r'Every page of every',
          r'\bindex entries\b', r'Searchable page text', r'Source and size evidence', r'checked by two independent',
          r'\b\d[\d,]* documents\b']
pattern = re.compile('|'.join(BANNED))
hits = []
for page in Path('dist').rglob('*.html'):
    tree = html.parse(str(page)).getroot()
    if tree is None:
        continue
    for bad in tree.xpath('//script|//style|//*[@hidden]|//template'):
        bad.drop_tree()
    for el in tree.xpath('//main'):
        m = pattern.search(' '.join(el.text_content().split()))
        if m:
            hits.append(f'{page.relative_to("dist")}: {m[0]}')
for h in hits[:40]:
    print(h)
if hits:
    sys.exit(f'{len(hits)} page(s) show build or inventory notes')
print('No build or inventory notes in the visible site text.')
