"""LADOT standard drawings as CAD: one DWG per drawing (MPP 531, MPP 521, Red Book), one sheet layout
per page at the publication's page size, built from the publisher's PDF.

Vector pages become lines, curves, filled areas and text (1 unit = 1 paper inch, on layers by role:
LADOT-LINE, LADOT-FILL, LADOT-TEXT). Scanned pages are placed as a 200 dpi black and white image at sheet size; those
drawings download as a ZIP holding the DWG and its images. Encoded as AutoCAD 2018 with ODA File
Converter and read back with LibreDWG. Files go to the download store (GitHub Release), never to Pages;
data/reference/ladot-detail-cad.json maps each drawing page to its download.

  python3 pipeline/ladot_dwg.py --libredwg <dir> --keep <folder>     # then pack the folder:
  tar cf - *.dwg *.zip | xz -6 > data/reference/ladot-cad/ladot-cad.tar.xz
The site build unpacks the archive into public/downloads/ladot-cad/; the download store moves every
file there to the release on deploy, and each LADOT drawing page links its file.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from current_catalog import BASE
from ladot_drawings import native_route, ownership, read, source_pdf

OUT = Path('data/reference/ladot-detail-cad.json')
DOCS = {'mpp-531': 'MPP531', 'mpp-521': 'MPP521', 'red-book': 'REDBOOK'}
GAP = 2.0    # in between sheets in model space


def asset_name(key, code):
    return f'LADOT-{DOCS[key]}-{re.sub(r"[^A-Za-z0-9]+", "-", code).strip("-").upper()}'


def flatten(item, k=8):
    """Points of one PyMuPDF path item, curves flattened."""
    import pymupdf
    kind = item[0]
    if kind == 'l':
        return [item[1], item[2]]
    if kind == 'c':
        p0, p1, p2, p3 = item[1:5]
        out = []
        for i in range(k + 1):
            t = i / k
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
            out.append(pymupdf.Point(a * p0.x + b * p1.x + c * p2.x + d * p3.x, a * p0.y + b * p1.y + c * p2.y + d * p3.y))
        return out
    if kind == 're':
        r = item[1]
        return [r.tl, r.tr, r.br, r.bl, r.tl]
    if kind == 'qu':
        q = item[1]
        return [q.ul, q.ur, q.lr, q.ll, q.ul]
    return []


def vector_page(page):
    return len(page.get_drawings()) >= 60


def add_page(doc, page, ox, images, work, stem, n):
    import pymupdf
    msp = doc.modelspace()
    h = page.rect.height / 72

    def P(pt):
        return (ox + pt.x / 72, h - pt.y / 72)
    if vector_page(page):
        for d in page.get_drawings():
            loops, cur = [], []
            for item in d['items']:
                pts = flatten(item)
                if not pts:
                    continue
                if cur and (abs(cur[-1].x - pts[0].x) > 0.05 or abs(cur[-1].y - pts[0].y) > 0.05):
                    loops.append(cur)
                    cur = []
                cur += pts if not cur else pts[1:]
            if cur:
                loops.append(cur)
            fill = d.get('fill')
            if fill is not None and d.get('type') in ('f', 'fs') and not all(c > 0.95 for c in fill):
                hatch = msp.add_hatch(dxfattribs={'layer': 'LADOT-FILL', 'color': 256})
                for loop in loops:
                    if len(loop) > 2:
                        hatch.paths.add_polyline_path([P(p) for p in loop], is_closed=True)
            if d.get('type') in ('s', 'fs') and d.get('color') is not None and not all(c > 0.95 for c in d['color']):
                width = (d.get('width') or 0.5) / 72
                for loop in loops:
                    if len(loop) > 1:
                        msp.add_lwpolyline([P(p) for p in loop], dxfattribs={
                            'layer': 'LADOT-LINE', 'const_width': width if width > 0.012 else 0})
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                dx, dy = line['dir']
                angle = -__import__('math').degrees(__import__('math').atan2(dy, dx))
                for span in line['spans']:
                    text = span['text'].strip()
                    if not text:
                        continue
                    x, y = span['origin']
                    msp.add_text(text, height=span['size'] * 0.7 / 72, rotation=angle,
                                 dxfattribs={'layer': 'LADOT-TEXT', 'style': 'ROMANS', 'insert': P(pymupdf.Point(x, y))})
        return False
    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY, alpha=False)
    name = f'{stem}-SHEET-{n}.png'
    from PIL import Image          # scans are black line work: 1-bit keeps them crisp and small
    Image.frombytes('L', (pix.width, pix.height), pix.samples).point(lambda v: 255 if v > 170 else 0).convert('1').save(
        work / name, optimize=True)
    images.append(name)
    w = page.rect.width / 72
    idef = doc.add_image_def(filename=name, size_in_pixel=(pix.width, pix.height))
    msp.add_image(idef, insert=(ox, 0), size_in_units=(w, h), dxfattribs={'layer': 'LADOT-SHEET'})
    return True


def sheet_layout(doc, name, ox, w, h):
    lay = doc.layouts.new(name)
    lay.page_setup(size=(w, h), margins=(0, 0, 0, 0), units='inch')
    lay.add_viewport(center=(w / 2, h / 2), size=(w, h), view_center_point=(ox + w / 2, h / 2), view_height=h)


def build_drawing(key, code, pages, pdf, work):
    import ezdxf
    doc = ezdxf.new('R2018', setup=False)
    doc.units = 1
    doc.header['$INSUNITS'] = 1
    doc.styles.new('ROMANS', dxfattribs={'font': 'romans.shx'})
    for layer, color in (('LADOT-LINE', 7), ('LADOT-FILL', 7), ('LADOT-TEXT', 7), ('LADOT-SHEET', 7)):
        doc.layers.new(layer, dxfattribs={'color': color})
    stem = asset_name(key, code)
    images, ox, raster = [], 0.0, False
    for n, number in enumerate(pages, 1):
        page = pdf[number - 1]
        w, h = page.rect.width / 72, page.rect.height / 72
        raster |= add_page(doc, page, ox, images, work, stem, n)
        sheet_layout(doc, f'{code} SHEET {n}', ox, w, h)
        ox += w + GAP
    if 'Layout1' in doc.layouts:
        doc.layouts.delete('Layout1')
    doc.saveas(work / (stem + '.dxf'))
    return stem, images


def oda(src, out):
    cmd = ['ODAFileConverter', str(src), str(out), 'ACAD2018', 'DWG', '0', '1', '*.dxf']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=7200)


def build(libredwg, dest, only=()):
    import ezdxf
    editions = read('data/reference/ladot-editions.json')
    made = {}
    stage = dest / 'dxf'
    stage.mkdir(parents=True, exist_ok=True)
    plan = []
    for key in DOCS:
        pdf = source_pdf(key, editions[key])
        doc = read('data/docs/ladot__' + key + '.json')
        for code, pages in ownership(key, pdf, doc, editions[key]).items():
            if only and code not in only:
                continue
            stem, images = build_drawing(key, code, pages, pdf, stage)
            plan.append((key, code, pages, stem, images))
    out = dest / 'dwg'
    out.mkdir(exist_ok=True)
    oda(stage, out)
    for key, code, pages, stem, images in plan:
        dwg = out / (stem + '.dwg')
        back = dest / (stem + '.check.dxf')
        subprocess.run([str(libredwg / 'dwg2dxf'), '-y', '-o', str(back), str(dwg)], capture_output=True)
        read_back = ezdxf.readfile(back)
        if len(read_back.modelspace()) == 0 or len([l for l in read_back.layouts if l.name != 'Model']) != len(pages):
            raise ValueError(f'{stem}: read-back is empty or missing sheets')
        if images:
            final = dest / (stem + '.zip')
            with zipfile.ZipFile(final, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(dwg, dwg.name)
                for name in images:
                    z.write(stage / name, name)
        else:
            final = dest / dwg.name
            shutil.copy(dwg, final)
        data = final.read_bytes()
        made[f'{key}/{code}'] = dict(doc=key, code=code, page=native_route(key, code), file=final.name, bytes=len(data),
                                     sha256=hashlib.sha256(data).hexdigest(), sheets=len(pages), raster=bool(images))
    return made, dest


def publish(made):
    rules = json.loads(Path('data/reference/asset-store.json').read_text())
    base = f'https://github.com/{rules["repository"]}/releases/download/{rules["release"]}/'
    out = {k: dict(v, url=base + v['file']) for k, v in sorted(made.items())}
    OUT.write_text(json.dumps(out, indent=1) + '\n')
    return out


ARCHIVE = Path('data/reference/ladot-cad/ladot-cad.tar.xz')


def hydrate(dest=Path('public/downloads/ladot-cad')):
    """Unpack the packed drawings for the download store (they never stay on Pages); check each hash."""
    import tarfile
    if not ARCHIVE.exists() or not OUT.exists():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE) as tar:
        tar.extractall(dest, filter='data')
    for m in json.loads(OUT.read_text()).values():
        data = (dest / m['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != m['sha256']:
            raise ValueError(f'LADOT CAD file changed: {m["file"]}')
    return len(json.loads(OUT.read_text()))


def link_pages(root):
    """Add the CAD download to each LADOT drawing page (run after ladot_drawings.prepare)."""
    if not OUT.exists():
        return 0
    n = 0
    for m in json.loads(OUT.read_text()).values():
        page = Path(root) / (m['page'].removeprefix(BASE + '/').strip('/') + '.md')
        if not page.exists():
            continue
        text = page.read_text()
        kind = 'ZIP' if m['raster'] else 'DWG'
        size = f'{m["bytes"] / 1e6:.1f} MB' if m['bytes'] >= 1e6 else f'{m["bytes"] // 1000} KB'
        link = (f'<p class="cad-drawing-download"><a class="ai-btn" download href="{m["url"]}">CAD drawing · {kind} · {size}</a>'
                f' <small>{m["sheets"]} sheet{"s" if m["sheets"] > 1 else ""}, one layout each'
                f'{", scanned sheets as images" if m["raster"] else ""}</small></p>')
        if 'cad-drawing-download' in text:
            continue
        head = re.search(r'<div class="dwg-head"[^>]*>.*?</div>\s*', text, re.S)
        at = head.end() if head else text.index('\n---\n', 4) + 5
        page.write_text(text[:at] + '\n' + link + '\n\n' + text[at:])
        n += 1
    return n


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--libredwg', type=Path, required=True)
    ap.add_argument('--only', nargs='*', default=())
    ap.add_argument('--keep', type=Path, help='folder to keep the built files in')
    a = ap.parse_args()
    dest = a.keep or Path(tempfile.mkdtemp()) / 'ladot'
    made, dest = build(a.libredwg, dest, set(a.only))
    print(len(made), 'drawings in', dest)
    publish(made)
