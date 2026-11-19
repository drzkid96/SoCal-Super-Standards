"""Sophisticated indexing for SoCal Super Standards.

1. Tags every indexed item (drawings, figures, tables, markings, line types, design-guide pages, signs) with
   concepts from the domain thesaurus (pipeline/glossary.py), expanding search keywords with synonyms.
2. Builds a cross-reference graph between standard drawings (refers to / referred to by), links Caltrans
   striping details named in notes, and finds similar drawings at other agencies (IDF-weighted concept overlap).
3. Writes the A-Z Keyword Index page (/keywords/), public/data/glossary.json, and adds concept terms to lookup.json.
4. Rewrites the index block at the foot of every standard drawing page and weights summaries for site search.
"""
import glob, html, json, math, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glossary import LIST, CATS
from topics_def import T

BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=True)
nk = lambda t: re.sub(r"(?<=[a-z])(es|s)$", "", re.sub(r"[^a-z0-9]+", "", t.lower()))
slugify = lambda t: re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
TOPIC_NAME = {t[0]: t[1] for t in T}

# ------------------------------------------------------------------ concept matchers
def term_re(t):
    t = t.strip()
    body = re.escape(t).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]?")
    abbr = len(t) <= 6 and re.fullmatch(r"[A-Z0-9&/().\-]+", t) and re.search(r"[A-Z]", t)
    tail = "" if abbr else r"(?:s|es)?"
    return body + tail, bool(abbr)

MATCH = []
for c in LIST:
    cs, ci = [], []
    for t in [c["term"]] + c["aka"]:
        r, a = term_re(t)
        (cs if a else ci).append(r)
    pats = []
    if ci:
        pats.append(re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(sorted(ci, key=len, reverse=True)) + r")(?![A-Za-z0-9])", re.I))
    if cs:
        pats.append(re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(sorted(cs, key=len, reverse=True)) + r")(?![A-Za-z0-9])"))
    MATCH.append((c, pats))
CBY = {c["id"]: c for c in LIST}

def concepts(strong_text, weak_text=""):
    s, w = [], []
    for c, pats in MATCH:
        n1 = sum(len(p.findall(strong_text)) for p in pats)
        if n1:
            s.append(c["id"]); continue
        if weak_text:
            n2 = sum(len(p.findall(weak_text)) for p in pats)
            if n2 >= 2:
                w.append(c["id"])
    return s, w

# ------------------------------------------------------------------ data
det = json.load(open("public/data/details.json"))
_dj = json.load(open("data/dups.json")) if os.path.exists("data/dups.json") else {"dups": {}, "blank": []}
DROP = set(_dj["dups"]) | set(_dj["blank"])
signs = json.load(open("public/data/signs-index.json"))
lookup = json.load(open("public/data/lookup.json"))
lt_ids = {x["detail"].upper(): x["url"] for x in json.load(open("public/data/linetypes.json"))}

DWG_URL = {(i["src"], i["num"]): i["url"] for i in det if i["type"] == "Standard drawing"}
# clean notes and raw text per drawing url
notes_by_url, raw_by_url = defaultdict(str), defaultdict(str)
for f in glob.glob("data/docs/*__*.json"):
    d = json.load(open(f))
    for p in d.get("pages", []):
        if not (p.get("image") and p.get("drawings")):
            continue
        url = DWG_URL.get((d.get("short"), p["drawings"][0]))
        if not url:
            continue
        cl = p.get("clean") or {}
        notes_by_url[url] += "\n" + (cl.get("notes") or "") + "\n" + (cl.get("description") or "")
        raw_by_url[url] += "\n" + (p.get("text") or "")

# ------------------------------------------------------------------ tag every item
for i in det:
    strong = " ".join([i.get("num", ""), i.get("title", ""), i.get("kw", ""), i.get("sum", ""), " ".join(i.get("signs", []))])
    weak = notes_by_url.get(i["url"], "") if i["type"] == "Standard drawing" else ""
    s, w = concepts(strong, weak)
    i["c"] = s + w
    i["cs"] = s
    terms = []
    for cid in s:
        terms += [CBY[cid]["term"]] + CBY[cid]["aka"]
    for cid in w:
        terms.append(CBY[cid]["term"])
    terms += [TOPIC_NAME.get(t, t) for t in i.get("topics", [])]
    terms += [signs[x]["descriptor"] for x in i.get("signs", []) if x in signs]
    seen, kx = set(), []
    for t in terms:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl); kx.append(tl)
    i["kx"] = " | ".join(kx)
    i["el"] = sorted({CATS[CBY[cid]["cat"]] for cid in s})

sign_c = {}
for code, rec in signs.items():
    s, _ = concepts(code + " " + rec.get("descriptor", ""))
    sign_c[code] = s

# ------------------------------------------------------------------ cross references between drawings
dwgs = [i for i in det if i["type"] == "Standard drawing"]
PRI = ["MPP 531", "MPP 521", "Red Book"]
reg = defaultdict(list)
for i in dwgs:
    reg[(i["sg"], i["num"].upper())].append(i)
def resolve(sg, num, src):
    for k in (num, num + ".0"):
        c = reg.get((sg, k.upper()), [])
        if c:
            same = [x for x in c if x["src"] == src]
            if same:
                return same[0]
            return sorted(c, key=lambda x: PRI.index(x["src"]) if x["src"] in PRI else 9)[0]
    return None
REF_RE = re.compile(r"(?<![A-Z0-9])(S-\d{1,3}(?:\.\d+){0,3}|BT-\d{3}[A-Z]?(?:-\d)?|(?:RSP\s)?A\d{2}[A-F])(?![\w.])")
DET_RE = re.compile(r"\bDetails?\s+(\d{1,2}[A-D]?)(?:\s*(?:,|and|&|to)\s*(\d{1,2}[A-D]?))*", re.I)
refs, refby, ctdet = defaultdict(list), defaultdict(list), defaultdict(list)
for i in dwgs:
    txt = notes_by_url.get(i["url"], "") + " " + i.get("sum", "") + " " + raw_by_url.get(i["url"], "")
    for m in REF_RE.finditer(txt):
        num = m.group(1).replace("RSP ", "")
        tgt = resolve(i["sg"], num, i["src"])
        if tgt and tgt["url"] != i["url"] and tgt not in refs[i["url"]]:
            refs[i["url"]].append(tgt)
            refby[tgt["url"]].append(i)
    clean_txt = notes_by_url.get(i["url"], "") + " " + i.get("sum", "")
    for m in DET_RE.finditer(clean_txt):
        for g in re.findall(r"\d{1,2}[A-D]?", m.group(0)):
            if g.upper() in lt_ids and g.upper() not in ctdet[i["url"]]:
                ctdet[i["url"]].append(g.upper())

# similar drawings (IDF-weighted overlap of strong concepts)
df = Counter(c for i in dwgs for c in set(i["cs"]))
N = len(dwgs)
idf = {c: math.log((N + 1) / (n + 0.5)) for c, n in df.items()}
def sim(a, b):
    A, B = set(a["cs"]), set(b["cs"])
    if not A or not B:
        return 0
    inter = sum(idf[c] for c in A & B)
    uni = sum(idf[c] for c in A | B)
    return inter / uni if uni else 0
similar = {}
for i in dwgs:
    sc = sorted(((sim(i, j), j) for j in dwgs if j is not i), key=lambda x: -x[0])
    other = [j for s, j in sc if s >= 0.28 and j["src"] != i["src"]][:6]
    same = [j for s, j in sc if s >= 0.35 and j["src"] == i["src"]][:4]
    similar[i["url"]] = (other, same)

# ------------------------------------------------------------------ drawing page index blocks
def dlink(j):
    return f'<a class="xchip" href="{j["url"]}"><b>{esc(j["num"])}</b> {esc(j["title"][:70])}<span>{esc(j["src"])}</span></a>'
ag_dir = {}
for i in dwgs:
    rel = i["url"].replace(BASE + "/", "", 1).rstrip("/")
    mdp = f"src/content/docs/{rel}.md"
    if not os.path.exists(mdp):
        continue
    s = open(mdp).read()
    kw_raw = re.search(r'<div class="kw">Keywords: (.*?)</div>', s)
    kws0 = [k.strip() for k in html.unescape(re.sub(r"<[^>]+>", "", kw_raw.group(1))).split(",") if k.strip()] if kw_raw else []
    kws, kwl = [], set()
    for k in kws0:
        if nk(k) not in kwl:
            kwl.add(nk(k)); kws.append(k)
    aka = []
    for cid in i["cs"]:
        for t in [CBY[cid]["term"]] + CBY[cid]["aka"]:
            if nk(t) not in kwl:
                kwl.add(nk(t)); aka.append(t)
    rows = []
    if kws:
        rows.append(("Keywords", " ".join(f'<a class="kchip" href="{BASE}/details/?q={esc(k)}">{esc(k)}</a>' for k in kws)))
    if aka:
        rows.append(("Also searched as", ", ".join(esc(a) for a in aka[:40])))
    if i["c"]:
        bycat = defaultdict(list)
        for cid in i["c"]:
            bycat[CBY[cid]["cat"]].append(cid)
        rows.append(("Index entries", " &middot; ".join(
            f'{esc(CATS[cat])}: ' + ", ".join(f'<a href="{BASE}/keywords/#c-{cid}">{esc(CBY[cid]["term"])}</a>' for cid in ids)
            for cat, ids in bycat.items())))
    if refs[i["url"]]:
        rows.append(("Refers to", "".join(dlink(j) for j in refs[i["url"]][:12])))
    if refby[i["url"]]:
        rows.append(("Referred to by", "".join(dlink(j) for j in refby[i["url"]][:12])))
    if ctdet[i["url"]]:
        rows.append(("Caltrans striping details named", " ".join(
            f'<a class="kchip dref" href="{lt_ids[d]}" data-svg="{BASE}/linetypes/detail-{d.lower()}.svg">Detail {d}</a>' for d in ctdet[i["url"]])))
    oth, same = similar[i["url"]]
    if oth:
        rows.append(("Similar drawings at other agencies", "".join(dlink(j) for j in oth)))
    if same:
        rows.append((f"Related in {i['src']}", "".join(dlink(j) for j in same)))
    block = ('<section class="xidx-wrap" data-pagefind-weight="4"><h2 id="index-and-related">Index and related drawings</h2><dl class="xidx">'
             + "".join(f"<div><dt>{esc(a)}</dt><dd>{b}</dd></div>" for a, b in rows) + "</dl></section>")
    s = re.sub(r'<section class="xidx-wrap".*?</section>', lambda _: block, s, flags=re.S) if 'class="xidx-wrap"' in s else \
        re.sub(r'<div class="kw">Keywords: .*?</div>', lambda _: block, s, count=1, flags=re.S)
    s = s.replace('<p class="dwg-sum">', '<p class="dwg-sum" data-pagefind-weight="6">')
    open(mdp, "w").write(s)

# ------------------------------------------------------------------ keyword index page
TYPES = [("Standard drawing", "Standard drawings", 60), ("Line type", "Caltrans striping details", 12), ("Marking", "Pavement markings", 10),
         ("Figure", "Manual figures", 10), ("Table", "Manual tables", 6), ("Figure page", "Design guide and document pages", 10)]
by_c = defaultdict(list)
for i in det:
    for cid in i["c"]:
        by_c[cid].append(i)
sign_by_c = defaultdict(list)
for code, cs in sign_c.items():
    for cid in cs:
        sign_by_c[cid].append(code)

def item_li(i):
    lab = i["num"] if i["type"] not in ("Figure page",) else ""
    return f'<li><a href="{i["url"]}">{("<b>" + esc(lab) + "</b> ") if lab else ""}{esc(i["title"][:90])}</a> <span class="ksrc">{esc(i["src"])}</span></li>'

entries = []
for c in sorted(LIST, key=lambda c: c["term"].lower()):
    items = by_c.get(c["id"], [])
    sg = sign_by_c.get(c["id"], [])
    if not items and not sg:
        continue
    parts = []
    for ty, lab, cap in TYPES:
        xs = [i for i in items if i["type"] == ty]
        if ty == "Figure":
            xs.sort(key=lambda i: 0 if i["src"].startswith("CA") else 1)
        if ty == "Standard drawing":
            xs.sort(key=lambda i: (0 if c["id"] in i["cs"] else 1, i["src"], i["num"]))
        _seen, _xs = set(), []
        for x in xs:
            key = (re.sub(r"[^a-z0-9]+", " ", (x["num"] + " " + x["title"]).lower() if x["type"] != "Figure page" else x["title"].lower()).strip(), x["src"])
            if key not in _seen:
                _seen.add(key); _xs.append(x)
        xs = _xs
        if not xs:
            continue
        more = f'<li class="kmore"><a href="{BASE}/details/?q={esc(c["term"])}&type={esc(ty).replace(" ", "+")}">All {len(xs)} in the Detail Index</a></li>' if len(xs) > cap else ""
        parts.append(f'<div class="kgrp"><h4>{lab} <span>{len(xs)}</span></h4><ul>{"".join(item_li(i) for i in xs[:cap])}{more}</ul></div>')
    if sg:
        sg = sorted(sg)[:24]
        parts.append('<div class="kgrp"><h4>Signs <span>' + str(len(sign_by_c[c["id"]])) + '</span></h4><p class="ksigns">' + " ".join(
            f'<a class="sref" href="{signs[x]["url"]}" data-svg="{signs[x]["svg"]}">{esc(x)}</a>' for x in sg) + "</p></div>")
    n = len(items) + len(sign_by_c.get(c["id"], []))
    entries.append((c, n, f'<div class="kentry" id="c-{c["id"]}" data-q="{esc((c["term"] + " " + " ".join(c["aka"])).lower())}">'
                          f'<h3>{esc(c["term"])} <span class="kcat">{esc(CATS[c["cat"]])}</span><span class="kn">{n}</span></h3>'
                          f'<p class="kaka">Also: {esc(", ".join(c["aka"]))}</p>{"".join(parts)}</div>'))

# drawing keywords A to Z (terms not already covered by a concept)
covered, KFORM = set(), {}
for c in LIST:
    covered |= {nk(c["term"])} | {nk(a) for a in c["aka"]}
kwmap = defaultdict(list)
url_by_title = {}
for i in det:
    if i["type"] in ("Standard drawing", "Figure page"):
        url_by_title[i["url"]] = i
# map clean units to items through their keywords: use details.json kw which holds the cleaned keywords joined by spaces,
# so rebuild from the clean data per page record instead
for f in glob.glob("data/docs/*__*.json"):
    d = json.load(open(f))
    for p in d.get("pages", []):
        cl = p.get("clean")
        if not cl or p["url"] in DROP:
            continue
        url = (DWG_URL.get((d.get("short"), p["drawings"][0])) if p.get("image") and p.get("drawings") else None) or p["url"]
        it = url_by_title.get(url)
        lab = (it["num"] + " " + it["title"]) if it and it["type"] == "Standard drawing" else (cl.get("title") or p.get("title") or "")
        src = it["src"] if it else d.get("short", "")
        for k in cl.get("keywords", []):
            k = k.strip().lower()
            if len(k) < 3 or nk(k) in covered:
                continue
            k = KFORM.setdefault(nk(k), k)
            if url in DROP or url in [a for a, _, _ in kwmap[k]] or (lab.lower(), src) in [(b.lower(), c) for _, b, c in kwmap[k]]:
                continue
            if True:
                kwmap[k].append((url, lab, src))
kw_rows = []
for k in sorted(kwmap, key=lambda x: re.sub(r"^[^a-z0-9]+", "", x)):
    v = kwmap[k]
    kw_rows.append(f'<li data-q="{esc(k)}"><b>{esc(k)}</b> ' + "; ".join(f'<a href="{u}">{esc(l[:70])}</a> <span class="ksrc">{esc(s)}</span>' for u, l, s in v[:8]) + "</li>")

letters = sorted({c["term"][0].upper() for c, _, _ in entries})
by_letter = defaultdict(list)
for c, n, h in entries:
    by_letter[c["term"][0].upper()].append(h)
cat_nav = "".join(f'<div><b>{esc(CATS[cat])}</b> ' + ", ".join(f'<a href="#c-{c["id"]}">{esc(c["term"])}</a>' for c, _, _ in entries if c["cat"] == cat) + "</div>" for cat in CATS)
body = "".join(f'<h2 id="l-{L}">{L}</h2>' + "".join(by_letter[L]) for L in letters)
md = f'''---
title: Keyword Index
description: A to Z index of design concepts across every standard drawing, manual figure, table, marking, line type, sign and design-guide page on the site, with synonyms and abbreviations.
tableOfContents: false
---

<div class="sfilter kfilter"><input id="kq" type="search" placeholder="Filter the index: cat tracks, RRFB, bulb-out, pull box, 2WLTL..."><span id="kcount">{len(entries)} index entries &middot; {len(kw_rows)} drawing keywords</span></div>

Each entry gathers every drawing, figure, table, marking and sign on the site that deals with one design concept, under the name you are most likely to search plus its synonyms and abbreviations. Drawings that name the concept in their title, summary or keywords are listed first; drawings that only mention it in their notes follow. The same synonyms power the Detail Index filter and site search.

<nav class="knav">{" ".join(f'<a href="#l-{L}">{L}</a>' for L in letters)} <a href="#kw-az">Drawing keywords</a></nav>

<details class="kcats"><summary>Browse by category</summary>{cat_nav}</details>

{body}

<h2 id="kw-az">Drawing keywords, A to Z</h2>

Plain-language keywords written for each drawing and scanned page, other than the index entries above.

<ul class="kwaz">{"".join(kw_rows)}</ul>

<script>
(function(){{const q=document.getElementById('kq'),n=document.getElementById('kcount');const E=[...document.querySelectorAll('.kentry, .kwaz li')];
q.addEventListener('input',()=>{{const w=q.value.toLowerCase().trim();let c=0;E.forEach(el=>{{const ok=!w||el.dataset.q.includes(w)||el.textContent.toLowerCase().includes(w);el.style.display=ok?'':'none';if(ok)c++}});n.textContent=c+' matches'}});
const go=()=>{{if(location.hash){{const t=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(t)t.scrollIntoView()}}}};let user=false;['wheel','touchstart','keydown'].forEach(ev=>addEventListener(ev,()=>{{user=true}},{{once:true,passive:true}}));const g2=()=>{{if(!user)go()}};[0,300,900,1800,3000].forEach(ms=>setTimeout(g2,ms));addEventListener('load',g2);addEventListener('hashchange',go);}})();
</script>
'''
os.makedirs("src/content/docs/keywords", exist_ok=True)
open("src/content/docs/keywords/index.md", "w").write(md)

# ------------------------------------------------------------------ data files
json.dump([{"id": c["id"], "cat": CATS[c["cat"]], "term": c["term"], "aka": c["aka"]} for c in LIST], open("public/data/glossary.json", "w"))
norm = lambda s: re.sub(r"\s+", "", s.upper())
for c, n, _ in entries:
    for t in [c["term"]] + c["aka"]:
        k = norm(t)
        ent = [f"Keyword Index: {c['term']} ({n})", f"{BASE}/keywords/#c-{c['id']}"]
        if ent not in lookup.get(k, []):
            lookup.setdefault(k, []).append(ent)
for i in det:
    i.pop("cs", None)
json.dump(det, open("public/data/details.json", "w"))
json.dump(lookup, open("public/data/lookup.json", "w"))
print("concepts used", len(entries), "of", len(LIST), "| tagged items", sum(1 for i in det if i["c"]), "of", len(det),
      "| refs", sum(len(v) for v in refs.values()), "| striping detail links", sum(len(v) for v in ctdet.values()),
      "| similar", sum(1 for v in similar.values() if v[0]), "| drawing keywords", len(kw_rows))
