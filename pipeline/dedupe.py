"""Remove duplicates from the site's indexes.

Runs after build_details. Three kinds of duplicate:
1. Manual figures and tables listed more than once: entries that point at a list-of-figures page are dropped
   (Figure 2C-13 should live in chapter 2C), and multi-sheet figures collapse to one entry with a sheet count.
2. The same page repeated inside one document (e.g. Parking Standards p83 = p135): identical image and text.
3. The same drawing published in two documents (e.g. S-100.0 in MPP 531 and MPP 521, or an MPP sheet
   reproduced in the Supplemental Street Design Guide): one canonical entry stays, the others become
   "also published in" notes, and duplicate drawing pages turn into short pointer pages.
Writes data/dups.json and rewrites public/data/details.json and data/docs/drawing_pages.json.
"""
import difflib, glob, json, os, re
from collections import defaultdict
from PIL import Image

BASE = "/SoCal-Super-Standards"
PRI = ["MPP 531", "MPP 521", "Red Book", "Burbank Std. Plans", "Pasadena Std. Plans", "Caltrans Std. Plans 2018"]
det = json.load(open("public/data/details.json"))

def dhash(url):
    try:
        im = Image.open("public" + url.replace(BASE, "", 1)).convert("L").resize((17, 16))
    except Exception:
        return None
    px = im.tobytes()
    return [px[r * 17 + c] > px[r * 17 + c + 1] for r in range(16) for c in range(16)]
ham = lambda a, b: sum(x != y for x, y in zip(a, b))
norm = lambda t: re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

# text per item (page text or concatenated sheet text)
text = defaultdict(str)
DWG_URL = {(i["src"], i["num"]): i["url"] for i in det if i["type"] == "Standard drawing"}
for f in glob.glob("data/docs/*__*.json"):
    d = json.load(open(f))
    for p in d.get("pages", []):
        if p.get("image") and p.get("drawings"):
            u = DWG_URL.get((d.get("short"), p["drawings"][0]))
        else:
            u = p["url"]
        if u:
            text[u] += " " + (p.get("text") or "")

def same_text(a, b):
    ta, tb = norm(text[a["url"]])[:3000], norm(text[b["url"]])[:3000]
    if len(ta) < 600 or len(tb) < 600:
        da, db = re.sub(r"\d+", "", ta).split(), re.sub(r"\d+", "", tb).split()
        return len(ta) >= 80 and da == db
    if len(ta) < 80 or len(tb) < 80:
        return norm(a["title"]) == norm(b["title"]) and len(ta) < 80 and len(tb) < 80 and ta == tb
    return difflib.SequenceMatcher(None, ta, tb, autojunk=False).quick_ratio() > 0.9 and \
        difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio() > 0.85

dups = {}          # dup url -> canonical url
blank = {i["url"] for i in det if i["type"] == "Figure page" and "thispageisintentionallyleftblank" in re.sub(r"[^a-z]", "", text[i["url"]].lower()) and len(norm(text[i["url"]])) < 160}
also = defaultdict(list)

# ---- 2 and 3: pages and drawings
cand = [i for i in det if i["type"] in ("Standard drawing", "Figure page") and i["url"] not in blank]
for i in cand:
    i["_h"] = dhash(i["img"]) if i.get("img") else None
def rank(i):
    return (0 if i["type"] == "Standard drawing" else 1, PRI.index(i["src"]) if i["src"] in PRI else 9,
            int(re.sub(r"\D", "", i["num"]) or 0) if i["type"] == "Figure page" else 0)
for a_ in range(len(cand)):
    a = cand[a_]
    if a["url"] in dups or not a["_h"]:
        continue
    for b in cand[a_ + 1:]:
        if b["url"] in dups or not b["_h"] or b["url"] == a["url"]:
            continue
        if ham(a["_h"], b["_h"]) <= 8 and same_text(a, b):
            keep, drop = sorted([a, b], key=rank)
            dups[drop["url"]] = keep["url"]
            also[keep["url"]].append({"src": drop["src"], "num": drop["num"], "url": drop["url"], "type": drop["type"]})
            if drop is a:
                break

# resolve chains (a -> b -> c becomes a -> c)
for k in list(dups):
    v = dups[k]
    while v in dups:
        v = dups[v]
    dups[k] = v
also = defaultdict(list)
for k, v in dups.items():
    x = next(i for i in cand if i["url"] == k)
    also[v].append({"src": x["src"], "num": x["num"], "url": x["url"], "type": x["type"]})
# ---- 1: manual figures and tables
out, seen = [], {}
for i in det:
    i.pop("_h", None)
    if i["url"] in dups or i["url"] in blank:
        continue
    if i["type"] in ("Figure", "Table") and i.get("sg") == "MUTCD":
        chap = i["num"].split("-")[0].lower() if "-" in i["num"] else ""
        m = re.search(r"/(ca-mutcd|mutcd)/([0-9a-z]+)/", i["url"])
        if chap and m and m.group(2) != chap and not chap.startswith(m.group(2)):
            continue                       # list-of-figures page, not the figure
        key = (i["src"], i["type"], i["num"])
        if key in seen:
            k = seen[key]
            k["parts"] = k.get("parts", 1) + 1
            continue
        seen[key] = i
    out.append(i)
for i in out:
    if i["url"] in also:
        i["also"] = also[i["url"]]

json.dump(out, open("public/data/details.json", "w"))
json.dump({"dups": dups, "blank": sorted(blank)}, open("data/dups.json", "w"), indent=1)

# drawing index used by the hub and topic pages
dp = json.load(open("data/docs/drawing_pages.json"))
dp = [r for r in dp if r[3] not in dups]
json.dump(dp, open("data/docs/drawing_pages.json", "w"))

# duplicate drawing pages -> pointer pages; canonical pages get an "also published in" line
byurl = {i["url"]: i for i in det}
for du, cu in dups.items():
    d_, c_ = byurl.get(du), byurl.get(cu)
    if not d_ or d_["type"] != "Standard drawing":
        continue
    rel = du.replace(BASE + "/", "", 1).rstrip("/")
    mdp = f"src/content/docs/{rel}.md"
    if os.path.exists(mdp):
        s = open(mdp).read()
        fm = s.split("---", 2)
        body = (f'\n<div class="dupnote">This sheet is the same drawing as <a href="{cu}"><b>{c_["num"]}</b> {c_["title"]}</a> '
                f'({c_["src"]}). It is listed once on this site, under that page.</div>\n')
        s = "---" + fm[1] + "---\n" + body
        open(mdp, "w").write(s)
for cu, lst in also.items():
    c_ = byurl.get(cu)
    if not c_ or c_["type"] != "Standard drawing":
        continue
    rel = cu.replace(BASE + "/", "", 1).rstrip("/")
    mdp = f"src/content/docs/{rel}.md"
    if os.path.exists(mdp):
        s = open(mdp).read()
        if 'class="alsopub"' in s:
            s = re.sub(r'<p class="alsopub">.*?</p>\n', "", s)
        line = '<p class="alsopub">Also published as ' + "; ".join(
            (f'{x["src"]} {x["num"]}' if x["type"] == "Standard drawing" else f'{x["src"]} page {x["num"].lstrip("p")}') for x in lst) + \
            '. Those copies are not listed separately.</p>\n'
        s = s.replace("\n## Sheets", "\n" + line + "\n## Sheets", 1)
        open(mdp, "w").write(s)

n_fig = len(det) - len(out) - len(dups) - len(blank)
print("blank pages dropped:", len(blank), "| duplicates removed:", len(dups), "pages/drawings,", n_fig, "repeated figure/table entries | items now", len(out))
for du, cu in list(dups.items())[:80]:
    print("  ", byurl[du]["src"], byurl[du]["num"], "->", byurl[cu]["src"], byurl[cu]["num"])
