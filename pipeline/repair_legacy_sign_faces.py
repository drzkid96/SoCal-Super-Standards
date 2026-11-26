"""Recover native ink for four legacy MUTCD faces and their two directional mates."""
import argparse
import json
from pathlib import Path

import ezdxf
from ezdxf.fonts import fonts
from ezdxf.path import make_path, single_paths
from PIL import Image, ImageDraw
from shapely.affinity import translate
from shapely.geometry import GeometryCollection, Polygon
from shapely.ops import unary_union

from cad_blocks.geometry import drawing_context, record


def hexrange(start,end):
    return [f'{v:X}' for v in range(int(start,16),int(end,16)+1)]


def ring(doc,handles):
    """Join the original LINE/ARC endpoints in their closest connected order."""
    paths=[]
    for handle in handles:
        curve=make_path(doc.entitydb[handle])
        paths.append([(v.x,v.y) for v in curve.flattening(.00004,segments=8)])
    points=paths.pop(0)
    def distance(a,b):
        return (a[0]-b[0])**2+(a[1]-b[1])**2
    while paths:
        gap,i,reverse=min((distance(points[-1],path[-1 if reverse else 0]),i,reverse)
                          for i,path in enumerate(paths)for reverse in [False,True])
        assert gap<.011**2,(handles,gap)
        part=paths.pop(i)
        points.extend(reversed(part) if reverse else part)
    assert distance(points[-1],points[0])<.011**2
    return Polygon(points).buffer(0)


def letters(doc,ctx,row,handle):
    polygons=GeometryCollection()
    for mark in record(doc,ctx,{**row,'entities':[handle]}):
        for path in single_paths(mark.paths):
            coords=[(v.x,v.y) for v in path.flattening(.00004,segments=8)]
            polygons=polygons.symmetric_difference(Polygon(coords).buffer(0))
    return polygons


def mask(geometry,box,output):
    x0,y0,x1,y1=box
    scale=1600/(x1-x0)
    image=Image.new('L',(1600,round((y1-y0)*scale)),255)
    pen=ImageDraw.Draw(image)
    def coords(ring):
        return [((x-x0)*scale,(y1-y)*scale) for x,y in ring.coords]
    polygons=geometry.geoms if geometry.geom_type=='MultiPolygon' else [geometry]
    for polygon in sorted(polygons,key=lambda x:-x.area):
        pen.polygon(coords(polygon.exterior),fill=0)
        for hole in polygon.interiors:pen.polygon(coords(hole),fill=255)
    image.save(output,optimize=True)


def recover(doc,ctx,row):
    code=row['code']
    if code=='M2-1':
        border=ring(doc,hexrange('100C8','100CF')).difference(ring(doc,hexrange('100D0','100D7')))
        legend=letters(doc,ctx,row,'100D8')
        bx,by,*be=border.bounds
        tx,ty,*te=legend.bounds
        legend=translate(legend,(bx+be[0]-tx-te[0])/2,(by+be[1]-ty-te[1])/2)
        return border.union(legend),'Original library JCT contours centered within its original nested border to clear the descender.'
    if code=='W7-3b':
        edge=ring(doc,hexrange('11493','1149A')).difference(ring(doc,hexrange('1255D','12564')))
        upper=letters(doc,ctx,row,'1149B')
        lower=letters(doc,ctx,row,'1149C')
        slash=ring(doc,['1149D','114A0','114A1','114A2'])
        percent=unary_union([slash,ring(doc,['1149E']).difference(ring(doc,['114A3'])),
                             ring(doc,['1149F']).difference(ring(doc,['114A4']))])
        left_to_right=sorted(upper.geoms,key=lambda x:x.bounds[0])
        gap_center=(left_to_right[0].bounds[2]+left_to_right[1].bounds[0])/2
        sign_center=(percent.bounds[0]+percent.bounds[2])/2
        percent=translate(percent,gap_center-sign_center,0)
        assert percent.distance(upper)>.018
        return unary_union([edge,upper,lower,percent]),'Original 9 and percent sign separated using the space before GRADE. FHWA Standard Highway Signs 2004, W7-3b, verifies 9% GRADE / 7 MILES.'
    rows={
        'M4-10L':(hexrange('1013D','10140'),hexrange('10144','1014C'),'10143'),
        'M4-10R':(hexrange('1014D','10150'),hexrange('10154','1015C'),'10153'),
        'R6-1L':(hexrange('121A1','121A8'),hexrange('10973','1097B'),'1097C'),
        'R6-1R':(hexrange('121A9','121B0'),hexrange('10987','1098F'),'10990')}
    frame,arrow,text=rows[code]
    ground=ring(doc,frame)
    cutout=ring(doc,arrow)
    legend=letters(doc,ctx,row,text)
    # The source uses a substituted TEXT style. Align its actual ink extents
    # to the straight shaft so the top of ONE WAY does not fuse into the ground.
    shaft_paths=[make_path(doc.entitydb[h]) for h in arrow]
    shaft_edges=[p for p in shaft_paths if abs(p.start.y-p.end.y)<.001 and abs(p.start.x-p.end.x)>1]
    assert len(shaft_edges)==2
    x=(max(min(p.start.x,p.end.x) for p in shaft_edges)+min(max(p.start.x,p.end.x) for p in shaft_edges))/2
    y=sum(p.start.y for p in shaft_edges)/2
    xmin,ymin,xmax,ymax=legend.bounds
    legend=translate(legend,x-(xmin+xmax)/2,y-(ymin+ymax)/2)
    assert cutout.covers(legend)
    return ground.difference(cutout).union(legend),'Original CAD perimeter and arrow form the reverse field around the original lettering, preserving the documented hand and message.'


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('work',type=Path)
    cli.add_argument('--font-folder',type=Path)
    args=cli.parse_args()
    work=args.work.resolve()
    if args.font_folder:fonts.font_manager.scan_folder(args.font_folder)
    original=work/'all-sources/mutcd-standard-signs.dxf'
    doc=ezdxf.readfile(original)
    ctx=drawing_context(doc)
    rows=json.loads((work/'block-inputs/mutcd-library.json').read_text())
    output=work/'masks'/'repaired-legacy'
    output.mkdir(parents=True,exist_ok=True)
    evidence=[]
    for row in rows:
        if row['code'] not in {'M2-1','W7-3b','M4-10L','M4-10R','R6-1L','R6-1R'}:continue
        geom,note=recover(doc,ctx,row)
        file=output/(row['id']+'.png')
        mask(geom,row['physicalBounds'],file)
        override={'id':row['id'],'outlineMask':str(file),'notes':note}
        if row['code']=='M2-1':
            src={'publisher':'FHWA','reference':'2004 Standard Highway Signs, M2-1 Junction Auxiliary, sheet 3-13.','url':'https://mutcd.fhwa.dot.gov/SHSe/guide.pdf#page=47','page':47,'sha256':'eb0d9cf3c728146dfb386d59fb805a7aa4c178783cd3fa04d9f85a0524d4f246'}
            override.update(publisherPlateSize=[21,15],publisherSizeBasis='width-height',publisherPlateSource=src,publisherPlateCondition='2004 black-on-white Junction Auxiliary plaque')
        if row['code']=='W7-3b':
            src={'publisher':'FHWA','reference':'2004 Standard Highway Signs, W7-3b Hill Plaque (24 × 18 in).','url':'https://mutcd.fhwa.dot.gov/SHSe/Warning.pdf#page=52','page':52,'sha256':'104fb0ea2dc76749f86708ef6a14709aad8336fb8ea6798340781995552fbe64'}
            override.update(publisherPlateSize=[24,18],publisherSizeBasis='width-height',publisherPlateSource=src,publisherPlateCondition='2004 hill plaque, 9% GRADE / 7 MILES')
        evidence.append(override)
    assert len(evidence)==6
    (work/'block-inputs/zz-mutcd-repaired-legacy.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':
    main()
