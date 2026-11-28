"""Preview pictures for the marking and signal block pages, drawn from each published DWG.

Each DWG is converted with ODA File Converter (so dynamic blocks show the state they were saved in),
its block insert is drawn (the code label is left out) and the picture is written as SVG to public/block-previews/<route>/<file stem>.svg. Everything is drawn
as plotted: black on white (white markings print black), green and red fields in their guidance colors.
Only the block itself is drawn; the base point is described in the block details.

  python3 pipeline/block_previews.py [--only CODE ...]   (needs ODAFileConverter, and xvfb-run when headless)
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration, HatchPolicy, LineweightPolicy

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/block-previews')


def convert(folder, out):
    cmd = ['ODAFileConverter', str(folder), str(out), 'ACAD2018', 'DXF', '0', '1', '*.dwg']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=1800)


def draw(doc):
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    if not ext.has_data:
        raise ValueError('empty drawing')
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, hatch_policy=HatchPolicy.SHOW_SOLID,
                        lineweight_policy=LineweightPolicy.RELATIVE, min_lineweight=0.6)
    for e in list(msp):
        if e.dxftype() not in ('INSERT',):
            msp.delete_entity(e)
    # green fields are pattern hatches in AutoCAD (symbols show through); drawn solid here, so they go back
    for blk in doc.blocks:
        space = blk.entity_space
        items = list(space)
        back = [e for e in items if e.dxftype() == 'HATCH' and (e.dxf.get('true_color') is not None or e.dxf.get('color') in (3, 74, 76))]
        if back:
            space.clear()
            for e in back + [e for e in items if e not in back]:
                space.add(e)
    for blk in doc.blocks:      # helpers that never plot stay out of the picture
        for e in [e for e in blk if e.dxf.get('layer', '').upper() in ('NOPLOT', 'DEFPOINTS')]:
            blk.delete_entity(e)
    ext = bbox.extents(msp)
    backend = svg.SVGBackend()
    Frontend(RenderContext(doc), backend, config=cfg).draw_layout(msp)
    w, h = ext.size.x, ext.size.y
    w, h = max(w, 0.3 * h), max(h, 0.3 * w)  # keep thin symbols (single lines) readable
    side = 240
    pad = 0.08 * max(w, h)
    page = layout.Page(side * (w + 2 * pad) / max(w + 2 * pad, h + 2 * pad), side * (h + 2 * pad) / max(w + 2 * pad, h + 2 * pad),
                       layout.Units.px, margins=layout.Margins.all(side * 0.04))
    text = backend.get_string(page, settings=layout.Settings(fit_page=True, output_coordinate_space=10000))
    text = text.replace('#808080', '#9a9a9a').replace('#00ff00', '#3c9002').replace('#ffff00', '#d9a400')   # ACI 3 as guidance green, yellow readable on white
    # pen widths readable at thumbnail size: at least 1.2 percent of the long side
    view = [float(v) for v in re.search(r'viewBox="([^"]+)"', text)[1].split()]
    pen = 0.012 * max(view[2:])
    text = re.sub(r'stroke-width: ([0-9.]+)', lambda m: f'stroke-width: {max(float(m[1]), pen):.0f}', text)
    return re.sub(r' width="[^"]+" height="[^"]+"', '', text, count=1)


def build(only=()):
    catalog = json.loads(CATALOG.read_text())
    done = 0
    for route, collection in catalog.items():
        rows = [r for r in collection['blocks'] if not only or r['code'] in only]
        if not rows:
            continue
        target = OUT / route
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            src, dxf = Path(tmp) / 'in', Path(tmp) / 'out'
            src.mkdir(), dxf.mkdir()
            for row in rows:
                shutil.copy(Path('public/downloads') / route / row['file'], src / row['file'])
            convert(src, dxf)
            for row in rows:
                stem = Path(row['file']).stem
                doc = ezdxf.readfile(dxf / (stem + '.dxf'))
                (target / (stem + '.svg')).write_text(draw(doc))
                done += 1
    return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='*', default=())
    a = ap.parse_args()
    print(build(set(a.only)), 'previews written to', OUT)
