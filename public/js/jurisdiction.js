(() => {
  const base = '/SoCal-Super-Standards';
  const modes = window.__agencyCatalog;
  if (!modes) return;
  for (const control of document.querySelectorAll('[data-pref]')) {
    const key=control.dataset.pref;
    const apply=()=>document.documentElement.dataset['reader'+key]=control.value;
    try { const saved=localStorage.getItem('display-'+key); if([...control.options].some(o=>o.value===saved))control.value=saved; } catch {}
    apply();control.onchange=()=>{apply();try{localStorage.setItem('display-'+key,control.value);}catch{}};
  }
  const store = 'standards-agency';
  const url = new URL(location.href);
  let active = url.searchParams.get('agency');
  try { if (active === null) active = localStorage.getItem(store); } catch {}
  if (!Object.hasOwn(modes, active)) active = '';
  const inScope = (href, key=active) => {
    if (!key) return true;
    const dest = new URL(href, location.href);
    if (dest.origin !== location.origin || !dest.pathname.startsWith(base+'/')) return false;
    const path = dest.pathname.slice(base.length);
    return modes[key].roots.some(prefix => path.startsWith(prefix));
  };
  window.SSSAgency = {active, inScope};
  function change(key) {
    if (key && !Object.hasOwn(modes,key)) return;
    try { if (key) localStorage.setItem(store,key); else localStorage.removeItem(store); } catch {}
    location.assign((key ? modes[key].home : base+'/regions/')+'?agency='+encodeURIComponent(key));
  }
  if (url.searchParams.has('agency')) {
    try { if(active)localStorage.setItem(store,active);else localStorage.removeItem(store); } catch {}
  }
  const searchPath=base+'/search/';
  const mapPath=base+'/map/';
  if(active && !inScope(location.href) && location.pathname!==searchPath && !location.pathname.startsWith(mapPath)){
    location.replace(modes[active].home+'?agency='+encodeURIComponent(active)); return;
  }
  const select=document.querySelector('#agency-mode');
  if(select){
    for(const [key,m] of Object.entries(modes).sort((a,b)=>a[1].name.localeCompare(b[1].name)))select.add(new Option(m.name,key));
    select.value=active;select.addEventListener('change',()=>change(select.value));
  }
  if(active){
    document.documentElement.dataset.agencyMode=active;
    const hue=[...active].reduce((a,c)=>(a*31+c.charCodeAt(0))%360,0);
    document.documentElement.style.setProperty('--agency-hue',String(hue));
    document.title=modes[active].name+' · '+document.title;
    document.querySelectorAll('.sss-topnav,.sidebar-content,.right-sidebar-panel nav,.sss-pager').forEach(nav=>{
      nav.querySelectorAll('a[href]').forEach(a=>{
        if(!inScope(a.href) && new URL(a.href).pathname!==searchPath && !new URL(a.href).pathname.startsWith(mapPath)) (a.closest('li')||a).hidden=true;
      });
      nav.querySelectorAll('details').forEach(d=>{if(![...d.querySelectorAll('a')].some(a=>!a.closest('[hidden]')))d.hidden=true;});
    });
    document.querySelectorAll('.title-wrapper a').forEach(a=>a.href=modes[active].home);
    document.querySelectorAll('main a[href]').forEach(a=>{
      const dest=new URL(a.href);
      if(dest.origin!==location.origin || !dest.pathname.startsWith(base+'/') || !dest.pathname.endsWith('/') || inScope(a.href) || dest.pathname===searchPath || dest.pathname.startsWith(mapPath))return;
      const card=a.closest('figure,.dx-card,.pbig,.scard,li');
      if(card && !card.closest('.prov,.dtext'))card.hidden=true;
      else a.replaceWith(document.createTextNode(a.textContent));
    });
    const label=document.querySelector('[data-workspace-name]');
    if(label)label.textContent=modes[active].name;
    const preferences=label?.closest('details');
    if(preferences){
      const home=document.createElement('a');home.href=modes[active].home;home.textContent=modes[active].name+' standards';
      preferences.querySelector('.nav-dropdown').prepend(home);
    }
    document.querySelectorAll('[data-set-mode]').forEach(e=>e.hidden=true);
    const searchLink=document.querySelector('.sss-search-link');
    if(searchLink)searchLink.setAttribute('aria-label','Search '+modes[active].name);
    const facets=document.querySelector('#standards-search select[name="source"]');
    if(facets){facets.value='';facets.hidden=true;document.querySelector('label[for=standards-source]')?.setAttribute('hidden','');}
  }
  document.querySelectorAll('[data-set-mode]').forEach(b=>b.onclick=()=>change(b.dataset.setMode));
  const browser=document.querySelector('.agency-browser');
  if(browser){
    const input=browser.querySelector('input'), list=browser.querySelector('ul');
    const count=browser.querySelector('[role=status]'), more=browser.querySelector('button');
    const browseLabel=more.textContent;
    let request, limit=12, browsed=false;

    function collection(){
      if(!request)request=fetch(base+'/data/collections/'+browser.dataset.agency+'.json')
        .then(r=>{if(!r.ok)throw new Error('Index unavailable');return r.json();})
        .then(rows=>rows.filter(([path])=>inScope(base+path,browser.dataset.agency)&&base+path!==modes[browser.dataset.agency].home))
        .catch(error=>{request=undefined;throw error;});
      return request;
    }
    async function display(){
      if(!input.value.trim() && !browsed){
        list.replaceChildren();count.textContent='';more.hidden=false;more.textContent=browseLabel;return;
      }
      try{
        const entries=await collection();
        const words=input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
        if(!words.length && !browsed)return;
        const found=entries.filter(([path,title,tag,keys])=>words.every(t=>(title+' '+keys.join(' ')+' '+path).toLowerCase().includes(t)));
        list.replaceChildren(...found.slice(0,limit).map(([path,title])=>{
          const li=document.createElement('li'),a=document.createElement('a');a.href=base+path;a.textContent=title;li.append(a);return li;
        }));
        count.textContent=found.length ? 'Showing '+Math.min(limit,found.length)+' of '+found.length.toLocaleString() : 'No matching references';
        more.textContent='Show more';more.hidden=found.length<=limit;
      }catch{
        count.textContent='Collection index unavailable.';more.hidden=false;more.textContent='Retry';
      }
    }
    input.oninput=()=>{limit=12;browsed=false;display();};
    more.onclick=()=>{if(browsed||input.value.trim())limit+=12;browsed=true;display();};
  }
  const bar=document.querySelector('.reg-controls');
  if(bar){
    const pages=[...document.querySelectorAll('.reg-page')], select=bar.querySelector('select');
    const filter=document.createElement('input');filter.type='search';filter.placeholder='Find a sheet or phrase';filter.ariaLabel=filter.placeholder;
    const matches=document.createElement('span');matches.setAttribute('role','status');bar.prepend(filter,matches);
    const records=pages.map(page=>({page,words:page.textContent.toLowerCase()}));
    function filterList(){
      const words=filter.value.toLowerCase().trim().split(/\s+/);
      const rows=records.filter(row=>words.every(w=>row.words.includes(w)));
      select.replaceChildren(...rows.map(({page})=>new Option(page.dataset.label,page.id)));
      matches.textContent=filter.value?rows.length+' matches':'';
      select.disabled=!rows.length;
      if(rows.some(({page})=>page===bar._current))select.value=bar._current.id;
      else if(rows.length && filter.value)go(rows[0].page.id);
    }
    filter.oninput=filterList;filterList();
    function draw(){
      const current=pages.find(p=>'#'+p.id===location.hash)||pages[0];
      (bar._current || pages[0]).hidden=true;
      current.hidden=false;bar._current=current;select.value=current.id;
      const scan=current.querySelector('.reg-scan');
      if(scan && !scan.firstElementChild){
        const im=new Image();im.src=scan.href;im.alt=scan.dataset.title;scan.replaceChildren(im);
      }
      if(!contact.hidden)showGrid();
      const n=pages.indexOf(current);
      bar.querySelector('[data-step="-1"]').disabled=n===0;bar.querySelector('[data-step="1"]').disabled=n===pages.length-1;
    }
    pages.forEach(p=>p.hidden=true);
    const contact=document.querySelector('.reg-contact'),overview=bar.querySelector('.reg-overview');
    function showGrid(){
      contact.replaceChildren();
      const start=Math.floor(pages.indexOf(bar._current)/12)*12;
      for(const page of pages.slice(start,start+12)){
        const card=document.createElement('a'),im=new Image();
        im.src=page.querySelector('.reg-scan').href;im.loading='lazy';im.alt='';
        card.href='#'+page.id;card.append(im,document.createTextNode(page.dataset.label));
        card.onclick=e=>{e.preventDefault();contact.hidden=true;overview.setAttribute('aria-expanded','false');go(page.id);};
        contact.append(card);
      }
    }
    overview.onclick=()=>{contact.hidden=!contact.hidden;overview.setAttribute('aria-expanded',String(!contact.hidden));if(!contact.hidden)showGrid();};
    function go(id){history.pushState(null,'','#'+id);draw();}
    select.onchange=()=>go(select.value);
    bar.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>go(pages[pages.indexOf(bar._current)+Number(b.dataset.step)].id));
    bar.hidden=false;draw();window.addEventListener('hashchange',draw);window.addEventListener('popstate',draw);
  }
})();
window.addEventListener('storage',event=>{
  if(event.key==='standards-agency'){
    const url=new URL(location.href);url.searchParams.delete('agency');location.replace(url.href);
  }
});
