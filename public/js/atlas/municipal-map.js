// The overview is deliberately independent of raster tiles and street/stop databases.
const major = new Set(['Los Angeles','Long Beach','Pasadena','Santa Ana','Irvine','Anaheim','Riverside','Ontario','San Bernardino','Palm Springs','Victorville','San Diego','Oceanside','Escondido','El Centro','Chula Vista','Oxnard','San Buenaventura (Ventura)','Lancaster','Temecula','Blythe']);
export function cityName(place) {
  return place.name.startsWith('San Buenaventura') ? 'Ventura (San Buenaventura)' : place.name;
}
export function drawMunicipalities({L,map,places,counties,outline,overview,land,boundaries,allowed,onCity,onCounty,onInspect,inspecting,onIssue}) {
  function pane(name,z){
    const layer=map.createPane(name);
    layer.style.zIndex=z;
    return name;
  }
  const landPane=pane('atlas-land',205), countyPane=pane('atlas-counties',210), cityPane=pane('atlas-municipalities',230), labelPane=pane('atlas-labels',430);
  map.getPane(labelPane).style.pointerEvents='none';
  const byId=new Map(places.map(p=>[p.id,p]));
  const shapes=new Map(), detailed=new Map();
  let selected='', aerial=false, minimal=true, revision=0;
  const region=land && L.geoJSON(land,{pane:landPane,interactive:false,style:{fillColor:'#f4f1e8',fillOpacity:1,stroke:false}}).addTo(map);
  const outlineLayer=L.geoJSON(outline,{pane:countyPane,bubblingMouseEvents:false,
    onEachFeature:(f,layer)=>layer.on('click',e=>inspecting()?onInspect(e.latlng):onCounty(f.properties.county))
  }).addTo(map);
  const labels=L.layerGroup().addTo(map);
  function style(id){
    if(id===selected)return {color:aerial?'#ffe7a2':'#075e50',weight:3,opacity:1,fillColor:aerial?'#e2be77':'#75b89e',fillOpacity:minimal?.74:.24};
    return {color:aerial?'#a5e3ca':'#729587',weight:map.getZoom()>9?1.35:.85,opacity:.93,fillColor:'#ccdfd3',fillOpacity:minimal?.76:.09};
  }
  function redraw(){
    revision++;
    if(region){if(minimal)region.addTo(map);else region.remove();}
    outlineLayer.setStyle({color:aerial?'#e4dcc6':'#76847e',weight:1.45,opacity:.85,dashArray:'5 3',fillColor:'#edece3',fillOpacity:minimal?.15:.015});
    for(const [id,layer] of shapes)layer.setStyle(style(id));
    if(selected)shapes.get(selected)?.bringToFront();
    labels.clearLayers();
    const size=map.getSize(),placed=[];
    function label(xy,text,cls,width,height=18){
      const pos=map.latLngToContainerPoint([xy[1],xy[0]]);
      if(pos.x<0||pos.x>size.x||pos.y<0||pos.y>size.y)return;
      const r=[pos.x-width/2-2,pos.y-height/2-2,pos.x+width/2+2,pos.y+height/2+2];
      if(placed.some(v=>r[0]<v[2]&&r[2]>v[0]&&r[1]<v[3]&&r[3]>v[1]))return;
      placed.push(r);
      const span=document.createElement('span');span.textContent=text;
      L.marker([xy[1],xy[0]],{pane:labelPane,icon:L.divIcon({html:span,className:cls,iconSize:[width,height],iconAnchor:[width/2,height/2]}),interactive:false,keyboard:false}).addTo(labels);
    }
    const zoom=map.getZoom(),cities=places.filter(p=>p.kind==='city'&&allowed(p));
    if(selected&&byId.has(selected)){const p=byId.get(selected);label(p.center,cityName(p),'atlas-city-label',cityName(p).length*7+12);}
    if(zoom<9)for(const c of counties)label(c.center,c.name+' County','atlas-county-label',(c.name.length+7)*7);
    if(minimal&&zoom<=9)label([-118.48,33.30],'Pacific Ocean','atlas-water-label',108);
    if(zoom>7)for(const p of cities.sort((a,b)=>Number(major.has(b.name))-Number(major.has(a.name))||a.name.localeCompare(b.name))){
      if(p.id===selected||zoom<10&&!major.has(p.name))continue;
      const text=cityName(p).split(' (')[0];label(p.center,text,'atlas-city-label',text.length*7+10);
    }
  }
  function addShape(feature,replace=false){
    const id=feature.properties.id,place=byId.get(id);
    if(!place||place.kind!=='city'||!allowed(place)||shapes.has(id)&&!replace)return;
    const previous=shapes.get(id);
    let layer;
    L.geoJSON(feature,{pane:cityPane,bubblingMouseEvents:false,smoothFactor:.6,style:()=>style(id),onEachFeature:(_,l)=>{layer=l;}});
    layer.addTo(map);
    const el=layer.getElement();
    if(el){el.dataset.city=id;el.setAttribute('aria-label',cityName(place));}
    const tooltip=document.createElement('span');tooltip.textContent=cityName(place);
    layer.bindTooltip(tooltip,{sticky:true,direction:'top'});
    layer.on('click',e=>inspecting()?onInspect(e.latlng):onCity(place));
    layer.on('mouseover',()=>layer.setStyle({weight:id===selected?3.5:2,color:aerial?'#fff3c9':'#286b57'}));
    layer.on('mouseout',()=>layer.setStyle(style(id)));
    if(previous)previous.remove();
    shapes.set(id,layer);
  }
  for(const f of overview.features)addShape(f);
  async function detail(){
    const ticket=revision;
    if(map.getZoom()<10 && overview.features.length)return;
    const viewport=map.getBounds();
    const inView=counties.filter(c=>viewport.intersects([[c.bbox[1],c.bbox[0]],[c.bbox[3],c.bbox[2]]]) && places.some(p=>p.kind==='city'&&p.county===c.county&&allowed(p)));
    await Promise.all(inView.map(async c=>{
      if(detailed.has(c.county))return;
      try{
        const data=await boundaries(c.county);
        if(ticket!==revision||detailed.has(c.county))return;
        for(const f of data.features)addShape(f,true);
        detailed.set(c.county,true);
        if(selected)shapes.get(selected)?.bringToFront();
      }catch{if(ticket===revision)onIssue('Detailed city limits are unavailable. The city list and standards links still work.');}
    }));
  }
  function update(){redraw();void detail();}
  map.attributionControl.addAttribution('<a href="https://gis.data.ca.gov/">California CDT/CDTFA</a> · <a href="https://www.naturalearthdata.com/">Natural Earth</a>');
  map.on('moveend',update);
  return {
    select(id){selected=id||'';update();},
    basemap(value){minimal=value==='local';aerial=value==='aerial';update();}
  };
}
