"""Build one searchable identifier and title catalog and tag the full-text index by source."""
from html import escape, unescape
from pathlib import Path
import json
import re

from current_catalog import BASE, PUBLIC, save

CITIES = {'burbank','pasadena','long-beach','palmdale','torrance','gardena','glendora','santa-monica','west-hollywood','culver-city'}
SCOPES = {'boe':'LA BOE','ladot':'LADOT','ca-mutcd':'CA MUTCD','mutcd':'Federal MUTCD',
          'caltrans':'Caltrans','signs':'Signs','markings':'Markings','topics':'Topics and tools'}


def scope_for(url):
    path = url.removeprefix(BASE).strip('/').split('#')[0].split('/')
    if path[0] == 'details' and len(path)>1:
        path = path[1:]
    if path[0] == 'bulletins' and len(path)>1:
        if path[1].startswith('caltrans-'): return 'Caltrans'
        if path[1].startswith('ladot-'): return 'LADOT'
    if path[0] in CITIES: return 'Local cities'
    return SCOPES.get(path[0], 'Guides and references')


def build(root,lookup,details):
    records = {}
    def add(url,title,key=''):
        if not url.startswith(BASE+'/') or '/s/' in url:
            return
        record = records.setdefault(url,[unescape(title),scope_for(url),[]])
        if key and key not in record[2]: record[2].append(key)
    for key, entries in lookup.items():
        for label,url in entries:
            add(url,label,key)
    for item in details:
        add(item['url'],(item['num']+' '+item['title']).strip(),item['num'])
    add(BASE+'/santa-monica/standard-plans/#ttcp','Santa Monica TTCP review and submission requirements','Santa Monica TTCP')
    chapter = re.compile(r'^## (\d[A-Z]\.\d+(?:\(CA\))?)\s+(.+)',re.M)
    for path in sorted(root.rglob('*')):
        if path.suffix not in ('.md','.mdx'):continue
        slug=path.relative_to(root).with_suffix('').as_posix().removesuffix('/index')
        if slug in ('index','search','ask'):continue
        url=f'{BASE}/{slug}/'
        body=path.read_text()
        title=re.search(r'^title:\s*(.+)$',body,re.M)
        if not title:continue
        value=title[1].strip().strip('"\'')
        # Prefer a real page title when the lookup text was only an alias.
        add(url,value)
        if slug.startswith(('ca-mutcd/','mutcd/')):
            for m in chapter.finditer(body):
                num,name=m.groups()
                anchor=re.sub(r'[^a-z0-9]','',num.lower())
                add(url+'#'+anchor,scope_for(url)+' '+num+' '+re.sub('<[^>]+>','',name),num)
        if slug == 'caltrans/standard-plans-2026':
            for code,name in re.findall(r'<span id="plan-t\w+">(T\w+)</span> \| ([^|]+) \|',body):
                add(url+'#plan-'+code.lower(),f'Caltrans {code} · {name.strip()}',code)
        # Pagefind reads explicit-value tags inside the article, including on deep municipal pages.
        marker='<span hidden data-pagefind-filter="source:'+escape(scope_for(url),quote=True)+'"></span>'
        head,sep,article=body.partition('\n---\n')
        if sep:path.write_text(head+sep+'\n'+marker+'\n'+article)
    save(PUBLIC/'search-catalog.json',[[url.removeprefix(BASE),*fields] for url,fields in records.items()])
