"""Compare decoded sign DWGs with their CAD source artwork and independently issued sign faces.

Run from a workspace containing the repository, decoded originals, approved face
selections, size/face authority crosswalk, and the packaged and reopened DWGs.
Only independently signed-off visual inspections receive a human review status.
Rerenders changed DWG checksums and caches source/agency previews between runs.
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from pathlib import Path

import ezdxf
import fitz
import numpy as np
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf
from ezdxf.fonts import fonts
from ezdxf.math import BoundingBox2d
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


def key(value):
    value = value.upper().translate(str.maketrans("–—‑−","----"))
    value = re.sub(r"\(([^()]*)\)", lambda m:"CA" if m[1].strip()=="CA" else "-"+m[1].strip().replace(" ","-"),value)
    value = re.sub(r"[\s-]*\bMOD(?:IFIED)?\b[\s-]*","-MOD-",value)
    value = re.sub(r"(?<=[0-9A-Z])MOD(?=$|[ -])","-MOD",value)
    value = re.sub(r"-(LT|RT)(?=-|$)",lambda m:"-LEFT" if m[1]=="LT" else "-RIGHT",value)
    if re.fullmatch(r"(?:[A-Z]\.)+[A-Z]\.?",value):
        value = value.replace(".","")
    return re.sub(r"\s","",value).strip("-")


def render(doc, ctx, entities, box=None):
    backend = pymupdf.PyMuPdfBackend()
    conf = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.COLOR, lineweight_policy=config.LineweightPolicy.RELATIVE)
    frontend = Frontend(ctx,backend,config=conf)
    frontend.set_background("#ffffff")
    frontend.draw_entities(entities)
    frontend.pipeline.finalize()
    bounds = BoundingBox2d([(box[0],box[1]),(box[2],box[3])]) if box else backend.player().bbox()
    w,h = bounds.size
    if w <= 0 or h <= 0:
        raise ValueError("No drawable sign face")
    page = layout.Page(80*w/max(w,h)+3,80*h/max(w,h)+3,margins=layout.Margins.all(1.5))
    settings=layout.Settings(output_coordinate_space=100000,output_layers=False,max_stroke_width=.004,min_stroke_width=.09)
    img=backend.get_pixmap_bytes(page,fmt="png",dpi=100,alpha=False,settings=settings,render_box=bounds)
    return Image.open(BytesIO(img)).convert("RGB")


def context(doc):
    ctx=RenderContext(doc)
    for layer in ctx.layers.values():
        layer.is_visible=True
    # The uploaded plans require Arial Narrow. Match its narrow metrics if unavailable.
    for style in doc.styles:
        face=style.dxf.font.lower()
        if face not in ("arialn.ttf","arialnb.ttf") or fonts.font_manager.has_font(face):continue
        substitute="LiberationSansNarrow-"+("Bold" if face=="arialnb.ttf" else "Regular")+".ttf"
        if fonts.font_manager.has_font(substitute):
            ctx.fonts[style.dxf.name.lower()]=fonts.font_manager.get_font_face(substitute)
    return ctx


def image_file(path):
    if path.suffix.lower()==".svg":
        doc=fitz.open(stream=path.read_bytes(), filetype="svg")
        page=doc[0]
        factor=340/max(page.rect.width,page.rect.height)
        return Image.open(BytesIO(page.get_pixmap(matrix=fitz.Matrix(factor,factor),alpha=False).tobytes("png"))).convert("RGB")
    return Image.open(path).convert("RGB")

def publisher_preview(public,out):
    # The site may correct a crop at a stable URL. Cache the actual artwork bytes.
    stamp=hashlib.sha256(public.read_bytes()).hexdigest()[:20]
    target=out/(stamp+".png")
    if not target.is_file():
        image_file(public).save(target)
    return target

def source_batch(args):
    drawing,rows,workspace,site,out=args
    doc=None
    results={}
    for record in rows:
        face_id=record["id"]
        img_path=record.get("sourceImage") or record.get("image")
        if record.get("sourceKind") in ("source region","embedded bitmap"):
            img_path=record.get("mask") or img_path
        if record.get("sourceKind")=="reconciled source variant":
            img_path=None  # Original caption 25, original drawn number 30.
        elif record.get("drawing")=="official-standard" and record.get("outlineMask"):
            img_path=record.get("outlineMask")
        source_data={k:record.get(k) for k in ("entities","block","physicalBounds","sourceImage","image","sourceKind")}
        if not img_path:
            source_data["plotPens"]="legible-on-white-v1"
        if img_path:
            p=Path(img_path)
            if not p.is_file():
                p=site/"public"/img_path.lstrip("/")
            if p.is_file():
                source_data["artworkSha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
        signature=hashlib.sha256(json.dumps(source_data,sort_keys=True).encode()).hexdigest()[:10]
        path=out/(face_id+"-"+signature+".png")
        if path.exists():
            results[face_id]=str(path)
            continue
        try:
            if img_path:
                im=image_file(p)
            else:
                if doc is None:
                    doc=ezdxf.readfile(workspace/"all-sources"/(drawing+".dxf"))
                    ctx=context(doc)
                if "entities" in record:
                    selected=[doc.entitydb[h] for h in record["entities"]]
                else:
                    selected=list(doc.blocks[record["block"]])
                im=render(doc,ctx,selected,record.get("physicalBounds"))
                # CAD index-color yellow and green were authored for a dark canvas.
                # Darken only saturated light pen pixels for the white comparison page.
                pix=np.asarray(im).copy()
                low=pix.min(2);high=pix.max(2)
                pen=(high.astype(int)-low.astype(int)>46)&(pix.mean(2)>123)&(pix[:,:,1]>190)
                pix[pen]=(pix[pen].astype(float)*.48).astype("uint8")
                im=Image.fromarray(pix)
            im.thumbnail((360,360))
            im.save(path)
            results[face_id]=str(path)
        except Exception as exc:
            results[face_id]={"error":str(exc)[:150]}
    return results


def draw_reopened(args):
    src,output,*native=args
    try:
        if native:
            dwg,expected_sha,decoder=native
            actual=hashlib.sha256(dwg.read_bytes()).hexdigest()
            if actual!=expected_sha:
                raise ValueError("Packaged DWG checksum mismatch")
            if not output.is_file():
                with tempfile.TemporaryDirectory(prefix="cad-review-") as tmp:
                    decoded=Path(tmp)/"independent.dxf"
                    subprocess.run([str(decoder),str(dwg),"-o",str(decoded),"-y"],capture_output=True,check=True,timeout=50)
                    doc=ezdxf.readfile(decoded)
                    render(doc,context(doc),doc.modelspace()).save(output)
        elif not output.is_file():
            doc=ezdxf.readfile(src)
            render(doc,context(doc),doc.modelspace()).save(output)
        return str(output)
    except Exception as exc:
        return {"error":str(exc)[:150]}


def silhouette(im, side=132):
    # Color-to-ink model used only for triage. Preserve the visual design on yellow
    # or orange warning panels; dark, red, green and blue reverse grounds remain ink.
    a=np.asarray(im.convert("RGB"),dtype=float)
    r,g,b=a.transpose(2,0,1)
    dark=(.299*r+.587*g+.114*b)<172
    yellow=(r>160)&(g>120)&(b<np.minimum(r,g)*.69)
    ink=dark&~yellow
    y,x=np.nonzero(ink)
    if not len(y):return np.zeros((side,side),bool),0
    ink=ink[y.min():y.max()+1,x.min():x.max()+1]
    h,w=ink.shape
    size=(max(1,round(w*side/max(w,h))),max(1,round(h*side/max(w,h))))
    small=Image.fromarray(np.uint8(ink)*255).resize(size,Image.Resampling.BILINEAR)
    canvas=Image.new("L",(side,side));canvas.paste(small,((side-size[0])//2,(side-size[1])//2))
    return np.asarray(canvas)>100,w/h


def metrics(left,right):
    a,ar=silhouette(left);b,br=silhouette(right)
    def similarity(x,y):
        if not x.any() or not y.any():return 0.0
        a_close=ndimage.binary_dilation(x,iterations=2)
        b_close=ndimage.binary_dilation(y,iterations=2)
        p=(x&b_close).sum()/x.sum();r=(y&a_close).sum()/y.sum()
        return 2*p*r/(p+r) if p+r else 0
    near=similarity(a,b);mirror=similarity(np.fliplr(a),b)
    return {"alignedInkAgreement":round(near,3),"mirroredInkAgreement":round(mirror,3),
            "inkAreaRatio":round(float(a.sum()/max(1,b.sum())),3),
            "aspectRatioDifference":round(abs(math.log(ar/br)),3) if ar and br else None}


def draw_sheets(records,folder,limit=24):
    # Three image columns per specimen retain every artwork at its original aspect ratio.
    folder.mkdir(exist_ok=True)
    for first in range(0,len(records),limit):
        part=records[first:first+limit];w,h=710,182
        canvas=Image.new("RGB",(w*2,h*math.ceil(len(part)/2)),"#fafafa")
        paint=ImageDraw.Draw(canvas)
        for i,r in enumerate(part):
            x=i%2*w;y=i//2*h;parts=[("Decoded DWG",r["render"]),("Issued face in monochrome" if r["source"]=="official-standard" else "Original drawing",r.get("sourcePreview")),("Publisher source",r.get("referencePreview"))]
            paint.text((x+7,y+4),f'{r["code"]}   /   {r["source"]}   {r["handle"]}',fill="#141414")
            for j,(label,fp) in enumerate(parts):
                dx=x+3+j*232
                if fp and isinstance(fp,str) and Path(fp).is_file():
                    im=Image.open(fp).convert("RGB");im.thumbnail((217,132),Image.Resampling.LANCZOS)
                    canvas.paste(im,(dx+(229-im.width)//2,y+25+(132-im.height)//2))
                paint.text((dx+7,y+160),label if fp else "No matching asset",fill="#555")
            paint.line((x,y+h-1,x+w,y+h-1),fill="#ccc")
        canvas.save(folder/f'{first//limit+1:03d}.jpg',quality=83)
        for r in part:r["contactSheet"]=str(folder/f'{first//limit+1:03d}.jpg')


def read(file):
    return json.loads(file.read_text())


def carry_review(row, check, cache):
    """A re-encoded WBLOCK may retain a reviewed verdict only for identical plotted pixels."""
    if not check or not isinstance(row.get("render"), str):
        return
    old_sha = check.get("sha256", "")
    def apply_review(basis):
        row["visualReview"] = check["verdict"]
        row["visualReviewBasis"] = basis
        if check.get("classification"):
            row.setdefault("automatedTriage",row["status"])
            row["status"] = check["classification"]
            if row["status"]=="publisher artwork visually checked" and not row.get("referenceType"):
                row["status"]="original CAD artwork visually checked"
        elif row["status"]=="source comparison only":
            row["automatedTriage"]=row["status"]
            row["status"]="original CAD artwork visually checked"
    if old_sha == row["dwgSha256"]:
        apply_review("Reviewed native DWG checksum")
        return
    if not re.fullmatch("[a-f0-9]{64}", old_sha):
        return
    prefix = f"{row['id']}-{old_sha[:12]}"
    with Image.open(row["render"]) as image:
        new_pixels = image.convert("RGB")
    for candidate in (cache / f"{prefix}-independent.png", cache / f"{prefix}.png"):
        if candidate.is_file():
            with Image.open(candidate) as image:
                previous_pixels = image.convert("RGB")
            if previous_pixels.size == new_pixels.size and previous_pixels.tobytes() == new_pixels.tobytes():
                apply_review("Decoded drawing pixels exactly match the reviewed sign image")
                row["previouslyReviewedDwgSha256"] = old_sha
                return


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--site",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,action="append",default=[])
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--decoder",type=Path,help="Independently reopen the manifest’s actual DWG bytes with libdxfrw and validate each SHA-256.")
    parser.add_argument("--limit",type=int)
    parser.add_argument("--id",action="append",help="Only compare these exact catalog records.")
    args=parser.parse_args()
    wd=args.workspace.resolve();site=args.site.resolve();out=args.output.resolve();out.mkdir(exist_ok=True,parents=True)
    for directory in ("dwg","source","issued"):
        (out/directory).mkdir(exist_ok=True)
    faces=read(site/"data/reference/plan-examples/cad-sign-art.json")
    for p in sorted((wd/"block-inputs").glob("*.json")):faces+=read(p)
    selections={}
    for face in faces:selections.setdefault(face["id"],{}).update(face)
    callouts_dir=site/"data/reference/cad-standards/callout-faces"
    for filename in ("fhwa-variants.json","historic-faces.json"):
        for face in read(callouts_dir/filename) if (callouts_dir/filename).is_file() else []:
            slug=re.sub("[^a-z0-9-]","-",face["key"].casefold()).strip("-")
            selection=selections.get("official-callout-"+slug)
            if selection is not None:
                selection["publisherPanel"]=str(callouts_dir/face.get("asset",slug+".svg"))
                selection["panelType"]="issued archived sign foil" if face.get("status") else "issued directional sign foil"
    sizes_path=site/"data/reference/plan-examples/verified-publisher-panel-sizes.json"
    if sizes_path.is_file():
        for id,measure in read(sizes_path).items():
            if measure.get("sourceMask") and measure.get("artworkSourceUrl") and id in selections:
                asset=site/measure["sourceMask"]
                if hashlib.sha256(asset.read_bytes()).hexdigest()!=measure["sourceMaskSha256"]:
                    raise ValueError("Publisher source artwork changed: "+id)
                selections[id].update(publisherPanel=str(asset),panelType="issuer-derived plate mask",sourceUrl=measure["artworkSourceUrl"])
    standards=read(wd/"standards/sign-standards.json")["records"]
    manifests=args.manifest or sorted(wd.glob("cad-source-*/manifest.json"))
    artifacts={}
    for p in manifests:
        for row in read(p)["records"]:
            artifacts[row["id"]]=(row,p.parent)
    if args.id:artifacts={id:artifacts[id] for id in args.id}
    if args.limit:artifacts=dict(list(artifacts.items())[:args.limit])
    source_groups=defaultdict(list);queue=[];rows=[]
    for id,(row,pack_path) in sorted(artifacts.items()):
        pack=pack_path.name
        candidate=selections.get(id,{});drawing=row["sourceDrawing"];code=row["code"];sha=row["sha256"]
        src=wd/"block-stage"/pack/(id+".roundtrip.dxf")
        if not src.is_file():
            src=next((f for f in (wd/"block-stage").glob("*/"+id+".roundtrip.dxf") if f.is_file()),src)
        output=out/"dwg"/(id+"-"+sha[:12]+("-independent" if args.decoder else "")+".png")
        job=(src,output,pack_path/row["file"],sha,args.decoder.resolve()) if args.decoder else (src,output)
        queue.append(job)
        if candidate:source_groups[drawing].append(candidate)
        authority=standards.get(key(code),{});ref=authority.get("referenceFace") or {};asset=ref.get("asset")
        # The code must independently resolve at its full sign level, including modifiers.
        # A project spelling alone never licenses an authority match to a parent sign.
        exact=key(code)==key(authority.get("standardCode") or "") and "MOD" not in key(code)
        refpath=None;refurl=None;reference_type=None
        if candidate.get("publisherPanel"):
            refpath=publisher_preview(Path(candidate["publisherPanel"]),out/"issued")
            refurl=candidate["sourceUrl"];reference_type=candidate["panelType"]
        elif candidate.get("referenceURL") and candidate.get("sourceImage"):
            refpath=Path(candidate["sourceImage"]);refurl=candidate["referenceURL"];reference_type="issued corrected legend"
        elif candidate.get("sourceKind")=="current issued sign artwork" and candidate.get("referenceAsset"):
            public=site/"public"/candidate["referenceAsset"].lstrip("/")
            if public.is_file():
                refpath=publisher_preview(public,out/"issued")
                refurl=candidate.get("sourceUrl");reference_type=candidate.get("referenceType")
        elif exact and asset:
            public=site/"public"/asset.lstrip("/")
            if public.is_file():
                refpath=publisher_preview(public,out/"issued")
                refurl=ref.get("source");reference_type=ref.get("type")
        rows.append({"id":id,"code":code,"source":drawing,"sourceKind":row.get("sourceKind"),"handle":row.get("sourceHandle"),"dwgSha256":sha,
                     "reviewMethod":"native DWG checksum and independently decoded libdxfrw rendering" if args.decoder else "packager DWG round-trip DXF rendering",
                     "render":str(output),"referencePreview":str(refpath) if refpath else None,
                     "publisherURL":refurl,"referenceType":reference_type,"geometryStatus":row.get("geometryStatus")})
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        renders=list(pool.map(draw_reopened,queue,chunksize=5))
        lists=list(pool.map(source_batch,[(k,vals,wd,site,out/"source") for k,vals in source_groups.items()]))
    sources={k:v for values in lists for k,v in values.items()}
    for r,rendered in zip(rows,renders):
        r["render"]=rendered;r["sourcePreview"]=sources.get(r["id"])
        if isinstance(rendered,dict):
            r["status"]="DWG render failed";continue
        try:
            final=Image.open(rendered)
            for field in ("sourcePreview","referencePreview"):
                if isinstance(r.get(field),str):
                    r["sourceMetrics" if field=="sourcePreview" else "agencyMetrics"]=metrics(final,Image.open(r[field]))
            comp=r.get("agencyMetrics")
            if comp:
                r["status"]="agency comparison requires visual review"
                if comp["alignedInkAgreement"]<.66 or comp["inkAreaRatio"]<.5 or comp["inkAreaRatio"]>1.9:
                    r["status"]="publisher difference flagged"
                if comp["mirroredInkAgreement"]>comp["alignedInkAgreement"]+.09:
                    r["status"]="possible handedness difference"
                if r["referenceType"]=="source-figure-crop":
                    r["status"]="publisher figure context; face requires identification"
            else:r["status"]="source comparison only" if "sourceMetrics" in r else "no comparable source image"
        except Exception as e:r["status"]="comparison error: "+str(e)[:70]
    reviewed={}
    previous_site_report=site/"public/downloads/sign-blocks-qa/CAD-VISUAL-CHECKS.json"
    if previous_site_report.is_file():
        for previous in read(previous_site_report)["records"]:
            if previous.get("visualReview"):
                checked={"sha256":previous["dwgSha256"],"verdict":previous["visualReview"]}
                if previous.get("automatedTriage"):checked["classification"]=previous["status"]
                reviewed[previous["id"]]=checked
    if (out/"reviewed.json").is_file():reviewed.update(read(out/"reviewed.json"))
    for r in rows:
        carry_review(r, reviewed.get(r["id"]), out/"dwg")
    rows.sort(key=lambda r:(r["status"],r["source"],r["code"],r["id"]))
    draw_sheets(rows,out/"sheets")
    (out/"comparisons.json").write_text(json.dumps(rows,ensure_ascii=False,indent=1)+"\n")
    print("Reopened",len(rows),"artifacts,",dict(Counter(r["status"] for r in rows)),flush=True)

if __name__=="__main__":
    main()
