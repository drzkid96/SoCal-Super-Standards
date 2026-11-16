"""Outline reference cards for copyrighted design guides: headings and page numbers only, no text or figures."""
import json, re, html, os, sys
import pymupdf
sys.path.insert(0, os.path.dirname(__file__))
from topics_def import T
BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
TOPIC_RX = {t[0]: re.compile(t[4] + "|" + t[6], re.I) for t in T}
TN = {t[0]: t[1] for t in T}
U = "/mnt/user-data/uploads/"
G = [
 dict(slug="nacto-urban-bikeway", path=U + "dd934814-NACTO-BIKEWAY-DESIGN-GUIDE.pdf", title="NACTO Urban Bikeway Design Guide", short="NACTO UBDG",
      edition="Third edition (Island Press)", url="https://nacto.org/publication/urban-bikeway-design-guide/", maxlvl=3,
      about="NACTO's national guide to designing bikeways and bike intersections for all ages and abilities. It covers network planning, bike lane and protected bikeway types, intersection treatments and maintenance. It is guidance, not a standard: in California, CA MUTCD 2026 and Caltrans and local standards govern devices and markings."),
 dict(slug="nacto-urban-street", path=U + "7cd360d1-NACTO-URBAN-STREET-DESIGN-GUIDE.pdf", title="NACTO Urban Street Design Guide", short="NACTO USDG",
      edition="2013 (Island Press)", url="https://nacto.org/publication/urban-street-design-guide/", maxlvl=3,
      about="NACTO's guide to designing city streets: street types, street design elements (lanes, sidewalks, curb extensions, transit), interim strategies, intersections, intersection design elements, and design controls such as design speed and design vehicle. Guidance only."),
 dict(slug="cpbs-plts", path=U + "8bfaa087-CPBS-PLTS-APPLICATION-AND-VALIDATION-2025-07.pdf", title="Pedestrian Level of Traffic Stress (PLTS) Application and Validation", short="CPBS PLTS",
      edition="July 2025, Center for Pedestrian and Bicyclist Safety (Schneider et al.)", url="https://pedbikesafety.org/", maxlvl=3,
      about="A research report that applies and validates a pedestrian level of traffic stress (PLTS) method for rating how stressful streets and crossings feel to walk along and across. Appendix A has the PLTS criteria. Use it for network analysis and prioritization, not as a design standard."),
]
os.makedirs("src/content/docs/guides", exist_ok=True)
cards = []
for g in G:
    d = pymupdf.open(g["path"])
    toc = [t for t in d.get_toc() if t[0] <= g["maxlvl"] and t[2] >= 1]
    toc = [t for t in toc if not re.match(r"(Cover|About Island Press|Subscribe|Title Page|Contents|Copyright)", t[1])]
    rows, entries = [], []
    for i, (lvl, t, p) in enumerate(toc):
        t = re.sub(r"\s+", " ", t).strip()
        nxt = next((x[2] for x in toc[i + 1:] if x[0] <= lvl), len(d) + 1)
        tops = [k for k, rx in TOPIC_RX.items() if rx.search(t)]
        entries.append({"title": t, "level": lvl, "page": p, "end": max(p, nxt - 1), "topics": tops})
        chips = " ".join(f'<a class="chip" href="{BASE}/topics/{k}/">{esc(TN[k])}</a>' for k in tops)
        rows.append(f'<tr class="lv{lvl}"><td style="padding-left:{(lvl - 1) * 1.2}rem">{"<b>" if lvl == 1 else ""}{esc(t)}{"</b>" if lvl == 1 else ""}</td><td class="src-page">PDF p. {p}{"&ndash;" + str(max(p, nxt - 1)) if nxt - 1 > p else ""}</td><td>{chips}</td></tr>')
    g["entries"] = entries
    md = f'''---
title: "{g["title"]}"
description: "Outline and page index for {g["title"]}. Headings and page numbers only."
tableOfContents: false
---

<div class="srcbar">{esc(g["edition"])} &middot; {len(d)} pages &middot; outline only</div>

{esc(g["about"])}

<div class="note-box">This guide is copyrighted, so this site shows only its outline and page numbers, never its text or figures. Open your own copy at the page listed, or get it from <a href="{g["url"]}">the publisher</a>. Each heading links to the topic pages where the matching CA MUTCD and local standards are.</div>

<input class="dwq" type="search" placeholder="Filter headings" oninput="const q=this.value.toLowerCase();this.nextElementSibling.querySelectorAll('tbody tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?'':'none')">
<table class="dwtab outline"><thead><tr><th>Heading</th><th>Pages</th><th>Topics on this site</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
'''
    open(f"src/content/docs/guides/{g['slug']}.md", "w").write(md)
    cards.append(g)
json.dump([{k: g[k] for k in ("slug", "title", "short", "edition", "entries")} for g in cards], open("data/refcards.json", "w"))
open("src/content/docs/guides/index.md", "w").write(f'''---
title: Design guides (outline only)
description: Copyrighted national design guides, indexed by heading and page so you can go straight to the right page in your copy.
tableOfContents: false
---

These guides are copyrighted. The site indexes their headings and page numbers and links each heading to the matching topic page. It does not reproduce their text or figures.

<div class="tcards">{"".join(f'<a class="tcard" href="{BASE}/guides/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["about"])}</span><em>{esc(g["edition"])} &middot; {len(g["entries"])} headings</em></a>' for g in cards)}</div>
''')
print([(g["short"], len(g["entries"])) for g in cards])
