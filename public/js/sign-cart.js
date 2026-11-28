/* One ordered legend per plan sheet; a native block can occur on several sheets. */
(() => {
  if (window.SSSSignCart) return;
  const base='/SoCal-Super-Standards', key='sss-sign-legends-v2', manual='@manual';
  const shell=document.querySelector('[data-sign-cart]'), pick=name=>shell?.querySelector('['+name+']');
  const dialog=pick('data-cart-dialog'), count=pick('data-cart-count'), open=pick('data-cart-open');
  const items=pick('data-cart-items'), status=pick('data-cart-status'), clear=pick('data-cart-clear'), download=pick('data-cart-download');
  const grid=pick('data-legend-grid'), preview=pick('data-legend-preview'), caption=pick('data-legend-caption');
  const previous=pick('data-legend-prev'), next=pick('data-legend-next'), pdf=pick('data-cart-pdf');
  const layoutKey='sss-sign-legend-layout-v1', fields={title:pick('data-layout-title'),columns:pick('data-layout-columns'),
    rows:pick('data-layout-rows'),page:pick('data-layout-page'),cellScale:pick('data-layout-scale')};
  const whole=(v,lo,hi,d)=>{const n=Math.round(Number(v));return Number.isFinite(n)?Math.max(lo,Math.min(hi,n)):d;};
  // One layout drives the preview, the DWG legend tables and the PDF chart.
  function layout(){
    return {title:(fields.title?.value||'').trim(),columns:whole(fields.columns?.value,1,8,2),rows:whole(fields.rows?.value,1,24,14),
      page:fields.page?.value||'tabloid-landscape',cellScale:Number(fields.cellScale?.value)||1};
  }
  const perTable=()=>{const l=layout();return l.columns*l.rows;};
  const fileStem=fallback=>{const t=layout().title.toUpperCase().replace(/[^A-Z0-9]+/g,'-').replace(/^-|-$/g,'');return t||fallback;};
  const nodes=new Map();
  for(const input of document.querySelectorAll('input[data-cart-select]')){
    const id=input.dataset.cartSelect;
    if(!nodes.has(id))nodes.set(id,[]);
    nodes.get(id).push(input);
  }
  let groups=[],selected=new Set(),catalog,catalogRequest,busy=false,persistent=true,tableIndex=0;
  const idsOf=group=>group.records.map(r=>typeof r==='string'?r:r?.id).filter(id=>typeof id==='string'&&id);
  const cleaned=list=>(Array.isArray(list)?list:[]).filter(g=>g&&typeof g.sheetId==='string'&&Array.isArray(g.records))
    .map(g=>({sheetId:g.sheetId,label:String(g.label||g.sheetId),records:[...new Set(idsOf(g))]})).filter(g=>g.records.length);
  // Every legend is kept in sign-code order (R1-1, R1-2, R1-10P, R2-1 ...), so charts are always alphabetized.
  const natural=code=>String(code).toUpperCase().match(/\d+|[^\d]+/g)||[];
  function compareCodes(a,b){
    const x=natural(a),y=natural(b);
    for(let i=0;i<Math.max(x.length,y.length);i++){
      if(x[i]===undefined)return -1;if(y[i]===undefined)return 1;
      const nx=/^\d/.test(x[i]),ny=/^\d/.test(y[i]);
      if(nx&&ny&&+x[i]!==+y[i])return +x[i]-+y[i];
      if(nx!==ny)return nx?-1:1;
      if(x[i]!==y[i])return x[i]<y[i]?-1:1;
    }
    return 0;
  }
  const codeOf=id=>catalog?.get(id)?.code||id;
  const alphabetize=list=>list.map(g=>({...g,records:[...g.records].sort((a,b)=>compareCodes(codeOf(a),codeOf(b))||compareCodes(a,b))}));
  function stored(){
    if(!persistent)return cleaned(groups);
    try{
      const saved=localStorage.getItem(key);
      if(saved!==null)return cleaned(JSON.parse(saved));
      return cleaned([{sheetId:manual,label:'Manual selection',records:JSON.parse(localStorage.getItem('sss-selected-sign-dwgs-v1')||'[]')}]);
    }catch{return cleaned(groups);}
  }
  function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
  function button(text,title){
    const b=el('button',text);b.type='button';b.setAttribute('aria-label',title);return b;
  }
  async function options(){
    if(catalog)return catalog;
    if(!catalogRequest)catalogRequest=fetch(base+'/data/sign-block-options.json').then(response=>{
      if(!response.ok)throw Error('The sign file list could not load. Try again.');
      return response.json();
    }).then(records=>catalog=new Map(records.map(r=>[r.id,r]))).catch(error=>{catalogRequest=null;throw error;});
    return catalogRequest;
  }
  function tablesFor(list){
    const tables=[];
    for(const group of list){
      const size=perTable();
      for(let i=0;i<group.records.length;i+=size)tables.push({group,records:group.records.slice(i,i+size),number:1+i/size,total:Math.ceil(group.records.length/size)});
    }
    return tables;
  }
  function drawPreview(){
    const tables=tablesFor(groups);
    preview.hidden=!tables.length;if(!tables.length){grid.replaceChildren();return;}
    tableIndex=Math.max(0,Math.min(tables.length-1,tableIndex));
    const t=tables[tableIndex], fragment=document.createDocumentFragment();
    const l=layout();grid.style.gridTemplateColumns='repeat('+l.columns+',minmax(0,1fr))';
    caption.textContent=(l.title||(t.group.sheetId===manual?'Sign legend':t.group.label))+' · Table '+t.number+' of '+t.total+' · '+l.columns+' × '+l.rows;
    for(let i=0;i<l.columns*l.rows;i++){
      const cell=el('div');cell.dataset.legendCell=String(i+1);
      if(i<t.records.length){
        const id=t.records[i],record=catalog?.get(id);cell.dataset.recordId=id;cell.title=record?.code||id;
        if(record?.preview){const image=el('img');image.src=base+record.preview;image.alt='';cell.append(image);}
        cell.append(el('span',record?.code||'…'));
      }else cell.setAttribute('aria-hidden','true');
      fragment.append(cell);
    }
    grid.replaceChildren(fragment);pick('data-legend-nav').hidden=tables.length===1;
    previous.disabled=tableIndex===0;next.disabled=tableIndex===tables.length-1;
  }
  function review(){
    if(!dialog?.open)return;
    const fragment=document.createDocumentFragment();
    for(const group of groups){
      if(groups.length>1 || group.sheetId!==manual){
        const heading=el('li',group.label);heading.className='cart-sheet-heading';fragment.append(heading);
      }
      group.records.forEach((id,index)=>{
        const r=catalog?.get(id),li=el('li');
        li.dataset.group=group.sheetId;li.dataset.recordId=id;
        const description=el('div');description.className='cart-line-label';
        description.append(el('strong',(index+1)+'. '+(r?.code||id)),
          el('small',r?[r.sizeLabel,r.variant].filter(Boolean).join(' · '):(catalog?'Drawing unavailable in this edition':'Loading drawing…')));
        const controls=el('div');controls.className='cart-line-controls';
        for(const [action,text,label,disabled] of [['remove','×','Remove',false]]){
          const b=button(text,label+' · '+(r?.code||id)+' · '+group.label);b.setAttribute('data-cart-'+action,id);b.title=label;b.disabled=busy||disabled;controls.append(b);
        }
        li.append(description,controls);fragment.append(li);
      });
    }
    items.replaceChildren(fragment);drawPreview();
    pick('data-cart-order-label').hidden=!selected.size;
    clear.disabled=busy||!selected.size;download.disabled=busy||!selected.size||Boolean(catalog&&[...selected].some(id=>!catalog.has(id)));
    if(pdf)pdf.disabled=download.disabled;
    if(!selected.size)status.textContent='No signs selected.';
  }
  function sync(updated){
    const live=cleaned(updated),ids=new Set(live.flatMap(g=>g.records));
    const manualIds=new Set(live.find(g=>g.sheetId===manual)?.records);
    for(const id of new Set([...selected,...ids]))for(const input of nodes.get(id)||[]){
      input.checked=manualIds.has(id);input.indeterminate=ids.has(id)&&!manualIds.has(id);
      input.title=input.indeterminate?'On an imported sheet. Edit its placement in Selected signs.':'';
    }
    groups=live;selected=ids;
    if(count){const placements=groups.reduce((s,g)=>s+g.records.length,0);count.textContent=String(placements);open.setAttribute('aria-label','Review sign legend ('+placements+' placements)');}
    review();
  }
  function store(updated){
    const live=alphabetize(cleaned(updated));
    try{localStorage.setItem(key,JSON.stringify(live));}catch{persistent=false;}
    if(status)status.textContent='';
    sync(live);
  }
  function toggle(id,on){
    const list=stored();
    if(on){
      let g=list.find(x=>x.sheetId===manual);if(!g){g={sheetId:manual,label:'Manual selection',records:[]};list.unshift(g);}
      if(!g.records.includes(id))g.records.push(id);
    }else {
      const g=list.find(x=>x.sheetId===manual);
      if(g)g.records=g.records.filter(x=>x!==id);
    }
    store(list);
  }
  async function show(){
    if(!dialog){location.assign(base+'/signs/?cart=1');return;}
    status.textContent='';if(!dialog.open)dialog.showModal();review();
    try{await options();store(stored());}catch(error){status.textContent=error.message;}
  }
  async function importGroups(input,{mode='merge',open:openCart=true}={}){
    if(!['merge','replace'].includes(mode))throw Error('Choose merge or replace.');
    const incoming=cleaned(input),valid=await options();
    if(!incoming.length)throw Error('Choose at least one sign to import.');
    const unknown=incoming.flatMap(g=>g.records).find(id=>!valid.has(id));
    if(unknown)throw Error('Drawing unavailable: '+unknown);
    const list=mode==='replace'?[]:stored();
    for(const g of incoming){
      if(g.sheetId===manual)throw Error('Use a sheet identifier for imported signs.');
      const existing=list.find(x=>x.sheetId===g.sheetId);
      if(existing){existing.records=[...new Set([...existing.records,...g.records])];existing.label=g.label;}
      else list.push(g);
    }
    tableIndex=0;store(list);if(openCart)await show();
    return cleaned(groups);
  }
  window.SSSSignCart={importGroups,getGroups:()=>cleaned(stored()),open:show};
  window.addEventListener('storage',e=>{if(e.key===key||e.key===null)sync(stored());});
  window.addEventListener('pageshow',()=>sync(stored()));
  window.dispatchEvent(new Event('sss-sign-cart-ready'));
  sync(stored());if(!shell)return;
  document.addEventListener('change',e=>{const input=e.target.closest('input[data-cart-select]');if(input)toggle(input.dataset.cartSelect,input.checked);});
  open.addEventListener('click',show);pick('data-cart-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>open.focus({preventScroll:true}));
  previous.addEventListener('click',()=>{tableIndex--;drawPreview();});next.addEventListener('click',()=>{tableIndex++;drawPreview();});
  items.addEventListener('click',e=>{
    const b=e.target.closest('button'),row=b?.closest('li[data-group]');if(!row||busy)return;
    const list=stored(),g=list.find(x=>x.sheetId===row.dataset.group);if(!g)return;
    const current=g.records.indexOf(row.dataset.recordId);if(current<0)return;
    const remove=b.hasAttribute('data-cart-remove'),to=current+(b.hasAttribute('data-cart-earlier')?-1:1);
    if(remove)g.records.splice(current,1);
    else if(to>=0 && to<g.records.length)[g.records[current],g.records[to]]=[g.records[to],g.records[current]];
    if(!remove){
      const size=perTable(),offset=list.slice(0,list.indexOf(g)).reduce((s,x)=>s+Math.ceil(x.records.length/size),0);
      tableIndex=offset+Math.floor(to/size);
    }
    store(list);
    const rows=[...items.querySelectorAll('li[data-group]')].filter(x=>x.dataset.group===g.sheetId);
    const focus=rows[Math.max(0,Math.min(rows.length-1,remove?current:to))];
    (focus?.querySelector('button:not([disabled])')||pick('data-cart-close')).focus({preventScroll:true});
  });
  clear.addEventListener('click',()=>{if(!busy){tableIndex=0;store([]);}});
  async function exportLegend(kind){
    if(busy||!selected.size)return;
    const snapshot=cleaned(groups),settings=layout();busy=true;review();
    status.textContent=kind==='pdf'?'Preparing PDF chart…':'Preparing sign legend…';
    try{
      const catalog=await options(),ordered=alphabetize(snapshot).map(g=>({...g,records:g.records.map(id=>catalog.get(id))}));
      const records=[...new Set(ordered.flatMap(g=>g.records))];if(records.some(r=>!r))throw Error('Remove unavailable drawings and try again.');
      const blob=await window.SSSBuildSignZip(records,(n,total)=>{status.textContent='Preparing legend · '+n+' of '+total+' drawing files';},ordered,settings,kind);
      const objectURL=URL.createObjectURL(blob),a=el('a');
      a.download=kind==='pdf'?fileStem('SIGN-LEGEND-CHART')+'.pdf':fileStem('LADOT-SIGN-LEGEND')+'.zip';a.href=objectURL;document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(objectURL),60000);
      status.textContent=kind==='pdf'?'Downloaded the PDF sign chart.':'Downloaded the sign legend and '+records.length+' individual DWG'+(records.length===1?'':'s')+'.';
    }catch(error){status.textContent='Download failed. '+(error?.message||'Try again.');}finally{busy=false;review();}
  }
  download.addEventListener('click',()=>exportLegend('dwg'));
  pdf?.addEventListener('click',()=>exportLegend('pdf'));
  try{const saved=JSON.parse(localStorage.getItem(layoutKey)||'{}');for(const [k,f] of Object.entries(fields))if(f&&saved[k]!==undefined)f.value=saved[k];}catch{}
  for(const f of Object.values(fields))f?.addEventListener('input',()=>{
    try{localStorage.setItem(layoutKey,JSON.stringify(layout()));}catch{}
    tableIndex=0;drawPreview();
  });
  shell.hidden=false;sync(stored());
  if(new URL(location.href).searchParams.get('cart')==='1')show();
})();
