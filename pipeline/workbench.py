"""Guide hierarchy, operator library, geographic API and homepage."""
import json,re,io,zipfile
from pathlib import Path
from html import escape
import pymupdf
from current_catalog import BASE,save
from regional_reader import write,slug

def build(root,lookup):
    api=Path('public/api/v1');api.mkdir(exist_ok=True,parents=True)
    editions=json.loads(Path('data/reference/transit-guides.json').read_text())
    folder=Path('public/transit-publications')
    from transit_publications import prepare
    prepare(editions)
    intro=[]
    modes=json.loads(Path('public/data/agency-modes.json').read_text())
    instructions={
       'ictc':'Use the on-street bus stop and transfer station chapters for Imperial Valley Transit projects. The handbook includes a stop relocation checklist.',
       'gold-coast':'Use the stop classification and amenity guidance when reviewing projects with the operator and the street owner.',
       'la-metro':'Start with the service design chapter for stop location, transfer movements and zone layout.',
       'octa':'Follow the street design and stop layout guidance from network planning to the curbside footprint.',
       'mts':'Use the bus design chapter for stop placement, boarding areas, amenities and fleet accommodation.',
       'omnitrans':'Review the stop requirements alongside development review and facility placement.',
       'riverside-transit':'Review stop placement, passenger amenities and the interface with the public right-of-way.'
    }
    for key,name,county,title,source in editions:
        route='transit/'+key;url=BASE+'/'+route+'/';pdf=folder/(key+'.pdf')
        countyurl=BASE+'/regions/#county-'+slug(county)
        intro.append(f'<a class="operator-entry" href="{url}"><strong>{escape(name)}</strong><span>{escape(title)}</span><small>{escape(county)} County</small></a>')
        body=[instructions[key],f'[Publisher edition]({source}) · [{county} County references]({countyurl})','']
        if pdf.is_file():
            with pymupdf.open(pdf) as doc:
                from PIL import Image
                art=Path('public/operator-pages')/key;art.mkdir(exist_ok=True,parents=True)
                for i,page in enumerate(doc,1):
                    dest=art/(str(i)+'.webp')
                    if not dest.exists():
                        pix=page.get_pixmap(matrix=pymupdf.Matrix(1150/max(page.rect.width,page.rect.height),1150/max(page.rect.width,page.rect.height)),alpha=False)
                        Image.frombytes('RGB',(pix.width,pix.height),pix.samples).save(dest,'WEBP',quality=71)
                toc=[(n,t,p) for n,t,p in doc.get_toc() if 1<=p<=len(doc)]
                if key=='ictc':
                    toc=[(1,t,n) for n,t in [(8,'Introduction'),(10,'Need and purpose'),(12,'Sustainability and transit-oriented development'),(14,'Transit vehicles'),(22,'On-street bus stops'),(40,'Off-street transfer stations'),(56,'Appendices and checklists')]]
                if key=='la-metro':
                    toc=[(1,t,n) for n,t in [(7,'Introduction and purpose'),(11,'Bus system design'),(15,'Bus service design guidelines'),(38,'Bus service performance evaluation'),(42,'Metro Micro'),(48,'Customer information and amenities'),(54,'Service change process')]]
                if key=='mts':
                    toc=[(1,t,n) for n,t in [(9,'Introduction'),(17,'Making transit work better for your community'),(31,'Transit-oriented communities'),(45,'Design standards for bus transit'),(63,'Development around light rail transit')]]
                groups=sorted(set([1]+[p for n,t,p in toc if n==1]))
                body.append(f'<div class="operator-book" data-pdf="{BASE}/transit-publications/{key}.pdf" data-sections="{",".join(map(str,groups))}" data-count="{len(doc)}" data-images="{BASE}/operator-pages/{key}/"><label>Page <input type="number" min="1" max="{len(doc)}" value="1"></label> of {len(doc)} <button type="button" data-turn="-1">Previous</button> <button type="button" data-turn="1">Next</button><div class="export-tools"></div><img alt="{escape(title)} · source page" src="{BASE}/operator-pages/{key}/1.webp"></div>')
                for level, title_in_book, page_no in toc:
                    if level<=2:
                        lookup.setdefault(name+' '+title_in_book,[]).append([name+' · '+title_in_book,url+'#page-'+str(page_no)])
                if toc:body+=['','## Contents','']+[f'- [{escape(t)}](#page-{p})' for n,t,p in toc if n<=2]
                body+=['','## Find a source page','']
                for i,page in enumerate(doc,1):
                    txt=' '.join(page.get_text().split())
                    label=next((t for _,t,p in reversed(toc) if p==i),f'Page {i}')
                    body.append(f'<details id="page-{i}"><summary><a href="#page-{i}">p. {i} · {escape(label)}</a></summary><p>{escape(txt)}</p></details>')
        elif key!='riverside-transit':
            body+=['','## Publisher edition','',f'[Read the complete {name} publication]({source}).']
        else:
            sections=[
                (7,'Development review','Gather the project information RTA uses to review proposed stop changes.'),
                (14,'Transit vehicle clearance','Check the design vehicle and its envelope before fixing the curb return.'),
                (15,'Bus turning movements','Review the swept path where a route turns or enters an off-street facility.'),
                (23,'Bus stop spacing and pads','Compare the stop spacing table and the concrete pad cross section.'),
                (28,'Queue jumps and signal priority','Review the relationship between a bus bypass lane and the signal operation.'),
                (31,'Bus stop signage','Check visibility for approaching operators and waiting riders.'),
                (32,'Passenger amenities and accessibility','Review the boarding area, shelter, and accessible passenger path together.'),
                (43,'Transit compatibility checklist','Use the operator checklist when coordinating development review.')]
            body+=['<section class="publisher-reader" data-publisher-pdf="'+escape(source,quote=True)+'" data-pages="52"><p>August 2015 · 52 pages</p><label>PDF page <input type="number" value="1" min="1" max="52"></label> <button type="button">View publisher page</button><div></div></section>']
            body+=['','## Review by task','','The August 2015 edition has 52 pages. Each entry opens the corresponding page in the publisher’s PDF.','']
            for n,label,summary in sections:
                chapter_id='page-'+str(n)
                body+=['<section id="'+chapter_id+'"><h3>'+escape(label)+'</h3><p>'+summary+'</p><a href="'+source+'#page='+str(n)+'">Publisher PDF · p. '+str(n)+'</a></section>']
                lookup.setdefault(name+' '+label,[]).append([name+' · '+label,url+'#'+chapter_id])

        write(root,route,name+' · '+title,'\n\n'.join(body))
        lookup[name+' transit guide']=[[name+' · '+title,url]]
        if key not in modes:modes[key]={'name':name,'roots':[],'home':url}
        modes[key]['roots'].append('/'+route+'/')
        (root/route/'index.md').open('a').write(f'\n<span hidden data-pagefind-filter="agency:{key}"></span>\n')
        if key!='octa':(root/route/'index.md').open('a').write(f'\n<button data-set-mode="{key}">Use {name} mode</button>\n')
        reg=root/'regions/index.md';s=reg.read_text();marker='id="county-'+slug(county)+'"';start=s.index(marker);end=s.index('</div>',start);reg.write_text(s[:end]+f'<a href="{url}">{name} transit guidance →</a>'+s[end:])
    write(root,'transit','Transit agency design guides','<div class="operator-directory">'+''.join(intro)+'</div>')
    save(Path('public/data/agency-modes.json'),modes)
    for topic in ('transit','accessibility','bikeways','curb-parking-loading','striping-intersections'):
        path=root/'topics'/(topic+'.md')
        s=path.read_text();position=s.find('\n## ')
        if position<0:position=len(s)
        path.write_text(s[:position]+f'\n\n[Transit operator guidance · stops, boarding and operations]({BASE}/transit/)\n\n'+s[position:])
    geo=json.loads(Path('data/reference/regional/counties.geojson').read_text())
    reg=(root/'regions/index.md').read_text()
    for f in geo['features']:
        county=f['properties']['name'];block=reg.split('id="county-'+slug(county)+'"',1)[1].split('</section>')[0]
        f['properties']['issuers']=[{'name':re.sub(r'<.*?>','',' '.join(label.split())).replace('→','').strip(),'url':u} for u,label in re.findall(r'<a href="([^"]+)">(.*?)</a>',block)]
    with (root/'regions/index.md').open('a') as out:out.write(f'\n\n[County boundaries and agencies · GeoJSON]({BASE}/api/v1/counties.geojson) · [Reference API v1]({BASE}/api/v1/index.json)\n')
    save(api/'counties.geojson',geo);save(api/'agencies.json',modes)
    books={}
    for f in sorted(Path('data/docs').glob('*.json')):
        data=json.loads(f.read_text())
        if not isinstance(data,dict):continue
        key=data.get('slug','');chapters=data.get('chapters',[])
        if chapters and (root/key/'index.md').exists():
            books[key]=[[c['title'],key+'/'+c['slug']] for c in chapters if (root/key/(c['slug']+'.md')).is_file()]
    for key in ('mutcd','ca-mutcd'):
        books[key]=[[c['code']+' · '+c['title'],key+'/'+c['code'].lower()] for c in json.loads(Path('data',key,'chapters.json').read_text()) if (root/key/(c['code'].lower()+'.md')).is_file()]
    boe=json.loads(Path('.standards/boe-navigation.json').read_text())
    books['boe/street-design']=[[v['label'],u.removeprefix(BASE+'/').rstrip('/')] for u,v in boe.items()]
    for key,items in books.items():
        if not items:continue
        for loc in [root/key/'index.md',*[root/(c+'.md') for _,c in items]]:
            s=loc.read_text();header,sep,body=s.partition('\n---\n')
            tool=f'<div class="book-reader" data-book="{key}"><a href="{BASE}/{key}/?read=1">Read continuous guide</a></div>'
            loc.write_text(header+sep+tool+'\n\n'+body)
    save(api/'guides.json',books)
    save(api/'index.json',{'version':1,'counties':'counties.geojson','agencies':'agencies.json','guides':'guides.json','coordinates':'WGS84 longitude, latitude','source':'US Census county boundaries, Plotly US counties GeoJSON distribution'})
    home=root/'index.mdx';old=home.read_text()
    search=old[old.index('<div class="home-search-wrap">'):old.index('<div class="ql-samples"')].strip()+'</div>'
    from project_photos import field_card
    from atlas_places import home_map_card
    def column(title, path, destinations, photo):
        links=''.join(f'<a href="{BASE}/{url}/">{name}</a>' for name,url in destinations)
        return (f'<section class="home-column home-lane"><h2><a href="{BASE}/{path}/">{title}</a></h2>'+
                '<nav aria-label="'+title+'">'+links+'</nav>'+field_card(photo,home=True)+'</section>')
    cols=[
        column('Guides','guides',[('California MUTCD','ca-mutcd'),('Federal MUTCD','mutcd'),
                ('Transit agency guides','transit'),('LADOT manuals','ladot')],'redondo'),
        column('Topics','topics',[('Bikeways','topics/bikeways'),('Crossings','topics/crosswalks'),
                ('Transit and boarding','topics/transit'),('Striping and intersections','topics/striping-intersections')],'venice'),
        home_map_card(BASE,Path('public/api/v2')),
    ]
    home.write_text('---\ntitle: Southern California transportation standards\ntemplate: splash\n---\n\n'+search+'\n\n<div class="home-columns">'+''.join(cols)+'</div>\n\n'+f'<nav class="home-tools"><a href="{BASE}/details/">Drawing index</a> <a href="{BASE}/signs/">Sign library</a> <a href="{BASE}/markings/">Pavement markings</a></nav>\n')
