"""Rebuild manual tables as searchable HTML under each table image (CA MUTCD 2026 and federal MUTCD)."""
import glob, html, json, re, sys
import pymupdf
CA, FED = sys.argv[1], sys.argv[2]
idx = json.load(open("public/data/signs-index.json"))
RX = re.compile(r"(?<![A-Za-z0-9-])((?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d{1,3}[A-Za-z]?(?:-\d{1,3}[A-Za-z]{0,4})?(?:\(CA\))?)(?![A-Za-z0-9])")
esc = lambda t: html.escape(str(t), quote=False)
def cell(t):
    t = esc(re.sub(r"\s+", " ", (t or "").replace("\n", " ")).strip())
    return RX.sub(lambda m: f'<a class="sref" href="{idx[m.group(1)]["url"]}" data-svg="{idx[m.group(1)]["svg"]}">{m.group(1)}</a>' if m.group(1) in idx else m.group(0), t)
stats = {}
sizes = {}
for manual, pdf, sub in (("ca-mutcd", CA, "ca-mutcd"), ("mutcd", FED, "mutcd")):
    doc = pymupdf.open(pdf)
    cache = {}
    n = 0
    for f in sorted(glob.glob(f"src/content/docs/{manual}/*.md")):
        t = open(f).read()
        t = re.sub(r'<details class="mtab-wrap">.*?</details>', "", t, flags=re.S)
        def add(m):
            global n
            fig = m.group(0)
            pm = re.search(rf"/figs/{sub}/p(\d{{4}})\.webp", fig)
            if not pm or 'alt="Table' not in fig:
                return fig
            pno = int(pm.group(1)) - 1
            if pno not in cache:
                try:
                    tabs = doc[pno].find_tables().tables
                except Exception:
                    tabs = []
                parts = []
                W = doc[pno].get_text("words")
                for tb in tabs:
                    rows = []
                    for r in tb.rows:
                        row = []
                        for c in r.cells:
                            if c is None:
                                row.append("")
                                continue
                            R = pymupdf.Rect(c)
                            ws = sorted([w for w in W if R.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))], key=lambda w: (round(w[1] / 2), w[0]))
                            row.append(" ".join(w[4] for w in ws))
                        if not any(x.strip() for x in row):
                            continue
                        filled = [i for i, x in enumerate(row) if x.strip()]
                        if rows and filled == [0] and len(row) > 2:
                            rows[-1][0] = (rows[-1][0] + " " + row[0]).strip()
                            continue
                        rows.append(row)
                    if len(rows) < 2 or max(len(r) for r in rows) < 2:
                        continue
                    if manual == "ca-mutcd" and any("Designation" in (c or "") for c in rows[0]):
                        H = rows[0][:]
                        if len(rows) > 1 and not rows[1][0].strip() and not any(re.search(r"\d+ ?x ?\d+", c) for c in rows[1]):
                            H = [(a + " " + b).strip() if b.strip() else a for a, b in zip(H, rows[1] + [""] * len(H))]
                        di = next(i for i, c in enumerate(rows[0]) if "Designation" in c)
                        tid = re.search(r'alt="(Table [^."]+)', fig).group(1)
                        for r in rows[1:]:
                            des = r[di].replace(" ", "")
                            if not re.match(r"^(?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d", des):
                                continue
                            base = re.match(r"^((?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d{1,3}[A-Za-z]?)-?", des)
                            codes = []
                            for k, part in enumerate(re.split(r",", des)):
                                if k == 0:
                                    codes.append(part)
                                else:
                                    pref = re.match(r"^(.*-)", codes[0])
                                    codes.append((pref.group(1) if pref and not re.match(r"^[A-Z]", part) else "") + part)
                            for c in codes:
                                if not re.search(r"x", " ".join(r)):
                                    continue
                                sizes.setdefault(c, {"table": tid, "page": pno + 1, "name": r[0], "cols": {H[i]: r[i] for i in range(len(r)) if i not in (0, di) and H[i] and r[i].strip() and "Section" not in H[i] and not re.search(r"\d+ ?x ?\d+|^\d[A-Z]\.\d", H[i])}})
                    hdr = "".join(f"<th>{cell(c)}</th>" for c in rows[0])
                    body = "".join("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                    parts.append(f'<div class="mtab-scroll"><table class="mtab"><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table></div>')
                cache[pno] = "".join(parts)
            if not cache[pno]:
                return fig
            n += 1
            return fig + f'<details class="mtab-wrap"><summary>Table as text (page {pno + 1}, searchable; check against the image)</summary>{cache[pno]}</details>'
        t2 = re.sub(r'<figure class="mfig">.*?</figure>', add, t, flags=re.S)
        open(f, "w").write(t2)
    stats[manual] = n
json.dump(sizes, open("data/signs/ca_sizes.json", "w"), indent=0)
print("tables rebuilt", stats, "sign sizes", len(sizes))
