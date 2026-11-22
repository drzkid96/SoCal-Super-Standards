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
    is_code = bool(re.search(r"[A-Z]+\d+-\d+", t))
    if is_code:
        body = re.escape(t)
    else:
        body = re.escape(t).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]?")
    abbr = len(t) <= 6 and re.fullmatch(r"[A-Z0-9&/().\-]+", t) and re.search(r"[A-Z]", t)
    tail = "" if (abbr or is_code) else r"(?:s|es)?"
    return body + tail, bool(abbr or is_code)

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

# similar drawings (IDF-weighted strong concepts + shared signs + shared topics)
df = Counter(c for i in dwgs for c in set(i["cs"]))
N = len(dwgs)
idf = {c: math.log((N + 1) / (n + 0.5)) for c, n in df.items()}
def sim(a, b):
    A, B = set(a["cs"]), set(b["cs"])
    c_sc = 0.0
    if A and B:
        inter = sum(idf[c] for c in A & B)
        uni = sum(idf[c] for c in A | B)
        c_sc = inter / uni if uni else 0.0
    SA, SB = set(a.get("signs") or []), set(b.get("signs") or [])
    s_sc = (len(SA & SB) / len(SA | SB)) if (SA and SB) else 0.0
    TA, TB = set(a.get("topics") or []), set(b.get("topics") or [])
    t_sc = (len(TA & TB) / len(TA | TB)) if (TA and TB) else 0.0
    if not c_sc and s_sc < 0.25:
        return 0.0
    return 0.72 * c_sc + 0.20 * s_sc + 0.08 * t_sc

SRC_PRI = {"Caltrans Std. Plans 2026": 0, "MPP 531": 1, "MPP 521": 2, "Red Book": 3, "Burbank Std. Plans": 4, "Pasadena Std. Plans": 5, "Caltrans Std. Plans 2018": 9}
similar = {}
same_num_map = {}
for i in dwgs:
    num_u = i["num"].upper()
    is_2018 = i["src"] == "Caltrans Std. Plans 2018"
    same_num = [j for j in dwgs if j is not i and j["sg"] == i["sg"] and j["num"].upper() == num_u]
    same_num.sort(key=lambda x: SRC_PRI.get(x["src"], 6))
    same_num_map[i["url"]] = same_num

    sc = sorted(((sim(i, j), j) for j in dwgs if j is not i), key=lambda x: (-x[0], SRC_PRI.get(x[1]["src"], 6)))
    other, seen_o = [], set()
    same, seen_s = [], set()
    for s_val, j in sc:
        if j["num"].upper() == num_u and j["sg"] == i["sg"]:
            continue
        if j["src"] == "Caltrans Std. Plans 2018" and not is_2018:
            continue
        if j["sg"] != i["sg"] and s_val >= 0.26:
            k = (j["sg"], j["num"].upper())
            if k not in seen_o:
                seen_o.add(k); other.append(j)
                if len(other) >= 6:
                    pass
        elif j["sg"] == i["sg"] and s_val >= 0.30:
            k = j["num"].upper()
            if k not in seen_s:
                seen_s.add(k); same.append(j)
    similar[i["url"]] = (other[:6], same[:6])

# match bulletins to drawings
buls = [x for x in det if x.get("type") == "Bulletin"]
def match_bulletins(item):
    it_t = set(item.get("topics") or [])
    it_c = set(item.get("cs") or [])
    scored = []
    for b in buls:
        bt = set(b.get("topics") or [])
        bc = set(b.get("cs") or [])
        ov_c = len(it_c & bc)
        ov_t = len(it_t & bt)
        if not (ov_c >= 2 or (ov_c >= 1 and ov_t >= 1)):
            continue
        ag_bonus = 1.2 if (item.get("sg") == b.get("sg")) else 0.0
        scored.append((ov_c * 2.2 + ov_t * 0.9 + ag_bonus, b))
    scored.sort(key=lambda x: (-x[0], x[1]["num"]))
    return [b for _, b in scored[:4]]

# ------------------------------------------------------------------ drawing page index & related blocks
def trunc(s, n=66):
    s = str(s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(" ,;:-(")
    return (cut or s[:n].rstrip()) + "\u2026"

def dlink(j, show_date=False):
    sup = ' <em class="xchip-sup">superseded</em>' if j["src"] == "Caltrans Std. Plans 2018" else ""
    dt = f' &middot; {esc(j["date"])}' if (show_date and j.get("date")) else ""
    return f'<a class="xchip" href="{j["url"]}"><b>{esc(j["num"])}</b> {esc(trunc(j["title"], 68))}<span>{esc(j["src"])}{dt}</span>{sup}</a>'

for i in dwgs:
    rel = i["url"].replace(BASE + "/", "", 1).rstrip("/")
    mdp = f"src/content/docs/{rel}.md"
    if not os.path.exists(mdp):
        continue
    s = open(mdp).read()

    rel_rows = []
    if same_num_map[i["url"]]:
        rel_rows.append(("Also published in", "".join(dlink(j, show_date=True) for j in same_num_map[i["url"]][:6])))
    if refs[i["url"]]:
        rel_rows.append(("Refers to", "".join(dlink(j) for j in refs[i["url"]][:12])))
    if refby[i["url"]]:
        rel_rows.append(("Referred to by", "".join(dlink(j) for j in refby[i["url"]][:12])))
    if ctdet[i["url"]]:
        rel_rows.append(("Caltrans striping details", " ".join(
            f'<a class="kchip dref" href="{lt_ids[d]}" data-svg="{BASE}/linetypes/detail-{d.lower()}.svg">Detail {d}</a>' for d in ctdet[i["url"]])))
    oth, same = similar[i["url"]]
    if same:
        rel_rows.append((f"Related in {i['sg']}", "".join(dlink(j) for j in same)))
    if oth:
        rel_rows.append(("Similar at other agencies", "".join(dlink(j) for j in oth)))
    mbuls = match_bulletins(i)
    if mbuls:
        rel_rows.append(("Related bulletins & memos", "".join(
            f'<a class="xchip" href="{b["url"]}"><b>{esc(b["num"])}</b> {esc(trunc(b["title"], 64))}<span>{esc(b["src"])}</span></a>' for b in mbuls)))
    if i.get("topics"):
        rel_rows.append(("Topics", " ".join(
            f'<a class="kchip tchip" href="{BASE}/topics/{t}/">{esc(TOPIC_NAME.get(t, t))}</a>' for t in i["topics"])))
    idx_c = i["cs"] or i["c"][:6]
    if idx_c:
        bycat = defaultdict(list)
        for cid in idx_c[:10]:
            bycat[CBY[cid]["cat"]].append(cid)
        rel_rows.append(("Index entries", " &middot; ".join(
            f'<b>{esc(CATS[cat])}:</b> ' + ", ".join(f'<a href="{BASE}/keywords/#c-{cid}">{esc(CBY[cid]["term"])}</a>' for cid in ids)
            for cat, ids in bycat.items())))

    block = (
        '<section class="xidx-wrap" data-pagefind-weight="4">'
        '<h2 id="index-and-related">Related standards and index</h2>'
        '<dl class="xidx">' + "".join(f"<div><dt>{esc(a)}</dt><dd>{b}</dd></div>" for a, b in rel_rows) + "</dl>"
        "</section>"
    ) if rel_rows else ""

    if 'class="xidx-wrap"' in s:
        s = re.sub(r'<section class="xidx-wrap".*?</section>', lambda _: block, s, flags=re.S)
    elif '<div class="kw">' in s:
        s = re.sub(r'<div class="kw">Keywords: .*?</div>', lambda _: block, s, count=1, flags=re.S)
    elif block:
        s = s.rstrip() + "\n\n" + block + "\n"
    open(mdp, "w").write(s)

# ------------------------------------------------------------------ related sections on Sign Library pages
signs_full = json.load(open("data/signs/signs.json")) if os.path.exists("data/signs/signs.json") else []
dwgs_by_sign = defaultdict(list)
for i in dwgs:
    if i["src"] == "Caltrans Std. Plans 2018":
        continue
    for code in i.get("signs") or []:
        dwgs_by_sign[code].append(i)
for code in dwgs_by_sign:
    dwgs_by_sign[code].sort(key=lambda x: (SRC_PRI.get(x["src"], 6), x["num"]))

signs_by_series = defaultdict(list)
sign_by_code = {}
for rec in signs_full:
    sign_by_code[rec["code"]] = rec
    signs_by_series[rec.get("series", "")].append(rec)

def sign_stem(code):
    # e.g. R3-17aP -> R3-17, W11-2 -> W11-2, R1-5b -> R1-5
    m = re.match(r"^([A-Z]+\d+-\d+)", code)
    return m.group(1) if m else code

# map glossary concepts to topics using details.json co-occurrence
c_topics = defaultdict(Counter)
for i in det:
    for cid in i.get("cs") or []:
        for t in i.get("topics") or []:
            c_topics[cid][t] += 1

sign_rel_count = 0
for rec in signs_full:
    code = rec["code"]
    mdp = f"src/content/docs/signs/{rec['slug']}.md"
    if not os.path.exists(mdp):
        continue
    stem = sign_stem(code)
    ser = signs_by_series.get(rec.get("series", ""), [])
    my_c = set(sign_c.get(code, []))
    # 1. Paired plaques & closely related signs in same series
    peers = []
    for o in ser:
        if o["code"] == code:
            continue
        sc = 0
        if sign_stem(o["code"]) == stem:
            sc += 50
        oc = set(sign_c.get(o["code"], []))
        if my_c and oc:
            sc += len(my_c & oc) * 10
        if o.get("ca_status") == "not adopted":
            sc -= 5
        if sc > 0 or len(ser) <= 12:
            peers.append((sc, o))
    peers.sort(key=lambda x: (-x[0], x[1]["code"]))
    peers = [o for _, o in peers[:8]]

    # 2. Standard drawings citing this sign (deduplicated by agency+num)
    sdwgs, seen_sd = [], set()
    for d in dwgs_by_sign.get(code, []):
        k = (d["sg"], d["num"].upper())
        if k not in seen_sd:
            seen_sd.add(k); sdwgs.append(d)
            if len(sdwgs) >= 8:
                break

    # 3. Topics & keyword index entries
    tc = Counter()
    for d in sdwgs:
        for t in d.get("topics") or []:
            tc[t] += 2
    for cid in my_c:
        tc.update(c_topics[cid])
    stopics = [t for t, _ in tc.most_common(4)]
    sconcepts = [cid for cid in sign_c.get(code, []) if cid in CBY][:6]

    rows = []
    if peers:
        cards = "".join(
            f'<a class="rsign" href="{BASE}/signs/{o["slug"]}/">'
            f'<img loading="lazy" src="{BASE}{o["svg"]}" alt="{esc(o["code"])}">'
            f'<span><b>{esc(o["code"])}</b> {esc(trunc(o.get("descriptor", o["name"]), 46))}</span></a>'
            for o in peers
        )
        rows.append(("Related signs & plaques", f'<div class="rsign-grid">{cards}</div>'))
    if sdwgs:
        rows.append(("Standard drawings citing this sign", "".join(dlink(d) for d in sdwgs)))
    if stopics:
        rows.append(("Topics", " ".join(f'<a class="kchip tchip" href="{BASE}/topics/{t}/">{esc(TOPIC_NAME.get(t, t))}</a>' for t in stopics)))
    if sconcepts:
        rows.append(("Keyword Index", " ".join(f'<a class="kchip" href="{BASE}/keywords/#c-{cid}">{esc(CBY[cid]["term"])}</a>' for cid in sconcepts)))

    t = open(mdp).read()
    t = re.sub(r"\n*<!-- rel-sign -->.*?<!-- /rel-sign -->\n*", "\n", t, flags=re.S)
    if rows:
        sign_rel_count += 1
        rel_html = (
            '\n<!-- rel-sign -->\n'
            '<section class="xidx-wrap rel-sign" data-pagefind-weight="2">'
            '<h2 id="related-signs-and-drawings">Related signs, drawings and topics</h2>'
            '<dl class="xidx">'
            + "".join(f"<div><dt>{esc(a)}</dt><dd>{b}</dd></div>" for a, b in rows)
            + "</dl></section>\n<!-- /rel-sign -->\n"
        )
        t = t.rstrip() + "\n" + rel_html
    open(mdp, "w").write(t)

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
            xs.sort(key=lambda i: (0 if c["id"] in i["cs"] else 1, SRC_PRI.get(i["src"], 6), i["src"], i["num"]))
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
body = "".join(f'<div class="ksec" data-letter="{L}"><h2 id="l-{L}">{L}</h2>' + "".join(by_letter[L]) + "</div>" for L in letters)
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

<div class="ksec-kw">
<h2 id="kw-az">Drawing keywords, A to Z</h2>

Plain-language keywords written for each drawing and scanned page, other than the index entries above.

<ul class="kwaz">{"".join(kw_rows)}</ul>
</div>

<script>
(function(){{
  const q=document.getElementById('kq'),n=document.getElementById('kcount');
  const E=[...document.querySelectorAll('.kentry, .kwaz li')];
  const secs=[...document.querySelectorAll('.ksec')];
  const kwSec=document.querySelector('.ksec-kw');
  E.forEach(el=>{{el._t=(el.dataset.q+' '+el.textContent).toLowerCase();}});
  function run(){{
    const words=q.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
    let c=0;
    E.forEach(el=>{{const ok=!words.length||words.every(w=>el._t.includes(w));el.style.display=ok?'':'none';if(ok)c++;}});
    secs.forEach(s=>{{s.style.display=[...s.querySelectorAll('.kentry')].some(e=>e.style.display!=='none')?'':'none';}});
    if(kwSec) kwSec.style.display=[...kwSec.querySelectorAll('.kwaz li')].some(e=>e.style.display!=='none')?'':'none';
    n.textContent=words.length?(c+' matches'):'{len(entries)} index entries \u00b7 {len(kw_rows)} drawing keywords';
    const u=new URLSearchParams(location.search);
    if(q.value.trim()) u.set('q',q.value.trim()); else u.delete('q');
    history.replaceState(null,'',location.pathname+(u.toString()?'?'+u:'')+location.hash);
  }}
  q.addEventListener('input',run);
  const initQ=new URLSearchParams(location.search).get('q');
  if(initQ){{q.value=initQ;run();}}
  const go=()=>{{if(location.hash){{const t=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(t)t.scrollIntoView()}}}};
  let user=false;['wheel','touchstart','keydown'].forEach(ev=>addEventListener(ev,()=>{{user=true}},{{once:true,passive:true}}));
  const g2=()=>{{if(!user)go()}};[0,300,900,1800,3000].forEach(ms=>setTimeout(g2,ms));addEventListener('load',g2);addEventListener('hashchange',go);
}})();
</script>
'''
os.makedirs("src/content/docs/keywords", exist_ok=True)
open("src/content/docs/keywords/index.md", "w").write(md)

# ------------------------------------------------------------------ data files (deduplicate & authority-sort lookup.json)
json.dump([{"id": c["id"], "cat": CATS[c["cat"]], "term": c["term"], "aka": c["aka"]} for c in LIST], open("public/data/glossary.json", "w"))
norm = lambda s: re.sub(r"\s+", "", s.upper())
for c, n, _ in entries:
    for t in [c["term"]] + c["aka"]:
        k = norm(t)
        ent = [f"Keyword Index: {c['term']} ({n})", f"{BASE}/keywords/#c-{c['id']}"]
        if ent not in lookup.get(k, []):
            lookup.setdefault(k, []).append(ent)

def look_rank(ent):
    lbl, u = ent[0], ent[1]
    if "standard-plans-2018" in u or "2018" in lbl and "/caltrans/" in u:
        return 90
    if "/ca-mutcd/" in u or "/s/ca/" in u or "/la28-supplement/" in u:
        return 10
    if "caltrans-std-plans-2026" in u or "/caltrans/standard-plans-2026/" in u:
        return 15
    if "/details/ladot/mpp-531" in u or "/details/ladot/mpp-521" in u or "/details/ladot/red-book" in u:
        return 20
    if "/bulletins/" in u or "/markings/line-types/" in u:
        return 25
    if "/signs/" in u:
        return 30
    if "/details/" in u:
        return 35
    if "/keywords/" in u:
        return 45
    if "/mutcd/" in u or "/s/fed/" in u:
        return 60
    return 40

for k in list(lookup.keys()):
    seen_u, dedup = set(), []
    for ent in sorted(lookup[k], key=look_rank):
        if ent[1] not in seen_u:
            seen_u.add(ent[1]); dedup.append(ent)
    lookup[k] = dedup

for i in det:
    i.pop("cs", None)
json.dump(det, open("public/data/details.json", "w"))
json.dump(lookup, open("public/data/lookup.json", "w"))
print("concepts used", len(entries), "of", len(LIST), "| tagged items", sum(1 for i in det if i["c"]), "of", len(det),
      "| refs", sum(len(v) for v in refs.values()), "| striping detail links", sum(len(v) for v in ctdet.values()),
      "| similar", sum(1 for v in similar.values() if v[0]), "| sign pages enriched", sign_rel_count, "| drawing keywords", len(kw_rows))
