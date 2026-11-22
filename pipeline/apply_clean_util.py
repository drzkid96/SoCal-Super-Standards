import html, re
esc = html.escape

def clean_notes(t):
    """Return meaningful engineering notes text, or '' if empty/AI filler."""
    t = (t or "").strip()
    if not t:
        return ""
    low = re.sub(r"\s+", " ", t.lower()).strip()
    if re.search(r"^(?:no (?:other |numbered )?notes\b|text on the page:|footer text:|exhibit\s+\d+\.?$)", low):
        return ""
    if "the notes themselves are not on this sheet" in low:
        return ""
    if "thispageisintentionallyleftblank" in re.sub(r"[^a-z]", "", low):
        return ""
    lines = []
    for line in [x.strip() for x in t.split("\n") if x.strip()]:
        ll = line.lower()
        if re.fullmatch(r"no (?:other |numbered )?notes(?: (?:are printed |appear )?on this (?:sheet|page))?\.?", ll):
            continue
        if re.match(r"^(?:photo credit|watermark text|footer text|drawing labels|labels on this sheet|labels shown|other labels|callouts? on the sheet):", ll):
            continue
        lines.append(line)
    joined = "\n".join(lines).strip()
    if not joined:
        return ""
    if len(joined) < 40 and re.fullmatch(r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}(?:,\s*updated)?\.?", joined, re.I):
        return ""
    return joined

def notes_html(t):
    out = []
    for line in [x.strip() for x in (t or "").split("\n") if x.strip()]:
        if len(line) < 70 and (line.isupper() or line.endswith(":")) and not re.match(r"^\d+\.", line):
            out.append(f"<h5>{esc(line)}</h5>")
        else:
            out.append(f"<p>{esc(line)}</p>")
    return "\n".join(out)


