"""Read citations before PDF layout whitespace is flattened into article text."""
from functools import lru_cache
from html import escape
import re
from urllib.parse import urlsplit

WEB = re.compile(r'https?://[^\s<>"\']+', re.I)
WRAP = r'(?:[ \t]*\n[ \t]*)?'
CONTINUATION = re.compile(r'[A-Za-z0-9%][A-Za-z0-9._~%/?#=&+-]*')
DANGLING = re.compile(r'[-_%=&?#]$|%[0-9A-Fa-f]$')


def partial_url(value):
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return True
    return (not host or '.' not in host or host.endswith('.') or
            bool(DANGLING.search(value)) or any(c.isspace() for c in value))


def printed_token(value):
    value = value.rstrip('.,;:!?]')
    while value.endswith(')') and value.count(')') > value.count('('):
        value = value[:-1]
    return value


@lru_cache(maxsize=2048)
def annotation_pattern(url):
    # PDF link rectangles are frequently split at wraps. The stored target carries
    # the complete spelling even where the visible host omits its scheme or www.
    address = re.sub(r'^https?://(?:www\.)?', '', url, flags=re.I)
    chars = WRAP.join(re.escape(c) for c in address.rstrip('/'))
    slash = r'/?' if url.endswith('/') else ''
    return re.compile(r'(?<![\w./-])(?:https?://)?(?:www\.)?' + chars + slash + r'(?![\w/%#?=&-])', re.I)


def transcript(page):
    lines = [line.strip() for line in page.get_text().splitlines()]
    text = '\n'.join(lines)
    spans = []
    targets = {link['uri'].strip() for link in page.get_links()
               if re.match(r'^https?://', link.get('uri', ''), re.I)}
    for url in sorted(targets, key=lambda x: (-len(x), x)):
        if partial_url(url):
            continue
        for match in annotation_pattern(url).finditer(text):
            if not any(start < match.end() and end > match.start() for start,end,_ in spans):
                spans.append((match.start(), match.end(), url))

    for match in WEB.finditer(text):
        if any(start <= match.start() < end for start,end,_ in spans):
            continue
        url = printed_token(match[0])
        # A dot before a wrapped top-level domain is part of the host.
        if match[0].endswith('.') and re.match(r'\n[a-z]{2,12}/', text[match.end():], re.I):
            url = match[0]
        end = match.start() + len(url)
        # Join only at an actual line end, with URL syntax on the following line.
        # A normal heading or sentence starts a new passage in the transcript.
        while end < len(text) and text[end] == '\n':
            following = text[end + 1:].partition('\n')[0]
            token = printed_token(following)
            if not token or not CONTINUATION.fullmatch(token):
                break
            if not re.search(r'[/._%?&#=-]', token) or re.match(r'www\.', token, re.I):
                break
            if url[-1] not in '-/_.%?=&':
                # Alphanumeric line breaks are ambiguous without a PDF annotation.
                url = ''
                break
            url += token
            end += len(token) + 1
        if url and any(target != url and target.startswith(url) for target in targets):
            continue
        if (url and not partial_url(url) and
                not any(start < end and stop > match.start() for start,stop,_ in spans)):
            spans.append((match.start(), end, url))
    out = []
    last = 0
    for start,end,url in sorted(spans):
        out.append(escape(text[last:start], quote=False))
        label = re.sub(r'\s*\n\s*', '', text[start:end])
        out.append(f'<a href="{escape(url, quote=True)}">{escape(label, quote=False)}</a>')
        last = end
    out.append(escape(text[last:], quote=False))
    return ' '.join(''.join(out).split())
