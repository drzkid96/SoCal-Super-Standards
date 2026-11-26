"""Re-extract the pinned CA 2026 and FHWA 11th Rev 1 sign dimension tables.

Usage: python extract_tables.py --california FILE --federal-dir DIR [--output FILE]
The federal directory must contain all individual chapter/part files in retrieval.json.
Source PDF byte hashes are verified before extracting. Requires PyMuPDF.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import re

import pymupdf as fitz

HERE = Path(__file__).resolve().parent
CAPTION = re.compile(r'\bTable\s+([1-9][A-Z]-\d+(?:\s?\(CA\))?)\s*\.\s*((?:(?!\bTable\b|\bSection\b).){0,160}?(?:Sizes?|Dimensions))', re.I)

def clean(text):
    return ' '.join((text or '').split()).translate(str.maketrans({'‑':'-', '–':'-', '−':'-'}))

def deletion(path):
    col = path.get('color')
    rect = path['rect']
    return (path['type']=='s' and col and len(col)==3 and col[2]>.6 and col[0]<.4
            and col[1]<.4 and rect.height<1 and rect.width>2)

def caltrans_table_paths(page):
    # A blue horizontal strike excludes the characters it crosses in the adopted text.
    blue = [p['rect'] for p in page.get_drawings() if deletion(p)]
    for rect in blue:
        mid = (rect.y0+rect.y1)/2
        page.add_redact_annot(fitz.Rect(rect.x0+.1,mid-.05,rect.x1-.1,mid+.05),fill=False)
    if blue:
        page.apply_redactions(images=0, graphics=0, text=0)
    return [p for p in page.get_drawings() if not deletion(p)]

def extract_rows(raw):
    raw = raw[next((i for i,row in enumerate(raw[:4]) if any('Designation' in (v or '') for v in row)),0):]
    if len(raw)<2:
        return
    header = [clean(cell) for cell in raw[0]]
    pos = next((i for i,col in enumerate(header) if 'Designation' in col),None)
    if pos is None or not any(re.search('Conventional|Minimum|Roadway|way',col) for col in header):
        return
    columns = [(i,col) for i,col in enumerate(header) if col]
    start = 1
    second = [clean(cell) for cell in raw[1]]
    if not second[pos] and any(re.search(r'(?:Single|Multi)\s*-?\s*Lane',c,re.I) for c in second):
        for i,col in enumerate(second):
            if re.search('Single',col,re.I):
                columns = [(j,'Conventional Road Single Lane' if j==i else hdr) for j,hdr in columns]
            if re.search('Multi',col,re.I):
                columns.append((i,'Conventional Road Multi-Lane'))
        columns.sort()
        start = 2
    rows = []
    for row in raw[start:]:
        vals = {}
        for n,(col,label) in enumerate(columns):
            end = columns[n+1][0] if n+1<len(columns) else len(row)
            vals[label] = ' '.join(clean(v) for v in row[col:end] if clean(v))
        if vals.get(header[pos]):
            rows.append(vals)
    return header,rows

def extract_file(task):
    file,cal,expected_hash = task
    with file.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest() != expected_hash:
            raise ValueError(f'File bytes do not match the pinned edition: {file}')
    pages = []
    with fitz.open(file) as doc:
        for n,page in enumerate(doc,1):
            # Part 1A shows an example of markup, not an operative size table.
            if cal and n==66:
                continue
            text = clean(page.get_text())
            if not ('Designation' in text and CAPTION.search(text)):
                continue
            captions=[]
            for block in page.get_text('blocks'):
                match=CAPTION.search(clean(block[4]))
                if match:
                    captions.append((block[1],match))
            fallback=CAPTION.search(text)
            paths=caltrans_table_paths(page) if cal else page.get_drawings()
            strategy = 'lines' if cal and n==1260 else 'lines_strict'
            for table in page.find_tables(strategy=strategy,paths=paths).tables:
                parsed=extract_rows(table.extract())
                if parsed is None:
                    continue
                eligible=[cap for cap in captions if cap[0] <= table.bbox[1]+8]
                caption=max(eligible,key=lambda cap:cap[0])[1] if eligible else fallback
                header,rows=parsed
                pages.append({'n':n,'table':caption[1].replace(' ',''),'title':caption[2],
                    'head':header,'rows':rows,'source':'ca-mutcd-sign-source.pdf' if cal else file.name})
    return pages

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--california',type=Path,required=True)
    parser.add_argument('--federal-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=HERE/'sources/official-size-table-rows.json.gz')
    args=parser.parse_args()
    receipt=json.loads((HERE/'sources/retrieval.json').read_text())
    tasks=[(args.california,True,receipt['california']['sha256'])]
    tasks.extend((args.federal_dir/name,False,sha) for name,sha in sorted(receipt['federal'].items()))
    with ProcessPoolExecutor(4) as pool:
        tables=[t for group in pool.map(extract_file,tasks) for t in group]
    output=json.dumps(tables,ensure_ascii=False,separators=(',',':')).encode()
    args.output.write_bytes(gzip.compress(output,mtime=0))
    print(f'{sum(len(t["rows"]) for t in tables)} rows across {len(tables)} sheet tables')

if __name__=='__main__':
    main()
