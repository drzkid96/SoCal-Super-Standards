"""Reference guide indexes: supports PDF-bookmark outlines (NACTO, CPBS) and JSON-backed structured indexes (AASHTO GBF-5)."""
import json, re, html, os, sys
try:
    import pymupdf
except ImportError:
    pymupdf = None
sys.path.insert(0, os.path.dirname(__file__))
from topics_def import T

BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)
TOPIC_RX = {t[0]: re.compile(t[4] + "|" + t[6], re.I) for t in T}
TN = {t[0]: t[1] for t in T}
U = "/mnt/user-data/uploads/"

PDF_GUIDES = [
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

prev_cards = {}
if os.path.exists("data/refcards.json"):
    for c in json.load(open("data/refcards.json")):
        prev_cards[c["slug"]] = c

os.makedirs("src/content/docs/guides", exist_ok=True)
cards = []

# ------------------------------------------------------------------ AASHTO GBF-5 (2024) from data/aashto_gbf5.json
if os.path.exists("data/aashto_gbf5.json"):
    gb = json.load(open("data/aashto_gbf5.json"))
    gbf_figs_dir = "public/figs/aashto/gbf-5"
    has_extracted_figs = os.path.isdir(gbf_figs_dir) and any(f.endswith(".webp") for f in os.listdir(gbf_figs_dir))
    has_full_chapters = os.path.isdir("src/content/docs/aashto/bike-guide") and any(f.endswith(".md") for f in os.listdir("src/content/docs/aashto/bike-guide"))

    # Chapter summary table
    ch_rows = []
    ch_page = {s["chapter"]: s["page"] for s in gb["sections"] if s["level"] == 1 and s["num"].startswith("Ch.")}
    for ch in gb["chapters"]:
        pg = ch_page.get(ch["num"], f"{ch['num']}-1")
        ch_link = f'<a href="{BASE}/aashto/bike-guide/ch-{ch["num"]:02d}/"><b>Chapter {ch["num"]}: {esc(ch["title"])}</b></a>' if has_full_chapters else f'<b>Chapter {ch["num"]}: {esc(ch["title"])}</b>'
        ch_rows.append(
            f'<tr><td>{ch_link}</td>'
            f'<td><span class="badge {"ca-amend" if ch["status"] == "New" else "ca-same"}">{esc(ch["status"])}</span></td>'
            f'<td>{esc(ch["summary"])}</td>'
            f'<td class="src-page">p. {esc(pg)}</td></tr>'
        )

    # December 2024 Errata table
    err_rows = []
    for er in gb["errata"]:
        err_rows.append(
            f'<tr><td class="src-page">p. {esc(er["page"])}</td>'
            f'<td><b>{esc(er["section"])}</b></td>'
            f'<td>{esc(er["stale"])}</td>'
            f'<td>{esc(er["corrected"])}</td></tr>'
        )

    # Full filterable index: Sections + Figures + Tables
    idx_rows = []
    ref_entries = []
    for s in gb["sections"]:
        label = f'{s["num"]} {s["title"]}'.strip() if s["num"] else s["title"]
        tops = [k for k, rx in TOPIC_RX.items() if rx.search(s["title"])]
        if "bikeways" not in tops and s["level"] == 1:
            tops = ["bikeways"] + tops
        if s["level"] <= 2:
            ref_entries.append({"title": label, "level": s["level"], "page": s["page"], "end": s["page"], "topics": tops})
        chips = " ".join(f'<a class="chip" href="{BASE}/topics/{k}/">{esc(TN[k])}</a>' for k in tops[:3])
        pad = (s["level"] - 1) * 1.1
        idx_rows.append(
            f'<tr class="lv{s["level"]}" data-kind="sec" data-ch="{s["chapter"]}">'
            f'<td><span class="badge muted">Section</span></td>'
            f'<td style="padding-left:{pad:.1f}rem">{"<b>" if s["level"] == 1 else ""}{esc(label)}{"</b>" if s["level"] == 1 else ""}</td>'
            f'<td class="src-page">p. {esc(s["page"])}</td>'
            f'<td>{chips}</td></tr>'
        )

    for fig in gb["figures"]:
        tops = [k for k, rx in TOPIC_RX.items() if rx.search(fig["title"])]
        chips = " ".join(f'<a class="chip" href="{BASE}/topics/{k}/">{esc(TN[k])}</a>' for k in tops[:3])
        fslug = f'fig-{fig["num"].lower()}.webp'
        fimg = f' <a href="{BASE}/figs/aashto/gbf-5/{fslug}">View figure</a>' if (has_extracted_figs and os.path.exists(f"{gbf_figs_dir}/{fslug}")) else ""
        enote = f' <span class="badge rev" title="{esc(fig["errata"])}">Errata</span>' if fig.get("errata") else ""
        idx_rows.append(
            f'<tr data-kind="fig" data-ch="{fig["chapter"]}">'
            f'<td><span class="badge ca-amend">Figure</span></td>'
            f'<td><b>Figure {esc(fig["num"])}:</b> {esc(fig["title"])}{enote}{fimg}</td>'
            f'<td class="src-page">p. {esc(fig["page"])}</td>'
            f'<td>{chips}</td></tr>'
        )

    for tab in gb["tables"]:
        tops = [k for k, rx in TOPIC_RX.items() if rx.search(tab["title"])]
        chips = " ".join(f'<a class="chip" href="{BASE}/topics/{k}/">{esc(TN[k])}</a>' for k in tops[:3])
        idx_rows.append(
            f'<tr data-kind="tab" data-ch="{tab["chapter"]}">'
            f'<td><span class="badge ca-same">Table</span></td>'
            f'<td><b>Table {esc(tab["num"])}:</b> {esc(tab["title"])}</td>'
            f'<td class="src-page">p. {esc(tab["page"])}</td>'
            f'<td>{chips}</td></tr>'
        )

    about = ("AASHTO's national bicycle facility design guide (5th Edition, December 2024; supersedes the 2012 4th Edition). "
             "Covers bikeway selection, elements of design, shared use paths, separated bike lanes, side paths, bicycle boulevards, "
             "conventional/buffered bike lanes, signals, interchanges, roundabouts, structures, and wayfinding across 16 chapters. "
             "National guidance only: in California, Caltrans HDM Chapter 1000, DIB 89-02, and CA MUTCD 2026 Part 9 govern.")

    status_note = (
        f'<div class="note-box"><b>California precedence (SHC &sect; 891):</b> AASHTO GBF-5 is national engineering guidance. '
        f'In California, <a href="{BASE}/bulletins/caltrans-hdm-ch1000/">Caltrans HDM Chapter 1000</a> (rev. 12/16/2024), '
        f'<a href="{BASE}/bulletins/caltrans-dib-89-02/">Caltrans DIB 89-02</a> (Class IV), and '
        f'<a href="{BASE}/ca-mutcd/9a/">CA MUTCD 2026 Part 9</a> govern. '
        f'See the <a href="{BASE}/bulletins/bikeway-design-comparison/">Bikeway Design Comparison</a> for side-by-side differences and California overrides. '
        f'Source: <a href="{gb["url"]}">AASHTO GBF-5</a> &middot; <a href="{gb["errata_url"]}">December 2024 Errata (PDF)</a>.</div>'
    )

    md = f'''---
title: "{gb["title"]}"
description: "Complete 16-chapter section, figure, table, and errata index for AASHTO Guide for the Development of Bicycle Facilities, 5th Edition (GBF-5, December 2024)."
tableOfContents: false
---

<div class="srcbar">{esc(gb["edition"])} &middot; {gb["pages"]} pages &middot; ISBN {esc(gb["isbn"])} &middot; 16 chapters, {len(gb["sections"])} sections, {len(gb["figures"])} figures, {len(gb["tables"])} tables</div>

{about}

{status_note}

## Chapters (16)

<table class="dwtab"><thead><tr><th>Chapter</th><th>Status vs. 2012</th><th>Scope</th><th>Start</th></tr></thead><tbody>{"".join(ch_rows)}</tbody></table>

## December 2024 Errata

Technical corrections issued by AASHTO in [GBF-5-Errata.pdf]({gb["errata_url"]}). Verify these against printed or early digital copies before citing.

<table class="dwtab"><thead><tr><th>Page</th><th>Section / Figure</th><th>Pre-errata text</th><th>Corrected</th></tr></thead><tbody>{"".join(err_rows)}</tbody></table>

## Full Index: Sections ({len(gb["sections"])}), Figures ({len(gb["figures"])}), and Tables ({len(gb["tables"])})

<div class="sbtns" id="gbf-tabs" style="margin-bottom:.5rem">
<button type="button" class="on" data-k="all">All ({len(idx_rows)})</button>
<button type="button" data-k="sec">Sections ({len(gb["sections"])})</button>
<button type="button" data-k="fig">Figures ({len(gb["figures"])})</button>
<button type="button" data-k="tab">Tables ({len(gb["tables"])})</button>
</div>
<input class="dwq" id="gbf-q" type="search" placeholder="Filter by section, figure, table, or keyword (e.g. protected intersection, vertical curve, Table 7-3, buffer)...">
<table class="dwtab outline" id="gbf-tbl"><thead><tr><th>Type</th><th>Title</th><th>Page</th><th>Topics on this site</th></tr></thead><tbody>{"".join(idx_rows)}</tbody></table>

<script>
(() => {{
  const tabs = document.getElementById('gbf-tabs');
  const inp = document.getElementById('gbf-q');
  const rows = Array.from(document.querySelectorAll('#gbf-tbl tbody tr'));
  let kind = 'all';
  const apply = () => {{
    const q = (inp.value || '').toLowerCase().trim();
    for (const r of rows) {{
      const okK = kind === 'all' || r.dataset.kind === kind;
      const okQ = !q || r.textContent.toLowerCase().includes(q);
      r.style.display = (okK && okQ) ? '' : 'none';
    }}
  }};
  tabs.addEventListener('click', (e) => {{
    const b = e.target.closest('button[data-k]');
    if (!b) return;
    kind = b.dataset.k;
    tabs.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
    apply();
  }});
  inp.addEventListener('input', apply);
}})();
</script>
'''
    open("src/content/docs/guides/aashto-bike-guide.md", "w").write(md)
    cards.append({
        "slug": "aashto-bike-guide",
        "title": gb["title"],
        "short": gb["short"],
        "edition": gb["edition"],
        "about": about,
        "entries": ref_entries,
        "meta_label": f'{len(gb["chapters"])} chapters &middot; {len(gb["figures"])} figures &middot; {len(gb["tables"])} tables',
    })

# ------------------------------------------------------------------ PDF-backed guides (NACTO, CPBS)
for g in PDF_GUIDES:
    if pymupdf and os.path.exists(g["path"]):
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
    elif g["slug"] in prev_cards:
        # Preserve existing generated page & entries when local source PDF is absent
        g["entries"] = prev_cards[g["slug"]]["entries"]
        cards.append(g)

json.dump([{k: g[k] for k in ("slug", "title", "short", "edition", "entries")} for g in cards], open("data/refcards.json", "w"))
open("src/content/docs/guides/index.md", "w").write(f'''---
title: National Design Guides
description: National bicycle, street, and pedestrian design guides (AASHTO, NACTO, CPBS), indexed by chapter, section, figure, and table and cross-linked to governing California standards.
tableOfContents: false
---

National design guides indexed by chapter, section, figure, and table, linked directly to the governing California MUTCD, Caltrans, and local standards on this site.

<div class="tcards">{"".join(f'<a class="tcard" href="{BASE}/guides/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["about"])}</span><em>{esc(g["edition"])} &middot; {g.get("meta_label") or (str(len(g["entries"])) + " headings")}</em></a>' for g in cards)}</div>
''')
print([(g["short"], len(g["entries"])) for g in cards])
