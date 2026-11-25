"""Render the exact agency PDFs catalogued in the regional reader."""
import gzip
import hashlib
import json
import os
import shutil
import time
from multiprocessing import get_context
from pathlib import Path
from urllib.request import Request, urlopen

CATALOG = Path('data/reference/regional/catalog.json.gz')
ASSETS = Path('public/regional-sheets')

def render(reg):
    import pymupdf
    from PIL import Image
    key = reg['key']
    target = ASSETS/key
    marker = target/'.digest'
    if marker.exists() and marker.read_text()==reg['sha256'] and len(list(target.glob('*.avif')))==reg['pages']:
        return
    cache = Path('.regional-cache')/(key+'.pdf')
    cache.parent.mkdir(exist_ok=True)
    for attempt in range(3):
        try:
            data = cache.read_bytes() if cache.exists() else urlopen(Request(reg['source'], headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read()
            if hashlib.sha256(data).hexdigest()!=reg['sha256']:
                raise ValueError('Edition differs from indexed source')
            cache.write_bytes(data)
            break
        except (OSError, ValueError) as err:
            cache.unlink(missing_ok=True)
            if attempt==2:raise RuntimeError(f"{reg['agency']} · {key}: {err}") from err
            time.sleep(2**attempt)
    target.mkdir(exist_ok=True,parents=True)
    with pymupdf.open(cache) as doc:
        assert len(doc)==reg['pages']
        for i,page in enumerate(doc,1):
            scale=1440/max(page.rect.width,page.rect.height)
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            Image.frombytes('RGB',(pix.width,pix.height),pix.samples).save(target/f'{i}.avif','AVIF',quality=43,speed=8,max_threads=1)
    marker.write_text(reg['sha256'])

def prepare():
    with gzip.open(CATALOG,'rt',encoding='utf-8') as f: records=json.load(f)
    # PyMuPDF documents must be handled by separate processes.
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(mp_context=get_context('fork'), max_workers=min(5,os.cpu_count() or 1)) as pool:
        list(pool.map(render,records))
    return records
