"""Review outgoing article links. Distinguish confirmed missing resources from hosts limiting access."""
import argparse
import concurrent.futures
import json
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
destinations=defaultdict(set)
for page in Path('dist').rglob('*.html'):
    body=page.read_text().partition('class="sl-markdown-content"')[2]
    for raw in re.findall(r'href="(https?://[^"]+)"',body):
        url=urldefrag(unescape(raw))[0]
        host=urlsplit(url).hostname or ''
        if host.endswith(('.gov','.org','.edu','.com','.us','.net')) and host!='drzkid96.github.io':
            destinations[url].add(str(page.relative_to('dist')))
if not destinations:raise SystemExit('Build the site before auditing links.')


def probe(entry):
    url,pages=entry
    try:
        for method in ('HEAD','GET'):
            try:
                req=urllib.request.Request(url,method=method,headers={'User-Agent':'SoCal-Standards-Reference-Check/1.0'})
                with urllib.request.urlopen(req,timeout=8) as resp:
                    status=resp.status; final=resp.url;break
            except urllib.error.HTTPError as e:
                status=e.code;final=e.url
                if method=='HEAD' and status in (400,403,404,405,410,501):continue
                break
        verdict='reachable' if status<400 else 'missing' if status in (404,410) else 'unverified'
    except (OSError,ValueError) as e:
        status=str(e);final=url;verdict='unverified'
    return dict(url=url,status=status,result=verdict,final=final,pages=sorted(pages))


with concurrent.futures.ThreadPoolExecutor(5) as pool:
    rows=list(pool.map(probe,sorted(destinations.items())))
args.output.write_text(json.dumps(rows,indent=2)+'\n')
print('External destinations:',dict(Counter(r['result'] for r in rows)))
