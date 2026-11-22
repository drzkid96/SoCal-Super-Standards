"""Line Type Database: standardized pattern drawings and a filterable index of every Caltrans striping detail."""
import json, os, re, html, sys
sys.path.insert(0, os.path.dirname(__file__))
from striping_db import D, MARKERS
BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
items = {i["detail"].upper().replace("DETAIL ", ""): i for i in json.load(open("data/markings/items.json")) if i["kind"] == "line" and i["detail"].startswith("Detail")}
figs = {}
for f in json.load(open("data/ca-mutcd/figures.json")):
    figs.setdefault(f["id"], f["url"])
os.makedirs("public/linetypes", exist_ok=True)
PX, LEN, X0 = 8, 96, 40           # px per ft, ft shown, left margin
COL = {"Y": "#f6c700", "W": "#ffffff", "K": "#141414"}
MC = {"Y2": ("#f6c700", "#f6c700"), "Y1": ("#f6c700", "#141414"), "C1": ("#ffffff", "#141414"), "RC": ("#ffffff", "#d22b2b"), "RY": ("#f6c700", "#d22b2b")}

def svg(rec):
    rows = rec["rows"]
    ys = [r["y"] for r in rows]
    top, bot = min(ys), max(r["y"] + r.get("w", 4) for r in rows)
    S = 2.0  # px per inch, vertical
    H = int((bot - top) * S + 70)
    W = X0 * 2 + LEN * PX
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Caltrans Detail {rec["d"]}">',
           f'<rect width="{W}" height="{H}" rx="8" fill="#4b4c4e"/>',
           f'<path d="M{X0-26} 20 h16 m-6 -5 l6 5 l-6 5" stroke="#cfcfcf" stroke-width="2.5" fill="none"/>']
    y0 = 35 - top * S
    for r in rows:
        y = y0 + r["y"] * S
        if "t" in r:
            y += 2 * S
            fg, bg = MC[r["t"]]
            x = r["phase"]
            while x <= LEN:
                cx = X0 + x * PX
                out.append(f'<rect x="{cx-4.5:.1f}" y="{y-4.5:.1f}" width="9" height="9" fill="{fg}" stroke="#111" stroke-width="0.8"/>')
                if fg != bg:
                    out.append(f'<rect x="{cx:.1f}" y="{y-4.5:.1f}" width="4.5" height="9" fill="{bg}"/>')
                x += r["every"]
            continue
        h = max(5.0, r["w"] * S * (0.6 if r["c"] == "K" else 1.0))
        c = COL[r["c"]]
        if not r["pat"]:
            out.append(f'<rect x="{X0}" y="{y:.1f}" width="{LEN*PX}" height="{h:.1f}" fill="{c}"/>')
        else:
            on, off, ph = r["pat"]
            x = ph - (on + off) * 4
            while x < LEN:
                a, b = max(0, x), min(LEN, x + on)
                if b > a:
                    out.append(f'<rect x="{X0 + a*PX:.1f}" y="{y:.1f}" width="{(b-a)*PX:.1f}" height="{h:.1f}" fill="{c}"/>')
                x += on + off
    # scale bar
    out.append(f'<g fill="#e8e8e8" font-family="Albert Sans, sans-serif" font-size="11"><rect x="{X0}" y="{H-14}" width="{24*PX}" height="3"/><text x="{X0}" y="{H-18}">24 ft</text>'
               f'<text x="{W - X0}" y="{H-8}" text-anchor="end">Detail {rec["d"]} &#183; 96 ft shown &#183; widths exaggerated</text></g>')
    out.append("</svg>")
    return "\n".join(out)

# Detail -> sheet. Prefer the 2026 Standard Plans (read from the sheets' own detail labels, deleted details left out);
# fall back to the 2018 sheets when the 2026 set is not loaded.
CT, CT_ED = {}, ""
if os.path.exists("data/caltrans_2026_details.json") and os.path.exists("data/docs/caltrans__standard-plans-2026.json"):
    m = json.load(open("data/caltrans_2026_details.json"))
    for sheet, dets in m["sheets"].items():
        for dn in dets:
            CT[dn] = (sheet, "/SoCal-Super-Standards/details/caltrans/caltrans-std-plans-2026-" + sheet.lower() + "/")
    CT_DEL, CT_ED = set(m["deleted"]), "2026"
else:
    CT_SHEETS = {
     "A20A": "1 2 5 6 8 9 9A 11 12 12A 15 16 18 19 21 22",
     "A20B": "24 25 25A 26 27 27B 27C 28 29 31 32 34 34A 35 35A",
     "RSP A20D": "38 38A 38B 38D 39 39A 40 41",
    }
    CT_DEL, CT_ED = set(), "2018"
    if os.path.exists("data/docs/caltrans__standard-plans-2018.json"):
        for sheet, dets in CT_SHEETS.items():
            for dn in dets.split():
                CT[dn] = (sheet, "/SoCal-Super-Standards/details/caltrans/caltrans-std-plans-2018-" + sheet.replace("RSP ", "").lower() + "/")
rows_html, data = [], []
for rec in D:
    k = rec["d"]
    it = items.get(k)
    use = (it or {}).get("desc", "") if it else ""
    if re.match(r"^[\d .ftinmx]+$", use or "x") or use.count(" ft") > 3:
        use = ""
    pic = ""
    if rec["rows"]:
        open(f"public/linetypes/detail-{k.lower()}.svg", "w").write(svg(rec))
        pic = f"{BASE}/linetypes/detail-{k.lower()}.svg"
    crop = f"{BASE}{it['img']}" if it else ""
    furl = figs.get(rec["fig"], f"{BASE}/ca-mutcd/3a/")
    pattern = f'{rec["seg"]} ft line / {rec["gap"]} ft gap ({rec["cycle"]} ft cycle)' if rec.get("seg") else ("Continuous" if "olid" in rec["type"] else rec["type"])
    rec2 = {"detail": k, "function": rec["fn"], "use_case": rec["sub"], "color": rec["color"], "type": rec["type"], "pattern": pattern,
            "segment_ft": rec.get("seg"), "gap_ft": rec.get("gap"), "cycle_ft": rec.get("cycle"), "spacing": rec.get("spacing", ""),
            "markers": rec["markers"], "speed": rec["speed"], "policy": use, "figure": rec["fig"], "plan_sheet": (f"Caltrans Std. Plan {CT[k][0]} ({CT_ED} edition)" if k in CT else (f"Deleted from the Caltrans {CT_ED} Standard Plans" if k in CT_DEL else rec.get("plan", "Caltrans Std. Plans A20A to A20F"))),
            "plan_url": CT[k][1] if k in CT else "",
            "drawing": pic, "source_crop": crop, "url": f"{BASE}/markings/line-types/#detail-{k.lower()}"}
    data.append(rec2)
    q = " ".join(str(v) for v in rec2.values() if isinstance(v, (str, int, float))).lower()
    rows_html.append(f'''<div class="ltc" id="detail-{k.lower()}" data-q="{esc(q)}" data-fn="{esc(rec["fn"])}" data-color="{rec["color"]}" data-speed="{esc(rec["speed"])}" data-type="{esc(rec["type"].lower())}">
<div class="ltc-head"><b>Detail {esc(k)}</b><span class="lt-chip {rec["color"].lower()}">{esc(rec["color"])}</span><span class="ltc-fn">{esc(rec["fn"])}</span><span class="ltc-sub">{esc(rec["sub"])}</span></div>
<div class="ltc-pic">{f'<img loading="lazy" src="{pic}" alt="Standardized drawing of Caltrans Detail {esc(k)}">' if pic else (f'<img loading="lazy" class="src" src="{crop}" alt="CA MUTCD source drawing, Detail {esc(k)}">' if crop else '')}</div>
<dl class="ltc-attr"><div><dt>Type</dt><dd>{esc(rec["type"])}</dd></div><div><dt>Line / gap</dt><dd>{esc(pattern)}</dd></div>{f'<div><dt>Spacing</dt><dd>{esc(rec["spacing"])}</dd></div>' if rec.get("spacing") else ''}<div><dt>Markers</dt><dd>{esc(rec["markers"])}</dd></div><div><dt>Speed</dt><dd>{esc(rec["speed"])}</dd></div><div><dt>Source</dt><dd><a href="{furl}">CA MUTCD Fig. {esc(rec["fig"])}</a></dd></div><div><dt>Plan sheet</dt><dd>{(f'<a href="{rec2["plan_url"]}">' + esc(rec2["plan_sheet"]) + '</a>') if rec2.get("plan_url") else esc(rec2["plan_sheet"])}</dd></div></dl>
{f'<p class="lt-pol">Policy: {esc(use[:300])}</p>' if use else ''}{f'<details class="ltc-src"><summary>Source drawing from CA MUTCD 2026</summary><a href="{crop}" target="_blank"><img loading="lazy" src="{crop}" alt=""></a></details>' if crop and pic else ''}
</div>''')
json.dump(data, open("public/data/linetypes.json", "w"), indent=1)

# pattern index (by geometry)
from collections import defaultdict
pat = defaultdict(list)
for r in data:
    key = f'{r["segment_ft"]} / {r["gap_ft"]} ft' if r["segment_ft"] else ("Solid" if "olid" in r["type"] else r["type"])
    pat[key].append(r["detail"])
pat_rows = "".join(f'<tr><td><b>{esc(k)}</b></td><td>' + ", ".join(f'<a href="#detail-{d.lower()}">{d}</a>' for d in v) + "</td></tr>" for k, v in sorted(pat.items(), key=lambda kv: (kv[0] == "Solid", kv[0])))
fns = sorted({r["fn"] for r in D}, key=lambda f: [r["fn"] for r in D].index(f))
fopts = "".join(f"<option>{esc(f)}</option>" for f in fns)
mk = "".join(f'<li><svg width="18" height="12"><rect x="1" y="1" width="10" height="10" fill="{MC[k][0]}" stroke="#111"/>{f"<rect x=6 y=1 width=5 height=10 fill={MC[k][1]} />" if MC[k][0] != MC[k][1] else ""}</svg> {esc(v)}</li>' for k, v in MARKERS.items())
md = f'''---
title: Line Type Database
description: Every Caltrans striping detail (Detail 1 to Detail 45) as a standardized pattern drawing with color, line type, segment and gap lengths, cycle, spacing, markers, speed range, policy and source figure. Filterable and downloadable.
tableOfContents: false
---

<div class="srcbar">Source: CA MUTCD 2026, Section 3A.04 and Figures 3A-101(CA) to 3A-113(CA). The values below were read from the dimensioned details. Each drawing shows 96 ft of the pattern at the same scale, with line widths exaggerated. <a href="{BASE}/data/linetypes.json">Download the database (JSON)</a></div>

<div class="lt-filter">
<input id="ltq" type="search" placeholder="Search: two-way left-turn, 12 ft, red-clear, bike lane, 45 mph...">
<select id="ltfn"><option value="">All functions</option>{fopts}</select>
<select id="ltcol"><option value="">Any color</option><option>Yellow</option><option>White</option></select>
<select id="ltsp"><option value="">Any speed</option><option>40 mph or less</option><option>45 mph or more</option><option>All</option><option>Freeway</option></select>
<select id="ltty"><option value="">Any type</option><option value="broken">Broken</option><option value="dotted">Dotted</option><option value="solid">Solid</option><option value="double">Double</option><option value="markers">With markers</option></select>
<span id="ltn"></span></div>

<div class="ltlist" id="lt">
{"".join(rows_html)}
</div>

## Pattern index

Details grouped by line and gap geometry.

<table class="dwtab"><thead><tr><th>Line / gap</th><th>Details</th></tr></thead><tbody>{pat_rows}</tbody></table>

## Rules that apply to every detail

- **Line width:** 6 in for lane lines, edge lines and centerlines on State highways; at least 4 in on local agency roadways, where 6 in is an option. A wide line is at least twice the normal width. <a href="{BASE}/s/ca/3A.04/">CA MUTCD 3A.04</a>
- **Federal patterns, for comparison:**
  - broken lines of 10 ft segments and 30 ft gaps (or a similar ratio)
  - dotted lane lines of 3 ft and 9 ft
  - dotted extensions of 2 ft with 2 to 6 ft gaps

  California requires the patterns in Figures 3A-101(CA) to 3A-114(CA), shown above. <a href="{BASE}/s/ca/3A.04/">CA MUTCD 3A.04 paragraphs 06, 07 and 07a</a>
- **Paint centerlines:** where the centerline material is paint, a 3 in black line is placed between the yellow lines on State highways, and may be placed on local streets. (Figure 3A-107(CA), Note 2)
- **Marker legend:**
<ul class="lt-legend">{mk}</ul>

- **Plan sheet references** come from the Caltrans 2026 Standard Plans sheets on this site (A20A to A20F, dated September 18, 2026), read from each sheet's detail labels. Details Caltrans has deleted are marked as deleted. The 2018 sheets remain on the site for reference only.

<script>
(function(){{
  const $=id=>document.getElementById(id);
  const rows=[...document.querySelectorAll('#lt .ltc')];
  const alnum=s=>s.toLowerCase().replace(/[^a-z0-9]/g,'');
  rows.forEach(r=>{{r._a=alnum(r.dataset.q||'');}});
  function run(){{
    const w=$('ltq').value.toLowerCase().trim().split(/\\s+/).filter(Boolean),fn=$('ltfn').value,c=$('ltcol').value,sp=$('ltsp').value,ty=$('ltty').value;
    let n=0;
    rows.forEach(r=>{{
      const ok=(!fn||r.dataset.fn===fn)&&(!c||r.dataset.color===c)&&(!sp||r.dataset.speed===sp)&&(!ty||r.dataset.type.includes(ty))
        &&w.every(x=>r.dataset.q.includes(x)||(alnum(x).length>=2&&r._a.includes(alnum(x))));
      r.style.display=ok?'':'none';
      if(ok)n++;
    }});
    $('ltn').textContent=n+' of '+rows.length+' details';
    const u=new URLSearchParams();
    if($('ltq').value.trim()) u.set('q',$('ltq').value.trim());
    if(fn) u.set('fn',fn); if(c) u.set('col',c); if(sp) u.set('sp',sp); if(ty) u.set('ty',ty);
    history.replaceState(null,'',location.pathname+(u.toString()?'?'+u:'')+location.hash);
  }}
  const p=new URLSearchParams(location.search);
  if(p.get('q')) $('ltq').value=p.get('q');
  if(p.get('fn')) $('ltfn').value=p.get('fn');
  if(p.get('col')) $('ltcol').value=p.get('col');
  if(p.get('sp')) $('ltsp').value=p.get('sp');
  if(p.get('ty')) $('ltty').value=p.get('ty');
  ['ltq','ltfn','ltcol','ltsp','ltty'].forEach(i=>$(i).addEventListener('input',run));
  run();
  if(location.hash){{const t=document.querySelector(location.hash);if(t)t.classList.add('lt-hit');}}
}})();
</script>
'''
os.makedirs("src/content/docs/markings", exist_ok=True)
open("src/content/docs/markings/line-types.md", "w").write(md)
# point detail lookups and hover previews at the standardized drawing
look = json.load(open("public/data/lookup.json"))
for r in data:
    key = ("DETAIL" + r["detail"]).upper()
    entry = [f'Caltrans Detail {r["detail"]}: {r["function"]} ({r["pattern"]})', r["url"]]
    look[key] = [entry] + [e for e in look.get(key, []) if "/markings/#" not in e[1]]
json.dump(look, open("public/data/lookup.json", "w"), separators=(",", ":"))
det = [d for d in json.load(open("public/data/details.json")) if d["type"] != "Line type"]
for r in data:
    det.append({"src": "CA MUTCD 2026", "sg": "MUTCD", "type": "Line type", "num": "Detail " + r["detail"], "title": f'{r["function"]}: {r["use_case"]} ({r["color"]}, {r["pattern"]})',
                "img": r["drawing"] or r["source_crop"], "url": r["url"], "topics": ["striping-intersections"] + (["bikeways"] if "Bike" in r["function"] else []), "kw": r["policy"][:200] + " " + r["markers"]})
json.dump(det, open("public/data/details.json", "w"), separators=(",", ":"))
print("line types", len(data), "drawn", sum(1 for r in data if r["drawing"]))
