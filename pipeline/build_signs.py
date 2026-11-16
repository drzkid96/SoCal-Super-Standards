"""Build the Sign Library and link sign codes across the site.

Inputs: data/signs/shs.json, CA MUTCD 2026 PDF (for California status), generated manual pages.
Outputs:
  data/signs/signs.json                      final sign records
  src/content/docs/signs/index.md           the chart (grouped, filterable)
  src/content/docs/signs/<slug>.md           one page per sign
  manual pages rewritten so every sign code is a link with a hover preview

Usage: python3 -I pipeline/build_signs.py CAMUTCD2026.pdf REPO_ROOT
"""
import glob, html, json, os, re, sys
from collections import OrderedDict, defaultdict
import pymupdf

CAPDF, ROOT = sys.argv[1], sys.argv[2]
BASE = os.environ.get("SITE_BASE", "/SoCal-Super-Standards")
raw = json.load(open(f"{ROOT}/data/signs/shs.json"))
_have = {r["code"].split(",")[0].strip() for r in raw}
if os.path.exists(f"{ROOT}/data/signs/ca_extra.json"):
    raw += [r for r in json.load(open(f"{ROOT}/data/signs/ca_extra.json")) if r["code"] not in _have]

CATS = OrderedDict([
    ("Regulatory Signs", "regulatory"), ("Warning Signs and Object Markers", "warning"),
    ("School Signs", "school"), ("Temporary Traffic Control Signs", "ttc"), ("Guide Signs", "guide"),
    ("Standard Arrows", "arrows"),
])
SERIES = {
    "R1": "STOP, YIELD, and pedestrian crossing", "R2": "Speed limits", "R3": "Movement prohibition and lane control",
    "R4": "Passing, keep right, and lane use", "R5": "Selective exclusion and wrong way", "R6": "One way and divided highway",
    "R7": "Parking", "R8": "Parking, standing, and stopping", "R9": "Pedestrians and bicycles", "R10": "Traffic signals",
    "R11": "Road closed", "R12": "Weight limits", "R13": "Weigh station", "R14": "Truck routes and hazmat",
    "R15": "Rail and LRT crossings", "R16": "Other regulatory", "R20": "Other regulatory", "R22": "Other regulatory",
    "R26": "Other regulatory", "R50": "Other regulatory", "R52": "Other regulatory",
    "W1": "Horizontal alignment", "W2": "Intersections", "W3": "Advance traffic control", "W4": "Merging and lanes",
    "W5": "Road narrows and bridges", "W6": "Divided highway and two-way traffic", "W7": "Grades",
    "W8": "Roadway and weather conditions", "W9": "Lane ends", "W10": "Rail and LRT crossings",
    "W11": "Vehicular and non-vehicular traffic", "W12": "Clearance", "W13": "Advisory speed",
    "W14": "Dead end, no passing", "W15": "Playground", "W16": "Supplemental plaques", "W17": "Speed hump",
    "W18": "No traffic signs", "W19": "Freeway ends", "W20": "Work zones", "W21": "Work zones",
    "W22": "Blasting zones", "W23": "Traffic pattern", "W24": "Shifts", "W25": "Extended green", "W26": "Stopped traffic",
    "W27": "Other warning", "OM": "Object markers", "S1": "School area", "S2": "School area", "S3": "School bus",
    "S4": "School speed and plaques", "S5": "School speed limit", "CW": "Work zones", "G20": "Work zones",
}
STATUS_LABEL = {"ca": "Used in CA MUTCD 2026", "not-adopted": "Not adopted in California", "national": "National only (not shown in CA MUTCD)"}


KIND = {"Regulatory Signs": "regulatory sign", "Warning Signs and Object Markers": "warning sign",
        "School Signs": "school sign", "Temporary Traffic Control Signs": "work zone sign", "Guide Signs": "guide sign",
        "Standard Arrows": "arrow"}
TOPIC_TAGS = {
    "R1": "intersection control, right of way, crosswalk", "R2": "speed, speed zone, traffic calming", "R3": "lane use, turn restriction, intersection",
    "R4": "lane use, passing", "R5": "access restriction, wrong way, exclusion", "R6": "one way, circulation",
    "R7": "parking, curb management", "R8": "parking, stopping, curb management", "R9": "pedestrian, bicycle, active transportation",
    "R10": "traffic signal, signal operation", "R11": "road closure, access", "R12": "truck, weight", "R14": "truck, freight",
    "R15": "rail, LRT, grade crossing", "R16": "regulatory", "W1": "curve, alignment", "W2": "intersection", "W3": "advance warning, signal ahead",
    "W4": "merge, lane drop", "W9": "lane drop", "W10": "rail, LRT, grade crossing", "W11": "crossing, pedestrian, bicycle",
    "W16": "plaque, supplemental", "W17": "speed hump, traffic calming", "W20": "work zone, construction, TTC", "W21": "work zone, construction, TTC",
    "S1": "school, safe routes to school", "S3": "school bus", "S4": "school zone", "S5": "school zone, speed", "OM": "object marker, hazard",
}
SYN = {"pedestrian": "ped, pedestrian crossing", "bicycle": "bike, cyclist", "bike": "bicycle, cyclist", "parking": "curb, loading",
       "stop": "stop control", "yield": "yield control", "school": "SRTS", "train": "rail, LRT", "bus": "transit"}


VOCAB = set()
for _f in glob.glob(f"{ROOT}/src/content/docs/ca-mutcd/*.md"):
    for _w in re.findall(r"[A-Za-z]{3,}", re.sub(r"<[^>]+>", " ", open(_f).read())):
        VOCAB.add(_w.lower())


def descriptor(rec):
    name = rec.get("name") or rec.get("caption", "").title()
    name = re.sub(r"\s*\((plaque|sign)\)\s*", " ", name, flags=re.I).strip()
    is_plaque = rec["code"].endswith("P") or "plaque" in (rec.get("name") or "").lower()
    kind = "plaque" if is_plaque else KIND.get(rec["category"], "sign")
    if rec["code"].startswith("OM"):
        kind = "object marker"
    if name and kind.split()[0].lower() in name.lower().split():
        kind = kind.split()[-1]
    return (name + " " + kind).strip() if name else kind.capitalize()


def keywords(rec):
    words = []
    def add(t):
        for w in re.split(r"[,/]| - ", t):
            w = w.strip().lower()
            if w and len(w) > 1 and w not in words:
                words.append(w)
    add(rec["code"])
    add(rec.get("name", ""))
    cap = rec.get("caption", "")
    if cap:
        add(cap.title())
    for w in re.findall(r"[A-Za-z]{3,}", rec.get("legend_ocr", "")):
        if w.lower() in VOCAB:
            add(w)
    add(KIND.get(rec["category"], "sign"))
    if rec["series_name"].lower() not in words:
        words.append(rec["series_name"].lower())
    add(TOPIC_TAGS.get(rec["series"], ""))
    col = rec.get("colors", "")
    for c in ("red", "white", "black", "yellow", "fluorescent yellow-green", "green", "blue", "orange", "brown", "purple"):
        if c.upper() in col.upper():
            add(c)
    blob = " ".join(words)
    for k, v in SYN.items():
        if k in blob:
            add(v)
    return words[:28]


def series_of(code):
    m = re.match(r"([A-Z]+)(\d+)", code)
    if not m:
        return code
    if m.group(1) in ("OM", "CW"):
        return m.group(1)
    return m.group(1) + m.group(2)


def slug(code):
    return re.sub(r"[^a-z0-9\-]", "", code.lower().replace("(", "").replace(")", ""))


# ------------------------------------------------------------------ merge sheets
signs = OrderedDict()
for s in raw:
    base = s["code"].split(",")[0].strip()
    rec = signs.get(base)
    if rec is None:
        rec = dict(s)
        rec["code"] = base
        rec["sheets"] = []
        signs[base] = rec
    else:
        rec["sheets"].append(s["svg"])
        if not rec.get("name") and s.get("name"):
            rec["name"] = s["name"]
        if not rec.get("dims") and s.get("dims"):
            rec["dims"] = s["dims"]
for code, rec in signs.items():
    if not rec.get("category"):
        p = re.match(r"[A-Z]+", code).group(0)
        rec["category"] = {"R": "Regulatory Signs", "W": "Warning Signs and Object Markers", "OM": "Warning Signs and Object Markers",
                           "S": "School Signs", "CW": "Temporary Traffic Control Signs", "G": "Temporary Traffic Control Signs"}.get(p, "Guide Signs")
    if not rec.get("name"):
        m = re.search(rf"{re.escape(code)}\s+([A-Z][A-Z0-9 ,'/&()\-]+?)\s+(?:COLORS|\*|2024)", rec.get("colors", ""))
        rec["name"] = m.group(1).title() if m else ""
    rec["series"] = series_of(code)
    rec["series_name"] = SERIES.get(rec["series"], "Other")
    rec["slug"] = slug(code)
    rec["descriptor"] = descriptor(rec)
    rec["keywords"] = keywords(rec)

# ------------------------------------------------------------------ California status
ca = pymupdf.open(CAPDF)
crossed, mentioned = set(), set()
CODE_RE = re.compile(r"(?<![A-Za-z0-9-])((?:OM|CW|[RWSDMEIG])\d{1,3}[A-Za-z]?-\d{1,3}[A-Za-z]{0,4})(?![A-Za-z0-9-])")
CA_RE = re.compile(r"(?<![A-Za-z0-9-])((?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d{1,3}[A-Z]?(?:-\d{1,3}[A-Za-z]{0,3})?\(CA\))")
for pno in range(54, len(ca)):
    pg = ca[pno]
    txt = pg.get_text()
    for c in CODE_RE.findall(txt):
        mentioned.add(c)
    blue = [d for d in pg.get_drawings() if d.get("color") and d["color"][2] > 0.8 and d["color"][0] < 0.3
            and d["color"][1] < 0.3 and d["type"] == "s" and len(d["items"]) == 1 and d["items"][0][0] == "l"]
    if not blue:
        continue
    boxes = {}
    for d in blue:
        k = tuple(round(v) for v in d["rect"])
        boxes[k] = boxes.get(k, 0) + 1
    words = pg.get_text("words")
    for (x0, y0, x1, y1), n in boxes.items():
        if n < 2 or (x1 - x0) < 20 or (y1 - y0) < 20:
            continue
        best = None
        for w in words:
            if CODE_RE.fullmatch(w[4]) and x0 - 5 <= (w[0] + w[2]) / 2 <= x1 + 5 and -4 <= w[1] - y1 <= 18:
                if best is None or w[1] < best[1]:
                    best = w
        if best:
            crossed.add(best[4])
for code, rec in signs.items():
    rec["ca_status"] = "ca" if rec.get("ca_only") else ("not-adopted" if code in crossed else ("ca" if code in mentioned else "national"))

# ------------------------------------------------------------------ where each code is mentioned
mentions = defaultdict(list)
for manual, label, d in (("ca-mutcd", "CA MUTCD 2026", "ca-mutcd"), ("mutcd", "MUTCD 11E R1", "mutcd")):
    secs = json.load(open(f"{ROOT}/data/{d}/sections.json"))
    by_anchor = {(s["chapter"].lower(), s["anchor"]): s for s in secs}
    for f in glob.glob(f"{ROOT}/src/content/docs/{d}/*.md"):
        ch = os.path.basename(f)[:-3]
        if ch == "index":
            continue
        t = open(f).read()
        parts = re.split(r'<span id="([a-z0-9]+)" class="anchor"></span>', t)
        for i in range(1, len(parts), 2):
            anchor, body = parts[i], parts[i + 1]
            s = by_anchor.get((ch, anchor))
            if not s:
                continue
            plain = re.sub(r"<[^>]+>", " ", body)
            for c in set(CODE_RE.findall(plain)) | set(CA_RE.findall(plain)):
                if c in signs:
                    mentions[c].append({"manual": label, "num": s["num"], "title": s["title"], "url": s["url"]})
for code, rec in signs.items():
    rec["mentions"] = mentions.get(code, [])

json.dump(list(signs.values()), open(f"{ROOT}/data/signs/signs.json", "w"), indent=1)

# ------------------------------------------------------------------ pages
os.makedirs(f"{ROOT}/src/content/docs/signs", exist_ok=True)
for f in glob.glob(f"{ROOT}/src/content/docs/signs/*.md"):
    os.remove(f)
esc = lambda t: html.escape(str(t), quote=True)


def card(rec):
    return (f'<a class="scard" href="{BASE}/signs/{rec["slug"]}/" data-code="{esc(rec["code"])}" '
            f'data-name="{esc((rec["descriptor"] + " " + " ".join(rec["keywords"])).lower())}" data-cat="{CATS.get(rec["category"], "other")}" data-ca="{rec["ca_status"]}">'
            f'<span class="simg"><img loading="lazy" src="{BASE}{rec["svg"]}" alt="{esc(rec["code"])} {esc(rec["name"])}"></span>'
            f'<span class="scode">{esc(rec["code"])}</span><span class="sname">{esc(rec["descriptor"])}</span>'
            f'{"<span class=\"sflag na\">Not in CA</span>" if rec["ca_status"] == "not-adopted" else ""}</a>')


grouped = OrderedDict()
for rec in signs.values():
    grouped.setdefault(rec["category"], OrderedDict()).setdefault(rec["series"], []).append(rec)
order = list(CATS.keys())
sections = []
for cat in sorted(grouped, key=lambda c: order.index(c) if c in order else 99):
    cid = CATS.get(cat, "other")
    block = [f'<h2 id="{cid}" class="sgroup">{esc(cat)} <span class="count">{sum(len(v) for v in grouped[cat].values())}</span></h2>']
    def sk(s):
        m = re.match(r"([A-Z]+)(\d*)", s)
        return (m.group(1), int(m.group(2) or 0))
    for ser in sorted(grouped[cat], key=sk):
        recs = grouped[cat][ser]
        block.append(f'<div class="sseries" data-cat="{cid}"><h3 id="series-{ser.lower()}">{esc(ser)} &middot; {esc(SERIES.get(ser, "Other"))}</h3>'
                     f'<div class="sgrid">' + "".join(card(r) for r in recs) + "</div></div>")
    sections.append("\n".join(block))

n_all = len(signs)
n_na = sum(1 for r in signs.values() if r["ca_status"] == "not-adopted")
index = f"""---
title: Sign Library
description: Every standard sign, drawn clean at the same size, grouped by MUTCD type, with California status, sizes, and governing sections.
tableOfContents: false
---

<div class="srcbar">Federal sign artwork and dimensions: FHWA Standard Highway Signs, 2024 Edition (Releases 1-4). California-only signs (codes ending in (CA)): cut from the CA MUTCD 2026 figures; search "(CA)" to list them. {n_all} signs; {n_na} federal signs are crossed out (not adopted) in California.</div>

<div class="sfilter" id="sfilter">
  <input type="search" id="sq" placeholder="Filter by code or name, e.g. R10-6, bike, school..." autocomplete="off">
  <div class="sbtns">
    <button data-f="all" class="on">All</button>
    {''.join(f'<button data-f="{v}">{k.replace(" Signs", "").replace(" and Object Markers", "")}</button>' for k, v in CATS.items() if any(r['category'] == k for r in signs.values()))}
  </div>
  <label class="scheck"><input type="checkbox" id="sca"> Hide signs not adopted in California</label>
  <span id="scount" class="scount"></span>
</div>

{chr(10).join(sections)}

<script>
(() => {{
  const q = document.getElementById('sq'), ca = document.getElementById('sca'), cnt = document.getElementById('scount');
  let cat = 'all';
  const cards = [...document.querySelectorAll('.scard')];
  function run() {{
    const t = q.value.trim().toLowerCase();
    let n = 0;
    cards.forEach(c => {{
      const ok = (cat === 'all' || c.dataset.cat === cat) && (!ca.checked || c.dataset.ca !== 'not-adopted') &&
        (!t || c.dataset.code.toLowerCase().includes(t) || c.dataset.name.includes(t));
      c.hidden = !ok; if (ok) n++;
    }});
    document.querySelectorAll('.sseries').forEach(s => s.hidden = !s.querySelector('.scard:not([hidden])'));
    document.querySelectorAll('.sgroup').forEach(h => {{
      let el = h.nextElementSibling, any = false;
      while (el && !el.classList.contains('sgroup')) {{ if (el.classList.contains('sseries') && !el.hidden) any = true; el = el.nextElementSibling; }}
      h.hidden = !any;
    }});
    cnt.textContent = n + ' signs';
  }}
  q.addEventListener('input', run); ca.addEventListener('change', run);
  document.querySelectorAll('.sbtns button').forEach(b => b.addEventListener('click', () => {{
    document.querySelectorAll('.sbtns button').forEach(x => x.classList.remove('on')); b.classList.add('on'); cat = b.dataset.f; run();
  }}));
  const h = new URLSearchParams(location.search).get('q'); if (h) q.value = h;
  run();
}})();
</script>
"""
open(f"{ROOT}/src/content/docs/signs/index.md", "w").write(index)

for rec in signs.values():
    dims = rec.get("dims") or []
    tbl = ""
    if dims and len(dims) > 1:
        head = dims[0]
        rows = [r for r in dims[1:] if any(ch.isdigit() for ch in "".join(r))]
        tbl = "<table class=\"dims\"><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>"
    ments = rec["mentions"]
    ment_html = "".join(f'<li><a href="{m["url"]}">{esc(m["manual"])} &sect;{esc(m["num"])}</a> {esc(m["title"])}</li>' for m in ments) or "<li>No section text mentions this code directly.</li>"
    sheets = "".join(f'<img class="sheet" src="{BASE}{s}" alt="additional sheet">' for s in rec["sheets"])
    status_cls = {"ca": "ca-same", "not-adopted": "rev", "national": "muted"}[rec["ca_status"]]
    body = f"""---
title: "{rec['code']} {rec['descriptor'].replace('"', "'")}"
description: "{rec['code']} {rec['name'].replace('"', "'")}: {rec['category']}, series {rec['series']}. Sign artwork, sizes, colors, California status, and governing MUTCD sections."
tableOfContents: false
---

<div class="sdetail">
<div class="sdetail-img"><img src="{BASE}{rec['svg']}" alt="{esc(rec['code'])}">{sheets}</div>
<div class="sdetail-info">
<p class="scode-big">{esc(rec['code'])}</p>
<p><span class="badge {status_cls}">{STATUS_LABEL[rec['ca_status']]}</span></p>
<dl>
<dt>Descriptor</dt><dd>{esc(rec['descriptor'])}</dd>
<dt>Legend</dt><dd>{esc(rec.get('caption') or '-')}</dd>
<dt>Keywords</dt><dd class="kw">{esc(', '.join(rec['keywords']))}</dd>
<dt>Type</dt><dd><a href="{BASE}/signs/#{CATS.get(rec['category'], 'other')}">{esc(rec['category'])}</a></dd>
<dt>Series</dt><dd><a href="{BASE}/signs/#series-{rec['series'].lower()}">{esc(rec['series'])} &middot; {esc(rec['series_name'])}</a></dd>
<dt>Colors</dt><dd>{esc(rec['colors'].split(rec['code'])[0].strip() if rec['colors'] else 'See layout')}</dd>
<dt>Source</dt><dd>{esc(rec['source'])}, page {esc(rec['page_label'])}</dd>
</dl>
</div>
</div>

## Sizes and layout dimensions (inches)

{tbl or '<p>See the FHWA layout sheet for dimensions.</p>'}

<p class="note">Column A is the sign size. Use the MUTCD size tables for which size applies (conventional road, minimum, oversized).</p>

## Governing sections

<ul class="ments">{ment_html}</ul>
"""
    open(f"{ROOT}/src/content/docs/signs/{rec['slug']}.md", "w").write(body)

# ------------------------------------------------------------------ link sign codes in manual pages (hover previews)
def link_codes(text):
    out = []
    for seg in re.split(r"(<[^>]+>)", text):
        if seg.startswith("<"):
            out.append(seg)
            continue
        out.append(CODE_RE.sub(lambda m: (f'<a class="sref" href="{BASE}/signs/{signs[m.group(1)]["slug"]}/" '
                                         f'data-svg="{BASE}{signs[m.group(1)]["svg"]}">{m.group(1)}</a>')
                                if m.group(1) in signs else m.group(0), seg))
    return "".join(out)


for d in ("ca-mutcd", "mutcd"):
    for f in glob.glob(f"{ROOT}/src/content/docs/{d}/*.md"):
        t = open(f).read()
        if 'class="sref"' in t:
            continue
        fm_end = t.find("---", 3) + 3
        head, body = t[:fm_end], t[fm_end:]
        # only inside HTML paragraphs, not markdown headings or anchors
        body = re.sub(r"(<p>.*?</p>)", lambda m: link_codes(m.group(1)), body, flags=re.S)
        open(f, "w").write(head + body)

def link_ca(text):
    out, depth = [], 0
    for seg in re.split(r"(<[^>]+>)", text):
        if seg.startswith("<"):
            if seg.startswith("<a "):
                depth += 1
            elif seg.startswith("</a"):
                depth -= 1
            out.append(seg)
            continue
        if depth:
            out.append(seg)
            continue
        out.append(CA_RE.sub(lambda m: (f'<a class="sref" href="{BASE}/signs/{signs[m.group(1)]["slug"]}/" data-svg="{BASE}{signs[m.group(1)]["svg"]}">{m.group(1)}</a>')
                             if m.group(1) in signs else m.group(0), seg))
    return "".join(out)


for d in ("ca-mutcd", "mutcd"):
    for f in glob.glob(f"{ROOT}/src/content/docs/{d}/*.md"):
        t = open(f).read()
        fm_end = t.find("---", 3) + 3
        head, body = t[:fm_end], t[fm_end:]
        nb = re.sub(r"(<p>.*?</p>)", lambda m: link_ca(m.group(1)), body, flags=re.S)
        if nb != body:
            open(f, "w").write(head + nb)

json.dump({c: {"code": c, "descriptor": r["descriptor"], "url": f"{BASE}/signs/{r['slug']}/", "svg": f"{BASE}{r['svg']}", "ca": r["ca_status"]}
           for c, r in signs.items()}, open(f"{ROOT}/public/data/signs-index.json", "w"))
print("signs", n_all, "not adopted in CA", n_na, "CA used", sum(1 for r in signs.values() if r["ca_status"] == "ca"),
      "with mentions", sum(1 for r in signs.values() if r["mentions"]))
