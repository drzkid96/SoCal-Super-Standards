"""Check that printed-address repairs retain their target and source page after rendering."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from lxml import html

from printed_citations import DIRECTORIES


def check(root):
    rules={}
    for name in DIRECTORIES:
        for row in json.loads(Path(f'data/reference/printed-urls-{name}.json').read_text()):
            ref=sha256(row['match'].encode()).hexdigest()[:12]
            rules[ref]=row
    occurrences=Counter()
    copies=Counter()
    for path in root.rglob('*.html'):
        body=path.read_text()
        if 'data-printed-ref=' not in body:continue
        for node in html.fromstring(body).xpath('//*[@data-printed-ref]'):
            ref=node.attrib['data-printed-ref']
            row=rules[ref];occurrences[ref]+=1
            if row['url']:
                assert node.tag=='a' and node.get('href')==row['url'],(path,ref,node.get('href'))
                copies['direct']+=1
            else:
                assert node.tag=='code' and 'printed-address' in node.get('class',''),(path,ref)
                if not row.get('source'):continue
                link=node.getnext()
                assert link is not None and link.tag=='a' and link.get('href'),(path,ref)
                base=row['source'].split('#')[0]
                assert link.get('href').split('#')[0]==base,(path,ref,link.get('href'))
                if '#page=' in row['source']:
                    assert re.search(r'#page=\d+$',link.get('href')),(path,ref,link.get('href'))
                copies['source page']+=1
    missing=set(rules)-set(occurrences)
    if missing:raise ValueError('Missing published citations: '+', '.join(rules[k]['match'] for k in sorted(missing)))
    print(f'{len(rules)} reviewed citation spellings · {sum(occurrences.values())} rendered occurrences · {dict(copies)}')


if __name__=='__main__':
    check(Path(sys.argv[1]) if len(sys.argv)>1 else Path('dist'))
