"""Topic hubs: one page per practice topic, pulling together CA MUTCD 2026, federal MUTCD 11th Ed. Rev. 1,
LADOT documents and drawings, signs and figures. Output: src/content/docs/topics/<slug>.md + index."""
import glob, html, json, os, re
ROOT, BASE = ".", "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
ca = json.load(open("data/ca-mutcd/sections.json"))
fed = {s["num"]: s for s in json.load(open("data/mutcd/sections.json"))}
figs = json.load(open("data/ca-mutcd/figures.json"))
signs = json.load(open("data/signs/signs.json"))
ladot_cfg = json.load(open("pipeline/config/ladot.json"))
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

LABEL = {"std": "Standard", "gui": "Guidance", "opt": "Option", "sup": "Support"}
T = [
 ("crosswalks", "Crosswalks and pedestrian crossings", "Marking, signing and controlling pedestrian crossings: crosswalk patterns, uncontrolled crossings, RRFBs, PHBs, raised crosswalks, limit lines and advance yield lines.",
  r"crosswalk|pedestrian crossing|yield here to|stop here for ped|rectangular rapid|pedestrian hybrid|in-street ped|limit line|stop and yield lines|ped(estrian)? signs?|high-visibility",
  r"crosswalk|pedestrian|RRFB|yield line|stop line|limit line|hybrid beacon", ["R1-5", "R1-6", "R9-", "W11-2", "W16-7", "W16-9", "R10-15"], r"crosswalk|limit line|crossing island|raised crosswalk|continental|uncontrolled", ["crosswalks"]),
 ("bikeways", "Bikeways and bicycle facilities", "Bike lanes, separated bikeways (Class IV), buffered and green-colored lanes, bike boxes, two-stage turn queue boxes, shared lane markings, bike signals and bicycle signs.",
  r"bicycl|bike|shared lane|separated|two-stage|cycle", r"bicycl|bike|shared lane|separated|cycle", ["R81", "R3-17", "R4-11", "W11-1", "D11-1", "R9-6", "R10-22", "R10-26", "W16-1", "R4-4", "R9-5", "R5-1b"], r"bike|bicycl|sharrow|cycle", ["bikeways"]),
 ("transit", "Transit, bus lanes and bus stops", "Preferential and bus-only lanes, red transit lanes, bus bulbs and stops, queue jumps, transit signals and light rail.",
  r"preferential lane|bus|transit|light rail|hov|high-occupancy", r"bus|transit|preferential|light rail", ["R3-10", "R3-11", "R3-12", "R3-13", "R3-14", "R3-15", "R3-17", "R10-23", "R10-24", "R15-", "W10-7"], r"bus|transit", ["transit"]),
 ("curb-parking-loading", "Curb, parking and loading zones", "Curb paint colors, parking stalls, loading and passenger zones, no-parking and tow-away signs, shared mobility zones, meters and accessible parking.",
  r"parking|curb mark|loading|stopping|standing|tow", r"parking|curb|loading|stall", ["R7-", "R8-", "R26", "R28", "R30", "R99", "R100"], r"parking|stall|meter|loading|curb|tow away|street sweeping|red flag", ["parking-curb"]),
 ("speed-and-calming", "Speed limits, speed zones and traffic calming", "Speed limit signs and speed zones, school and senior speed limits, speed humps, speed tables, traffic circles and roundabouts, and narrowed roadways.",
  r"speed|traffic calming|roundabout|hump|traffic circle", r"speed|calming|roundabout|hump", ["R2-", "W13-", "W17-", "R2-1", "W3-5", "W2-6"], r"speed hump|speed table|traffic circle|roundabout|narrowed roadway|calming", ["speed-calming"]),
 ("signals", "Traffic signals and pedestrian signals", "Signal warrants, signal heads and placement, phasing, pedestrian signal heads and countdowns, accessible pedestrian signals, detection and beacons.",
  r"signal|beacon|warrant|detector|countdown|accessible pedestrian", r"signal|beacon|warrant|detect", ["R10-", "W3-3", "W25-"], r"signal|mastarm|loop|detector|beacon|pull box|conduit|controller", ["signals"]),
 ("striping-intersections", "Lane lines, striping and intersection markings", "Longitudinal markings, centerlines and lane lines, channelization, turn lanes, words and arrows, dotted extension lines and pavement marking materials.",
  r"longitudinal|center ?line|lane line|edge line|channeliz|word|arrow|pavement marking|extension|chevron|raised pavement|markings", r"marking|line|arrow|channeliz", ["R3-", "R3-8", "R3-5", "R3-6", "R3-7", "W24-", "W4-"], r"striping|lane|channelization|pavement marking|arrow|word|left turn|intersection striping", ["striping"]),
 ("school-zones", "School zones", "School area signs, school speed limits, school crosswalks, crossing guards and pick-up/drop-off areas.",
  r"school", r"school", ["S1-", "S3-", "S4-", "S5-", "R26", "SR4"], r"school", []),
 ("street-name-and-guide-signs", "Street name and guide signs", "Street name signs, overhead and mastarm-mounted name signs, advance street name signs, guide and wayfinding signs.",
  r"street name|guide sign|destination|wayfinding|route sign|advance street", r"street name|guide|destination|wayfinding", ["D3-", "D1-", "D11-", "M1-", "M3-", "M5-", "M6-", "E1-"], r"street name|guide sign|overhead", []),
 ("temporary-traffic-control", "Temporary traffic control", "Work zones, closures, detours, tapers, channelizing devices and pedestrian and bicycle accommodation through work zones.",
  r"temporary traffic|work zone|taper|flagger|channelizing|detour|closure|tta", r"temporary traffic|work zone|flagg|detour", ["W20-", "W21-", "G20-", "R11-", "M4-", "W1-6"], r"closure|block party|detour|construction|barricade", []),
 ("accessibility", "Accessibility: curb ramps and accessible signals", "Curb ramps, detectable warnings, accessible pedestrian routes in work zones, accessible pedestrian signals and accessible parking.",
  r"accessib|curb ramp|detectable", r"accessib|curb ramp|detectable", ["R7-8", "R99"], r"curb ramp|accessible|ada|detectable", ["accessibility"]),
 ("rail-crossings", "Railroad and light rail crossings", "Grade crossing signs, markings and signals, and light rail transit crossings.",
  r"grade crossing|railroad|rail|lrt|light rail", r"rail|crossing", ["R15-", "W10-", "R8-8", "I-13"], r"rail", []),
]

CHAPS = {"crosswalks": ["3C", "4J", "4L", "4K"], "bikeways": ["9A", "9B", "9C", "9D", "9E", "9F", "4H"], "transit": ["3E", "2G"],
         "curb-parking-loading": [], "speed-and-calming": ["3D"], "signals": ["4B", "4C", "4D", "4E", "4F", "4I", "4S"],
         "striping-intersections": ["3B", "3J", "3H"], "school-zones": ["7A", "7B", "7C", "7D"], "street-name-and-guide-signs": ["2D"],
         "temporary-traffic-control": ["6A", "6B", "6C", "6F", "6G", "6H", "6K"], "accessibility": ["4K", "6C"], "rail-crossings": ["8A", "8B", "8C", "8D", "8E"]}
os.makedirs("src/content/docs/topics", exist_ok=True)
for f in glob.glob("src/content/docs/topics/*.md"):
    os.remove(f)
cards = []
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
    fhtml = "".join(f'<a class="tfig" href="{x["url"]}"><img loading="lazy" src="{BASE}{x["image"]}" alt="{esc(x["kind"])} {esc(x["id"])}"><span><b>{esc(x["kind"])} {esc(x["id"])}</b> {esc(x["title"][:90])}</span></a>' for x in fgu[:24])
    # signs
    sg = [s for s in signs if any(s["code"].startswith(p) for p in sign_pref)]
    sg = sorted(sg, key=lambda s: (s.get("ca_status") == "not adopted", s["code"]))[:72]
    shtml = "".join(f'<a class="tsign sref" href="{BASE}/signs/{s["slug"]}/" data-svg="{BASE}{s["svg"]}"><img loading="lazy" src="{BASE}{s["svg"]}" alt="{esc(s["code"])}"><span><b>{esc(s["code"])}</b> {esc(s.get("descriptor", s["name"]))[:48]}</span></a>' for s in sg)
    # LADOT drawings + pages
    lrows, lpages = [], []
    for d in ladot:
        for k, v in d["drawings"].items():
            t = d.get("drawing_titles", {}).get(k, {}).get("title", "")
            if t and lrx.search(t):
                lrows.append(f'<tr><td><strong>{esc(k)}</strong></td><td>{esc(t)}</td><td>{esc(d["short"])}</td><td><a href="{BASE}/{d["slug"]}/{v[0]["chapter"]}/#p{v[0]["page"]}">open</a></td></tr>')
        for p in d["pages"]:
            if p["image"] and (lrx.search(p["title"] or "") or (ladot_tags and set(ladot_tags) <= set(p["topics"]) and len(p["topics"]) <= 3)):
                lpages.append((d["short"], p))
    lthumbs = "".join(f'<a class="tfig" href="{p["url"]}"><img loading="lazy" src="{p["image"]}" alt="{esc(a)} page {p["page"]}"><span><b>{esc(a)}</b> p{p["page"]} {esc((p["title"] or "")[:70])}</span></a>' for a, p in lpages[:30])
    q = f"Compare what CA MUTCD 2026, the federal MUTCD and LADOT say about {name.lower()}; note conflicts and which governs."
    md = f'''---
title: "{name}"
description: "{intro}"
sidebar:
  order: {order}
---

<div class="topic-intro">{esc(intro)}</div>

<div class="topic-stats"><span><b>{len(secs)}</b> CA MUTCD sections</span><span><b>{stats["std"]}</b> standards (shall)</span><span><b>{stats["gui"]}</b> guidance (should)</span><span><b>{stats["opt"]}</b> options (may)</span><span><b>{len(sg)}</b> signs</span><span><b>{len(lrows)}</b> LADOT drawings</span></div>

<p><a class="ai-btn" href="{BASE}/ask/?q={html.escape(q.replace(" ", "%20"))}">Ask Claude to compare all sources on this topic</a></p>

## The rules

CA MUTCD 2026 governs in California. Each row shows the section's first Standard (or Guidance, when there is no Standard), how many shall, should and may provisions it has, and the matching federal section. Open a section and use **Explain with Claude** there to see the CA and federal differences.

<table class="trules"><thead><tr><th>CA MUTCD</th><th>Section and key provision</th><th>Federal 11th Ed. R1</th></tr></thead><tbody>{"".join(rows)}</tbody></table>

## LADOT requirements

{("<table class=\"dwtab\"><thead><tr><th>Drawing</th><th>Title</th><th>Document</th><th></th></tr></thead><tbody>" + "".join(lrows) + "</tbody></table>") if lrows else "<p class=\"muted\">No LADOT standard drawing is titled for this topic; see the pages below and search.</p>"}

{("<div class=\"tgrid\">" + lthumbs + "</div>") if lthumbs else ""}

## Figures

{("<div class=\"tgrid\">" + fhtml + "</div>") if fhtml else "<p class=\"muted\">No CA MUTCD figure is titled for this topic.</p>"}

## Signs

<div class="tsigns">{shtml}</div>

<p><a href="{BASE}/signs/">Open the full Sign Library</a></p>
'''
    open(f"src/content/docs/topics/{slug}.md", "w").write(md)
    cards.append(f'<a class="tcard" href="{BASE}/topics/{slug}/"><b>{esc(name)}</b><span>{esc(intro)}</span><em>{len(secs)} sections &middot; {len(sg)} signs &middot; {len(lrows)} LADOT drawings</em></a>')
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

<div class="tcards">{"".join(cards)}</div>
''')
