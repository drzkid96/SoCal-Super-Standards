"""Extract stroked marking outlines from a Caltrans standard plan page, scaled by each figure's 1-ft grid."""
import pymupdf as fitz, sys, json, math, collections, re
def items_pts(dr):
    segs=[]
    for it in dr['items']:
        k=it[0]
        if k=='l': segs.append([(it[1].x,it[1].y),(it[2].x,it[2].y)])
        elif k=='c':
            p0,c1,c2,p3=it[1:5]; pts=[]
            for i in range(9):
                t=i/8; a=(1-t)**3; b=3*(1-t)**2*t; c=3*(1-t)*t*t; e=t**3
                pts.append((a*p0.x+b*c1.x+c*c2.x+e*p3.x, a*p0.y+b*c1.y+c*c2.y+e*p3.y))
            segs.append(pts)
        elif k=='re':
            r=it[1]; segs.append([(r.x0,r.y0),(r.x1,r.y0),(r.x1,r.y1),(r.x0,r.y1),(r.x0,r.y0)])
        elif k=='qu':
            q=it[1]; segs.append([(q.ul.x,q.ul.y),(q.ur.x,q.ur.y),(q.lr.x,q.lr.y),(q.ll.x,q.ll.y),(q.ul.x,q.ul.y)])
    return segs
def chain(segs,tol=0.6):
    segs=[s[:] for s in segs if len(s)>1]; loops=[]
    while segs:
        cur=segs.pop(); changed=True
        while changed:
            changed=False
            for i,s in enumerate(segs):
                d=lambda a,b: math.hypot(a[0]-b[0],a[1]-b[1])
                if d(cur[-1],s[0])<tol: cur+=s[1:]
                elif d(cur[-1],s[-1])<tol: cur+=s[::-1][1:]
                elif d(cur[0],s[-1])<tol: cur=s+cur[1:]
                elif d(cur[0],s[0])<tol: cur=s[::-1]+cur[1:]
                else: continue
                segs.pop(i); changed=True; break
        closed=math.hypot(cur[0][0]-cur[-1][0],cur[0][1]-cur[-1][1])<tol and len(cur)>3
        loops.append((cur,closed))
    return loops
def clusters(drs,tol=1.0):
    boxes=[fitz.Rect(d['rect']) for d in drs]; parent=list(range(len(drs)))
    def f(i):
        while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for i in range(len(boxes)):
        bi=fitz.Rect(boxes[i].x0-tol,boxes[i].y0-tol,boxes[i].x1+tol,boxes[i].y1+tol)
        for j in range(i+1,len(boxes)):
            if bi.intersects(boxes[j]): parent[f(i)]=f(j)
    g=collections.defaultdict(list)
    for i in range(len(drs)): g[f(i)].append(drs[i])
    return list(g.values())
def grid_step(grid_segs, box):
    """Median spacing of the 1-ft grid lines that cross the figure."""
    xs=set(); ys=set()
    for a,b in grid_segs:
        if not (box.x0-2<=max(a[0],b[0]) and min(a[0],b[0])<=box.x1+2 and box.y0-2<=max(a[1],b[1]) and min(a[1],b[1])<=box.y1+2): continue
        if abs(a[0]-b[0])<0.05 and abs(a[1]-b[1])>3: xs.add(round(a[0],2))
        if abs(a[1]-b[1])<0.05 and abs(a[0]-b[0])>3: ys.add(round(a[1],2))
    diffs=[]
    for v in (sorted(xs),sorted(ys)):
        diffs+=[b-a for a,b in zip(v,v[1:]) if b-a>1]
    if not diffs: return None
    diffs.sort(); return diffs[len(diffs)//2]
def rotate(drs, m):
    out=[]
    for x in drs:
        y=dict(x); items=[]
        for it in x['items']:
            k=it[0]
            if k=='re':
                r=it[1]; q=fitz.Quad(r.tl,r.tr,r.bl,r.br)*m; items.append(('qu',q))
            elif k=='qu': items.append(('qu',it[1]*m))
            else: items.append((k,)+tuple(pt*m for pt in it[1:] if isinstance(pt,fitz.Point)))
        y['items']=items; y['rect']=fitz.Rect(x['rect'])*m; out.append(y)
    return out
def run(pdf, page_no, outline_widths, grid_width=0.12):
    d=fitz.open(pdf); p=d[page_no]; p.set_rotation(0); drs=p.get_drawings()
    grid=[(seg[i],seg[i+1]) for x in drs if round(x.get('width') or 0,2)==grid_width for seg in items_pts(x) for i in range(len(seg)-1)]
    outl=[x for x in drs if round(x.get('width') or 0,2) in outline_widths]
    words=p.get_text('words')
    out=[]
    for cl in clusters(outl):
        box=fitz.Rect(cl[0]['rect'])
        for x in cl[1:]: box|=fitz.Rect(x['rect'])
        if box.width<4 or box.height<4: continue
        step=grid_step(grid, box)
        # label: the rotated caption runs beside the figure, toward smaller x
        near=[w for w in words if box.x0-45<w[0]<box.x0+4 and w[1]<box.y1+20 and w[3]>box.y0-20]
        cols=collections.defaultdict(list)
        for w in near: cols[round(w[0])].append(w)
        label=''
        for x in sorted(cols, reverse=True):
            t=' '.join(w[4] for w in sorted(cols[x],key=lambda w:-w[1]))
            if re.search(r'ARROW|MARKING|SYMBOL|STOP|XING|CROSSING|ONLY|LANE|YIELD|BIKE|SCHOOL|AHEAD|PED|SIGNAL|KEEP|CLEAR|BUS|TYPE',t,re.I): label=t; break
        segs=[s for x in cl for s in items_pts(x)]
        out.append(dict(box=list(box),step=step,label=label,loops=[(l,c) for l,c in chain(segs)]))
    return out
if __name__=='__main__':
    res=run(sys.argv[1],int(sys.argv[2]),{float(w) for w in sys.argv[3].split(',')})
    for r in res: print(round(r['box'][0]),round(r['box'][1]),'step',r['step'],'loops',len(r['loops']),sum(c for _,c in r['loops']),'|',r['label'])
