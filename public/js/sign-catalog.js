(() => {
  if(new URLSearchParams(location.search).get('import')==='1') {
    const host=document.createElement('section');host.id='sign-import-root';
    const chart=document.querySelector('.sign-chart-actions')||document.getElementById('sfilter');
    if(chart) {
      chart.before(host);
      const css=document.createElement('link');css.rel='stylesheet';
      css.href=new URL('sign-import.css',document.currentScript.src);document.head.append(css);
      import(new URL('sign-import.mjs',document.currentScript.src).href).catch(()=>{
        host.textContent='Could not load the sign importer. Reload this page to try again.';
      });
    }
  }
  const input=document.getElementById('sq'), status=document.getElementById('sca');
  const origin=document.getElementById('sorigin'), count=document.getElementById('scount');
  const dwgOnly=document.getElementById('chart-dwg-only');
  if(!input||!origin)return;
  const buttons=[...document.querySelectorAll('.sbtns button')];
  const compact=s=>s.toLowerCase().replace(/[^a-z0-9]/g,'');
  const key=window.SSSSearch?.designation || (text=>text.trim().toUpperCase());
  const exactRows=new Map();
  const rows=[...document.querySelectorAll('.scard')].map(card=>{
    const codes=[card.dataset.code,...(card.dataset.aliases||'').split('|')].filter(Boolean);
    const row={card,codes:codes.map(compact),words:(card.dataset.name||'').toLowerCase(),
      group:card.closest('.sseries'),category:card.dataset.cat,california:card.dataset.ca==='ca',
      origins:new Set(['cad','plan','mod','dwg'].filter(id=>card.dataset[id]==='1'))};
    for(const id of new Set(codes.map(key))){
      if(!exactRows.has(id))exactRows.set(id,[]);
      exactRows.get(id).push(row);
    }
    return row;
  });
  const headings=[...document.querySelectorAll('.sgroup')], sections=[...document.querySelectorAll('.sseries')];
  const setHidden=(el,hidden)=>{if(el.hidden!==hidden)el.hidden=hidden;};
  const params=new URLSearchParams(location.search);
  input.value=params.get('q')||'';status.checked=params.get('ca')==='1';
  origin.value=params.get('origin')||'';if(!origin.value)origin.selectedIndex=0;
  let category=buttons.find(b=>b.dataset.f===params.get('cat'))?.dataset.f||'all';
  const toolbar=document.getElementById('sfilter'),filters=document.getElementById('sign-filter-options');
  if(status.checked||origin.value||category!=='all')filters.open=true;
  toolbar.hidden=false;
  function run(){
    const phrase=input.value.trim().toLowerCase(), exact=key(phrase);
    const terms=phrase.split(/\s+/).filter(Boolean).map(word=>({word,compactWord:compact(word)}));
    const ca=status.checked, kind=origin.value;
    if(dwgOnly)dwgOnly.checked=kind==='dwg';
    const eligible=r=>(category==='all'||r.category===category)&&(!ca||r.california)&&(!kind||r.origins.has(kind));
    const literal=exactRows.get(exact)?.filter(eligible);
    const strict=literal?.length?new Set(literal):null;
    const groups=new Set(),categories=new Map();
    let visible=0;
    for(const row of rows){
      const match=strict?strict.has(row):eligible(row)&&terms.every(({word,compactWord})=>
        row.words.includes(word)||(compactWord.length>=2&&row.codes.some(code=>code.includes(compactWord))));
      setHidden(row.card,!match);
      if(match){visible++;groups.add(row.group);categories.set(row.category,(categories.get(row.category)||0)+1);}
    }
    for(const section of sections)setHidden(section,!groups.has(section));
    for(const heading of headings){
      setHidden(heading,!categories.has(heading.id));
      const badge=heading.querySelector('.count');
      if(badge && categories.has(heading.id))badge.textContent=String(categories.get(heading.id));
    }
    for(const b of buttons){const on=b.dataset.f===category;b.classList.toggle('on',on);b.setAttribute('aria-pressed',String(on));}
    count.textContent=visible===rows.length?visible.toLocaleString()+' records':visible.toLocaleString()+' of '+rows.length.toLocaleString();
    const active=Number(Boolean(origin.value))+Number(status.checked)+Number(category!=='all');
    filters.querySelector('summary').textContent=active?'Filters ('+active+')':'Filters';
    const url=new URL(location.href);
    for(const [name,value] of Object.entries({q:input.value.trim(),cat:category==='all'?'':category,ca:status.checked?'1':'',origin:origin.value})){
      if(value)url.searchParams.set(name,value);else url.searchParams.delete(name);
    }
    history.replaceState(history.state,'',url);
  }
  for(const b of buttons)b.addEventListener('click',()=>{category=b.dataset.f;run();});
  input.addEventListener('input',run);origin.addEventListener('change',run);status.addEventListener('change',run);
  dwgOnly?.addEventListener('change',()=>{origin.value=dwgOnly.checked?'dwg':'';run();});
  run();
})();
