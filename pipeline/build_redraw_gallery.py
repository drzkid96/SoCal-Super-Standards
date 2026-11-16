"""Gallery of redrawn MPP standard drawings (consistent detail style), with PNG thumbnails."""
import json, os, re, subprocess, html
BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
dp = {(a, k): u for a, k, t, u in json.load(open("data/docs/drawing_pages.json"))}
secs = []
for slug, short in (("mpp-531", "MPP 531"), ("mpp-521", "MPP 521")):
    p = f"data/docs/redraw_{slug}.json"
    if not os.path.exists(p):
        continue
    recs = json.load(open(p))
    os.makedirs(f"public/thumbs/redraw/{slug}", exist_ok=True)
    by = {}
    for r in recs:
        by.setdefault(r["drawing"], []).append(r)
        src = "public" + r["svg"].replace(BASE, "")
        th = src.replace("public/redraw/", "public/thumbs/redraw/").replace(".svg", ".png")
        if not os.path.exists(th) or os.path.getmtime(th) < os.path.getmtime(src):
            subprocess.run(["rsvg-convert", "-w", "420", src, "-o", th], capture_output=True)
            if os.path.exists(th):
                from PIL import Image
                Image.open(th).convert("RGB").save(th.replace(".png", ".webp"), "WEBP", quality=72)
                os.remove(th)
        r["thumb"] = th.replace("public", BASE).replace(".png", ".webp")
    key = lambda k: [int(x) for x in re.findall(r"\d+", k)]
    cards = []
    for k in sorted(by, key=key):
        rs = sorted(by[k], key=lambda r: r["sheet"])
        page = dp.get((short, k), "")
        cards.append(f'<div class="rdg"><div class="rdg-h"><b>{esc(k)}</b> {esc(rs[0]["title"])} <span class="muted">{len(rs)} sheet(s)</span>'
                     + (f' <a href="{page}">drawing page</a>' if page else "") + '</div><div class="rdg-s">'
                     + "".join(f'<a href="{r["svg"]}" target="_blank" title="Sheet {r["sheet"]}"><img loading="lazy" src="{r["thumb"]}" alt="{esc(k)} sheet {r["sheet"]}"><span>Sheet {r["sheet"]}{" &middot; traced" if r["kind"] == "scan" else ""}</span></a>' for r in rs)
                     + "</div></div>")
    secs.append(f"## LADOT {short}\n\n<div class=\"rdgl\">{''.join(cards)}</div>\n")
open("src/content/docs/ladot/mpp-details.md", "w").write(f'''---
title: MPP standard drawings, redrawn
description: Every LADOT MPP 531 and MPP 521 standard drawing sheet redrawn in one consistent detail style, with a uniform frame and title block. Linked to the originals.
tableOfContents: false
---

<div class="srcbar">Each sheet is set on the same 11 x 8.5 frame with the same palette, line weights, Albert Sans lettering and title block, and the original title block and border are removed. Vector sheets are rebuilt from the PDF geometry. Scanned sheets are cleaned and traced, with the notes re-set from OCR, so check numbers against the original. These are reference redraws, not LADOT-issued drawings.</div>

{"".join(secs)}
''')
print("gallery written")
