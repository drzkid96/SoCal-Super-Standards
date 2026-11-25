(() => {
  const base = '/SoCal-Super-Standards';
  const modes = window.__agencyCatalog;
  if (!modes) return;
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
  if(active && !inScope(location.href) && location.pathname!==searchPath){
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
        if(!inScope(a.href) && new URL(a.href).pathname!==searchPath) (a.closest('li')||a).hidden=true;
      });
      nav.querySelectorAll('details').forEach(d=>{if(![...d.querySelectorAll('a')].some(a=>!a.closest('[hidden]')))d.hidden=true;});
    });
    document.querySelectorAll('.title-wrapper a').forEach(a=>a.href=modes[active].home);
    document.querySelectorAll('main a[href]').forEach(a=>{
      const dest=new URL(a.href);
      if(dest.origin!==location.origin || !dest.pathname.startsWith(base+'/') || !dest.pathname.endsWith('/') || inScope(a.href) || dest.pathname===searchPath)return;
      const card=a.closest('figure,.dx-card,.pbig,.scard,li');
      if(card && !card.closest('.prov,.dtext'))card.hidden=true;
      else a.replaceWith(document.createTextNode(a.textContent));
    });
    const banner=document.createElement('nav');banner.className='mode-banner';
    const home=document.createElement('a');home.href=modes[active].home;home.textContent=modes[active].name+' workspace';
    const leave=document.createElement('button');leave.textContent='Show all agencies';leave.onclick=()=>change('');
    banner.append(home,leave);document.querySelector('main')?.prepend(banner);
    document.querySelectorAll('[data-set-mode],.sss-topnav,.right-group').forEach(e=>e.hidden=true);
    const searchLink=document.querySelector('.sss-search-link');
    if(searchLink)searchLink.setAttribute('aria-label','Search '+modes[active].name);
    const facets=document.querySelector('#standards-search select[name="source"]');
    if(facets){facets.value='';facets.hidden=true;document.querySelector('label[for=standards-source]')?.setAttribute('hidden','');}
  }
  document.querySelectorAll('[data-set-mode]').forEach(b=>b.onclick=()=>change(b.dataset.setMode));
  const browser=document.querySelector('.agency-browser');
  if(browser){
    const input=browser.querySelector('input'), list=browser.querySelector('ul'), count=browser.querySelector('[role=status]'), more=browser.querySelector('button');
    fetch(base+'/data/search-catalog.json').then(r=>r.json()).then(all=>{
      const entries=all.filter(([path])=>inScope(base+path,browser.dataset.agency)&&base+path!==modes[browser.dataset.agency].home);
      let limit=30;
      function display(){
        const terms=input.value.trim().toLowerCase().split(/\s+/);
        const found=entries.filter(([path,title,tag,keys])=>terms.every(t=>(title+' '+keys.join(' ')+' '+path).toLowerCase().includes(t)));
        list.replaceChildren();
        for(const [path,title] of found.slice(0,limit)){
          const li=document.createElement('li'),a=document.createElement('a');a.href=base+path;a.textContent=title;li.append(a);list.append(li);
        }
        count.textContent=found.length.toLocaleString()+' matching references';more.hidden=found.length<=limit;
      }
      input.oninput=()=>{limit=30;display();};more.onclick=()=>{limit+=30;display();};display();
    }).catch(()=>count.textContent='Collection index unavailable.');
  }
  const bar=document.querySelector('.reg-controls');
  if(bar){
    const pages=[...document.querySelectorAll('.reg-page')], select=bar.querySelector('select');
    pages.forEach(p=>select.add(new Option(p.dataset.label,p.id)));
    function draw(){
      const current=pages.find(p=>'#'+p.id===location.hash)||pages[0];
      pages.forEach(p=>p.hidden=p!==current);select.value=current.id;
      const n=pages.indexOf(current);
      bar.querySelector('[data-step="-1"]').disabled=n===0;bar.querySelector('[data-step="1"]').disabled=n===pages.length-1;
    }
    function go(id){history.pushState(null,'','#'+id);draw();}
    select.onchange=()=>go(select.value);
    bar.querySelectorAll('button').forEach(b=>b.onclick=()=>go(pages[select.selectedIndex+Number(b.dataset.step)].id));
    bar.hidden=false;draw();window.addEventListener('hashchange',draw);window.addEventListener('popstate',draw);
  }
})();
window.addEventListener('storage',event=>{
  if(event.key==='standards-agency'){
    const url=new URL(location.href);url.searchParams.delete('agency');location.replace(url.href);
  }
});
