(() => {
  const input=document.getElementById('sq'), status=document.getElementById('sca');
  const origin=document.getElementById('sorigin'), count=document.getElementById('scount');
  if(!input||!origin)return;
  const buttons=[...document.querySelectorAll('.sbtns button')];
  const compact=s=>s.toLowerCase().replace(/[^a-z0-9]/g,'');
  const key=window.SSSSearch?.designation || (text=>text.trim().toUpperCase());
  const rows=[...document.querySelectorAll('.scard')].map(card=>{
    const codes=[card.dataset.code,...(card.dataset.aliases||'').split('|')].filter(Boolean);
    return {card,keys:codes.map(key),codes:codes.map(compact),words:(card.dataset.name||'').toLowerCase()};
  });
  const headings=[...document.querySelectorAll('.sgroup')], sections=[...document.querySelectorAll('.sseries')];
  const params=new URLSearchParams(location.search);
  input.value=params.get('q')||'';status.checked=params.get('ca')==='1';
  origin.value=params.get('origin')||'';if(!origin.value)origin.selectedIndex=0;
  let category=buttons.find(b=>b.dataset.f===params.get('cat'))?.dataset.f||'all';
  const toolbar=document.getElementById('sfilter'),filters=document.getElementById('sign-filter-options');
  if(status.checked||origin.value||category!=='all')filters.open=true;
  toolbar.hidden=false;
  function run(){
    const phrase=input.value.trim().toLowerCase(), exact=key(phrase);
    const words=phrase.split(/\s+/).filter(Boolean);
    const eligible=card=>(category==='all'||card.dataset.cat===category)&&(!status.checked||card.dataset.ca==='ca')
      &&(!origin.value||card.dataset[origin.value]==='1');
    const strict=rows.some(r=>eligible(r.card)&&r.keys.includes(exact));
    let visible=0;
    for(const {card,keys,codes,words:hay} of rows){
      const match=strict?keys.includes(exact):words.every(w=>hay.includes(w)||
        compact(w).length>=2&&codes.some(code=>code.includes(compact(w))));
      const ok=match&&eligible(card);
      card.hidden=!ok;if(ok)visible++;
    }
    for(const section of sections)section.hidden=!section.querySelector('.scard:not([hidden])');
    for(const h of headings){
      let next=h.nextElementSibling,any=false;
      while(next&&!next.classList.contains('sgroup')){
        if(next.classList.contains('sseries')&&!next.hidden)any=true;
        next=next.nextElementSibling;
      }
      h.hidden=!any;
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
  run();
})();
