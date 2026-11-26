"""Render the reopened native block so sign variants can be distinguished on the download page."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json

import ezdxf
from ezdxf.addons.drawing import RenderContext
from PIL import Image
from render_cad_sign_art import render


def render_one(task):
    dxf, target, name = task
    drawing = ezdxf.readfile(dxf)
    block = drawing.blocks[name]
    record = {'entities':[e.dxf.handle for e in block]}
    picture = render(drawing, RenderContext(drawing), record)
    picture.thumbnail((344,344), Image.Resampling.LANCZOS)
    picture.convert('L').save(target,'WEBP',lossless=True,method=4)


def render_batch(folder, stage, target):
    target.mkdir(parents=True,exist_ok=True)
    rows=json.loads((folder/'manifest.json').read_text())['records']
    jobs=[(stage/(r['id']+'.roundtrip.dxf'),target/(r['id']+'.webp'),r['blockName']) for r in rows]
    jobs=[job for job in jobs if not job[1].is_file() or job[0].stat().st_mtime>job[1].stat().st_mtime]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for _ in pool.map(render_one,jobs,chunksize=6):
            pass

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work',type=Path)
    parser.add_argument('batches',nargs='+')
    args=parser.parse_args()
    for batch in args.batches:
        render_batch(args.work/batch,args.work/'block-stage'/batch,args.work/'block-previews')
