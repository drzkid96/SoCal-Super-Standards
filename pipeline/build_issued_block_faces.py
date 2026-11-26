"""Prepare monochrome sign faces from the issued art for exact designations present in CAD."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pymupdf
from PIL import Image
from scipy import ndimage


def normalized_code(value):
    return re.sub(r'\s+', '', value).casefold()


def render_pixels(path, resolution):
    if path.suffix.lower() == '.svg':
        with pymupdf.open(path) as doc:
            page = doc[0]
            factor = resolution / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False)
            return np.frombuffer(pix.samples, dtype='uint8').reshape(pix.height, pix.width, 3)
    with Image.open(path) as source:
        return np.asarray(source.convert('RGB'))


def monochrome(pixels):
    red, green, blue = pixels.astype(np.int16).transpose(2, 0, 1)
    light = .299 * red + .587 * green + .114 * blue
    high = pixels.max(axis=2).astype(np.int16)
    low = pixels.min(axis=2).astype(np.int16)
    colored = high - low > 42
    # Red, blue, dark green and purple become black. Yellow/orange/lime retain dark legends on a white field.
    warm = colored & (red > blue + 42) & (green > blue + 35) & (red > 139) & (green > 102) & (light > 121)
    prohibition = colored & (red > green * 1.45) & (red > blue * 1.4) & ~warm
    dark_ink = ~colored & (light < 146)
    fill = colored & ~warm & (light < 225)
    length = max(pixels.shape[:2])
    # Keep the boundary between a red slash and the original black pictogram visible in a monochrome rendering.
    if prohibition.any() and dark_ink.any():
        separation = ndimage.binary_dilation(prohibition, iterations=max(1, round(length * .0034)))
        dark_ink &= ~separation
    ink = dark_ink | fill
    # A yellow substrate has a real panel boundary outside the black inset border.
    # Keep it only for a colored field enclosing most of the sign area.
    if np.count_nonzero(warm) > .17 * ink.size:
        field = ndimage.binary_fill_holes(warm | ink)
        lab, count = ndimage.label(field)
        if count:
            areas = np.bincount(lab.ravel())
            areas[0] = 0
            poly = lab == np.argmax(areas)
            if poly.sum() > .34 * ink.size:
                ink |= poly & ~ndimage.binary_erosion(poly, iterations=max(1, round(length * .0014)))
    return ink


def isolate_issued_panel(pixels, ink, code):
    """Discard alternate legends printed outside the physical panel on FHWA plates."""
    rgb = pixels.astype('int16')
    high = rgb.max(axis=2)
    chroma = high - rgb.min(axis=2)
    content = (chroma > 39) | (high < 154)
    # A solid substrate or closed border encloses the panel. Detached margin lettering
    # has no geometric connection to that boundary.
    closed = ndimage.binary_closing(np.pad(content, 3), iterations=2)[3:-3,3:-3]
    labels, count = ndimage.label(ndimage.binary_fill_holes(closed))
    if not count:
        return ink, None
    areas = np.bincount(labels.ravel())
    areas[0] = 0
    panel = labels == np.argmax(areas)
    yy,xx = np.where(panel)
    if (panel.sum() < .26 * ink.size or np.ptp(xx) < .55 * ink.shape[1] or
        np.ptp(yy) < .55 * ink.shape[0]):
        return ink, None
    if code.upper() == 'OM1-3':
        # The issued marker is a solid yellow retroreflective face with no graphic.
        return panel, panel
    boundary = ndimage.binary_dilation(panel,iterations=2)
    return ink & boundary, panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('standards', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--resolution', type=int, default=1100)
    parser.add_argument('--threads', type=int, default=3)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    ref = json.loads(args.standards.read_text())['records']
    candidates = []
    for path in sorted(args.inputs.glob('*.json')):
        if path.name.startswith('official-'): continue
        parsed = json.loads(path.read_text())
        candidates.extend(parsed if isinstance(parsed,list) else parsed.get('records',[]))
    candidates.extend(json.loads((root/'data/reference/plan-examples/cad-sign-art.json').read_text()))
    for file in ('cad-signs.json','sign-library-records.json','3346-sign-records.json'):
        p = root/'data/reference/plan-examples'/file
        if p.exists():
            obj = json.loads(p.read_text())
            candidates.extend(obj if isinstance(obj,list) else obj.get('records',[]))
    observed = {normalized_code(r.get('code') or r.get('designation') or '') for r in candidates}
    seen = set()
    tasks = []
    for r in ref.values():
        code = r.get('standardCode') or r.get('code')
        if not code or normalized_code(code) not in observed: continue
        f = r.get('referenceFace') or {}
        if not f.get('asset') or not f.get('source') or f.get('type') not in ('published-face-vector','source-figure-crop','caltrans-specification-face'): continue
        if normalized_code(r.get('code','')) != normalized_code(code): continue
        path = root/'public'/f['asset'].lstrip('/')
        if not path.is_file() or normalized_code(code) in seen: continue
        seen.add(normalized_code(code));tasks.append((code,f,path))
    args.output.mkdir(parents=True,exist_ok=True)
    def convert(task):
        code,f,path = task
        key = re.sub(r'[^a-z0-9-]+','-',code.casefold()).strip('-')
        from ca_issued_sign_faces import SPECS, prepare_issued
        slug=re.sub(r'[^a-z0-9-]','',code.lower())
        if slug in SPECS and SPECS[slug][0]==code:
            spec=args.standards.parent/'ca-specs'/(slug+'.pdf')
            return prepare_issued(slug,spec,path,args.output/(key+'.png'),key,args.resolution)
        plate = root/'data/reference/cad-standards/plate-outlines'/(key+'.svg')
        retained_plate = plate.is_file()
        pixels = render_pixels(plate if retained_plate else path, 1400 if retained_plate else args.resolution)
        ink = pixels[:, :, 0] < 128 if retained_plate else monochrome(pixels)
        panel = None
        if not retained_plate and path.suffix.lower() == '.svg':
            ink, panel = isolate_issued_panel(pixels, ink, code)
        rows, cols = np.where(ink)
        if not len(rows): return None
        # Isolated sign face crops sometimes include a white page margin. Protect the true colored face, even if its bevel turns white.
        rgb = pixels.astype('int16')
        visible = (rgb.max(axis=2)-rgb.min(axis=2)>40) | (rgb.max(axis=2)<208)
        yy,xx=np.where(panel if panel is not None else visible)
        if len(yy) and not retained_plate:
            x0,x1,y0,y1 = min(cols.min(),xx.min()),max(cols.max(),xx.max()),min(rows.min(),yy.min()),max(rows.max(),yy.max())
            ink=ink[y0:y1+1,x0:x1+1]
        out=args.output/(key+'.png'); Image.fromarray(np.where(ink,0,255).astype('uint8')).save(out)
        result = {'id':'official-'+key,'drawing':'official-standard','code':code,'outlineMask':str(out.resolve()),
                'sourceKind':'current issued sign artwork','sourceUrl':f['source'],'referenceTitle':f.get('reference','Published sign face'),
                'referenceAsset':f['asset'],'referenceType':f['type'],'referenceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'resolution':[ink.shape[1],ink.shape[0]],'notes':'Monochrome reconstruction of the publisher’s illustrated sign face. Variable legends follow the published example.'}
        if retained_plate:
            result['outlineSource'] = str(plate.relative_to(root))
            result['outlineSourceSha256'] = hashlib.sha256(plate.read_bytes()).hexdigest()
        if retained_plate and code == 'R1-2':
            result['notes'] = ('FHWA SHS 2024, sheet R1-2, PDF page 23. The 36-inch side dimension A spans '
                               'the virtual corners. The retained nominal frame preserves the smaller rounded outline '
                               'and the published three-quarter-inch red inset.')
        return result
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        rows = sorted((r for r in pool.map(convert,tasks) if r), key=lambda r:r['code'].casefold())
    (args.inputs/'official-faces.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1)+'\n')
    print(f'{len(rows)} exact issued sign references for {len(observed)} observed designations', flush=True)

if __name__=='__main__':
    main()
