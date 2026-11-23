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
parser.add_argument('--host',action='append',help='Check only this publisher hostname (repeatable).')
parser.add_argument('--site',type=Path,default=Path('dist'),help='Built site directory')
args=parser.parse_args()
destinations=defaultdict(set)
for page in args.site.rglob('*.html'):
    body=page.read_text().partition('class="sl-markdown-content"')[2]
    for raw in re.findall(r'href="(https?://[^"]+)"',body):
        url=urldefrag(unescape(raw))[0]
        host=urlsplit(url).hostname or ''
        if args.host and host not in args.host:continue
        if host.endswith(('.gov','.org','.edu','.com','.us','.net')) and host!='drzkid96.github.io':
            destinations[url].add(str(page.relative_to(args.site)))
if not destinations:raise SystemExit('Build the site before auditing links.')


def probe(entry):
    url,pages=entry
    try:
        for method in ('GET',):
            try:
                req=urllib.request.Request(url,method=method,headers={'User-Agent':'SoCal-Standards-Reference-Check/1.0'})
                with urllib.request.urlopen(req,timeout=8) as resp:
                    status=resp.status;final=resp.url
                    if 'text/html' in resp.headers.get('Content-Type',''):
                        sample=resp.read(6000).lower()
                        if any(t in sample for t in (b'pardon our interruption',b'just a moment...',b'access denied')):
                            return dict(url=url,status=status,result='unverified',final=final,pages=sorted(pages))
                    break
            except urllib.error.HTTPError as e:
                status=e.code;final=e.url
                if method=='HEAD' and status in (400,403,404,405,410,501):continue
                break
        verdict='reachable' if status<400 else 'missing' if status in (404,410) else 'unverified'
    except (OSError,ValueError) as e:
        status=str(e);final=url;verdict='unverified'
    return dict(url=url,status=status,result=verdict,final=final,pages=sorted(pages))


rows=[]
with concurrent.futures.ThreadPoolExecutor(5) as pool:
    for future in concurrent.futures.as_completed([pool.submit(probe,entry) for entry in destinations.items()]):
        rows.append(future.result())
        tmp=args.output.with_suffix('.partial')
        tmp.write_text(json.dumps(rows,indent=2)+'\n')
        tmp.replace(args.output)
rows.sort(key=lambda r:r['url'])
args.output.write_text(json.dumps(rows,indent=2)+'\n')
print('External destinations:',dict(Counter(r['result'] for r in rows)))
