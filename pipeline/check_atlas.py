"""Check the published jurisdiction profiles, route identities and linked database as one release."""
import gzip
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

BASE='/SoCal-Super-Standards/'
ROOT=Path('dist')
API=ROOT/'api/v2'

def read(path):return json.loads(path.read_text())
def open_db(path):
    conn=sqlite3.connect(':memory:')
    conn.deserialize(gzip.decompress(path.read_bytes()))
    if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError(path)
    return conn

def verify():
    from lxml import html
    profiles=read(API/'profiles.json');m=read(API/'layers.json');places=read(API/'places.json')
    cities={v['id']:v for v in places if v['kind']=='city'}
    assert all(urlsplit(v['official']).scheme=='https' and urlsplit(v['directorySource']).scheme=='https' for v in cities.values())
    directory=html.parse(str(ROOT/'regions/index.html'))
    links={v.rsplit('=',1)[-1] for v in directory.xpath('//a/@href') if v.startswith(BASE+'map/?city=')}
    assert links==set(cities),'The fallback agency directory must include every mapped municipality'
    counties=m['countyLayers']
    assert set(counties)=={'025','037','059','065','071','073','111'}
    assert set(counties)=={v['county'] for v in profiles.values() if v['kind']=='County public works'}
    assert all(v['place'] for v in profiles.values() if v['kind'] in ('City','Municipal agency'))
    indexed=0;expected=['Publications and drawings','Review by topic','Find a reference','Project coordination','Publisher and coverage']
    for key,p in profiles.items():
        if not p['official'].startswith('https://'):raise AssertionError(key+' publisher')
        file=ROOT/p['home'].removeprefix(BASE)/'index.html'
        doc=html.parse(str(file));article=doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," sl-markdown-content ")]')[0]
        sections=[h.xpath('normalize-space(string(.))') for h in article.xpath('./h2|./div/h2')]
        assert all(any(h in s for s in sections) for h in expected),(key,sections)
        assert article.xpath('.//*[@data-agency=$k]',k=key) and article.xpath('.//a[contains(@href,$u)]',u='?issuer='+key),key
        assert p['publications'] and p['referenceCount']>0 and p['topics'],key
        for group in [p['publications'],*[refs for refs in p['topics'].values()]]:
            for ref in group:
                target=urlsplit(ref['url'])
                assert target.path.startswith(BASE) and (ROOT/target.path.removeprefix(BASE)/'index.html').exists(),ref
                indexed+=1
    assert not any('s-714/' in r['url'] for r in profiles['pasadena']['topics'].get('transit',[]))
    assert any('s-709/' in r['url'] for r in profiles['pasadena']['topics']['crosswalks'])
    with open_db(API/'db/site.sqlite.gz') as db:
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('SELECT count(*) FROM agency').fetchone()[0]==len(profiles)
        for k,p in profiles.items():
            assert db.execute('SELECT count(*) FROM agency_reference WHERE agency=?',(k,)).fetchone()[0]==p['referenceCount']
        refs=db.execute('SELECT count(*) FROM reference').fetchone()[0]
    for code,v in counties.items():
        with open_db(API/v['network']['file']) as db:
            assert db.execute('SELECT count(*) FROM stop').fetchone()[0]==v['network']['stops']
        inventory=json.loads(gzip.decompress((API/v['intersections']['index']).read_bytes()))
        assert all((API/c['file']).is_file() for c in inventory['parts']) and inventory['streets']
        assert len(read(API/'boundaries'/(code+'.geojson'))['features'])==sum(p['county']==code for p in places)
    pages=0
    for f in ROOT.rglob('*.html'):
        if f in (ROOT/'index.html',ROOT/'404.html'):continue
        raw=f.read_text()
        if re.search(r'<meta[^>]*http-equiv=["\']?refresh',raw,re.I):continue
        assert raw.count('data-section-identity=')==1,f
        pages+=1
    assert '/vendor/atlas/leaflet.js' not in (ROOT/'index.html').read_text()
    print(f'{pages:,} section identities; {len(profiles)} authority profiles; {refs:,} indexed reference URLs; {indexed:,} publication and topic links; 7 geographic databases verified.')

if __name__=='__main__':verify()
