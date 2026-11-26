"""Plot the FP scenic-route specimen and the hatched school-crossing pictogram."""
import io
import math
import subprocess

from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, LineweightPolicy
from ezdxf.math import BoundingBox2d
from ezdxf.path import make_path
from PIL import Image,ImageDraw

SCENIC = 'fp-signs-ad7'
CROSSING = 'fp-signs-a62d'


def school_crossing(entities, width=2100):
    # The source carries the fill as individual lines repeated on 0.08-unit centers.
    # Join adjacent plotted lines at their original endpoints, including the white spaces
    # between arms and the little gaps at both briefcases.
    ext=bbox.extents(entities)
    x0,y0=ext.extmin.x,ext.extmin.y
    x1,y1=ext.extmax.x,ext.extmax.y
    scale=(width-2)/(x1-x0)
    height=round((y1-y0)*scale)+2
    mask=Image.new('L',(width,height),255)
    draw=ImageDraw.Draw(mask)
    pen=math.ceil(.085*scale)
    for entity in entities:
        points=make_path(entity).flattening(.001)
        shape=[(round((p.x-x0)*scale)+1,round((y1-p.y)*scale)+1) for p in points]
        stroke=pen
        if entity.dxftype()=='LINE':
            a,b=entity.dxf.start,entity.dxf.end
            if (abs(a.y-b.y)<1e-5 and 68<a.y<82 and
                    min(a.x,b.x)>1144 and max(a.x,b.x)<1158):
                # Pictogram hatching uses a separate 0.17-unit pitch.
                stroke=math.ceil(.18*scale)
        draw.line(shape,fill=0,width=stroke,joint='curve')
    return mask


def scenic_route(doc, entities, width=2100):
    # The drawing contains three landscape hatch fields made out of individual
    # 45-degree LINEs. Plot their actual clipped paths, at a readable scale.
    # Multiple discontinuous segments on the same hatch line stay together.
    plot=[]
    for entity in entities:
        if entity.dxftype()!='INSERT' or entity.dxf.name=='*X0':
            plot.append(entity)
            continue
        lines=list(entity.virtual_entities())
        intercepts=[p.dxf.start.y-p.dxf.start.x for p in lines]
        axes=sorted({round(v,4) for v in intercepts})
        chosen=set(axes[::5])
        plot.extend(e for e,angle in zip(lines,intercepts) if round(angle,4) in chosen)
    backend=svg.SVGBackend()
    cfg=Configuration(background_policy=BackgroundPolicy.WHITE,color_policy=ColorPolicy.BLACK,
                      lineweight_policy=LineweightPolicy.RELATIVE_FIXED,max_flattening_distance=.002)
    front=Frontend(RenderContext(doc),backend,config=cfg)
    front.set_background('#ffffff')
    front.draw_entities(plot)
    front.pipeline.finalize()
    # Bounds from the true panel boundary rather than the padded font bounding box.
    boundary=[e for e in entities if e.dxf.handle in {f'{h:X}' for h in range(0x101C1,0x101C9)}]
    if len(boundary)!=8:
        raise ValueError('Scenic-route boundary changed')
    ext=bbox.extents(boundary)
    bounds=BoundingBox2d((ext.extmin,ext.extmax))
    page=layout.Page(bounds.size.x,bounds.size.y,layout.Units.mm)
    opts=layout.Settings(max_stroke_width=.0012,fixed_stroke_width=1,output_coordinate_space=24000)
    drawing=backend.get_string(page,settings=opts,render_box=bounds)
    png=subprocess.run(['inkscape','--pipe','--export-type=png',f'--export-width={width}',
                         '--export-filename=-'],input=drawing.encode(),stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,check=True).stdout
    mask=Image.open(io.BytesIO(png)).convert('L').point(lambda v:0 if v<150 else 255)
    scale=(mask.width-1)/(ext.extmax.x-ext.extmin.x)
    draw=ImageDraw.Draw(mask)
    for edge in boundary:
        points=make_path(edge).flattening(.001)
        xy=[((p.x-ext.extmin.x)*scale,(ext.extmax.y-p.y)*scale) for p in points]
        draw.line(xy,fill=0,width=math.ceil(.13*scale),joint='curve')
    return mask


def prepare(lib,records,work):
    dest=work/'masks'
    dest.mkdir(exist_ok=True)
    for row in records:
        if row['id'] not in (SCENIC,CROSSING):
            continue
        entities=[lib.entities[h] for h in row['entities']]
        mask=scenic_route(lib.doc,entities) if row['id']==SCENIC else school_crossing(entities)
        target=dest/(row['id']+'-chart.png');mask.save(target)
        row.update(mask=str(target.resolve()),sourceKind='source monochrome plot')
