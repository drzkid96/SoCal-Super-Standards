"""One library drawing with every pavement marking block, for AutoCAD's Blocks palette (Libraries tab),
DesignCenter or tool palettes.

Each published marking drawing is read back, its block definition is copied in unchanged, and one
reference of each is laid out by group with its code under it (ROMANS). Units are feet.

  python3 pipeline/marking_library.py --libredwg <dir with dxf2dwg and dwg2dxf>
"""
import argparse
import tempfile
from pathlib import Path

from ezdxf import bbox


CATALOG = Path('data/reference/design-blocks.json')
FOLDER = Path('public/downloads/markings/cad')
NAME = 'SSS-PMARK-LIBRARY.dwg'
GAP = 4.0      # ft between blocks
TEXT = 1.0     # ft label height


def build(libredwg, libdxfrw=None):
    """Superseded by block_libraries.py (group sheet layouts, AutoCAD 2018); kept as the entry point."""
    import block_libraries
    spec = next(s for s in block_libraries.LIBRARIES if s['file'] == NAME)
    with tempfile.TemporaryDirectory() as tmp:
        return block_libraries.build_library(spec, libredwg, libdxfrw, Path(tmp))[0]


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
    parser.add_argument('--libdxfrw', type=Path)
    a = parser.parse_args()
    print(build(a.libredwg, a.libdxfrw), 'blocks in', FOLDER / NAME)
