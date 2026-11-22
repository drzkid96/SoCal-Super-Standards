"""Extract FHWA MUTCD 11th Edition with Revision 1 (December 2025) into site content.

Outputs:
  src/content/docs/mutcd/<chapter>.md    one page per chapter, sections anchored, figures placed after their section
  public/figs/mutcd/p<page>.webp         figure and table snips
  data/mutcd/{chapters,sections,figures}.json
  public/s/us/<num>/index.html           short links

Each section is flagged when it sits on a page FHWA re-issued in Revision 1 (footer "December 2025"),
and is cross-linked to the matching CA MUTCD 2026 section, noting whether California amended it.

Usage: python3 -I pipeline/extract_fedmutcd.py MUTCD-11E-R1.pdf REPO_ROOT
"""
import html, json, os, re, sys
from collections import OrderedDict
import pymupdf

SRC, ROOT = sys.argv[1], sys.argv[2]
doc = pymupdf.open(SRC)
BASE = os.environ.get("SITE_BASE", "/SoCal-Super-Standards")
PART_NAMES = {
    "1": "General", "2": "Signs", "3": "Markings", "4": "Highway Traffic Signals",
    "5": "Automated Vehicle Considerations", "6": "Temporary Traffic Control",
    "7": "Traffic Control for School Areas", "8": "Railroad and Light Rail Transit Grade Crossings",
    "9": "Traffic Control for Bicycle Facilities", "A": "Appendices",
}

ca_secs = {}
try:
    for s in json.load(open(f"{ROOT}/data/ca-mutcd/sections.json")):
        ca_secs[s["num"]] = s
except FileNotFoundError:
    pass

# ------------------------------------------------------------------ chapters from the bookmarks
toc = doc.get_toc()
heads = []
for lvl, title, page in toc:
    if lvl == 2 and page >= 42:
        m = re.match(r"CHAPTER\s+(\d[A-Z])\.\s*(.*)", title)
        a = re.match(r"APPENDIX\s+(A\d)\s*(.*)", title)
        if m:
            heads.append((m.group(1), m.group(2), page))
        elif a:
            heads.append((a.group(1), a.group(2) or "Appendix", page))
chapters = OrderedDict()
for i, (code, title, page) in enumerate(heads):
    end = heads[i + 1][2] - 1 if i + 1 < len(heads) else len(doc)
    t = title.strip().title().replace("—", " - ").replace("–", "-")
    t = re.sub(r"\b(And|Or|Of|For|The|To|In|On|At|With|A)\b", lambda m: m.group(1).lower(), t)
    t = t[0].upper() + t[1:] if t else t
    chapters[code] = {"code": code, "title": t, "first": page, "last": end}
# fixes for garbled bookmark titles
FIX = {"5A": "General", "8A": "General"}


def esc(t):
    return html.escape(t, quote=False)


def slug(num):
    return num.lower().replace(".", "").replace("(", "").replace(")", "")


def fig_slug(fid):
    return "fig-" + fid.lower().replace(" ", "")


def chapter_url(code):
    return f"{BASE}/mutcd/{code.lower()}/"


def printed_page(pno):
    t = doc[pno].get_text()
    m = re.search(r"Page\s+(\d+)", t[:400]) or re.search(r"Page\s+(\d+)", t)
    return int(m.group(1)) if m else pno + 1


def revised(pno):
    foot = " ".join(b[4] for b in doc[pno].get_text("blocks") if b[1] > 740)
    return "December 2025" in foot


def figs_on(pno):
    t = re.sub(r"\s+", " ", doc[pno].get_text())
    found = OrderedDict()
    for m in re.finditer(r"(Figure|Table)\s+(\d[A-Z]-\d+)\.\s+(.{4,140}?)(?=\s(?:Figure|Table|Notes?:|Legend|\(Sheet|Sect\.|December|[A-Z]\s–)|$)", t):
        found.setdefault(m.group(2), (m.group(1), m.group(3).strip()))
    return found


def content_clip(pno):
    pg = doc[pno]
    r = pymupdf.Rect()
    for b in pg.get_text("blocks"):
        br = pymupdf.Rect(b[:4])
        if br.y0 > 38 and br.y1 < 742:
            r |= br
    for d in pg.get_drawings():
        dr = d["rect"]
        if dr.y0 > 36 and dr.y1 < 745 and dr.width < 600:
            r |= dr
    for im in pg.get_image_info():
        ir = pymupdf.Rect(im["bbox"])
        if ir.y0 > 36 and ir.y1 < 745:
            r |= ir
    if r.is_empty or r.width < 50:
        r = pymupdf.Rect(20, 36, 592, 745)
    return (r + (-8, -8, 8, 8)) & pg.rect


LABELS = {"Standard:": "std", "Guidance:": "gui", "Option:": "opt", "Support:": "sup"}
SEC_INDEX = {}


def link_text(txt):
    txt = re.sub(r"(Figures?|Tables?)\s+(\d[A-Z]-\d+)", lambda m: f'<a href="#{fig_slug(m.group(2))}">{m.group(0)}</a>', txt)
    txt = re.sub(r"Sections?\s+(\d[A-Z]\.\d+)", lambda m: f'<a href="{SEC_INDEX.get(m.group(1), "#")}">{m.group(0)}</a>', txt)
    return txt


def parse_chapter(c, write_figs):
    out, sections = [], []
    st = {"block": None, "para": None, "pnum": None, "pending_figs": [], "sec": None}

    def flush_para():
        if st["para"] is not None:
            txt = re.sub(r"\s+", " ", " ".join(st["para"])).strip()
            if txt:
                num = f'<span class="pn">{st["pnum"]}</span> ' if st["pnum"] else ""
                out.append(f"<p>{num}{link_text(txt)}</p>")
            st["para"], st["pnum"] = None, None

    def close_block():
        flush_para()
        if st["block"]:
            out.append("</div>")
            st["block"] = None

    def flush_figs():
        if st["pending_figs"]:
            close_block()
            out.append('<div class="mfig-grid">' + "\n".join(st["pending_figs"]) + "</div>")
            st["pending_figs"] = []

    figs_meta = []
    for pno in range(c["first"] - 1, c["last"]):
        pp = printed_page(pno)
        rev = revised(pno)
        lines = []
        for b in doc[pno].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                sp = [s for s in l["spans"] if s["text"].strip()]
                if sp and 38 < l["bbox"][1] < 742:
                    lines.append((l["bbox"], sp))
        lines.sort(key=lambda x: (round(x[0][1]), x[0][0]))
        # attach each paragraph number to the text line it belongs to (printed ~7pt lower)
        nums, rest = {}, []
        for bb, sp in lines:
            raw = "".join(s["text"] for s in sp).strip()
            if "Neue" in sp[0]["font"] and re.fullmatch(r"\d{2}[a-z]?", raw):
                nums[(bb[0], bb[1])] = raw
            else:
                rest.append((bb, sp))
        tagged = []
        for bb, sp in rest:
            tag = None
            for (nx, ny), n in list(nums.items()):
                if bb[0] > nx + 12 and -2 <= ny - bb[1] <= 12:
                    tag = n
                    del nums[(nx, ny)]
                    break
            tagged.append((bb, sp, tag))
        lines = tagged
        i = 0
        pend_num = None
        while i < len(lines):
            bb, sp, tag = lines[i]
            if tag:
                pend_num = tag
            f0, sz0 = sp[0]["font"], sp[0]["size"]
            raw = "".join(s["text"] for s in sp).strip()
            if not f0.startswith("Times"):
                i += 1
                continue
            if sz0 >= 11.5 and "Bold" in f0:
                if re.match(r"Section\s+\d[A-Z]\.\d", raw):
                    title = raw
                    while i + 1 < len(lines) and "Bold" in lines[i + 1][1][0]["font"] and lines[i + 1][1][0]["size"] >= 11.5 \
                            and not re.match(r"(Section|CHAPTER|PART)", "".join(s["text"] for s in lines[i + 1][1]).strip()):
                        nxt = "".join(s["text"] for s in lines[i + 1][1]).strip()
                        if nxt.upper() == nxt:
                            break
                        title += " " + nxt
                        i += 1
                    m = re.match(r"Section\s+(\d[A-Z]\.\d+)\s*(.*)", re.sub(r"\s+", " ", title))
                    flush_figs()
                    close_block()
                    num, name = m.group(1), m.group(2)
                    sid = slug(num)
                    sec = {"num": num, "title": name, "page": pp, "anchor": sid, "revised": rev}
                    sections.append(sec)
                    st["sec"] = sec
                    t = re.sub(r"([*_`\[\]<>])", r"\\\1", f"{num} {name}")
                    out.append(f'\n<span id="{sid}" class="anchor"></span>\n\n## {t}\n\n')
                    out.append(f"<!--META:{num}-->")
                    i += 1
                    continue
                if raw.startswith(("CHAPTER", "PART")):
                    i += 1
                    continue
                if raw.upper() == raw and len(raw) > 3:
                    close_block()
                    out.append(f'\n<div class="subch">{esc(raw.title())}</div>\n')
                    i += 1
                    continue
            if sz0 < 10.5:
                i += 1
                continue
            if raw in LABELS:
                close_block()
                st["block"] = LABELS[raw]
                out.append(f'<div class="prov {LABELS[raw]}"><div class="prov-label">{raw[:-1]}</div>')
                if st["sec"] and rev:
                    st["sec"]["revised"] = True
                i += 1
                continue
            chunk = esc("".join(s["text"] for s in sp))
            if pend_num:
                flush_para()
                st["para"], st["pnum"] = [chunk], pend_num
                pend_num = None
            else:
                if st["para"] is None:
                    st["para"], st["pnum"] = [], None
                st["para"].append(chunk)
            if st["sec"] and rev:
                st["sec"]["revised"] = True
            i += 1
        # figures on this page
        found = figs_on(pno)
        if found:
            img = f"p{pp:04d}.webp"
            if write_figs:
                dst = f"{ROOT}/public/figs/mutcd/{img}"
                if not os.path.exists(dst):
                    doc[pno].get_pixmap(dpi=150, clip=content_clip(pno)).pil_save(dst, format="WEBP", quality=80, method=4)
            anchors = "".join(f'<span id="{fig_slug(k)}"></span>' for k in found)
            cap = "; ".join(f"{v[0]} {k}. {v[1]}" for k, v in found.items())
            st["pending_figs"].append(
                f'<figure class="mfig">{anchors}<a href="{BASE}/figs/mutcd/{img}">'
                f'<img loading="lazy" src="{BASE}/figs/mutcd/{img}" alt="{html.escape(cap)}"></a>'
                f'<figcaption>{esc(cap)} <span class="src-page">p {pp}</span></figcaption></figure>')
            for k, v in found.items():
                figs_meta.append({"id": k, "kind": v[0], "title": v[1], "chapter": c["code"], "page": pp,
                                  "image": f"/figs/mutcd/{img}", "url": chapter_url(c["code"]) + "#" + fig_slug(k)})
    flush_figs()
    close_block()
    return out, sections, figs_meta


os.makedirs(f"{ROOT}/src/content/docs/mutcd", exist_ok=True)
os.makedirs(f"{ROOT}/public/figs/mutcd", exist_ok=True)
os.makedirs(f"{ROOT}/data/mutcd", exist_ok=True)

for code, c in chapters.items():
    _, secs, _ = parse_chapter(c, False)
    for s in secs:
        SEC_INDEX[s["num"]] = chapter_url(code) + "#" + s["anchor"]

all_secs, all_figs, ch_rows = [], [], []
for order, (code, c) in enumerate(chapters.items()):
    if code in FIX and len(c["title"]) > 40:
        c["title"] = FIX[code]
    out, secs, figs = parse_chapter(c, True)
    first_pp, last_pp = printed_page(c["first"] - 1), printed_page(c["last"] - 1)
    body = "\n".join(out)
    for s in secs:
        ca = ca_secs.get(s["num"])
        bits = [f"Section {esc(s['num'])}", f"manual page {s['page']}"]
        if s["revised"]:
            bits.append('<span class="badge rev">Revision 1 page</span>')
        if ca:
            lab = "CA amended" if ca.get("ca_changes") else "CA MUTCD 2026"
            cls = "ca-amend" if ca.get("ca_changes") else "ca-same"
            bits.append(f'<a class="badge {cls}" href="{ca["url"]}">{lab}: {esc(ca["num"])}</a>')
        else:
            bits.append('<span class="badge muted">no CA counterpart found</span>')
        bits.append(f'<a href="{BASE}/s/us/{s["num"]}/">short link</a>')
        body = body.replace(f"<!--META:{s['num']}-->", '<div class="secmeta">' + " &middot; ".join(bits) + "</div>", 1)
    part = code[0] if code[0].isdigit() else "A"
    fm = (f"---\ntitle: \"{code} {c['title']}\"\n"
          f"description: \"MUTCD 11th Edition with Revision 1, Chapter {code}, {c['title']}. Pages {first_pp}-{last_pp}.\"\n"
          f"sidebar:\n  order: {order}\n  label: \"{code} {c['title']}\"\n---\n\n")
    head = (f'<div class="srcbar">FHWA MUTCD 11th Edition with Revision 1 (December 2025, effective March 5, 2026) &middot; '
            f'Part {part} {PART_NAMES[part]} &middot; pages {first_pp}&ndash;{last_pp}</div>\n\n')
    toc_html = ""
    if secs:
        toc_html = '<details class="sec-toc" open><summary>Sections in this chapter</summary><ul>' + "".join(
            f'<li><a href="#{s["anchor"]}">{esc(s["num"])} {esc(s["title"])}</a>{" <span class=\"badge rev\">R1</span>" if s["revised"] else ""}</li>' for s in secs) + "</ul></details>\n\n"
    with open(f"{ROOT}/src/content/docs/mutcd/{code.lower()}.md", "w") as fh:
        fh.write(fm + head + toc_html + body)
    for s in secs:
        all_secs.append({**s, "chapter": code, "url": chapter_url(code) + "#" + s["anchor"]})
    all_figs += figs
    ch_rows.append({"code": code, "title": c["title"], "first": first_pp, "last": last_pp})

json.dump(all_secs, open(f"{ROOT}/data/mutcd/sections.json", "w"), indent=1)
json.dump(all_figs, open(f"{ROOT}/data/mutcd/figures.json", "w"), indent=1)
json.dump(ch_rows, open(f"{ROOT}/data/mutcd/chapters.json", "w"), indent=1)
for s in all_secs:
    d = f"{ROOT}/public/s/us/{s['num']}"
    os.makedirs(d, exist_ok=True)
    open(f"{d}/index.html", "w").write(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={s["url"]}">'
        f'<link rel="canonical" href="{s["url"]}"><a href="{s["url"]}">Section {s["num"]}</a>')
print("chapters", len(chapters), "sections", len(all_secs), "revised", sum(s["revised"] for s in all_secs), "figures", len(all_figs))
