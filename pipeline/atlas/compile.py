"""Compile small read-only SQLite databases for viewport and text queries.

Run with python pipeline/atlas/compile.py from the repository root.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
import math
import re
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path
import shapefile
from layers import Areas, compact, database, publish_db, save, source_roads, stop_rows
from sources import CACHE, CITY, COUNTIES, COUNTY, EDGES, HPMS, OUTPUT, SHN, STOPS, edges, hpms_database

def clean(s):
    return ' '.join(re.findall('[a-z0-9]+',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()))

def intersections(code, areas):
    nodes={}
    with shapefile.Reader(str(edges(code)),encoding='latin1') as shape_file:
        for record in shape_file.iterRecords(fields=['ROADFLG','MTFCC','FULLNAME','TNIDF','TNIDT']):
            if record.ROADFLG!='Y' or not record.FULLNAME or record.MTFCC not in {'S1100','S1200','S1400','S1630','S1640','S1730','S1740'}:continue
            line=shape_file.shape(record.oid)
            if not line.points:continue
            for k,point in [(record.TNIDF,line.points[0]),(record.TNIDT,line.points[-1])]:
                row=nodes.setdefault(k,(point,set()))
                row[1].add(record.FULLNAME.strip())
    nodes={k:row for k,row in nodes.items() if len(row[1])>1}
    chunks=defaultdict(list)
    source=list(nodes.items())
    for start in range(0,len(source),25000):
        batch=source[start:start+25000]
        places=areas.locate([row[0] for _,row in batch])
        for (k,(xy,roads)),(_,place) in zip(batch,places):
            x,y=round(xy[0],5),round(xy[1],5)
            chunks[(math.floor(x*5),math.floor(y*5))].append((k,x,y,place,sorted(roads)))
    membership=defaultdict(list);parts=[]
    for cell,items in sorted(chunks.items()):
        names=sorted({name for _,_,_,_,roads in items for name in roads})
        ids={name:i for i,name in enumerate(names,1)}
        conn,path=database(f'{code}-nodes-{cell[0]}_{cell[1]}.sqlite')
        conn.executescript("""
        CREATE TABLE street(id INTEGER PRIMARY KEY,name TEXT NOT NULL,search TEXT NOT NULL);
        CREATE TABLE crossing(node INTEGER PRIMARY KEY,x REAL,y REAL,place TEXT);
        CREATE TABLE approach(street INTEGER,node INTEGER,PRIMARY KEY(street,node)) WITHOUT ROWID;
        """)
        conn.executemany('INSERT INTO street VALUES(?,?,?)',[(v,k,clean(k)) for k,v in ids.items()])
        conn.executemany('INSERT INTO crossing VALUES(?,?,?,?)',(row[:4] for row in items))
        conn.executemany('INSERT INTO approach VALUES(?,?)',((ids[name],row[0]) for row in items for name in row[4]))
        conn.execute('CREATE INDEX approach_node ON approach(node,street)')
        index=len(parts)
        for name in names:membership[name].append(index)
        parts.append({**publish_db(conn,path),'places':sorted({r[3] for r in items if r[3]})})
    index_path=OUTPUT/'db'/(code+'-streets.json.gz')
    with index_path.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as out:
        out.write(compact({'parts':parts,'streets':membership}).encode())
    return {'index':'db/'+index_path.name,'bytes':index_path.stat().st_size,'crossings':len(source),'streets':len(membership)}


def local_network(code,stops,roads):
    conn,path=database(code+'-network.sqlite')
    conn.executescript("""
    CREATE TABLE stop(source_id INTEGER PRIMARY KEY,agency TEXT,stop_id TEXT,name TEXT,routes TEXT,mode TEXT,x REAL,y REAL,place TEXT);
    CREATE TABLE highway(source_id INTEGER,route INTEGER,type TEXT,direction TEXT,district INTEGER,postmile_id TEXT,w REAL,s REAL,e REAL,n REAL,line TEXT);
    """)
    conn.executemany('INSERT INTO stop VALUES(?,?,?,?,?,?,?,?,?)',stops)
    conn.executemany('INSERT INTO highway VALUES(?,?,?,?,?,?,?,?,?,?,?)',roads)
    conn.executescript('CREATE INDEX stop_xy ON stop(x,y);CREATE INDEX highway_box ON highway(w,e,s,n);')
    return {**publish_db(conn,path),'stops':len(stops),'highwayPaths':len(roads)}

def road_tiles(folder):
    # Partition the regional ownership file geographically so a point lookup downloads only neighboring data.
    sql_filter='county_id IN ('+','.join(str(int(c)) for c in COUNTIES)+') AND ownership IS NOT NULL AND ownership > 0'
    cmd=['ogr2ogr','-f','GeoJSONSeq','-select','route_id,routename,ownership,maintenance_operations,county_id,begin_point,end_point',
         '-where',sql_filter,'-simplify','0.000025','-dim','XY','-lco','COORDINATE_PRECISION=5','/vsistdout/',str(folder),'HPMS_FULL_CA_2024']
    process=subprocess.Popen(cmd,stdout=subprocess.PIPE)
    tiles={};counts=Counter()
    try:
        for line in process.stdout:
            feature=json.loads(line.strip().lstrip(b'\x1e'));p=feature['properties'];geom=feature['geometry']
            if not geom:continue
            county='%03d'%p['county_id']
            lines=geom['coordinates'] if geom['type']=='MultiLineString' else [geom['coordinates']]
            for coords in lines:
                if len(coords)<2:continue
                xs,ys=zip(*coords); w,s,e,n=min(xs),min(ys),max(xs),max(ys)
                # A tile's actual bounds include long segments extending beyond its cell.
                key=f'{math.floor((w+e)*2)}_{math.floor((s+n)*2)}'
                if key not in tiles:
                    conn,path=database('ownership-'+key+'.sqlite')
                    conn.execute('CREATE TABLE road(route_id TEXT,name TEXT,owner INTEGER,maintenance INTEGER,county TEXT,begin REAL,end REAL,w REAL,s REAL,e REAL,n REAL,line TEXT)')
                    tiles[key]=(conn,path,[w,s,e,n])
                conn,path,bounds=tiles[key]
                bounds[:]=[min(w,bounds[0]),min(s,bounds[1]),max(e,bounds[2]),max(n,bounds[3])]
                conn.execute('INSERT INTO road VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                             (p['route_id'],p.get('routename'),p['ownership'],p.get('maintenance_operations'),county,p.get('begin_point'),p.get('end_point'),w,s,e,n,compact(coords)))
                counts[county]+=1
    finally:
        process.stdout.close()
        if process.wait():raise RuntimeError('Cannot read the California HPMS layer')
    catalog=[]
    for key,(conn,path,bbox) in sorted(tiles.items()):
        conn.execute('CREATE INDEX bounds ON road(w,e,s,n)')
        catalog.append({**publish_db(conn,path),'bbox':bbox})
    if set(counts)!=set(COUNTIES):raise ValueError('Missing roadway ownership coverage')
    return catalog,counts

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    areas=Areas();areas.publish()
    stops=stop_rows(areas); highways=source_roads(); layers={}
    for code in COUNTIES:
        network=local_network(code,stops[code],highways[code])
        crossings=intersections(code,areas)
        if network['stops']==0 or network['highwayPaths']==0 or crossings['crossings']<100:raise ValueError('Incomplete county '+code)
        layers[code]={'network':network,'intersections':crossings,'name':COUNTIES[code],
                      'operators':sorted({r[1] for r in stops[code] if r[1]})}
        print(COUNTIES[code],network['stops'],'stop records;',crossings['crossings'],'crossings',flush=True)
    tiles,counts=road_tiles(hpms_database())
    for code,value in counts.items():layers[code]['ownershipPaths']=value
    # Aggregation stamp refers to the source retrieval, independent of subsequent site rebuilds.
    retrieved=datetime.fromtimestamp((CACHE/'transit-stops.geojson').stat().st_mtime,timezone.utc).date().isoformat()
    manifest={'version':2,'snapshot':retrieved,'crs':'EPSG:4326','places':'places.json','counties':'counties.geojson',
              'countyLayers':layers,'ownershipTiles':tiles,'sources':{
              'places':{'title':'CDT / CDTFA incorporated city boundaries','url':CITY},
              'counties':{'title':'CDT / CDTFA county boundaries','url':COUNTY},
              'intersections':{'title':'US Census 2025 TIGER/Line topological road nodes','url':EDGES},
              'ownership':{'title':'FHWA / BTS 2024 Highway Performance Monitoring System','url':'https://www.arcgis.com/home/item.html?id='+HPMS.split('/')[-1]},
              'transit':{'title':'Caltrans statewide GTFS stop inventory','url':STOPS},
              'highways':{'title':'Caltrans State Highway Network postmiles','url':SHN}}}
    from operator_feeds import main as identify_operators
    identify_operators()
    save(OUTPUT/'layers.json',manifest)
    print('Ownership paths:',sum(counts.values()),'in',len(tiles),'partitions',flush=True)
if __name__=='__main__':main()
