"""Supersedence and relevance checks for every page.

Writes public/data/checks.json  {page_path: [{sev, title, text, links:[[label, url]], for}]}
and src/content/docs/bulletins/standards-status.md.
sev: "warn" = something newer or deleted governs; "info" = guidance in effect that bears on this page.
Run after build_bulletins.py and build_index.py.
"""
import collections, glob, json, os, re

BASE = "/SoCal-Super-Standards"
CHECKED = "November 18, 2026"
B = f"{BASE}/bulletins"
det = json.load(open("public/data/details.json"))
signs = json.load(open("public/data/signs-index.json"))
deleted = json.load(open("data/ca_deleted_signs.json"))
DEL = {re.sub(r"\s+", "", k.upper()): v for k, v in deleted["codes"].items()}
CT26 = "https://dot.ca.gov/programs/design/2026-ccs-standard-plans-and-standard-specifications"

checks = collections.defaultdict(list)


def add(path, sev, title, text, links=(), for_=""):
    path = path.split("#")[0]
    for c in checks[path]:
        if c["title"] == title:
            if for_ and for_ not in c["for"].split(", "):
                c["for"] = (c["for"] + ", " + for_).strip(", ")
            return
    checks[path].append({"sev": sev, "title": title, "text": text, "links": [list(l) for l in links], "for": for_})


# ---------------------------------------------------------------- rule: same drawing in several documents
def dkey(d):
    m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", d or "")
    if not m:
        return None
    mo, dy, yr = map(int, m.groups())
    yr += 2000 if yr < 50 else (1900 if yr < 100 else 0)
    return (yr, mo, dy)


# document edition dates used when a sheet carries no date of its own
DOC_DATE = {"Red Book": "01-01-26"}
REPRINT = {"Supp. Street Design Guide", "Crosswalk Guidelines", "Parking Standards"}  # reprints of MPP sheets

bynum = collections.defaultdict(list)
for x in det:
    if x["type"] == "Standard drawing":
        bynum[x["num"]].append(x)
for num, xs in bynum.items():
    if len({x["src"] for x in xs}) < 2:
        continue
    for x in xs:
        if not x.get("date") and x["src"] in DOC_DATE:
            x["_d"] = DOC_DATE[x["src"]]
        else:
            x["_d"] = x.get("date")
    dated = [x for x in xs if dkey(x["_d"])]
    newest = max(dated, key=lambda x: dkey(x["_d"])) if dated else None
    for x in xs:
        others = [o for o in xs if o is not x and o["src"] != x["src"]]
        links = [(f'{o["src"]} {num}' + (f' ({o["date"]})' if o.get("date") else ""), o["url"]) for o in others]
        nd = newest["_d"] if newest else ""
        nlab = f"dated {newest['date']}" if newest and newest.get("date") else f"in its {nd[-2:] and '20' + nd[-2:]} edition" if newest else ""
        if newest and newest is not x and newest["src"] != x["src"] and dkey(x["_d"]) and dkey(x["_d"]) < dkey(nd):
            txt = (f"This copy is dated {x['_d']}. {newest['src']} carries {num} dated {newest['date']}. Use the newer sheet unless the project is tied to this edition."
                   if newest.get("date") else
                   f"This copy is dated {x['_d']}. The {newest['src']} (20{nd[-2:]} edition, the City's current contract set) also carries {num}. Compare the two sheets and cite the {newest['src']} copy where they differ.")
            add(x["url"], "warn", f"Newer copy of {num} in {newest['src']}", txt, links, num)
        elif newest and newest is not x and not dkey(x["_d"]) and x["src"] in REPRINT:
            add(x["url"], "warn", f"Controlling copy of {num} is in {newest['src']}",
                f"This document reprints {num} without its own date. The standard drawing is maintained in {newest['src']} ({nlab}). Cite that copy.",
                links, num)
        else:
            add(x["url"], "info", f"{num} also appears in other documents",
                "The same drawing number is published in more than one LADOT document. Confirm the sheets match before citing one.", links, num)

# ---------------------------------------------------------------- rule: Caltrans 2018 Standard Plans
for x in det:
    if x["src"].startswith("Caltrans Std. Plans 2018"):
        add(x["url"], "warn", "Caltrans 2026 Standard Plans supersede the 2018 sheets",
            "Caltrans issued the 2026 Standard Plans (revision digest October 19, 2026). The A20 pavement marker details were revised, including Types G and H markers. Check the 2026 sheet before citing this one on a State highway project.",
            [("Caltrans 2026 sheets on this site", f"{BASE}/caltrans/standard-plans-2026/"), ("Caltrans Standard Plans (official)", CT26)], x["num"])
for f in glob.glob("src/content/docs/caltrans/standard-plans-2018/**/*.md", recursive=True):
    p = f[len("src/content/docs"):-3]
    p = BASE + (p[:-6] if p.endswith("/index") else p) + "/"
    add(p, "warn", "Caltrans 2026 Standard Plans supersede the 2018 sheets",
        "Caltrans issued the 2026 Standard Plans (revision digest October 19, 2026). The A20 pavement marker details were revised, including Types G and H markers.",
        [("Caltrans 2026 sheets on this site", f"{BASE}/caltrans/standard-plans-2026/"), ("Caltrans Standard Plans (official)", CT26)])

# ---------------------------------------------------------------- rule: deleted CA signs referenced
sign_re = re.compile(r"\b([A-Z]{1,3}\d{1,3}(?:-\d{1,3})?[A-Z]{0,2}(?:-\d)?[A-Z]?)\s?\((?:CA)\)")
del_note = f"Caltrans lists these California signs as deleted in CA MUTCD 2026 (list dated {deleted['date']}). Use the current federal or California sign shown in CA MUTCD 2026 Part 2."


def page_path(f):
    p = f[len("src/content/docs"):-3]
    return BASE + (p[:-6] if p.endswith("/index") else p) + "/"


for f in glob.glob("src/content/docs/**/*.md", recursive=True):
    if "/ca-mutcd/" in f or "/signs/" in f or "/bulletins/" in f:
        continue
    t = open(f).read()
    hits = sorted({m.group(1) + "(CA)" for m in sign_re.finditer(t) if (m.group(1) + "(CA)") in DEL})
    if hits:
        add(page_path(f), "warn", "Refers to California signs deleted in CA MUTCD 2026",
            del_note + " On this page: " + ", ".join(f"{h} ({DEL[h]})" for h in hits[:8]) + ("" if len(hits) <= 8 else f", and {len(hits) - 8} more") + ".",
            [("Standards status: deleted CA signs", f"{B}/standards-status/#deleted-california-signs"), ("Caltrans deleted sign list", deleted["source"])])
for code, s in signs.items():
    if re.sub(r"\s+", "", code.upper()) in DEL:
        add(s["url"], "warn", f"{code} was deleted in CA MUTCD 2026", del_note,
            [("Standards status: deleted CA signs", f"{B}/standards-status/#deleted-california-signs")])

# ---------------------------------------------------------------- rule: federal MUTCD vs CA MUTCD
for f in glob.glob("src/content/docs/mutcd/*.md"):
    ch = os.path.basename(f)[:-3]
    links = [("Standards status", f"{B}/standards-status/")]
    if os.path.exists(f"src/content/docs/ca-mutcd/{ch}.md"):
        links.insert(0, ("CA MUTCD 2026" if ch == "index" else f"CA MUTCD 2026 Chapter {ch.upper()}", f"{BASE}/ca-mutcd/" + ("" if ch == "index" else f"{ch}/")))
    add(page_path(f), "warn", "In California, the CA MUTCD 2026 governs",
        "This is the federal MUTCD 11th Edition Revision 1 (effective March 5, 2026). California has two years to adopt the revision, so on California streets the CA MUTCD 2026 (effective January 18, 2026) is the standard until Caltrans issues a revision.",
        links)
for f in glob.glob("src/content/docs/ca-mutcd/*.md"):
    add(page_path(f), "info", "Federal MUTCD Revision 1 is pending adoption in California",
        "FHWA issued MUTCD 11th Edition Revision 1 (effective March 5, 2026). Caltrans has a CA MUTCD revision in process through the CTCDC. This edition governs until that revision takes effect.",
        [("Standards status", f"{B}/standards-status/")])

# ---------------------------------------------------------------- rule: LA28 Supplement amends CA MUTCD chapters on the GRN
L28 = f"{BASE}/caltrans/la28-supplement/"
l28_secs = collections.defaultdict(lambda: collections.OrderedDict())
for f in sorted(glob.glob("src/content/docs/caltrans/la28-supplement/*.md")):
    t = open(f).read()
    for sec in re.findall(r"<p><a href=\"[^\"]*/s/ca/(\d[A-Z])\.(\d{2,3})/\">Section \1\.\2</a> [A-Z]", t):
        l28_secs[sec[0]][sec[0] + "." + sec[1]] = page_path(f)
    add(page_path(f), "info", "LA28 Supplement applies only on the Games Route Network",
        "These provisions supplement CA MUTCD 2026 for roadways in the established Games Route Network (GRN). LA28 and PERMIT ONLY markings are in place from June 1 to September 1, 2028 and are then removed and the prior markings restored.",
        [("CA MUTCD 2026", f"{BASE}/ca-mutcd/"), ("LADOT 2028 Games Corridors guide", f"{BASE}/ladot/games-corridors/")])
for ch, secs in l28_secs.items():
    first = next(iter(secs.values()))
    for root, lab in (("ca-mutcd", "warn"), ("mutcd", "info")):
        if os.path.exists(f"src/content/docs/{root}/{ch.lower()}.md"):
            add(f"{BASE}/{root}/{ch.lower()}/", "info", f"LA28 Supplement amends Chapter {ch} on the Games Route Network",
                f"On GRN roadways during the 2028 Games, the LA28 Supplement (effective July 15, 2026) adds to Section{'s' if len(secs) > 1 else ''} {', '.join(list(secs)[:10])}{' and others' if len(secs) > 10 else ''}.",
                [("LA28 Supplement, Chapter " + ch, first), ("LA28 Supplement overview", L28)])
for f in glob.glob("src/content/docs/ladot/games-corridors/*.md"):
    add(page_path(f), "info", "CA MUTCD LA28 Supplement (July 15, 2026)",
        "Caltrans' LA28 Supplement sets the LA28 plaques and panels (light blue), PERMIT ONLY signs, LA28 word markings and CMS messages for Games Route Network lanes. Check it against this guide's details.",
        [("LA28 Supplement", L28)])

# ---------------------------------------------------------------- rule: concept-driven guidance in effect
RULES = [
    ({"lanewidth", "xsection", "dib"}, "Lane widths: DIB 94, MPP 531 and BOE differ",
     "Caltrans DIB 94 sets 10.5 to 12 ft lanes on State highways. LADOT MPP 531 allows narrower City lanes. Compare before setting widths, especially where a City street continues onto a State route.",
     [("Lane width comparison", f"{B}/lane-widths/"), ("Caltrans DIB 94", f"{B}/caltrans-dib-94/")]),
    ({"bikelane", "cycletrack", "greenpaint", "bikebox", "sharrow", "bikecross"}, "LADOT Bikeway Marking guidance (Dec 2022)",
     "In Los Angeles, the 2022 LADOT bikeway marking guidance sets green paint, conflict zone and bike box practice and can be newer than the drawing on this page.",
     [("LADOT Bikeway Marking (2022)", f"{B}/ladot-bikeway-marking-2022/")]),
    ({"lpi"}, "LADOT LPI policy (rev. June 2021)",
     "LADOT leading pedestrian interval policy sets where LPIs are installed and their timing.",
     [("LADOT LPI policy", f"{B}/ladot-lpi-2021/")]),
    ({"diagonal"}, "LADOT Exclusive Pedestrian Phase policy (Jan 2017)",
     "Diagonal crossings and scramble phases in Los Angeles follow the 2017 exclusive pedestrian phase policy.",
     [("Exclusive Pedestrian Phase", f"{B}/ladot-exclusive-ped-phase-2017/")]),
    ({"roaddiet"}, "LADOT Lane Reconfiguration guidance (Apr 2023)",
     "Road diets and lane reconfigurations in Los Angeles follow the 2023 Complete Streets Lane Reconfiguration guidance.",
     [("Lane Reconfiguration (2023)", f"{B}/ladot-lane-reconfiguration-2023/")]),
    ({"curbramp", "dws", "ada"}, "PROWAG and current curb ramp details",
     "PROWAG (2023) is enforceable at transit stops through U.S. DOT and is the current federal guidance elsewhere. Detectable warnings must be at least 24 in. deep and contrast visually. Caltrans 2026 Standard Plans A88A and A88B carry the current State curb ramp details.",
     [("PROWAG digest", f"{B}/prowag-2023/"), ("Caltrans 2026 A88A", f"{BASE}/details/caltrans/caltrans-std-plans-2026-a88a/"), ("Curb ramp guide", f"{BASE}/ada/curb-ramps/")]),
    ({"aps", "pushbutton"}, "Accessible pedestrian signals and pushbutton signs",
     "PROWAG R209 requires accessible pedestrian signals wherever pedestrian signals are provided. CA MUTCD 2026 deleted the California R62 pushbutton signs: use the current pushbutton signs in CA MUTCD 2026.",
     [("PROWAG digest", f"{B}/prowag-2023/"), ("Deleted CA signs", f"{B}/standards-status/#deleted-california-signs")]),
    ({"disparking"}, "Accessible parking: CBC 2025 and PROWAG",
     "Off-street spaces follow the 2025 CBC Chapter 11B (effective January 1, 2026). On-street spaces follow LADOT Accessible Parking Zones in Los Angeles, with PROWAG R214 as federal guidance.",
     [("CBC 11B digest", f"{B}/ca-accessible-parking-2026/"), ("LADOT Accessible Parking Zones", f"{B}/ladot-accessible-parking-2017/"), ("Caltrans 2026 A90B on-street", f"{BASE}/details/caltrans/caltrans-std-plans-2026-a90b/")]),
]
GL = {g["id"]: [g["term"].lower()] + [a.lower() for a in g.get("aka", [])] for g in json.load(open("public/data/glossary.json"))}


def strong(x, cid):
    """Concept named in the drawing's own title, keywords or summary (not only in sheet notes)."""
    t = " ".join([x.get("title", ""), x.get("kw", ""), x.get("sum", "")]).lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in GL.get(cid, []))


STRONG_TYPES = {"Standard drawing", "Figure page", "Figure", "Marking", "Line type"}
for x in det:
    if x["type"] not in STRONG_TYPES or x["src"].endswith("bulletins"):
        continue
    cs = {c for c in x.get("c", []) if strong(x, c)}
    for ids, title, text, links in RULES:
        if cs & ids and not any(l[1].split("#")[0] == x["url"].split("#")[0] for l in links):
            add(x["url"], "info", title, text, links, x["num"])

# ---------------------------------------------------------------- order and cap
SEV = {"warn": 0, "info": 1}
out = {}
for p, cs in checks.items():
    cs.sort(key=lambda c: SEV[c["sev"]])
    out[p] = cs[:6]
json.dump(out, open("public/data/checks.json", "w"), separators=(",", ":"))

# ---------------------------------------------------------------- standards status page
by_letter = collections.defaultdict(list)
for k, v in sorted(deleted["codes"].items()):
    by_letter[k[0]].append(f"{k} {v}")
in_lib = [c for c in signs if re.sub(r"\s+", "", c.upper()) in DEL]
rows = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in [
    ("California MUTCD", "2026 Edition, effective January 18, 2026", "Governs on all California streets. Caltrans has a revision in process through the CTCDC to adopt federal Revision 1."),
    ("Federal MUTCD", "11th Edition Revision 1, effective March 5, 2026", "States have two years to adopt. Reference only in California until the CA MUTCD revision takes effect."),
    ("Caltrans Standard Plans", "2026 edition (sheets dated September 18, 2026; required for projects submitted on or after October 19, 2026)", "On this site: A20A to A24L, A88A, A88B, A90A and A90B. Supersedes the 2018 sheets also shown here. The A20A marker details for Types G and H were revised."),
    ("Caltrans Highway Design Manual", "Updated August 8, 2025", "Lane width design values are in DIB 94."),
    ("California Building Code, Chapter 11B", "2025 edition, effective January 1, 2026", "Governs off-street accessible parking signs and markings."),
    ("PROWAG (36 CFR 1190)", "Final, August 8, 2023", "Enforceable for transit stops in the public right-of-way (U.S. DOT, effective January 17, 2025). Not adopted by DOJ; best available guidance elsewhere."),
    ("LADOT MPP 531", "February 2023", "Controls over older LADOT reprints of the same drawing numbers."),
])
status = f'''---
title: Standards Status
description: Which edition of each standard governs as of {CHECKED}, what supersedes what, and the California signs deleted in CA MUTCD 2026.
---

Checked {CHECKED}. Every page on this site shows a **Checks** panel (right edge) that applies these rules to the drawing or chapter you are viewing.

## Current editions

| Standard | Current edition | What it means here |
|---|---|---|
{rows}

## What the checks panel flags

- **Newer copy:** a LADOT drawing number published in two documents with different dates. The newer date is flagged as the controlling copy.
- **Superseded edition:** Caltrans 2018 Standard Plans, and federal MUTCD pages where the CA MUTCD governs.
- **Deleted signs:** pages that cite a California sign Caltrans lists as deleted in CA MUTCD 2026.
- **Guidance in effect:** bulletins and memos that bear on the drawing, such as DIB 94 for lane widths, LADOT bikeway marking guidance, the LPI policy and PROWAG.

## Deleted California signs

Caltrans published the list of California signs deleted in CA MUTCD 2026 on {deleted["date"]} ([official list]({deleted["source"]})). {len(deleted["codes"])} codes are listed. Signs in this site's sign library that are on the list: {", ".join(f"[{c}]({signs[c]['url']})" for c in in_lib) or "none"}.

<details><summary>Show all {len(deleted["codes"])} deleted codes</summary>

{chr(10).join(f"- **{L}:** " + "; ".join(v) for L, v in sorted(by_letter.items()))}

</details>

Sources: Caltrans CA MUTCD 2026 and deleted sign list; FHWA MUTCD 11th Edition Revision 1; Caltrans Standard Plans revision digest; U.S. Access Board and U.S. DOT final rules; California Building Standards Commission.
'''
open("src/content/docs/bulletins/standards-status.md", "w").write(status)
n = collections.Counter(c["sev"] for cs in out.values() for c in cs)
print("checks:", len(out), "pages,", dict(n))
