/* Geographic and text queries execute off the main thread. */
importScripts('../../vendor/atlas/sql-wasm.js', '../../vendor/atlas/fflate.js');
const api=new URL('../../api/v2/',self.location.href);
const databases=new Map(), databaseLimit=9;
let engineRequest,manifestRequest;

// A hosting service may return the gzip file or apply Content-Encoding itself.
async function readAsset(file,decode){
  const url=new URL(file,api);
  for(let attempt=0;attempt<2;attempt++){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
    let permanent=false;
    try{
      const response=await fetch(url,{signal:controller.signal,cache:attempt?'reload':'default'});
      if(!response.ok){
        permanent=response.status>=400&&response.status<500&&![408,429].includes(response.status);
        throw Error('HTTP '+response.status);
      }
      let bytes=new Uint8Array(await response.arrayBuffer());
      if(bytes[0]===0x1f&&bytes[1]===0x8b)bytes=fflate.gunzipSync(bytes);
      return decode(bytes);
    }catch(error){
      if(permanent||attempt===1)throw Error(url.pathname+': '+error.message);
    }finally{clearTimeout(timeout);}
  }
}
const jsonBytes=bytes=>JSON.parse(new TextDecoder().decode(bytes));
function getManifest(){
  manifestRequest ||= readAsset('layers.json',bytes=>{
    const m=jsonBytes(bytes);
    if(!m.countyLayers||!Array.isArray(m.ownershipTiles))throw Error('Invalid layer manifest');
    return m;
  }).catch(error=>{manifestRequest=undefined;throw error;});
  return manifestRequest;
}
function getEngine(){
  const wasm=new URL('../../vendor/atlas/sql-wasm.wasm',self.location.href);
  engineRequest ||= readAsset(wasm,bytes=>{
    if(bytes.length<8||bytes[0]!==0||bytes[1]!==97||bytes[2]!==115||bytes[3]!==109)throw Error('Invalid SQLite engine');
    return bytes;
  }).then(wasmBinary=>initSqlJs({wasmBinary})).catch(error=>{engineRequest=undefined;throw error;});
  return engineRequest;
}
function trimDatabases(){
  for(const [file,entry] of databases){
    if(databases.size<=databaseLimit)break;
    if(entry.users||!entry.db)continue;
    entry.db.close();
    databases.delete(file);
  }
}
// Protect active reads from eviction by simultaneous viewport and search queries.
async function withDatabase(file,read){
  let entry=databases.get(file);
  if(!entry){
    entry={users:0,db:null};
    const data=readAsset(file,bytes=>{
      if(new TextDecoder().decode(bytes.subarray(0,16))!=='SQLite format 3\0')throw Error('Invalid SQLite database');
      return bytes;
    });
    entry.ready=Promise.all([getEngine(),data]).then(([SQL,bytes])=>{
      entry.db=new SQL.Database(bytes);return entry.db;
    }).catch(error=>{databases.delete(file);throw error;});
  }else databases.delete(file);
  databases.set(file,entry);
  entry.users++;
  try{return read(await entry.ready);}
  finally{entry.users--;trimDatabases();}
}
function rows(db, sql, params=[]) {
  const stmt=db.prepare(sql), result=[];
  try {stmt.bind(params);while(stmt.step())result.push(stmt.getAsObject());}
  finally {stmt.free();}
  return result;
}
const normalize=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/['’]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
const short={avenue:'ave',street:'st',boulevard:'blvd',road:'rd',parkway:'pkwy',highway:'hwy',drive:'dr',court:'ct',place:'pl',lane:'ln',terrace:'ter',north:'n',south:'s',east:'e',west:'w',northeast:'ne',northwest:'nw',southeast:'se',southwest:'sw',circle:'cir',mount:'mt',center:'ctr',trail:'trl',first:'1st',second:'2nd',third:'3rd',fourth:'4th',fifth:'5th',sixth:'6th',seventh:'7th',eighth:'8th',ninth:'9th',tenth:'10th'};
const words=s=>normalize(s).split(' ').map(v=>short[v]||v).join(' ');
const streetIndexes=new Map();
function streetIndex(index){
  if(!streetIndexes.has(index))streetIndexes.set(index,readAsset(index,bytes=>JSON.parse(fflate.strFromU8(bytes)))
    .then(({parts,streets})=>({parts,streets,entries:Object.entries(streets).map(([name,tiles])=>({name,tiles,key:words(name)}))}))
    .catch(e=>{streetIndexes.delete(index);throw e;}));
  return streetIndexes.get(index);
}
function matchedStreets(index,term,place,prefix=false){
  const query=words(term);
  if(!query)return [];
  const keys=[' '+query+(prefix?'':' ')];
  if(prefix){
    const raw=normalize(term).split(' '),last=raw.pop();
    if(last.length>=2){
      const leading=raw.map(v=>short[v]||v);
      for(const [full,abbreviation] of Object.entries(short)){
        if(full.startsWith(last)&&full!==last)keys.push(' '+[...leading,abbreviation].join(' ')+' ');
      }
    }
  }
  return index.entries.filter(({key,tiles})=>keys.some(wanted=>(' '+key+' ').includes(wanted)) &&
    (!place||tiles.some(i=>index.parts[i].places.includes(place))));
}
function byTile(matches){
  const by=new Map();
  for(const {name,tiles} of matches)for(const tile of tiles){
    if(!by.has(tile))by.set(tile,[]);
    by.get(tile).push(name);
  }
  return by;
}
const marks=items=>items.map(()=>'?').join(',');
function crossingTiles(index,pair,place){
  const [left,right]=pair.map(v=>byTile(matchedStreets(index,v,place)));
  return [...left].filter(([i])=>right.has(i)&&(!place||index.parts[i].places.includes(place)))
    .map(([i,a])=>({file:index.parts[i].file,groups:[a,right.get(i)]}));
}
async function crossingPage(tiles,params){
  const {county,place,cursor}=params, results=[], start=cursor?.part||0;
  for(let i=start;i<tiles.length;i++){
    const {file,groups}=tiles[i], needed=35-results.length;
    const found=await withDatabase(file,db=>{
      // Resolve the few relevant street IDs first. Using the approach(street,node)
      // index avoids a full scan of an urban tile for each query.
      const ids=groups.map(names=>rows(db,'SELECT id FROM street WHERE name IN ('+marks(names)+')',names).map(r=>r.id));
      if(ids.some(group=>!group.length))return [];
      const other=ids[1];
      return rows(db,`SELECT DISTINCT c.node,c.x,c.y,c.place,
        (SELECT group_concat(name,' & ') FROM street JOIN approach ON street.id=approach.street WHERE approach.node=c.node) AS label
        FROM approach a JOIN crossing c ON c.node=a.node
        WHERE a.street IN (${marks(ids[0])}) AND c.node>?
        ${other?'AND EXISTS(SELECT 1 FROM approach b WHERE b.node=c.node AND b.street!=a.street AND b.street IN ('+marks(other)+'))':''}
        ${place?'AND c.place=?':''} ORDER BY c.node LIMIT ?`,
        [...ids[0],i===start&&cursor?cursor.after:0,...(other||[]),...(place?[place]:[]),needed+1]);
    });
    results.push(...found.slice(0,needed).map(r=>({...r,county,type:'Intersection'})));
    if(found.length>needed || results.length===35 && i+1<tiles.length){
      results.push({label:'Find more intersections',more:{...params,cursor:{part:i,after:results.at(-1).node}}});
      break;
    }
  }
  return results;
}
async function streetMatches(index,query,county,place){
  const term=words(query);
  const ordered=matchedStreets(index,query,place,true).sort((a,b)=>
    Number(b.key===term)-Number(a.key===term)||
    Number((' '+b.key+' ').includes(' '+term+' '))-Number((' '+a.key+' ').includes(' '+term+' '))||
    a.name.length-b.name.length||a.name.localeCompare(b.name));
  const names=[];
  // Tile membership accelerates discovery, but only a matching crossing proves
  // that a street belongs to a selected municipality.
  if(place){
    for(let n=0;n<ordered.length && names.length<12;n+=24){
      const batch=ordered.slice(n,n+24), verified=new Set();
      for(const [i,candidates] of byTile(batch)){
        if(!index.parts[i].places.includes(place))continue;
        const remaining=candidates.filter(v=>!verified.has(v));
        if(!remaining.length)continue;
        const rowsHere=await withDatabase(index.parts[i].file,db=>rows(db,`SELECT s.name FROM street s WHERE s.name IN (${marks(remaining)}) AND EXISTS (
          SELECT 1 FROM approach a JOIN crossing c ON a.node=c.node WHERE a.street=s.id AND c.place=?)`,[...remaining,place]));
        for(const row of rowsHere)verified.add(row.name);
      }
      names.push(...batch.filter(entry=>verified.has(entry.name)));
    }
  }else names.push(...ordered.slice(0,12));
  return names.slice(0,12).map(({name,key})=>({street:name,label:name,county,place,type:'Street',exact:key===term}));
}
async function stopMatches(file,query,county,place,agencyNames){
  const tokens=normalize(query).split(' ').filter(Boolean);
  if(!tokens.length)return [];
  const conditions=tokens.map(()=>"lower(coalesce(name,'') || ' ' || coalesce(stop_id,'') || ' ' || coalesce(agency,'')) LIKE ?");
  const params=tokens.map(t=>'%'+t+'%');
  if(place){conditions.push('place=?');params.push(place);}
  if(agencyNames?.length){
    conditions.push('('+agencyNames.map(()=>'lower(agency) LIKE ?').join(' OR ')+')');
    params.push(...agencyNames.map(a=>'%'+a.toLowerCase()+'%'));
  }
  return withDatabase(file,db=>rows(db,`SELECT source_id,name AS label,x,y,place,agency,stop_id FROM stop WHERE ${conditions.join(' AND ')}
    ORDER BY lower(stop_id)=lower(?) DESC, lower(name)=lower(?) DESC, length(name), name, agency, stop_id LIMIT 36`,
    [...params,query,query]).map(r=>({...r,county,type:'Transit stop',exact:normalize(r.label)===normalize(query)||normalize(r.stop_id)===normalize(query)})));
}
async function search({query,county,place,pair,mode,agencyNames,cursor}){
  const data=(await getManifest()).countyLayers[county];
  if(!data)throw Error('County index unavailable');
  if(mode==='stops')return stopMatches(data.network.file,query,county,place,agencyNames);
  const index=await streetIndex(data.intersections.index);
  if(!pair&&!mode){
    const split=query.split(/\s*(?:&|@|\/)\s*|\s+(?:and|at)\s+/i);
    if(split.length===2&&split.every(s=>s.trim()))pair=split;
  }
  if(pair){
    if(words(pair[0])===words(pair[1]))return [];
    const tiles=crossingTiles(index,pair,place);
    if(mode==='candidates')return tiles.length?[{county,type:'County candidate'}]:[];
    return crossingPage(tiles,{query,county,place,pair,mode:'crossings',cursor});
  }
  const streets=await streetMatches(index,query,county,place);
  if(mode==='streets')return streets;
  return [...streets,...await stopMatches(data.network.file,query,county,place,agencyNames)];
}
async function onStreet({street,county,place,cursor}){
  const data=(await getManifest()).countyLayers[county];
  if(!data)throw Error('County index unavailable');
  const index=await streetIndex(data.intersections.index);
  const tiles=(index.streets[street]||[]).filter(i=>!place||index.parts[i].places.includes(place))
    .map(i=>({file:index.parts[i].file,groups:[[street]]}));
  return crossingPage(tiles,{street,county,place,cursor});
}
const overlap=(a,b)=>a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];
function metric(x,y){
  const xm=111320*Math.cos(y*Math.PI/180), ym=110900;
  return {box:r=>[x-r/xm,y-r/ym,x+r/xm,y+r/ym],
    distance:(a,b)=>Math.hypot((a-x)*xm,(b-y)*ym),
    line(line){
      let best=Infinity;
      for(let i=1;i<line.length;i++){
        const ax=(line[i-1][0]-x)*xm,ay=(line[i-1][1]-y)*ym,dx=(line[i][0]-line[i-1][0])*xm,dy=(line[i][1]-line[i-1][1])*ym;
        const t=Math.min(1,Math.max(0,-(ax*dx+ay*dy)/(dx*dx+dy*dy||1)));
        best=Math.min(best,Math.hypot(ax+t*dx,ay+t*dy));
      }
      return best;
    }};
}
function nearbyLines(db,table,box) {
  return rows(db,'SELECT * FROM '+table+' WHERE w<=? AND e>=? AND s<=? AND n>=?',[box[2],box[0],box[3],box[1]]);
}
function fillNearby(result,records,geo,radius){
  for(const record of records){
    record.line=JSON.parse(record.line);
    record.distance=geo.line(record.line);
    if(record.distance<=radius)result.push(record);
  }
}
function nearestUnique(records,key){
  records.sort((a,b)=>a.distance-b.distance);
  const seen=new Set();
  return records.filter(record=>{
    const id=key(record);
    if(seen.has(id))return false;
    seen.add(id);return true;
  });
}
let localStreets;
async function roadContext(layer,box,geo){
  if(!layer||!overlap(layer.bbox,box))return [];
  const readStreets=file=>readAsset(file,bytes=>{
    const collection=jsonBytes(bytes);
    if(!Array.isArray(collection.features))throw Error('Invalid street inventory');
    return collection.features.map(f=>{
      const line=f.geometry.coordinates,bounds=[Infinity,Infinity,-Infinity,-Infinity];
      for(const [x,y] of line){
        bounds[0]=Math.min(bounds[0],x);bounds[1]=Math.min(bounds[1],y);
        bounds[2]=Math.max(bounds[2],x);bounds[3]=Math.max(bounds[3],y);
      }
      return {...f.properties,id:f.id,source:layer.sources[f.properties.source],line,bounds};
    });
  });
  localStreets ||= (layer.compressedFile
    ? readStreets(layer.compressedFile).catch(()=>readStreets(layer.file))
    : readStreets(layer.file)
  ).catch(error=>{localStreets=undefined;throw error;});
  const matches=[];
  for(const r of await localStreets){
    if(!overlap(box,r.bounds))continue;
    const distance=geo.line(r.line);
    if(distance<=40)matches.push({...r,distance});
  }
  return matches.sort((a,b)=>a.distance-b.distance);
}
async function attemptLayer(unavailable,label,task){
  try{await task();}
  catch{unavailable.add(label);}
}
async function identify({x,y,counties}){
  const m=await getManifest(),geo=metric(x,y),stopBox=geo.box(400),roadBox=geo.box(40);
  const stops=[],highways=[],roads=[],unavailable=new Set(),tasks=[];
  let context=[];
  for(const code of new Set(counties)){
    const county=m.countyLayers[code];
    if(!county)continue;
    tasks.push(attemptLayer(unavailable,county.name+' County stops and state highways',()=>
      withDatabase(county.network.file,db=>{
        const found=rows(db,'SELECT * FROM stop WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ?',
          [stopBox[0],stopBox[2],stopBox[1],stopBox[3]]);
        for(const stop of found){
          stop.distance=geo.distance(stop.x,stop.y);
          if(stop.distance<=400)stops.push(stop);
        }
        fillNearby(highways,nearbyLines(db,'highway',roadBox),geo,40);
      })
    ));
  }
  for(const tile of m.ownershipTiles){
    if(!overlap(tile.bbox,roadBox))continue;
    tasks.push(attemptLayer(unavailable,'FHWA road ownership',()=>
      withDatabase(tile.file,db=>fillNearby(roads,nearbyLines(db,'road',roadBox),geo,40))
    ));
  }
  tasks.push(attemptLayer(unavailable,'Local road records',async()=>{
    context=await roadContext(m.roadContext,roadBox,geo);
  }));
  await Promise.all(tasks);
  return {
    stops:nearestUnique(stops,p=>[p.agency,p.stop_id,p.x,p.y].join('|')),
    roads:nearestUnique(roads,p=>[p.county,p.route_id,p.owner,p.begin,p.end].join('|')),
    highways:nearestUnique(highways,p=>[p.route,p.direction,p.district].join('|')),
    roadContext:context,unavailable:[...unavailable].sort()
  };
}
async function visible({bounds,counties,zoom,stops,highways}){
  const result={stops:[],highways:[],limited:false,unavailable:[]};
  const showStops=stops&&zoom>=14,showHighways=highways&&zoom>=10;
  if(!showStops&&!showHighways)return result;
  const m=await getManifest(),unavailable=new Set();
  await Promise.all([...new Set(counties)].map(code=>{
    const county=m.countyLayers[code];
    if(!county)return;
    return attemptLayer(unavailable,county.name+' County network',()=>withDatabase(county.network.file,db=>{
      if(showStops){
        const found=rows(db,'SELECT source_id,x,y,name,agency,place FROM stop WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? ORDER BY source_id LIMIT 751',
          [bounds[0],bounds[2],bounds[1],bounds[3]]);
        result.limited ||= found.length>750;
        result.stops.push(...found.slice(0,750));
      }
      if(showHighways)for(const h of nearbyLines(db,'highway',bounds))
        result.highways.push({line:JSON.parse(h.line),route:h.route});
    }));
  }));
  result.unavailable=[...unavailable].sort();
  return result;
}
const operations={search,onStreet,identify,visible};
self.onmessage=async({data:{id,method,params}})=>{
  try{
    if(!Object.hasOwn(operations,method))throw Error('Unknown map operation');
    self.postMessage({id,value:await operations[method](params)});
  }
  catch(e){self.postMessage({id,error:e.message});}
};
