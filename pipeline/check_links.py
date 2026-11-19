"""Internal link checker for the built site (dist/). Reports links to pages or files that do not exist.
Usage: python3 -I pipeline/check_links.py  (after npm run build)"""
import collections, glob, json, os, re, sys
from urllib.parse import unquote

BASE = "/SoCal-Super-Standards"
DIST = "dist"
href = re.compile(r'(?:href|src)="(/SoCal-Super-Standards/[^"#?]*)')


def exists(u):
    p = unquote(u[len(BASE):]).lstrip("/")
    f = os.path.join(DIST, p)
    return os.path.isfile(f) or os.path.isfile(os.path.join(f, "index.html")) or os.path.isfile(f + ".html")


bad = collections.defaultdict(set)
pages = glob.glob(f"{DIST}/**/*.html", recursive=True)
for f in pages:
    for u in set(href.findall(open(f, encoding="utf8", errors="ignore").read())):
        if not exists(u):
            bad[u].add(f[len(DIST):])
# links inside data files used by the scripts
for jf in ["checks.json", "details.json", "previews.json"]:
    t = open(f"public/data/{jf}").read()
    for u in set(re.findall(r'"(/SoCal-Super-Standards/[^"#?]*)', t)):
        if not exists(u):
            bad[u].add("data/" + jf)
print(f"{len(pages)} pages checked, {len(bad)} broken internal targets")
for u, fs in sorted(bad.items())[:60]:
    print(f"  {u}  <- {', '.join(sorted(fs)[:3])}{' ...' if len(fs) > 3 else ''}")
json.dump({u: sorted(fs) for u, fs in bad.items()}, open("/tmp/broken_links.json", "w"), indent=1)
sys.exit(0)
