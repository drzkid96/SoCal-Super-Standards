"""Resolve publisher book locations and render the missing original figure/table pages."""
import re
from pathlib import Path
from current_catalog import BASE, read

ART = read('data/reference/manual-illustrations.json')
SHEET_COUNTS = read('data/reference/manual-sheet-counts.json')
CA = read('data/reference/ca-chapter-urls.json')
FIRST = {e:{c['code']:c['first'] for c in read('data/'+e+'/chapters.json')} for e in ART}
FHWA = 'https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/'


def illustration_url(edition, kind, number):
    kind = kind.rstrip('s')
    number = number.replace(' ', '').upper()
    if f'{kind} {number}' not in ART[edition]:
        return None
    chapter = number.split('-')[0].lower()
    slug = number.lower().replace('(', '').replace(')', '')
    prefix = 'table' if kind == 'Table' else 'fig'
    return f'{BASE}/{edition}/{chapter}/#{prefix}-{slug}'


def source(edition, number, page):
    chapter=number.split('-')[0]
    if edition=='ca-mutcd':
        return CA[chapter],page-FIRST[edition][chapter]+1
    file='Chapter'+chapter.lower()+'r1.pdf' if chapter.startswith('2') else 'part'+chapter[0]+'r1.pdf'
    first=FIRST[edition][chapter if chapter.startswith('2') else chapter[0]+'A']
    return FHWA+file,page-first+1


if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor
    from collections import defaultdict
    from urllib.request import Request, urlopen
    from PIL import Image
    import pymupdf
    jobs=defaultdict(dict)
    for edition,items in ART.items():
        for key,(title,page) in items.items():
            for offset in range(SHEET_COUNTS[edition].get(key,1)):
                physical=page+offset
                path=Path(f'public/figs/{edition}/p{physical:04d}.webp')
                if path.exists():continue
                url,n=source(edition,key.split()[1],physical)
                jobs[url][n]=(physical,path)
    cache=Path('.manual-art')
    cache.mkdir(exist_ok=True)
    def render(job):
        url,records=job
        pdf=cache/url.rsplit('/',1)[1]
        if not pdf.exists():
            with urlopen(Request(url,headers={'User-Agent':'SoCal-Standards source verification'}),timeout=50) as r:
                data=r.read()
            if not data.startswith(b'%PDF'):raise ValueError(url)
            pdf.write_bytes(data)
        with pymupdf.open(pdf) as doc:
            for n,(page,path) in records.items():
                sheet=doc[n-1]
                # Verify the printed page before using any chapter-relative PDF offset.
                if not re.search(r'\bPage\s+'+str(page)+r'\b',sheet.get_text(),re.I):
                    raise ValueError(f'{url} PDF page {n} does not identify printed page {page}')
                pix=sheet.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
                Image.frombytes('RGB',(pix.width,pix.height),pix.samples).save(path,'WEBP',quality=89,method=4)
        return len(records)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(render,jobs.items()):print('Rendered',result,'source pages',flush=True)
