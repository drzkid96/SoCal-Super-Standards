// Verify literal drawing designations against public search, chart routes and source artwork.
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
const root=fileURLToPath(new URL('../',import.meta.url)), base='/SoCal-Super-Standards';
const read=rel=>readFile(path.join(root,rel),'utf8');
const json=async rel=>JSON.parse(await read(rel));
const rows=await json('public/data/plan-signs.json');
const source=[];
for(const name of ['cad-signs','sign-library-records','3346-sign-records']){
  source.push(...await json('data/reference/plan-examples/'+name+'.json'));
}
const sourcesPublic=await json('public/data/cad-sign-evidence.json');
const art=await json('data/reference/plan-examples/cad-sign-art.json');
assert.deepEqual(sourcesPublic.records,source,'Public CAD evidence must match the source inventory');
const registry=new Map(rows.map(r=>[r.key,r]));
const chart=await read('.standards/docs/signs/index.md');
const inventory=await read('.standards/docs/ladot/plan-reference.md');
const window={},document={getElementById(){return null;},addEventListener(){}};
const context={window,document,URL,location:{origin:'https://example.org'},
  fetch:async url=>new Response(await read('public'+url.replace(base,'')))};
vm.runInNewContext(await read('public/js/search.js'),context);
const {direct,designation}=window.SSSSearch;
const sourceInventory=await read('.standards/docs/signs/cad/sources/fp-signs.md');
assert.match(sourceInventory,/href="[^"]*cad-sign-evidence.json"/);
const escaped=value=>value.replaceAll('&','&amp;').replaceAll('"','&quot;');
const pages=new Map();
async function page(url){
  const rel=url.slice(base.length+1).split('#')[0].replace(/\/$/,'');
  if(!pages.has(rel))pages.set(rel,await read('.standards/docs/'+rel+'.md'));
  return pages.get(rel);
}
for(const record of rows){
  const body=await page(record.url);
  const anchor=record.url.split('#')[1];
  if(anchor)assert.ok(body.includes('id="'+anchor+'"'),record.url);
  const legacySpeed=record.code.match(/^R2-1(\d{2})$/i);
  if(legacySpeed){
    const code='R2-1('+legacySpeed[1]+')';
    const cards=[...chart.matchAll(/<a [^>]*class="scard"[^>]*>/g)].map(m=>m[0]).filter(tag=>tag.includes('data-code="'+code+'"'));
    assert.equal(cards.length,1,'One chart card for '+code);
    assert.ok(cards[0].match(/data-aliases="([^"]*)"/)?.[1].split('|').includes(record.code),'Missing source alias '+record.code);
  }else if(!chart.includes('href="'+escaped(record.url)+'"')){
    const cards=[...chart.matchAll(/<a [^>]*class="scard[^"]*"[^>]*>/g)].filter(([tag])=>
      tag.match(/data-aliases="([^"]*)"/)?.[1].split('|').includes(escaped(record.code)));
    assert.equal(cards.length,1,'One chart card for directional alias '+record.code);
  }
  if(record.modified)assert.ok(!record.official,'A project modification received official status: '+record.code);
  for(const alias of record.aliases){
    const hits=await direct(alias,'Signs',12,'exact');
    const first=hits[0];
    assert.ok(first,alias+' has no exact results');
    if(record.withdrawal)assert.equal(first.tag,'Retired',alias+' must show its withdrawal');
    else assert.equal(first.url,record.url,alias+' must lead to its own record');
    assert.ok(hits.some(r=>r.url===record.url),alias+' is missing the drawing record');
  }
}
for(const obs of source){
  const row=registry.get(designation(obs.designation));
  assert.ok(row,obs.designation);
  const proof=row.drawings.find(d=>d.source===obs.source);
  assert.ok(proof,obs.source+' '+obs.designation);
  const sourcePage=proof.url.startsWith(base+'/signs/cad/sources/') ? await page(proof.url) : inventory;
  assert.ok(sourcePage.includes('id="'+proof.url.split('#')[1]+'"'),proof.url);
  for(const id of obs.detailIDs||[]){
    assert.ok(proof.details.includes(id));
    assert.ok(inventory.includes('id="'+id+'"'));
  }
}
for(const asset of art){
  const row=registry.get(designation(asset.code));
  assert.ok(row?.art.some(a=>a.id===asset.id&&a.drawing===asset.drawing&&a.image===asset.image),asset.id);
  const body=await page(row.url);
  assert.ok(body.includes('src="'+base+asset.image+'"') || body.includes('class="cad-preview"') || (row.official && body.includes('<img ')),
    asset.id+' has no issued or source artwork on the sign page');
  assert.ok((await stat(path.join(root,'public',asset.image))).size>0,asset.id+' empty');
}
for(const [query,end] of [['R10-15','/signs/r10-15/'],['R10-15 (MOD)','/signs/r10-15/#plan-r10-15-mod'],
  ['R10-15-MOD','/signs/r10-15/#plan-r10-15-mod'],['R2-1(30)','/signs/r2-1/#plan-r2-1-30'],
  ['G1-4(CA)','/signs/g1-4ca/'],['W11-2(MOD B)','/signs/w11-2/#plan-w11-2-mod-b']]){
  const hits=await direct(query);
  assert.equal(hits[0].url,base+end,query);
}
const release=await json('public/downloads/sign-blocks/manifest.json');
const nativeLinks=new Set(release.records.map(r=>r.recordUrl));
const issued=new Set(release.records.filter(r=>r.sourceKind==='current issued sign artwork').map(r=>designation(r.code)));
for(const code of new Set(release.records.map(r=>r.code))){
  for(const query of ['CAD '+code, 'DWG '+code,code+' CAD',code+' DWG']){
    const hits=await direct(query,'Signs',5,'exact');
    assert.ok(nativeLinks.has(hits[0]?.url),query+' should open an actual block record');
    if(issued.has(designation(code)))assert.ok(hits[0].label.includes(' · CAD from issued artwork · '),query+' should prefer issued artwork');
  }
}
for(const alias of ['Custom Turn Wheels City Sign','Turn Wheels Custom Sign','R30(CA)(M0D)','R61-19(Mod)(RT)','R49(CA)(L)']){
  const matching=new Set(release.records.filter(r=>r.aliases.some(a=>designation(a)===designation(alias))).map(r=>r.recordUrl));
  assert.ok(matching.size,alias+' requires a source-confirmed match');
  const hits=await direct('DWG '+alias,'Signs',100,'exact');
  assert.ok(hits.length && hits.every(hit=>matching.has(hit.url)),alias+' should resolve to the confirmed face and direction');
  if(alias==='R61-19(Mod)(RT)')assert.ok(hits.length===1 && hits[0].url===base+'/signs/cad/#block-pico-r61-19-ca-mod-rt-14251d8');
  if(alias.includes('Turn Wheels'))assert.ok(hits.some(hit=>hit.url.endsWith('#block-3346-title-103AC67')));
}
console.log('Verified',rows.length,'sign records,',source.length,'drawing designations by source and',art.length,'CAD sign images, including exact search, withdrawals, detail links and base/MOD variants.');
