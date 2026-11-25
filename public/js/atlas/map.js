const root=document.querySelector('[data-atlas]');
const base=root.dataset.atlas, api=base+'/api/v2/';
const $=id=>document.getElementById('atlas-'+id);
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;if(cls)el.className=cls;return el;};
const link=(label,href)=>{const a=node('a',label);a.href=href;return a;};
const button=(label,fn)=>{const b=node('button',label);b.type='button';b.onclick=fn;return b;};
const norm=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const json=async path=>{const r=await fetch(api+path);if(!r.ok)throw Error('Source unavailable: '+path);return r.json();};
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
  if(!window.L)await import(base+'/vendor/atlas/leaflet.js');
  const L=window.L;
  const [m,places,profiles,aliases,outline,topics]=await Promise.all(['layers.json','places.json','profiles.json','operator-aliases.json','counties.geojson','topics.json'].map(json));
  const lookup=new Map(places.map(p=>[p.id,p])), cities=places.filter(p=>p.kind==='city'), counties=places.filter(p=>p.kind==='county');
  const url=new URL(location.href), scope=window.SSSAgency?.active||'';
  const scopedIssuer=profiles[scope],initialIssuer=scopedIssuer||profiles[url.searchParams.get('issuer')];
  const countySelect=$('county'),topicSelect=$('topic');
  for(const [key,title] of Object.entries(topics))topicSelect.add(new Option(title,key));
  topicSelect.value=url.searchParams.get('topic')||'';
  for(const c of counties.filter(c=>!scopedIssuer?.county||c.county===scopedIssuer.county).sort((a,b)=>a.name.localeCompare(b.name)))countySelect.add(new Option(c.name+' County',c.county));
  countySelect.value=initialIssuer?.county||((m.countyLayers[url.searchParams.get('county')]&&url.searchParams.get('county'))||'037');
  if(scopedIssuer?.county)countySelect.disabled=true;
  const map=L.map($('map'),{preferCanvas:false,scrollWheelZoom:false,minZoom:6,maxZoom:19,zoomControl:true,attributionControl:true});
  const displayBounds=b=>[[b[1],b[0]],[b[3],b[2]]];
  const fit=(p,max=13)=>map.fitBounds(displayBounds(p.bbox),{padding:[14,14],maxZoom:max,animate:false});
  const geoCache=new Map();
  function boundaries(code){
    if(!geoCache.has(code))geoCache.set(code,json('boundaries/'+code+'.geojson').catch(e=>{geoCache.delete(code);throw e;}));
    return geoCache.get(code);
  }
  const mapLayers={street:L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}),
    aerial:L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',{maxNativeZoom:16,maxZoom:19,attribution:'Imagery: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>'})};
  let basemap,operatorIndex,failedTile=false;
  function setBase(){
    if(basemap)map.removeLayer(basemap);failedTile=false;
    basemap=mapLayers[$('basemap').value];if(basemap)basemap.addTo(map);
    refreshLayers();
  }
  Object.values(mapLayers).forEach(l=>l.on('tileerror',()=>{if(l===basemap&&!failedTile){failedTile=true;layerStatus();}}));
  L.geoJSON(outline,{bubblingMouseEvents:false,onEachFeature:(f,layer)=>{
    layer.bindTooltip(node('span',f.properties.name),{permanent:false,sticky:true});
    layer.on('click',e=>{if(map.getZoom()<=8){countySelect.value=f.properties.county;selectCounty();}else choose(e.latlng.lng,e.latlng.lat,'',false);});
  },style:{color:'#4b726a',weight:1.5,opacity:.75,fillOpacity:.035}}).addTo(map);
  const stopRenderer=L.canvas({padding:.2});
  const countyLabels=L.layerGroup().addTo(map);
  for(const c of counties){
    const label=node('span',c.name);const icon=L.divIcon({className:'atlas-county-label',html:label,iconSize:[100,20],iconAnchor:[50,10]});
    L.marker([c.center[1],c.center[0]],{icon,interactive:false,keyboard:false}).addTo(countyLabels);
  }
  map.on('zoomend',()=>{if(map.getZoom()>8)map.removeLayer(countyLabels);else if(!map.hasLayer(countyLabels))countyLabels.addTo(map);});
  const cityLayer=L.layerGroup().addTo(map),stopsLayer=L.layerGroup().addTo(map),highwayLayer=L.layerGroup().addTo(map),selectedLayer=L.layerGroup().addTo(map);
  let pin,locationTicket=0,layerTicket=0,findTicket=0,timer,current=null,shownStops=0,networkError=false;
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
    const z=map.getZoom(),hints=[];
    if($('stops').checked)hints.push(z<14?'Zoom to street level to see stops':shownStops+' stops drawn (up to 750 per county)');
    if(failedTile)hints.push('Basemap tile unavailable. Local lookup still works.');
    if(networkError)hints.push('An overlay could not load. Pan or change a layer to retry.');
    $('layer-status').textContent=hints.join(' · ');
  }
  async function refreshLayers(){
    const epoch=++layerTicket;clearTimeout(timer);
    timer=setTimeout(async()=>{
      networkError=false; const bounds=map.getBounds(),box=[bounds.getWest(),bounds.getSouth(),bounds.getEast(),bounds.getNorth()];
      const z=map.getZoom(), codes=counties.filter(p=>(!scopedIssuer?.county||p.county===scopedIssuer.county)&&nearBox(p.bbox,box)).map(p=>p.county);
      const stops=$('stops').checked && z>=14,highways=$('highways').checked && z>=10;
      try{
        const [collections,objects]=await Promise.all([
          $('cities').checked && z>=8?Promise.all(codes.map(boundaries)):[],
          stops||highways?request('visible',{bounds:box,counties:codes,zoom:z,stops,highways}):{stops:[],highways:[]}]);
        if(epoch!==layerTicket)return;
        cityLayer.clearLayers();stopsLayer.clearLayers();highwayLayer.clearLayers();
        for(const data of collections)L.geoJSON(data,{filter:f=>f.properties.kind==='city'&&(!scopedIssuer?.place||f.properties.id===scopedIssuer.place)&&nearBox(lookup.get(f.properties.id).bbox,box),
          interactive:false,style:{color:basemap===mapLayers.aerial?'#8aecd0':'#497d72',weight:1.4,fillOpacity:.055}}).addTo(cityLayer);
        for(const h of objects.highways)L.polyline(latLng(h.line),{color:'#aa6044',weight:3,opacity:.75,interactive:false}).addTo(highwayLayer);
        let mappedOperators={};
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

      }catch(e){if(epoch===layerTicket)networkError=true;}
      if(epoch===layerTicket)layerStatus();
    },120);
  }
  function updateURL(x,y){
    const next=new URL(location.href);next.searchParams.set('lat',y.toFixed(5));next.searchParams.set('lon',x.toFixed(5));
    next.searchParams.set('z',String(map.getZoom()));next.searchParams.delete('county');
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
  function overview(county,issuer,move=true){
    const place=issuer?.place&&lookup.get(issuer.place);
    summary(issuer?.name||(county?county.name+' County':'Southern California'),'Select a point to identify the roadway and nearby transit operators.');
    const panel=$('context');panel.replaceChildren();
    if(!county && !issuer){
      const region=section('Browse by county');
      for(const c of counties){
        const chosen=button(c.name,()=>{countySelect.value=c.county;selectCounty();});
        chosen.className='atlas-county-row';region.append(chosen);
      }
      panel.append(region);
      if(move)map.fitBounds([[32.52,-119.7],[35.82,-114.1]],{padding:[6,6]});
      return;
    }
    const featured=section('Indexed authorities');
    const keys=issuer?[issuer.key]:Object.values(profiles).filter(p=>p.county===county.county).map(p=>p.key);
    featured.append(sources(keys));panel.append(featured);
    if(move){if(place)fit(place);else if(issuer&&!issuer.county)map.fitBounds([[32.52,-119.7],[35.82,-114.1]]);else if(county)fit(county,10);}
  }
  async function choose(x,y,label='',move=true,push=true){
    if(!Number.isFinite(x)||!Number.isFinite(y))return;
    const ticket=++locationTicket;current={x,y,label};selectedLayer.clearLayers();mark(x,y);
    if(move)map.setView([y,x],Math.max(15,map.getZoom()),{animate:false});
    if(push)updateURL(x,y);
    summary(label||'Selected location',coords(x,y));
    const panel=$('context');panel.setAttribute('aria-busy','true');panel.replaceChildren(node('p','Checking boundaries, roadway records, and scheduled stops…'));
    const candidates=counties.filter(p=>insideBox(x,y,[p.bbox[0]-.006,p.bbox[1]-.006,p.bbox[2]+.006,p.bbox[3]+.006]));
    try{
      const data=await Promise.all(candidates.map(p=>boundaries(p.county)));
      if(ticket!==locationTicket)return;
      const matched=data.flatMap(c=>c.features.filter(f=>insideBox(x,y,lookup.get(f.properties.id).bbox)&&inArea(x,y,f.geometry)).map(f=>lookup.get(f.properties.id)));
      const county=matched.find(p=>p.kind==='county')||candidates.find(p=>matched.some(v=>v.county===p.county));
      if(!county){panel.replaceChildren(node('p','This point is outside the seven-county coverage area.'));return;}
      const city=matched.find(p=>p.kind==='city');
      if(scopedIssuer && ((scopedIssuer.place && scopedIssuer.place!==city?.id)||(scopedIssuer.county && scopedIssuer.county!==county.county))){
        summary('Outside '+scopedIssuer.name+' coverage',coords(x,y));
        panel.replaceChildren(link('Open '+scopedIssuer.name+' references',scopedIssuer.home));return;
      }
      countySelect.value=county.county;
      const heading=summary(label||(city?.name||'Unincorporated '+county.name+' County'),
                            (city?city.name:'Unincorporated area')+' · '+county.name+' County · '+coords(x,y));
      const share=button('Copy location link',async()=>{try{await navigator.clipboard.writeText(location.href);share.textContent='Link copied';}catch{share.textContent='Copy the address bar URL';}});
      heading.append(share);
      const agencies=section('Standards for this location');agencies.append(sources(scopedIssuer?[scope]:referenceKeys(city,county)));
            const selectedTopic=topicSelect.value;
      if(selectedTopic&&!scope)agencies.append(link('Compare guidance across agencies · '+topics[selectedTopic],base+'/topics/'+selectedTopic+'/'));
      if(!scope&&city&&!Object.values(profiles).some(p=>p.place===city.id))agencies.append(node('p','City collection not indexed. County publications above cover county work.'));
      panel.replaceChildren(agencies);
      const found=await request('identify',{x,y,counties:candidates.map(p=>p.county)});
      if(ticket!==locationTicket)return;
      const roads=section('Reported road ownership','FHWA HPMS 2024 · centerlines within 40 m');
      if(!found.roads.some(r=>scope!=='caltrans'||r.owner===1))roads.append(node('p','No ownership record within 40 m. Confirm the segment with the reviewing agency.'));
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
      roads.append(link('Ownership source',m.sources.ownership.url));panel.append(roads);
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
      if(!operators.size)transit.append(node('p','No matching stop records in this radius in the source snapshot.'));
      transit.append(link('Stop inventory source',m.sources.transit.url));panel.append(transit);
    }catch(e){if(ticket===locationTicket)panel.append(node('p','Location lookup could not finish. '+e.message),button('Retry lookup',()=>choose(x,y,label,false,false)));}
    finally{if(ticket===locationTicket)panel.setAttribute('aria-busy','false');}
  }
  function displayResults(items){
    const list=$('results');list.replaceChildren();
    if(!items.length){list.append(node('p','No matches. Try a street name, a city, a stop, or two streets separated by &.'));return;}
    const ul=node('ul');
    for(const item of items){
      const li=node('li'),place=lookup.get(item.place),b=button(item.label,()=>{
        list.replaceChildren();
        if(item.street){
          const ticket=++findTicket;list.textContent='Finding intersections on '+item.label+'…';
          request('onStreet',{street:item.street,county:countySelect.value,place:item.place}).then(rows=>{
            if(ticket===findTicket)displayResults(rows);
          }).catch(e=>{if(ticket===findTicket)list.textContent=e.message;});return;
        }
        if(item.area){countySelect.value=item.area.county;fit(item.area);choose(item.x,item.y,item.label,false);}
        else choose(item.x,item.y,item.label);
      });b.append(node('small',[item.type,place?.name,item.agency].filter(Boolean).join(' · ')));li.append(b);ul.append(li);
    }
    list.append(ul);
  }
  function findCity(name){const t=norm(name);return cities.find(c=>norm(c.name)===t || (c.name==='San Buenaventura' && t==='ventura'));}
  root.querySelector('form').onsubmit=async e=>{
    e.preventDefault();const ticket=++findTicket,query=$('query').value.trim();
    if(!query)return;
    const xy=query.match(/^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/);
    if(xy){const a=+xy[1],b=+xy[2],x=a<0?a:b,y=a<0?b:a;if(Math.abs(x)>180||Math.abs(y)>90){$('results').textContent='Enter valid longitude and latitude.';return;}$('results').replaceChildren();choose(x,y);return;}
    const pieces=query.split(',').map(s=>s.trim());const city=pieces.length>1?findCity(pieces.at(-1)):null;
    if(pieces.length>1 && !city){$('results').textContent='City qualifier not found. Select a county or use an incorporated city name.';return;}
    if(city && scopedIssuer && ((scopedIssuer.place&&city.id!==scopedIssuer.place)||(scopedIssuer.county&&city.county!==scopedIssuer.county))){
      $('results').textContent='This city is outside '+scopedIssuer.name+' coverage.';return;
    }
    if(city)countySelect.value=city.county;
    const exact=findCity(query);
    if(exact && scopedIssuer && ((scopedIssuer.place&&exact.id!==scopedIssuer.place)||(scopedIssuer.county&&exact.county!==scopedIssuer.county))){
      $('results').textContent='This city is outside '+scopedIssuer.name+' coverage.';return;
    }
    if(exact){displayResults([{area:exact,x:exact.center[0],y:exact.center[1],label:exact.name,type:'City boundary'}]);return;}
    const term=city?pieces.slice(0,-1).join(', '):query;
    $('results').textContent='Searching '+m.countyLayers[countySelect.value].name+' County…';
    const matchedCities=city?[]:cities.filter(c=>(!scopedIssuer?.place||c.id===scopedIssuer.place)&&(!scopedIssuer?.county||c.county===scopedIssuer.county)&&norm(c.name).startsWith(norm(term))).slice(0,8).map(c=>({area:c,x:c.center[0],y:c.center[1],label:c.name,type:'City boundary · '+m.countyLayers[c.county].name+' County'}));
    try{const items=await request('search',{query:term,county:countySelect.value,place:scopedIssuer?.place||city?.id});
      if(ticket===findTicket)displayResults([...matchedCities,...items]);
    }catch(e){if(ticket===findTicket)$('results').textContent='Search unavailable. '+e.message;}
  };
  function selectCounty(){
    findTicket++;locationTicket++;current=null;$('results').replaceChildren();selectedLayer.clearLayers();if(pin){pin.remove();pin=null;}
    const county=counties.find(c=>c.county===countySelect.value);
    const next=new URL(location.href);for(const k of ['lat','lon','z','issuer'])next.searchParams.delete(k);next.searchParams.set('county',county.county);
    history.pushState(null,'',next);overview(county);
  }
  function restore(){
    const u=new URL(location.href);topicSelect.value=u.searchParams.get('topic')||'';const x=parseFloat(u.searchParams.get('lon')),y=parseFloat(u.searchParams.get('lat'));
    if(Number.isFinite(x)&&Number.isFinite(y)&&Math.abs(x)<=180&&Math.abs(y)<=90){
      const z=Math.max(6,Math.min(19,parseInt(u.searchParams.get('z'),10)||16));map.setView([y,x],z);choose(x,y,'',false,false);
    }else{
      locationTicket++;current=null;selectedLayer.clearLayers();if(pin){pin.remove();pin=null;}
      const issuer=profiles[scope||u.searchParams.get('issuer')],code=issuer?.county||(m.countyLayers[u.searchParams.get('county')]&&u.searchParams.get('county'))||'037';
      countySelect.value=code;overview(issuer||u.searchParams.has('county')?counties.find(c=>c.county===code):null,issuer);
    }
  }
  map.on('click',e=>choose(e.latlng.lng,e.latlng.lat,'',false));map.on('moveend',refreshLayers);
  for(const layer of ['cities','stops','highways'])$(layer).onchange=refreshLayers;
  $('basemap').onchange=setBase;countySelect.onchange=selectCounty;
  topicSelect.onchange=()=>{
    const u=new URL(location.href);
    if(topicSelect.value)u.searchParams.set('topic',topicSelect.value);else u.searchParams.delete('topic');
    history.pushState(null,'',u);
    if(current)choose(current.x,current.y,current.label,false,false);
    else {
      const issuer=profiles[scope||u.searchParams.get('issuer')];
      overview(issuer||u.searchParams.has('county')?counties.find(c=>c.county===countySelect.value):null,issuer,false);
    }
  };
  window.addEventListener('popstate',restore);
  restore();setBase();new ResizeObserver(()=>map.invalidateSize({pan:false})).observe($('map'));
}
start().catch(e=>{$('summary').textContent='Map unavailable. '+e.message;$('context').append(link('Browse the jurisdiction directory',base+'/regions/'));});
