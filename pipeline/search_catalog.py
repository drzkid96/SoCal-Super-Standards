"""Build one searchable identifier and title catalog and tag the full-text index by source."""
from html import escape, unescape
from pathlib import Path
import json
import re

from current_catalog import BASE, PUBLIC, save
from manual_art import ART, SHEET_COUNTS

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
    sheet_sets = []
    for item in details:
        path = item['url'].removeprefix(BASE)
        edition = path.strip('/').split('/')[0]
        key = item['type']+' '+item['num']
        count = SHEET_COUNTS.get(edition,{}).get(key)
        if count:
            route, anchor = path.split('#')
            first_page = ART[edition][key][1]
            sheets = [[anchor if i == 1 else f'{anchor}-sheet-{i}', first_page+i-1] for i in range(1, count+1)]
            sheet_sets.append({'keys':[key, item['num']], 'label':key+' · '+item['title'], 'tag':scope_for(item['url']),
                              'route':route, 'sheets':sheets})
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
        if slug.startswith('details/ladot/'):
            ids = re.findall(r'<figure id="(sheet-\d+)" class="dfig"><a href="[^"]*/p(\d+)\.webp"', body)
            drawing = re.search(r'<span class="dwg-num">([^<]+)</span>', body)
            if ids and drawing:
                code = unescape(drawing[1])
                keys = [code]
                publication = re.search(r'/mpp-(\d+)-', url)
                if publication: keys.append('MPP '+publication[1]+' '+code)
                sheet_sets.append({'keys':keys, 'label':records[url][0], 'tag':'LADOT', 'route':url.removeprefix(BASE),
                                   'sheets':[[anchor,int(page)] for anchor,page in ids]})
        if slug == 'santa-monica/standard-plans':
            for doc, name, keys in [
                ('requirements','TTCP Review & Submission Requirements',['Santa Monica TTCP','Santa Monica TTCP requirements']),
                ('supplement','Traffic Control Plan Supplement',['Santa Monica TCP supplement','Santa Monica TTCP supplement'])]:
                ids = re.findall(r'id="(sheet-ttcp-'+doc+r'-(\d+))"', body)
                if ids:
                    sheet_sets.append({'keys':keys, 'label':'Santa Monica · '+name, 'tag':'Local cities',
                                       'route':url.removeprefix(BASE), 'sheets':[[anchor,int(page)] for anchor,page in ids]})
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
    save(PUBLIC/'search-sheets.json',sheet_sets)
    save(PUBLIC/'search-catalog.json',[[url.removeprefix(BASE),*fields] for url,fields in records.items()])
