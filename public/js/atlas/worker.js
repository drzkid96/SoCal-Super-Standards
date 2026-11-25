/* Spatial and text queries run off the UI thread. Databases are fetched by county or road tile. */
importScripts('../../vendor/atlas/sql-wasm.js', '../../vendor/atlas/fflate.js');
const api = new URL('../../api/v2/', self.location.href);
const engine = initSqlJs({locateFile: () => new URL('../../vendor/atlas/sql-wasm.wasm', self.location.href).href});
const manifest = fetch(new URL('layers.json', api)).then(checked).then(r=>r.json());
const cached = new Map();
const pending = new Map();
function checked(response) {
  if (!response.ok) throw Error('Could not load '+new URL(response.url).pathname);
  return response;
}
async function database(file) {
  if (cached.has(file)) {
    const db=cached.get(file); cached.delete(file); cached.set(file,db); return db;
  }
  if (!pending.has(file)) pending.set(file,(async()=>{
    const r=checked(await fetch(new URL(file,api)));
    const bytes=fflate.gunzipSync(new Uint8Array(await r.arrayBuffer()));
    const db=new (await engine).Database(bytes);
    cached.set(file,db);
    while (cached.size>9) {const oldest=cached.keys().next().value;cached.get(oldest).close();cached.delete(oldest);}
    return db;
  })().finally(()=>pending.delete(file)));
  return pending.get(file);
}
function rows(db, sql, params=[]) {
  const stmt=db.prepare(sql), result=[];
  try {stmt.bind(params);while(stmt.step())result.push(stmt.getAsObject());}
  finally {stmt.free();}
  return result;
}
const normalize=s=>s.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const short={avenue:'ave',street:'st',boulevard:'blvd',road:'rd',parkway:'pkwy',highway:'hwy',drive:'dr',court:'ct',place:'pl',lane:'ln',terrace:'ter',north:'n',south:'s',east:'e',west:'w',circle:'cir',mount:'mt',center:'ctr'};
const words=s=>normalize(s).split(' ').map(v=>short[v]||v).join(' ');
function streetIds(db,query) {
  const term=words(query);
  if(!term)return [];
  const distinctive=term.split(' ').filter(w=>!Object.values(short).includes(w)).sort((a,b)=>b.length-a.length)[0]||term;
  return rows(db,'SELECT id,name FROM street WHERE search LIKE ?',['%'+distinctive+'%'])
    .filter(r=>(' '+words(r.name)+' ').includes(' '+term+' ')).map(r=>r.id);
}
const streetIndexes=new Map();
function streetIndex(index){
  if(!streetIndexes.has(index))streetIndexes.set(index,fetch(new URL(index,api)).then(checked).then(r=>r.arrayBuffer())
    .then(b=>JSON.parse(fflate.strFromU8(fflate.gunzipSync(new Uint8Array(b))))).catch(e=>{streetIndexes.delete(index);throw e;}));
  return streetIndexes.get(index);
}
async function crossingParts(index,pair,place){
  const {parts,streets}=await streetIndex(index);
  const groups=pair.map(q=>{const wanted=' '+words(q)+' ',indexes=new Set();
    for(const [name,ids] of Object.entries(streets))if((' '+words(name)+' ').includes(wanted))ids.forEach(i=>indexes.add(i));
    return indexes;});
  return [...groups[0]].filter(i=>groups[1].has(i)&&(!place||parts[i].places.includes(place))).map(i=>parts[i].file);
}
async function search({query,county,place}) {
  const data=(await manifest).countyLayers[county];
  if(!data)return [];
  const pair=query.split(/\s*(?:&|@|\/)\s*|\s+(?:and|at)\s+/i);
  if(pair.length===2 && pair.every(v=>v.trim())){
    const matches=[];
    for(const file of await crossingParts(data.intersections.index,pair,place)){
    const db=await database(file);
    const [a,b]=pair.map(q=>streetIds(db,q));
    if(!a.length||!b.length)continue;
    const qs=ids=>ids.map(()=>'?').join(',');
    const querySql=`SELECT DISTINCT c.node,c.x,c.y,c.place,
      (SELECT group_concat(name,' & ') FROM street JOIN approach ON street.id=approach.street WHERE approach.node=c.node) AS label
      FROM approach a JOIN approach b ON b.node=a.node AND b.street!=a.street JOIN crossing c ON c.node=a.node
      WHERE a.street IN (${qs(a)}) AND b.street IN (${qs(b)}) ${place?'AND c.place=?':''} ORDER BY c.node LIMIT 35`;
    matches.push(...rows(db,querySql,[...a,...b,...(place?[place]:[])]).map(r=>({...r,type:'Intersection'})));
    if(matches.length>=35)break;
    }
    return matches.slice(0,35);
  }
  const db=await database(data.network.file);
  const tokens=normalize(query).split(' ').filter(Boolean).slice(0,8);
  if(!tokens.length)return [];
  const condition=tokens.map(()=>'lower(name || \' \' || stop_id || \' \' || agency) LIKE ?').join(' AND ');
  const {parts,streets}=await streetIndex(data.intersections.index);
  const queryWords=words(query);
  const roadMatches=Object.entries(streets).filter(([n,ids])=>(' '+words(n)+' ').includes(' '+queryWords+' ') && (!place||ids.some(i=>parts[i].places.includes(place))))
    .sort(([a],[b])=>Number(words(b)===queryWords)-Number(words(a)===queryWords)||a.length-b.length||a.localeCompare(b))
    .slice(0,10).map(([street])=>({street,label:street,type:'Street · browse intersections',place}));
  const stops=rows(db,'SELECT name AS label,x,y,place,agency,stop_id FROM stop WHERE '+condition+
    (place?' AND place=?':'')+' ORDER BY name,agency,stop_id LIMIT 35',
    [...tokens.map(t=>'%'+t+'%'),...(place?[place]:[])]).map(r=>({...r,type:'Transit stop'}));
  return [...roadMatches,...stops];
}
async function onStreet({street,county,place}){
  const d=(await manifest).countyLayers[county];
  const {parts,streets}=await streetIndex(d.intersections.index);
  const hits=[];
  for(const i of streets[street]||[]){
    if(place&&!parts[i].places.includes(place))continue;
    const db=await database(parts[i].file);
    hits.push(...rows(db,`SELECT c.node,c.x,c.y,c.place,
      (SELECT group_concat(name,' & ') FROM street JOIN approach ON street.id=approach.street WHERE approach.node=c.node) AS label
      FROM crossing c JOIN approach a ON c.node=a.node JOIN street s ON a.street=s.id
      WHERE s.name=? ${place?'AND c.place=?':''} ORDER BY c.node LIMIT 35`,place?[street,place]:[street]).map(r=>({...r,type:'Intersection'})));
    if(hits.length>=35)break;
  }
  return hits.slice(0,35);
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
async function identify({x,y,counties}){
  const m=await manifest,geo=metric(x,y),sb=geo.box(400),rb=geo.box(40);
  const stops=[],highways=[],roads=[];
  for(const code of counties){
    const network=await database(m.countyLayers[code].network.file);
    for(const p of rows(network,'SELECT * FROM stop WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ?',[sb[0],sb[2],sb[1],sb[3]])){
      p.distance=geo.distance(p.x,p.y);if(p.distance<=400)stops.push(p);
    }
    for(const p of nearbyLines(network,'highway',rb)){
      p.line=JSON.parse(p.line);p.distance=geo.line(p.line);if(p.distance<=40)highways.push(p);
    }
  }
  for(const tile of m.ownershipTiles.filter(t=>overlap(t.bbox,rb))){
    const db=await database(tile.file);
    for(const r of nearbyLines(db,'road',rb)){
      r.line=JSON.parse(r.line);r.distance=geo.line(r.line);if(r.distance<=40)roads.push(r);
    }
  }
  const byDistance=(a,b)=>a.distance-b.distance;
  const unique=(arr,key)=>[...arr.sort(byDistance).reduce((acc,v)=>acc.has(key(v))?acc:acc.set(key(v),v),new Map()).values()];
  return {stops:unique(stops,p=>p.agency+'|'+p.stop_id+'|'+p.x+'|'+p.y),roads:unique(roads,p=>p.route_id+'|'+p.owner),highways:unique(highways,p=>p.route+'|'+p.direction)};
}
async function visible({bounds,counties,zoom,stops,highways}){
  const m=await manifest,result={stops:[],highways:[]};
  for(const code of counties){
    const db=await database(m.countyLayers[code].network.file);
    if(stops && zoom>=14)result.stops.push(...rows(db,'SELECT source_id,x,y,name,agency,place FROM stop WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? ORDER BY source_id LIMIT 750',[bounds[0],bounds[2],bounds[1],bounds[3]]));
    if(highways && zoom>=10)result.highways.push(...nearbyLines(db,'highway',bounds).map(p=>({line:JSON.parse(p.line),route:p.route})));
  }
  return result;
}
const operations={search,onStreet,identify,visible};
self.onmessage=async({data:{id,method,params}})=>{
  try{self.postMessage({id,value:await operations[method](params)});}
  catch(e){self.postMessage({id,error:e.message});}
};
