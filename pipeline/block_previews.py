"""Preview pictures for the marking and signal block pages, drawn from each published DWG.

Each DWG is converted with ODA File Converter (so dynamic blocks show the state they were saved in),
its block insert is drawn (the code label is left out) and the picture is written as SVG to public/block-previews/<route>/<file stem>.svg. Markings sit on a
pavement-gray tile in field colors; signal and survey symbols are drawn black on white.

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
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, HatchPolicy, LineweightPolicy

CATALOG = Path('data/reference/design-blocks.json')
OUT = Path('public/block-previews')
# field colors for markings (screen approximations of the MUTCD marking colors)
FIELD = {'#ffffff': '#f4f4f1', '#000000': '#f4f4f1', '#00ff00': '#3a9a4b', '#ffff00': '#f2c230', '#0000ff': '#2e6bb5',
         '#ff0000': '#cf3b32', '#00ffff': '#f4f4f1', '#ff00ff': '#f4f4f1'}


def convert(folder, out):
    cmd = ['ODAFileConverter', str(folder), str(out), 'ACAD2018', 'DXF', '0', '1', '*.dwg']
    if shutil.which('xvfb-run'):
        cmd = ['xvfb-run', '-a'] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=1800)


def draw(doc, marking):
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    if not ext.has_data:
        raise ValueError('empty drawing')
    if marking:
        cfg = Configuration(background_policy=BackgroundPolicy.CUSTOM, custom_bg_color='#3b3b3b', hatch_policy=HatchPolicy.SHOW_SOLID,
                            lineweight_policy=LineweightPolicy.RELATIVE, min_lineweight=0.6)
    else:
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK,
                            lineweight_policy=LineweightPolicy.RELATIVE, min_lineweight=0.6)
    for e in list(msp):
        if e.dxftype() not in ('INSERT',):
            msp.delete_entity(e)
    if marking:
        # green fields are pattern hatches in AutoCAD (symbols show through); drawn solid here,
        # so they go to the back of each block
        for blk in doc.blocks:
            space = blk.entity_space
            items = list(space)
            back = [e for e in items if e.dxftype() == 'HATCH' and e.dxf.get('color') == 3]
            if back:
                space.clear()
                for e in back + [e for e in items if e not in back]:
                    space.add(e)
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
    if marking:
        text = re.sub(r'#[0-9a-fA-F]{6}', lambda m: FIELD.get(m[0].lower(), m[0]), text)
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
                (target / (stem + '.svg')).write_text(draw(doc, route.startswith('markings')))
                done += 1
    return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='*', default=())
    a = ap.parse_args()
    print(build(set(a.only)), 'previews written to', OUT)
