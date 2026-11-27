"""One library drawing with every pavement marking block, for AutoCAD's Blocks palette (Libraries tab),
DesignCenter or tool palettes.

Each published marking drawing is read back, its block definition is copied in unchanged, and one
reference of each is laid out by group with its code under it (ROMANS). Units are feet.

  python3 pipeline/marking_library.py --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

from sign_cells import r2000_document

CATALOG = Path('data/reference/design-blocks.json')
FOLDER = Path('public/downloads/markings/cad')
NAME = 'SSS-PMARK-LIBRARY.dwg'
GAP = 4.0      # ft between blocks
TEXT = 1.0     # ft label height


def build(libredwg):
    section = json.loads(CATALOG.read_text())['markings/cad']
    rows = [r for r in section['blocks'] if r['file'] != NAME]
    lib = r2000_document()
    lib.units = 2
    for name, color in (('P-PMARK', 7), ('P-PMARK-TEXT', 7)):
        if name not in lib.layers:
            lib.layers.new(name, dxfattribs={'color': color})
    msp = lib.modelspace()
    y = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for group in section['groups']:
            members = [r for r in rows if r['group'] == group]
            if not members:
                continue
            msp.add_mtext(group.upper(), dxfattribs={'layer': 'P-PMARK-TEXT', 'style': 'ROMANS', 'char_height': 2 * TEXT,
                                                     'insert': (0, y), 'attachment_point': 7})
            y -= 3 * TEXT + GAP
            x, row_h = 0.0, 0.0
            for r in members:
                dxf = Path(tmp) / (r['code'] + '.dxf')
                subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', dxf, FOLDER / r['file']], capture_output=True, check=True)
                src = ezdxf.readfile(dxf)
                imp = Importer(src, lib)
                imp.import_block(r['code'])
                imp.finalize()
                ext = bbox.extents(lib.blocks[r['code']])
                w, h = ext.extmax.x - ext.extmin.x, ext.extmax.y - ext.extmin.y
                if x and (x + w > 120 or group == 'Striping patterns'):  # one striping detail per row reads clearly
                    x, y, row_h = 0.0, y - row_h - GAP - 2 * TEXT, 0.0
                bx, top = x - ext.extmin.x, y - ext.extmax.y
                msp.add_blockref(r['code'], (bx, top), dxfattribs={'layer': 'P-PMARK'})
                label = r['code'].replace('CT-', '')
                msp.add_mtext(label, dxfattribs={'layer': 'P-PMARK-TEXT', 'style': 'ROMANS', 'char_height': TEXT * 0.6,
                                                 'insert': (x + w / 2, y - h - 0.5), 'attachment_point': 2})
                x += max(w, len(label) * TEXT * 0.6 * 1.1) + GAP  # label width with margin
                row_h = max(row_h, h + TEXT)
            y -= row_h + 2 * GAP + 2 * TEXT
        lib.set_modelspace_vport(height=-y * 1.05, center=(60, y / 2))
        path = Path(tmp) / 'lib.dxf'
        lib.saveas(path)
        target = FOLDER / NAME
        log = subprocess.run([libredwg / 'dxf2dwg', '-y', '--as', 'r2000', '-o', target, path], capture_output=True, text=True, check=True)
        if re.search(r'warning|error', log.stdout + log.stderr, re.I):
            raise ValueError('library: ' + (log.stdout + log.stderr)[-300:])
        back = Path(tmp) / 'rt.dxf'
        subprocess.run([libredwg / 'dwg2dxf', '-y', '-o', back, target], capture_output=True, check=True)
        read = ezdxf.readfile(back)
        names = {b.name for b in read.blocks if not b.is_any_layout and not b.name.startswith('*')}
        missing = {r['code'] for r in rows} - names
        if missing:
            raise ValueError(f'library is missing {sorted(missing)}')
        for r in rows:
            if len(read.blocks[r['code']]) != len(lib.blocks[r['code']]):
                raise ValueError(r['code'] + ': library block differs after read-back')
        render(read, FOLDER / NAME.replace('.dwg', '.webp'))
    return len(rows)


def render(doc, target, width_px=1000):
    """Overview image for the page, drawn from the DWG as read back (what users will get)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    ext = bbox.extents(doc.modelspace())
    w, h = ext.extmax.x - ext.extmin.x, ext.extmax.y - ext.extmin.y
    fig = plt.figure(figsize=(7, 7 * h / w))
    ax = fig.add_axes([0, 0, 1, 1])
    # pavement gray, so white and yellow markings read as they do on the street
    config = Configuration(background_policy=BackgroundPolicy.CUSTOM, custom_bg_color='#2e2e2e')
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(doc.modelspace())
    png = Path(tempfile.mkdtemp()) / 'lib.png'
    fig.savefig(png, dpi=2 * width_px / 7, facecolor='#2e2e2e')
    plt.close(fig)
    im = Image.open(png).convert('RGB')
    im = im.resize((width_px, round(im.height * width_px / im.width)), Image.LANCZOS)
    im.save(target, 'WEBP', quality=82)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--libredwg', type=Path, required=True)
    print(build(parser.parse_args().libredwg), 'blocks in', FOLDER / NAME)
