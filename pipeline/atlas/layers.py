"""Compile the official jurisdiction polygons, state highway network and stop inventory."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import sqlite3
import gzip
import shutil
from pathlib import Path
from shapely import STRtree, points
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from sources import ABBREV, CACHE, CITY, COUNTIES, COUNTY, OUTPUT, SHN, STOPS, arc_features

def compact(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(compact(value))

def thin_polygon(geometry,simplify):
    geom=geometry.simplify(simplify,preserve_topology=True)
    def clean(coords):
        if isinstance(coords[0], (float,int)): return [round(coords[0],5),round(coords[1],5)]
        return [clean(r) for r in coords]
    raw=mapping(geom)
    return {'type':raw['type'],'coordinates':clean(raw['coordinates'])}

class Areas:
    def __init__(self):
        where='CDTFA_COUNTY IN ('+','.join("'"+name+" County'" for name in COUNTIES.values())+')'
        self.items=[]
        self.polygons=[]
        for typ,service in [('county',COUNTY),('city',CITY)]:
            features=arc_features(typ+'-boundaries',service,'CDTFA_COUNTY,CDT_NAME_SHORT,CENSUS_GEOID',where,generalize=.000015,chunk=25)
            groups=defaultdict(list)
            for f in features:
                v=f['properties'];name=v['CDT_NAME_SHORT'];county=v['CDTFA_COUNTY'].removesuffix(' County')
                polygon=shape(f['geometry'])
                groups[(str(v['CENSUS_GEOID']),name,county)].append(polygon if polygon.is_valid else polygon.buffer(0))
            for (key,name,county),parts in sorted(groups.items()):
                if not name or key=='None':raise ValueError('Jurisdiction without stable identifiers')
                geo=unary_union(parts)
                self.polygons.append(geo)
                ref=geo.representative_point()
                self.items.append(dict(id=key,name=name,county=next(k for k,v in COUNTIES.items() if v==county),
                                       kind=typ,center=[round(ref.x,5),round(ref.y,5)],bbox=[round(n,5) for n in geo.bounds]))
        self.tree=STRtree(self.polygons)
        assert len([r for r in self.items if r['kind']=='county'])==7
    def locate(self,xy):
        """Return county and place IDs for a batch, breaking ties consistently at boundary nodes."""
        hits=self.tree.query(points(xy),predicate='intersects')
        owners=[['',''] for _ in xy]
        for i,k in zip(*hits):
            v=self.items[k]; idx=int(v['kind']=='city')
            owners[i][idx]=min(owners[i][idx] or v['id'],v['id'])
        return owners
    def publish(self):
        save(OUTPUT/'places.json',self.items)
        for code in COUNTIES:
            def features(tolerance):
                return [{'type':'Feature','properties':{'id':r['id'],'name':r['name'],'kind':r['kind'],'county':code},
                         'geometry':thin_polygon(g,tolerance)} for r,g in zip(self.items,self.polygons) if r['county']==code]
            save(OUTPUT/'boundaries'/(code+'.geojson'),{'type':'FeatureCollection','features':features(.00002)})
        small=[{'type':'Feature','properties':{'id':r['id'],'name':r['name'],'county':r['county']},'geometry':thin_polygon(g,.0008)}
               for r,g in zip(self.items,self.polygons) if r['kind']=='county']
        save(OUTPUT/'counties.geojson',{'type':'FeatureCollection','features':small})

def database(filename):
    path=CACHE/'compiled'/filename;path.parent.mkdir(exist_ok=True,parents=True)
    path.unlink(missing_ok=True)
    conn=sqlite3.connect(path);conn.execute('PRAGMA journal_mode=OFF');conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA user_version=2')
    return conn,path

def publish_db(conn,path):
    conn.commit();assert conn.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    conn.close();target=OUTPUT/'db'/(path.name+'.gz');target.parent.mkdir(exist_ok=True,parents=True)
    with path.open('rb') as src,target.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,compresslevel=7,filename='') as out:
        shutil.copyfileobj(src,out)
    return {'file':'db/'+target.name,'bytes':target.stat().st_size}

def stop_rows(areas):
    features=arc_features('transit-stops',STOPS,'agency,stop_id,stop_name,route_ids_served,route_type','1=1',
                          envelope='-120.7,32.40,-114.05,35.83',chunk=800)
    features=[f for f in features if f.get('geometry')]
    locations=areas.locate([f['geometry']['coordinates'][:2] for f in features])
    groups=defaultdict(list)
    for f,(county,city) in zip(features,locations):
        if not county:continue
        x,y=f['geometry']['coordinates'][:2];p=f['properties']
        groups[county[-3:]].append((p['OBJECTID'],p['agency'],str(p['stop_id']),p['stop_name'],p['route_ids_served'],p['route_type'],x,y,city))
    return groups

def source_roads():
    where='County IN ('+','.join("'"+c+"'" for c in ABBREV)+')'
    features=arc_features('state-highways',SHN,'Route,RouteType,County,District,Direction,PMRouteID',where,generalize=.00005,chunk=70)
    by=defaultdict(list)
    for f in features:
        p=f['properties']; geom=f['geometry']
        lines=geom['coordinates'] if geom['type']=='MultiLineString' else [geom['coordinates']]
        for line in lines:
            coords=[[round(v[0],5),round(v[1],5)] for v in line]
            xs,ys=zip(*coords)
            by[ABBREV[p['County']]].append((p['OBJECTID'],p['Route'],p['RouteType'],p['Direction'],p['District'],p['PMRouteID'],
                                         min(xs),min(ys),max(xs),max(ys),compact(coords)))
    return by
