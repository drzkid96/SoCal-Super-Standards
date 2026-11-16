"""LADOT hub page: documents, a combined standard-drawing index across all LADOT documents, sign back-links."""
import json, os, re, html, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
BASE = "/SoCal-Super-Standards"
cfg = json.load(open(f"{ROOT}/pipeline/config/ladot.json"))
docs = [json.load(open(f"{ROOT}/data/docs/{c['slug'].replace('/', '__')}.json")) | {"cfg": c} for c in cfg]
esc = lambda t: html.escape(str(t), quote=False)
rows = "".join(f'<tr><td><a href="{BASE}/{d["slug"]}/"><strong>{esc(d["title"])}</strong></a></td><td>{esc(d["edition"])}</td>'
               f'<td>{len(d["pages"])}</td><td>{sum(1 for p in d["pages"] if p["image"])}</td><td>{len(d["drawings"])}</td></tr>' for d in docs)
# combined drawing index
dw = []
for d in docs:
    for k, v in d["drawings"].items():
        t = d.get("drawing_titles", {}).get(k, {})
        dw.append((k, t.get("title", ""), t.get("date", ""), d["short"], d["slug"], v))
key = lambda x: [int(n) for n in re.findall(r"\d+", x[0])]
dwrows = "".join(f'<tr data-q="{esc((k + " " + t + " " + s).lower())}"><td><strong>{esc(k)}</strong></td><td>{esc(t)}</td><td>{esc(dt)}</td><td>{esc(s)}</td><td>'
                 + " ".join(f'<a href="{BASE}/{sl}/{p["chapter"]}/#p{p["page"]}">p{p["page"]}</a>' for p in v[:8]) + "</td></tr>"
                 for k, t, dt, s, sl, v in sorted(dw, key=key))
md = f"""---
title: LADOT standards
description: Every LADOT manual, policy and standard drawing on this site, with a combined standard-drawing index.
tableOfContents: false
---

<div class="srcbar">City of Los Angeles Department of Transportation and partner agencies &middot; {len(docs)} documents &middot; {sum(len(d["pages"]) for d in docs)} pages</div>

Every page of every LADOT document is here: native text where the PDF has it, OCR where it is a scan or outlined CAD text, and a sharpened image of every drawing or figure page. Sign codes link to the [Sign Library]({BASE}/signs/) and MUTCD section references link to the manuals. Search (Ctrl+K) covers all of it, OCR text included.

## Documents

<table class="dwtab"><thead><tr><th>Document</th><th>Edition</th><th>Pages</th><th>Drawing and figure pages</th><th>Std. drawings</th></tr></thead><tbody>{rows}</tbody></table>

**Superseded, not on this site:** MPP 531 dated 06/23/2022 (replaced by 02/2023) and the 2028 Games Corridors Design Guide of 09/2025 (replaced by the 06/2026 print). LADOT CSC documents (LPI, EPP, Lane Reconfiguration, Bikeway Marking) and the Drafting Manual are not loaded yet.

## Standard drawing index

Numbers are as printed on each document. MPP 531 drawings are the S-100 to S-527 striping and signing series; MPP 521 and the Red Book use the S-50 to S-99 signal series, so the same number can mean different things in different documents.

<input id="dwq" class="dwq" type="search" placeholder="Filter drawings: number, title or document (e.g. crosswalk, S-481, bus bulb)">

<table class="dwtab" id="dwtab"><thead><tr><th>Drawing</th><th>Title</th><th>Dated</th><th>Document</th><th>Sheets</th></tr></thead><tbody>{dwrows}</tbody></table>

<script>
document.getElementById('dwq').addEventListener('input', e => {{
  const q = e.target.value.toLowerCase().trim();
  document.querySelectorAll('#dwtab tbody tr').forEach(r => r.style.display = !q || r.dataset.q.includes(q) ? '' : 'none');
}});
</script>
"""
open(f"{ROOT}/src/content/docs/ladot/index.md", "w").write(md)

# sign back-links: append "In LADOT documents" to each sign page
refs = {}
for d in docs:
    for p in d["pages"]:
        for c in p["sign_codes"]:
            refs.setdefault(c, []).append((d["short"], p["url"], p["page"], p["title"]))
signs = json.load(open(f"{ROOT}/data/signs/signs.json"))
n = 0
for s in signs:
    f = f"{ROOT}/src/content/docs/signs/{s['slug']}.md"
    if not os.path.exists(f):
        continue
    t = open(f).read()
    t = re.sub(r"\n<!-- ladot -->.*", "", t, flags=re.S)
    r = refs.get(s["code"])
    if r:
        n += 1
        t += "\n<!-- ladot -->\n## In LADOT documents\n\n" + "\n".join(f'- [{esc(a)}, page {pg}{(" - " + esc(ti)) if ti else ""}]({u})' for a, u, pg, ti in r[:30]) + "\n"
    open(f, "w").write(t)
json.dump({c: [{"doc": a, "url": u, "page": pg} for a, u, pg, ti in v] for c, v in refs.items()}, open(f"{ROOT}/public/data/ladot-sign-refs.json", "w"))
# compact page index for the AI agent
json.dump([{"doc": d["short"], "page": p["page"], "title": p["title"], "url": p["url"], "drawings": p["drawings"][:4], "signs": p["sign_codes"][:12], "topics": p["topics"]}
           for d in docs for p in d["pages"]], open(f"{ROOT}/public/data/ladot-index.json", "w"))
print("drawings", len(dw), "signs with LADOT refs", n)
