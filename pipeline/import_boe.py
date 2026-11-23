"""Build BOE manual pages from the City's navigation tree. Run before Astro."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag, quote
from urllib.request import urlopen
import argparse
import json
import re
import time

from lxml import etree, html

ORIGIN = 'https://completestreetdesignmanual.engineering.lacity.gov'
START = ORIGIN + '/e-100-introduction-and-general-information'
BASE = '/SoCal-Super-Standards/boe/street-design'
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src/content/docs/boe/street-design'
EXCLUDE = re.compile(r'retaining walls?|bulkheads?|slope stability|structural pavement|pavement structural|structural section|side slopes|soil mechanics|bridge structural|foundation design', re.I)
ALLOWED = set('a p br div span h2 h3 h4 h5 h6 ul ol li table caption colgroup col thead tbody tfoot tr th td strong b em i sub sup blockquote figure figcaption img hr dl dt dd pre code u s del ins'.split())


def slug(url):
    path = urlsplit(url).path.strip('/')
    return re.sub('[^a-z0-9-]+', '-', path.rsplit('/', 1)[-1].lower()).strip('-') + '-' + sha256(path.encode()).hexdigest()[:8]


def fetch(url, cache):
    path = cache / (sha256(url.encode()).hexdigest()+'.html')
    if not path.exists():
        for attempt in range(3):
            try:
                with urlopen(url, timeout=35) as response:
                    if urlsplit(response.url).netloc != urlsplit(ORIGIN).netloc:
                        raise ValueError('Unexpected City page redirect')
                    data = response.read()
                tree = html.fromstring(data)
                if not tree.xpath('//main//h1'): raise ValueError('City page lacks a manual heading: '+url)
                path.write_bytes(data)
                break
            except OSError:
                if attempt == 2: raise
                time.sleep(2**attempt)
    return html.fromstring(path.read_bytes())


def included(url, title):
    return not (re.search('/e-6(?:70|80)(?:-|/|$)', url) or EXCLUDE.search(title))


def children(doc, url):
    for a in doc.xpath('//main//a[contains(concat(" ",normalize-space(@class)," ")," tile ")] | //main//*[contains(@class,"views-row")]//a[@href]'):
        href = urldefrag(urljoin(url,a.get('href')))[0].rstrip('/')
        title = ' '.join(a.text_content().split())
        if href.startswith(ORIGIN+'/') and not Path(urlsplit(href).path).suffix and included(href,title):
            yield href


def render(node, url, known):
    if not isinstance(node.tag,str) or node.tag in ('script','style','form','iframe'): return ''
    tag=node.tag.lower()
    body=escape(node.text or '')+''.join(render(c,url,known)+escape(c.tail or '') for c in node)
    if tag not in ALLOWED:return body
    attrs = {}
    for key in ('id','name','alt','colspan','rowspan','scope','start','value','title'):
        if node.get(key):attrs[key]=node.get(key)
    key = {'a':'href','img':'src'}.get(tag)
    if key and node.get(key):
        target,frag=urldefrag(urljoin(url,node.get(key)))
        if urlsplit(target).scheme in ('https','http','mailto'):
            target=BASE+'/'+slug(target.rstrip('/'))+'/' if target.rstrip('/') in known else target
            attrs[key]=target+('#'+frag if frag else '')
    att=''.join(f' {k}="{escape(v, quote=True)}"' for k,v in attrs.items())
    if tag in ('img','br','hr','col'):return f'<{tag}{att}>'
    return f'<{tag}{att}>{body}</{tag}>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=ROOT/'.boe-cache')
    args=parser.parse_args()
    args.cache.mkdir(parents=True,exist_ok=True)
    start=fetch(START,args.cache)
    seed={urljoin(ORIGIN,u) for u in start.xpath('//a/@href') if re.match(r'^/e-\d',u) and included(u,'')}
    if len(seed)<40:raise ValueError('City navigation is incomplete')
    pages={}
    todo=seed
    while todo:
        with ThreadPoolExecutor(max_workers=5) as pool:
            for u,d in zip(sorted(todo),pool.map(lambda x:fetch(x,args.cache),sorted(todo))):
                title=' '.join(d.xpath('string(//main//h1)').split())
                pages[u]=(title,d)
        todo={v for u in todo for v in children(pages[u][1],u)}-pages.keys()
    files={}
    catalog=[]
    index=['---','title: "Los Angeles BOE Street Design Manual"','---','','City of Los Angeles Bureau of Engineering. Browse street-design provisions by chapter and section.','']
    for u,(title,d) in sorted(pages.items(),key=lambda item:item[1][0]):
        body=d.xpath('//main//*[contains(@class,"field--name-description") or contains(@class,"field--name-body") or contains(@class,"field--name-field-document-file")]')
        child=list(dict.fromkeys(children(d,u)))
        links=[f'<li><a href="{BASE}/{slug(v)}/">{escape(pages[v][0])}</a></li>' for v in child]
        text=''.join(render(n,u,pages) for n in body)
        if not text.strip() and not child:
            nodes=d.xpath('//main//*[contains(@class,"region-content")]')
            if not nodes: raise ValueError('Unrecognized content template: '+u)
            text=''.join(render(n,u,pages) for n in nodes)
        content=f'---\ntitle: {json.dumps(title)}\n---\n\n<a href="{escape(u)}">City of Los Angeles Bureau of Engineering · Official section</a>\n\n<div>'+text+'</div>\n'
        if links:content+='\n<ul>'+''.join(links)+'</ul>\n'
        files[slug(u)+'.md']=content
        catalog.append({'title':title, 'url':BASE+'/'+slug(u)+'/', 'source':u, 'sections':len(child), 'tables':sum(len(n.xpath('.//table')) for n in body), 'illustrations':sum(len(n.xpath('.//img')) for n in body)})
        if u in seed:index.append(f'- [{title}]({BASE}/{slug(u)}/)')
    files['index.md']='\n'.join(index)+'\n'
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for name,content in files.items():(OUTPUT/name).write_text(content)
    for old in OUTPUT.glob('*.md'):
        if old.name not in files:old.unlink()
    destination=ROOT/'public/data/boe-sections.json'
    destination.write_text(json.dumps(catalog, ensure_ascii=False, indent=1)+'\n')
    print(f'Imported {len(pages)} BOE pages from {len(seed)} navigation entries.')


if __name__=='__main__':main()
