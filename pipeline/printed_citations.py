"""Restore reviewed citations broken across text runs or paragraphs in source guides."""
from bisect import bisect_right
from collections import Counter, defaultdict
from hashlib import sha256
from html import escape, unescape
import json
from pathlib import Path
from urllib.parse import urlsplit
import re

DIRECTORIES = {
    'guides': ('ada','ca-mutcd','mutcd','ladot','fhwa'),
    'mobility': ('ladot/mobility-plan',),
    'regional': ('regions',),
}
# Adjacent source paragraphs sometimes contain the two halves of one address.
GAP = r'(?:\s|&nbsp;|</p>\s*<p>)+'
PROTECTED = r'<a\b[^>]*>.*?</a>|<code\b[^>]*>.*?</code>|<[^>]+>'
PAGE = re.compile(r'\bid="p-?(\d+)"')
PREVIOUS = re.compile(r'<(?P<tag>a|code)\b[^>]*data-printed-ref="(?P<ref>[a-f0-9]+)"[^>]*>.*?</(?P=tag)>'
                      r'(?: \(<a data-source-citation href="[^"]+">[^<]*</a>\))?', re.S)


def spelling(value):
    words = value.split()
    optional_scheme = r'(?:https?://)?' if value.startswith('www.') else ''
    return optional_scheme+GAP.join('(?:&amp;|&)'.join(re.escape(piece) for piece in word.split('&')) for word in words)


DESCRIPTION = re.compile(r'<p class="detail-description">(.*?)</p>', re.S)


def plain(value):
    return ' '.join(unescape(re.sub('<[^>]+>', '', value)).split())


def repair(root, details=()):
    totals = Counter()
    by_page = defaultdict(lambda: defaultdict(list))
    for record in details:
        route=urlsplit(record['url']).path.removeprefix('/SoCal-Super-Standards/').strip('/')
        by_page[route][' '.join(record['description'].split())].append(record)
    for name, directories in DIRECTORIES.items():
        file = Path('data/reference')/f'printed-urls-{name}.json'
        rules = sorted(json.loads(file.read_text()), key=lambda r:-len(r['match']))
        if len({r['match'] for r in rules})!=len(rules):raise ValueError('Duplicate printed citation in '+file.name)
        # Match in text only. Existing source provenance, nested links, HTML attributes,
        # and previously repaired addresses retain their original markup.
        markers={sha256(row['match'].encode()).hexdigest()[:12]:row for row in rules}
        choices = [f'(?P<c{i}>{spelling(row["match"])})' for i,row in enumerate(rules)]
        pattern = re.compile(PROTECTED+'|'+r'(?<![\w/=])(?:'+'|'.join(choices)+r')(?=$|[\s<>.,;:?!\)\]”"])', re.S)
        for directory in directories:
            for path in (root/directory).rglob('*.md'):
                if name=='guides' and (root/'ladot/mobility-plan') in path.parents:continue
                before=path.read_text()
                text=PREVIOUS.sub(lambda m:escape(markers[m['ref']]['match'],quote=False) if m['ref'] in markers else m[0],before)
                if not any(rule['match'].split()[0].partition('&')[0] in text for rule in rules):continue
                positions=[(m.start(),m[1]) for m in PAGE.finditer(text)]
                def restore(match):
                    if not match.lastgroup:return match[0]
                    row=rules[int(match.lastgroup[1:])]
                    label=row.get('label') or ''.join(row['match'].split()).replace('\u00ad','')
                    url=row.get('url')
                    marker=sha256(row['match'].encode()).hexdigest()[:12]
                    totals[name,row['match']]+=1
                    if url:
                        return f'<a data-source-citation data-printed-ref="{marker}" href="{escape(url,quote=True)}">{escape(label)}</a>'
                    text=f'<code class="printed-address" data-printed-ref="{marker}">{escape(label)}</code>'
                    source=row.get('source')
                    if not source:return text
                    # Use the local publication's actual PDF page even when this
                    # reference appears more than once in its bibliography.
                    i=bisect_right(positions,(match.start(),'z'))-1
                    if i>=0 and ('#page=' in source or '{page}' in source):
                        number=positions[i][1]
                        source=re.sub(r'(#page=)(?:\d+|\{page\})',lambda m:m[1]+number,source)
                    page=re.search(r'#page=(\d+)',source)
                    title='Source p. '+page[1] if page else 'Source publication'
                    return text+f' (<a data-source-citation href="{escape(source,quote=True)}">{title}</a>)'
                after=pattern.sub(restore,text)
                route=path.relative_to(root).with_suffix('').as_posix().removesuffix('/index')
                if route in by_page and text!=after:
                    # Publication repairs can change the printed label inside a description.
                    # Update only records with that exact pre-repair text on this same page.
                    prior=DESCRIPTION.findall(text)
                    current=DESCRIPTION.findall(after)
                    for raw, restored in zip(prior,current,strict=True):
                        if raw!=restored:
                            for record in by_page[route].get(plain(raw),()):
                                record['description']=plain(restored)
                if before!=after:path.write_text(after)
        unused=[r['match'] for r in rules if not totals[name,r['match']]]
        if unused:raise ValueError('Printed citation absent from '+name+' source: '+repr(unused))
    return totals
