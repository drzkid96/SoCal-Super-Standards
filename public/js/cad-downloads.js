(() => {
  const library = document.querySelector('[data-cad-downloads]');
  if (!library) return;
  const form = library.querySelector('.cad-find');
  const count = library.querySelector('.cad-count');
  const paging = library.querySelector('.cad-paging');
  const prev = paging.querySelector('[data-prev]');
  const next = paging.querySelector('[data-next]');
  const clear = form.querySelector('button[type=reset]');
  const filters = form.querySelector('.cad-filter-options');
  const rows = [...library.querySelectorAll('.cad-records > li')];
  const pageSize = 36;
  const fields = ['q', 'source', 'size', 'kind'];
  const normalize = value => value.normalize('NFKD').toLowerCase().replace(/[–—−]/g, '-');
  const words = value => normalize(value).replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  const index = new Map(rows.map(row => [row, words(row.dataset.query)]));
  const sources = new Map(rows.map(row => [row, new Set((row.dataset.sources||row.dataset.source).split('|'))]));
  const codes = new Map();
  for (const row of rows) {
    for (const key of new Set(row.dataset.keys.split('|'))) {
      if (!codes.has(key)) codes.set(key, new Set());
      codes.get(key).add(row);
    }
  }
  let page = 1;
  function writeURL() {
    const url = new URL(location.href);
    for (const name of fields) {
      const val = form.elements.namedItem(name).value.trim();
      if (val) url.searchParams.set(name, val);
      else url.searchParams.delete(name);
    }
    if (page > 1) url.searchParams.set('page', String(page));
    else url.searchParams.delete('page');
    url.hash = '';
    history.replaceState(history.state, '', url);
  }
  function render({anchor = false, updateURL = false} = {}) {
    const input = form.elements.namedItem('q').value.trim();
    const dimensions=input.match(/(^|\s)(\d+(?:\.\d+)?)\s*(?:in\b|")?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:in\b|")?(?=\s|$)/i);
    const phrase=dimensions?input.replace(dimensions[0],' ').trim():input;
    const tokens = words(phrase).split(/\s+/).filter(Boolean);
    const key = window.SSSSearch?.designation?.(phrase);
    const exact = codes.get(key);
    const source = form.elements.namedItem('source').value;
    const size = form.elements.namedItem('size').value;
    const kind = form.elements.namedItem('kind').value;
    const active = [source,size,kind].filter(Boolean).length;
    filters.querySelector('summary').textContent = active ? 'Filters ('+active+')' : 'Filters';
    clear.hidden = !active && !input;
    const matches = (exact ? [...exact] : rows).filter(row =>
      (!dimensions || [[row.dataset.width,row.dataset.height],[row.dataset.publishedWidth,row.dataset.publishedHeight]]
        .some(([w,h])=>Number(w)===Number(dimensions[2]) && Number(h)===Number(dimensions[3]))) &&
      (!source || sources.get(row).has(source)) &&
      (!size || row.dataset.status === size) &&
      (!kind || row.dataset.kind === kind) &&
      (exact || tokens.every(term => index.get(row).includes(term)))
    );
    if (anchor && location.hash) {
      const target = document.getElementById(location.hash.slice(1));
      const at = matches.indexOf(target);
      if (at !== -1) page = Math.floor(at / pageSize) + 1;
    }
    const last = Math.max(1, Math.ceil(matches.length / pageSize));
    page = Math.max(1, Math.min(last, page));
    const start = (page - 1) * pageSize;
    const visible = new Set(matches.slice(start, start + pageSize));
    for (const row of rows) {
      const hidden = !visible.has(row);
      if (row.hidden !== hidden) row.hidden = hidden;
    }
    count.textContent = matches.length
      ? (start + 1) + '–' + Math.min(start + pageSize, matches.length) + ' of ' + matches.length.toLocaleString() + ' records'
      : 'No matching records. Change the search or clear the filters.';
    prev.disabled = page <= 1;
    next.disabled = page >= last;
    paging.hidden = last <= 1;
    if (updateURL) writeURL();
    if (anchor && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  }
  function restore() {
    const params = new URL(location.href).searchParams;
    for (const name of fields) form.elements.namedItem(name).value = params.get(name) || '';
    page = Math.max(1, parseInt(params.get('page'), 10) || 1);
    if (fields.some(name => name !== 'q' && form.elements.namedItem(name).value)) filters.open = true;
    render({anchor: true});
  }
  function filter() {
    page = 1;
    render({updateURL: true});
  }
  form.elements.namedItem('q').addEventListener('input', filter);
  form.addEventListener('change', event => {if (event.target.tagName==='SELECT') filter();});
  form.addEventListener('submit', event => {event.preventDefault(); filter();});
  form.addEventListener('reset', () => requestAnimationFrame(filter));
  function turn(direction) {
    page += direction;
    render({updateURL: true});
    count.scrollIntoView({block: 'start'});
    count.focus({preventScroll: true});
  }
  prev.addEventListener('click', () => turn(-1));
  next.addEventListener('click', () => turn(1));
  window.addEventListener('popstate', restore);
  window.addEventListener('hashchange', () => render({anchor: true}));
  count.tabIndex = -1;
  form.hidden = false;
  restore();
})();
