"""Connect the geographic database to the live edition, authority and section catalogs."""
import gzip
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from html import escape, unescape
from pathlib import Path
from topic_reader import PATTERNS
from current_catalog import BASE, PUBLIC, read, save
from atlas_places import attach_municipal_portals, ROSTER
from regional_reader import slug, write, subject

API=Path('public/api/v2')
COUNTY_ISSUER={'025':'imperial-county','037':'los-angeles-county-public-works','059':'orange-county-public-works',
    '065':'riverside-county','071':'san-bernardino-county','073':'san-diego-county','111':'ventura-county'}
NATIONAL={'fhwa','u-s-access-board','caltrans'}
REGIONAL={'sandag','san-diego-regional-standards'}
TOPIC_NAMES={t['slug']:t['name'] for g in read('data/topics.json') for t in g['topics']}
OFFICIAL={
 'fhwa':'https://mutcd.fhwa.dot.gov/','caltrans':'https://dot.ca.gov/','u-s-access-board':'https://www.access-board.gov/',
 'ladot':'https://ladot.lacity.gov/','la-boe':'https://engineering.lacity.gov/','los-angeles-county-public-works':'https://pw.lacounty.gov/',
 'sandag':'https://www.sandag.org/','san-diego-regional-standards':'https://www.regional-stds.com/',
 'la-metro':'https://www.metro.net/','octa':'https://www.octa.net/','mts':'https://www.sdmts.com/',
 'omnitrans':'https://omnitrans.org/','riverside-transit':'https://www.riversidetransit.com/','gold-coast':'https://www.gctd.org/',
 'ictc':'https://www.imperialctc.org/'}
OPERATORS={'la-metro':['Los Angeles County Metropolitan Transportation Authority','Los Angeles Metro'],
 'octa':['Orange County Transportation Authority'], 'mts':['San Diego Metropolitan Transit System','San Diego Metropolitan Transit System (MTS)'],
 'riverside-transit':['Riverside Transit Agency'],'gold-coast':['Gold Coast Transit District','Gold Coast Transit'],
 'omnitrans':['Omnitrans'], 'ictc':['Imperial Valley Transit','Imperial County Transportation Commission']}
TITLES={'la-boe':'Los Angeles Bureau of Engineering','ladot':'Los Angeles Department of Transportation',
        'fhwa':'Federal Highway Administration','mts':'San Diego Metropolitan Transit System','ictc':'Imperial County Transportation Commission'}
SECTIONS={
 'tools':('Tools','Look up standards, get CAD blocks or run an engineering check.','teal'),
 'cad':('CAD','Sign, pavement marking and signal blocks as DWG, block editors and AutoCAD templates.','teal'),
 'topics':('Design topics','Compare treatments, then follow their governing sections and agency drawings.','teal'),
 'signs':('Sign chart','Every sign by code, with its face, sizes, sources and DWG.','amber'),
 'markings':('Pavement markings','Caltrans striping details, arrows, words, crosswalks, bicycle and colored-pavement markings and curb paint.','amber'),
 'mutcd':('Federal MUTCD','FHWA · 11th Edition with Revision 1','blue'),
 'ca-mutcd':('California MUTCD','Caltrans · California MUTCD 2026','green'),
 'details':('Drawing and detail index','Find the drawing number, source publication, and all sheets in the set.','amber'),
 'transit':('Transit operator guidance','Select the operating agency and trace the boarding, vehicle, and street design requirements.','violet'),
 'agencies':('Issuing agencies','Find the authority responsible for a publication and open its reference collection.','green'),
 'regions':('Jurisdiction directory','Browse by county, city, operator, or issuing agency.','green'),
 'cities':('Municipal standards','Locate city standards and check the street jurisdiction for your project.','green'),
 'guides':('Design guides','Compare design guidance by publisher and application.','teal'),
 'bulletins':('Design bulletins and policy','Read the issuing agency, applicability, and related manual sections together.','blue'),
 'boe':('Los Angeles Bureau of Engineering','City of Los Angeles · public works and street design','green'),
 'ladot':('Los Angeles Department of Transportation','City of Los Angeles · traffic design and operations','green'),
 'caltrans':('Caltrans publications','State highway design, standard plans, and California traffic control guidance.','green'),
 'fhwa':('Federal Highway Administration','Federal transportation guidance and evaluation resources.','blue'),
 'ada':('Accessibility guidance','U.S. Access Board · accessible routes and facility elements','violet'),
 'map':('Browse by location','Choose a municipality to find its standards, issuing agencies, and official city website. Select a street for roadway and transit records.','teal'),
 'sources':('Source directory','Browse issuing organizations and source publications.','blue'),
 'keywords':('Keyword index','Find a subject and follow it to its reference.','teal'),
 'search':('Standards search','Find an identifier, a publication, or wording across the site.','teal'),
 'guide':('Using the reference','Browse by guide, design topic, or municipality.','blue'),
 'ask':('Reference tools','Search sources and review the available engineering tools.','blue')}

def anchor(url,label):
    return '<a href="'+escape(url,quote=True)+'">'+escape(label)+'</a>'

def route(path):
    return BASE+'/'+path.strip('/')+'/'

def pathfor(root,key):
    return next((p for p in [root/key/'index.md',root/(key+'.md'),root/(key+'.mdx')] if p.is_file()),None)

def read_title(path):
    m=re.search('^title: *(.+)$',path.read_text(),re.M)
    return unescape(m[1].strip().strip('"\'')) if m else path.stem

def atlas_vendor():
    folder=Path('public/vendor/atlas');folder.mkdir(parents=True,exist_ok=True)
    for module,files in {'leaflet':['dist/leaflet.js','dist/leaflet.css','dist/images','LICENSE'],
                         'sql.js':['dist/sql-wasm.js','dist/sql-wasm.wasm','LICENSE'],
                         'fflate':['umd/index.js','LICENSE']}.items():
        for name in files:
            source=Path('node_modules')/module/name
            dest=folder/({'LICENSE':module+'-LICENSE.txt','umd/index.js':'fflate.js'}.get(name,Path(name).name))
            if source.is_dir():shutil.copytree(source,dest,dirs_exist_ok=True)
            else:shutil.copyfile(source,dest)

def prepare(root,look):
    atlas_vendor()
    if not (API/'layers.json').is_file() or not (API/'stop-operators.json').is_file():
        raise RuntimeError('Run python pipeline/atlas/compile.py to prepare the public geographic sources before building.')
    modes=read(PUBLIC/'agency-modes.json')
    places=read(API/'places.json')
    attach_municipal_portals(places)
    save(API/'places.json',places)
    county_names={v['name']:v['county'] for v in places if v['kind']=='county'}
    editions=read('data/reference/transit-guides.json')
    for key,_,_,_,_ in editions:
        profile='/regions/'+key+'/'
        modes[key]['home']=BASE+profile
        if profile not in modes[key]['roots']:modes[key]['roots'].append(profile)
    save(PUBLIC/'agency-modes.json',modes)
    save(Path('public/api/v1/agencies.json'),modes)
    location_by_name={slug(v['name']):v for v in places if v['kind']=='city'}
    operators={row[0]:row for row in editions}
    registry=defaultdict(list)
    with gzip.open('data/reference/regional/catalog.json.gz','rt') as f:regional=json.load(f)
    regional+=read('data/reference/atlas/county-publications.json')
    for row in regional:
        key=slug(row['agency']); title=row['title']
        if row['source'].endswith('BikewaysConnectivityStudy_September2025Presentation.pdf'):title='Bikeways Connectivity Study · September 2025 webinar'
        registry[key].append(dict(title=title,url=route('regions/'+key+'/'+row['key']),source=row['source'],pages=row['pages'],kind='Publication'))
    for key,name,county,title,url in editions:
        local=Path('public/transit-publications')/(key+'.pdf')
        import pymupdf
        with pymupdf.open(local) if local.exists() else __import__('contextlib').nullcontext() as doc:
            registry[key].append(dict(title=title,url=route('transit/'+key),source=url,pages=len(doc) if doc else 0,kind='Operator guide' if doc else 'Guide overview'))
    guides=read('public/api/v1/guides.json')
    for book,chapters in guides.items():
        link='/'+book+'/'
        for key,mode in modes.items():
            if not link.startswith(tuple(mode['roots'])):continue
            file=pathfor(root,book)
            if file:registry[key].append(dict(title=read_title(file),url=BASE+link,chapters=len(chapters),kind='Manual'))
    city_table=(root/'cities/index.md').read_text()
    for name,body in re.findall(r'<tr data-city="([^"]+)"[^>]*>(.*?)</tr>',city_table,re.S):
        match=re.search(r'href="(https://[^"]+)"',body)
        if match:OFFICIAL.setdefault(slug(name),unescape(match[1]))
    profiles={}
    for key,mode in modes.items():
        name=mode['name']; place=None; county=None
        if key in COUNTY_ISSUER.values():
            typ='County public works'; county=next(k for k,v in COUNTY_ISSUER.items() if v==key)
        elif key in NATIONAL:typ='State agency' if key=='caltrans' else 'Federal agency'
        elif key in operators:typ='Transit agency';county=county_names[operators[key][2]]
        elif key in REGIONAL:typ='Regional agency' if key=='sandag' else 'Regional standards';county='073'
        else:
            typ='Municipal agency' if key in ('ladot','la-boe') else 'City'
            place=location_by_name.get('los-angeles' if key in ('ladot','la-boe') else key.removeprefix('city-of-'))
            if place:county=place['county']
        if not registry[key] and pathfor(root,key+'/standard-plans'):
            file=pathfor(root,key+'/standard-plans')
            registry[key].append(dict(title=read_title(file),url=route(key+'/standard-plans'),source=OFFICIAL.get(key,''),kind='Standard plans'))
        if not registry[key]:raise ValueError('Missing publication for '+key)
        official=OFFICIAL.get(key) or next((r['source'] for r in registry[key] if r.get('source')),None)
        if not official:raise ValueError('Missing official source for '+key)
        profiles[key]=dict(key=key,name=name,fullName=TITLES.get(key,name),kind=typ,county=county,
                           place=place['id'] if place else None,home=mode['home'],official=official,publications=registry[key])
    for key,p in profiles.items():
        if key in NATIONAL:related=[k for k in NATIONAL if k!=key]
        else:related=[k for k,q in profiles.items() if k!=key and q['county']==p['county'] and (q['kind']=='County public works' or k in operators or q['place'] and q['place']==p['place'])]
        p['related']=sorted(related)
        write(root,'regions/'+key,p['name'],profile_body(p,profiles))
        look.setdefault(p['fullName'],[]).append([p['name']+' · jurisdiction profile',p['home']])
    save(API/'profiles.json',profiles)
    save(API/'operator-aliases.json',OPERATORS)
    save(API/'topics.json',TOPIC_NAMES)
    save(Path('.standards/section-identity.json'),SECTIONS)
    # Keep county anchors from previous editions and route every issuer through its profile.
    directory=root/'regions/index.md';text=directory.read_text()
    start=text.index('<div class="geobrowse">');end=text.index('<section class="county-group"',start)
    text=text[:start]+('<p class="jurisdiction-intro">Browse by county or '+anchor(route('map'),'choose a city on the map')+'.</p>\n\n')+text[end:]
    for key,_,_,_,_ in editions:
        text=text.replace('"'+route('transit/'+key)+'"','"'+profiles[key]['home']+'"')
    for name,code in county_names.items():
        tag='id="county-'+slug(name)+'"'
        pos=text.index('</h2>',text.index(tag))+5
        text=text[:pos]+anchor(route('map')+'?county='+code,'Explore '+name+' County on the map')+text[pos:]
        cities=sorted((p for p in places if p['kind']=='city' and p['county']==code),key=lambda p:p['name'])
        entries=[]
        for city in cities:
            title='Ventura (San Buenaventura)' if city['name']=='San Buenaventura' else city['name']
            url=route('map')+'?city='+city['id']
            entry=anchor(url,title)+' · '+anchor(city['official'],'City website')
            local=[anchor(p['home'],p['name']+' standards') for p in profiles.values() if p['place']==city['id']]
            entries.append('<li id="city-'+city['id']+'">'+entry+(' · '+' · '.join(local) if local else '')+'</li>')
            aliases=[city['name']] if title==city['name'] else [city['name'],'Ventura',title]
            for label in aliases:
                look.setdefault(label,[]).append([title+' · municipal standards map ('+name+' County)',url])
        end=text.index('</section>',pos)
        directory_list='<details><summary>All '+str(len(cities))+' municipalities in '+escape(name)+' County</summary><ul>'+''.join(entries)+'</ul></details>'
        text=text[:end]+directory_list+text[end:]
    first=text.index('<section class="county-group"')
    last=text.rindex('</section>')+len('</section>')
    directory.write_text(text[:first]+'<div class="county-directory">'+text[first:last]+'</div>'+text[last:])
    home=root/'index.mdx';text=home.read_text()
    for name,code in county_names.items():
        text=text.replace(route('regions')+'#county-'+slug(name),route('map')+'?county='+code)
    home.write_text(text)
    for page in ('agencies','cities','sources'):
        f=pathfor(root,page);text=f.read_text();front,sep,body=text.partition('\n---\n')
        f.write_text(front+sep+'\n<nav class="source-paths" aria-label="Find an authority">'+anchor(route('map'),'Find standards by municipality')+anchor(route('regions'),'Browse jurisdiction profiles')+'</nav>\n\n'+body)
    for key in TOPIC_NAMES:
        f=pathfor(root,'topics/'+key)
        if f:
            text=f.read_text()
            label=anchor(route('map')+'?topic='+key,'Browse this topic by municipality')
            f.write_text(text.replace('</nav>',label+'</nav>',1))
    source=pathfor(root,'santa-monica/standard-plans')
    text=source.read_text()
    def heading(match):
        title=unescape(match[1]);key='review-'+slug(title)
        look.setdefault('Santa Monica '+title,[]).append([title,route('santa-monica/standard-plans')+'#'+key])
        return '<span id="'+key+'"></span>\n\n'+match[0]
    source.write_text(re.sub(r'^## (.+)$',heading,text,flags=re.M))
    for term in ('municipal standards map','city map','browse by municipality','standards map'):
        look[term]=[['Municipal standards map · cities, agencies and standards',route('map')]]
    # The map is a shared lookup surface, never an authority for project requirements.
    write(root,'map','Municipal standards map',Path('src/map/atlas.html').read_text().replace('%%BASE%%',BASE))
    write(root,'map/data','Geographic data and downloads',data_page(profiles))
    return profiles

def profile_body(p,profiles):
    name=p['name'];publications=p['publications'];key=p['key']; county=p['county']
    county_name=read(API/'layers.json')['countyLayers'][county]['name']+' County' if county else 'California' if key=='caltrans' else 'United States'
    leads={'City':f'Start with {name}’s local drawings and design references, then check the road segment and any operator serving the stop.',
           'County public works':f'Use this collection for {name} review. Check reported ownership on the project segment, especially at city limits.',
           'Municipal agency':f'Use the {name} collection for City of Los Angeles work. Confirm which department reviews the design element.',
           'Transit agency':f'Use the {name} operator guidance for stops and passenger facilities. Check the street owner separately for roadway approvals.',
           'State agency':'Use the California MUTCD, Caltrans standard plans, and design bulletins together when checking work on the state highway system.',
           'Federal agency':f'Find {name} publications and verify the applicable edition for the project.',
           'Regional agency':'Find regional planning guidance and identify the city, county, or operator responsible for implementation.',
           'Regional standards':'Find the regional drawing series, then check the adopting agency and its local supplements.'}
    mapurl=route('map')+'?issuer='+key
    head=(f'<div class="publisher-toolbar"><span>{escape(p["kind"])} · {escape(county_name)}</span>'+
          anchor(mapurl,'View on map')+f'<button class="mode-action" data-set-mode="{key}">Use {escape(name)} mode</button></div>')
    cards=[]
    for doc in publications:
        n=doc.get('pages');chapters=doc.get('chapters')
        count=(f'{n} '+('page' if n==1 else 'pages') if n else f'{chapters} '+('chapter' if chapters==1 else 'chapters') if chapters else doc['kind'])
        card='<a href="'+escape(doc['url'])+'"><strong>'+escape(doc['title'])+'</strong><span>'+escape(count)+'</span></a>'
        cards.append((subject(doc),card))
    if len(cards)<=16:
        shelves='<div class="authority-books">'+''.join(c for _,c in cards)+'</div>'
    else:
        grouped=defaultdict(list)
        for label,card in cards:grouped[label].append(card)
        groups=[]
        for label,items in sorted(grouped.items()):
            remaining=len(items)-2
            more=('<details><summary>Show '+str(remaining)+' more</summary><div class="authority-books">'+''.join(items[2:])+'</div></details>') if remaining>0 else ''
            groups.append('<section><h3>'+escape(label)+'</h3><div class="authority-books">'+''.join(items[:2])+'</div>'+more+'</section>')
        shelves='<div class="publication-families">'+''.join(groups)+'</div>'
    sections=[head,
              '## Publications and drawings',shelves,'## Find a reference',
              f'<div class="agency-browser" data-agency="{key}"><label><span class="sr-only">Search this collection</span><input type="search" aria-label="Search this collection" placeholder="Drawing number, title, or subject"></label><button type="button">Browse all references</button><div role="status" aria-live="polite"></div><ul></ul></div>',
              '## Project coordination',leads[p['kind']],'<div class="authority-related">'+''.join(anchor(profiles[k]['home'],profiles[k]['name']) for k in p['related'])+'</div>',
              '## Publisher and coverage',anchor(p['official'],name+' publisher website')+' · '+anchor(route('map/data'),'Geographic sources and coverage'),
              f'<span hidden data-pagefind-filter="agency:{key}"></span>']
    return '\n\n'.join(sections)

def data_page(profiles):
    m=read(API/'layers.json')
    rows=['Source snapshots use longitude and latitude in WGS 84. The map queries compressed SQLite databases in a browser worker. Download the same databases for desktop analysis.',
          '## Municipalities and standards',
          anchor(BASE+'/api/v2/index.json','API v2 manifest')+' · '+anchor(BASE+'/api/v2/places.json','City and county identifiers and municipal websites')+' · '+
          anchor(BASE+'/api/v2/profiles.json','Jurisdiction and publication directory')+' · '+anchor(BASE+'/api/v2/db/site.sqlite.gz','Download the standards index (SQLite, gzip)'),
          anchor(BASE+'/api/v2/municipalities.geojson','Municipal boundary overview (GeoJSON)')+' · '+anchor(BASE+'/js/atlas/land.geojson','Regional land basemap (GeoJSON)'),
          '## Coverage by county','','| County | Named street intersections | Scheduled stop records | HPMS road paths | Files |','|---|---:|---:|---:|---|']
    for code,d in m['countyLayers'].items():
        links=' · '.join([anchor(BASE+'/api/v2/boundaries/'+code+'.geojson','Boundaries'),anchor(BASE+'/api/v2/'+d['network']['file'],'Stops and highways'),anchor(BASE+'/api/v2/'+d['intersections']['index'],'Street index')])
        rows.append(f'| {d["name"]} | {d["intersections"]["crossings"]:,} | {d["network"]["stops"]:,} | {d["ownershipPaths"]:,} | {links} |')
    road_context=API/'road-context.json'
    if road_context.is_file():
        local=read(road_context)
        source=local['sources']['pasadena-streets']
        rows+=['','## Pasadena street inventory',
               f"The City of Pasadena lists {local['count']:,} named street centerlines in its {source['sourceEdited']} GIS snapshot. Each segment links its publisher record and includes the city’s street classification. Check the HPMS ownership record separately.",
               anchor(source['catalog'],'City of Pasadena GIS source')+' · '+anchor(BASE+'/api/v2/road-context.json','Inventory metadata')+' · '+anchor(BASE+'/api/v2/'+local['file'],'Street centerlines (GeoJSON)')]
    rows+=['','## How to interpret a location','City boundaries identify the municipality containing a point. A nearby road record reports the HPMS ownership category and source route ID. At an intersection or interchange, inspect each approach separately. Maintenance agreements and permit authority require agency confirmation.',
           'Where the statewide inventory lists an operator group, an operator-specific match requires the same stop ID, nearby coordinates, and all reported routes serving that stop in the native GTFS feed. '+anchor('https://www.sdmts.com/google_transit_files/google_transit.zip','San Diego MTS feed')+' · '+anchor('https://govcbus.com/gtfs','Ventura operator feed')+'.',
           'Stop distances are measured to the published stop point. Operators are drawn from the Caltrans GTFS snapshot. The stop list is a design reference and does not provide live departures.',
           '## Data sources','Database snapshot assembled '+m['snapshot']+'. Source editions and publication dates can differ.']
    rows += ['- '+anchor(s['url'],s['title']) for s in m['sources'].values()]
    rows.append('- '+anchor(ROSTER,'California Secretary of State · 2026 incorporated cities and towns')+'. Each incorporated city has a municipal website and a directory source. Cities with indexed publications also link to the relevant agency collection.')
    rows+=['','## Working with the database',
           'The layer manifest lists county network databases, street name indexes, and ownership partitions with bounding boxes. Gzip-decompress each .sqlite.gz file before opening it in SQLite. Street indexes map a street name to the partitions containing it. Join the approach table to crossing by node and to street by ID. Ownership paths and state highways store ordered WGS 84 line coordinates as JSON.',
           'The site database connects each authority to indexed references and publications. Its URLs open directly in the reader. '+anchor(BASE+'/api/v2/layers.json','Open the geographic layer manifest')+'.']
    if all('referenceCount' in v for v in profiles.values()):
        rows+=['','## Indexed jurisdictions','','| Issuing agency | Coverage | Publications | Indexed destinations |','|---|---|---:|---:|']
        for p in sorted(profiles.values(),key=lambda p:((p['county'] or ''),p['name'])):
            county=m['countyLayers'][p['county']]['name']+' County' if p['county'] else p['kind']
            rows.append('| '+anchor(p['home'],p['name'])+' | '+county+' | '+str(len(p['publications']))+' | '+f"{p['referenceCount']:,}"+' |')
    return '\n'.join(rows)

def topic_references(p, collection, details):
    by_topic=defaultdict(list)
    books={r['url']:r['title'] for r in p['publications']}
    for path, label, _, aliases in collection:
        url=BASE+path
        if url==p['home']:continue
        item=details.get(url)
        title=(item['num']+' · '+item['title']) if item else books.get(url,label)
        title=unescape(title)
        title=re.sub(r'^'+re.escape(p['name'])+r' [·—] ', '',title)
        plain=re.sub(r'^Page (\d+) · ', '',title)
        for key,pattern in PATTERNS.items():
            rank=int(p['name']+' · '+key in aliases)
            if re.search(pattern,plain,re.I):rank=4
            if item and key in item.get('topics',[]) and re.search(pattern,(item.get('kw') or '')+' '+(item.get('sum') or ''),re.I):
                rank=max(2,rank)
            if key=='transit' and p['kind']=='Transit agency' and url in books:rank=5
            if not rank:continue
            if not item and not url in books and title==p['name']:continue
            if item and item['type'] in ('Standard drawing','Agency sheet'):rank+=2
            if '#page-' in url and p['kind']=='Transit agency':rank+=2
            if key=='transit' and re.search(r'bus stop|stop placement|bus transit|boarding|bus pad|bus bulb|stop location',plain,re.I):rank+=3
            by_topic[key].append((-rank,len(title),title,url))
    result={}
    for key,entries in by_topic.items():
        used=set();rows=[]
        for _,_,title,url in sorted(entries):
            comparable=re.sub(r'^Page \d+ · ', '',title).lower()
            if comparable in used:continue
            used.add(comparable);rows.append(dict(title=title,url=url))
            if len(rows)==4:break
        result[key]=rows
    return result

def task_section(p):
    groups=[]
    for key,label in TOPIC_NAMES.items():
        refs=p['topics'].get(key)
        if not refs:continue
        groups.append('<details><summary>'+escape(label)+'</summary><ul>'+''.join('<li>'+anchor(r['url'],r['title'])+'</li>' for r in refs)+'</ul></details>')
    if groups:return '<div class="authority-topics">'+''.join(groups)+'</div>'
    return 'The publisher files this material by document. Use the publication list above or search this collection by title.'

def finish(root,profiles):
    # A stable URL is the reference key across search, geography, and exported SQL.
    conn=sqlite3.connect(':memory:')
    conn.executescript("""
    CREATE TABLE agency(id TEXT PRIMARY KEY,name TEXT,kind TEXT,county TEXT,place TEXT,profile TEXT);
    CREATE TABLE publication(agency TEXT REFERENCES agency(id),url TEXT,title TEXT,kind TEXT,source TEXT,pages INTEGER,chapters INTEGER,PRIMARY KEY(agency,url));
    CREATE TABLE reference(url TEXT PRIMARY KEY,title TEXT,source TEXT);
    CREATE TABLE agency_reference(agency TEXT REFERENCES agency(id),url TEXT REFERENCES reference(url),PRIMARY KEY(agency,url));
    CREATE TABLE topic(id TEXT PRIMARY KEY,name TEXT);
    CREATE TABLE agency_topic_reference(agency TEXT REFERENCES agency(id),topic TEXT REFERENCES topic(id),url TEXT REFERENCES reference(url),position INTEGER,PRIMARY KEY(agency,topic,url));
    CREATE INDEX reference_by_source ON reference(source);
    PRAGMA user_version=2;
    """)
    records=read(PUBLIC/'search-catalog.json')
    details={r['url']:r for r in read(PUBLIC/'details.json')}
    conn.executemany('INSERT INTO topic VALUES(?,?)',TOPIC_NAMES.items())
    conn.executemany('INSERT OR IGNORE INTO reference VALUES(?,?,?)',[(BASE+url,title,source) for url,title,source,_ in records])
    for key,p in profiles.items():
        coll=read(PUBLIC/'collections'/ (key+'.json'))
        scoped={BASE+r[0] for r in coll if BASE+r[0]!=p['home']}
        p['referenceCount']=len(scoped)
        p['topics']=topic_references(p,coll,details)
        path=root/'regions'/key/'index.md'
        txt=path.read_text().replace('Browse all references</button>',f'Browse all {len(scoped):,}</button>')
        path.write_text(txt.replace('## Project coordination','## Review by topic\n\n'+task_section(p)+'\n\n## Project coordination',1))
        conn.execute('INSERT INTO agency VALUES(?,?,?,?,?,?)',(key,p['name'],p['kind'],p['county'],p['place'],p['home']))
        for topic,rows in p['topics'].items():
            conn.executemany('INSERT INTO agency_topic_reference VALUES(?,?,?,?)',[(key,topic,r['url'],i) for i,r in enumerate(rows,1)])
        for r in p['publications']:
            conn.execute('INSERT OR IGNORE INTO publication VALUES(?,?,?,?,?,?,?)',(key,r['url'],r['title'],r['kind'],r.get('source'),r.get('pages'),r.get('chapters')))
        conn.executemany('INSERT OR IGNORE INTO agency_reference VALUES(?,?)',((key,v) for v in scoped))
    conn.commit();(API/'db').mkdir(exist_ok=True)
    with gzip.open(API/'db/site.sqlite.gz','wb',compresslevel=8) as out:out.write(conn.serialize())
    conn.close();save(API/'profiles.json',profiles)
    write(root,'map/data','Geographic data and downloads',data_page(profiles))
    save(API/'index.json',{'version':2,'crs':'EPSG:4326','snapshot':read(API/'layers.json')['snapshot'],
         'layers':'layers.json','places':'places.json','countyGeometry':'counties.geojson','municipalityGeometry':'municipalities.geojson','basemapLand':'../../js/atlas/land.geojson','authorities':'profiles.json','topics':'topics.json','stopOperators':'stop-operators.json','siteDatabase':'db/site.sqlite.gz','guideHierarchy':'../v1/guides.json','documentation':route('map/data')})
    old=read(Path('public/api/v1/index.json'));old['geographicIndex']=old['projectAtlas']='../v2/index.json';save(Path('public/api/v1/index.json'),old)
