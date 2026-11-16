"""Extract clean sign artwork + data from FHWA Standard Highway Signs (2024 Edition) PDFs.

For each sign page (one bookmark per sign code) the filled shapes are replayed onto a new page
sized to the sign, dropping dimension lines (strokes), dimension text and arrowheads. The result
is saved as SVG at a uniform display size later by CSS.

Outputs:
  public/signs/<code>.svg
  data/signs/shs.json   [{code, name, category, page_label, colors, dims, svg, source}]

Usage: python3 -I pipeline/extract_shs.py SHS.pdf REPO_ROOT [SOURCE_LABEL]
"""
import json, os, re, sys
import pymupdf

SRC, ROOT = sys.argv[1], sys.argv[2]
LABEL = sys.argv[3] if len(sys.argv) > 3 else "FHWA Standard Highway Signs, 2024 Edition"
doc = pymupdf.open(SRC)
os.makedirs(f"{ROOT}/public/signs", exist_ok=True)
os.makedirs(f"{ROOT}/data/signs", exist_ok=True)

# ------------------------------------------------------------------ names and categories from the table of contents
toc = doc.get_toc()
code_page = {t[1].strip(): t[2] for t in toc if t[0] == 1 and re.match(r"^[A-Z]{1,3}\d", t[1].strip())}
cat_ranges = [(t[1], t[2]) for t in toc if t[0] == 2]
names, cats = {}, {}
toc_last = min(code_page.values()) - 1 if code_page else 21
current = None
CAT_HEADS = ["Regulatory Signs", "Warning Signs and Object Markers", "Guide Signs", "Temporary Traffic Control Signs",
             "School Signs", "Standard Arrows"]
toc_lines = []
for pno in range(toc_last):
    toc_lines += [l.strip() for l in doc[pno].get_text().splitlines() if l.strip()]
pending = None
for s_ in toc_lines:
    for h in CAT_HEADS:
        if s_.startswith(h):
            current = h
    if re.fullmatch(r"[A-Z]{1,3}\d+[A-Za-z0-9\-]*(?:\s*\(CA\))?", s_):
        pending = s_
        continue
    m = re.match(r"^(?:([A-Z]{1,3}\d+[A-Za-z0-9\-]*)\s+)?(.+?)\s*\.{3,}\s*([0-9A-Z]+-\d+)\s*$", s_)
    if m:
        code = m.group(1) or pending
        if code:
            names.setdefault(code, m.group(2).strip())
            cats.setdefault(code, current)
        pending = None


def replay(src_page, paths, bbox, outline):
    out = pymupdf.open()
    W, H = bbox.width, bbox.height
    pg = out.new_page(width=W, height=H)
    mat = pymupdf.Matrix(1, 1).pretranslate(-bbox.x0, -bbox.y0)
    for p in paths:
        sh = pg.new_shape()
        for it in p["items"]:
            k = it[0]
            if k == "l":
                sh.draw_line(it[1] * mat, it[2] * mat)
            elif k == "c":
                sh.draw_bezier(it[1] * mat, it[2] * mat, it[3] * mat, it[4] * mat)
            elif k == "re":
                sh.draw_rect(it[1] * mat)
            elif k == "qu":
                sh.draw_quad(it[1] * mat)
        is_outline = outline is not None and p is outline
        if p["type"] == "s":
            sh.finish(fill=None, color=p["color"], width=p.get("width") or 1, closePath=p.get("closePath", False))
            sh.commit()
            continue
        sh.finish(fill=p["fill"], color=(0.55, 0.55, 0.55) if is_outline else None,
                  width=0.8 if is_outline else 0, even_odd=p.get("even_odd", False),
                  closePath=p.get("closePath", True), fill_opacity=p.get("fill_opacity") or 1)
        sh.commit()
    return out


def dims_table(page):
    """Return the dimension table as rows of strings (header first), from word positions."""
    try:
        tabs = page.find_tables()
    except Exception:
        return []
    best = None
    for t in tabs.tables:
        r = pymupdf.Rect(t.bbox)
        if best is None or r.width * r.height > best.width * best.height:
            best = r
    if best is None:
        return []
    words = page.get_text("words", clip=best + (-2, -2, 2, 2))
    rows = {}
    for w in words:
        rows.setdefault(round(w[1] / 4), []).append(w)
    out = []
    for k in sorted(rows):
        ws = sorted(rows[k], key=lambda w: w[0])
        # merge tokens that touch (e.g. "0" "." "375")
        cells, last = [], None
        for w in ws:
            if last is not None and w[0] - last[2] < 1.2:
                cells[-1] += w[4]
            else:
                cells.append(w[4])
            last = w
        out.append(cells)
    return out


def colors_text(page):
    t = page.get_text()
    m = re.search(r"COLORS?:\s*(.+?)(?:\n\s*\n|\Z|\n\d+-\d+\s*$)", t, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:400]


signs = []
for code, page in sorted(code_page.items(), key=lambda kv: kv[1]):
    pg = doc[page - 1]
    draws = pg.get_drawings()
    fills = [p for p in draws if p.get("fill") is not None and p["type"] in ("f", "fs")]
    fills = [p for p in fills if p["rect"].width * p["rect"].height > 14 and p["rect"].y1 < 640]
    if not fills:
        continue
    biggest = max(fills, key=lambda p: p["rect"].width * p["rect"].height)
    body = pymupdf.Rect(biggest["rect"]) + (-1.5, -1.5, 1.5, 1.5)

    def junk(p):
        r = p["rect"]
        area = r.width * r.height
        kinds = {it[0] for it in p["items"]}
        if kinds <= {"l"} and len(p["items"]) <= 4 and area < 60:      # dimension arrowheads
            return True
        if area < 5:                                                     # specks
            return True
        if (r.width < 1.3 or r.height < 1.3) and max(r.width, r.height) > 20 and kinds <= {"l", "re"}:  # leader lines drawn as fills
            return True
        return False

    kept = [p for p in fills if body.contains(p["rect"]) and not junk(p)]
    # heavy closed strokes inside the sign (e.g. object-marker reflectors), never thin dimension lines
    kept += [p for p in draws if p["type"] == "s" and (p.get("width") or 0) >= 1.0 and body.contains(p["rect"])
             and p["rect"].width > 4 and p["rect"].height > 4 and p.get("color") is not None]
    kept.sort(key=lambda p: p.get("seqno", 0))
    bbox = pymupdf.Rect(biggest["rect"]) + (-2, -2, 2, 2)
    fill = biggest["fill"]
    outline = biggest if min(fill) > 0.9 else None
    rec = replay(pg, kept, bbox, outline)
    svg = rec[0].get_svg_image(text_as_path=True)
    # official caption printed under the drawing: "<code>" then "<UPPERCASE NAME>"
    caption = ""
    lines = [l.strip() for l in pg.get_text().splitlines() if l.strip()]
    for i, l in enumerate(lines[:-1]):
        if l == code.split(",")[0].strip() and re.match(r"^[A-Z0-9 ,'/&()\-.:]+$", lines[i + 1]) and not lines[i + 1].startswith("COLORS"):
            caption = lines[i + 1]
            break
    # OCR the legend from a clean render
    ocr = ""
    try:
        import subprocess, tempfile
        pix = rec[0].get_pixmap(dpi=200)
        with tempfile.NamedTemporaryFile(suffix=".png") as tf:
            pix.save(tf.name)
            r = subprocess.run(["tesseract", tf.name, "-", "--psm", "11"], capture_output=True, text=True, timeout=30)
            ocr = re.sub(r"[^A-Za-z0-9 $%/\-]", " ", r.stdout)
            ocr = " ".join(w for w in ocr.split() if len(w) > 1 or w.isdigit())
    except Exception:
        pass
    fname = re.sub(r"[^A-Za-z0-9\-]", "_", code)
    with open(f"{ROOT}/public/signs/{fname}.svg", "w") as fh:
        fh.write(svg)
    label = ""
    m = re.search(r"\n\s*(\d+-\d+)\s*\n?\s*$", pg.get_text())
    if m:
        label = m.group(1)
    signs.append({
        "code": code,
        "name": names.get(code, ""),
        "category": cats.get(code) or "",
        "page_label": label,
        "pdf_page": page,
        "colors": colors_text(pg),
        "caption": caption,
        "legend_ocr": ocr[:300],
        "dims": dims_table(pg),
        "svg": f"/signs/{fname}.svg",
        "aspect": round(bbox.width / bbox.height, 3),
        "source": LABEL,
    })

out_path = f"{ROOT}/data/signs/shs.json"
existing = []
if os.path.exists(out_path):
    existing = [s for s in json.load(open(out_path)) if s["source"] != LABEL]
json.dump(existing + signs, open(out_path, "w"), indent=1)
print("signs", len(signs), "named", sum(1 for s in signs if s["name"]), "categorized", sum(1 for s in signs if s["category"]))
