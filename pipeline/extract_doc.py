"""Generic document reader extractor (LADOT and other PDFs).

For every page: native text (or OCR when the page is a scan), a sharpened image snip when the page
is graphic (drawings, figures, scans), detected standard-drawing numbers, sign codes (linked to the
Sign Library), MUTCD section references (linked to the readers), keywords and topics.

Outputs:
  src/content/docs/<slug>/index.md            document overview (chapters, drawings index)
  src/content/docs/<slug>/<chapter>.md        chapter pages (page-by-page, anchored #p<N>)
  public/figs/<slug>/p<NNNN>.webp
  data/docs/<slug>.json                       per-page records for search and the AI agent

Usage: python3 -I pipeline/extract_doc.py CONFIG.json SLUG REPO_ROOT
"""
import html, io, json, os, re, subprocess, sys, tempfile
from collections import Counter
import pymupdf
from PIL import Image, ImageFilter, ImageOps

CFG_PATH, SLUG, ROOT = sys.argv[1:4]
cfg = next(c for c in json.load(open(CFG_PATH)) if c["slug"] == SLUG)
BASE = os.environ.get("SITE_BASE", "/SoCal-Super-Standards")
doc = pymupdf.open(cfg["path"])
signs = {}
try:
    for s in json.load(open(f"{ROOT}/data/signs/signs.json")):
        signs[s["code"]] = s
except FileNotFoundError:
    pass
ca_secs = {s["num"] for s in json.load(open(f"{ROOT}/data/ca-mutcd/sections.json"))}

CODE_RE = re.compile(r"(?<![A-Za-z0-9-])((?:OM|SR|SW|CW|[RWSDMEIG])\d{1,3}[A-Za-z]?-\d{1,3}[A-Za-z]{0,4}(?:\s?\(CA\))?)(?![A-Za-z0-9])")
DWG_RE = re.compile(r"\b(S-\d{2,3}(?:\.\d+){0,3})\b")
SEC_RE = re.compile(r"\b(?:Section|Sec\.)\s+(\d[A-Z]\.\d{2,3}(?:\(CA\))?)")
TOPICS = {
    "crosswalks": r"crosswalk|pedestrian crossing|ped xing|continental|ladder",
    "bikeways": r"bike|bicycl|cycle track|class iv|class ii",
    "transit": r"\bbus\b|transit|bus bulb|bus lane|bus stop",
    "signals": r"signal|phasing|pedestrian head|mast ?arm|controller|detector|loop",
    "parking-curb": r"parking|curb zone|loading|red curb|meter|stall",
    "speed-calming": r"speed hump|traffic calming|speed table|raised crosswalk|traffic circle|roundabout",
    "striping": r"striping|lane line|centerline|channelization|taper|cat ?track|elephant track|limit line",
    "signs": r"\bsign(s|ing)?\b",
    "accessibility": r"curb ramp|ada|detectable warning|accessible",
    "intersections": r"intersection|turn lane|channelized right",
}
STOP = set("the and for with that this shall should may from are not all any per see each where when its into than been have such other which also used will can more use their there these only both less most must over upon under very within without about after before being between during".split())

out_dir = f"{ROOT}/src/content/docs/{SLUG}"
fig_dir = f"{ROOT}/public/figs/{SLUG}"
os.makedirs(out_dir, exist_ok=True)
os.makedirs(fig_dir, exist_ok=True)
os.makedirs(f"{ROOT}/data/docs", exist_ok=True)
for f in os.listdir(out_dir):
    if f.endswith(".md"):
        os.remove(os.path.join(out_dir, f))

skip = set(cfg.get("skip_pages", []))


def esc(t):
    return html.escape(t, quote=False)


def ocr(pg):
    pix = pg.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        pix.save(tf.name)
        r = subprocess.run(["tesseract", tf.name, "-", "--psm", "3"], capture_output=True, text=True, timeout=120)
    return r.stdout


def is_graphic(pg, text):
    nd = len(pg.get_drawings())
    imgs = pg.get_image_info()
    big_img = any((i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1]) > 0.15 * pg.rect.width * pg.rect.height for i in imgs)
    return nd > 150 or big_img or len(text.strip()) < 250


def snip(pg, pno, scanned):
    fn = f"p{pno + 1:04d}.webp"
    dst = f"{fig_dir}/{fn}"
    if not os.path.exists(dst):
        long_edge = max(pg.rect.width, pg.rect.height)
        dpi = max(110, min(220, int(2000 / (long_edge / 72))))
        pix = pg.get_pixmap(dpi=dpi)
        im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        if scanned:
            # clean up scans: lift contrast, sharpen line work, flatten paper tone
            im = ImageOps.autocontrast(im, cutoff=1)
            im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=170, threshold=3))
        else:
            im = im.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=2))
        im.save(dst, "WEBP", quality=74, method=5)
    return f"{BASE}/figs/{SLUG}/{fn}"


def blocks_html(pg):
    d = pg.get_text("dict")
    sizes = Counter()
    for b in d["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    sizes[round(s["size"])] += len(s["text"])
    body = sizes.most_common(1)[0][0] if sizes else 10
    out = []
    for b in d["blocks"]:
        lines = [l for l in b.get("lines", []) if "".join(s["text"] for s in l["spans"]).strip()]
        if not lines:
            continue
        txt = " ".join("".join(s["text"] for s in l["spans"]).strip() for l in lines)
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) < 2:
            continue
        sz = max(s["size"] for l in lines for s in l["spans"])
        bold = any("Bold" in s["font"] for l in lines for s in l["spans"])
        if (sz >= body * 1.25 or (bold and len(txt) < 90)) and len(txt) < 140:
            out.append(("h", txt))
        else:
            out.append(("p", txt))
    return out


def link_codes(t):
    t = CODE_RE.sub(lambda m: (f'<a class="sref" href="{BASE}/signs/{signs[m.group(1)]["slug"]}/" data-svg="{BASE}{signs[m.group(1)]["svg"]}">{m.group(1)}</a>'
                               if m.group(1) in signs else m.group(0)), t)
    t = SEC_RE.sub(lambda m: (f'<a href="{BASE}/s/ca/{m.group(1)}/">{m.group(0)}</a>' if m.group(1) in ca_secs else m.group(0)), t)
    return t


def keywords(text, n=14):
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)]
    c = Counter(w for w in words if w not in STOP)
    return [w for w, _ in c.most_common(n)]


# ------------------------------------------------------------------ chapters
toc = [t for t in doc.get_toc() if t[0] <= cfg.get("toc_level", 1) and t[2] >= 1]
if cfg.get("toc_filter"):
    toc = [t for t in toc if re.match(cfg["toc_filter"], t[1].strip())]
# page -> bookmark label (drawing sets bookmark each sheet)
page_label = {}
for lvl, title, page in toc:
    lab = re.sub(r"\.pdf$", "", re.sub(r"\s+", " ", title).strip(), flags=re.I)
    page_label.setdefault(page, lab)
mode = cfg.get("mode", "toc")
chapters = []
if cfg.get("chapters"):
    chapters = [list(c) for c in cfg["chapters"]]  # [[title, first, last], ...] 1-based
elif mode == "toc" and toc:
    starts = []
    for lvl, title, page in toc:
        if not starts or page > starts[-1][1]:
            starts.append((re.sub(r"\s+", " ", title).strip()[:90], page))
    for i, (t, p) in enumerate(starts):
        last = starts[i + 1][1] - 1 if i + 1 < len(starts) else len(doc)
        chapters.append([t, p, last])
    if starts and starts[0][1] > 1:
        chapters.insert(0, ["Front matter", 1, starts[0][1] - 1])
if cfg.get("group_after"):
    # keep explicit chapters up to group_after, then group remaining pages into drawing sets of ~chunk pages
    g0, step = cfg["group_after"], cfg.get("chunk", 16)
    chapters = [c for c in chapters if c[2] < g0] if chapters else []
    a = g0
    while a <= len(doc):
        b = min(len(doc), a + step - 1)
        labs = [page_label[p] for p in range(a, b + 1) if p in page_label]
        def short(x):
            m = DWG_RE.search(x.replace("-0-", ".0-").replace("S-", "S-"))
            return m.group(1) if m else x[:24]
        name = f"Drawings {short(labs[0])} to {short(labs[-1])}" if labs else f"Pages {a}-{b}"
        chapters.append([name, a, b])
        a = b + 1
if not chapters:
    step = cfg.get("chunk", 20)
    for a in range(1, len(doc) + 1, step):
        chapters.append([f"Pages {a}-{min(len(doc), a + step - 1)}", a, min(len(doc), a + step - 1)])

records, drawings = [], {}
IDX_RE = re.compile(r"(S-\d{2,3}(?:\.\d+)*)\s+([A-Z][^\n]{4,90}?)\s+(\d{1,2})\s+(\d\d-\d\d-\d\d)")
dwg_titles = {}
for _p in range(min(len(doc), 25)):
    for m in IDX_RE.finditer(re.sub(r"[ \t]+", " ", doc[_p].get_text().replace("\n", " "))):
        k = m.group(1) if "." in m.group(1) else m.group(1) + ".0"
        dwg_titles.setdefault(k, {"title": m.group(2).strip(" -_"), "sheets": int(m.group(3)), "date": m.group(4)})
cur_label = ""
MIN_D = cfg.get("dwg_min_digits", 2)

def norm_d(ds):
    out = []
    for d in ds:
        n = d[2:].split(".")[0]
        if len(n) < MIN_D:
            continue
        if "." not in d:
            d += ".0"
        if d not in out:
            out.append(d)
    return out

for ci, (ctitle, a, b) in enumerate(chapters):
    cslug = f"{ci + 1:02d}-" + re.sub(r"[^a-z0-9]+", "-", ctitle.lower()).strip("-")[:40]
    parts = []
    for pno in range(a - 1, b):
        if pno + 1 in skip:
            continue
        pg = doc[pno]
        native = pg.get_text()
        scanned = len(native.strip()) < 120
        text = native
        if scanned:
            try:
                text = ocr(pg)
            except Exception:
                text = ""
        graphic = is_graphic(pg, native)
        img = snip(pg, pno, scanned) if graphic else None
        flat = re.sub(r"\s+", " ", text)
        if pno + 1 in page_label:
            cur_label = page_label[pno + 1]
        lab = cur_label if cfg.get("carry_label") else page_label.get(pno + 1, "")
        lab_d = DWG_RE.findall(re.sub(r"S-(\d+)-(\d+)(?:-(\d+))?", lambda m: "S-" + ".".join(x for x in m.groups() if x), lab))
        dwgs = norm_d(lab_d + sorted(set(DWG_RE.findall(flat))))
        codes = sorted({c for c in CODE_RE.findall(flat)})
        secs = sorted(set(SEC_RE.findall(flat)))
        topics = [k for k, rx in TOPICS.items() if re.search(rx, flat, re.I)]
        kw = keywords(flat)
        title = ""
        bl = blocks_html(pg) if not scanned else []
        for kind, t in bl:
            if kind == "h":
                title = t
                break
        if lab and not title:
            title = lab
        if dwgs and dwgs[0] in dwg_titles and graphic:
            title = f"{dwgs[0]} {dwg_titles[dwgs[0]]['title']}"
        if dwgs and graphic:
            if dwgs[0] not in title:
                title = (title + " " if title else "") + "(" + ", ".join(dwgs[:2]) + ")"
            for dw in dwgs[:2]:
                drawings.setdefault(dw, []).append({"page": pno + 1, "chapter": cslug})
        rec = {"doc": SLUG, "page": pno + 1, "chapter": cslug, "title": title[:140], "image": img,
               "drawings": dwgs, "sign_codes": codes, "sections": secs, "topics": topics, "keywords": kw,
               "url": f"{BASE}/{SLUG}/{cslug}/#p{pno + 1}", "text": flat[:4000], "ocr": scanned}
        records.append(rec)
        # page block
        head = f'\n<span id="p{pno + 1}" class="anchor"></span>\n\n### Page {pno + 1}{(" - " + esc(title)) if title else ""}\n\n'
        meta = []
        if dwgs:
            meta.append("Drawings: " + ", ".join(f"<strong>{esc(d)}</strong>" for d in dwgs[:6]))
        if codes:
            meta.append("Signs: " + link_codes(" ".join(codes[:24])))
        if secs:
            meta.append("MUTCD: " + link_codes(" ".join("Section " + s for s in secs[:10])))
        if topics:
            meta.append("Topics: " + ", ".join(topics))
        block = head + ('<div class="pmeta">' + " &middot; ".join(meta) + "</div>\n" if meta else "")
        if img:
            block += (f'<figure class="dfig"><a href="{img}" target="_blank"><img loading="lazy" src="{img}" alt="{esc(cfg["short"])} page {pno + 1} {esc(title)}"></a>'
                      f'<figcaption>{esc(cfg["short"])}, page {pno + 1}{" (scanned, cleaned and sharpened)" if scanned else ""}. Click to enlarge.</figcaption></figure>\n')
        if bl and not (graphic and len(native.strip()) < 600):
            body = []
            for kind, t in bl:
                t2 = link_codes(esc(t))
                body.append(f"<h4>{t2}</h4>" if kind == "h" else f"<p>{t2}</p>")
            block += '<div class="dtext">' + "\n".join(body) + "</div>\n"
        elif flat.strip():
            block += (f'<details class="ocr"><summary>Text on this page{" (OCR)" if scanned else ""}</summary>'
                      f"<p>{link_codes(esc(flat[:6000]))}</p></details>\n")
        block += f'<div class="kw">Keywords: {esc(", ".join(kw))}</div>\n'
        parts.append(block)
    fm = (f'---\ntitle: "{cfg["short"]}: {ctitle.replace(chr(34), chr(39))}"\n'
          f'description: "{cfg["title"].replace(chr(34), chr(39))}, {ctitle.replace(chr(34), chr(39))}, pages {a}-{b}."\n'
          f"sidebar:\n  order: {ci + 1}\n---\n\n")
    src = f'<div class="srcbar">{esc(cfg["title"])} &middot; {esc(cfg["edition"])} &middot; pages {a}&ndash;{b}</div>\n'
    open(f"{out_dir}/{cslug}.md", "w").write(fm + src + "\n".join(parts))
    chapters[ci].append(cslug)

# ------------------------------------------------------------------ overview
rows = "".join(f'<li><a href="{BASE}/{SLUG}/{c[3]}/">{esc(c[0])}</a> <span class="src-page">pp {c[1]}-{c[2]}</span></li>' for c in chapters)
dw_rows = ""
if drawings:
    def dk(d):
        return [int(x) for x in re.findall(r"\d+", d)]
    dw_rows = "<h2>Standard drawings</h2><table class=\"dwtab\"><thead><tr><th>Drawing</th><th>Title</th><th>Dated</th><th>Sheets (pages)</th></tr></thead><tbody>" + "".join(
        f'<tr><td><strong>{esc(d)}</strong></td><td>{esc(dwg_titles.get(d, {}).get("title", ""))}</td><td>{esc(dwg_titles.get(d, {}).get("date", ""))}</td><td>' + ", ".join(f'<a href="{BASE}/{SLUG}/{x["chapter"]}/#p{x["page"]}">p {x["page"]}</a>' for x in v) + "</td></tr>"
        for d, v in sorted(drawings.items(), key=lambda kv: dk(kv[0]))) + "</tbody></table>"
thumbs = "".join(f'<a href="{r["url"]}"><img loading="lazy" src="{r["image"].replace('/figs/', '/thumbs/figs/')}" alt="page {r["page"]}"><span>p {r["page"]}{(" " + esc(", ".join(r["drawings"][:1]))) if r["drawings"] else ""}</span></a>'
                 for r in records if r["image"])[:400000]
ov = (f'---\ntitle: "{cfg["title"].replace(chr(34), chr(39))}"\ndescription: "{cfg["short"]}: {cfg["edition"]}. Full document, page by page, with drawings, OCR text and linked signs."\n'
      f"sidebar:\n  order: 0\n  label: Overview\ntableOfContents: false\n---\n\n"
      f'<div class="srcbar">{esc(cfg["publisher"])} &middot; {esc(cfg["edition"])} &middot; {len(doc)} pages{(" &middot; " + esc(cfg["note"])) if cfg.get("note") else ""}</div>\n\n'
      f"<h2>Chapters</h2><ul class=\"chlist\">{rows}</ul>\n{dw_rows}\n<h2>Every drawing and figure page</h2><div class=\"thumbgrid\">{thumbs}</div>\n")
open(f"{out_dir}/index.md", "w").write(ov)
json.dump({"slug": SLUG, "title": cfg["title"], "short": cfg["short"], "edition": cfg["edition"],
           "chapters": [{"title": c[0], "first": c[1], "last": c[2], "slug": c[3]} for c in chapters],
           "drawings": drawings, "drawing_titles": dwg_titles, "pages": records}, open(f"{ROOT}/data/docs/{SLUG.replace('/', '__')}.json", "w"))
print(SLUG, "pages", len(records), "graphic", sum(1 for r in records if r["image"]), "ocr", sum(1 for r in records if r["ocr"]),
      "drawings", len(drawings), "chapters", len(chapters))
