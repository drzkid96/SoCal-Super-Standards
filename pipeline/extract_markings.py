"""Crop individual marking details from CA MUTCD 2026 figure pages.
Type A: Caltrans longitudinal striping details (DETAIL n / OPTION n) on Figures 3A-101(CA) to 3A-113(CA).
Type B: captioned symbols (arrows, words, symbols, bike markings) on Part 3 and Part 9 figure pages.
Output: public/markings/<id>.webp (3x) and data/markings/items.json
"""
import json, os, re, sys
import pymupdf
from PIL import Image
import io
SRC = sys.argv[1]
d = pymupdf.open(SRC)
os.makedirs("public/markings", exist_ok=True)
os.makedirs("data/markings", exist_ok=True)
items = []
def fig_title(pg):
    LL = lines(pg)
    first = [l for l in LL if l["t"].startswith("Figure ") and l["bb"].y0 < 80]
    if first:
        f0 = first[0]
        top = [f0] + [l for l in LL if l is not f0 and l["font"] == f0["font"] and 0 < l["bb"].y0 - f0["bb"].y0 < 30]
        t = " ".join(l["t"] for l in top)
    else:
        t = pg.get_text()
    m = re.search(r"Figure (\d[A-Z]-\d+(?:\(CA\))?)\.\s*(.+?)(?:\n|$)", t)
    return (m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()) if m else ("", "")
def lines(pg):
    out = []
    for bi, b in enumerate(pg.get_text("dict")["blocks"]):
        first = "".join(s["text"] for s in b["lines"][0]["spans"]).strip() if b.get("lines") else ""
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                s0 = l["spans"][0]
                out.append({"t": t, "bb": pymupdf.Rect(l["bbox"]), "size": s0["size"], "font": s0["font"], "color": s0["color"], "note": first.startswith(("Note", "*", "\u2605")) or len(first) > 60})
    return out
def save(pg, rect, name, zoom=3.0):
    rect = rect & pg.rect
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect)
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    im.save(f"public/markings/{name}.webp", "WEBP", quality=82, method=5)
    return f"/markings/{name}.webp", im.size

# ---------- Type A
for pno in range(850, 865):
    pg = d[pno]
    fid, ftitle = fig_title(pg)
    L = lines(pg)
    labels = [l for l in L if re.match(r"^(DETAIL|OPTION) \d+[A-Z]?( - .+)?$", l["t"]) and "Italic" in l["font"]]
    bars = [l for l in L if l["color"] == 0xFFFFFF or (l["t"].isupper() and "Bold" in l["font"] and l["t"] not in ("POLICY", "LEGEND") and not l["t"].startswith(("DETAIL", "OPTION", "NOT TO")) and len(l["t"]) > 10)]
    stops = sorted([l["bb"].y0 for l in labels + bars] + [l["bb"].y0 for l in L if l["t"] in ("NOT TO SCALE", "LEGEND")] + [pg.rect.height - 40])
    reg = [l["bb"].x0 for l in L if "Bold" not in l["font"] and l["bb"].x0 > 280 and l["size"] >= 8.8 and not re.search(r"\d+ (ft|in)", l["t"])]
    policy_x = (min(reg) - 6) if reg else pg.rect.width * 0.55
    for lab in sorted(labels, key=lambda l: l["bb"].y0):
        y0 = lab["bb"].y0 - 3
        y1 = min(s for s in stops if s > lab["bb"].y0 + 2) - 2
        group = ""
        for b in sorted(bars, key=lambda b: b["bb"].y0):
            if b["bb"].y0 < lab["bb"].y0:
                group = b["t"]
        wide = " - " in lab["t"]
        x1 = pg.rect.width - 30 if wide else policy_x
        if wide:
            desc = " ".join(l["t"] for l in L if y0 + 14 < l["bb"].y0 < y1 and "Bold" not in l["font"] and not re.search(r"^\d+(\.\d+)? ?(ft|in)|^See Detail", l["t"]) and len(l["t"]) > 25)
        else:
            desc = " ".join(l["t"] for l in L if l["bb"].x0 >= policy_x and y0 <= l["bb"].y0 < y1 and l["t"] != "POLICY")
        num, _, sub = lab["t"].partition(" - ")
        num = num.title()
        key = re.sub(r"\W+", "-", f"ca-{fid}-{num}".lower()).strip("-")
        if not wide and not desc:
            x1 = pg.rect.width - 20
        img, size = save(pg, pymupdf.Rect(12, y0, x1, y1), key)
        items.append({"id": key, "kind": "line", "name": f"Caltrans {num}" if num.startswith("Detail") else f"{fid} {num}",
                      "detail": num, "group": group, "subtitle": sub, "figure": fid, "figure_title": ftitle, "desc": desc, "page": pno + 1,
                      "img": img, "w": size[0], "h": size[1]})

# ---------- Type B
TYPEB = list(range(925, 942)) + [943, 945, 946, 947, 954, 962, 988, 1651, 1681]
SKIP = re.compile(r"^(NOT TO SCALE|LEGEND|NOTES?:?|POLICY|DIRECTION OF|EDGE OF|1 ft Grid)", re.I)
for pno in TYPEB:
    pg = d[pno]
    fid, ftitle = fig_title(pg)
    L = lines(pg)
    title_bottom = max([l["bb"].y1 for l in L if l["t"].startswith("Figure ")] or [40])
    caps = [l for l in L if "Bold" in l["font"] and l["bb"].y0 > title_bottom + 5 and not SKIP.match(l["t"]) and 8.5 <= l["size"] <= 12.5
            and not l["t"].startswith("Figure") and re.search(r"[A-Z]{2,}", l["t"])]
    # merge caption lines into blocks (stacked, overlapping x)
    blocks = []
    for c in sorted(caps, key=lambda c: (c["bb"].y0, c["bb"].x0)):
        for b in blocks:
            if -8 <= c["bb"].y0 - b["bb"].y1 < 6 and not (c["bb"].x1 < b["bb"].x0 or c["bb"].x0 > b["bb"].x1):
                b["t"] += " " + c["t"]; b["bb"] |= c["bb"]; break
        else:
            blocks.append({"t": c["t"], "bb": pymupdf.Rect(c["bb"])})
    # sub-caption regular lines chained directly below a block
    used = set()
    for b in blocks:
        while True:
            nxt = [l for l in L if "Bold" not in l["font"] and id(l) not in used and -6 <= l["bb"].y0 - b["bb"].y1 < 5 and l["bb"].y0 > b["bb"].y0 + 4
                   and abs((l["bb"].x0 + l["bb"].x1) / 2 - (b["bb"].x0 + b["bb"].x1) / 2) < 60]
            if not nxt:
                break
            for l in nxt:
                used.add(id(l))
                b["sub"] = (b.get("sub", "") + " " + l["t"]).strip(); b["bb"] |= l["bb"]
    W = pg.rect.width
    if not blocks or len(blocks) == 1:
        dr = [pymupdf.Rect(x["rect"]) for x in pg.get_drawings() if x["rect"].y0 > title_bottom and x["rect"].width < W * 0.95]
        tx = [l["bb"] for l in L if l["bb"].y0 > title_bottom and not l["t"].startswith(("California MUTCD", "Page ", "December", "2026 Edition"))]
        allr = dr + tx
        if not allr:
            continue
        bb = pymupdf.Rect(allr[0])
        for r in allr:
            bb |= r
        bb = pymupdf.Rect(bb.x0 - 4, bb.y0 - 4, bb.x1 + 4, min(bb.y1 + 4, pg.rect.height - 50))
        key = re.sub(r"\W+", "-", f"ca-{fid}-p{pno + 1}".lower()).strip("-")
        img, size = save(pg, bb, key, zoom=2.2)
        items.append({"id": key, "kind": "figure", "name": ftitle, "figure": fid, "figure_title": ftitle, "page": pno + 1, "img": img, "w": size[0], "h": size[1]})
        continue
    drawings = [pymupdf.Rect(x["rect"]) for x in pg.get_drawings() if x["rect"].width < W * 0.95 and x["rect"].y0 > title_bottom]
    capset = set(id(c) for c in caps)
    legend_y = min([l["bb"].y0 for l in L if l["t"] in ("LEGEND", "NOT TO SCALE") or l["t"].startswith("Note")] + [pg.rect.height - 50])
    els = [r for r in drawings if r.y1 < legend_y] + [l["bb"] for l in L if id(l) not in capset and not l["note"] and l["t"] not in ("NOT TO SCALE",) and title_bottom < l["bb"].y0 < legend_y and not any(l["bb"].intersects(bk["bb"]) for bk in blocks)]
    # union-find clustering of elements
    par = list(range(len(els)))
    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    inf = [pymupdf.Rect(r.x0 - 5, r.y0 - 5, r.x1 + 5, r.y1 + 5) for r in els]
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            if inf[i].intersects(els[j]):
                par[f(i)] = f(j)
    cl = {}
    for i, r in enumerate(els):
        k = f(i)
        cl[k] = (cl[k] | r) if k in cl else pymupdf.Rect(r)
    clusters = list(cl.values())
    for b in blocks:
        cx = (b["bb"].x0 + b["bb"].x1) / 2
        same_row = [o for o in blocks if o is not b and abs(o["bb"].y1 - b["bb"].y1) < 200]
        left = max([(cx + (o["bb"].x0 + o["bb"].x1) / 2) / 2 for o in same_row if (o["bb"].x0 + o["bb"].x1) / 2 < cx] or [20])
        right = min([(cx + (o["bb"].x0 + o["bb"].x1) / 2) / 2 for o in same_row if (o["bb"].x0 + o["bb"].x1) / 2 > cx] or [W - 20])
        above = [o["bb"].y1 for o in blocks if o["bb"].y1 < b["bb"].y0 - 10 and not (o["bb"].x1 < left or o["bb"].x0 > right)]
        top = max(above + [title_bottom + 4])
        region = pymupdf.Rect(left, top, right, b["bb"].y1 + 2)
        def frac_in(c):
            inter = c & region
            return 0 if inter.is_empty else inter.get_area() / max(1, c.get_area())
        sel = [c for c in clusters if frac_in(c) > 0.5]
        inside = [c & region for c in clusters if 0 < frac_in(c) <= 0.5]
        if not sel and not inside:
            continue
        bb = pymupdf.Rect(b["bb"])
        for c in sel + inside:
            bb |= c
        bb = pymupdf.Rect(bb.x0 - 4, bb.y0 - 4, bb.x1 + 4, bb.y1 + 4)
        if bb.width < 40 or bb.height < 40:
            continue
        name = re.sub(r"\s+", " ", b["t"]).strip()
        if re.match(r"^OPTION [A-Z]$", name):
            continue
        key = re.sub(r"\W+", "-", f"ca-{fid}-{name}".lower()).strip("-")[:90]
        if any(i["id"] == key for i in items):
            key += f"-p{pno + 1}"
        img, size = save(pg, bb, key)
        items.append({"id": key, "kind": "symbol", "name": name.title() if name.isupper() else name, "sub": b.get("sub", ""),
                      "figure": fid, "figure_title": ftitle, "page": pno + 1, "img": img, "w": size[0], "h": size[1]})
json.dump(items, open("data/markings/items.json", "w"), indent=0)
from collections import Counter
print(len(items), Counter(i["kind"] for i in items))
