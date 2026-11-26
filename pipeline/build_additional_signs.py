"""Build individual inch-based drawings and matching browser legend geometry from FHWA faces."""
import gzip
import io
import json
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import contourpy
import ezdxf
import numpy as np
from PIL import Image
from matplotlib.path import Path as VectorPath
from build_issued_block_faces import render_pixels, monochrome, isolate_issued_panel

CODES = """R1-2aP R1-2bP R1-2cP R1-3P R1-10P R2-5P R2-5aP R2-5bP R2-5cP
R2-6P R2-6aP R3-5bP R3-5dP R3-5fP R3-5gP R3-9dP R9-11a R9-12
W8-5P W8-5aP W8-5bP W8-5cP W10-9P W10-13P W11-15P W16-12aP W16-13P W16-15P""".split()


def build(converter):
    signs = {r['code']: r for r in json.loads(Path('data/signs/signs.json').read_text())}
    sizes = json.loads(Path('data/signs/ca_sizes.json').read_text())
    records, geometry = [], {}
    with tempfile.TemporaryDirectory() as temp, ZipFile('data/reference/additional-sign-blocks.zip','w',ZIP_DEFLATED) as archive:
        for code in CODES:
            r = signs[code]
            sizes_by_use = sizes[code]['cols']
            size = next(v for k,v in sizes_by_use.items() if 'Single Lane' in k or k=='Conventional Road')
            w,h = map(int,size.split(' x '))
            pixels = render_pixels(Path('public'+r['svg']),1000)
            ink,panel = isolate_issued_panel(pixels,monochrome(pixels),code)
            y,x = np.where(panel if panel is not None else ink)
            ink = ink[y.min():y.max()+1,x.min():x.max()+1]
            height,width = ink.shape
            doc = ezdxf.new('R2000');doc.units=1
            curves = contourpy.contour_generator(z=np.pad(ink.astype(float),1),fill_type='OuterOffset')
            polys,cuts = curves.filled(.5,2)
            for poly,offsets in zip(polys,cuts):
                hatch=doc.modelspace().add_hatch(color=7)
                for i,(a,b) in enumerate(zip(offsets,offsets[1:])):
                    points=[((px-.5)*w/width-w/2,h/2-(py-.5)*h/height) for px,py in poly[a:b]]
                    path=VectorPath(points);path.simplify_threshold=min(w/width,h/height)*.5;loop=path.cleaned(simplify=True).vertices[:-1]
                    if len(loop)>3:hatch.paths.add_polyline_path(loop[:-1],is_closed=True,flags=int(i==0))
                if not hatch.paths:doc.modelspace().delete_entity(hatch)
            dxf=Path(temp)/'sign.dxf';dwg=dxf.with_suffix('.dwg');doc.saveas(dxf)
            subprocess.run([converter,'-y','-o',str(dwg),str(dxf)],check=True,capture_output=True)
            pairs=list(zip(*[iter(dxf.read_text().splitlines())]*2));tags=[]
            for k,v in pairs[pairs.index(('  2','ENTITIES'))+1:]:
                if int(k)==0 and v=='ENDSEC':break
                if int(k) not in (5,330):tags.extend([k,v])
            geom=gzip.compress(('\n'.join(tags)+'\n').encode(),mtime=0)
            key='shs-'+code.lower();native=dwg.read_bytes()
            preview='/figs/cad-blocks/'+key+'.webp';file='individual/FHWA/'+code+'.dwg'
            image=Image.fromarray(np.where(ink,0,255).astype('uint8'));image.thumbnail((320,320))
            buf=io.BytesIO();image.save(buf,'WEBP',lossless=True)
            archive.writestr(file,native);archive.writestr(preview[1:],buf.getvalue());archive.writestr('geometry/'+key+'.dxf.gz',geom)
            geometry[key]=dict(name=code,sha256=sha256(geom).hexdigest(),bytes=len(geom),entities=len(doc.modelspace()),bounds=[-w/2,-h/2,w/2,h/2])
            records.append(dict(id=key,code=code,blockName=code,file=file,width=w,height=h,sizeStatus='published reference size',aliases=[code],signUrl='/SoCal-Super-Standards/signs/'+r['slug']+'/',sourceDrawing='official-standard',preview=preview,sha256=sha256(native).hexdigest(),bytes=len(native),description=r['name'],matchStatus='From issued artwork'))
        archive.writestr('records.json',json.dumps(records));archive.writestr('geometry.json',json.dumps(geometry))


if __name__=='__main__':
    build(sys.argv[1])
