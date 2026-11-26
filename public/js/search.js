/* Shared title, identifier, and full-text retrieval for the site and reference drawer. */
(() => {
  const base = '/SoCal-Super-Standards';
  const clean = s => s.normalize('NFKD').toLowerCase().replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const compact = s => clean(s).replace(/ /g, '');
  // Hyphens distinguish California designations, e.g. G1-4(CA) and G14(CA).
  function designation(raw) {
    let id=raw.trim().toUpperCase().replace(/[–—−]/g,'-').replace(/\(([^()]*)\)/g,(_,part)=>{
      const word=part.trim().replace(/\s+/g,'-');
      return word==='CA'?'CA':'-'+word;
    }).replace(/[\s-]*\bMOD(?:IFIED)?\b[\s-]*/g,'-MOD-').replace(/([0-9A-Z])MOD(?=$|[ -])/g,'$1-MOD')
      .replace(/-(LT|RT)(?=-|$)/g,(_,side)=>side==='LT'?'-LEFT':'-RIGHT');
    if(/^(?:[A-Z]\.)+[A-Z]\.?$/.test(id))id=id.replaceAll('.','');
    return id.replace(/\s/g,'').replace(/^-+|-+$/g,'');
  }
  const urlFor = (q, source = '') => {
    const url = new URL(base + '/search/', location.origin);
    if (q.trim()) url.searchParams.set('q', q.trim());
    if (source) url.searchParams.set('source', source);
    return url.pathname + url.search;
  };
  let catalogPromise, fullPromise, sheetPromise;
  async function json(name) {
    const response = await fetch(base + '/data/' + name + '.json');
    if (!response.ok) throw Error('Search index unavailable');
    return response.json();
  }
  function catalog() {
    return catalogPromise ||= Promise.all([json(window.SSSAgency?.active ? 'collections/'+window.SSSAgency.active : 'search-catalog'), json('retired'), json('glossary')]).then(([rows, retired, glossary]) => {
      const records = rows.map(([path, label, tag, keys]) => ({
        url: base + path, label, tag, names: clean(label),
        hay: clean(label + ' ' + tag + ' ' + path.replaceAll('/', ' ') + ' ' + keys.join(' ')),
        keys: keys.map(compact), exact:keys.map(designation)
      }));
      const signIds=new Map();
      for(const row of records)if(row.tag==='Signs')for(const code of row.exact){
        if((/^[A-Z]{1,5}-?\d/.test(code)||row.url.includes('/signs/plan-')||row.url.includes('/signs/cad/#block-')||row.url.includes('#plan-'))&&!signIds.has(code))signIds.set(code,[]);
      }
      for(const row of records)for(const code of new Set(row.exact)){
        const found=signIds.get(code);
        if(found)found.push(row);
      }
      const withdrawn = new Map(Object.entries(retired.codes).map(([code, name]) =>
        [designation(code), {label: code + ' · ' + name + ' · Caltrans deletion notice', url: retired.source, tag: 'Retired', cls: 'sup'}]));
      const synonyms = new Map();
      for (const row of glossary) {
        for (const alias of row.aka) synonyms.set(clean(alias), clean(row.term));
      }
      return {records, withdrawn, synonyms, signIds};
    }).catch(error => { catalogPromise = null; throw error; });
  }
  const sources = [
    [/^sign\s+(?=[a-z]{1,4}-?\d)/i,'Signs'],
    [/^(?:california|ca)\s+mutcd\s+/i, 'CA MUTCD'], [/^(?:federal|fhwa)\s+mutcd\s+/i, 'Federal MUTCD'],
    [/^(?:la\s+)?boe\s+/i, 'LA BOE'], [/^ladot\s+/i, 'LADOT'], [/^caltrans\s+/i, 'Caltrans']
  ];
  function parse(raw, facet) {
    let query = raw.trim(), scope = facet;
    for (const [pattern, source] of sources) {
      if (pattern.test(query) && (!facet || facet === source)) {
        scope = source; query = query.replace(pattern, ''); break;
      }
    }
    query=query.replace(/^fig\.\s+/i,'Figure ');
    query = query.replace(/^(?:section|sec\.?|drawing|dwg\.?)\s+(?=\w*\d)/i, '');
    return {query, scope};
  }
  const sheetQualifier = /^(.+?)[\s,;]+(sheet|page|p\.)\s*#?\s*(\d+)$/i;
  async function findSheet(query, scope) {
    const request = query.match(sheetQualifier);
    if (!request) return [];
    sheetPromise ||= json('search-sheets').catch(error => { sheetPromise = null; throw error; });
    const key = compact(request[1]), bySheet = request[2].toLowerCase() === 'sheet';
    const number = Number(request[3]);
    const hits = [], available = [];
    for (const doc of await sheetPromise) {
      if (window.SSSAgency && !window.SSSAgency.inScope(base+doc.route)) continue;
      if ((scope && scope !== doc.tag) || !doc.keys.some(alias => compact(alias) === key)) continue;
      const index = bySheet ? number-1 : doc.sheets.findIndex(([,page]) => page === number);
      if (!doc.sheets[index]) {
        const note = bySheet ? 'Available sheets 1–'+doc.sheets.length : 'Page '+number+' is outside this drawing';
        available.push({tag:doc.tag, cls:'c', sheetMatch:true, missingSheet:true,
          label:doc.label+' · '+note, url:base+doc.route+'#'+doc.sheets[0][0]});
        continue;
      }
      const [anchor, page] = doc.sheets[index];
      hits.push({tag:doc.tag, cls:'c', sheetMatch:true, url:base+doc.route+'#'+anchor,
        label:doc.label+' · Sheet '+(index+1)+' of '+doc.sheets.length+' · p. '+page});
    }
    return hits.length ? hits : available;
  }
  async function direct(raw, facet = '', limit = 12, match = 'all', issuer = '') {
    let {query, scope} = parse(raw, facet);
    if (!query) return [];
    if (sheetQualifier.test(query)) {
      const sheets = await findSheet(query, scope);
      if (sheets.length) return sheets.filter(hit=>!issuer||window.SSSAgency.inScope(hit.url,issuer)).slice(0, limit);
    }
    const {records, withdrawn, synonyms, signIds} = await catalog();
    // A literal block name can itself begin with "SIGN ", e.g. SIGN SP-1.
    if ((!scope || scope==='Signs') && signIds.has(designation(raw))) query=raw.trim();
    const request = raw.trim().match(/^(?:DWG|CAD)\s+(.+)$|^(.+?)\s+(?:DWG|CAD)$/i);
    if (request && (!scope || scope==='Signs')) {
      const alias = 'CAD '+(request[1] || request[2]);
      if (signIds.has(designation(alias))) query = alias;
    }
    const code = compact(query), phrase = clean(query);
    if (!code) return [];
    const id=designation(query);
    const retired=!issuer && !window.SSSAgency?.active && (!scope || ['Caltrans','Signs','CA MUTCD'].includes(scope)) ? withdrawn.get(id) : null;
    const words = phrase.split(' '), expanded = synonyms.get(phrase);
    const signCode=signIds.has(id)||/^[A-Z]{1,5}-?\d/.test(id);
    const priority = {'CA MUTCD': 6, LADOT: 5, Caltrans: 5, 'LA BOE': 4};
    const hits = [];
    const pool=(!scope||scope==='Signs')&&signIds.has(id)?signIds.get(id):records;
    for (const record of pool) {
      if (window.SSSAgency && !window.SSSAgency.inScope(record.url)) continue;
      if (issuer && !window.SSSAgency.inScope(record.url,issuer))continue;
      if (scope && scope !== record.tag) continue;
      const exact=record.exact.includes(id);
      if(retired&&!(exact&&record.tag==='Signs'&&record.url.includes('/signs/plan-')))continue;
      if(match==='exact' && !exact && designation(record.label)!==id)continue;
      let score;
      if (exact) score = record.tag==='Signs' && signCode ? 155 : 135;
      else if (record.keys.includes(code)) score = 120;
      else if (record.names === phrase) score = 110;
      else if (record.names.includes(phrase)) score = 78;
      else if (words.every(w => record.hay.split(' ').some(term=>term===w || (w.length>=3 && term.startsWith(w))))) score = 55;
      else if (expanded && record.hay.includes(expanded)) score = 43;
      else if (code.length >= 2 && /\d/.test(code) && record.keys.some(k => k.startsWith(code))) score = 38;
      else continue;
      if (exact && request && record.label.includes(' · CAD from issued artwork · ')) score += 8;
      if (record.url.includes('/keywords/#')) score -= 10;
      if (record.url.includes('/topics/') && !/\d/.test(query)) score += 5;
      if (record.url.endsWith('/standard-plans/') && phrase === clean(record.url.split('/').at(-3))) score += 42;
      hits.push({signMatch:exact&&signCode&&record.tag==='Signs', exact, score: score+(priority[record.tag]||0), label:record.label, tag:record.tag, url:record.url, cls:'c'});
    }
    if(retired)hits.unshift({...retired,score:200,exact:true});
    const ranked=hits.some(hit=>hit.signMatch)?hits.filter(hit=>hit.exact):hits;
    return ranked.sort((a,b) => b.score-a.score || a.label.length-b.label.length || a.label.localeCompare(b.label)).slice(0,limit);
  }
  function fullIndex() {
    return fullPromise ||= import(base+'/pagefind/pagefind.js').then(async api => {
      await api.options({baseUrl:base+'/'}); await api.init(); return api;
    }).catch(error => { fullPromise = null; throw error; });
  }
  async function full(raw, facet = '', issuer = '') {
    const {query, scope} = parse(raw, facet);
    if (!query) return [];
    const api = await fullIndex();
    const filters = {};
    if(scope) filters.source=scope;
    if(window.SSSAgency?.active || issuer) filters.agency=window.SSSAgency.active || issuer;
    const hits = await api.search(query,{filters});
    return hits.results;
  }
  function fullRow(d) {
    const sub = d.sub_results?.find(s => s.url && s.url.includes('#'));
    const text = new DOMParser().parseFromString(sub?.excerpt || d.excerpt || '', 'text/html').body.textContent || '';
    return {label: sub ? sub.title+' · '+d.meta.title : d.meta.title, url: sub?.url || d.url,
      tag: d.filters?.source?.[0] || 'Full text', excerpt: text};
  }
  window.SSSSearch = {direct, full, fullRow, urlFor, designation};
  window.__openSiteSearch = q => {
    if (location.pathname === base+'/search/' && !q) { document.getElementById('standards-query')?.focus(); return; }
    location.assign(urlFor(q || ''));
  };
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === 'k') {
      e.preventDefault(); window.__openSiteSearch('');
    }
  });
  const form = document.getElementById('standards-search');
  if (!form) return;
  const input = form.elements.q, source = form.elements.source, results = document.getElementById('standards-results');
  const status = document.getElementById('standards-status'), more = document.getElementById('standards-more');
  const params = new URLSearchParams(location.search);
  input.value = params.get('q') || ''; source.value = window.SSSAgency?.active ? '' : (params.get('source') || '');
  const issuer=form.elements.issuer;
  for(const [key,mode] of Object.entries(window.__agencyCatalog||{}).sort((a,b)=>a[1].name.localeCompare(b[1].name)))issuer.add(new Option(mode.name,key));
  issuer.value=window.SSSAgency?.active||params.get('issuer')||'';issuer.disabled=!!window.SSSAgency?.active;
  issuer.onchange=()=>{clearTimeout(timer);run();};
  const matching=form.elements.match, suggestions=document.getElementById('query-guesses');
  matching.value=params.get('match')||'all';
  const vocabulary=['accessible parking','bus stop','bus boarding island','bicycle lane','California MUTCD','crosswalk','curb ramp','delineator','driveway','intersection','pavement marking','pedestrian refuge','protected intersection','traffic signal','transit signal priority','turn pocket','yield line'];
  const closeWord=(a,b)=>{let row=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){let next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(row[j]+1,next[j-1]+1,row[j-1]+Number(a[i-1]!==b[j-1]));row=next;}return row[b.length];};
  async function complete(){const q=clean(input.value);suggestions.replaceChildren();if(q.length<2)return;
    for(const term of vocabulary.filter(t=>t.includes(q)||closeWord(q,t)<=Math.min(2,Math.floor(q.length/3))).slice(0,7))suggestions.append(new Option(term,term));
    try {
      const {records}=await catalog();if(q!==clean(input.value))return;
      const labels=new Set(Array.from(suggestions.options,o=>o.value));
      const add=record=>{if((!issuer.value||window.SSSAgency.inScope(record.url,issuer.value))&&(!source.value||record.tag===source.value)&&labels.size<10&&record.label.length<=105)labels.add(record.label);};
      for(const record of records){if(record.names.startsWith(q)||record.exact.some(k=>k.startsWith(designation(input.value))))add(record);if(labels.size===10)break;}
      suggestions.replaceChildren(...[...labels].map(t=>new Option(t,t)));
    }catch{} }
  input.addEventListener('input',complete);
  matching.addEventListener('change',()=>{clearTimeout(timer);run();});
  let generation = 0, timer, ready = [], pages = [], seen, index, fullUnavailable, directUnavailable;
  function showRows(rows) {
    for (const hit of rows) {
      const url = new URL(hit.url, location.href);
      if (window.SSSAgency?.active && !window.SSSAgency.inScope(url.href)) continue;
      if (seen.has(url.href)) continue;
      seen.add(url.href);
      const item = document.createElement('li'), a = document.createElement('a'), label = document.createElement('small');
      a.href = url.href; a.textContent = hit.label; label.textContent = hit.tag;
      item.append(label, a);
      if (hit.excerpt) { const p = document.createElement('p'); p.textContent = hit.excerpt; item.append(p); }
      results.append(item);
    }
  }
  async function append(id) {
    more.disabled = true;
    showRows(ready.splice(0,15));
    if (!ready.length && index < pages.length) {
      const chunk = pages.slice(index,index+15); index += chunk.length;
      const batch = await Promise.allSettled(chunk.map(p => p.data()));
      if (id !== generation) return;
      fullUnavailable ||= batch.some(row => row.status !== 'fulfilled');
      showRows(batch.filter(row=>row.status==='fulfilled').map(row=>fullRow(row.value)));
    }
    if (id !== generation) return;
    more.disabled = false; more.hidden = !ready.length && index >= pages.length;
    status.textContent = seen.size ? seen.size+' result'+(seen.size===1?'':'s')+' shown.' : 'No matches. Try another code, fewer words, or a different source.';
    if (fullUnavailable || directUnavailable) status.textContent += ' '+(fullUnavailable && directUnavailable ? 'Search indexes are unavailable.' : fullUnavailable ? 'Full-text results are unavailable.' : 'Code and title results are unavailable.')+' Submit again to retry.';
  }
  async function run(restore = null) {
    const id = ++generation, q = input.value.trim(), scope = source.value;
    const dest=new URL(urlFor(q,scope),location.origin);if(issuer.value&&!issuer.disabled)dest.searchParams.set('issuer',issuer.value);if(matching.value!=='all')dest.searchParams.set('match',matching.value);history.replaceState({...history.state, searchReturn:null},'',dest);
    results.replaceChildren(); more.hidden=true; seen=new Set(); index=0;
    if (!q) { status.textContent='Enter a drawing number, section, or design question.'; return; }
    status.textContent='Searching…';
    const matches = direct(q,scope,250,matching.value,issuer.value);
    // Exact drawing and sign identifiers can resolve from the local catalog alone.
    const identifier=sheetQualifier.test(q)||/^(?:sign\s+)?[a-z]{1,5}\s*-?\d|^(?:CAD|DWG)\s|\s(?:CAD|DWG)$/i.test(q);
    const text = matching.value!=='all' ? Promise.resolve([]) : identifier
      ? matches.then(hits => hits[0]?.sheetMatch||hits[0]?.signMatch||hits[0]?.tag==='Retired' ? [] : full(q,scope,issuer.value), () => full(q,scope,issuer.value))
      : full(q,scope,issuer.value);
    const [d,f] = await Promise.allSettled([matches, text]);
    if (id !== generation) return;
    directUnavailable=d.status==='rejected'; fullUnavailable=f.status==='rejected';
    ready=d.value || []; pages=f.value || [];
    if (ready[0]?.tag==='Retired') pages=[];
    await append(id);
    if (restore?.q === q && restore.scope === scope && id === generation) {
      while (seen.size < restore.count && !more.hidden && id === generation) await append(id);
      if (id !== generation) return;
      const link = [...results.querySelectorAll('a')].find(a => a.href === restore.href);
      if (link) {
        link.focus({preventScroll:true});
        link.scrollIntoView({block:'nearest',behavior:'instant'});
      }
    }
  }
  input.addEventListener('input', () => { generation++; clearTimeout(timer); more.hidden=true; timer=setTimeout(run,160); });
  source.addEventListener('change', () => {clearTimeout(timer); run();});
  form.addEventListener('submit', e => {e.preventDefault(); clearTimeout(timer); run();});
  more.addEventListener('click', () => append(generation));
  results.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    history.replaceState({...history.state, searchReturn:{q:input.value.trim(), scope:source.value,
      count:seen.size, href:link.href}},'');
  });
  if (!input.value) input.focus({preventScroll:true});
  const restore = performance.getEntriesByType('navigation')[0]?.type === 'back_forward' ? history.state?.searchReturn : null;
  run(restore);
})();
