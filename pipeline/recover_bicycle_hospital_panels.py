"""Recover the FP library's two-color route 13 and the issued conventional hospital service panel."""
import argparse
import io
import json
import subprocess
from pathlib import Path

import ezdxf
import numpy as np
import pymupdf
from PIL import Image,ImageDraw
from ezdxf import bbox
from ezdxf.path import make_path
from ezdxf.math import BoundingBox2d
from ezdxf.addons.drawing import Frontend,RenderContext,layout,svg
from ezdxf.addons.drawing.config import ColorPolicy,BackgroundPolicy,Configuration
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]

def route_13(work, target):
    # Original ACI 3 hatches and the bicycle linework both become black under a naive pen table.
    # Use the FP glyph outlines as knockouts on the same oval; retain the original number 13.
    source=ezdxf.readfile(work/'all-sources/fp-signs.dxf')
    rows=json.loads((work/'block-inputs/fp-supplemental.json').read_text())
    row=next(r for r in rows if r['id']=='fp-signs-14021')
    boundary=source.entitydb['138BB']
    ext=bbox.extents([boundary]);x,y=ext.extmin.x,ext.extmin.y
    w,h=ext.size.x,ext.size.y
    scale=2000/h
    panel=Image.new('L',(round(w*scale),2000),255);draw=ImageDraw.Draw(panel)
    def vertices(e):
        return [((v.x-x)*scale,(ext.extmax.y-v.y)*scale) for v in make_path(e).flattening(.001)]
    draw.line(vertices(boundary),fill=0,width=4,joint='curve')
    draw.polygon(vertices(source.entitydb['138BE']),fill=0)
    for handle in ('13D66','13D96'):
        draw.polygon(vertices(source.entitydb[handle]),fill=255)
    bike=[source.entitydb[h] for h in row['entities'] if 0x13880<=int(h,16)<0x138BB]
    backend=svg.SVGBackend();front=Frontend(RenderContext(source),backend,config=Configuration(
        color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE,max_flattening_distance=.002))
    front.set_background('#ffffff');front.draw_entities(bike);front.pipeline.finalize()
    raw=backend.get_string(layout.Page(w,h),render_box=BoundingBox2d((ext.extmin,ext.extmax)),
                           settings=layout.Settings(output_coordinate_space=24000))
    run=subprocess.run(['inkscape','--pipe','--export-type=png','--export-height=2000','--export-filename=-'],
                       input=raw.encode(),check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    ink=np.array(Image.open(io.BytesIO(run.stdout)).convert('L').resize(panel.size))<128
    a=np.array(panel);a[ink]=255
    Image.fromarray(a).save(target)

def hospital(pdf,target):
    with pymupdf.open(pdf) as doc:
        page=doc[86];drawings=page.get_drawings()[:4]
        assert 'D9-2' in page.get_text() and 'HOSPITAL' in page.get_text()
        outer=drawings[0]['rect']
        assert abs(outer.width/outer.height-1)<.001
        fg=drawings[2]['fill']
        assert fg[2]>fg[1]>fg[0] and min(drawings[3]['fill'])>.99
        new=pymupdf.open();panel=new.new_page(width=outer.width,height=outer.height)
        for path,ink in zip(drawings,[1,0,0,1]):
            shape=panel.new_shape()
            def point(pt):return (pt.x-outer.x0,pt.y-outer.y0)
            for item in path['items']:
                if item[0]=='l':shape.draw_line(*(point(e) for e in item[1:]))
                elif item[0]=='c':shape.draw_bezier(*(point(e) for e in item[1:]))
                else:raise ValueError(f'Unexpected path in hospital sheet: {item[0]}')
            shape.finish(color=None,fill=(ink,),even_odd=path['even_odd'],closePath=True)
            shape.commit()
        factor=1800/outer.width
        px=panel.get_pixmap(matrix=pymupdf.Matrix(factor,factor),colorspace=pymupdf.csGRAY)
        ink=np.frombuffer(px.samples,dtype='uint8').reshape(px.height,px.width)<128
        # Keep the 1/2-inch white inset on all sides; the cut perimeter is visible on white paper.
        solid=ndimage.binary_fill_holes(ink)
        Image.fromarray(np.where(ink| (solid&~ndimage.binary_erosion(solid)),0,255).astype('uint8')).save(target)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('work',type=Path)
    parser.add_argument('--guide',type=Path,default=ROOT/'.fhwa-releases/2024_SHS_Release_6-Guide_Signs.pdf')
    args=parser.parse_args();target=ROOT/'data/reference/cad-standards/source-masks';target.mkdir(exist_ok=True)
    route_13(args.work,target/'fp-signs-14021.png')
    hospital(args.guide,target/'mutcd-sheet-d9-2-11f56.png')
if __name__=='__main__':main()
