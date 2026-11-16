"""Topic hubs: one page per practice topic, pulling together CA MUTCD 2026, federal MUTCD 11th Ed. Rev. 1,
LADOT documents and drawings, signs and figures. Output: src/content/docs/topics/<slug>.md + index."""
import glob, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
ROOT, BASE = ".", "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
ca = json.load(open("data/ca-mutcd/sections.json"))
fed = {s["num"]: s for s in json.load(open("data/mutcd/sections.json"))}
figs = json.load(open("data/ca-mutcd/figures.json"))
signs = json.load(open("data/signs/signs.json"))
ladot_cfg = json.load(open("pipeline/config/ladot.json")) + json.load(open("pipeline/config/agencies.json"))
ladot = [json.load(open(f"data/docs/{c['slug'].replace('/', '__')}.json")) for c in ladot_cfg]

# ---- section bodies from the CA reader markdown
body = {}
for f in glob.glob("src/content/docs/ca-mutcd/*.md"):
    parts = re.split(r'<span id="([a-z0-9-]+)" class="anchor"></span>', open(f).read())
    for i in range(1, len(parts), 2):
        body[parts[i]] = parts[i + 1]
def provs(anchor):
    t = body.get(anchor, "")
    out = []
    for kind, inner in re.findall(r'<div class="prov (std|gui|opt|sup)"><div class="prov-label">[^<]*</div>(.*?)</div>\s*(?=<div class="prov|$|\n\n)', t, re.S):
        for p in re.findall(r"<p>(.*?)</p>", inner, re.S):
            txt = re.sub(r"<[^>]+>", "", p)
            txt = re.sub(r"^\s*\d+[a-z]?\s+", "", html.unescape(txt)).strip()
            out.append((kind, txt))
    return out
def excerpt(anchor):
    ps = provs(anchor)
    for want in ("std", "gui", "opt", "sup"):
        for k, t in ps:
            if k == want and len(t) > 30:
                return k, (t[:260] + "...") if len(t) > 260 else t, Counter(k for k, _ in ps)
    return None, "", Counter()
from collections import Counter

from topics_def import LABEL, T, CHAPS, GROUPS
TOPIC_RX_ALL = {t[0]: re.compile(t[4] + "|" + t[6], re.I) for t in T}
os.makedirs("src/content/docs/topics", exist_ok=True)
for f in glob.glob("src/content/docs/topics/*.md"):
    os.remove(f)
cards = []
DP = {(a, k): sl for a, k, t, sl in json.load(open("data/docs/drawing_pages.json"))}
ORDER = {sl: i for i, sl in enumerate([x for g in GROUPS for x in g[1]], 1)}
GROUP_OF = {x: g[0] for g in GROUPS for x in g[1]}
DET = json.load(open("public/data/details.json"))
GUIDES = [json.load(open(f"data/docs/{c['slug'].replace('/', '__')}.json")) | {"cfg": c} for c in json.load(open("pipeline/config/guides.json"))]
REF = json.load(open("data/refcards.json"))
for order, (slug, name, intro, sec_rx, fig_rx, sign_pref, ladot_rx, ladot_tags) in enumerate(T, 1):
    srx, frx, lrx = re.compile(sec_rx, re.I), re.compile(fig_rx, re.I), re.compile(ladot_rx, re.I)
    chs = CHAPS.get(slug, [])
    secs = [s for s in ca if s["chapter"] in chs or (srx.search(s["title"]) and not s["num"].startswith(("1", "A", "2E", "2F", "2J", "2K", "2L", "2M", "3F", "4P", "4R", "4Q")))]
    if slug not in ("temporary-traffic-control", "accessibility"):
        secs = [s for s in secs if not s["num"].startswith("6")]
    if slug not in ("rail-crossings",):
        secs = [s for s in secs if not s["num"].startswith("8")]
    if slug not in ("school-zones",):
        secs = [s for s in secs if not s["num"].startswith("7")] if slug not in ("crosswalks", "speed-and-calming") else secs
    # rules table grouped by part
    rows = []
    stats = Counter()
    for s in secs[:110]:
        k, ex, c = excerpt(s["anchor"])
        stats.update(c)
        f = fed.get(s["num"].replace("(CA)", ""))
        fedlink = f'<a href="{f["url"]}">Federal {esc(f["num"])}</a>' if f else '<span class="muted">CA only</span>' if "(CA)" in s["num"] else '<span class="muted">-</span>'
        badge = '<span class="badge ca-amend">CA amended</span>' if s["ca_changes"] else ""
        cnt = " ".join(f'<span class="pc {kk}">{c[kk]} {LABEL[kk].lower()}</span>' for kk in ("std", "gui", "opt") if c[kk])
        rows.append(f'<tr><td><a href="{s["url"]}"><strong>{esc(s["num"])}</strong></a></td><td><a href="{s["url"]}">{esc(s["title"])}</a> {badge}<div class="tex {k or ""}">{("<b>" + LABEL[k] + ":</b> ") if k else ""}{esc(ex)}</div><div class="pcs">{cnt}</div></td><td>{fedlink}</td></tr>')
    # figures
    fg = [x for x in figs if frx.search(x["title"]) and x.get("image") and not x["chapter"].startswith(("6", "8")) or (slug in ("temporary-traffic-control",) and x["chapter"].startswith("6") and frx.search(x["title"])) or (slug == "rail-crossings" and x["chapter"].startswith("8") and frx.search(x["title"]))]
    seen, fgu = set(), []
    for x in fg:
        if x["image"] not in seen:
            seen.add(x["image"]); fgu.append(x)
    fhtml = "".join(f'<a class="tfig" href="{x["url"]}"><img loading="lazy" src="{BASE}/thumbs{x["image"]}" alt="{esc(x["kind"])} {esc(x["id"])}"><span><b>{esc(x["kind"])} {esc(x["id"])}</b> {esc(x["title"][:90])}</span></a>' for x in fgu[:24])
    # signs
    sg = [s for s in signs if any(s["code"].startswith(p) and (p.endswith("-") or len(s["code"]) == len(p) or not s["code"][len(p)].isdigit()) for p in sign_pref) or (frx.search(s["name"]) and s["category"] != "Temporary Traffic Control Signs" if slug != "temporary-traffic-control" else False)]
    sg = sorted(sg, key=lambda s: (s.get("ca_status") == "not adopted", s["code"]))[:72]
    shtml = "".join(f'<a class="tsign sref" href="{BASE}/signs/{s["slug"]}/" data-svg="{BASE}{s["svg"]}"><img loading="lazy" src="{BASE}{s["svg"]}" alt="{esc(s["code"])}"><span><b>{esc(s["code"])}</b> {esc(s.get("descriptor", s["name"]))[:48]}</span></a>' for s in sg)
    # LADOT drawings + pages
    lrows, lpages = [], []
    for d in ladot:
        for k, v in d["drawings"].items():
            t = d.get("drawing_titles", {}).get(k, {}).get("title", "")
            if t and lrx.search(t):
                lrows.append(f'<tr><td><strong>{esc(k)}</strong></td><td>{esc(t)}</td><td>{esc(d["short"])}</td><td><a href="{DP[(d['short'], k)] if (d['short'], k) in DP else (BASE + '/' + d['slug'] + '/' + v[0]['chapter'] + '/#p' + str(v[0]['page']))}">open drawing</a></td></tr>')
        for p in d["pages"]:
            if p["image"] and (lrx.search(p["title"] or "") or (ladot_tags and set(ladot_tags) <= set(p["topics"]) and len(p["topics"]) <= 3)):
                lpages.append((d["short"], p))
    lthumbs = "".join(f'<a class="tfig" href="{p["url"]}"><img loading="lazy" src="{p["image"].replace("/figs/", "/thumbs/figs/")}" alt="{esc(a)} page {p["page"]}"><span><b>{esc(a)}</b> p{p["page"]} {esc((p["title"] or "")[:70])}</span></a>' for a, p in lpages[:30])
    # federal guidance pages (FHWA, Access Board)
    gp = []
    for d in GUIDES:
        for p in d["pages"]:
            if TOPIC_RX_ALL[slug].search((p["title"] or "") + " " + " ".join(p["keywords"][:6])):
                gp.append((d, p))
    ghtml = "".join(f'<li><a href="{p["url"]}">{esc(d["short"])}, page {p["page"]}{(": " + esc(p["title"][:90])) if p["title"] else ""}</a></li>' for d, p in gp[:25])
    # outline-only design guides
    rr = []
    for g in REF:
        for e in g["entries"]:
            if slug in e["topics"]:
                rr.append(f'<li><a href="{BASE}/guides/{g["slug"]}/">{esc(g["short"])}</a>: {esc(e["title"])} <span class="src-page">PDF p. {e["page"]}{("-" + str(e["end"])) if e["end"] > e["page"] else ""}</span></li>')
    q = f"Compare what CA MUTCD 2026, the federal MUTCD and LADOT say about {name.lower()}; note conflicts and which governs."
    md = f'''---
title: "{name}"
description: "{intro}"
sidebar:
  order: {ORDER.get(slug, 99)}
---

<div class="crumb"><a href="{BASE}/topics/">Topics</a> &rsaquo; {GROUP_OF.get(slug, "")}</div>

<div class="topic-intro">{esc(intro)}</div>
{('<p><a class="ai-btn" href="' + BASE + '/ladot/curb-paint/">LADOT curb paint, red curb distances and the S-481.0 calculator</a></p>') if slug == "curb-parking-loading" else ''}{('<p><a class="ai-btn" href="' + BASE + '/markings/line-types/">Line Type Database: every Caltrans striping detail</a></p>') if slug == "striping-intersections" else ''}

<div class="topic-stats"><span><b>{len(secs)}</b> CA MUTCD sections</span><span><b>{stats["std"]}</b> standards (shall)</span><span><b>{stats["gui"]}</b> guidance (should)</span><span><b>{stats["opt"]}</b> options (may)</span><span><b>{len(sg)}</b> signs</span><span><b>{len(lrows)}</b> local standard drawings</span></div>

<p><a class="ai-btn ghost" href="{BASE}/details/?topic={slug}">Browse all {sum(1 for x in DET if slug in x["topics"])} figures and drawings on this topic</a> <a class="ai-btn" href="{BASE}/ask/?q={html.escape(q.replace(" ", "%20"))}">Ask Claude to compare all sources on this topic</a></p>

## The rules

CA MUTCD 2026 governs in California. Each row shows the section's first Standard (or Guidance, when there is no Standard), how many shall, should and may provisions it has, and the matching federal section. Open a section and use **Explain with Claude** there to see the CA and federal differences.

<table class="trules"><thead><tr><th>CA MUTCD</th><th>Section and key provision</th><th>Federal 11th Ed. R1</th></tr></thead><tbody>{"".join(rows)}</tbody></table>

## Local agency standards (LADOT, Burbank, Pasadena)

{("<table class=\"dwtab\"><thead><tr><th>Drawing</th><th>Title</th><th>Document</th><th></th></tr></thead><tbody>" + "".join(lrows) + "</tbody></table>") if lrows else "<p class=\"muted\">No LADOT standard drawing is titled for this topic; see the pages below and search.</p>"}

{("<div class=\"tgrid\">" + lthumbs + "</div>") if lthumbs else ""}

## Federal guidance (FHWA, U.S. Access Board)

{("<ul>" + ghtml + "</ul>") if ghtml else "<p class=\"muted\">No FHWA or Access Board page on this topic yet.</p>"}

## National design guides (NACTO, CPBS)

These are copyrighted, so only their headings and page numbers are listed.

{("<ul class=\"reflist\">" + "".join(rr[:30]) + "</ul>") if rr else "<p class=\"muted\">No matching heading.</p>"}

## Figures

{("<div class=\"tgrid\">" + fhtml + "</div>") if fhtml else "<p class=\"muted\">No CA MUTCD figure is titled for this topic.</p>"}

## Signs

<div class="tsigns">{shtml}</div>

<p><a href="{BASE}/signs/">Open the full Sign Library</a></p>
'''
    open(f"src/content/docs/topics/{slug}.md", "w").write(md)
    cards.append((slug, f'<a class="tcard" href="{BASE}/topics/{slug}/"><b>{esc(name)}</b><span>{esc(intro)}</span><em>{len(secs)} sections &middot; {len(sg)} signs &middot; {len(lrows)} LADOT drawings</em></a>'))
    print(slug, len(secs), len(fgu), len(sg), len(lrows), len(lpages))
open("src/content/docs/topics/index.md", "w").write(f'''---
title: Topics
description: Practice topics that pull together CA MUTCD 2026, federal MUTCD, LADOT and the sign library.
tableOfContents: false
sidebar:
  order: 0
  label: All topics
---

Each topic page gathers every source on one subject: CA MUTCD 2026 sections with their key provisions, the matching federal sections, LADOT standard drawings and pages, figures and signs.

{"".join("<h2>" + g + "</h2><div class=\"tcards\">" + "".join(c for sl, c in cards if sl in m) + "</div>" for g, m in GROUPS)}
''')

NAMES = {t[0]: t[1] for t in T}
json.dump([{"group": g, "topics": [{"slug": x, "name": NAMES[x]} for x in m]} for g, m in GROUPS], open("data/topics.json", "w"))
