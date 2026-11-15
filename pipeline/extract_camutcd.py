"""Extract CA MUTCD 2026 into site content.

Outputs (paths relative to the repo root):
  src/content/docs/ca-mutcd/<chapter>.md   one page per chapter, every section anchored
  public/figs/ca-mutcd/<page>.webp          figure and table page snips (cropped)
  data/ca-mutcd/sections.json               section index (num, title, chapter, page, url)
  data/ca-mutcd/figures.json                figure index (id, title, chapter, page, image)
  public/s/ca/<num>/index.html              short redirect links, e.g. /s/ca/4I.06/

Usage: python3 -I pipeline/extract_camutcd.py SOURCE.pdf REPO_ROOT
"""
import html, json, os, re, sys
from collections import OrderedDict
import pymupdf

SRC, ROOT = sys.argv[1], sys.argv[2]
doc = pymupdf.open(SRC)
BASE = os.environ.get("SITE_BASE", "/SoCal-Super-Standards")

PART_NAMES = {
    "1": "General", "2": "Signs", "3": "Markings", "4": "Highway Traffic Signals",
    "5": "Traffic Control Devices for Automated Vehicles", "6": "Temporary Traffic Control",
    "7": "Traffic Control for School Areas", "8": "Railroad and Light Rail Transit Grade Crossings",
    "9": "Traffic Control for Bicycle Facilities", "A": "Appendices",
}

# ------------------------------------------------------------------ page classification
FOOT_RE = re.compile(r"(?:Chapter|Appendix)\s+(\d[A-Z]|A\d)\s*[–-]\s*(.+?)(?:\s*\((Figures|Tables)\))?\s*$")
FIG_RE = re.compile(r"(Figure|Table)\s+(\d[A-Z]-\d+(?:\s?\(CA\))?)\.?\s+(.+)")


def page_lines(pno):
    out = []
    for b in doc[pno].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            sp = [s for s in l["spans"] if s["text"].strip()]
            if sp:
                out.append((l["bbox"], sp))
    return out


def footer_info(pno):
    txt = ""
    for bbox, sp in page_lines(pno):
        if bbox[1] > 730:
            t = "".join(s["text"] for s in sp).strip()
            if t.startswith(("Chapter", "Appendix")):
                txt = t
    m = FOOT_RE.match(txt)
    return (m.group(1), m.group(2).strip(), m.group(3)) if m else (None, None, None)


def title_band(pno):
    t = " ".join("".join(s["text"] for s in sp) for bbox, sp in page_lines(pno) if 38 < bbox[1] < 75)
    return re.sub(r"\s+", " ", t).strip()


pages = []  # dict per page
prev = None
for pno in range(len(doc)):
    ch, chtitle, kind = footer_info(pno)
    full = doc[pno].get_text()
    if "INTENTIONALLY LEFT BLANK" in full.upper() and len(full) < 400:
        prev = None
        continue
    if full.count("....") >= 5 or pno < 54:  # front matter / table of contents
        continue
    if ch is None:
        m = re.search(r"CHAPTER\s+(\d[A-Z])\.\s+([A-Z ,\-–—]+)", full)
        if m:
            ch, chtitle = m.group(1), m.group(2).strip().title()
        elif prev and re.search(r"Section\s+\d[A-Z]\.\d|\n\d{2}\s*\n", full):
            ch, chtitle = prev
        else:
            continue
    prev = (ch, chtitle if kind is None else re.sub(r"\s*\((Figures|Tables)\)", "", chtitle))
    band = title_band(pno)
    if kind is None:
        if re.match(r"(Figure|Table)\s+\d[A-Z]-\d+", band):
            kind = "Figures" if band.startswith("Figure") else "Tables"
        else:
            kind = "Text"
    pages.append({"pno": pno, "chapter": ch, "chtitle": chtitle, "kind": kind})

chapters = OrderedDict()
for p in pages:
    c = chapters.setdefault(p["chapter"], {"code": p["chapter"], "title": None, "pages": []})
    c["pages"].append(p)
    if p["kind"] == "Text" and not c["title"]:
        c["title"] = p["chtitle"]
for c in chapters.values():
    if not c["title"]:
        c["title"] = re.sub(r"\s*\((Figures|Tables)\)", "", c["pages"][0]["chtitle"])
    c["title"] = c["title"].replace("—", " - ").replace("–", "-").strip()


# ------------------------------------------------------------------ text to HTML
def esc(t):
    return html.escape(t, quote=False)


def span_html(s):
    t = esc(s["text"])
    f = s["font"]
    blue = s["color"] == 0x0000FF
    if blue:
        t = f'<span class="ca">{t}</span>'
    return t


LABELS = {"Standard:": "std", "Guidance:": "gui", "Option:": "opt", "Support:": "sup"}


def slug(num):
    return num.lower().replace(".", "").replace("(", "").replace(")", "")


def fig_slug(fid):
    return "fig-" + fid.lower().replace(" ", "").replace("(", "").replace(")", "")


class ChapterWriter:
    def __init__(self, code):
        self.code = code
        self.out = []
        self.block = None      # current label class
        self.para = None       # list of html chunks
        self.sections = []
        self.figrefs = set()

    def flush_para(self):
        if self.para is not None:
            txt = " ".join(self.para).strip()
            txt = re.sub(r"\s+", " ", txt)
            txt = re.sub(r"(Figure|Table)\s+(\d[A-Z]-\d+(?:\s?\(CA\))?)",
                         lambda m: f'<a href="#{fig_slug(m.group(2))}">{m.group(0)}</a>', txt)
            txt = re.sub(r"Section\s+(\d[A-Z]\.\d+(?:\(CA\))?)",
                         lambda m: f'<a href="{sec_href(m.group(1))}">{m.group(0)}</a>', txt)
            num = f'<span class="pn">{self.pnum}</span> ' if self.pnum else ""
            self.out.append(f"<p>{num}{txt}</p>")
            self.para = None
            self.pnum = None

    def close_block(self):
        self.flush_para()
        if self.block:
            self.out.append("</div>")
            self.block = None

    def label(self, cls, name):
        self.close_block()
        self.block = cls
        self.out.append(f'<div class="prov {cls}"><div class="prov-label">{name}</div>')

    def heading(self, num, title, page):
        self.close_block()
        sid = slug(num)
        self.sections.append({"num": num, "title": title, "page": page, "anchor": sid})
        t = re.sub(r"([*_`\[\]<>])", r"\\\1", f"{num} {title}")
        self.out.append(f'\n<span id="{sid}" class="anchor"></span>\n\n## {t}\n\n'
                        f'<div class="secmeta">Section {esc(num)} &middot; manual page {page} &middot; '
                        f'<a href="{BASE}/s/ca/{num}/">short link</a></div>\n')

    def sub(self, text):
        self.close_block()
        self.out.append(f'\n<div class="subch">{esc(text.title())}</div>\n')

    def text(self, chunk, pnum=None):
        if pnum:
            self.flush_para()
            self.para = [chunk]
            self.pnum = pnum
        else:
            if self.para is None:
                self.para = []
                self.pnum = None
            self.para.append(chunk)


SEC_INDEX = {}  # num -> url (filled in a first pass)


def sec_href(num):
    return SEC_INDEX.get(num, "#")


def chapter_url(code):
    return f"{BASE}/ca-mutcd/{code.lower()}/"


def parse_text_pages(c):
    w = ChapterWriter(c["code"])
    pending_title = None
    for p in c["pages"]:
        if p["kind"] != "Text":
            continue
        pno = p["pno"]
        printed = pno + 1
        lines = [(bb, sp) for bb, sp in page_lines(pno) if 40 < bb[1] < 730]
        i = 0
        while i < len(lines):
            bb, sp = lines[i]
            raw = "".join(s["text"] for s in sp).strip()
            f0, sz0 = sp[0]["font"], sp[0]["size"]
            bold12 = "Bold" in f0 and sz0 >= 11.5
            if bold12 and raw.startswith("CHAPTER"):
                i += 1
                continue
            if bold12 and raw.startswith("PART "):
                i += 1
                continue
            if bold12 and re.match(r"Section\s+\d[A-Z]\.\d", raw):
                title = raw
                # merge wrapped title lines
                while i + 1 < len(lines):
                    nb, nsp = lines[i + 1]
                    nraw = "".join(s["text"] for s in nsp).strip()
                    if "Bold" in nsp[0]["font"] and nsp[0]["size"] >= 11.5 and not re.match(r"(Section|CHAPTER|Standard|Guidance|Option|Support)", nraw) and nraw.upper() != nraw:
                        title += " " + nraw
                        i += 1
                    else:
                        break
                m = re.match(r"Section\s+(\d[A-Z]\.\d+(?:\s?\(CA\))?)\s*(.*)", re.sub(r"\s+", " ", title))
                w.heading(m.group(1).replace(" (CA)", "(CA)"), m.group(2), printed)
                i += 1
                continue
            if bold12 and raw.upper() == raw and len(raw) > 3 and not raw[0].isdigit():
                w.sub(raw)
                i += 1
                continue
            if raw in LABELS:
                w.label(LABELS[raw], raw[:-1])
                i += 1
                continue
            # paragraph number?
            pnum = None
            spans = sp
            if sz0 < 9 and re.fullmatch(r"\d{2}[a-z]?", sp[0]["text"].strip()):
                pnum = sp[0]["text"].strip()
                spans = sp[1:]
                if not spans and i + 1 < len(lines) and abs(lines[i + 1][0][1] - bb[1]) < 4:
                    i += 1
                    spans = lines[i][1]
            if not spans:
                i += 1
                continue
            chunk = "".join(span_html(s) for s in spans)
            if w.block in ("std",) or "Bold" in spans[0]["font"]:
                pass
            w.text(chunk, pnum)
            i += 1
    w.close_block()
    return w


# ------------------------------------------------------------------ figures


def content_clip(pno):
    pg = doc[pno]
    r = pymupdf.Rect()
    for b in pg.get_text("blocks"):
        br = pymupdf.Rect(b[:4])
        if br.y0 > 42 and br.y1 < 735:
            r |= br
    for d in pg.get_drawings():
        dr = d["rect"]
        if dr.y0 > 40 and dr.y1 < 740 and dr.width < 600:
            r |= dr
    for im in pg.get_image_info():
        ir = pymupdf.Rect(im["bbox"])
        if ir.y0 > 40 and ir.y1 < 740:
            r |= ir
    if r.is_empty or r.width < 50:
        r = pymupdf.Rect(30, 40, 582, 740)
    return (r + (-8, -8, 8, 8)) & pg.rect


def page_figures(pno):
    """All figure/table ids + titles printed on the page."""
    t = re.sub(r"\s+", " ", doc[pno].get_text())
    found = OrderedDict()
    for m in re.finditer(r"(Figure|Table)\s+(\d[A-Z]-\d+(?:\s?\(CA\))?)\.\s+([^.]{4,140}?)(?=\s(?:Chapter|Figure|Table|Notes?:|[A-Z]\s–|\(Sheet)|$)", t):
        fid = m.group(2).replace(" (CA)", "(CA)")
        if fid not in found:
            found[fid] = (m.group(1), m.group(3).strip())
    return found


# ------------------------------------------------------------------ run
os.makedirs(f"{ROOT}/src/content/docs/ca-mutcd", exist_ok=True)
os.makedirs(f"{ROOT}/public/figs/ca-mutcd", exist_ok=True)
os.makedirs(f"{ROOT}/data/ca-mutcd", exist_ok=True)

# pass 1: section index for cross-links
writers = {}
for code, c in chapters.items():
    writers[code] = parse_text_pages(c)
    for s in writers[code].sections:
        SEC_INDEX[s["num"]] = chapter_url(code) + "#" + s["anchor"]
# pass 2 with links resolved
all_secs, all_figs = [], []
for order, (code, c) in enumerate(chapters.items()):
    w = parse_text_pages(c)
    part = code[0]
    figs_html = []
    for p in c["pages"]:
        if p["kind"] == "Text":
            continue
        pno = p["pno"]
        img = f"public/figs/ca-mutcd/p{pno + 1:04d}.webp"
        dst = f"{ROOT}/{img}"
        if not os.path.exists(dst):
            clip = content_clip(pno)
            pix = doc[pno].get_pixmap(dpi=150, clip=clip)
            pix.pil_save(dst, format="WEBP", quality=80, method=4) if hasattr(pix, "pil_save") else pix.save(dst.replace(".webp", ".png"))
        found = page_figures(pno)
        ids = list(found.keys()) or [f"p{pno + 1}"]
        anchors = "".join(f'<span id="{fig_slug(i)}"></span>' for i in ids)
        cap = "; ".join(f"{found[i][0]} {i}. {found[i][1]}" for i in found) or f"{p['kind'][:-1]} page {pno + 1}"
        figs_html.append(
            f'<figure class="mfig">{anchors}<a href="{BASE}/figs/ca-mutcd/p{pno + 1:04d}.webp" target="_blank">'
            f'<img loading="lazy" src="{BASE}/figs/ca-mutcd/p{pno + 1:04d}.webp" alt="{html.escape(cap)}"></a>'
            f'<figcaption>{esc(cap)} <span class="src-page">p {pno + 1}</span></figcaption></figure>')
        for i in found:
            all_figs.append({"id": i, "kind": found[i][0], "title": found[i][1], "chapter": code,
                             "page": pno + 1, "image": f"/figs/ca-mutcd/p{pno + 1:04d}.webp",
                             "url": chapter_url(code) + "#" + fig_slug(i)})
    first = c["pages"][0]["pno"] + 1
    last = c["pages"][-1]["pno"] + 1
    fm = (f"---\ntitle: \"{code} {c['title']}\"\n"
          f"description: \"CA MUTCD 2026 Chapter {code}, {c['title']}. Manual pages {first}-{last}.\"\n"
          f"sidebar:\n  order: {order}\n  label: \"{code} {c['title']}\"\n---\n\n")
    head = (f'<div class="srcbar">California MUTCD 2026 Edition (effective January 18, 2026) &middot; '
            f'Part {part} {PART_NAMES[part]} &middot; manual pages {first}&ndash;{last}</div>\n\n')
    toc = ""
    if w.sections:
        toc = '<details class="sec-toc" open><summary>Sections in this chapter</summary><ul>' + "".join(
            f'<li><a href="#{s["anchor"]}">{esc(s["num"])} {esc(s["title"])}</a></li>' for s in w.sections) + "</ul></details>\n\n"
    body = "\n".join(w.out)
    figs = ""
    if figs_html:
        figs = '\n\n<h2 id="figures-tables">Figures and tables</h2>\n\n<div class="mfig-grid">' + "\n".join(figs_html) + "</div>\n"
    with open(f"{ROOT}/src/content/docs/ca-mutcd/{code.lower()}.md", "w") as fh:
        fh.write(fm + head + toc + body + figs)
    for s in w.sections:
        all_secs.append({**s, "chapter": code, "url": chapter_url(code) + "#" + s["anchor"]})

json.dump(all_secs, open(f"{ROOT}/data/ca-mutcd/sections.json", "w"), indent=1)
json.dump(all_figs, open(f"{ROOT}/data/ca-mutcd/figures.json", "w"), indent=1)
json.dump([{"code": k, "title": v["title"], "first": v["pages"][0]["pno"] + 1, "last": v["pages"][-1]["pno"] + 1}
           for k, v in chapters.items()], open(f"{ROOT}/data/ca-mutcd/chapters.json", "w"), indent=1)

# short links /s/ca/<num>/
for s in all_secs:
    d = f"{ROOT}/public/s/ca/{s['num']}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/index.html", "w") as fh:
        fh.write(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={s["url"]}">'
                 f'<link rel="canonical" href="{s["url"]}"><a href="{s["url"]}">Section {s["num"]}</a>')
print("chapters", len(chapters), "sections", len(all_secs), "figures", len(all_figs))
