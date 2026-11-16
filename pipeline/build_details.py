"""Detail and Drawing Index.
- One page per LADOT standard drawing (all sheets, OCR, signs, MUTCD refs, topics, prev/next).
- public/data/details.json: every figure, table, standard drawing and design-guide figure page across all sources.
- public/data/lookup.json: instant resolver for sign codes, section numbers, figure/table ids and drawing numbers.
"""
import html, json, os, re, sys, glob
import pymupdf
sys.path.insert(0, os.path.dirname(__file__))
from topics_def import T, GROUPS
BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
slugify = lambda t: re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
TOPIC_RX = {t[0]: re.compile(t[4] + "|" + t[6], re.I) for t in T}
TOPIC_NAME = {t[0]: t[1] for t in T}
def topics_for(text):
    return [k for k, rx in TOPIC_RX.items() if rx.search(text or "")]

items = []
ca_figs = json.load(open("data/ca-mutcd/figures.json"))
fed_figs = json.load(open("data/mutcd/figures.json"))
for src, figs, lab in (("CA MUTCD 2026", ca_figs, "ca"), ("Federal MUTCD", fed_figs, "fed")):
    for f in figs:
        items.append({"src": src, "sg": "MUTCD", "type": f["kind"], "num": f["id"], "title": f["title"][:160],
                      "img": BASE + f["image"] if f.get("image") else "", "url": f["url"], "topics": topics_for(f["title"]),
                      "part": f["chapter"][0]})

cfg = json.load(open("pipeline/config/ladot.json")) + json.load(open("pipeline/config/agencies.json"))
signs = {s["code"]: s for s in json.load(open("data/signs/signs.json"))}
ca_secs = {s["num"]: s for s in json.load(open("data/ca-mutcd/sections.json"))}
for f in glob.glob("src/content/docs/details/*/*.md"):
    os.remove(f)
dwg_pages = []
for c in cfg:
    d = json.load(open(f"data/docs/{c['slug'].replace('/', '__')}.json"))
    pages = {p["page"]: p for p in d["pages"]}
    # running section labels from bookmarks (level <= 2) for design guides
    doc = pymupdf.open(c["path"])
    toc = [t for t in doc.get_toc() if t[0] <= 2 and t[2] >= 1 and not t[1].startswith(("_", "section", "toc-", "typical-")) and not t[1].lower().endswith(".pdf")]
    run, cur = {}, ""
    tocd = {}
    for lvl, title, pg in toc:
        tocd.setdefault(pg, []).append(re.sub(r"\s+", " ", title).strip())
    for pno in range(1, len(doc) + 1):
        if pno in tocd:
            cur = tocd[pno][-1]
        run[pno] = cur
    # group sheets by primary drawing
    groups = {}
    AG = c.get("agency", "LADOT"); ag = AG.lower()
    os.makedirs(f"src/content/docs/details/{ag}", exist_ok=True)
    for p in d["pages"]:
        if p["image"] and p["drawings"] and not c.get("refs_only"):
            groups.setdefault(p["drawings"][0], []).append(p)
    doc_slug = slugify(c["short"])
    order = sorted(groups, key=lambda k: [int(x) for x in re.findall(r"\d+", k)])
    for i, k in enumerate(order):
        sheets = groups[k]
        meta = d.get("drawing_titles", {}).get(k, {})
        title = meta.get("title") or (sheets[0]["title"] or "").replace(f"({k})", "").strip() or "Standard drawing"
        slug = f"{doc_slug}-{slugify(k)}"
        url = f"{BASE}/details/{ag}/{slug}/"
        codes = sorted({x for p in sheets for x in p["sign_codes"]})
        secs = sorted({x for p in sheets for x in p["sections"]})
        kw = []
        for p in sheets:
            kw += [w for w in p["keywords"] if w not in kw]
        tops = topics_for(title + " " + " ".join(kw[:12]))
        dwg_pages.append((c, k, title, slug, url))
        prev_l = f'<a href="{BASE}/details/{ag}/{doc_slug}-{slugify(order[i-1])}/">&larr; {esc(order[i-1])}</a>' if i else ""
        next_l = f'<a href="{BASE}/details/{ag}/{doc_slug}-{slugify(order[i+1])}/">{esc(order[i+1])} &rarr;</a>' if i + 1 < len(order) else ""
        sheet_html = ""
        for j, p in enumerate(sheets, 1):
            sheet_html += (f'\n### Sheet {j} of {len(sheets)} (document page {p["page"]})\n\n'
                           f'<figure class="dfig"><a href="{p["image"]}" target="_blank"><img loading="lazy" src="{p["image"]}" alt="{esc(k)} sheet {j}"></a>'
                           f'<figcaption>{esc(c["short"])} {esc(k)}, sheet {j}. <a href="{p["url"]}">Open in the document</a>.</figcaption></figure>\n'
                           f'<details class="ocr"><summary>Notes and text on this sheet{" (OCR)" if p["ocr"] else ""}</summary><p>{esc(p["text"][:5000])}</p></details>\n')
        sign_html = "".join(f'<a class="tsign sref" href="{BASE}/signs/{signs[x]["slug"]}/" data-svg="{BASE}{signs[x]["svg"]}"><img loading="lazy" src="{BASE}{signs[x]["svg"]}" alt="{esc(x)}"><span><b>{esc(x)}</b> {esc(signs[x]["descriptor"][:40])}</span></a>' for x in codes if x in signs)
        sec_html = ", ".join(f'<a href="{ca_secs[x]["url"]}">CA MUTCD {esc(x)} {esc(ca_secs[x]["title"][:60])}</a>' for x in secs if x in ca_secs)
        top_html = " ".join(f'<a class="chip" href="{BASE}/topics/{t}/">{esc(TOPIC_NAME[t])}</a>' for t in tops)
        md = f'''---
title: "{k} {title.replace(chr(34), "'")}"
description: "{c['short']} standard drawing {k}: {title.replace(chr(34), "'")}. {len(sheets)} sheet(s){(', dated ' + meta['date']) if meta.get('date') else ''}."
tableOfContents: false
---

<div class="dwg-head"><div><span class="dwg-num">{esc(k)}</span><span class="dwg-src">{esc(c["title"])} &middot; {esc(c["edition"])}</span></div>
<div class="dwg-facts"><span><b>{len(sheets)}</b> sheet(s)</span>{f'<span>Dated <b>{esc(meta["date"])}</b></span>' if meta.get("date") else ""}<span>Pages {", ".join(str(p["page"]) for p in sheets)}</span></div></div>

<div class="dwg-nav">{prev_l} <a href="{BASE}/details/?src={esc(c["short"])}">All {esc(c["short"])} drawings</a> {next_l}</div>

{('<p class="dwg-topics">Topics: ' + top_html + '</p>') if top_html else ''}
{('<p>Referenced MUTCD sections: ' + sec_html + '</p>') if sec_html else ''}
{('<h2>Signs on this drawing</h2><div class="tsigns">' + sign_html + '</div>') if sign_html else ''}

## Sheets
{sheet_html}

<div class="kw">Keywords: {esc(", ".join(kw[:30]))}</div>
'''
        open(f"src/content/docs/details/{ag}/{slug}.md", "w").write(md)
        items.append({"src": c["short"], "sg": AG, "type": "Standard drawing", "num": k, "title": title, "img": sheets[0]["image"],
                      "url": url, "topics": tops, "date": meta.get("date", ""), "sheets": len(sheets), "signs": codes[:12],
                      "kw": " ".join(kw[:20])})
    # design-guide figure pages without a drawing number
    for p in d["pages"]:
        if p["image"] and not p["drawings"]:
            lab = run.get(p["page"], "")
            t = p["title"] or lab or f"Page {p['page']}"
            if lab and p["title"] and lab not in p["title"]:
                t = f"{lab}: {p['title']}"
            items.append({"src": c["short"], "sg": AG, "type": "Figure page", "num": f"p{p['page']}", "title": t[:150], "img": p["image"],
                          "url": p["url"], "topics": topics_for(t + " " + " ".join(p["keywords"][:8])), "signs": p["sign_codes"][:8],
                          "kw": " ".join(p["keywords"][:12])})

# small thumbnails for index grids
from PIL import Image
def thumb(url):
    if not url:
        return url
    rel = url.replace(BASE + "/", "", 1)
    src, dst = "public/" + rel, "public/thumbs/" + rel
    if not os.path.exists(dst) and os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im = Image.open(src); im.thumbnail((360, 360)); im.save(dst, "WEBP", quality=70)
    return BASE + "/thumbs/" + rel
for c in cfg:
    for p in json.load(open(f"data/docs/{c['slug'].replace('/', '__')}.json"))["pages"]:
        thumb(p["image"])
for it in items:
    it["full"] = it["img"]; it["img"] = thumb(it["img"])
json.dump(items, open("public/data/details.json", "w"), separators=(",", ":"))

# --------------- lookup resolver
look = {}
def add(k, label, url):
    look.setdefault(k.upper().replace(" ", ""), []).append([label, url])
for s in json.load(open("data/ca-mutcd/sections.json")):
    add(s["num"], f"CA MUTCD {s['num']} {s['title']}", s["url"])
for s in json.load(open("data/mutcd/sections.json")):
    add(s["num"], f"Federal MUTCD {s['num']} {s['title']}", s["url"])
for f in ca_figs:
    add(f["id"], f"CA MUTCD {f['kind']} {f['id']}", f["url"])
for f in fed_figs:
    add(f["id"], f"Federal {f['kind']} {f['id']}", f["url"])
for code, s in signs.items():
    add(code, f"Sign {code} {s['descriptor']}", f"{BASE}/signs/{s['slug']}/")
for c, k, title, slug, url in dwg_pages:
    add(k, f"{c['short']} {k} {title}", url)
    if k.endswith(".0"):
        add(k[:-2], f"{c['short']} {k} {title}", url)
json.dump(look, open("public/data/lookup.json", "w"), separators=(",", ":"))
json.dump([[c["short"], k, t, u] for c, k, t, s, u in dwg_pages], open("data/docs/drawing_pages.json", "w"))
from collections import Counter
print(len(items), Counter(i["type"] for i in items), "drawing pages", len(dwg_pages), "lookup keys", len(look))
