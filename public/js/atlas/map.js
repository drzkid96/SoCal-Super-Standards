import {groupCrossingPoints,makePlaceSearch} from './location-query.js';
import {cityName,drawMunicipalities} from './municipal-map.js';
const root=document.querySelector('[data-atlas]');
const base=root.dataset.atlas, api=base+'/api/v2/';
const $=id=>document.getElementById('atlas-'+id);
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;if(cls)el.className=cls;return el;};
const link=(label,href)=>{const a=node('a',label);a.href=href;return a;};
const button=(label,fn)=>{const b=node('button',label);b.type='button';b.onclick=fn;return b;};
const norm=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const json=async path=>{const r=await fetch(api+path,{signal:globalThis.AbortSignal?.timeout?.(15000)});if(!r.ok)throw Error('Source unavailable: '+path);return r.json();};
const nearBox=(a,b)=>a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];
const insideBox=(x,y,b)=>x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3];
function inRing(x,y,ring){
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [ax,ay]=ring[i],[bx,by]=ring[j];
    if((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;
  }
  return inside;
}
function inArea(x,y,g){
  return (g.type==='Polygon'?[g.coordinates]:g.coordinates).some(poly=>inRing(x,y,poly[0]) && !poly.slice(1).some(h=>inRing(x,y,h)));
}

const ownerLabels={1:'State highway agency',2:'County highway agency',3:'Town or township highway agency',4:'City or municipal highway agency',11:'State park, forest, or reservation agency',12:'Local park, forest, or reservation agency',21:'Other state agency',25:'Other local agency',26:'Private',27:'Railroad',31:'State toll authority',32:'Local toll authority',40:'Other public instrumentality',50:'Tribal nation',60:'Other federal agency',62:'Bureau of Indian Affairs',63:'U.S. Fish and Wildlife Service',64:'U.S. Forest Service',66:'National Park Service',67:'Tennessee Valley Authority',68:'Bureau of Land Management',69:'Bureau of Reclamation',70:'U.S. Army Corps of Engineers',72:'U.S. Air Force',73:'U.S. Navy',74:'U.S. Army',80:'Other'};
function roadName(r){
  if(r.name && r.name!==r.route_id)return r.name;
  const state=/^SHS_0*(\d+)([A-Z]?)/i.exec(r.route_id||'');
  if(state)return 'State highway route '+state[1]+state[2];
  const parts=(r.route_id||'').split('_');
  return parts.length>=4?parts.slice(2,-1).join(' '):r.route_id;
}
const coords=(x,y)=>y.toFixed(5)+', '+x.toFixed(5);
const latLng=line=>line.map(([x,y])=>[y,x]);
async function start(){
  const emptyGeo={type:'FeatureCollection',features:[]};
  const optional=(path,fallback)=>json(path).catch(()=>fallback);
  const resources=await Promise.all([
    json('places.json'),optional('profiles.json',{}),optional('topics.json',{}),
    optional('counties.geojson',emptyGeo),optional('municipalities.geojson',emptyGeo),
    fetch(new URL('./land.geojson',import.meta.url)).then(r=>r.ok?r.json():null).catch(()=>null),
    window.L?null:import(base+'/vendor/atlas/leaflet.js').catch(()=>null)
  ]);
  const [places,profiles,topics,outline,municipalities,land]=resources;
  let m={sources:{}},aliases={},metadata;
  function streetMetadata(){
    metadata ||= Promise.allSettled([json('layers.json'),json('operator-aliases.json')]).then(([inventory,operators])=>{
      if(inventory.status==='fulfilled')m=inventory.value;
      if(operators.status==='fulfilled')aliases=operators.value;
      if(inventory.status==='rejected'||operators.status==='rejected')metadata=null;
    });
    return metadata;
  }
  const L=window.L;
  const lookup=new Map(places.map(p=>[p.id,p])), cities=places.filter(p=>p.kind==='city'), counties=places.filter(p=>p.kind==='county');
  const scope=window.SSSAgency?.active||'', scopedIssuer=profiles[scope];
  const countySelect=$('county'),citySelect=$('city'),topicSelect=$('topic');
  const inScope=p=>(!scopedIssuer?.place||p.id===scopedIssuer.place)&&(!scopedIssuer?.county||p.county===scopedIssuer.county);
  const orderedCounties=counties.slice().sort((a,b)=>a.name.localeCompare(b.name));
  for(const [key,title] of Object.entries(topics))topicSelect.add(new Option(title,key));
  for(const c of orderedCounties.filter(c=>!scopedIssuer?.county||c.county===scopedIssuer.county))countySelect.add(new Option(c.name+' County',c.county));
  countySelect.disabled=!!scopedIssuer?.county;
  function setCityOptions(code,id=''){
    countySelect.value=code||'';
    citySelect.replaceChildren(new Option('Choose a city',''));
    for(const county of orderedCounties){
      if(code&&county.county!==code)continue;
      const group=document.createElement('optgroup');group.label=county.name+' County';
      const items=cities.filter(c=>c.county===county.county&&inScope(c)).sort((a,b)=>cityName(a).localeCompare(cityName(b)));
      for(const c of items)group.append(new Option(cityName(c),c.id));
      if(items.length)citySelect.append(group);
    }
    citySelect.value=id;
    citySelect.disabled=!!scopedIssuer?.place;
  }
  let map,cartography;
  const regionalView=[[32.48,-119.65],[35.82,-114.12]];
  if(L)map=L.map($('map'),{scrollWheelZoom:false,minZoom:6,maxZoom:19,zoomSnap:.25,attributionControl:true}).fitBounds(regionalView);
  const displayBounds=b=>[[b[1],b[0]],[b[3],b[2]]];
  const fit=(p,max=13)=>map.fitBounds(displayBounds(p.bbox),{padding:[14,14],maxZoom:max,animate:false});
  const geoCache=new Map();
  function boundaries(code){
    if(!geoCache.has(code))geoCache.set(code,json('boundaries/'+code+'.geojson').catch(e=>{geoCache.delete(code);throw e;}));
    return geoCache.get(code);
  }
  const mapLayers=map?{street:L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}),
    aerial:L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',{maxNativeZoom:16,maxZoom:19,attribution:'Imagery: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS</a>'})}:{};
  let basemap,operatorIndex,failedTile=false,baseIssue='',overlayIssues=[],limited=false;
  let pin,locationTicket=0,layerTicket=0,findTicket=0,timer,current=null,selectedCity=null,shownStops=0;
  const stopRenderer=map&&L.canvas({padding:.2});
  const stopsLayer=map&&L.layerGroup().addTo(map),highwayLayer=map&&L.layerGroup().addTo(map),selectedLayer=map&&L.layerGroup().addTo(map);
  function setBase(){
    if(!map)return;
    if(basemap)map.removeLayer(basemap);
    failedTile=false;
    basemap=mapLayers[$('basemap').value];
    if(basemap)basemap.addTo(map);
    cartography.basemap($('basemap').value);
    refreshLayers();
  }
  Object.values(mapLayers).forEach(layer=>layer.on('tileerror',()=>{
    if(layer!==basemap||failedTile)return;
    $('basemap').value='local';
    setBase();failedTile=true;layerStatus();
  }));
  const pending=new Map();let requestNumber=0,worker;
  function request(method,params){
    if(!worker){
      worker=new Worker(base+'/js/atlas/worker.js');
      worker.onmessage=({data})=>{const p=pending.get(data.id);if(p){pending.delete(data.id);data.error?p.reject(Error(data.error)):p.resolve(data.value);}};
      worker.onerror=()=>{for(const p of pending.values())p.reject(Error('Database worker unavailable'));pending.clear();worker.terminate();worker=null;};
    }
    return new Promise((resolve,reject)=>{const id=++requestNumber;pending.set(id,{resolve,reject});worker.postMessage({id,method,params});});
  }
  function layerStatus(){
    const z=map?.getZoom()||0,hints=[];
    if(baseIssue)hints.push(baseIssue);
    if($('stops').checked)hints.push(z<14?'Zoom to street level for transit stops':shownStops+' stops drawn'+(limited?' · zoom in for the remaining stops':''));
    if($('highways').checked && z<10)hints.push('Zoom in for state highways');
    if(failedTile)hints.push('The imagery provider could not load. Restored the minimal basemap.');
    if(overlayIssues.length)hints.push('Layer unavailable: '+overlayIssues.join(', ')+'. Pan or toggle the layer to retry.');
    $('layer-status').textContent=hints.join(' · ');
  }
  async function refreshLayers(){
    const epoch=++layerTicket;clearTimeout(timer);
    timer=setTimeout(async()=>{
      overlayIssues=[];limited=false;const bounds=map.getBounds(),box=[bounds.getWest(),bounds.getSouth(),bounds.getEast(),bounds.getNorth()];
      const z=map.getZoom(), codes=counties.filter(p=>(!scopedIssuer?.county||p.county===scopedIssuer.county)&&nearBox(p.bbox,box)).map(p=>p.county);
      const stops=$('stops').checked && z>=14,highways=$('highways').checked && z>=10;
      try{
        const objects=stops||highways?await request('visible',{bounds:box,counties:codes,zoom:z,stops,highways}):{stops:[],highways:[]};
        if(epoch!==layerTicket)return;
        stopsLayer.clearLayers();highwayLayer.clearLayers();
        overlayIssues=objects.unavailable||[];limited=!!objects.limited;
        for(const h of objects.highways)L.polyline(latLng(h.line),{color:'#aa6044',weight:3,opacity:.75,interactive:false}).addTo(highwayLayer);
        let mappedOperators={};
        if(scopedIssuer?.kind==='Transit agency'&&objects.stops.length)await streetMetadata();
        if(scopedIssuer?.kind==='Transit agency'&&objects.stops.some(s=>relatedOperators(s.agency).length)){
          operatorIndex ||= json('stop-operators.json').catch(()=>{operatorIndex=null;return {stops:{}};});
          mappedOperators=(await operatorIndex).stops;
          if(epoch!==layerTicket)return;
        }
        shownStops=0;
        for(const s of objects.stops){
          const operators=Object.keys(mappedOperators[s.source_id]||{[s.agency]:true});
          if(scopedIssuer?.kind==='Transit agency'&&!operators.some(op=>operatorKey(op)===scope))continue;
          if(scopedIssuer?.place && s.place!==scopedIssuer.place)continue;
          shownStops++;
          const marker=L.circleMarker([s.y,s.x],{renderer:stopRenderer,radius:4,color:'#fff',weight:1,fillColor:'#61477d',fillOpacity:.95,bubblingMouseEvents:false}).addTo(stopsLayer);
          marker.bindTooltip(node('span',s.name+' · '+s.agency));marker.on('click',()=>choose(s.x,s.y,s.name));
        }

      }catch(e){if(epoch===layerTicket){overlayIssues=['Requested overlay'];stopsLayer.clearLayers();highwayLayer.clearLayers();shownStops=0;}}
      if(epoch===layerTicket)layerStatus();
    },120);
  }
  function updateURL(x,y){
    const next=new URL(location.href);next.searchParams.set('lat',y.toFixed(5));next.searchParams.set('lon',x.toFixed(5));
    next.searchParams.set('z',String(map?.getZoom()||16));for(const field of ['county','city','issuer'])next.searchParams.delete(field);
    if(next.href!==location.href)history.pushState(null,'',next);
  }
  function section(title,detail){
    const el=node('section',null,'atlas-section');el.append(node('h3',title));if(detail)el.append(node('p',detail));return el;
  }
  const allowed=key=>!scope||key===scope;
  function sources(keys){
    const items=document.createDocumentFragment(),seen=new Set();
    for(const key of keys){
      if(!profiles[key]||seen.has(key)||!allowed(key))continue;seen.add(key);
      const p=profiles[key],row=node('div',null,'atlas-source');
      row.append(link(p.name,p.home));
      const topic=topicSelect.value;
      if(topic){
        const matches=p.topics[topic]||[];
        for(const item of matches.slice(0,3))row.append(link(item.title,item.url));
        if(!matches.length)row.append(node('small','No indexed match for '+topics[topic]+'. Browse the collection by title.'));
      }else{
        const mainRoutes={caltrans:['/ca-mutcd/','/caltrans/standard-plans-2026/'],fhwa:['/mutcd/'],ladot:['/ladot/mpp-531/'],
          'los-angeles-county-public-works':['/regions/los-angeles-county-public-works/la-road-plans/']};
        const selected=p.kind==='Transit agency'?p.publications.filter(v=>v.url.includes('/transit/')):
          p.publications.length===1?p.publications:(mainRoutes[key]||[]).map(path=>p.publications.find(v=>v.url===base+path)).filter(Boolean);
        for(const book of selected)row.append(link(book.title,book.url));
        if(!selected.length)row.append(link('Browse '+p.publications.length+' publications and drawings',p.home+'#publications-and-drawings'));
      }
      items.append(row);
    }
    return items;
  }
  function operatorKey(name){
    const value=norm(name);
    return Object.keys(aliases).find(k=>[profiles[k]?.name,...aliases[k]].some(s=>norm(s)===value));
  }
  function relatedOperators(name){
    const v=norm(name);
    if(v.includes('san diego metropolitan transit system')&&!operatorKey(name))return ['mts'];
    if(v.includes('gold coast')&&!operatorKey(name))return ['gold-coast'];
    return [];
  }
  function mark(x,y){
    if(pin)pin.setLatLng([y,x]);
    else pin=L.marker([y,x],{icon:L.divIcon({className:'atlas-pin',html:'<span></span>',iconSize:[24,24],iconAnchor:[12,12]}),interactive:false}).addTo(map);
  }
  function summary(title,subtitle){
    const s=$('summary');s.replaceChildren(node('h2',title),node('p',subtitle));return s;
  }
  function referenceKeys(city,county){
    return Object.values(profiles).filter(p=>(city&&p.place===city.id)||(p.county===county.county&&p.kind==='County public works')).map(p=>p.key);
  }
  function clearPoint(){
    locationTicket++;findTicket++;current=null;selectedCity=null;root.dataset.selection='area';
    $('results').replaceChildren();$('results').removeAttribute('aria-busy');$('context').setAttribute('aria-busy','false');
    selectedLayer?.clearLayers();if(pin){pin.remove();pin=null;}
  }
  function areaURL(params){
    const next=new URL(location.href);
    for(const field of ['city','county','lat','lon','z','issuer'])next.searchParams.delete(field);
    for(const [field,value] of Object.entries(params))if(value)next.searchParams.set(field,value);
    if(next.href!==location.href)history.pushState(null,'',next);
  }
  function shareButton(label){
    const b=button(label,async()=>{try{await navigator.clipboard.writeText(location.href);b.textContent='Link copied';}catch{b.textContent='Copy the address from your browser';}});return b;
  }
  function displayMunicipality(city){
    const county=counties.find(c=>c.county===city.county);
    const heading=summary(cityName(city),county.name+' County · Incorporated municipality');
    heading.append(shareButton('Copy city link'));
    const panel=$('context');panel.replaceChildren();
    const own=Object.values(profiles).filter(p=>p.place===city.id&&allowed(p.key)).map(p=>p.key);
    const local=section(scopedIssuer&&!scopedIssuer.place?'Standards from '+scopedIssuer.name:'Municipal standards');
    if(own.length)local.append(sources(own));
    else if(scope&&scopedIssuer){local.append(sources([scope]));}
    else {
      local.append(node('p',Object.keys(profiles).length?'No municipal publication is indexed for '+cityName(city)+'.':'The publication index is temporarily unavailable.'));
      if(city.official)local.append(link(cityName(city)+' · official city website',city.official));
    }
    if(own.length&&city.official)local.append(link('Official municipal website',city.official));
    panel.append(local);
    if(scope)return;
    const countyKeys=Object.values(profiles).filter(p=>p.county===city.county&&p.kind==='County public works').map(p=>p.key);
    const other=section('County and regional references','Check these for county work or interagency coordination. The municipal boundary does not establish who maintains a street.');
    other.append(sources(countyKeys));
    const regional=Object.values(profiles).filter(p=>p.county===city.county&&['Transit agency','Regional agency','Regional standards'].includes(p.kind));
    for(const p of regional)other.append(link(p.fullName||p.name,p.home));
    const context=node('details',null,'atlas-more');context.append(node('summary','County, regional and statewide references'));
    context.append(other);
    const statewide=section('State and federal references');statewide.append(sources(['caltrans','fhwa']));context.append(statewide);
    context.open=!own.length||window.matchMedia('(min-width: 49rem)').matches;
    panel.append(context);
  }
  function showMunicipality(city,{push=true,move=true}={}){
    if(!city||city.kind!=='city'||!inScope(city))return;
    clearPoint();selectedCity=city;root.dataset.selection='city';$('inspect').checked=false;
    setCityOptions(city.county,city.id);cartography?.select(city.id);
    if(push)areaURL({city:city.id});
    if(map&&move)fit(city);
    displayMunicipality(city);
  }
  function overview(county,issuer,move=true){
    cartography?.select('');
    const panel=$('context');panel.replaceChildren();
    const local=cities.filter(p=>inScope(p)&&(!county||p.county===county.county));
    summary(issuer?.fullName||issuer?.name||(county?county.name+' County':'Southern California'),
      issuer?'Standards from this issuing agency.':county?local.length+' incorporated municipalities. Choose a city for its standards.':local.length+' municipalities across seven counties. Choose a city on the map or in the list.');
    if(!county&&!issuer){
      const region=section('Browse by county');
      for(const c of orderedCounties){
        const chosen=button(c.name,()=>{countySelect.value=c.county;selectCounty();});chosen.className='atlas-county-row';region.append(chosen);
      }
      panel.append(region);
      const featured=section('Municipal collections');
      const featuredIds=['0644000','0656000','0602000','0662000','0666000','0654652','0621782'];
      for(const id of featuredIds){
        const p=lookup.get(id);
        if(!p||!Object.values(profiles).some(v=>v.place===id))continue;
        const a=link(cityName(p),base+'/map/?city='+id);
        a.className='atlas-featured-city';
        a.onclick=e=>{if(!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!e.altKey){e.preventDefault();showMunicipality(p);}};
        featured.append(a);
      }
      if(featured.querySelector('a'))panel.append(featured);
    }else{
      const featured=section(issuer?'Agency standards':'County standards',issuer?'':'County publications and drawings for county-maintained facilities and unincorporated areas.');
      const keys=issuer?[issuer.key]:Object.values(profiles).filter(p=>p.county===county.county&&p.kind==='County public works').map(p=>p.key);
      featured.append(sources(keys));panel.append(featured);
    }
    if(move&&map){if(county)fit(county,10);else map.fitBounds(regionalView,{padding:[6,6],animate:false});}
  }
  async function choose(x,y,label='',move=true,push=true){
    if(!Number.isFinite(x)||!Number.isFinite(y))return;
    root.dataset.selection='point';
    const ticket=++locationTicket;current={x,y,label};selectedCity=null;citySelect.value='';cartography?.select('');selectedLayer?.clearLayers();if(map)mark(x,y);
    if(move&&map)map.setView([y,x],Math.max(15,map.getZoom()),{animate:false});
    if(push)updateURL(x,y);
    summary(label||'Selected location',coords(x,y));
    const panel=$('context');panel.setAttribute('aria-busy','true');panel.replaceChildren(node('p','Checking boundaries, roadway records, and scheduled stops…'));
    const candidates=counties.filter(p=>insideBox(x,y,[p.bbox[0]-.006,p.bbox[1]-.006,p.bbox[2]+.006,p.bbox[3]+.006]));
    try{
      const boundaryChecks=await Promise.allSettled(candidates.map(p=>boundaries(p.county)));
      if(ticket!==locationTicket)return;
      const failed=candidates.filter((_,i)=>boundaryChecks[i].status==='rejected');
      const data=boundaryChecks.filter(v=>v.status==='fulfilled').map(v=>v.value);
      const matched=data.flatMap(c=>c.features.filter(f=>insideBox(x,y,lookup.get(f.properties.id).bbox)&&inArea(x,y,f.geometry)).map(f=>lookup.get(f.properties.id)));
      const county=matched.find(p=>p.kind==='county')||candidates.find(p=>matched.some(v=>v.county===p.county));
      if(!county&&failed.length){
        panel.replaceChildren(node('p','Detailed boundaries are unavailable for '+failed.map(c=>c.name+' County').join(', ')+'. Choose a municipality above or retry this point.'),button('Retry boundaries',()=>choose(x,y,label,false,false)));
        return;
      }
      if(!county){panel.replaceChildren(node('p','This point is outside the seven-county coverage area.'));return;}
      const city=matched.find(p=>p.kind==='city');
      if(scopedIssuer && ((scopedIssuer.place && scopedIssuer.place!==city?.id)||(scopedIssuer.county && scopedIssuer.county!==county.county))){
        summary('Outside '+scopedIssuer.name+' coverage',coords(x,y));
        panel.replaceChildren(link('Open '+scopedIssuer.name+' references',scopedIssuer.home));return;
      }
      setCityOptions(county.county);
      const heading=summary(label||(city?.name||'Unincorporated '+county.name+' County'),
                            (city?city.name:'Unincorporated area')+' · '+county.name+' County · '+coords(x,y));
      const share=button('Copy location link',async()=>{try{await navigator.clipboard.writeText(location.href);share.textContent='Link copied';}catch{share.textContent='Copy the address bar URL';}});
      heading.append(share);
      const agencies=section('Standards for this location');agencies.append(sources(scopedIssuer?[scope]:referenceKeys(city,county)));
      const selectedTopic=topicSelect.value;
      if(selectedTopic&&!scope)agencies.append(link('Compare guidance across agencies · '+topics[selectedTopic],base+'/topics/'+selectedTopic+'/'));
      if(!scope&&city&&!Object.values(profiles).some(p=>p.place===city.id)){agencies.append(node('p','City collection not indexed. County publications above cover county work.'));if(city.official)agencies.append(link(cityName(city)+' · official city website',city.official));}
      panel.replaceChildren(agencies);
      if(failed.length)panel.append(node('p','Adjacent boundary data is unavailable for '+failed.map(c=>c.name+' County').join(', ')+'.'));
      const [found]=await Promise.all([request('identify',{x,y,counties:candidates.map(p=>p.county)}),streetMetadata()]);
      if(ticket!==locationTicket)return;
      if(found.unavailable?.length){const issue=section('Some street data is unavailable',found.unavailable.join(' · '));issue.append(button('Retry street data',()=>choose(x,y,label,false,false)));panel.append(issue);}
      if(found.roadContext?.length && (!scope || city&&scopedIssuer?.place===city.id)){
        const localRoads=section('Local street records','Municipal inventory and maintenance evidence within 40 m. Each entry identifies what the publisher records.');
        for(const record of found.roadContext.slice(0,8)){
          const row=node('div',null,'atlas-record');
          row.append(node('strong',record.name),node('span',record.agency+' · '+(record.role==='maintenance'?'Maintenance record':'Street inventory')+' · '+Math.round(record.distance)+' m'));
          if(record.classification)row.append(node('small',record.classification));
          if(record.source?.url){
            const specific=/\/(?:FeatureServer|MapServer)\/\d+\/?$/.test(record.source.url)&&Number.isInteger(record.ref);
            row.append(link(specific?'City GIS record '+record.ref:record.source.title||'Publisher record',
              specific?record.source.url.replace(/\/$/,'')+'/'+record.ref:record.source.url));
          }
          localRoads.append(row);
        }
        const source=found.roadContext[0].source;
        if(source?.privateStreetsUrl)localRoads.append(link('Pasadena private street register',source.privateStreetsUrl));
        panel.append(localRoads);
      }
      const roads=section('Reported road ownership','FHWA HPMS 2024 · centerlines within 40 m');
      if(!found.unavailable?.some(s=>s.toLowerCase().includes('ownership'))&&!found.roads.some(r=>scope!=='caltrans'||r.owner===1))roads.append(node('p','No ownership record within 40 m. Confirm the segment with the reviewing agency.'));
      for(const r of found.roads.filter(r=>scope!=='caltrans'||r.owner===1).slice(0,7)){
        const row=node('div',null,'atlas-record'),b=button(roadName(r)||'Recorded segment',()=>{
          selectedLayer.clearLayers();L.polyline(latLng(r.line),{color:'#cb5928',weight:6,interactive:false}).addTo(selectedLayer);
        });
        row.append(b,node('span',(ownerLabels[r.owner]||'Owner code '+r.owner)+' · '+Math.round(r.distance)+' m'),node('small','HPMS ID '+r.route_id));roads.append(row);
      }
      if(found.highways.length){
        roads.append(node('p','Caltrans network within 40 m: '+found.highways.slice(0,4).map(h=>'Route '+h.route+' '+(h.direction||'')+' · District '+h.district).join(' / ')));
      }
      if(found.highways.length||found.roads.some(v=>v.owner===1))roads.append(sources(['caltrans']));
      if(m.sources.ownership)roads.append(link('Ownership source',m.sources.ownership.url));panel.append(roads);
      const transit=section('Stops and operators','Published stop points within 400 m, measured straight-line.');
      const operators=new Map();
      let resolved={};
      if(found.stops.some(s=>relatedOperators(s.agency).length)){
        operatorIndex ||= json('stop-operators.json').catch(()=>{operatorIndex=null;return {stops:{}};});
        resolved=(await operatorIndex).stops;
        if(ticket!==locationTicket)return;
      }
      for(const s of found.stops){
        const byOperator=resolved[String(s.source_id)]||{[s.agency?.trim()||'Operator unspecified in stop inventory']:String(s.routes||'').split(',').map(r=>r.trim()).filter(Boolean)};
        for(const [agency,routes] of Object.entries(byOperator)){
          if(scopedIssuer?.kind==='Transit agency' && operatorKey(agency)!==scope)continue;
          if(!operators.has(agency))operators.set(agency,[]);
          operators.get(agency).push({...s,routes:routes.join(', ')});
        }
      }
      for(const [agency,stops] of operators){
        const group=node('div',null,'atlas-stop-group'),key=operatorKey(agency);
        group.append(key&&allowed(key)?link(agency,profiles[key].publications.find(p=>p.kind.includes('guide')||p.kind.includes('Guide'))?.url||profiles[key].home):node('strong',agency));
        for(const k of relatedOperators(agency).filter(allowed))group.append(link('Related operator guide · '+profiles[k].name,profiles[k].home));
        if(key && allowed(key) && topicSelect.value)for(const ref of (profiles[key].topics[topicSelect.value]||[]).slice(0,2))group.append(link(ref.title,ref.url));
        for(const s of stops.slice(0,3)){
          const b=button(s.name,()=>choose(s.x,s.y,s.name));
          group.append(b,node('small',Math.round(s.distance)+' m · Stop '+s.stop_id+(s.routes?' · Route IDs '+s.routes:'')));
        }
        if(stops.length>3){const more=node('details');more.append(node('summary',(stops.length-3)+' more stop records'));for(const s of stops.slice(3))more.append(button(s.name+' · '+Math.round(s.distance)+' m',()=>choose(s.x,s.y,s.name)));group.append(more);}
        transit.append(group);
      }
      if(!operators.size&&!found.unavailable?.some(s=>s.toLowerCase().includes('stops')))transit.append(node('p','No matching stop records in this radius in the source snapshot.'));
      if(m.sources.transit)transit.append(link('Stop inventory source',m.sources.transit.url));panel.append(transit);
    }catch(e){if(ticket===locationTicket)panel.append(node('p','Location lookup could not finish. '+e.message),button('Retry lookup',()=>choose(x,y,label,false,false)));}
    finally{if(ticket===locationTicket)panel.setAttribute('aria-busy','false');}
  }
  const locations=makePlaceSearch(places);
  const searchInput=$('query'), searchForm=root.querySelector('.atlas-search'), resultPanel=$('results');
  const countyName=code=>counties.find(p=>p.county===code)?.name+' County';
  const areaName=area=>area.kind==='county'?countyName(area.county):cityName(area);
  const allowedCounty=code=>!scopedIssuer?.county||scopedIssuer.county===code;
  const listId='atlas-location-suggestions',suggestions=node('datalist');
  suggestions.id=listId;searchInput.setAttribute('list',listId);searchForm.append(suggestions);
  searchInput.addEventListener('input',()=>{
    findTicket++;resultPanel.replaceChildren();resultPanel.removeAttribute('aria-busy');
    const value=searchInput.value,pieces=value.split(','),partial=pieces.pop().trim(),prefix=pieces.length?pieces.join(',')+', ':'';
    suggestions.replaceChildren(...locations.suggestions(partial,p=>inScope(p)&&(!countySelect.value||p.county===countySelect.value||pieces.length))
      .map(p=>new Option('',prefix+areaName(p))));
  });
  async function runJobs(jobs,ticket){
    let next=0;
    const items=[],failed=[];
    async function consume(){
      while(ticket===findTicket&&next<jobs.length){
        const job=jobs[next++];
        try{items.push(...await request('search',job));}
        catch{failed.push(countyName(job.county)+' '+(job.mode==='stops'?'stops':'streets'));}
      }
    }
    await Promise.all([consume(),consume()]);
    return {items,failed};
  }
  function searchError(message,retry){
    resultPanel.replaceChildren(node('p',message));
    if(retry)resultPanel.append(button('Retry search',retry));
    resultPanel.removeAttribute('aria-busy');
  }
  async function getCrossings(params,previous=[]){
    const ticket=++findTicket, more=params.cursor, street=params.street||params.pair.join(' & ');
    const name=lookup.get(params.place);
    resultPanel.setAttribute('aria-busy','true');
    resultPanel.textContent='Finding intersections on '+street+' in '+(name?cityName(name):countyName(params.county))+'…';
    try{
      const rows=await request(params.street?'onStreet':'search',params);
      if(ticket!==findTicket)return;
      displayResults([...previous,...rows],{caption:street+' · '+(name?cityName(name)+' · ':'')+countyName(params.county),
        empty:more?'No further intersections in the index.':'No shared street nodes found here. Try another cross street or city.'});
    }catch{if(ticket===findTicket)searchError('The intersection index could not load for '+countyName(params.county)+'.',()=>getCrossings(params,previous));}
  }
  function openSearchResult(item){
    ++findTicket;resultPanel.replaceChildren();resultPanel.removeAttribute('aria-busy');
    if(item.area?.kind==='city')showMunicipality(item.area);
    else if(item.area?.kind==='county'){countySelect.value=item.area.county;selectCounty();}
    else choose(item.x,item.y,item.label);
    const target=$('summary');target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({block:'nearest'});
  }
  function displayResults(items,{caption='',empty='No matching records. Try a city, street name, stop ID, or two streets joined by &.',actions=[],failed=[],retry}={}){
    const list=resultPanel;list.replaceChildren();list.removeAttribute('aria-busy');
    if(caption)list.append(node('p',caption,'atlas-hint'));
    if(failed.length){
      list.append(node('p','Incomplete coverage. Could not load '+[...new Set(failed)].sort().join(', ')+'.'));
      if(retry)list.append(button('Retry search',retry));
    }
    if(!items.length&&!failed.length)list.append(node('p',empty));
    const records=groupCrossingPoints(items),ul=node('ul');let shown=0;
    const page=()=>{
      for(const item of records.slice(shown,shown+20)){
        const li=node('li'),place=lookup.get(item.place);
        if(item.points){
          const details=node('details');
          const title=node('summary',item.label);
          title.append(node('small',' · '+item.points.length+' mapped points · '+[place&&cityName(place),countyName(item.county)].filter(Boolean).join(' · ')));
          details.append(title);
          for(const point of item.points)details.append(button(coords(point.x,point.y),()=>openSearchResult(point)));
          li.append(details);ul.append(li);continue;
        }
        const b=button(item.label,()=>{
          if(item.more){getCrossings(item.more,items.filter(i=>!i.more));return;}
          if(item.candidate){getCrossings(item.candidate);return;}
          if(item.street){getCrossings({street:item.street,county:item.county,place:item.place});return;}
          openSearchResult(item);
        });
        const detail=item.more?'':item.candidate?'Both names appear in this county’s street index':[
          item.type,place&&cityName(place),item.county&&countyName(item.county),item.agency,item.stop_id&&'Stop '+item.stop_id
        ].filter(Boolean).join(' · ');
        if(detail)b.append(node('small',detail));
        li.append(b);ul.append(li);
      }
      shown+=20;
      expand.hidden=shown>=records.length;
    };
    const expand=button('Show more results',page);
    if(items.length){list.append(ul,expand);page();}
    for(const [title,action] of actions)list.append(button(title,action));
  }
  async function findLocation(override=''){
    const ticket=++findTicket, input=searchInput.value.trim();
    const parsed=locations.parse(input);
    if(parsed.error){searchError(parsed.error);return;}
    if(parsed.x!==undefined){resultPanel.replaceChildren();resultPanel.removeAttribute('aria-busy');choose(parsed.x,parsed.y);return;}
    const {area,localCity,localCounty,term,pair}=parsed;
    if((area?.kind==='city'&&!inScope(area)) || (area?.kind==='county'&&(!allowedCounty(area.county)||scopedIssuer?.place)) ||
        (localCity&&!inScope(localCity)) || (localCounty&&!allowedCounty(localCounty.county))){
      searchError('That location is outside '+(scopedIssuer?.name||'the selected agency')+' coverage.');return;
    }
    const asResult=p=>({area:p,label:areaName(p),county:p.kind==='city'?p.county:'',type:p.kind==='city'?'Municipal standards':'County standards'});
    if(area){displayResults([asResult(area)]);return;}
    const city=localCity||lookup.get(scopedIssuer?.place||(!localCounty&&citySelect.value));
    const code=city?.county||localCounty?.county||scopedIssuer?.county||countySelect.value;
    const codes=code?[code]:orderedCounties.map(c=>c.county).filter(allowedCounty);
    const scopeLabel=city?cityName(city)+' · '+countyName(city.county):code?countyName(code):'All seven counties';
    const mode=override||parsed.mode;
    const retry=()=>findLocation(override);
    if(!term||norm(term).length<2&&!/^\d$/.test(term) || pair?.some(v=>!norm(v))){
      searchError('Enter at least two letters, a stop ID, or the names of both streets.');return;
    }
    const matchedCities=!pair&&!localCity&&!mode?locations.suggestions(term,p=>inScope(p)&&(!code||p.county===code)).map(asResult):[];
    const params={query:term,place:city?.id,pair,agencyNames:scopedIssuer?.kind==='Transit agency'?[scopedIssuer.name,...(aliases[scope]||[])].filter(Boolean):undefined};
    const regional=codes.length>1;
    const looksLikeStop=/\b(station|stop|transit|terminal|metrolink|park\s+and\s+ride)\b/i.test(term)||/^\d+$/.test(term);
    const modes=pair?[regional?'candidates':'crossings']:mode?[mode]:
      regional&&!looksLikeStop?['streets']:['streets','stops'];
    resultPanel.setAttribute('aria-busy','true');resultPanel.textContent='Searching · '+scopeLabel+'…';
    try{
      const {items,failed}=await runJobs(codes.flatMap(county=>modes.map(mode=>({...params,county,mode}))),ticket);
      if(ticket!==findTicket)return;
      if(pair&&regional){
        const candidates=items.sort((a,b)=>countyName(a.county).localeCompare(countyName(b.county)));
        if(candidates.length===1&&!failed.length){await getCrossings({...params,county:candidates[0].county,mode:'crossings'});return;}
        displayResults(candidates.map(({county})=>({label:'Check intersections in '+countyName(county),candidate:{...params,county,mode:'crossings'}})),{
          caption:candidates.length?'Choose a county to check the shared intersections for '+term+'.':scopeLabel,
          empty:'No indexed area contains both street names. Check spelling or try a different cross street.',failed,retry});
        return;
      }
      const actions=[];
      if(regional&&!mode&&!pair&&!modes.includes('stops')){
        if(!items.length && !matchedCities.length && !failed.length){await findLocation('stops');return;}
        actions.push(['Search transit stops for “'+term+'”',()=>findLocation('stops')]);
      }
      const rank=x=>x.area?0:x.exact?1:x.street?2:3;
      const sorted=[...matchedCities,...items.filter(r=>!r.more)].sort((a,b)=>rank(a)-rank(b)||
        a.label.localeCompare(b.label)||String(a.county).localeCompare(String(b.county))||String(a.stop_id||'').localeCompare(String(b.stop_id||'')));
      const tooManyStops=codes.some(c=>items.filter(r=>r.type==='Transit stop'&&r.county===c).length===36);
      displayResults([...sorted,...items.filter(r=>r.more)],{caption:scopeLabel+(tooManyStops?' · Showing a selection of stops. Add a city or stop ID to narrow the search.':''),
        failed,retry,actions,empty:'No matching '+(mode==='stops'?'transit stops':'records')+' in '+scopeLabel+'. Try another name or a different area.'});
    }catch{if(ticket===findTicket)searchError('Location search could not finish. Try again.',retry);}
  }
  searchForm.onsubmit=e=>{e.preventDefault();findLocation();};
  function selectCounty(){
    const code=scopedIssuer?.county||countySelect.value;
    clearPoint();$('inspect').checked=false;setCityOptions(code);
    areaURL({county:code});overview(counties.find(c=>c.county===code),scopedIssuer);
  }
  function restore(){
    const u=new URL(location.href),args=u.searchParams;
    topicSelect.value=args.get('topic')||'';
    const x=parseFloat(args.get('lon')),y=parseFloat(args.get('lat'));
    if(Number.isFinite(x)&&Number.isFinite(y)&&Math.abs(x)<=180&&Math.abs(y)<=90){
      const z=Math.max(6,Math.min(19,parseInt(args.get('z'),10)||16));map?.setView([y,x],z);choose(x,y,'',false,false);return;
    }
    const issuer=scopedIssuer||profiles[args.get('issuer')];
    const city=lookup.get(scopedIssuer?.place||args.get('city')||issuer?.place);
    if(city?.kind==='city'&&inScope(city)){showMunicipality(city,{push:false});return;}
    clearPoint();$('inspect').checked=false;
    const county=counties.find(c=>c.county===(issuer?.county||args.get('county')));
    setCityOptions(county?.county);overview(county,issuer);
    if(args.has('city')&&!city)$('context').prepend(node('p','Municipality not found. Choose a city from the list.','atlas-empty'));
  }
  if(map){
    cartography=drawMunicipalities({L,map,places,counties,outline,overview:municipalities,land,boundaries,allowed:inScope,
      onCity:showMunicipality,onCounty:code=>{if(scopedIssuer?.place||scopedIssuer?.county&&scopedIssuer.county!==code)return;countySelect.value=code;selectCounty();},
      inspecting:()=>$('inspect').checked,onInspect:pos=>choose(pos.lng,pos.lat,'',false),
      onIssue:message=>{baseIssue=message;layerStatus();}
    });
    map.on('click',e=>{if($('inspect').checked)choose(e.latlng.lng,e.latlng.lat,'',false);});
    map.on('moveend',refreshLayers);
    for(const layer of ['stops','highways'])$(layer).onchange=refreshLayers;
    new ResizeObserver(()=>map.invalidateSize({pan:false})).observe($('map'));
  }else{
    $('map').replaceChildren(node('p','The map could not load. Choose a municipality above to browse the same standards.'));
    $('map').style.height='auto';
  }
  $('basemap').onchange=setBase;countySelect.onchange=selectCounty;
  citySelect.onchange=()=>citySelect.value?showMunicipality(lookup.get(citySelect.value)):selectCounty();
  $('inspector').ontoggle=()=>{if(!$('inspector').open)$('inspect').checked=false;};
  topicSelect.onchange=()=>{
    const next=new URL(location.href);
    if(topicSelect.value)next.searchParams.set('topic',topicSelect.value);else next.searchParams.delete('topic');
    history.pushState(null,'',next);
    if(current)choose(current.x,current.y,current.label,false,false);
    else if(selectedCity)displayMunicipality(selectedCity);
    else overview(counties.find(c=>c.county===countySelect.value),scopedIssuer||profiles[next.searchParams.get('issuer')],false);
  };
  window.addEventListener('popstate',restore);
  restore();setBase();

}
start().catch(()=>{$('summary').textContent='The municipal index could not load.';$('context').replaceChildren(link('Browse the agency standards directory',base+'/regions/'),button('Retry map',()=>location.reload()));});
