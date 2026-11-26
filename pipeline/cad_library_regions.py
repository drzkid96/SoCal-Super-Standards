"""Read the FP library's three sidewalk-closure specimens from their native ASM region data."""
import io
import math
import re
import shutil
import subprocess
from pathlib import Path

import ezdxf
from ezdxf.acis.api import load_dxf
from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from PIL import Image

PANELS = [
    ('R9-9','14260','14274','1425F',('14270','14271'),'15CEB'),
    ('R9-10','14262','14286',None,('14279','1427A','1427B'),'15CEF'),
    ('R9-11','14269','1426A',None,('1426E','1427C','1427D','14283'),'15CF5'),
]


def extract(work):
    raw=work.parent/'cad-inputs/-FP_Signs.dwg';source=work/'fp-acis-2018.dxf'
    if not source.exists() or source.stat().st_mtime<raw.stat().st_mtime:
        runtime=shutil.which('dwg2dxf') or next((work.parent/'.fp-chatgpt/.cache/fp-cad-convert').glob('runtime-*/bin/dwg2dxf'),None)
        if not runtime:raise FileNotFoundError('dwg2dxf is needed to preserve the native ASM bodies')
        subprocess.run([str(runtime),'--as','r2018','-y','-o',str(source),str(raw)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    drawing=ezdxf.readfile(source)
    model=drawing.modelspace()
    out=work/'masks';out.mkdir(exist_ok=True)
    records=[]
    for code,label,reg,insert,content,duplicate in PANELS:
        bodies=load_dxf(drawing.entitydb[reg]);face=bodies[0].lump.shell.face
        boundary=list(next(iter(face.loops())).coedges())
        if len(bodies)!=1 or len(boundary) not in (8,10):raise ValueError(f'Unexpected source topology {reg}')
        vertices=[]
        for coedge in boundary:
            edge=coedge.edge
            vertex=edge.start_vertex.point.location
            if insert:vertex=drawing.entitydb[insert].matrix44().transform(vertex)
            # The native contour runs clockwise. Four circular 90-degree corners survive
            # as ellipse-curve records in this ASM version while their sweep and end tangencies are exposed.
            curved=edge.curve.type!='straight-curve'
            sweep=edge.end_param-edge.start_param
            if curved and abs(sweep-math.pi/2)>.001:raise ValueError(f'Unexpected curve in {reg}')
            vertices.append((vertex.x,vertex.y,-math.tan(sweep/4) if curved else 0))
        perimeter=model.add_lwpolyline(vertices,format='xyb',close=True,dxfattribs={'layer':'D5','lineweight':drawing.entitydb[reg].dxf.lineweight})
        backend=svg.SVGBackend();ctx=RenderContext(drawing)
        cfg=Configuration(background_policy=BackgroundPolicy.WHITE,color_policy=ColorPolicy.BLACK)
        Frontend(ctx,backend,config=cfg).draw_entities([perimeter]+[drawing.entitydb[h] for h in content])
        page=layout.Page(0,0,layout.Units.mm)
        # A transparent exported viewport carries the source artwork, independent of the CAD background.
        vector=re.sub(r'<rect[^>]*/>','',backend.get_string(page))
        run=subprocess.run(['inkscape','--pipe','--export-width=1400','--export-type=png','--export-filename=-'],
                           input=vector.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        ink=Image.open(io.BytesIO(run.stdout)).convert('RGBA').getchannel('A')
        mask=ink.point(lambda p:0 if p>=110 else 255)
        filename=out/f'fp-region-{reg.lower()}.png';mask.save(filename)
        records.append(dict(id='fp-signs-region-'+reg.lower(),code=code,drawing='fp-signs',block=model.block_record.dxf.name,
                            mask=str(filename.resolve()),sourceKind='source region',space='Model',use='placed',
                            handle=reg,labelHandle=label,recordHandle=model.block_record_handle,
                            blockHandle=drawing.blocks.get(model.block_record.dxf.name).block.dxf.handle,
                            regionHandle=reg,sourceEntities=[reg]+([insert] if insert else [])+list(content),duplicatePlacements=[duplicate],
                            text=[drawing.entitydb[h].dxf.text for h in content if drawing.entitydb[h].dxftype()=='TEXT'],
                            note='Source ASM perimeter, printed legends and arrows recovered from an R2018 export of the original DWG.'))
    return records
