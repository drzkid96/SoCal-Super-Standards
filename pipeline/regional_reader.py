"""Build the geographic directory, agency workspaces and local sheet readers."""
from collections import defaultdict
from html import escape
from pathlib import Path
import json,re
from current_catalog import BASE
from render_regionals import prepare

def slug(name): return re.sub('[^a-z0-9]+','-',name.lower()).strip('-')
def write(root,route,title,body):
    path=root/route/'index.md'
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text('---\ntitle: '+json.dumps(title,ensure_ascii=False)+'\ntemplate: splash\ntableOfContents: false\n---\n\n'+body+'\n')

def subject(record):
    title=record['title'].lower()
    groups=[
        ('Signals and detection',r'signal|detection|traffic loop|cctv'),
        ('Crossings and accessibility',r'crosswalk|pedestrian|curb ramp|accessible'),
        ('Bikeways and transit',r'bikeway|bicycle|bike lane|transit|bus stop'),
        ('Signs and markings',r'sign|striping|marking|lane line|center ?line|turn pocket|turn lane|legend|stop bar|pavement marker'),
        ('Parking and access',r'parking|driveway|loading|truck dock'),
    ]
    return next((label for label,pattern in groups if re.search(pattern,title)), 'Public works and street design')

def build(root,lookup):
    docs=prepare()
    from topic_reader import PATTERNS
    titles=json.loads(Path('data/reference/atlas/regional-sheet-titles.json').read_text())
    patterns={k:re.compile(v,re.I) for k,v in PATTERNS.items()}
    by=defaultdict(list)
    for d in docs:by[d['agency']].append(d)
    la=['Burbank','Pasadena','Long Beach','Palmdale','Torrance','Gardena','Glendora','Santa Monica','West Hollywood','Culver City']
    counties={'Ventura':['Ventura County','Oxnard'],'Los Angeles':['Los Angeles County Public Works','LADOT','LA BOE',*la],
      'Orange':['Orange County Public Works','Anaheim','Irvine','Santa Ana','Huntington Beach','OCTA'],
      'San Bernardino':['San Bernardino County','City of San Bernardino','Ontario','Fontana'],
      'Riverside':['Riverside County','City of Riverside','Moreno Valley'],
      'San Diego':['San Diego Regional Standards','San Diego County','City of San Diego','Chula Vista','Escondido','SANDAG'],
      'Imperial':['Imperial County']}
    agencies={}
    for name in ['Caltrans','FHWA','U.S. Access Board','LADOT','LA BOE',*la,*sorted(by)]:
        key=slug(name)
        base={'la-boe':'boe','u-s-access-board':'ada'}.get(key,key)
        prefix=['/'+base+'/','/details/'+base+'/'] if name not in by else []
        if name=='Caltrans':prefix+=['/ca-mutcd/','/bulletins/caltrans-','/markings/line-types/']
        if name=='FHWA':prefix+=['/mutcd/']
        agencies[key]={'name':name,'roots':prefix+['/regions/'+key+'/'],'home':BASE+'/regions/'+key+'/'}
    Path('public/data/agency-modes.json').write_text(json.dumps(agencies))
    for key,mode in agencies.items():
        name=mode['name'];items=by.get(name,[])
        lines=[f'<button class="mode-action" data-set-mode="{key}">Use {escape(name)} mode</button>']
        if items: lines+=['','## Publications','']
        last_subject=None
        for d in sorted(items,key=lambda row:(subject(row),row['title'])):
            if subject(d)!=last_subject and len(items)>3:
                last_subject=subject(d)
                lines+=['','### '+last_subject,'']
            route='regions/'+key+'/'+d['key'];url=BASE+'/'+route+'/'
            title=d['title'];count=d['pages']
            lines.append(f'- [{escape(title)}]({url}) · {count} '+('pages' if count!=1 else 'page'))
            body=[f'<p class="reg-credit">{escape(name)} · {count} pages · <a href="{escape(d["source"])}">Publisher PDF</a></p>',
                  '<div class="reg-controls" hidden><button type="button" data-step="-1">← Previous</button><label>Page <select aria-label="Select sheet"></select></label><button type="button" data-step="1">Next →</button><button type="button" class="reg-overview" aria-expanded="false">Sheet grid</button></div><div class="reg-contact" hidden></div>']
            for i,(label,txt) in enumerate(zip(d['labels'],d['texts'],strict=True),1):
                label=titles.get(d['key'],{}).get(str(i),label)
                img=f'{BASE}/regional-sheets/{d["key"]}/{i}.avif'
                heading=f'Page {i}'+(' · '+label[:110] if label else '')
                body.append(f'<section class="reg-page" id="p-{i}" data-label="{escape(heading,quote=True)}"><h2>{escape(heading)}</h2><a href="{img}" class="reg-scan" data-title="{escape(title,quote=True)}, page {i}">Open full sheet image</a><p><a href="{url}#p-{i}">Link to this page</a> · <a href="{escape(d["source"])}#page={i}">Publisher PDF, page {i}</a></p>')
                if txt:body.append('<details><summary>Searchable page text</summary><p>'+escape(txt)+'</p></details>')
                body.append('</section>')
                ref=url+'#p-'+str(i)
                listing=[name+' · '+(heading if label else title+' · p. '+str(i)),ref]
                lookup.setdefault(name+' '+(label[:100] if label else title+' p. '+str(i)),[]).append(listing)
                for topic,pattern in patterns.items():
                    if pattern.search(txt):lookup.setdefault(name+' · '+topic,[]).append(listing)
            write(root,route,name+' · '+title,'\n'.join(body))
        lines+=['','## Search this collection','','<div class="agency-browser" data-agency="'+key+'"><input aria-label="Filter collection" placeholder="Filter by title or identifier"><div role="status"></div><ul></ul><button hidden>More results</button></div>']
        write(root,'regions/'+key,name,'\n'.join(lines))
    shapes=json.loads(Path('data/reference/regional/county-paths.json').read_text())
    centers={'Ventura':(63,148),'Los Angeles':(133,157),'Orange':(158,227),'San Diego':(236,302),'Imperial':(366,303),'Riverside':(308,226),'San Bernardino':(301,133)}
    maplinks=[]
    for county,ds in shapes.items():
        x,y=centers[county]
        maplinks.append(f'<a href="#county-{slug(county)}" aria-label="Browse {county} County"><path d="{ds}"/><text x="{x}" y="{y}">{county}</text></a>')
    static_svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -20 460 380"><style>path{fill:#b5cec1;stroke:#fff;stroke-width:1.4}text{font:600 10px sans-serif;fill:#214b48;text-anchor:middle}</style>'+''.join(maplinks)+'</svg>'
    Path('public/data/region-map.svg').write_text(static_svg)
    body=['<div class="geobrowse"><svg viewBox="0 -20 460 380" role="group" aria-label="Southern California counties">' + ''.join(maplinks) + '</svg><p>Choose a county on the map or browse the directory below.</p></div>']
    for county,choices in [('State and federal',['Caltrans','FHWA','U.S. Access Board']),*counties.items()]:
        body+=['<section class="county-group" id="county-'+slug(county)+'"><h2>'+escape(county+(' County' if county in counties else ''))+'</h2><div class="juris-list">']
        for name in choices:
            mode=agencies[slug(name)];body+=['<a href="'+mode['home']+'">'+escape(name)+' <span aria-hidden="true">→</span></a>']
        body+=['</div></section>']
    write(root,'regions','Browse by geography','\n'.join(body))
    # Pagefind and the direct search catalog share the same ownership definitions.
    for p in root.rglob('*'):
        if p.suffix not in ('.md','.mdx'):continue
        path='/'+p.relative_to(root).with_suffix('').as_posix().removesuffix('/index')+'/'
        owners=[key for key,mode in agencies.items() if any(path.startswith(prefix) for prefix in mode['roots'])]
        if owners:
            content=p.read_text()
            content+='\n' + ''.join(f'<span hidden data-pagefind-filter="agency:{key}"></span>' for key in owners)+'\n'
            p.write_text(content)
