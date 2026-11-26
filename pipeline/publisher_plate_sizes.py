"""Recover the physical backing and publisher graphic from verified FHWA sign layouts."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pymupdf
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
SIZES = ROOT/'data/reference/plan-examples/verified-publisher-panel-sizes.json'
SVG = '{http://www.w3.org/2000/svg}'

def svg_alpha(root, resolution):
    with pymupdf.open(stream=ET.tostring(root),filetype='svg') as doc:
        page=doc[0]
        factor=resolution/max(page.rect.width,page.rect.height)
        pix=page.get_pixmap(matrix=pymupdf.Matrix(factor,factor),alpha=True)
        return np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4)[:,:,3]

def plate_mask(path, entry, target, resolution=1800):
    from build_issued_block_faces import monochrome,render_pixels
    src=ET.parse(path).getroot()
    # These reviewed SVGs begin with the filled, die-cut substrate and its thin plotted edge.
    first=src.find(SVG+'path')
    if first is None or first.get('fill') not in ('#ffffff','#f7921d','#ffd046','#bf301a'):
        raise ValueError(f'Unexpected outer plate path in {path}')
    base=ET.Element(src.tag,dict(src.attrib));base.append(copy.deepcopy(first))
    panel=svg_alpha(base,resolution)>127
    roi=ndimage.find_objects(panel.astype(np.uint8))[0]
    panel=panel[roi]
    bounds=entry['nominalBounds']
    if abs(math.log((panel.shape[1]/panel.shape[0])/(bounds[0]/bounds[1])))>.015:
        raise ValueError(f'Publisher backing and selected size conflict in {path}: {panel.shape}, {bounds}')
    if entry['sizeBasis']=='diamond-side-lengths':
        # The issued 18-inch diamond carries a 1.5-inch corner radius. Preserve the blank
        # virtual frame so the side across opposing flats remains 18 inches after tracing.
        ink=panel
        outer=entry['size'][0]*math.sqrt(2)
        trimmed=outer-2*1.5*(math.sqrt(2)-1)
        virtual=round(max(ink.shape)*outer/trimmed)
        dx=virtual-ink.shape[1];dy=virtual-ink.shape[0]
        ink=np.pad(ink,((dy//2,dy-dy//2),(dx//2,dx-dx//2)))
    else:
        ink=monochrome(render_pixels(path,resolution))[roi]&panel
        # Substrates remain visible as a thin cut line. Never scale the inner border
        # to the blank dimensions (R7-1 has a 3/8-inch inset on each edge).
        radius=max(1,round(.035*panel.shape[1]/bounds[0]))
        ink|=panel&~ndimage.binary_erosion(panel,iterations=radius)
    Image.fromarray(np.where(ink,0,255).astype('uint8')).save(target)

def main():
    args=argparse.ArgumentParser(description=__doc__);args.add_argument('work',type=Path)
    work=args.parse_args().work.resolve()
    items=json.loads(SIZES.read_text())
    issued={r['id']:r for r in json.loads((work/'block-inputs/official-faces.json').read_text())}
    output=work/'standards/verified-panel-masks';output.mkdir(exist_ok=True)
    for id,r in items.items():
        if r.get('sourceMask'):
            cached=ROOT/r['sourceMask']
            if hashlib.sha256(cached.read_bytes()).hexdigest()!=r['sourceMaskSha256']:
                raise ValueError(f'Source mask changed: {id}')
            r['outlineMask']=str(cached)
        if id not in issued:continue
        path=ROOT/'public'/issued[id]['referenceAsset'].lstrip('/')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=issued[id]['referenceSha256']:
            raise ValueError(f'Issued drawing changed: {id}')
        mask=output/(id+'.png');plate_mask(path,r,mask)
        r['outlineMask']=str(mask)
    (work/'standards/verified-additional-sizes.json').write_text(json.dumps(items,indent=2,ensure_ascii=False)+'\n')
    print(f'Checked {len(items)} panel dimensions; framed {sum("outlineMask" in o for o in items.values())} issued masks.')
if __name__=='__main__':main()
