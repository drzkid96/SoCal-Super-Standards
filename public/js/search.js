/* Shared title, identifier, and full-text retrieval for the site and reference drawer. */
(() => {
  const base = '/SoCal-Super-Standards';
  const clean = s => s.normalize('NFKD').toLowerCase().replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const compact = s => clean(s).replace(/ /g, '');
  // Hyphens distinguish California designations, e.g. G1-4(CA) and G14(CA).
  const designation = s => s.toUpperCase().replace(/[–—]/g,'-').replace(/[()\s]/g,'');
  const urlFor = (q, source = '') => {
    const url = new URL(base + '/search/', location.origin);
    if (q.trim()) url.searchParams.set('q', q.trim());
    if (source) url.searchParams.set('source', source);
    return url.pathname + url.search;
  };
  let catalogPromise, fullPromise;
  async function json(name) {
    const response = await fetch(base + '/data/' + name + '.json');
    if (!response.ok) throw Error('Search index unavailable');
    return response.json();
  }
  function catalog() {
    return catalogPromise ||= Promise.all([json('search-catalog'), json('retired'), json('glossary')]).then(([rows, retired, glossary]) => {
      const records = rows.map(([path, label, tag, keys]) => ({
        url: base + path, label, tag, names: clean(label),
        hay: clean(label + ' ' + tag + ' ' + path.replaceAll('/', ' ') + ' ' + keys.join(' ')),
        keys: keys.map(compact), exact:keys.map(designation)
      }));
      const withdrawn = new Map(Object.entries(retired.codes).map(([code, name]) =>
        [designation(code), {label: code + ' · ' + name + ' · Caltrans deletion notice', url: retired.source, tag: 'Retired', cls: 'sup'}]));
      const synonyms = new Map();
      for (const row of glossary) {
        for (const alias of row.aka) synonyms.set(clean(alias), clean(row.term));
      }
      return {records, withdrawn, synonyms};
    }).catch(error => { catalogPromise = null; throw error; });
  }
  const sources = [
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
  async function direct(raw, facet = '', limit = 12) {
    const {query, scope} = parse(raw, facet);
    if (!query) return [];
    const {records, withdrawn, synonyms} = await catalog();
    const code = compact(query), phrase = clean(query);
    if (!code) return [];
    if ((!scope || ['Caltrans','Signs','CA MUTCD'].includes(scope)) && withdrawn.has(designation(query))) return [withdrawn.get(designation(query))];
    const words = phrase.split(' '), expanded = synonyms.get(phrase);
    const priority = {'CA MUTCD': 6, LADOT: 5, Caltrans: 5, 'LA BOE': 4};
    const hits = [];
    for (const record of records) {
      if (scope && scope !== record.tag) continue;
      let score;
      if (record.exact.includes(designation(query))) score = 135;
      else if (record.keys.includes(code)) score = 120;
      else if (record.names === phrase) score = 110;
      else if (record.names.includes(phrase)) score = 78;
      else if (words.every(w => record.hay.includes(w))) score = 55;
      else if (expanded && record.hay.includes(expanded)) score = 43;
      else if (code.length >= 2 && /\d/.test(code) && record.keys.some(k => k.startsWith(code))) score = 38;
      else continue;
      if (record.url.includes('/keywords/#')) score -= 10;
      if (record.url.includes('/topics/') && !/\d/.test(query)) score += 5;
      if (record.url.endsWith('/standard-plans/') && phrase === clean(record.url.split('/').at(-3))) score += 42;
      hits.push({score: score+(priority[record.tag]||0), label:record.label, tag:record.tag, url:record.url, cls:'c'});
    }
    return hits.sort((a,b) => b.score-a.score || a.label.length-b.label.length || a.label.localeCompare(b.label)).slice(0,limit);
  }
  function fullIndex() {
    return fullPromise ||= import(base+'/pagefind/pagefind.js').then(async api => {
      await api.options({baseUrl:base+'/'}); await api.init(); return api;
    }).catch(error => { fullPromise = null; throw error; });
  }
  async function full(raw, facet = '') {
    const {query, scope} = parse(raw, facet);
    if (!query) return [];
    const api = await fullIndex();
    const hits = await api.search(query, scope ? {filters:{source:scope}} : {});
    return hits.results;
  }
  function fullRow(d) {
    const sub = d.sub_results?.find(s => s.url && s.url.includes('#'));
    const text = new DOMParser().parseFromString(sub?.excerpt || d.excerpt || '', 'text/html').body.textContent || '';
    return {label: sub ? sub.title+' · '+d.meta.title : d.meta.title, url: sub?.url || d.url,
      tag: d.filters?.source?.[0] || 'Full text', excerpt: text};
  }
  window.SSSSearch = {direct, full, fullRow, urlFor};
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
  input.value = params.get('q') || ''; source.value = params.get('source') || '';
  let generation = 0, timer, ready = [], pages = [], seen, index, fullUnavailable, directUnavailable;
  function showRows(rows) {
    for (const hit of rows) {
      const url = new URL(hit.url, location.href);
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
  async function run() {
    const id = ++generation, q = input.value.trim(), scope = source.value;
    history.replaceState(null,'',urlFor(q,scope));
    results.replaceChildren(); more.hidden=true; seen=new Set(); index=0;
    if (!q) { status.textContent='Enter a drawing number, section, or design question.'; return; }
    status.textContent='Searching…';
    const [d,f] = await Promise.allSettled([direct(q,scope,250), full(q,scope)]);
    if (id !== generation) return;
    directUnavailable=d.status==='rejected'; fullUnavailable=f.status==='rejected';
    ready=d.value || []; pages=f.value || [];
    if (ready[0]?.tag==='Retired') pages=[];
    await append(id);
  }
  input.addEventListener('input', () => { generation++; clearTimeout(timer); more.hidden=true; timer=setTimeout(run,160); });
  source.addEventListener('change', () => {clearTimeout(timer); run();});
  form.addEventListener('submit', e => {e.preventDefault(); clearTimeout(timer); run();});
  more.addEventListener('click', () => append(generation));
  if (!input.value) input.focus({preventScroll:true});
  run();
})();
