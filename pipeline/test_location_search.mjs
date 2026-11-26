// Run from the repository with node pipeline/test_location_search.mjs after building the geographic API.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import initSqlJs from 'sql.js';
import * as fflate from 'fflate';
import {groupCrossingPoints,makePlaceSearch} from '../public/js/atlas/location-query.js';

const publicURL=new URL('../public/',import.meta.url);
const fromPublic=path=>readFile(new URL(path,publicURL));
const places=JSON.parse(await fromPublic('api/v2/places.json'));
const {parse,suggestions}=makePlaceSearch(places);
for(const input of ['Ventura','San Buenaventura','Ventura (San Buenaventura)','San Buenaventura (Ventura)'])
  assert.equal(parse(input).area.id,'0665042',input);
assert.equal(makePlaceSearch([{kind:'city',name:'San Buenaventura (Ventura)',id:'0665042'}]).parse('Ventura').area.id,'0665042');
assert.equal(parse('Orange').area.kind,'city');
assert.equal(parse('OC').area.kind,'county');
assert.equal(parse('Orange County, California').area.county,'059');
assert.equal(parse('City of La Canada Flintridge, CA').area.name,'La Cañada Flintridge');
assert.equal(parse('San Diego, Los Angeles County').error,'The named location and county do not match.');
assert.equal(parse('Bad St, Unknownville').error.includes('not found'),true);
assert.equal(parse('Holly Street and Arroyo Parkway, Pasadena, Los Angeles County, CA 91103').localCity.id,'0656000');
assert.equal(parse('Holly & Arroyo, Los Angeles County').localCounty.county,'037');
assert.deepEqual(parse('34.148, -118.147'),{x:-118.147,y:34.148});
assert.deepEqual(parse('-118.147 34.148'),{x:-118.147,y:34.148});
assert.ok(parse('94, -118').error);
assert.ok(parse('Main &').error);
assert.ok(parse('Main & Main').error);
assert.equal(parse('stop: Vermont / Santa Monica').pair,null);
assert.equal(parse('Park and Ride, OC').pair,null);
assert.ok(suggestions('La Cañada',()=>true).some(v=>v.name==='La Cañada Flintridge'));

const reads=[];
let id=0;
const requests=new Map();
const workerURL=new URL('js/atlas/worker.js',publicURL);
const context={URL,AbortController,setTimeout,clearTimeout,TextDecoder,Uint8Array,fflate,initSqlJs,importScripts(){},
  fetch:async url=>{
    reads.push(fileURLToPath(url));
    return new Response(await readFile(url));
  },self:{location:{href:workerURL.href},postMessage(data){
    const {resolve,reject}=requests.get(data.id);
    requests.delete(data.id);
    if(data.error)reject(new Error(data.error));else resolve(data.value);
  }}};
vm.runInNewContext(await readFile(workerURL,'utf8'),context);
function call(method,params){
  return new Promise((resolve,reject)=>{
    const ticket=++id;requests.set(ticket,{resolve,reject});
    context.self.onmessage({data:{id:ticket,method,params}});
  });
}
const examplePairs=[
  ['025','El Centro','Main Street','4th Street'],
  ['037','Pasadena','Holly Street','Arroyo Parkway'],
  ['059','Anaheim','Harbor Boulevard','Katella Avenue'],
  ['065','Riverside','Main Street','University Avenue'],
  ['071','San Bernardino','Highland Avenue','E Street'],
  ['073','San Diego','Broadway','Fifth Avenue'],
  ['111','San Buenaventura','Main Street','California Street']
];
const pair=['Holly St','Arroyo Pkwy'];
const regional=await Promise.all(examplePairs.map(([county])=>call('search',{county,pair,query:pair.join(' & '),mode:'candidates'})));
assert.ok(regional.flat().some(v=>v.county==='037'));
assert.equal(reads.filter(p=>p.endsWith('.sqlite.gz')).length,0,'Regional intersection discovery must use only street indexes');
assert.equal(reads.filter(p=>p.endsWith('streets.json.gz')).length,7);
for(const [county,name,a,b] of examplePairs){
  const place=places.find(p=>p.kind==='city'&&p.name===name&&p.county===county).id;
  const result=await call('search',{query:a+' & '+b,county,place,pair:[a,b],mode:'crossings'});
  assert.ok(result.length,`No shared nodes in ${name} for ${a} & ${b}`);
  assert.ok(result.filter(r=>!r.more).every(r=>r.place===place&&r.county===county&&Number.isFinite(r.x)&&Number.isFinite(r.y)));
  if(name==='Anaheim'){
    const groups=groupCrossingPoints(result);
    assert.ok(groups[0].points?.length>=2,'A divided-road intersection should present its adjacent points together');
    assert.equal(groups.flatMap(g=>g.points||[g]).length,result.length);
    const far={...result[0],x:result[0].x+0.01};
    assert.equal(groupCrossingPoints([result[0],far]).length,2,'Distinct locations with the same name must stay separate');
  }
  console.log(name,result[0].label,result[0].y,result[0].x);
}
assert.equal((await call('search',{query:'Main St & Main Street',county:'037',pair:['Main St','Main Street'],mode:'crossings'})).length,0);
const qualified=await call('search',{query:'Arroyo Park',county:'037',place:'0656000',mode:'streets'});
assert.ok(qualified.some(r=>r.label.includes('Arroyo')),'Incomplete street words');
const actual=await call('onStreet',{street:qualified[0].street,county:'037',place:'0656000'});
assert.ok(actual.length&&actual.every(r=>r.more||r.place==='0656000'));
const urban=await call('onStreet',{street:'Broadway',county:'073'});
assert.ok(urban.at(-1).more,'Large streets must offer another page');
const next=await call('onStreet',urban.at(-1).more);
assert.ok(next.length);
assert.equal(urban.filter(v=>!v.more).some(r=>next.some(v=>v.node===r.node)),false,'Pagination must not repeat nodes');
const stops=await call('search',{query:'Union Station',county:'037',mode:'stops'});
assert.ok(stops.some(r=>r.label.toLowerCase().includes('union')&&r.stop_id));
console.log('Verified parser, regional discovery without SQLite, municipal results in all seven counties, street completion, transit stops and intersection pagination.');
