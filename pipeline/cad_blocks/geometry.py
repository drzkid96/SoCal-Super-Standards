"""Reduce selected CAD graphics to physical, font-independent, editable monochrome vectors."""
import math
from pathlib import Path
from dataclasses import dataclass
from ezdxf import path
from ezdxf.path.converter import build_edge_path
from ezdxf.addons.drawing import Frontend, RenderContext, config, recorder
from ezdxf.fonts import fonts
from ezdxf.math import Matrix44, Vec2
from shapely.geometry import Polygon, LineString, GeometryCollection
from shapely.ops import unary_union, polygonize
from scipy.spatial import cKDTree

@dataclass
class Mark:
    paths: list
    fill: bool
    white: bool
    kind: str = ""

def vertices_path(pts, close=False):
    it=iter(pts)
    p=path.Path(next(it))
    for v in it:p.line_to(v)
    if close:p.close()
    return p

def drawing_context(d):
    ctx=RenderContext(d)
    for style in d.styles:
        original=style.dxf.font.lower()
        if original not in ('arialn.ttf','arialnb.ttf'):continue
        if fonts.font_manager.has_font(original):continue
        substitute='LiberationSansNarrow-Bold.ttf' if original=='arialnb.ttf' else 'LiberationSansNarrow-Regular.ttf'
        if fonts.font_manager.has_font(substitute):
            ctx.fonts[style.dxf.name.lower()]=fonts.font_manager.get_font_face(substitute)
    return ctx

def record(d, ctx, selection):
    if 'entities' in selection:entities=[d.entitydb[h] for h in selection['entities']]
    else:entities=list(d.blocks[selection['block']])
    clean=[]
    for e in entities:
        if e.dxf.handle in selection.get('skipSourceHandles',[]):continue
        if e.dxftype()=='TEXT' and e.dxf.handle in selection.get('textOverrides',{}):
            value=selection['textOverrides'][e.dxf.handle]
            e=e.copy()
            e.dxf.text=str(value)
        if e.dxftype() in ('ATTDEF','ATTRIB'):
            replacement=selection.get('attributeTextOverrides',{}).get(e.dxf.handle)
            if replacement is None:continue
            attrs={k:v for k,v in e.dxfattribs().items() if k in {'insert','align_point','height','rotation','style','halign','valign','width','layer','color'}}
            from ezdxf.entities import Text
            e=Text.new(dxfattribs={**attrs,'text':str(replacement)},doc=d)
        if e.dxftype() in ('VIEWPORT','IMAGE','XLINE','RAY','DIMENSION','LEADER','MULTILEADER'):continue
        # Detail D's two side labels document the combined traffic-control face.
        if selection.get('handle')=='13A3E86' and e.dxf.handle in ('13A3E85','13A3E86'):continue
        if selection['code'].upper().startswith('OM') and e.dxftype()=='TEXT' and e.dxf.text.strip().upper() in ('(YELLOW)','(RED)'):continue
        if e.dxftype()=='MTEXT' and 'Arial Narrow|' in e.text and not fonts.font_manager.has_font('arialnb.ttf') and fonts.font_manager.has_font('LiberationSansNarrow-Bold.ttf'):
            e=e.copy();e.text=e.text.replace('Arial Narrow|','Liberation Sans Narrow|')
        clean.append(e)
    backend=recorder.Recorder()
    frontend=Frontend(ctx,backend,config=config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                    color_policy=config.ColorPolicy.COLOR, max_flattening_distance=.002, min_lineweight=.01))
    # Deliberately recovered legend geometry can be on a frozen original layer.
    # Only selected source entities are passed to the renderer.
    for layer in {str(e.dxf.layer).lower() for e in clean}:
        if layer in ctx.layers:ctx.layers[layer].is_visible=True
    frontend.set_background('#ffffff');frontend.draw_entities(clean);frontend.pipeline.finalize()
    marks=[]
    for r,props in backend.player().recordings():
        white=props.color.lower()[:7]=='#ffffff' or r.handle in selection.get('subtractHatches',[])
        source=d.entitydb.get(r.handle)
        kind=source.dxftype() if source else ''
        if isinstance(r,recorder.FilledPathsRecord):
            pp=[v.to_path() for v in r.paths];marks.append(Mark(pp,True,white,kind))
        elif isinstance(r,recorder.PathRecord):marks.append(Mark([r.path.to_path()],False,white,kind))
        elif isinstance(r,recorder.PointsRecord):
            pts=list(r.points.vertices())
            if len(pts)>=2:marks.append(Mark([vertices_path(pts,len(pts)>2)],len(pts)>2,white,kind))
        elif isinstance(r,recorder.SolidLinesRecord):
            pts=list(r.lines.vertices())
            marks.append(Mark([vertices_path(pts[i:i+2]) for i in range(0,len(pts),2)],False,white,kind))
    # The Pico author drew lane separators as bare centerlines. Give only those
    # lines printable ink width; generic hairlines on the source artwork stay intact.
    for h in selection.get('separatorHandles',[]):
        e=d.entitydb[h]
        line=path.make_path(e)
        a,b=line.start,line.end
        signwidth=selection['bounds'][1][0]-selection['bounds'][0][0]
        offset=(b-a).normalize().orthogonal()*signwidth*.0026
        marks.append(Mark([vertices_path([a-offset,b-offset,b+offset,a+offset],True)],True,False,'SOURCE-SEPARATOR'))
    for handles in selection.get('joinedGlyphContours',[]):
        points=[]
        for h,reverse in handles:
            pp=path.make_path(d.entitydb[h])
            vertices=list(pp.control_vertices())
            points.extend(reversed(vertices) if reverse else vertices)
        marks.append(Mark([vertices_path(points,True)],True,False,'SOURCE-GLYPH'))
    # Some exploded rims terminate just short of their original fork or hub.
    # Use the identified native curves, in source order, to close that aperture.
    for handles in selection.get('joinedApertureContours',[]):
        ring=path.Path()
        for handle,reverse in handles:
            part=path.make_path(d.entitydb[handle])
            ring.append_path(part.reversed() if reverse else part)
        ring.close()
        marks.append(Mark([ring],False,False,'SOURCE-APERTURE'))
    if selection.get('sourceRingSlash'):
        ring=[path.make_path(d.entitydb[h]) for h in selection['sourceRingSlash']]
        for p in ring:p.close()
        marks.append(Mark(ring,True,False,'SOURCE-SLASH'))
    for shape in selection.get('solidContours',[]):
        if shape.get('fill')=='black':marks.append(Mark([vertices_path(shape['vertices'],True)],True,False,'SOURCE-CLOSED'))
    return marks

def allpaths(marks):
    return [p for m in marks for p in m.paths if len(p)]

def polygon(p,tol):
    vertices=[(v.x,v.y) for v in p.flattening(tol,segments=6)]
    if len(vertices)<4:return None
    g=Polygon(vertices)
    if not g.is_valid:g=g.buffer(0)
    return g if not g.is_empty and g.area>tol*tol and g.geom_type=='Polygon' else None

def get_bounds(marks,selection):
    r=selection.get('physicalBounds')
    if r and len(r)==4:return tuple(r)
    if selection.get('bounds'):
        (x0,y0),(x1,y1)=selection['bounds'];return x0,y0,x1,y1
    b=path.bbox(allpaths(marks),fast=False)
    if not b.has_data:raise ValueError('empty drawing selection')
    return b.extmin.x,b.extmin.y,b.extmax.x,b.extmax.y

def scaled_marks(marks,bounds,width,height):
    x0,y0,x1,y1=bounds
    # The source panel can approximate the outline. Keep arrows, symbols and
    # type at the same relative proportions when fitting its physical envelope.
    scale=min(width/(x1-x0),height/(y1-y0))
    mx=Matrix44.chain(Matrix44.translate(-(x0+x1)/2,-(y0+y1)/2,0),Matrix44.scale(scale,scale,1))
    answer=[]
    for m in marks:
        paths=[p.transform(mx) for p in m.paths]
        near=[]
        for p in paths:
            if not len(p):continue
            bounds=path.bbox([p],fast=True)
            if bounds.extmax.x<-.52*width or bounds.extmin.x>.52*width or bounds.extmax.y<-.52*height or bounds.extmin.y>.52*height:continue
            near.append(p)
        if near:answer.append(Mark(near,m.fill,m.white,m.kind))
    return answer

def write_geometry(block, marks,width,height,solid_symbol=True,ink_extent=None,join_dangling=False):
    """Keep true source curves. Add compound hatches to outline-only symbols and borders."""
    tol=max(width,height)/6000
    attrs={'layer':'0','color':7}
    contour=[]
    linework=[]
    def emit_shell(outer,holes,white):
        obj=block.add_hatch(color=7,dxfattribs=attrs)
        if white:obj.rgb=(255,255,255)
        for pp,flag in [(outer,1)]+[(h,0) for h in holes]:
            pp.close()
            build_edge_path(obj.paths,pp,flag,tol,6,1.e-4)

    def hatch(paths,white=False,known_shell=False):
        rings=list(path.single_paths(paths))
        if not rings:return
        if known_shell or len(rings)==1:
            emit_shell(rings[0],rings[1:],white)
            return
        pairs=[(pp,polygon(pp,tol)) for pp in rings]
        pairs=sorted(((pp,g) for pp,g in pairs if g is not None),key=lambda x:-x[1].area)
        parents=[];depths=[]
        for i,(pp,g) in enumerate(pairs):
            parent=next((j for j in range(i-1,-1,-1) if pairs[j][1].covers(g)),None)
            parents.append(parent)
            depths.append(0 if parent is None else depths[parent]+1)
        for i,(pp,g) in enumerate(pairs):
            if depths[i]%2==0:
                holes=[pairs[j][0] for j in range(i+1,len(pairs)) if parents[j]==i]
                emit_shell(pp,holes,white)

    if not solid_symbol:
        for m in marks:
            if m.fill and not m.white:hatch(m.paths,known_shell=m.kind=='TRACE-SHELL')
        return
    # Detect a substrate drawn with solids before resolving text and contour color.
    # Source lettering may sit on white panel stock or inside a dark filled field.
    def filled_polygon(paths):
        parts=[]
        for pp in paths:
            for p in pp.sub_paths():
                g=polygon(p,tol)
                if g is not None:parts.append(g)
        geo=GeometryCollection()
        for g in parts:geo=geo.symmetric_difference(g)
        return geo
    fills=[(m,filled_polygon(m.paths)) for m in marks if m.fill]
    solid_interior=unary_union([g for m,g in fills if not m.white and m.kind not in {'TEXT','MTEXT','ATTDEF','ATTRIB'}])
    texts=[g for m,g in fills if m.kind in {'TEXT','MTEXT','ATTDEF','ATTRIB'} and g.area]
    negative=[];over=[]
    for m,g in fills:
        if g.is_empty:continue
        cut=(m.kind in {'TEXT','MTEXT','ATTDEF','ATTRIB'} and
             not solid_interior.is_empty and solid_interior.covers(g.representative_point()))
        if (m.white and g.area<width*height*.75) or cut:negative.append(g)
        else:over.append((m,g))
    cutouts=unary_union(negative)
    def paint_area(geo):
        if geo.is_empty:return
        if geo.geom_type=='Polygon':
            ringpaths=[vertices_path(r.coords,True) for r in [geo.exterior,*geo.interiors]]
            hatch(ringpaths,known_shell=True);return
        for sub in getattr(geo,'geoms',[]):paint_area(sub)
    for m,g in over:
        if m.white:continue
        if not cutouts.is_empty and g.intersects(cutouts):
            paint_area(g.difference(cutouts))
        else:hatch(m.paths)
    for m in marks:
        if m.fill:continue
        for p in m.paths:
            if not len(p):continue
            if not p.has_curves:
                vertices=list(p.control_vertices())
                if len(vertices)==2:
                    block.add_line(vertices[0],vertices[1],dxfattribs=attrs)
                else:block.add_lwpolyline([(v.x,v.y) for v in vertices],close=p.is_closed,dxfattribs=attrs)
            else:
                path.render_splines_and_polylines(block,[p],dxfattribs=attrs)
            if solid_symbol and not m.white:
                xy=[(round(v.x/tol)*tol,round(v.y/tol)*tol) for v in p.flattening(tol,segments=6)]
                if len(xy)>1 and xy[0]!=xy[-1] and len(set(xy))>1:
                    linework.append(LineString(xy))
            if p.is_closed and not m.white and solid_symbol:
                g=polygon(p,tol)
                if g is not None:contour.append((p,g))
    # A reverse-color panel already has explicit ink and knockouts. Keep its
    # unpainted symbols open, including white diamonds and ONE WAY arrows.
    if solid_interior.area>width*height*.38:return
    if solid_symbol and linework:
        endpoints=[p for line in linework for p in (line.coords[0],line.coords[-1])]
        endpoint_tree=cKDTree(endpoints)
        snap=max(width,height)/1800 if not join_dangling else max(width,height)*.0015
        targets=[]
        for i,endpoint in enumerate(endpoints):
            neighbours=endpoint_tree.query_ball_point(endpoint,snap)
            targets.append(min(endpoints[n] for n in neighbours))
        if join_dangling:
            from collections import Counter
            multiplicity=Counter(targets)
            dangling=[i for i,p in enumerate(targets) if multiplicity[p]==1]
            if len(dangling)>1:
                tree=cKDTree([targets[i] for i in dangling])
                distances,indices=tree.query([targets[i] for i in dangling],k=2)
                for i,(_,j) in enumerate(indices):
                    if i>=j or indices[j][1]!=i or distances[i][1]>max(width,height)*.045:continue
                    a,b=dangling[i],dangling[j]
                    targets[b]=targets[a]
        snapped=[]
        for i,line in enumerate(linework):
            coords=list(line.coords)
            coords[0],coords[-1]=targets[i*2],targets[i*2+1]
            if len(set(coords))>1:snapped.append(LineString(coords))
        for face in polygonize(unary_union(snapped)):
            if face.area>tol*tol:
                # Exploded CAD lettering and arrows often consist entirely of
                # individual lines and arcs with shared endpoints.
                for ring in [face.exterior, *face.interiors]:
                    g=Polygon(ring)
                    if g.area>tol*tol:contour.append((vertices_path(ring.coords,True),g))
    if not solid_symbol or not contour:return
    # The face substrate must stay open. Concentric outer contours form an inked
    # border; a single outer contour is the panel perimeter only. All other closed
    # paths retain their nested counters, e.g. an arrow, wheel or letter O.
    frame=[];interior=[]
    for p,g in contour:
        x0,y0,x1,y1=g.bounds
        is_frame=(x1-x0)>.81*width and (y1-y0)>.81*height and abs(x1+x0)<.16*width and abs(y1+y0)<.16*height
        (frame if is_frame else interior).append((p,g))
    # Signs composed of several panels use another physical perimeter for each
    # panel. Prevent a plaque or sign assembly's rectangular substrate becoming ink.
    if frame:
        frame.sort(key=lambda q:-q[1].area)
        outer,outer_g=frame[0]
        inner=next(((p,g) for p,g in reversed(frame[1:]) if .74<g.area/outer_g.area<.997 and outer_g.buffer(tol).covers(g)),None)
        if inner:hatch([outer,inner[0]])
    seen=[];ink=[]
    for p,g in sorted(interior,key=lambda row:-row[1].area):
        if any(g.equals_exact(h,tol) or g.symmetric_difference(h).area<max(g.area,h.area)*.004 for h in seen if abs(h.area-g.area)/g.area<.08):continue
        seen.append(g)
        x0,y0,x1,y1=g.bounds
        # A field-sized background or a panel in a stack is not a dark symbol.
        if ink_extent and (g.centroid.y/height+.5)<ink_extent:continue
        if g.area>width*height*.58 or ((x1-x0)>.83*width and g.area/((x1-x0)*(y1-y0))>.79):continue
        if not solid_interior.is_empty and solid_interior.intersection(g).area>g.area*.62:continue
        if any(g.covers(t.representative_point()) for t in texts):continue
        ink.append(p)
    if ink:hatch(ink)
