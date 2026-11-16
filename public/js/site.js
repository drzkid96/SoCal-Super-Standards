window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));
// Hover / focus previews for sign codes (a.sref) and keyboard helpers.
(() => {
  const tip = document.createElement('div');
  tip.className = 'sref-tip';
  tip.innerHTML = '<img alt=""><span></span>';
  window.__ready( () => document.body.appendChild(tip));
  let cur = null;
  function show(a) {
    cur = a;
    tip.querySelector('img').src = a.dataset.svg;
    tip.querySelector('span').textContent = a.textContent;
    const r = a.getBoundingClientRect();
    const top = r.bottom + 8 + 170 > innerHeight ? r.top - 178 : r.bottom + 8;
    tip.style.left = Math.min(innerWidth - 180, Math.max(8, r.left + r.width / 2 - 85)) + 'px';
    tip.style.top = top + 'px';
    tip.classList.add('on');
  }
  function hide() { cur = null; tip.classList.remove('on'); }
  document.addEventListener('mouseover', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a) show(a); else if (cur) hide(); });
  document.addEventListener('focusin', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a) show(a); });
  document.addEventListener('scroll', hide, { passive: true });
  // back-to-top button and reading progress
  window.__ready( () => {
    const b = document.createElement('button');
    b.className = 'to-top'; b.type = 'button'; b.setAttribute('aria-label', 'Back to top'); b.textContent = 'Top';
    b.onclick = () => scrollTo({ top: 0, behavior: 'smooth' });
    document.body.appendChild(b);
    const bar = document.createElement('div'); bar.className = 'read-bar'; document.body.appendChild(bar);
    addEventListener('scroll', () => {
      const h = document.documentElement; const p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
      bar.style.transform = `scaleX(${p})`; b.classList.toggle('show', h.scrollTop > 600);
    }, { passive: true });
  });
})();

/* ---------- quick lookup: numbers to pages ---------- */
(function () {
  const BASE = '/SoCal-Super-Standards';
  let LOOK = null;
  const norm = (s) => s.toUpperCase().replace(/^(FIGURE|FIG\.?|TABLE|SECTION|SEC\.?|DWG\.?|DRAWING|STD\.?)\s*/, '').replace(/\s+/g, '');
  async function look(q) {
    if (!LOOK) LOOK = await (await fetch(BASE + '/data/lookup.json')).json();
    const k = norm(q);
    if (!k) return [];
    if (LOOK[k]) return LOOK[k];
    const out = [];
    for (const key in LOOK) { if (key.startsWith(k)) { out.push(...LOOK[key]); if (out.length > 12) break; } }
    return out;
  }
  function mount(el) {
    const inp = el.querySelector('input'), res = el.querySelector('.ql-res');
    let t;
    inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(async () => {
      const r = await look(inp.value);
      res.innerHTML = r.slice(0, 12).map(([l, u]) => `<a href="${u}">${l.replace(/</g, '&lt;')}</a>`).join('') || (inp.value.trim() ? '<span class="muted">No exact number match. Press Enter to search all text.</span>' : '');
    }, 120); });
    inp.addEventListener('keydown', async (e) => {
      if (e.key !== 'Enter') return;
      const r = await look(inp.value);
      if (r.length) location.href = r[0][1];
      else { const b = document.querySelector('site-search button, button[data-open-modal]'); if (b) b.click(); }
    });
  }
  window.__ready( () => document.querySelectorAll('.quick-lookup').forEach(mount));
})();

/* ---------- detail and drawing index ---------- */
(function () {
  const BASE = '/SoCal-Super-Standards';
  window.__ready( async () => {
    const root = document.getElementById('dx');
    if (!root) return;
    const all = await (await fetch(BASE + '/data/details.json')).json();
    const $ = (id) => document.getElementById(id);
    const srcs = [...new Set(all.map((i) => i.src))];
    $('dx-src').innerHTML += srcs.map((s) => `<option>${s}</option>`).join('');
    const p = new URLSearchParams(location.search);
    for (const [k, id] of [['q', 'dx-q'], ['src', 'dx-src'], ['type', 'dx-type'], ['topic', 'dx-topic'], ['sg', 'dx-sg']]) if (p.get(k)) $(id).value = p.get(k);
    let shown = 0, list = [];
    const card = (i) => `<a class="dx-card" href="${i.url}"><div class="dx-img">${i.img ? `<img loading="lazy" src="${i.img}" alt="">` : ''}</div>
      <div class="dx-body"><div class="dx-tag ${i.sg === 'MUTCD' ? (i.src.startsWith('CA') ? 'c' : 'f') : 'l'}">${i.src}</div>
      <b>${i.type === 'Figure page' ? '' : (i.type === 'Standard drawing' ? '' : i.type + ' ') + i.num}</b> ${(i.title || '').replace(/</g, '&lt;')}
      ${i.date ? `<div class="dx-meta">Dated ${i.date} &middot; ${i.sheets} sheet(s)</div>` : ''}</div></a>`;
    function run(reset = true) {
      const q = $('dx-q').value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      const sg = $('dx-sg').value, src = $('dx-src').value, ty = $('dx-type').value, tp = $('dx-topic').value, nf = $('dx-noFed').checked;
      list = all.filter((i) => (!sg || i.sg === sg) && (!src || i.src === src) && (!ty || i.type === ty) && (!tp || (i.topics || []).includes(tp))
        && (!nf || i.src !== 'Federal MUTCD')
        && q.every((w) => (i.num + ' ' + i.title + ' ' + (i.kw || '') + ' ' + (i.signs || []).join(' ') + ' ' + i.src).toLowerCase().includes(w)));
      if (reset) { shown = 0; $('dx-grid').innerHTML = ''; }
      const next = list.slice(shown, shown + 90);
      $('dx-grid').insertAdjacentHTML('beforeend', next.map(card).join(''));
      shown += next.length;
      $('dx-count').textContent = `${list.length} of ${all.length} details`;
      $('dx-more').hidden = shown >= list.length;
      const u = new URLSearchParams();
      for (const [k, id] of [['q', 'dx-q'], ['sg', 'dx-sg'], ['src', 'dx-src'], ['type', 'dx-type'], ['topic', 'dx-topic']]) if ($(id).value) u.set(k, $(id).value);
      history.replaceState(null, '', location.pathname + (u.toString() ? '?' + u : ''));
    }
    root.querySelectorAll('input,select').forEach((e) => e.addEventListener('input', () => run()));
    $('dx-more').onclick = () => run(false);
    run();
  });
})();
