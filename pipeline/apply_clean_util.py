import html, re
esc = html.escape

def notes_html(t):
    out = []
    for line in [x.strip() for x in (t or "").split("\n") if x.strip()]:
        if len(line) < 70 and (line.isupper() or line.endswith(":")) and not re.match(r"^\d+\.", line):
            out.append(f"<h5>{esc(line)}</h5>")
        else:
            out.append(f"<p>{esc(line)}</p>")
    return "\n".join(out)

