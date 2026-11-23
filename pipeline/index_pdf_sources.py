"""Refresh the checked-in source index from Caltrans chapter PDFs and the two official contents PDFs.

python pipeline/index_pdf_sources.py CHAPTER_DIRECTORY CA_TOC.pdf FED_TOC.pdf
Uses PyMuPDF only during source refresh. Normal site builds require no PDFs.
"""
import argparse
import itertools
import json
import re
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/reference'
ITEM = re.compile(r'^(Figure|Table)\s+(\d[A-Z]-\d+(?:[a-z]|\s*\(CA\))?)(?=[.\s]|$)\.?\s*(.*)$')
SECTION = re.compile(r'^Section\s+(\d[A-Z]\.\d+(?:\s*\(CA\))?)')
PN = re.compile(r'\d{2}[a-z]?')


def contents(path):
    items = {}
    active = None
    with fitz.open(path) as doc:
        for page in doc:
            for line in page.get_text().splitlines():
                line = line.strip()
                match = ITEM.match(line)
                if match:
                    kind, num, line = match.groups()
                    active = f'{kind} {num.replace(" ", "")}'
                end = re.search(r'\.{2,}\s*(\d+)\s*$', line)
                if active and end:
                    items[active] = int(end[1])
                    active = None
    return items


def horizontal_strokes(page):
    strokes = []
    for path in page.get_drawings():
        for item in path['items']:
            if item[0] == 're':
                x0, y0, x1, y1 = item[1]
                if y1 - y0 > 1.5:
                    continue
            elif item[0] == 'l':
                (x0, y0), (x1, y1) = item[1:3]
                if abs(y1 - y0) > .6:
                    continue
            else:
                continue
            if abs(x1 - x0) >= 1.5:
                strokes.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2))
    return strokes


def span_runs(span, strokes):
    baseline = span['origin'][1]
    size = span['size']
    # Word strikeouts run through the x-height. Exclude underlines and the line above.
    cuts = [(x0, x1) for x0, x1, y in strokes if .17 * size < baseline - y < .49 * size]
    def struck(ch):
        center = (ch['bbox'][0] + ch['bbox'][2]) / 2
        return any(x0 - .1 <= center <= x1 + .1 for x0, x1 in cuts)
    for deleted, group in itertools.groupby(span['chars'], struck):
        yield deleted, ''.join(ch['c'] for ch in group)


def provisions(path):
    records = {}
    section = number = None
    with fitz.open(path) as pdf:
        for physical, page in enumerate(pdf, 1):
            plain = page.get_text()
            if not re.search(r'Section\s+\d[A-Z]\.\d|^\s*\d{2}[a-z]?\s*$', plain, re.M):
                continue
            if re.search(r'Chapter [^\n]+\((Figures|Tables)\)', plain):
                continue
            strokes = horizontal_strokes(page)
            for block in page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
                for line in block.get('lines', []):
                    if not 38 < line['bbox'][1] < 730:
                        continue
                    spans = [(s, ''.join(c['c'] for c in s['chars'])) for s in line['spans']]
                    spans = [(s,t) for s,t in spans if t.strip()]
                    if not spans:
                        continue
                    first, text = spans[0]
                    raw = ''.join(t for _,t in spans).strip()
                    heading = SECTION.match(raw) if 'Bold' in first['font'] and first['size'] >= 11.5 else None
                    if heading:
                        section = heading[1].replace(' ', '')
                        number = None
                        continue
                    if raw in ('Standard:', 'Guidance:', 'Option:', 'Support:'):
                        number = None
                        continue
                    if first['size'] < 9 and PN.fullmatch(text.strip()) and first['origin'][0] < 95 and section:
                        number = (section, text.strip())
                        records.setdefault(number, [physical, []])
                        spans = spans[1:]
                    if number and spans:
                        runs = records[number][1]
                        runs.append((False, ' '))
                        for s, _ in spans:
                            runs.extend(span_runs(s, strokes))
    output = {}
    for (section, num), (page, runs) in records.items():
        # A compact integer is enough for paragraphs with no struck characters.
        changes = any(deleted and t.strip() for deleted,t in runs)
        entry = page
        if changes:
            grouped = []
            for deleted, group in itertools.groupby(runs, key=lambda pair: pair[0]):
                segment = ''.join(t for _,t in group)
                grouped.append([int(deleted), segment])
            entry = [page, grouped]
        output.setdefault(section, {})[num] = entry
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chapters', type=Path)
    parser.add_argument('ca_toc', type=Path)
    parser.add_argument('fed_toc', type=Path)
    args = parser.parse_args()
    for name, path in [('ca-mutcd', args.ca_toc), ('mutcd', args.fed_toc)]:
        items = contents(path)
        if len(items) < 350:
            raise ValueError(f'Incomplete {name} table of contents: {len(items)} entries')
        (OUT / (name+'-items.json')).write_text(json.dumps(items, indent=1)+'\n')
    folder = OUT / 'provisions'
    folder.mkdir(exist_ok=True)
    for path in sorted(args.chapters.glob('*.pdf')):
        dest = folder / (path.stem.lower()+'.json')
        data = provisions(path)
        dest.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n')


if __name__ == '__main__':
    main()
