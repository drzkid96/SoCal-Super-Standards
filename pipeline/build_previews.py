"""Hover previews for every internal link.

For each page on the site, collect the images it shows (sign and marking hover images, drawing thumbnails,
figures, line types) and write public/data/previews.json: path -> {t: title, i: [images]}.
Pages about signs or markings get a set of up to 9 images; other pages up to 4. Anchored targets
(figures, line types, markings) get their own single image. Runs last in build_all.sh.
"""
import glob, json, os, re

BASE = "/SoCal-Super-Standards"
ROOT = "src/content/docs"
IMG_RE = re.compile(r'(?:data-svg|src)="(' + re.escape(BASE) + r'/[^"]+\.(?:svg|webp|png|jpe?g))"|!\[[^\]]*\]\((' + re.escape(BASE) + r'/[^)\s]+\.(?:svg|webp|png|jpe?g))\)', re.I)
SETPAGE = re.compile(r"^(signs|markings)/|curb-paint|line-types|keywords", re.I)

def rel_img(u):
    p = u.replace(BASE, "", 1)
    if p.startswith("/figs/") or p.startswith("/redraw/"):   # prefer the light thumbnail when there is one
        for t in ("/thumbs" + p, "/thumbs" + re.sub(r"\.svg$", ".webp", p)):
            if os.path.exists("public" + t):
                p = t
                break
    return p if os.path.exists("public" + p) else None

prev = {}
for f in glob.glob(f"{ROOT}/**/*.md*", recursive=True):
    rel = os.path.relpath(f, ROOT)
    rel = re.sub(r"\.mdx?$", "", rel)
    path = "/" if rel == "index" else "/" + re.sub(r"(^|/)index$", "", rel).strip("/") + "/"
    s = open(f).read()
    m = re.search(r'^title:\s*"?(.*?)"?\s*$', s, re.M)
    title = m.group(1) if m else rel
    cap = 9 if SETPAGE.search(rel) else 4
    imgs = []
    for a, b in IMG_RE.findall(s):
        p = rel_img(a or b)
        if p and p not in imgs:
            imgs.append(p)
        if len(imgs) >= cap:
            break
    prev[path] = {"t": title, "i": imgs, "set": cap == 9}

# items from the indexes: drawings first-sheet thumbnails, anchored figures, line types, markings, signs
det = json.load(open("public/data/details.json"))
for i in det:
    if not i.get("img"):
        continue
    u = i["url"].replace(BASE, "", 1)
    img = rel_img(BASE + i["img"].replace(BASE, "", 1)) if i["img"].startswith(BASE) else None
    if not img:
        continue
    t = f'{i.get("num", "")} {i.get("title", "")}'.strip()
    if "#" in u:
        prev[u] = {"t": t, "i": [img]}
    else:
        e = prev.setdefault(u, {"t": t, "i": []})
        if img not in e["i"]:
            e["i"].insert(0, img)
            e["i"] = e["i"][:9 if e.get("set") else 4]
signs = json.load(open("public/data/signs-index.json"))
for code, r in signs.items():
    u = r["url"].replace(BASE, "", 1)
    img = rel_img(r["svg"]) if r.get("svg", "").startswith(BASE) else None
    if img:
        e = prev.setdefault(u, {"t": f"{code} {r.get('descriptor', '')}".strip(), "i": []})
        if img not in e["i"]:
            e["i"].insert(0, img)
            e["i"] = e["i"][:4]
for k in list(prev):
    prev[k].pop("set", None)
    if not prev[k]["i"]:
        del prev[k]
json.dump(prev, open("public/data/previews.json", "w"), separators=(",", ":"))
print("previews:", len(prev), "targets,", round(os.path.getsize("public/data/previews.json") / 1024), "KB")
