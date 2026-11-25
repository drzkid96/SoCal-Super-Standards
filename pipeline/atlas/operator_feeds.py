"""Resolve a multi-operator statewide stop record against its publisher's native GTFS."""
import csv
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import zipfile
from sources import CACHE, OUTPUT, get

FEEDS={'mts':('https://www.sdmts.com/google_transit_files/google_transit.zip','San Diego Metropolitan Transit System, Airport, Flagship Cruises'),
       'ventura':('https://govcbus.com/gtfs','Ventura County (VCTC, Gold Coast, Cities of Camarillo, Moorpark, Ojai, Simi Valley, Thousand Oaks)')}
def main():
    inventory=json.loads((CACHE/'transit-stops.geojson').read_text())['features']
    records={};sources=[]
    for key,(url,group) in FEEDS.items():
        path=CACHE/(key+'-gtfs.zip')
        if not path.exists():path.write_bytes(get(url)[0])
        data=path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            def table(name):
                with z.open(name+'.txt') as f:yield from csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
            agencies={r['agency_id']:r['agency_name'] for r in table('agency')}
            if key=='mts' and agencies.get('MTS')=='MTS':agencies['MTS']='San Diego Metropolitan Transit System'
            routes={r['route_id']:agencies[r['agency_id']] for r in table('routes')}
            trips={t['trip_id']:t['route_id'] for t in table('trips')}
            points={r['stop_id']:(float(r['stop_lon']),float(r['stop_lat'])) for r in table('stops') if r['stop_lon'] and r['stop_lat']}
            served=defaultdict(set)
            for item in table('stop_times'):
                if item['trip_id'] in trips:served[item['stop_id']].add(trips[item['trip_id']])
        matched=0
        for feat in inventory:
            a=feat['properties'];sid=str(a['stop_id'])
            if a['agency']!=group or sid not in points or not feat.get('geometry'):continue
            x,y=feat['geometry']['coordinates'][:2];xx,yy=points[sid]
            if (x-xx)**2+(y-yy)**2>.0004**2:continue
            reported={v.strip() for v in str(a.get('route_ids_served') or '').split(',') if v.strip()}
            if not reported or not reported.issubset(served[sid]) or not reported.issubset(routes):continue
            operators=defaultdict(list)
            for route in sorted(reported):operators[routes[route]].append(route)
            records[str(a['OBJECTID'])]=dict(operators);matched+=1
        sources.append(dict(url=url,group=group,sha256=hashlib.sha256(data).hexdigest(),matched=matched))
    payload={'sources':sources,'stops':records}
    path=OUTPUT/'stop-operators.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    print([(s['group'],s['matched']) for s in sources])
if __name__=='__main__':main()
