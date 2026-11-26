"""Package the portable CAD visual review, keyed to the bytes of each delivered DWG."""
import argparse
import json
from collections import Counter
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image


def comparison_book(sheets, rows, target):
    """Use searchable labels, clickable authority links and deduplicated sign images."""
    doc=fitz.open()
    toc=[]
    cached={}
    pages={path.name:[] for path in sheets}
    for row in rows:
        pages[Path(row["contactSheet"]).name].append(row)
    font=fitz.Font(fontname="cjk")
    for n, group in enumerate(pages.values(),1):
        page=doc.new_page(width=760,height=1160)
        page.insert_font(fontname="QAFont",fontbuffer=font.buffer)
        page.insert_text((10,14),f"Native DWG visual review  /  {n} of {len(pages)}",fontname="QAFont",fontsize=10)
        for i,row in enumerate(group):
            x=8+374*(i%2); y=22+94*(i//2)
            name=f"{row['code']}   /   {row['source']}   {row['handle'] or ''}"
            width=font.text_length(name,fontsize=7)
            page.insert_text((x,y+8),name,fontname="QAFont",fontsize=7*min(1,365/max(1,width)))
            second="Issued face in monochrome" if row["source"]=="official-standard" else "Original drawing"
            panels=[("Reopened DWG","render"),(second,"sourcePreview"),("Publisher source","referencePreview")]
            for j,(label,key) in enumerate(panels):
                left=x+122*j
                asset=row.get(key)
                if isinstance(asset,str):
                    rect=fitz.Rect(left+2,y+12,left+118,y+79)
                    if asset not in cached:
                        with Image.open(asset) as image:
                            thumb=image.convert("RGB");thumb.thumbnail((232,134),Image.Resampling.LANCZOS)
                        data=BytesIO();thumb.save(data,format="JPEG",quality=66,optimize=True)
                        cached[asset]=page.insert_image(rect,stream=data.getvalue())
                    else:
                        page.insert_image(rect,xref=cached[asset])
                else:
                    label="No matching image"
                page.insert_text((left+2,y+87),label,fontname="QAFont",fontsize=5.8,color=(.24,.24,.24))
                if key=="referencePreview" and row.get("publisherURL"):
                    page.insert_link({"kind":fitz.LINK_URI,"from":fitz.Rect(left,y+10,left+120,y+89),"uri":row["publisherURL"]})
            page.draw_line((x,y+91),(x+367,y+91),color=(.82,.82,.82),width=.4)
        if group:toc.append([1,f"{n:02d}   {group[0]['code']} – {group[-1]['code']}",n])
    doc.set_toc(toc)
    doc.set_metadata({"title":"Sign CAD artwork checks","subject":"Reopened native signs, original CAD drawings and publisher sign artwork"})
    doc.subset_fonts()
    doc.save(target,garbage=4,deflate=True)


def portable_review(comparisons, package, output):
    rows=json.loads(comparisons.read_text())
    known={r["id"]:r for r in json.loads(package.read_text())["records"]}
    reviewed={r["id"]:r for r in rows if r["id"] in known and r["dwgSha256"]==known[r["id"]]["sha256"]}
    missing=sorted(set(known)-set(reviewed))
    failures=[r["id"] for r in reviewed.values() if r.get("status")=="DWG render failed" or isinstance(r.get("render"),dict)]
    if failures:
        raise ValueError(f"{len(failures)} DWG render errors: {failures[:6]}")
    if missing:
        raise ValueError(f"{len(missing)} delivered DWGs require current checksum-matched comparisons: {missing[:6]}")
    output.mkdir(parents=True,exist_ok=True)
    sheets=sorted({Path(r["contactSheet"]) for r in reviewed.values()})
    page_for={path.name:i+1 for i,path in enumerate(sheets)}
    records=[]
    for r in reviewed.values():
        record={k:r[k] for k in ("id","code","source","handle","dwgSha256","geometryStatus","reviewMethod","publisherURL","referenceType",
                               "sourceMetrics","agencyMetrics","visualReview","visualReviewBasis","previouslyReviewedDwgSha256","automatedTriage","status") if k in r and r[k] is not None}
        record["comparisonPage"]=page_for[Path(r["contactSheet"]).name]
        record["hasSourcePreview"]=isinstance(r.get("sourcePreview"),str)
        records.append(record)
    retained={"recordCount":len(records),"byStatus":dict(Counter(r["status"] for r in records)),
              "visuallyReviewedCount":sum("visualReview" in r for r in records),
              "hasPublisherImage":sum(bool(r.get("referenceType")) for r in records),
              "hasSourceImage":sum(r["hasSourcePreview"] for r in records),
              "method":"Decoded native DWG compared with available CAD source artwork and independently published sign artwork. Ink alignment, mirror affinity, area and aspect ratio are triage measurements. Comparative images and the originating edition determine legend, validity and handedness. Modified and uncoded local faces can lack an independent published match.",
              "records":records}
    (output/"CAD-VISUAL-CHECKS.json").write_text(json.dumps(retained,ensure_ascii=False,separators=(",",":"))+"\n")
    comparison_book(sheets, reviewed.values(), output/"CAD-SIGN-VISUAL-REVIEW.pdf")
    print({k:retained[k] for k in retained if k not in ("records","method")})

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("comparisons",type=Path);p.add_argument("manifest",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args();portable_review(args.comparisons,args.manifest,args.output)
