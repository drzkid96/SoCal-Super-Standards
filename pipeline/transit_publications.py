"""Fetch only pinned, publicly issued transit guides from their publisher."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request,urlopen
import hashlib,json,shutil,tempfile,time
import pymupdf

def prepare(editions):
    cache=Path('.transit-sources');cache.mkdir(exist_ok=True)
    dest=Path('public/transit-publications');dest.mkdir(exist_ok=True,parents=True)
    hashes=json.loads(Path('data/reference/transit-editions.json').read_text())
    def fetch(entry):
        key,name,county,title,url=entry
        if key not in hashes:return
        expected=hashes[key]
        raw=cache/(key+'.pdf');out=dest/(key+'.pdf')
        for attempt in range(2):
            try:
                if not raw.exists():
                    with urlopen(Request(url,headers={'User-Agent':'SoCalStandards reference publisher'}),timeout=30) as stream,raw.open('wb') as local:shutil.copyfileobj(stream,local)
                if hashlib.sha256(raw.read_bytes()).hexdigest()!=expected:raise ValueError('Publisher edition differs from indexed edition')
                stamp=cache/(key+'.stamp')
                if out.exists() and stamp.exists() and stamp.read_text()==expected:return
                with pymupdf.open(raw) as doc:
                    doc.rewrite_images(dpi_threshold=140,dpi_target=110,quality=68,bitonal=False)
                    new=out.with_suffix('.new');doc.save(new,garbage=4,deflate=True,use_objstms=1);new.replace(out)
                stamp.write_text(expected);return
            except Exception as error:
                raw.unlink(missing_ok=True)
                if attempt==1:
                    out.unlink(missing_ok=True)
                    print(f'Publisher PDF unavailable for {name}: {error}',flush=True)
                else:time.sleep(1)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,editions))
