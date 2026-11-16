"""California-only sign artwork from CA MUTCD 2026 figure pages.

Finds every sign code ending in (CA) printed under a sign on a figure page, skips signs crossed out with the
Caltrans blue X (deleted), clusters the vector artwork directly above each label and exports it as SVG.
Output: public/signs/ca/<slug>.svg and data/signs/ca_extra.json
Usage: python3 -I pipeline/extract_ca_signs.py CA_MUTCD.pdf
"""
import json, os, re, sys
import pymupdf

SRC = sys.argv[1]
src = pymupdf.open(SRC)
OUT = "public/signs/ca"
os.makedirs(OUT, exist_ok=True)
CODE = re.compile(r"^((?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d{1,3}[A-Z]?(?:-\d{1,3}[A-Za-z]{0,3})?\(CA\))$")
secs = json.load(open("data/ca-mutcd/sections.json"))
figs = json.load(open("data/ca-mutcd/figures.json"))
fig_by_page = {}
for f in figs:
    fig_by_page.setdefault(f["page"] - 1, f)


def slug(code):
    return re.sub(r"[^a-z0-9\-]", "", code.lower().replace("(", "").replace(")", ""))


def name_for(code):
    pat = re.escape(code)
    for s in secs:
        if re.search(pat, s["title"]):
            t = re.sub(r"\s*\(.*$", "", s["title"]).strip()
            return t, s
    return "", None


def crossed_boxes(pg):
    blue = [d for d in pg.get_drawings() if d.get("color") and d["color"][2] > 0.8 and d["color"][0] < 0.3
            and d["color"][1] < 0.3 and d["type"] == "s" and len(d["items"]) == 1 and d["items"][0][0] == "l"]
    boxes = {}
    for d in blue:
        k = tuple(round(v) for v in d["rect"])
        boxes[k] = boxes.get(k, 0) + 1
    return [pymupdf.Rect(k) for k, n in boxes.items() if n >= 2 and k[2] - k[0] > 15 and k[3] - k[1] > 15]


out, seen, deleted = [], set(), set()
for pno in range(54, len(src)):
    pg = src[pno]
    top = " ".join(w[4] for w in pg.get_text("words") if w[1] < 95)
    if "Figure" not in top and len(pg.get_drawings()) < 60:
        continue
    words = pg.get_text("words")
    labels = []
    for w in words:
        m = CODE.match(w[4].strip(",;"))
        if m:
            labels.append((m.group(1), pymupdf.Rect(w[:4])))
    if not labels:
        continue
    head = pg.get_text()[:600]
    if "Figure" not in pg.get_text():
        continue
    W, H = pg.rect.width, pg.rect.height
    xs = crossed_boxes(pg)
    label_rects = [r for _, r in labels]
    drs = [pymupdf.Rect(d["rect"]) for d in pg.get_drawings() if d["rect"].width < W * 0.6 and d["rect"].height < H * 0.5
           and d["rect"].y0 > 45 and d["rect"].y1 < H - 45 and d["rect"].width > 0.3]
    txt = [pymupdf.Rect(w[:4]) for w in words if 45 < w[1] < H - 45 and not CODE.match(w[4].strip(",;"))
           and not any(pymupdf.Rect(w[:4]).intersects(r) for r in label_rects) and not w[4].startswith("Figure")]
    els = drs + txt
    par = list(range(len(els)))

    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    inf = [pymupdf.Rect(r.x0 - 2.5, r.y0 - 2.5, r.x1 + 2.5, r.y1 + 2.5) for r in els]
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            if inf[i].intersects(els[j]):
                par[f(i)] = f(j)
    cl, ndr = {}, {}
    for i, r in enumerate(els):
        k = f(i)
        cl[k] = (cl[k] | r) if k in cl else pymupdf.Rect(r)
        ndr[k] = ndr.get(k, 0) + (1 if i < len(drs) else 0)
    clusters = [cl[k] for k in cl if ndr[k] >= 2]
    for code, lr in labels:
        if any(x.x0 - 6 <= (lr.x0 + lr.x1) / 2 <= x.x1 + 6 and -6 <= lr.y0 - x.y1 <= 22 for x in xs):
            deleted.add(code)
            continue
        if code in seen:
            continue
        cx = (lr.x0 + lr.x1) / 2
        cand = [c for c in clusters if c.y1 <= lr.y0 + 3 and c.y1 >= lr.y0 - 30 and c.x0 - 8 <= cx <= c.x1 + 8 and c.width < 260 and c.height < 300
                and c.width > 8 and c.height > 8]
        if not cand:
            continue
        c = max(cand, key=lambda r: (r.y1, -abs((r.x0 + r.x1) / 2 - cx)))
        bb = pymupdf.Rect(c.x0 - 1.5, c.y0 - 1.5, c.x1 + 1.5, c.y1 + 1.5)
        sl = slug(code)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(4, 4), clip=bb, alpha=False)
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        im.thumbnail((700, 700))
        im.save(f"{OUT}/{sl}.webp", "WEBP", quality=88, method=5)
        toks = []
        for w in sorted([w for w in words if bb.contains(pymupdf.Rect(w[:4]))], key=lambda w: (round(w[1] / 3), w[0])):
            if toks and (w[4] == toks[-1] or toks[-1].startswith(w[4]) or w[4].startswith(toks[-1])):
                if len(w[4]) > len(toks[-1]):
                    toks[-1] = w[4]
                continue
            toks.append(w[4])
        legend = " ".join(toks)
        name, sec = name_for(code)
        fig = fig_by_page.get(pno)
        mt = re.search(r"Figure\s+(\d[A-Z]-\d+(?:\(CA\))?)", top)
        if mt:
            fig = {"id": mt.group(1)}
        p = re.match(r"[A-Z]+", code).group(0)
        cat = {"R": "Regulatory Signs", "SR": "Regulatory Signs", "W": "Warning Signs and Object Markers", "SW": "Warning Signs and Object Markers",
               "OM": "Warning Signs and Object Markers", "S": "School Signs", "CW": "Temporary Traffic Control Signs", "C": "Temporary Traffic Control Signs"}.get(p, "Guide Signs")
        if fig and fig["id"].startswith("6"):
            cat = "Temporary Traffic Control Signs"
        if fig and fig["id"].startswith("7") and cat != "Temporary Traffic Control Signs":
            cat = "School Signs"
        out.append({"code": code, "name": name or (legend.title()[:60] if legend else ""), "category": cat, "page_label": "", "pdf_page": pno + 1,
                    "colors": "", "caption": legend, "legend_ocr": legend, "dims": [], "svg": f"/signs/ca/{sl}.webp",
                    "aspect": round(bb.width / max(1, bb.height), 3), "source": f"CA MUTCD 2026, Figure {fig['id']}" if fig else f"CA MUTCD 2026, page {pno + 1}",
                    "ca_only": True, "section": sec["num"] if sec else ""})
        seen.add(code)
json.dump(out, open("data/signs/ca_extra.json", "w"), indent=1)
print("CA signs", len(out), "deleted (crossed out)", len(deleted - seen))
