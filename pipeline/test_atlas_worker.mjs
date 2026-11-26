/** Exercise the shipped worker against SQLite, gzip, and recoverable partial network failures. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as fflate from 'fflate';
import initSqlJs from 'sql.js';

const bytes=file=>fs.readFileSync(file);
const wasm=bytes('node_modules/sql.js/dist/sql-wasm.wasm');
const SQL=await initSqlJs({wasmBinary:wasm});
const sql=file=>{
  const db=new SQL.Database();
  try{db.run(file);return db.export();}
  finally{db.close();}
};
const network=sql(`
  CREATE TABLE stop(source_id INTEGER,agency TEXT,stop_id TEXT,name TEXT,routes TEXT,x REAL,y REAL,place TEXT);
  WITH RECURSIVE n(i) AS (VALUES(1) UNION ALL SELECT i+1 FROM n WHERE i<753)
  INSERT INTO stop SELECT i,'Test agency',i,'Test stop','1',-118,34,'city' FROM n;
  CREATE TABLE highway(route INTEGER,direction TEXT,district INTEGER,w REAL,s REAL,e REAL,n REAL,line TEXT);
  INSERT INTO highway VALUES(1,'NB',7,-118.001,34,-117.999,34,'[[-118.001,34],[-117.999,34]]');
`);
const road=sql(`
  CREATE TABLE road(route_id TEXT,owner INTEGER,county TEXT,begin REAL,end REAL,w REAL,s REAL,e REAL,n REAL,line TEXT);
  INSERT INTO road VALUES('1',1,'A',0,1,-118.001,34,-117.999,34,'[[-118.001,34],[-117.999,34]]');
  INSERT INTO road VALUES('1',1,'A',1,2,-118,34,-118,34.001,'[[-118,34],[-118,34.001]]');
`);
const box=[-118.01,33.99,-117.99,34.01];
const countyLayers=Object.fromEntries(Array.from({length:12},(_,i)=>['c'+i,{name:'Test '+i,network:{file:'db/c'+i+'.gz'}}]));
const contextSource={title:'Municipal inventory',url:'https://example.org/roads'};
const manifest={countyLayers,ownershipTiles:[{bbox:box,file:'db/road.gz'}],
  roadContext:{bbox:box,file:'streets.geojson',compressedFile:'streets.geojson.gz',sources:{test:contextSource}}};
const feature={type:'Feature',id:'street-a',properties:{source:'test',name:'Street A',agency:'Test City',role:'inventory',ref:'123'},
  geometry:{type:'LineString',coordinates:[[-118.001,34],[-117.999,34]]}};
const encoder=new TextEncoder();
const payload=new Map([
  ['layers.json',encoder.encode(JSON.stringify(manifest))],
  ['sql-wasm.wasm',wasm],['road.gz',fflate.gzipSync(road)],
  ['streets.geojson.gz',fflate.gzipSync(encoder.encode(JSON.stringify({type:'FeatureCollection',features:[feature]})))]
]);
for(let i=0;i<12;i++)payload.set('c'+i+'.gz',i%2?network:fflate.gzipSync(network));
const failures=new Map(),calls=new Map();
async function fetchFixture(url){
  const file=new URL(url).pathname.split('/').pop();
  calls.set(file,(calls.get(file)||0)+1);
  const errors=failures.get(file);
  if(errors?.length)return new Response('data unavailable',{status:errors.shift()});
  return new Response(payload.get(file),{status:payload.has(file)?200:404});
}
function fixture(){
  const self={location:{href:'https://example.org/project/js/atlas/worker.js'}};
  const runtime=vm.createContext({self,URL,TextDecoder,AbortController,setTimeout,clearTimeout,
    Uint8Array,fetch:fetchFixture,importScripts(){},initSqlJs,fflate});
  vm.runInContext(bytes('public/js/atlas/worker.js').toString(),runtime);
  // Evaluate in the worker realm so no DB handle is accessed directly.
  return (method,params)=>vm.runInContext(method+'('+JSON.stringify(params)+')',runtime);
}
const identify={x:-118,y:34,counties:['c0']};
const viewport={bounds:box,counties:Object.keys(countyLayers),zoom:15,stops:true,highways:true};
const run=fixture();
await run('visible',{...viewport,zoom:5});
assert.equal(calls.size,0);
failures.set('layers.json',[503,503]);
await assert.rejects(run('identify',identify),/HTTP 503/);
failures.set('c0.gz',[503,503]);
const partial=await run('identify',identify);
assert.equal(partial.roads.length,2,'Preserve distinct approach segments sharing an HPMS route and owner.');
assert.equal(partial.stops.length,0);
assert.match(partial.unavailable.join(),/stops/);
assert.equal(partial.roadContext[0].source.url,contextSource.url);
assert.equal(partial.roadContext[0].distance,0);
assert.equal(calls.get('streets.geojson.gz'),1);
assert.equal(calls.has('streets.geojson'),false);
const restored=await run('identify',identify);
assert.equal(restored.stops.length,753);
assert.equal(restored.highways.length,1);
assert.equal(restored.unavailable.length,0);
failures.set('c5.gz',[404]);
const visible=await run('visible',viewport);
assert.equal(visible.highways.length,11);
assert.equal(visible.stops.length,11*750);
assert.equal(visible.limited,true);
assert.match(visible.unavailable.join(),/Test 5 County network/);
const all=await run('visible',viewport);
assert.equal(all.stops.length,12*750);
assert.equal(all.unavailable.length,0);
const rawInventory=encoder.encode(JSON.stringify({type:'FeatureCollection',features:[feature]}));
payload.set('streets.geojson',rawInventory);
failures.set('streets.geojson.gz',[404]);
const rawFallback=await fixture()('identify',identify);
assert.equal(rawFallback.roadContext[0].name,'Street A');
assert.equal(calls.get('streets.geojson'),1);
const fresh=fixture();
failures.set('road.gz',[404]);failures.set('streets.geojson.gz',[404]);failures.set('streets.geojson',[404]);
const unavailable=await fresh('identify',identify);
assert.equal(unavailable.stops.length,753);
assert.equal(unavailable.highways.length,1);
assert.equal(unavailable.roads.length,0);
assert.equal(unavailable.roadContext.length,0);
assert.equal(unavailable.unavailable.length,2);
console.log('Atlas worker passed gzip and decoded SQLite, concurrent eviction, manifest/network recovery, partial ownership and stop coverage, true overlay cap, and independent municipal evidence.');
