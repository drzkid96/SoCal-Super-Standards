"""Verified public inputs for the seven-county project atlas."""
import hashlib
import json
import os
import shutil
import struct
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CACHE = Path(os.getenv('SSS_ATLAS_CACHE', '.atlas-cache'))
CACHE.mkdir(parents=True, exist_ok=True)
OUTPUT = Path('public/api/v2')
COUNTIES = {'025':'Imperial','037':'Los Angeles','059':'Orange','065':'Riverside',
            '071':'San Bernardino','073':'San Diego','111':'Ventura'}
ABBREV = {'IMP':'025','LA':'037','ORA':'059','RIV':'065','SBD':'071','SD':'073','VEN':'111'}
CDT = 'https://services3.arcgis.com/uknczv4rpevve42E/arcgis/rest/services/'
CITY = CDT+'California_Cities_and_Identifiers_Blue_Version_view/FeatureServer/2'
COUNTY = CDT+'California_County_Boundaries_and_Identifiers_Blue_Version_view/FeatureServer/1'
STOPS = 'https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad/CA_Transit_Stops/FeatureServer/0'
SHN = 'https://geodata.dot.ca.gov/arcgis/rest/services/CHhighway/SHN_Postmiles/FeatureServer/0'
HPMS = 'https://www.arcgis.com/sharing/rest/content/items/5e6a977c2d7c4ec1bdc82e684d3384f2'
EDGES = 'https://www2.census.gov/geo/tiger/TIGER2025/EDGES/'
HEADERS = {'User-Agent':'SoCal Super Standards geographic index (github.com/drzkid96/SoCal-Super-Standards)'}

def get(url, headers=None, timeout=90):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={**HEADERS, **(headers or {})}), timeout=timeout) as r:
                return r.read(), r.headers
        except OSError:
            if attempt==2: raise
            time.sleep(2**attempt)

def query(layer, **params):
    result=json.loads(get(layer+'/query?'+urlencode(params))[0])
    if 'error' in result: raise ValueError(str(result['error']))
    return result

def arc_features(key, layer, fields, where, *, generalize=None, envelope=None, chunk=500):
    path=CACHE/(key+'.geojson')
    if path.exists(): return json.loads(path.read_text())['features']
    params={'where':where}
    if envelope:
        params.update(geometry=envelope, geometryType='esriGeometryEnvelope', inSR=4326, spatialRel='esriSpatialRelIntersects')
    ids=sorted(set(query(layer, **params, returnIdsOnly='true', f='json')['objectIds']))
    if not ids: raise ValueError('No features for '+key)
    def batch(start):
        requested=ids[start:start+chunk]
        options={'maxAllowableOffset':generalize} if generalize else {}
        subset=dict(params)
        subset['where']=f'({where}) AND OBJECTID BETWEEN {requested[0]} AND {requested[-1]}'
        data=query(layer, **subset,outFields='OBJECTID,'+fields,
                   outSR=4326, returnM='false',returnZ='false',geometryPrecision=6,f='geojson',**options)
        items=data.get('features',[])
        if {int(f['properties']['OBJECTID']) for f in items}!=set(requested):
            raise ValueError('Incomplete publisher response for '+key)
        return items
    with ThreadPoolExecutor(max_workers=4) as pool:
        features=[f for group in pool.map(batch,range(0,len(ids),chunk)) for f in group]
    temp=path.with_suffix('.part')
    temp.write_text(json.dumps({'type':'FeatureCollection','features':features},separators=(',',':')))
    temp.replace(path)
    print(key,len(features),flush=True)
    return features

def edges(code):
    filename='tl_2025_06'+code+'_edges.zip'
    file=CACHE/filename
    digest=json.loads(Path('data/reference/atlas/tiger-2025.json').read_text())[code]
    if not file.exists():
        data,_=get(EDGES+filename)
        if hashlib.sha256(data).hexdigest()!=digest: raise ValueError('Unexpected edition: '+filename)
        file.write_bytes(data)
    elif hashlib.sha256(file.read_bytes()).hexdigest()!=digest: raise ValueError('Damaged '+filename)
    return file

def hpms_database():
    """Range-read the release directory and California GDB members. Verify every member's CRC."""
    folder=CACHE/'HPMS2024.gdb'
    if (folder/'complete').exists(): return folder
    folder.mkdir(exist_ok=True)
    release=json.loads(Path('data/reference/atlas/hpms-2024-ca.json').read_text())
    def extract(group):
        first=group[0]['start']
        end=max(item['start']+item['compressed']+256 for item in group)
        end=min(end,release['archiveBytes'])
        data=bytearray()
        for start in range(first,end,8*1024*1024):
            last=min(end-1,start+8*1024*1024-1)
            block,head=get(HPMS+f'/data?range={start}-{last}',{'Range':f'bytes={start}-{last}','Accept-Encoding':'identity'})
            if head.get('Content-Range','').split('/')[0]!=f'bytes {start}-{last}' or len(block)!=last-start+1:
                raise ValueError('Publisher no longer serves the verified HPMS release range')
            data.extend(block)
        for item in group:
            offset=item['start']-first
            hdr=struct.unpack_from('<4s5H3L2H',data,offset)
            if hdr[0]!=b'PK\x03\x04':raise ValueError('Invalid HPMS archive header')
            begin=offset+30+hdr[-1]+hdr[-2]
            raw=data[begin:begin+item['compressed']]
            value=zlib.decompress(raw,-15) if hdr[3]==8 else raw
            if zlib.crc32(value)!=item['crc'] or len(value)!=item['size']:raise ValueError('HPMS checksum mismatch')
            (folder/item['name']).write_bytes(value)
    with ThreadPoolExecutor(3) as pool:list(pool.map(extract,release['groups']))
    (folder/'complete').touch()
    return folder
