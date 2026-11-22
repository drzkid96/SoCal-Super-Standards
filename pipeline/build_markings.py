"""Pavement Marking Library: a standardized chart of Caltrans striping details, arrows, words and symbols,
crosswalks, bicycle markings, colored pavement and curb paint, plus local agency marking standards."""
import json, re, html, os, glob
BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
items = json.load(open("data/markings/items.json"))
figs = json.load(open("data/ca-mutcd/figures.json"))
fig_url = {}
for f in figs:
    fig_url.setdefault(f["id"], f["url"])
secs = {s["num"]: s for s in json.load(open("data/ca-mutcd/sections.json"))}
ROMAN = {"Ii", "Iii", "Iv", "Vi", "Vii", "Viii", "Xi", "Cs", "I", "V", "Ix", "X"}
def tidy(n):
    w = n.split()
    out = []
    for x in w:
        core = x.strip("()")
        if core in ROMAN or core.upper() in ("CS",):
            x = x.replace(core, core.upper())
        x = x.replace("Ft)", "ft)").replace("(L)", "(L)")
        out.append(x)
    return " ".join(out).replace("Arrow Right Lane Drop Arrow", "Arrow (Right Lane Drop)")
CAT = [("lines", "Longitudinal lines (Caltrans striping details)"), ("arrows", "Arrows"), ("words", "Words and symbols"),
       ("crosswalks", "Crosswalks"), ("applications", "Application examples (arrows and lane use)"), ("bike", "Bicycle markings"), ("color", "Colored pavement"), ("curb", "Curb paint (CVC 21458)"),
       ("local", "Local agency marking standards")]
def cat_of(i):
    if i.get("cat"):
        return i["cat"]
    f = i["figure"]
    if i["kind"] == "line":
        return "bike" if i["detail"] in ("Detail 39", "Detail 39A") else "lines"
    if f.startswith(("3B-21", "3B-22")):
        return "arrows"
    if f.startswith("3C"):
        return "crosswalks"
    if f.startswith("9E"):
        return "bike"
    return "words"
SECTION_OF = {"applications": "3B.20", "lines": "3A.04", "arrows": "3B.20", "words": "3B.20", "crosswalks": "3C.03", "bike": "9E.01", "color": "3H.01", "curb": "3B.18"}
cards = {k: [] for k, _ in CAT}
lookup_add = {}
for i in items:
    c = cat_of(i)
    i["cat"] = c
    name = (i["name"] if i.get("cat") else tidy(i["name"])) if i["kind"] == "symbol" else i["name"]
    if i["kind"] == "line" and i.get("subtitle"):
        name = f'{i["name"]}: {i["subtitle"]}'
    i["display"] = name
    sub = i.get("sub") or i.get("group") or ""
    desc = i.get("desc", "")
    if re.match(r"^[\d .ftinmx]+$", desc or "x") or desc.count(" ft") > 3:
        desc = ""
    furl = fig_url.get(i["figure"], f'{BASE}/ca-mutcd/{i["figure"][:2].lower()}/')
    big = i["kind"] == "figure" or i["w"] > 1500
    q = " ".join([name, sub, desc, i["figure"], i["figure_title"], c]).lower()
    cards[c].append(f'''<div class="mcard{' wide' if big else ''}" data-q="{esc(q)}" id="{i["id"]}">
<a class="mimg" href="{BASE}{i["img"]}" target="_blank"><img loading="lazy" src="{BASE}{i["img"]}" alt="{esc(name)}"></a>
<div class="mbody"><b>{esc(name)}</b>{f'<div class="msub">{esc(sub)}</div>' if sub else ''}{f'<div class="mdesc">{esc(desc[:300])}</div>' if desc else ''}
<div class="msrc"><a href="{furl}">CA MUTCD Figure {esc(i["figure"])}</a> &middot; manual page {i["page"]}</div></div></div>''')
    if i["kind"] == "line":
        dn = i["detail"].replace("Detail ", "").lower()
        svgp = f"public/linetypes/detail-{dn}.svg"
        lookup_add.setdefault(i["detail"].upper().replace(" ", ""), [f"Caltrans striping {i['detail']} ({i['figure']})", f"{BASE}/markings/line-types/#detail-{dn}",
                              f"{BASE}/linetypes/detail-{dn}.svg" if os.path.exists(svgp) else f"{BASE}{i['img']}"])
# colored pavement (CA MUTCD 3H figures)
for f in figs:
    if f["chapter"] == "3H" and f["kind"] == "Figure":
        cards["color"].append(f'<div class="mcard wide" data-q="{esc(f["title"].lower())} colored pavement"><a class="mimg" href="{f["url"]}"><img loading="lazy" src="{BASE}/thumbs{f["image"]}" alt=""></a><div class="mbody"><b>Figure {esc(f["id"])}</b> {esc(f["title"][:80])}</div></div>')
COL = [("Green", "#2e9b4f", "Green-colored pavement for bicycle facilities (bike lanes, bike boxes, conflict areas)", "3H.06"),
       ("Red", "#c0392b", "Red-colored pavement for public transit (bus-only and transit lanes)", "3H.07"),
       ("Yellow", "#f2c200", "Yellow-colored pavement for medians and islands that separate opposing traffic", "3H.04"),
       ("White", "#ffffff", "White-colored pavement for islands, shoulders and buffers between same-direction traffic", "3H.05"),
       ("Purple", "#7b3fa0", "Purple-colored pavement for ETC account-only toll lanes", "3H.08")]
cards["color"] = [f'<div class="mcard swatch" data-q="{c.lower()} colored pavement {d.lower()}"><div class="sw" style="background:{h}"></div><div class="mbody"><b>{c}</b><div class="mdesc">{esc(d)}</div><div class="msrc"><a href="{secs[s]["url"]}">CA MUTCD {s}</a></div></div></div>' for c, h, d, s in COL] + cards["color"]
CURB = [("Red", "#c0392b", "No stopping, standing or parking (a bus may stop in a red zone marked as a bus loading zone)"),
        ("Yellow", "#f2c200", "Stopping only to load or unload passengers or freight, for the time set by local ordinance"),
        ("White", "#ffffff", "Stopping to load or unload passengers, or to deposit mail in an adjacent mailbox"),
        ("Green", "#2e9b4f", "Time-limit parking set by local ordinance"),
        ("Blue", "#1f5fbf", "Parking only for vehicles of disabled persons and disabled veterans with a placard or plate")]
cards["curb"] = [f'<div class="mcard swatch" data-q="{c.lower()} curb paint {d.lower()}"><div class="sw curb" style="background:linear-gradient(180deg,#bdb8ad 0 55%,{h} 55% 100%)"></div><div class="mbody"><b>{c} curb</b><div class="mdesc">{esc(d)}</div><div class="msrc"><a href="{secs["3B.18"]["url"]}">CA MUTCD 3B.18</a>, CVC 21458</div></div></div>' for c, h, d in CURB]
# local agency marking standards
det = json.load(open("public/data/details.json"))
LRX = re.compile(r"marking|striping|arrow|crosswalk|stop bar|limit line|stop pavement|centerline|turn lane|path|stop\b|school xing|raised pavement marker|bicycle|lane line|transition|parking tee|stall", re.I)
for d in det:
    if d["type"] == "Standard drawing" and d["sg"] != "MUTCD" and LRX.search(d["title"]):
        cards["local"].append(f'<div class="mcard" data-q="{esc((d["num"] + " " + d["title"] + " " + d["src"]).lower())} local"><a class="mimg" href="{d["url"]}"><img loading="lazy" src="{d["img"]}" alt=""></a><div class="mbody"><b>{esc(d["num"])}</b> {esc(d["title"])}<div class="msrc">{esc(d["src"])}{(" &middot; " + esc(d["date"])) if d.get("date") else ""}</div></div></div>')
nav = " ".join(f'<a href="#cat-{k}">{esc(n)} <span>{len(cards[k])}</span></a>' for k, n in CAT)
def head(k, n):
    h = f'<h2 id="cat-{k}">{esc(n)}</h2>'
    if k in SECTION_OF:
        sn = SECTION_OF[k]
        h += f'<p class="mcat-note"><a href="{secs[sn]["url"]}">Governing section: CA MUTCD {sn} {esc(secs[sn]["title"])}</a></p>'
    ct = {"lines": ["A20A", "A20B", "A20C", "A20D", "A20E", "A20F", "A20G"], "arrows": ["A24A", "A24B", "A24H"],
          "words": ["A24B", "A24C", "A24D", "A24E", "A24G", "A24J", "A24L"], "crosswalks": ["A24F", "A24G"], "bike": ["A24C", "A24K"]}
    if k in ct:
        h += '<p class="mcat-note">Caltrans 2026 Standard Plan sheets: ' + ", ".join(f'<a href="{BASE}/details/caltrans/caltrans-std-plans-2026-{n.lower()}/">{n}</a>' for n in ct[k]) + '</p>'
    return h
body = "".join(f'<section class="mcat-sec">{head(k, n)}<div class="mgrid">{"".join(cards[k])}</div></section>' for k, n in CAT)
n_total = sum(len(v) for v in cards.values())
md = f'''---
title: Pavement Marking Library
description: Every Caltrans striping detail, arrow, word and symbol marking, crosswalk pattern, bicycle marking, colored pavement and curb color, cropped from CA MUTCD 2026, plus local agency marking standards.
tableOfContents: false
---

<div class="sfilter mfilter"><input id="mq" type="search" placeholder="Filter markings: Detail 22, Type IV arrow, two-way left-turn, bike lane line, red curb..."><span id="mcount" class="scount">{n_total} markings</span></div>
<nav class="mnav">{nav}</nav>

<p><a class="ai-btn" href="{BASE}/markings/line-types/">Open the Line Type Database</a> <a class="ai-btn ghost" href="{BASE}/ladot/curb-paint/">LADOT curb paint and red curb</a></p>

In California, longitudinal lines follow the Caltrans striping details (Detail 1 to Detail 45) shown in CA MUTCD Figures 3A-101(CA) to 3A-113(CA), and arrows follow the Type I to Type XI arrow details in Figure 3B-21(CA). Each card is cropped straight from CA MUTCD 2026; click a drawing to open it full size. Hover over "Detail 22" (or any detail number) anywhere on this site to preview that detail.

{body}

<script>
(function(){{
  const q=document.getElementById('mq'),n=document.getElementById('mcount');
  const cards=[...document.querySelectorAll('.mcard')];
  const secs=[...document.querySelectorAll('.mcat-sec')];
  const alnum=s=>s.toLowerCase().replace(/[^a-z0-9]/g,'');
  cards.forEach(el=>{{el._a=alnum(el.dataset.q||'');}});
  function run(){{
    const w=q.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
    let c=0;
    cards.forEach(el=>{{
      const ok=!w.length||w.every(x=>el.dataset.q.includes(x)||(alnum(x).length>=2&&el._a.includes(alnum(x))));
      el.style.display=ok?'':'none';
      if(ok)c++;
    }});
    secs.forEach(s=>{{s.style.display=[...s.querySelectorAll('.mcard')].some(el=>el.style.display!=='none')?'':'none';}});
    n.textContent=c+' of '+cards.length+' markings';
    const u=new URLSearchParams(location.search);
    if(q.value.trim()) u.set('q',q.value.trim()); else u.delete('q');
    history.replaceState(null,'',location.pathname+(u.toString()?'?'+u:'')+location.hash);
  }}
  q.addEventListener('input',run);
  const q0=new URLSearchParams(location.search).get('q');
  if(q0){{q.value=q0;run();}}
}})();
</script>
'''
os.makedirs("src/content/docs/markings", exist_ok=True)
open("src/content/docs/markings/index.md", "w").write(md)
# add marking crops to the Detail and Drawing Index
det = [d for d in det if d["type"] != "Marking"]
for i in items:
    det.append({"src": "CA MUTCD 2026", "sg": "MUTCD", "type": "Marking", "num": i["figure"], "title": i["display"] + ((" - " + i.get("sub", "")) if i.get("sub") else ""),
                "img": BASE + i["img"], "url": f"{BASE}/markings/#{i['id']}", "topics": ["striping-intersections"] + (["bikeways"] if i["cat"] == "bike" else []) + (["crosswalks"] if i["cat"] == "crosswalks" else []), "kw": i.get("desc", "")[:200]})
json.dump(det, open("public/data/details.json", "w"), separators=(",", ":"))
# lookup additions + detail previews data
look = json.load(open("public/data/lookup.json"))
for k, (label, url, img) in lookup_add.items():
    look.setdefault(k, []).insert(0, [label, url])
json.dump(look, open("public/data/lookup.json", "w"), separators=(",", ":"))
json.dump({k: {"label": v[0], "url": v[1], "img": v[2]} for k, v in lookup_add.items()}, open("public/data/striping-details.json", "w"))
# link "Detail NN" mentions in readers to previews (hover uses data-svg)
DRX = re.compile(r"(?<![\w>])(Detail\s+(\d{1,2}[A-D]?))(?![\w<])")
n = 0
for f in glob.glob("src/content/docs/ca-mutcd/*.md") + glob.glob("src/content/docs/ladot/*/*.md") + glob.glob("src/content/docs/details/*/*.md") + glob.glob("src/content/docs/burbank/*/*.md") + glob.glob("src/content/docs/pasadena/*/*.md"):
    t = open(f).read()
    t0 = t
    t = re.sub(r'<a class="sref dref"[^>]*>(Detail\s+\d{1,2}[A-D]?)</a>', r"\1", t)
    def sub_p(m):
        inner = m.group(2)
        def rep(mm):
            k = ("DETAIL" + mm.group(2)).upper()
            if k in lookup_add:
                return f'<a class="sref dref" href="{lookup_add[k][1]}" data-svg="{lookup_add[k][2]}">{mm.group(1)}</a>'
            return mm.group(0)
        return m.group(1) + DRX.sub(rep, inner) + m.group(3)
    t = re.sub(r"(<p>|<summary>|<li>)(.*?)(</p>|</summary>|</li>)", sub_p, t, flags=re.S)
    if t != t0:
        open(f, "w").write(t); n += 1
print("markings", n_total, {k: len(v) for k, v in cards.items()}, "files with detail links", n)
