"""Merge cleaned OCR (plain-language titles, summaries, keywords, unjumbled notes) into the site.

Input: data/clean/*.json (lists of units, see /home/claude/work/clean/SPEC.md)
Writes: data/clean.json (id -> unit), adds "clean" fields to data/docs/*.json pages,
and rewrites the page text blocks in the generated document chapter pages.
Idempotent: safe to run after every extract_doc run.
"""
import glob, html, json, os, re

BASE = "/SoCal-Super-Standards"
esc = html.escape
U = {}
for f in sorted(glob.glob("data/clean/*.json")):
    for u in json.load(open(f)):
        U[u["id"]] = u
json.dump(U, open("data/clean.json", "w"), indent=0)
# pass 2: full sheet descriptions and fully interpreted notes for scanned sheets, read from the images
P2 = {}
for f in sorted(glob.glob("data/clean2/*.json")):
    for r in json.load(open(f)):
        P2[(r["id"].split("|")[0], int(r["page"]))] = r

def notes_html(t):
    out = []
    for line in [x.strip() for x in (t or "").split("\n") if x.strip()]:
        if len(line) < 70 and (line.isupper() or line.endswith(":")) and not re.match(r"^\d+\.", line):
            out.append(f"<h5>{esc(line)}</h5>")
        else:
            out.append(f"<p>{esc(line)}</p>")
    return "\n".join(out)

OV = json.load(open("data/dwg_overrides.json")) if os.path.exists("data/dwg_overrides.json") else {}
n_pages = n_md = 0
for f in sorted(glob.glob("data/docs/*__*.json")):
    slug = os.path.basename(f)[:-5]
    d = json.load(open(f))
    changed_md = {}
    FG = {}
    for p in d.get("pages", []):
        o = p.get("drawings_orig", p.get("drawings") or [])
        fin = OV.get(slug, {}).get(str(p["page"])) or (o[0] if o else None)
        fin = None if fin == "-" else fin
        if fin:
            FG.setdefault(fin, []).append(p["page"])
    for p in d.get("pages", []):
        if "drawings_orig" not in p:
            p["drawings_orig"] = list(p.get("drawings") or [])
        nd = OV.get(slug, {}).get(str(p["page"]))
        if nd == "-":
            p["drawings"] = []
            nd = None
        elif nd:
            p["drawings"] = [nd]
        u = None
        if p["drawings_orig"] and f"{slug}|{p['drawings_orig'][0]}" in U:
            u = U[f"{slug}|{p['drawings_orig'][0]}"]
        elif f"{slug}|p{p['page']}" in U:
            u = U[f"{slug}|p{p['page']}"]
        if not u:
            continue
        sh = next((s for s in u.get("sheets", []) if s.get("page") == p["page"]), None)
        p["clean"] = {"title": u.get("title", ""), "summary": u.get("summary", ""), "keywords": u.get("keywords", []),
                      "notes": (sh or {}).get("notes", "")}
        r2 = P2.get((slug, p["page"]))
        if r2:
            p["clean"]["notes"] = r2.get("notes") or p["clean"]["notes"]
            p["clean"]["description"] = r2.get("description", "")
            grp = FG.get(p["drawings"][0], []) if p.get("drawings") else []
            if len(u.get("sheets", [])) <= 1 or nd or sorted(grp) != sorted(x.get("page") for x in u.get("sheets", [])):
                p["clean"]["title"] = r2.get("title") or p["clean"]["title"]
                p["clean"]["summary"] = r2.get("summary") or p["clean"]["summary"]
        if p.get("drawings") and f'{slug}|{p["drawings"][0]}' in OV.get("_titles", {}):
            p["clean"]["title"] = OV["_titles"][f'{slug}|{p["drawings"][0]}']
        n_pages += 1
        # rewrite the page block in the chapter page
        m = re.match(rf"{BASE}/(.+?)/#p\d+$", p["url"])
        if not m:
            continue
        mdp = f"src/content/docs/{m.group(1)}.md"
        if not os.path.exists(mdp):
            continue
        s = changed_md.get(mdp) or open(mdp).read()
        a = s.find(f'<span id="p{p["page"]}" class="anchor">')
        if a < 0:
            continue
        b = s.find('<span id="p', a + 10)
        b = len(s) if b < 0 else b
        blk = s[a:b]
        c = p["clean"]
        new = (f'<div class="pclean"><p class="psum"><b>{esc(c["title"])}.</b> {esc(c["summary"])}</p>'
               + (f'<details class="sdesc" open><summary>What this sheet shows</summary>{notes_html(c["description"])}</details>' if c.get("description") else "")
               + (f'<details class="ocr" open><summary>Notes on this sheet (cleaned from the {"scan" if p.get("ocr") else "PDF text"})</summary>{notes_html(c["notes"])}</details>' if c["notes"] else "")
               + "</div>\n"
               + f'<div class="kw">Keywords: {esc(", ".join(c["keywords"]))}</div>\n')
        blk2 = re.sub(r'<div class="pclean">.*?</div>\n<div class="kw">.*?</div>\n', lambda _: new, blk, flags=re.S)
        if blk2 == blk:
            blk2 = re.sub(r'(<details class="ocr">.*?</details>\n)?<div class="kw">.*?</div>\n', lambda _: new, blk, count=1, flags=re.S)
        if c["notes"]:
            blk2 = re.sub(r'<div class="dtext">.*?</div>\n', '', blk2, flags=re.S)
        # generic page heading -> cleaned title
        blk2 = re.sub(r"(### Page \d+)( - [^\n]*)?\n", lambda mm: f"{mm.group(1)} - {esc(c['title'])}\n", blk2, count=1)
        s = s[:a] + blk2 + s[b:]
        changed_md[mdp] = s
    # fill blank drawing titles in the document overview table
    ov = None
    for p in d.get("pages", []):
        m = re.match(rf"{BASE}/(.+?)/[^/]+/#p\d+$", p["url"])
        if m:
            ov = f"src/content/docs/{m.group(1)}/index.md"
            break
    if ov and os.path.exists(ov):
        t = changed_md.get(ov) or open(ov).read()
        for uid, u in U.items():
            if uid.startswith(slug + "|") and not uid.split("|")[1].startswith("p"):
                k = uid.split("|")[1]
                t = t.replace(f"<td><strong>{esc(k)}</strong></td><td></td>", f"<td><strong>{esc(k)}</strong></td><td>{esc(u['title'])}</td>")
        changed_md[ov] = t
    for k, v in changed_md.items():
        open(k, "w").write(v)
        n_md += 1
    json.dump(d, open(f, "w"))
print("clean units", len(U), "pages", n_pages, "chapter files", n_md)
