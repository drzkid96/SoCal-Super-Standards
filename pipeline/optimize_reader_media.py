"""Build lightweight browse thumbnails and LADOT preview sheets backed by local source PDFs."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
import pymupdf


def candidates(source, dist):
    for thumb in (source/'thumbs').rglob('*.webp'):
        relative=thumb.relative_to(source/'thumbs')
        if (source/relative).is_file():
            yield thumb,dist/'thumbs'/relative,(320,320),72
    for name in ('mpp-521','mpp-531','red-book'):
        original=dist/'ladot-publications'/(name+'.pdf')
        if not original.is_file():continue
        with pymupdf.open(original) as pdf:pages=len(pdf)
        for sheet in (source/'figs/ladot'/name).glob('p*.webp'):
            page=sheet.stem[1:]
            if page.isdigit() and 1<=int(page)<=pages:
                yield sheet,dist/sheet.relative_to(source),(1100,1450),75


def optimize(job):
    source,destination,box,quality=job
    if not destination.is_file() or source.resolve()==destination.resolve():return 0
    raw=source.read_bytes()
    cache=Path('.standards/reader-media-cache')/f'{box[0]}-{box[1]}-{quality}-{sha256(raw).hexdigest()}.webp'
    if cache.exists():result=cache.read_bytes()
    else:
        with Image.open(BytesIO(raw)) as image:
            if image.width<=box[0] and image.height<=box[1]:return 0
            image.thumbnail(box,Image.Resampling.LANCZOS)
            out=BytesIO();image.save(out,format='WEBP',quality=quality,method=4)
            result=out.getvalue()
        if len(result)>=len(raw):return 0
        cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(result)
    if len(result)>=len(raw):return 0
    temp=destination.with_suffix('.webp.tmp');temp.write_bytes(result);temp.replace(destination)
    return len(raw)-len(result)


if __name__=='__main__':
    dist=Path(sys.argv[1] if len(sys.argv)>1 else 'dist')
    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes=list(pool.map(optimize,candidates(Path('public'),dist)))
    print(f'Optimized {sum(n>0 for n in sizes):,} browse and sheet previews, saving {sum(sizes):,} bytes. Full-size artwork and source PDFs are available at their original URLs.')
