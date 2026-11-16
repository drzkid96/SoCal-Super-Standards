"""Link every sign code (federal and (CA)) in document readers and drawing pages to the Sign Library with hover previews."""
import glob, json, re
idx = json.load(open("public/data/signs-index.json"))
RX = re.compile(r"(?<![A-Za-z0-9-])((?:OM|SR|SW|SG|SC|CW|[RWSDMGEI])\d{1,3}[A-Za-z]?(?:-\d{1,3}[A-Za-z]{0,4})?(?:\(CA\))?)(?![A-Za-z0-9])")
dirs = ["ladot", "burbank", "pasadena", "details", "fhwa", "ada", "topics"]
n = 0
for d in dirs:
    for f in glob.glob(f"src/content/docs/{d}/**/*.md", recursive=True):
        t = open(f).read()
        fm = t.find("---", 3) + 3
        head, body = t[:fm], t[fm:]
        out, depth, inscript = [], 0, False
        for seg in re.split(r"(<[^>]+>)", body):
            if seg.startswith("<"):
                low = seg.lower()
                if low.startswith("<a "):
                    depth += 1
                elif low.startswith("</a"):
                    depth -= 1
                elif low.startswith("<script"):
                    inscript = True
                elif low.startswith("</script"):
                    inscript = False
                out.append(seg)
                continue
            if depth or inscript:
                out.append(seg)
                continue
            out.append(RX.sub(lambda m: f'<a class="sref" href="{idx[m.group(1)]["url"]}" data-svg="{idx[m.group(1)]["svg"]}">{m.group(1)}</a>' if m.group(1) in idx else m.group(0), seg))
        nb = "".join(out)
        if nb != body:
            open(f, "w").write(head + nb)
            n += 1
print("files linked", n)
