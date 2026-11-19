"""Redraw LADOT MPP standard drawing sheets in one consistent SoCal Super Standards detail style.

Vector sheets: every path and text run is re-emitted with a fixed palette, three line weights and Albert Sans text.
CAD sheets with outlined text: paths are restyled the same way (the outlined text stays as linework).
Scanned sheets: cleaned, then traced to vector outlines with OpenCV, with red, yellow and blue ink traced
on their own layers.
Every sheet gets the same frame and title block, and the original title block and border are dropped.

Output: public/redraw/<doc>/<drawing>-s<n>.svg and data/docs/redraw_<doc>.json
Usage: python3 -I pipeline/redraw_mpp.py ladot/mpp-531 [ladot/mpp-521 ...]
"""
import html, io, json, math, os, re, sys
import numpy as np
import cv2
import pymupdf
from PIL import Image

BASE = "/SoCal-Super-Standards"
cfgs = {c["slug"]: c for c in json.load(open("pipeline/config/ladot.json"))}
esc = lambda t: html.escape(str(t), quote=True)
INK = "#1d2420"
PAL = {"yellow": "#e0b000", "red": "#c0392b", "blue": "#1f5fbf", "green": "#2f6b4f", "gray": "#8c8c88", "white": "#ffffff"}
FW, FH = 792, 612  # every redrawn sheet is set on a landscape 11x8.5 frame (points)
TB = 46            # title block height
M = 18             # margin


def color_name(c):
    if c is None:
        return None
    r, g, b = c[:3]
    if max(r, g, b) < 0.35:
        return "ink"
    if min(r, g, b) > 0.93:
        return "white"
    if abs(r - g) < 0.08 and abs(g - b) < 0.08:
        return "gray"
    if r > 0.7 and g > 0.6 and b < 0.4:
        return "yellow"
    if r > 0.6 and g < 0.45 and b < 0.45:
        return "red"
    if b > 0.5 and r < 0.4:
        return "blue"
    if g > 0.45 and r < 0.4 and b < 0.5:
        return "green"
    return "ink"


def col(c):
    n = color_name(c)
    return None if n is None else (INK if n == "ink" else PAL[n])


def qw(w):
    w = w or 0.5
    return 0.35 if w < 0.45 else (0.7 if w < 1.0 else 1.4)


def qsize(s):
    for q in (5.5, 6.5, 7.5, 9, 11, 14):
        if s <= q + 0.6:
            return q
    return 16


def path_d(items, T):
    d = []
    for it in items:
        k = it[0]
        if k == "l":
            a, b = T(it[1]), T(it[2])
            d.append(f"M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}")
        elif k == "c":
            p = [T(x) for x in it[1:5]]
            d.append(f"M{p[0][0]:.1f} {p[0][1]:.1f}C{p[1][0]:.1f} {p[1][1]:.1f} {p[2][0]:.1f} {p[2][1]:.1f} {p[3][0]:.1f} {p[3][1]:.1f}")
        elif k == "re":
            r = it[1]
            a, b = T((r.x0, r.y0)), T((r.x1, r.y1))
            d.append(f"M{a[0]:.1f} {a[1]:.1f}H{b[0]:.1f}V{b[1]:.1f}H{a[0]:.1f}Z")
        elif k == "qu":
            q = it[1]
            pts = [T((p.x, p.y)) for p in (q.ul, q.ur, q.lr, q.ll)]
            d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z")
    return "".join(d)


def frame_and_tb(meta):
    t = meta
    y0 = FH - M / 2 - TB
    title = t["title"].upper()
    l1, l2 = title, ""
    if len(title) > 58:
        cut = title.rfind(" ", 0, 58)
        l1, l2 = title[:cut], title[cut + 1:]
    tt = (f'<text x="{M/2+162}" y="{y0+17}" font-size="11.5" font-weight="700">{esc(l1)}</text>' +
          (f'<text x="{M/2+162}" y="{y0+30}" font-size="11.5" font-weight="700">{esc(l2[:70])}</text>' if l2 else ""))
    return (f'<rect x="{M/2}" y="{M/2}" width="{FW-M}" height="{FH-M}" fill="none" stroke="{INK}" stroke-width="1.2"/>'
            f'<line x1="{M/2}" y1="{y0}" x2="{FW-M/2}" y2="{y0}" stroke="{INK}" stroke-width="1"/>'
            f'<rect x="{M/2}" y="{y0}" width="150" height="{TB}" fill="#2f6b4f"/>'
            f'<g fill="{INK}">'
            f'<text x="{M/2+10}" y="{y0+17}" fill="#fff" font-size="9" font-weight="600">{esc(t["agency"])}</text>'
            f'<text x="{M/2+10}" y="{y0+35}" fill="#fff" font-size="16" font-weight="700">{esc(t["drawing"])}</text>'
            f'{tt}'
            f'<text x="{M/2+162}" y="{y0+41}" font-size="6.5" fill="#6a6a62">Redrawn from {esc(t["source"])} in SoCal Super Standards style. Reference only; verify against the official LADOT drawing.</text>'
            f'<line x1="{FW-M/2-110}" y1="{y0}" x2="{FW-M/2-110}" y2="{FH-M/2}" stroke="{INK}" stroke-width="0.7"/>'
            f'<text x="{FW-M/2-100}" y="{y0+13}" font-size="7" fill="#6a6a62">SHEET</text>'
            f'<text x="{FW-M/2-100}" y="{y0+30}" font-size="15" font-weight="700">{t["sheet"]} OF {t["sheets"]}</text>'
            f'<text x="{FW-M/2-100}" y="{y0+41}" font-size="6.5" fill="#6a6a62">{esc(t["date"])}</text>'
            f"</g>")


def fit(src_rect):
    """Transform from source content rect into the drawing area of the frame."""
    ax0, ay0, ax1, ay1 = M, M, FW - M, FH - M - TB - 4
    s = min((ax1 - ax0) / max(1, src_rect.width), (ay1 - ay0) / max(1, src_rect.height))
    ox = ax0 + ((ax1 - ax0) - src_rect.width * s) / 2 - src_rect.x0 * s
    oy = ay0 + ((ay1 - ay0) - src_rect.height * s) / 2 - src_rect.y0 * s
    return s, (lambda p: (p[0] * s + ox, p[1] * s + oy))


def title_block_top(pg, drawings, words):
    W, H = pg.rect.width, pg.rect.height
    cands = []
    for w in words:
        if w[1] > H * 0.7 and re.match(r"(?i)^(DEPARTMENT|TRANSPORTATION|Drawing|Title|CITY)$", w[4]):
            cands.append(w[1])
    long_h = [d["rect"].y0 for d in drawings if d["rect"].width > W * 0.6 and d["rect"].height < 2 and d["rect"].y0 > H * 0.72]
    if cands:
        above = [y for y in long_h if y < min(cands)]
        return (max(above) if above else min(cands) - 10)
    if long_h:
        return min(long_h)
    return H


def redraw_vector(pg, meta):
    W, H = pg.rect.width, pg.rect.height
    drs = pg.get_drawings()
    words = pg.get_text("words")
    tb = title_block_top(pg, drs, words)
    keep = [d for d in drs if not (d["rect"].width > W * 0.85 or d["rect"].height > H * 0.85) and d["rect"].y1 <= tb + 1]
    tbw = [pymupdf.Rect(w[:4]) for w in words if w[1] > H * 0.45 and re.sub(r"[^A-Z]", "", w[4].upper()) in ("APPROVED", "ANGELES", "DEPARTMENT", "TRANSPORTATION", "DWN", "CKD")]
    box = None
    if len(tbw) >= 2:
        u = tbw[0]
        for r_ in tbw[1:]:
            u = u | r_
        # grow to the lines that frame it
        frame = [pymupdf.Rect(d["rect"]) for d in keep if d["rect"].intersects(pymupdf.Rect(u.x0 - 20, u.y0 - 30, u.x1 + 60, u.y1 + 40))]
        box = pymupdf.Rect(u)
        for fr in frame:
            if fr.width < W * 0.6 and fr.height < H * 0.4:
                box |= fr
        box = pymupdf.Rect(box.x0 - 2, box.y0 - 2, box.x1 + 2, box.y1 + 2)
        keep = [d for d in keep if not box.contains(d["rect"])]
    if box is None:
        hl = [pymupdf.Rect(d["rect"]) for d in keep if d["rect"].width >= W * 0.22 and d["rect"].height < 2.5 and d["rect"].x0 > W * 0.4 and d["rect"].y0 > H * 0.6]
        groups = []
        for r_ in hl:
            g = [q for q in hl if abs(q.x0 - r_.x0) < 12 and abs(q.x1 - r_.x1) < 12]
            if len(g) > len(groups):
                groups = g
        hl = groups if len(groups) >= 3 else hl
        vl = [pymupdf.Rect(d["rect"]) for d in keep if d["rect"].width < 2.5 and d["rect"].height > 8 and d["rect"].y0 > H * 0.55]
        def boxed(r):
            return any(abs(v.y0 - r.y0) < 3 and (abs(v.x0 - r.x0) < 4 or abs(v.x0 - r.x1) < 4) for v in vl)
        hlb = [r for r in hl if boxed(r)]
        if hlb:
            hl = [r for r in hl if r.y0 >= min(q.y0 for q in hlb) - 1]
        if hl:
            top = min(hl, key=lambda r: r.y0)
            cand = pymupdf.Rect(min(r.x0 for r in hl) - 2, top.y0 - 2, max(r.x1 for r in hl) + 2, max(max(r.y1 for r in hl) + 30, tb))
            spans_in = [w for w in words if cand.contains(pymupdf.Rect(w[:4]))]
            x0m, x1m = min(r.x0 for r in hl), max(r.x1 for r in hl)
            aligned = [r for r in hl if abs(r.x0 - x0m) < 12 and abs(r.x1 - x1m) < 12]
            if len(aligned) >= 3 or any(re.match(r"^S-\d{2,3}", w[4]) for w in spans_in) or any(w[4].upper() in ("CKD.", "DWN.", "T.E.", "APPROVED") for w in spans_in):
                box = cand
                keep = [d for d in keep if not box.contains(d["rect"])]
    td = pg.get_text("dict")
    spans = []
    for b in td["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip() and s["bbox"][3] <= tb + 1 and not (box and box.contains(pymupdf.Rect(s["bbox"]))):
                    spans.append((s, l["dir"]))
    if not keep and not spans:
        return None
    r = None
    for d in keep:
        r = pymupdf.Rect(d["rect"]) if r is None else r | d["rect"]
    for s, _ in spans:
        r = pymupdf.Rect(s["bbox"]) if r is None else r | pymupdf.Rect(s["bbox"])
    r = pymupdf.Rect(r.x0 - 4, r.y0 - 4, r.x1 + 4, r.y1 + 4)
    sc, T = fit(r)
    out = []
    for d in keep:
        dd = path_d(d["items"], T)
        if not dd:
            continue
        fill = col(d.get("fill")) if d.get("type") in ("f", "fs") else None
        stroke = col(d.get("color")) if d.get("type") in ("s", "fs") else None
        if fill == PAL["white"] and not stroke:
            continue
        attrs = f'fill="{fill or "none"}"'
        if fill and d.get("even_odd"):
            attrs += ' fill-rule="evenodd"'
        if stroke:
            attrs += f' stroke="{stroke}" stroke-width="{qw(d.get("width")) * max(0.6, min(1.4, sc)):.2f}" stroke-linecap="round" stroke-linejoin="round"'
            if d.get("dashes") and d["dashes"] not in ("[] 0", "[] 0.0"):
                nums = re.findall(r"[\d.]+", d["dashes"])
                if len(nums) >= 2 and float(nums[0]) > 0:
                    attrs += f' stroke-dasharray="{" ".join(f"{float(n) * sc:.1f}" for n in nums[:-1])}"'
        out.append(f'<path d="{dd}" {attrs}/>')
    for s, dr in spans:
        x, y = T(s["origin"])
        size = qsize(s["size"]) * sc
        ang = -math.degrees(math.atan2(dr[1], dr[0])) if dr else 0
        bold = "700" if "Bold" in s["font"] or "bold" in s["font"].lower() else "400"
        ci = s.get("color", 0) or 0
        c = col(tuple(((ci >> k) & 255) / 255 for k in (16, 8, 0))) or INK
        rot = f' transform="rotate({-ang:.1f} {x:.1f} {y:.1f})"' if abs(ang) > 0.5 else ""
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" font-weight="{bold}" fill="{c}"{rot}>{esc(s["text"])}</text>')
    return out


def ocr_words(img_rgb, scale_to_pt):
    """Tesseract word boxes (in image px) with confidence; returns list of (x0,y0,x1,y1,text,conf)."""
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        Image.fromarray(img_rgb).save(tf.name)
        r = subprocess.run(["tesseract", tf.name, "-", "--psm", "11", "tsv"], capture_output=True, text=True, timeout=180)
    out = []
    for line in r.stdout.splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        try:
            conf = float(f[10])
        except ValueError:
            continue
        x, y, w, h = map(int, f[6:10])
        t = f[11].strip()
        if conf >= 30 and 8 <= h <= 60:
            out.append((x, y, x + w, y + h, t, conf, (f[2], f[3], f[4])))
    return out


def trace_layer(mask, color, sc_to_frame, min_area=6):
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return ""
    T = sc_to_frame
    d = []
    for i, c in enumerate(cnts):
        if cv2.contourArea(c) < min_area and hier[0][i][3] < 0:
            continue
        c = cv2.approxPolyDP(c, 0.7, True)
        if len(c) < 2:
            continue
        pts = [T((float(p[0][0]), float(p[0][1]))) for p in c]
        d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z")
    return f'<path d="{"".join(d)}" fill="{color}" fill-rule="evenodd"/>' if d else ""


def redraw_scan(pg, meta, dpi=200):
    pix = pg.get_pixmap(dpi=dpi)
    im = np.array(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    H, W = im.shape[:2]
    hsv = cv2.cvtColor(im, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 15)
    sat = hsv[:, :, 1] > 90
    red = (((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 165)) & sat & (hsv[:, :, 2] > 60)).astype(np.uint8) * 255
    yel = ((hsv[:, :, 0] > 18) & (hsv[:, :, 0] < 38) & sat & (hsv[:, :, 2] > 120)).astype(np.uint8) * 255
    blu = ((hsv[:, :, 0] > 95) & (hsv[:, :, 0] < 130) & sat).astype(np.uint8) * 255
    colored = cv2.bitwise_or(cv2.bitwise_or(red, yel), blu)
    ink = cv2.bitwise_and(ink, cv2.bitwise_not(colored))
    k = np.ones((2, 2), np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k)
    # drop original border and title block: find long horizontal rows in the bottom 30%
    rows = ink.sum(axis=1) / 255
    cut = H
    for y in range(int(H * 0.68), H):
        if rows[y] > W * 0.55:
            cut = y
            break
    ink[cut - 2:, :] = 0
    for m in (red, yel, blu):
        m[cut - 2:, :] = 0
    # remove page border lines
    cols_ = ink.sum(axis=0) / 255
    for x in range(W):
        if cols_[x] > H * 0.6:
            ink[:, x] = 0
    for y in range(H):
        if rows[y] > W * 0.8 and y < cut:
            ink[y, :] = 0
    allw = ocr_words(im, 72 / dpi)
    # crop to the drawing's inner frame: the largest near-rectangular contour
    cnts, _ = cv2.findContours(cv2.dilate(ink, np.ones((3, 3), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w > W * 0.6 and h > H * 0.6:
            if frame is None or w * h > frame[2] * frame[3]:
                frame = (x, y, w, h)
    if frame:
        x, y, w, h = frame
        band = 14
        for m in (ink, red, yel, blu):
            m[:y + band, :] = 0
            m[y + h - band:, :] = 0
            m[:, :x + band] = 0
            m[:, x + w - band:] = 0
    tbw = [w for w in allw if re.sub(r"[^A-Z]", "", w[4].upper()) in ("ANGELES", "DEPARTMENT", "TRANSPORTATION", "APPROVED", "CITY", "LOS") and w[1] > H * 0.45]
    tbw = [w for w in tbw if w[0] > W * 0.42 and w[1] > H * 0.55]
    if tbw:
        x0, y0 = min(w[0] for w in tbw), min(w[1] for w in tbw)
        x1, y1 = max(w[2] for w in tbw), max(w[3] for w in tbw)
        grew = True
        while grew:
            grew = False
            for w in allw:
                if w[0] > W * 0.4 and w[1] > H * 0.5 and not (x0 <= w[0] and w[2] <= x1 and y0 <= w[1] and w[3] <= y1):
                    if w[2] >= x0 - 60 and w[0] <= x1 + 60 and w[3] >= y0 - 45 and w[1] <= y1 + 45:
                        x0, y0, x1, y1 = min(x0, w[0]), min(y0, w[1]), max(x1, w[2]), max(y1, w[3])
                        grew = True
        # climb to the title block's top border: the highest long horizontal line above the words, spanning the block width
        xa, xb = max(0, int(x0) - 60), min(W, int(x1) + 40)
        last, top = int(y0), None
        for yy in range(int(y0) - 2, max(int(H * 0.45), int(y0) - 700), -1):
            frac = (ink[yy, xa:xb] > 0).mean()
            if frac > 0.55:
                top, last = yy, yy
            elif last - yy > 260:
                break
        if top is not None:
            y0 = top
        for m in (ink, red, yel, blu):
            m[max(0, int(y0) - 6):, max(0, int(x0) - 70):] = 0
        allw = [t for t in allw if not (t[0] >= x0 - 70 and t[1] >= y0 - 6)]
    # re-set confident OCR lines in Albert Sans; leave uncertain lines as traced linework
    lines = {}
    for w in allw:
        lines.setdefault(w[6], []).append(w)
    words = []
    for ln in lines.values():
        if len(ln) == 0:
            continue
        mc = sum(w[5] for w in ln) / len(ln)
        if mc >= 86 and min(w[5] for w in ln) >= 70 and all(re.match(r"^[A-Za-z0-9.,:;'()/&+\-\"%#=<>]+$", w[4]) for w in ln):
            words.extend(ln)
    words = [t for t in words if t[3] < cut - 2 and ink[t[1]:t[3], t[0]:t[2]].any()]
    for t in words:
        ink[max(0, t[1] - 2):t[3] + 2, max(0, t[0] - 2):t[2] + 2] = 0
    ys, xs = np.nonzero(ink | red | yel | blu)
    if len(xs) < 50:
        return None
    r = pymupdf.Rect(xs.min() - 6, ys.min() - 6, xs.max() + 6, ys.max() + 6)
    if words:
        allx = [w[0] for w in words] + [w[2] for w in words] + [r.x0, r.x1]
        ally = [w[1] for w in words] + [w[3] for w in words] + [r.y0, r.y1]
        r = pymupdf.Rect(min(allx) - 6, min(ally) - 6, max(allx) + 6, max(ally) + 6)
    sc, T = fit(r)
    out = [trace_layer(ink, INK, T)]
    hs = sorted(w[3] - w[1] for w in words)
    med = hs[len(hs) // 2] if hs else 12
    for (x0, y0, x1, y1, t, c, _ln) in words:
        X, Y = T((x0, y1))
        h = y1 - y0
        h = med if 0.55 * med <= h <= 1.7 * med else h
        hpt = h * sc * 1.18
        out.append(f'<text x="{X:.1f}" y="{Y:.1f}" font-size="{hpt:.1f}" fill="{INK}" textLength="{(x1 - x0) * sc:.1f}" lengthAdjust="spacingAndGlyphs">{esc(t)}</text>')
    for m, c in ((red, PAL["red"]), (yel, PAL["yellow"]), (blu, PAL["blue"])):
        if m.sum() > 255 * 200:
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
            out.append(trace_layer(m, c, T, 12))
    return [o for o in out if o]


def run(slug):
    cfg = cfgs[slug]
    d = json.load(open(f"data/docs/{slug.replace('/', '__')}.json"))
    doc = pymupdf.open(cfg["path"])
    groups = {}
    for p in d["pages"]:
        if p["image"] and p["drawings"]:
            groups.setdefault(p["drawings"][0], []).append(p)
    outdir = f"public/redraw/{slug.split('/')[-1]}"
    os.makedirs(outdir, exist_ok=True)
    recs = []
    only = os.environ.get("ONLY")
    for k, sheets in groups.items():
        if only and k not in only.split(","):
            continue
        meta0 = d.get("drawing_titles", {}).get(k, {})
        title = meta0.get("title") or re.sub(r"\(.*?\)", "", sheets[0]["title"] or "").strip() or "Standard drawing"
        for n, p in enumerate(sheets, 1):
            pg = doc[p["page"] - 1]
            nd, nt = len(pg.get_drawings()), len(pg.get_text().strip())
            kind = "vector" if nd > 120 else "scan"
            meta = {"agency": f"LADOT {cfg['short']}", "drawing": k, "title": title, "sheet": n, "sheets": len(sheets),
                    "date": ("DATED " + meta0["date"]) if meta0.get("date") else "", "source": f"LADOT {cfg['short']} {k}, document page {p['page']}"}
            body = redraw_vector(pg, meta) if kind == "vector" else redraw_scan(pg, meta)
            if not body and kind == "vector":
                body, kind = redraw_scan(pg, meta), "scan"
            if not body:
                continue
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {FW} {FH}" width="{FW*2}" height="{FH*2}">'
                   f'<style>text{{font-family:"Albert Sans",Arial,sans-serif}}</style><rect width="{FW}" height="{FH}" fill="#ffffff"/>' + "".join(body) + frame_and_tb(meta) + "</svg>")
            fn = f"{re.sub(r'[^a-z0-9]+', '-', k.lower()).strip('-')}-s{n}.svg"
            open(f"{outdir}/{fn}", "w").write(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", svg))
            recs.append({"drawing": k, "title": title, "sheet": n, "sheets": len(sheets), "page": p["page"], "kind": kind,
                         "svg": f"{BASE}/redraw/{slug.split('/')[-1]}/{fn}", "kb": round(len(svg) / 1024)})
    json.dump(recs, open(f"data/docs/redraw_{slug.split('/')[-1]}.json", "w"), indent=1)
    from collections import Counter
    print(slug, len(recs), Counter(r["kind"] for r in recs), "total MB", round(sum(r["kb"] for r in recs) / 1024, 1))


for s in sys.argv[1:]:
    run(s)
