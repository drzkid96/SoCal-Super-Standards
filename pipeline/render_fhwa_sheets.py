"""Render verified FHWA release pages. Usage: python pipeline/render_fhwa_sheets.py PDF_CACHE."""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
import json
import sys

import pymupdf
from PIL import Image

from sign_releases import CATALOG, FHWA
import shs_layouts

DIGESTS = {
    '2024_SHS_Release_5-Guide_Signs.pdf':'b00b809367526016294b487c67a169100a666553f423de36af315c37a65cf825',
    '2024_SHS_Release_6-Guide_Signs.pdf':'3eea7efcfc958c9da3bd42646e22da820b06c10fe94e6d089ee81bf381851b59',
    '2024_SHS_Release_6-Regulatory_Signs.pdf':'92c555817383ab63e8e8c9e72651e7d192c3a1f2c06f49be51302ef7cd0864c7',
    shs_layouts.FILE:shs_layouts.DIGEST,
}
cache=Path(sys.argv[1])
cache.mkdir(exist_ok=True,parents=True)
out=Path('public/figs/fhwa-shs')
out.mkdir(exist_ok=True,parents=True)
catalog=json.loads(CATALOG.read_text())
for name, digest in DIGESTS.items():
    path=cache/name
    if not path.exists():
        with urlopen(FHWA+"pdf/"+name,timeout=300) as response:
            data=response.read(160*1024*1024+1)
        if sha256(data).hexdigest()!=digest:raise ValueError('FHWA changed the release PDF. Review its bookmarks: '+name)
        path.write_bytes(data)
    if sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Unexpected PDF edition: '+name)
    with pymupdf.open(path) as doc:
        if name==shs_layouts.FILE:
            print(f'{shs_layouts.render(path)} sign layout drawings prepared.')
            continue
        for n in sorted({n for row in catalog if row['file']==name for n in row['pages']}):
            pix=doc[n-1].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
            Image.frombytes('RGB',(pix.width,pix.height),pix.samples).save(out/(path.stem+'-'+str(n)+'.webp'),'WEBP',quality=90,method=3)
print(f'{len(list(out.glob("*.webp")))} FHWA dimensioned sheets prepared.')
