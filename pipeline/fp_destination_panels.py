"""Preserve the destination legends of the printed multi-panel bicycle signs in monochrome."""
import io
import re
import subprocess

from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from PIL import Image


def prepare(lib, records, work):
    ctx=RenderContext(lib.doc)
    cfg=Configuration(background_policy=BackgroundPolicy.WHITE,color_policy=ColorPolicy.BLACK)
    dst=work/'masks';dst.mkdir(exist_ok=True)
    for rec in records:
        if not (rec['code'].startswith('D1-') and 'MOD ' in rec['code']):continue
        # Source drawing places the destination legends in ACI 255 on unfilled board linework.
        # Plot every native entity in the monochrome foreground, including original MTEXT and symbols.
        selected=[lib.entities[h] for h in rec['entities']]
        backend=svg.SVGBackend()
        Frontend(ctx,backend,config=cfg).draw_entities(selected)
        vector=re.sub(r'<rect[^>]*/>','',backend.get_string(layout.Page(0,0,layout.Units.mm)))
        run=subprocess.run(['inkscape','--pipe','--export-type=png','--export-width=1700','--export-filename=-'],
                           input=vector.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        alpha=Image.open(io.BytesIO(run.stdout)).convert('RGBA').getchannel('A')
        mask=alpha.point(lambda v:0 if v>=100 else 255)
        target=dst/(rec['id']+'-destination.png');mask.save(target)
        rec.update(mask=str(target.resolve()),sourceKind='source monochrome plot',
                   text=[lib.texts[h] for h in rec['entities'] if h in lib.texts])
