"""Keep sign and drawing detail pages focused on the depicted item and its downloads."""
from html import escape, unescape
import re


RELATED_SIGN = re.compile(r'<!-- rel-sign -->.*?<!-- /rel-sign -->', re.S)
DRAWING_FOOTER = re.compile(r'<section class="xidx-wrap"[^>]*>.*?</section>', re.S)
LADOT_MENTIONS = re.compile(r'<!-- ladot -->\s*## In LADOT documents\b.*?(?=\n<!--|\n## |\n<h3\b|\Z)', re.S)


def simplify_sign(text):
    # The old "mentions" table repeats every PDF page citing the same sign,
    # including index pages. The governing sections remain the reference links.
    text = LADOT_MENTIONS.sub('', text)
    text = RELATED_SIGN.sub('', text)
    def facts(m):
        rows = []
        for label, value in re.findall(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>', m[1], re.S):
            if label in ('Legend', 'Colors') and value not in ('See layout', '—', ''):
                rows.append(f'<dt>{label}</dt><dd>{value}</dd>')
            if label == 'Source':
                links = re.findall(r'<a href="(https?://[^"]+)"', value)
                if links and links[0] not in text[start + m.end():]:
                    rows.append('<dt>Layout</dt><dd><a href="' + escape(unescape(links[0]), quote=True) + '">Sign specification</a></dd>')
        return '<dl>' + ''.join(rows) + '</dl>' if rows else ''
    info = re.search(r'<div class="sdetail-info">', text)
    if info:
        start = info.end()
        text = text[:start] + re.sub(r'<dl>(.*?)</dl>', facts, text[start:], count=1, flags=re.S)
    # Maintain existing section anchors for bookmarks while folding lengthy
    # lists of manual mentions. The nearest section opens on an incoming link.
    text = re.sub(r'## Governing sections\s*\n+(<ul class="ments">.*?</ul>)',
                  r'<details class="sign-guidance" id="governing-sections"><summary>Governing MUTCD sections</summary>\1</details>',
                  text, flags=re.S)
    return text


def build(root):
    for page in (root/'signs').glob('*.md'):
        if page.name == 'index.md':
            continue
        original = page.read_text()
        text = simplify_sign(original)
        if text != original:
            page.write_text(text)
    for page in (root/'details').rglob('*.md'):
        original = page.read_text()
        if 'class="dwg-head"' not in original:
            continue
        text = DRAWING_FOOTER.sub('', original)
        text = re.sub(r'<h2>Signs on this drawing</h2>(<div class="tsigns">.*?</div>)',
                      r'<details class="drawing-signs" id="signs-on-this-drawing"><summary>Signs on this drawing</summary>\1</details>',
                      text, flags=re.S)
        if text != original:
            page.write_text(text)
