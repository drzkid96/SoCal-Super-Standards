window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));

// Helper: open Starlight's Pagefind search modal and optionally prefill a query.
window.__openSiteSearch = function (query) {
  const btn = document.querySelector('site-search button, button[data-open-modal]');
  if (!btn) return;
  btn.click();
  if (!query || !query.trim()) return;
  const q = query.trim();
  let tries = 0;
  const fill = () => {
    const inp = document.querySelector('.pagefind-ui__search-input, dialog input[type="search"], dialog input[type="text"]');
    if (inp) {
      inp.value = q;
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      inp.focus();
      return;
    }
    if (++tries < 25) setTimeout(fill, 60);
  };
  setTimeout(fill, 40);
};

// Hover / focus previews for sign codes (a.sref), page previews, back-to-top, reading progress, and navigation helpers.
(() => {
  const tip = document.createElement('div');
  tip.className = 'sref-tip';
  tip.innerHTML = '<img alt=""><span></span>';
  window.__ready(() => document.body.appendChild(tip));
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
  document.addEventListener('mouseover', (e) => { const a = e.target.closest && e.target.closest('a.sref, a[data-svg]'); if (a && a.dataset.svg) show(a); else if (cur) hide(); });
  document.addEventListener('focusin', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a) show(a); });
  document.addEventListener('scroll', hide, { passive: true });

  // Page previews for every internal link: one image, or a set for sign and marking pages.
  const BASEP = '/SoCal-Super-Standards';
  const ptip = document.createElement('div');
  ptip.className = 'pv-tip';
  window.__ready(() => document.body.appendChild(ptip));
  let PV = null, pvLoading = null, pvCur = null, pvTimer = null;
  const loadPV = () => pvLoading || (pvLoading = fetch(BASEP + '/data/previews.json').then((r) => r.json()).then((j) => (PV = j)).catch(() => (PV = {})));
  function key(a) {
    try {
      const u = new URL(a.href, location.href);
      if (u.origin !== location.origin || !u.pathname.startsWith(BASEP)) return null;
      const p = u.pathname.slice(BASEP.length) || '/';
      return [p + u.hash, p.endsWith('/') ? p : p + '/'];
    } catch (e) { return null; }
  }
  function placeP(a, w, h) {
    const r = a.getBoundingClientRect();
    const top = r.bottom + 10 + h > innerHeight ? Math.max(8, r.top - h - 10) : r.bottom + 10;
    ptip.style.left = Math.min(innerWidth - w - 8, Math.max(8, r.left)) + 'px';
    ptip.style.top = top + 'px';
  }
  async function showP(a) {
    const k = key(a); if (!k) return;
    if (!PV) await loadPV();
    if (pvCur !== a) return;
    const here = location.pathname.slice(BASEP.length) + location.hash;
    const e = PV[k[0]] || PV[k[1]];
    if (!e || !e.i.length || k[0] === here) return;
    const many = e.i.length > 1;
    ptip.className = 'pv-tip' + (many ? ' many' + (e.i.length > 4 ? ' nine' : '') : '');
    ptip.innerHTML = `<div class="pv-imgs">${e.i.map((x) => `<img alt="" src="${BASEP + x}">`).join('')}</div><div class="pv-t"></div>`;
    ptip.querySelector('.pv-t').textContent = e.t;
    placeP(a, many ? (e.i.length > 4 ? 330 : 300) : 260, many ? (e.i.length > 4 ? 340 : 260) : 230);
    ptip.classList.add('on');
  }
  function hideP() { pvCur = null; clearTimeout(pvTimer); ptip.classList.remove('on'); }
  document.addEventListener('mouseover', (ev) => {
    const a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || a.matches('a.sref, a[data-svg], .dx-card, .sss-navlink') || a.closest('.pv-tip, .sref-tip, .ql-res')) { if (pvCur && a !== pvCur) hideP(); return; }
    if (a === pvCur) return;
    hideP(); pvCur = a; loadPV();
    pvTimer = setTimeout(() => showP(a), 220);
  });
  document.addEventListener('mouseout', (ev) => { if (pvCur && !(ev.relatedTarget && pvCur.contains(ev.relatedTarget))) hideP(); });
  document.addEventListener('scroll', hideP, { passive: true });

  // Back-to-top button, reading progress, sidebar active scroll, and '/' search shortcut
  window.__ready(() => {
    const b = document.createElement('button');
    b.className = 'to-top'; b.type = 'button'; b.setAttribute('aria-label', 'Back to top'); b.textContent = 'Top';
    b.onclick = () => scrollTo({ top: 0, behavior: 'smooth' });
    document.body.appendChild(b);
    const bar = document.createElement('div'); bar.className = 'read-bar'; document.body.appendChild(bar);
    addEventListener('scroll', () => {
      const h = document.documentElement; const p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
      bar.style.transform = `scaleX(${p})`; b.classList.toggle('show', h.scrollTop > 600);
    }, { passive: true });

    // Scroll active sidebar link smoothly into view if off-screen
    const curSide = document.querySelector('#starlight__sidebar a[aria-current="page"]');
    if (curSide && curSide.scrollIntoView) {
      try { curSide.scrollIntoView({ block: 'nearest' }); } catch (e) {}
    }

    // Pressing '/' focuses the primary on-page filter/lookup input (or opens site search)
    document.addEventListener('keydown', (e) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      const target = document.querySelector('.quick-lookup input, #dx-q, #sq, #mq, #ltq, #kq, #dwq');
      e.preventDefault();
      if (target) { target.focus(); target.select && target.select(); }
      else window.__openSiteSearch('');
    });
  });
})();

/* ---------- unified quick lookup: numbers, signs, concepts, bulletins, topics & tools ---------- */
(function () {
  const BASE = '/SoCal-Super-Standards';
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const norm = (s) => s.toUpperCase().replace(/^(FIGURE|FIG\.?|TABLE|SECTION|SEC\.?|DWG\.?|DRAWING|STD\.?|DETAIL)\s*/, '').replace(/\s+/g, '');
  const alnum = (s) => s.toUpperCase().replace(/[^A-Z0-9]/g, '');

  const HUBS = [
    ['Lane Width Comparison (DIB 94 vs. MPP 531 vs. LA Streets)', BASE + '/bulletins/lane-widths/', 'Tool', 'lane width comparison dib 94 mpp 531 road diet travel lane'],
    ['Bikeway Design Comparison (HDM Ch. 1000, DIB 89-02, CA MUTCD & AASHTO GBF-5)', BASE + '/bulletins/bikeway-design-comparison/', 'Tool', 'bikeway design comparison aashto gbf-5 hdm 1000 dib 89-02 class iv separated bike lane shared use path sharrow'],
    ['AASHTO Bike Guide, 5th Edition (GBF-5, 2024) — 16 Chapters, 256 Figures, 50 Tables', BASE + '/guides/aashto-bike-guide/', 'Guide', 'aashto guide for the development of bicycle facilities 5th edition gbf-5 2024 errata bikeway'],
    ['LADOT Curb Paint, Red Curb & S-481.0 Calculator', BASE + '/ladot/curb-paint/', 'Tool', 'red curb paint daylighting blue yellow green white s-481 calculator'],
    ['Line Type Database (Caltrans 2026 Details 1-45)', BASE + '/markings/line-types/', 'Tool', 'line type striping detail 1 2 8 9 12 21 22 25 27b 32 38 39 a20a a20b'],
    ['Standards Status (What Governs & 219 Deleted CA Signs)', BASE + '/bulletins/standards-status/', 'Status', 'standards status superseded current edition deleted california signs'],
    ['Caltrans 2026 Standard Plans (A20-A24, A88, A90)', BASE + '/caltrans/standard-plans-2026/', 'Caltrans 2026', 'caltrans 2026 standard plans a20a a24a a88a a88b a90a a90b curb ramp'],
    ['LA28 Supplement to CA MUTCD 2026 (Games Route Network)', BASE + '/caltrans/la28-supplement/', 'CA MUTCD', 'la28 olympics paralympics games route network grn permit only'],
    ['Bulletins & Policy Memos (Caltrans DIBs, LADOT, PROWAG, CBC 11B)', BASE + '/bulletins/', 'Bulletin', 'bulletins policy memos dib 94 89-02 82-06 prowag cbc 11b lpi'],
    ['Sign Library (1,148 Federal & CA Signs)', BASE + '/signs/', 'Sign', 'sign library regulatory warning school guide ca signs'],
    ['Pavement Marking Library (203 Markings)', BASE + '/markings/', 'Marking', 'pavement marking library arrows symbols words crosswalk bike'],
    ['Detail and Drawing Index (1,529 Items)', BASE + '/details/', 'Tool', 'detail drawing index standard drawings figures tables'],
    ['Keyword Index A to Z', BASE + '/keywords/', 'Keyword', 'keyword index glossary synonyms abbreviations'],
    ['Ask the Standards (AI)', BASE + '/ask/', 'Tool', 'ask ai claude screenshot plan review comment'],
    ['Topic: Crosswalks and Pedestrian Crossings', BASE + '/topics/crosswalks/', 'Topic', 'crosswalks pedestrian crossing uncontrolled midblock ladder continental rrfb'],
    ['Topic: Accessibility (Curb Ramps & APS)', BASE + '/topics/accessibility/', 'Topic', 'accessibility ada prowag curb ramp detectable warning aps truncated domes'],
    ['Topic: Bikeways and Bicycle Facilities', BASE + '/topics/bikeways/', 'Topic', 'bikeways bike lane class ii class iv separated cycle track sharrow green paint'],
    ['Topic: Transit, Bus Lanes and Bus Stops', BASE + '/topics/transit/', 'Topic', 'transit bus lane bus stop bus bulb boarding island'],
    ['Topic: Curb, Parking and Loading Zones', BASE + '/topics/curb-parking-loading/', 'Topic', 'curb parking loading zone red curb blue curb accessible parking'],
    ['Topic: Speed Limits and Traffic Calming', BASE + '/topics/speed-and-calming/', 'Topic', 'speed limit speed hump cushion table traffic calming roundabouts'],
    ['Topic: Traffic Signals and Pedestrian Signals', BASE + '/topics/signals/', 'Topic', 'traffic signal pedestrian signal lpi countdown detector loop controller'],
    ['Topic: Lane Lines, Striping and Intersection Markings', BASE + '/topics/striping-intersections/', 'Topic', 'lane lines striping intersection markings turn bay taper cat tracks limit line'],
    ['Topic: School Zones', BASE + '/topics/school-zones/', 'Topic', 'school zone slow school xing yellow crosswalk safe routes'],
    ['Topic: Street Name and Guide Signs', BASE + '/topics/street-name-and-guide-signs/', 'Topic', 'street name sign guide sign wayfinding overhead'],
    ['Topic: Temporary Traffic Control (Work Zones)', BASE + '/topics/temporary-traffic-control/', 'Topic', 'temporary traffic control ttc work zone lane closure flagger detour'],
    ['Topic: Railroad and Light Rail Crossings', BASE + '/topics/rail-crossings/', 'Topic', 'railroad light rail lrt grade crossing preemption gates'],
  ];

  let LOOK = null, LOOK_KEYS = null, DET = null, DET_PROM = null;
  async function loadLook() {
    if (LOOK) return;
    LOOK = await (await fetch(BASE + '/data/lookup.json')).json();
    LOOK_KEYS = Object.keys(LOOK).map((k) => [k, alnum(k)]);
  }
  function loadDet() {
    if (DET) return Promise.resolve(DET);
    if (!DET_PROM) {
      DET_PROM = fetch(BASE + '/data/details.json').then((r) => r.json()).then((arr) => {
        arr.forEach((i) => {
          i._h = (i.num + ' ' + i.title + ' ' + (i.kw || '') + ' ' + (i.kx || '') + ' ' + (i.sum || '') + ' ' + i.src).toLowerCase();
          i._numA = alnum(i.num || '');
        });
        return (DET = arr);
      }).catch(() => (DET = []));
    }
    return DET_PROM;
  }

  function classify(label, url) {
    if (url.includes('/standard-plans-2018/') || /2018/.test(label) && url.includes('/caltrans/')) return { tag: 'Superseded', cls: 'sup', pri: -30 };
    if (url.includes('/ca-mutcd/') || url.includes('/s/ca/') || url.includes('/la28-supplement/')) return { tag: 'CA MUTCD', cls: 'c', pri: 22 };
    if (url.includes('/caltrans/standard-plans-2026/') || url.includes('caltrans-std-plans-2026')) return { tag: 'Caltrans 2026', cls: 'c', pri: 20 };
    if (url.includes('/topics/')) return { tag: 'Topic', cls: 't', pri: 18 };
    if (url.includes('/bulletins/')) return { tag: 'Bulletin', cls: 'b', pri: 17 };
    if (url.includes('/markings/line-types/')) return { tag: 'Line Type', cls: 'm', pri: 16 };
    if (url.includes('/markings/')) return { tag: 'Marking', cls: 'm', pri: 14 };
    if (url.includes('/details/ladot/mpp-531') || url.includes('/details/ladot/mpp-521') || url.includes('/details/ladot/red-book')) return { tag: 'LADOT', cls: 'l', pri: 16 };
    if (url.includes('/details/ladot/') || url.includes('/ladot/')) return { tag: 'LADOT', cls: 'l', pri: 11 };
    if (url.includes('/details/burbank/') || url.includes('/burbank/')) return { tag: 'Burbank', cls: 'l', pri: 12 };
    if (url.includes('/details/pasadena/') || url.includes('/pasadena/')) return { tag: 'Pasadena', cls: 'l', pri: 12 };
    if (url.includes('/signs/')) return { tag: 'Sign', cls: 's', pri: 15 };
    if (url.includes('/keywords/')) return { tag: 'Keyword', cls: 'k', pri: 13 };
    if (url.includes('/mutcd/') || url.includes('/s/fed/')) return { tag: 'Fed MUTCD', cls: 'f', pri: 4 };
    return { tag: 'Guide', cls: 'f', pri: 8 };
  }

  async function search(raw) {
    const trimmed = raw.trim();
    if (!trimmed) return [];
    await loadLook();
    const k = norm(trimmed);
    const ka = alnum(trimmed);
    const low = trimmed.toLowerCase();
    const words = low.split(/\s+/).filter(Boolean);
    const byUrl = new Map();

    const add = (label, url, baseScore, forcedTag) => {
      if (!url) return;
      const meta = classify(label, url);
      const score = baseScore + meta.pri;
      const prev = byUrl.get(url);
      if (!prev || score > prev.score) {
        byUrl.set(url, { label, url, score, tag: forcedTag || meta.tag, cls: meta.cls });
      }
    };

    // 1. Curated tools, topics & major hubs
    for (const [label, url, tag, kw] of HUBS) {
      const h = (label + ' ' + kw).toLowerCase();
      if (words.every((w) => h.includes(w))) {
        const boost = label.toLowerCase().includes(low) ? 75 : 55;
        add(label, url, boost, tag);
      }
    }

    // 2. Exact & prefix matches in lookup.json (both normalized and hyphen-stripped)
    if (k && LOOK[k]) {
      for (const [l, u] of LOOK[k]) add(l, u, 120);
    }
    if (ka && ka.length >= 2) {
      let prefCount = 0;
      for (const [key, keyA] of LOOK_KEYS) {
        if (key === k) continue;
        if (keyA === ka) {
          for (const [l, u] of LOOK[key]) add(l, u, 115);
        } else if (key.startsWith(k) || (ka.length >= 2 && keyA.startsWith(ka))) {
          for (const [l, u] of LOOK[key]) add(l, u, 70 - Math.min(20, keyA.length - ka.length));
          if (++prefCount > 40) break;
        }
      }
    }

    // 3. Multi-word / descriptive search across details.json when helpful
    if (byUrl.size < 8 && trimmed.length >= 2) {
      const det = await loadDet();
      let hits = 0;
      for (const i of det) {
        const numExact = ka && i._numA === ka;
        const numPref = ka && ka.length >= 2 && i._numA.startsWith(ka);
        const wordHit = words.every((w) => i._h.includes(w) || (alnum(w).length >= 3 && i._numA.includes(alnum(w))));
        if (!numExact && !numPref && !wordHit) continue;
        let sc = numExact ? 110 : numPref ? 65 : 35;
        if ((i.title || '').toLowerCase().includes(low)) sc += 25;
        else if (words.every((w) => (i.title || '').toLowerCase().includes(w))) sc += 15;
        const label = (i.num && i.type !== 'Figure page' ? i.num + ' ' : '') + (i.title || i.src) + (i.src ? ' — ' + i.src : '');
        add(label, i.url, sc);
        if (++hits >= 40) break;
      }
    }

    return [...byUrl.values()].sort((a, b) => b.score - a.score).slice(0, 12);
  }

  function mount(el) {
    const inp = el.querySelector('input');
    const res = el.querySelector('.ql-res');
    const clearBtn = el.querySelector('.ql-clear');
    const fullBtn = el.querySelector('[data-open-search]');
    let t, idx = -1, items = [];

    const setActive = (next) => {
      const links = [...res.querySelectorAll('a.ql-item, button.ql-all')];
      if (!links.length) { idx = -1; return; }
      idx = ((next % links.length) + links.length) % links.length;
      links.forEach((a, i) => {
        a.classList.toggle('active', i === idx);
        a.setAttribute('aria-selected', String(i === idx));
      });
      links[idx].scrollIntoView({ block: 'nearest' });
    };

    const render = (list, raw) => {
      items = list;
      idx = -1;
      if (!raw.trim()) {
        res.innerHTML = '';
        res.classList.remove('open');
        return;
      }
      const rows = list.map((r) =>
        `<a class="ql-item" role="option" aria-selected="false" href="${r.url}"><span class="ql-tag ${r.cls}">${esc(r.tag)}</span><span class="ql-lbl">${esc(r.label)}</span></a>`
      ).join('');
      const empty = !list.length ? `<div class="ql-empty">No direct code or title match for &ldquo;${esc(raw.trim())}&rdquo;.</div>` : '';
      const footer = `<button type="button" class="ql-all" role="option" aria-selected="false">Search full text across all 1,725 pages for &ldquo;${esc(raw.trim())}&rdquo; &rarr;</button>`;
      res.innerHTML = rows + empty + footer;
      res.classList.add('open');
      const allBtn = res.querySelector('.ql-all');
      if (allBtn) allBtn.onclick = () => window.__openSiteSearch(inp.value);
    };

    const runQuery = async () => {
      const raw = inp.value;
      if (clearBtn) clearBtn.hidden = !raw;
      if (!raw.trim()) { render([], ''); return; }
      const r = await search(raw);
      if (inp.value === raw) render(r, raw);
    };

    inp.addEventListener('input', () => {
      if (clearBtn) clearBtn.hidden = !inp.value;
      clearTimeout(t);
      t = setTimeout(runQuery, 110);
    });
    inp.addEventListener('focus', () => { if (inp.value.trim() && !res.classList.contains('open')) runQuery(); });
    inp.addEventListener('keydown', async (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(idx + 1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActive(idx - 1); return; }
      if (e.key === 'Escape') { res.classList.remove('open'); idx = -1; return; }
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const links = [...res.querySelectorAll('a.ql-item, button.ql-all')];
      if (idx >= 0 && links[idx]) { links[idx].click(); return; }
      const r = items.length ? items : await search(inp.value);
      if (r.length) location.href = r[0].url;
      else window.__openSiteSearch(inp.value);
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        inp.value = '';
        clearBtn.hidden = true;
        render([], '');
        inp.focus();
      });
    }
    if (fullBtn) {
      fullBtn.addEventListener('click', () => window.__openSiteSearch(inp.value));
    }

    // Wire example chips in the same container (.home-search-wrap)
    const wrap = el.closest('.home-search-wrap');
    if (wrap) {
      wrap.querySelectorAll('.ql-samples button[data-q]').forEach((btn) => {
        btn.addEventListener('click', () => {
          inp.value = btn.dataset.q || '';
          if (clearBtn) clearBtn.hidden = false;
          inp.focus();
          runQuery();
        });
      });
    }

    document.addEventListener('click', (ev) => {
      if (!el.contains(ev.target) && !(wrap && wrap.contains(ev.target))) res.classList.remove('open');
    });
  }

  window.__ready(() => document.querySelectorAll('.quick-lookup').forEach(mount));
})();

/* ---------- detail and drawing index ---------- */
(function () {
  const BASE = '/SoCal-Super-Standards';
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const alnum = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');

  window.__ready(async () => {
    const root = document.getElementById('dx');
    if (!root) return;
    const all = await (await fetch(BASE + '/data/details.json')).json();
    let GL = [];
    try { GL = await (await fetch(BASE + '/data/glossary.json')).json(); } catch (e) {}
    const GBY = Object.fromEntries(GL.map((g) => [g.id, g]));
    const PHR = [];
    GL.forEach((g) => [g.term, ...g.aka].forEach((t) => PHR.push([t.toLowerCase(), g.id])));
    PHR.sort((a, b) => b[0].length - a[0].length);

    const hay = (i) => (i.num + ' ' + i.title + ' ' + (i.kw || '') + ' ' + (i.kx || '') + ' ' + (i.sum || '') + ' ' + (i.signs || []).join(' ') + ' ' + i.src).toLowerCase();
    all.forEach((i) => {
      i._h = hay(i);
      i._na = alnum(i.num);
      i._tl = (i.title || '').toLowerCase();
      i._sup = i.src === 'Caltrans Std. Plans 2018';
    });

    function parse(raw) {
      let s = ' ' + raw.toLowerCase().trim() + ' ';
      const ids = [];
      for (const [t, id] of PHR) {
        if (t.length < 3) continue;
        const k = ' ' + t + ' ';
        if (s.includes(k)) { ids.push([id, t]); s = s.replace(k, ' '); }
      }
      return { ids, words: s.trim().split(/\s+/).filter(Boolean), rawLow: raw.toLowerCase().trim(), rawA: alnum(raw) };
    }

    const $ = (id) => document.getElementById(id);
    const allSrcs = [...new Set(all.map((i) => i.src))];
    const srcsBySg = {};
    all.forEach((i) => { (srcsBySg[i.sg] = srcsBySg[i.sg] || new Set()).add(i.src); });

    function populateSrcs(sg, keepVal) {
      const sel = $('dx-src');
      const cur = keepVal !== undefined ? keepVal : sel.value;
      const list = sg && srcsBySg[sg] ? [...srcsBySg[sg]] : allSrcs;
      sel.innerHTML = '<option value="">Any document</option>' + list.map((s) => `<option>${esc(s)}</option>`).join('');
      if (list.includes(cur)) sel.value = cur;
    }

    const p = new URLSearchParams(location.search);
    if (p.get('sg')) $('dx-sg').value = p.get('sg');
    populateSrcs($('dx-sg').value, p.get('src') || '');
    for (const [k, id] of [['q', 'dx-q'], ['type', 'dx-type'], ['topic', 'dx-topic'], ['sort', 'dx-sort']]) {
      if (p.get(k) && $(id)) $(id).value = p.get(k);
    }
    if (p.get('noFed') === '1') $('dx-noFed').checked = true;
    if (p.get('noSup') === '1' && $('dx-noSup')) $('dx-noSup').checked = true;

    let shown = 0, list = [];
    const card = (i) => `<a class="dx-card${i._sup ? ' is-sup' : ''}" href="${i.url}"><div class="dx-img">${i.img ? `<img loading="lazy" src="${i.img}" alt="">` : ''}</div>
      <div class="dx-body"><div class="dx-tags"><span class="dx-tag ${i.sg === 'MUTCD' ? (i.src.startsWith('CA') ? 'c' : 'f') : 'l'}">${esc(i.src)}</span>${i._sup ? '<span class="dx-sup">Superseded</span>' : ''}</div>
      <b>${i.type === 'Figure page' ? '' : (i.type === 'Standard drawing' ? '' : esc(i.type) + ' ') + esc(i.num)}</b> ${esc(i.title || '')}
      ${i.date ? `<div class="dx-meta">Dated ${esc(i.date)} &middot; ${i.sheets} sheet(s)</div>` : ''}
      ${i.parts ? `<div class="dx-meta">${i.parts} sheets</div>` : ''}
      ${i.also ? `<div class="dx-meta">Also published as ${esc(i.also.map((x) => x.src + ' ' + (x.type === 'Standard drawing' ? x.num : 'p ' + x.num.replace(/^p/, ''))).join('; '))}</div>` : ''}
      ${i.sum ? `<div class="dx-sum">${esc(i.sum.slice(0, 150))}${i.sum.length > 150 ? '...' : ''}</div>` : ''}</div></a>`;

    function scoreItem(i, pq) {
      let sc = 0;
      if (pq.rawA) {
        if (i._na && i._na === pq.rawA) sc += 120;
        else if (i._na && pq.rawA.length >= 2 && i._na.startsWith(pq.rawA)) sc += 70;
      }
      if (pq.rawLow) {
        if (i._tl.includes(pq.rawLow)) sc += 45;
        else if (pq.words.length && pq.words.every((w) => i._tl.includes(w))) sc += 25;
      }
      for (const [id] of pq.ids) {
        if ((i.c || []).includes(id)) sc += 20;
      }
      if (i.src === 'CA MUTCD 2026' || i.src === 'Caltrans Std. Plans 2026' || i.src === 'MPP 531') sc += 8;
      if (i.src === 'Federal MUTCD') sc -= 12;
      if (i._sup) sc -= 30;
      return sc;
    }

    function run(reset = true) {
      const rawQ = $('dx-q').value;
      const pq = parse(rawQ);
      const sg = $('dx-sg').value, src = $('dx-src').value, ty = $('dx-type').value, tp = $('dx-topic').value;
      const nf = $('dx-noFed').checked, ns = $('dx-noSup') ? $('dx-noSup').checked : false;
      const sort = $('dx-sort') ? $('dx-sort').value : 'rel';

      const anyFilter = !!(rawQ.trim() || sg || src || ty || tp || nf || ns);
      if ($('dx-reset')) $('dx-reset').hidden = !anyFilter;

      // Show matched glossary concepts so engineers see synonym expansion at work
      const chips = $('dx-chips');
      if (chips) {
        if (pq.ids.length) {
          chips.innerHTML = '<span>Matched concepts:</span> ' + pq.ids.map(([id]) => {
            const g = GBY[id];
            return g ? `<a class="kchip" href="${BASE}/keywords/#c-${id}">${esc(g.term)}</a>` : '';
          }).join('');
          chips.hidden = false;
        } else {
          chips.hidden = true;
          chips.innerHTML = '';
        }
      }

      list = all.filter((i) => (!sg || i.sg === sg) && (!src || i.src === src) && (!ty || i.type === ty) && (!tp || (i.topics || []).includes(tp))
        && (!nf || i.src !== 'Federal MUTCD')
        && (!ns || !i._sup)
        && pq.ids.every(([id, t]) => (i.c || []).includes(id) || i._h.includes(t))
        && pq.words.every((w) => {
          const wa = alnum(w);
          return i._h.includes(w) || (wa.length >= 2 && i._na && i._na.includes(wa));
        }));

      if (sort === 'num') {
        list.sort((a, b) => (a.num || '').localeCompare(b.num || '', undefined, { numeric: true, sensitivity: 'base' }));
      } else if (sort === 'src') {
        list.sort((a, b) => (a.src || '').localeCompare(b.src || '') || (a.num || '').localeCompare(b.num || '', undefined, { numeric: true }));
      } else if (rawQ.trim()) {
        list.sort((a, b) => scoreItem(b, pq) - scoreItem(a, pq));
      } else {
        list.sort((a, b) => (a._sup ? 1 : 0) - (b._sup ? 1 : 0));
      }

      if (reset) { shown = 0; $('dx-grid').innerHTML = ''; }
      const next = list.slice(shown, shown + 90);
      $('dx-grid').insertAdjacentHTML('beforeend', next.map(card).join(''));
      shown += next.length;
      $('dx-count').textContent = `${list.length.toLocaleString()} of ${all.length.toLocaleString()} details`;
      $('dx-more').hidden = shown >= list.length;

      const u = new URLSearchParams();
      for (const [k, id] of [['q', 'dx-q'], ['sg', 'dx-sg'], ['src', 'dx-src'], ['type', 'dx-type'], ['topic', 'dx-topic']]) {
        if ($(id) && $(id).value) u.set(k, $(id).value);
      }
      if (sort && sort !== 'rel') u.set('sort', sort);
      if (nf) u.set('noFed', '1');
      if (ns) u.set('noSup', '1');
      history.replaceState(null, '', location.pathname + (u.toString() ? '?' + u : ''));
    }

    $('dx-sg').addEventListener('change', () => { populateSrcs($('dx-sg').value); run(); });
    root.querySelectorAll('input,select').forEach((e) => {
      if (e.id !== 'dx-sg') e.addEventListener(e.type === 'checkbox' || e.tagName === 'SELECT' ? 'change' : 'input', () => run());
    });
    if ($('dx-reset')) {
      $('dx-reset').onclick = () => {
        ['dx-q', 'dx-sg', 'dx-src', 'dx-type', 'dx-topic'].forEach((id) => { if ($(id)) $(id).value = ''; });
        if ($('dx-sort')) $('dx-sort').value = 'rel';
        $('dx-noFed').checked = false;
        if ($('dx-noSup')) $('dx-noSup').checked = false;
        populateSrcs('');
        run();
      };
    }
    $('dx-more').onclick = () => run(false);
    run();
  });
})();

/* ---------- session back / forward / recent pages, sheet jumper & keyboard prev/next ---------- */
(() => {
  const KEY = 'sss_recent_v1';
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  window.__ready(() => {
    // 1. Track recent pages in this browser tab
    const curUrl = location.pathname + location.search;
    const h1 = document.querySelector('h1');
    const curTitle = (h1 ? h1.textContent : document.title.split('|')[0]).trim();
    let list = [];
    try { list = JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    list = [{ u: curUrl, t: curTitle }, ...list.filter((x) => x && x.u !== curUrl)].slice(0, 14);
    try { sessionStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {}

    // Wire Back / Forward / Recent controls in topbar
    const backBtn = document.querySelector('[data-nav-back]');
    const fwdBtn = document.querySelector('[data-nav-fwd]');
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        if (history.length > 1) history.back();
        else {
          const prev = list.find((x) => x.u !== curUrl);
          if (prev) location.href = prev.u;
        }
      });
    }
    if (fwdBtn) {
      fwdBtn.addEventListener('click', () => history.forward());
    }

    const recBtn = document.querySelector('[data-recent-toggle]');
    const recMenu = document.querySelector('.sss-recent-menu');
    if (recBtn && recMenu) {
      const others = list.filter((x) => x.u !== curUrl);
      if (!others.length) {
        recBtn.disabled = true;
        recBtn.title = 'Visit another page to populate recent history';
      } else {
        recMenu.innerHTML = others
          .map((x) => `<a role="menuitem" href="${esc(x.u)}">${esc(x.t)}</a>`)
          .join('');
        const closeMenu = () => {
          recMenu.hidden = true;
          recBtn.setAttribute('aria-expanded', 'false');
        };
        recBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const open = recMenu.hidden;
          recMenu.hidden = !open;
          recBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('click', (e) => {
          if (!recMenu.hidden && !recMenu.contains(e.target) && e.target !== recBtn) closeMenu();
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
      }
    }

    // 2. Multi-page chapter sheet jumper (pages with 2+ <span id="pN" class="anchor">)
    const anchors = Array.from(document.querySelectorAll('main span.anchor[id^="p"]'));
    if (anchors.length >= 2) {
      const bar = document.createElement('nav');
      bar.className = 'sss-sheetbar print:hidden';
      bar.setAttribute('aria-label', 'Jump to page in this chapter');
      const items = anchors.map((sp) => {
        const num = sp.id.replace(/^p/, '');
        const nxt = sp.nextElementSibling;
        const tip = nxt ? nxt.textContent.trim() : `Page ${num}`;
        return { id: sp.id, num, tip, el: sp };
      });
      bar.innerHTML =
        `<button type="button" class="sss-sstep" data-step="-1" title="Previous page in chapter">&lsaquo; Prev</button>` +
        `<div class="sss-spills">${items.map((it, idx) => `<a href="#${esc(it.id)}" data-idx="${idx}" title="${esc(it.tip)}">p.${esc(it.num)}</a>`).join('')}</div>` +
        `<button type="button" class="sss-sstep" data-step="1" title="Next page in chapter">Next &rsaquo;</button>`;
      const srcbar = document.querySelector('main .srcbar');
      if (srcbar && srcbar.parentNode) srcbar.insertAdjacentElement('afterend', bar);
      else anchors[0].insertAdjacentElement('beforebegin', bar);

      const pills = Array.from(bar.querySelectorAll('.sss-spills a'));
      let curIdx = 0;
      const setActive = (idx) => {
        curIdx = Math.max(0, Math.min(items.length - 1, idx));
        pills.forEach((a, i) => a.classList.toggle('on', i === curIdx));
        const active = pills[curIdx];
        if (active && active.scrollIntoView) {
          try { active.scrollIntoView({ inline: 'nearest', block: 'nearest' }); } catch (e) {}
        }
      };
      const syncScroll = () => {
        const y = window.scrollY + 130;
        let best = 0;
        for (let i = 0; i < items.length; i++) {
          const top = items[i].el.getBoundingClientRect().top + window.scrollY;
          if (top <= y) best = i; else break;
        }
        if (best !== curIdx) setActive(best);
      };
      setActive(0);
      window.addEventListener('scroll', syncScroll, { passive: true });
      bar.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-step]');
        if (!btn) return;
        const targetIdx = Math.max(0, Math.min(items.length - 1, curIdx + Number(btn.dataset.step)));
        items[targetIdx].el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setActive(targetIdx);
      });
    }

    // 3. Keyboard shortcuts '[' (previous page) and ']' (next page)
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector('.sss-lb.open')) return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.key === '[') {
        const prev = document.querySelector('a[rel="prev"]');
        if (prev) { e.preventDefault(); prev.click(); }
      } else if (e.key === ']') {
        const next = document.querySelector('a[rel="next"]');
        if (next) { e.preventDefault(); next.click(); }
      }
    });
  });
})();

/* ---------- in-tab image viewer (lightbox with zoom, pan, prev/next stepping — zero new tabs) ---------- */
(() => {
  const IMG_EXT = /\.(?:webp|png|jpe?g|svg|gif)(?:[?#].*)?$/i;

  window.__ready(() => {
    const lb = document.createElement('div');
    lb.className = 'sss-lb';
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-label', 'Image viewer');
    lb.hidden = true;
    lb.innerHTML = `
      <div class="sss-lb-bar">
        <div class="sss-lb-title"><span class="sss-lb-count"></span><span class="sss-lb-cap"></span></div>
        <div class="sss-lb-ctrls">
          <button type="button" data-lb="prev" title="Previous image (Left arrow)">&larr; Prev</button>
          <button type="button" data-lb="next" title="Next image (Right arrow)">Next &rarr;</button>
          <span class="sss-lb-sep" aria-hidden="true"></span>
          <button type="button" data-lb="zout" title="Zoom out (-)">&minus;</button>
          <button type="button" data-lb="fit" title="Fit to window (0)">Fit</button>
          <button type="button" data-lb="zin" title="Zoom in (+)">+</button>
          <button type="button" class="sss-lb-close" data-lb="close" aria-label="Close image viewer (Esc)">&times;</button>
        </div>
      </div>
      <div class="sss-lb-stage">
        <img class="sss-lb-img" alt="" draggable="false" />
      </div>`;
    document.body.appendChild(lb);

    const imgEl = lb.querySelector('.sss-lb-img');
    const stage = lb.querySelector('.sss-lb-stage');
    const capEl = lb.querySelector('.sss-lb-cap');
    const cntEl = lb.querySelector('.sss-lb-count');
    const prevBtn = lb.querySelector('[data-lb="prev"]');
    const nextBtn = lb.querySelector('[data-lb="next"]');
    const fitBtn = lb.querySelector('[data-lb="fit"]');

    let gallery = [];
    let index = 0;
    let scale = 1, tx = 0, ty = 0;
    let dragging = false, didDrag = false, sx = 0, sy = 0, stx = 0, sty = 0;
    let lastFocus = null;

    const applyTransform = () => {
      imgEl.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      stage.classList.toggle('zoomed', scale > 1.02);
      fitBtn.textContent = scale === 1 ? 'Fit' : Math.round(scale * 100) + '%';
    };
    const resetZoom = () => { scale = 1; tx = 0; ty = 0; applyTransform(); };

    const captionFor = (el) => {
      const fig = el.closest('figure');
      if (fig) {
        const fc = fig.querySelector('figcaption');
        if (fc) return fc.textContent.trim();
      }
      const card = el.closest('.mcard, .ltc, .sdetail');
      if (card) {
        const h = card.querySelector('.mbody strong, .ltc-head b, .scode-big');
        if (h) return h.textContent.trim();
      }
      const im = el.tagName === 'IMG' ? el : el.querySelector('img');
      return (im && im.alt) || el.getAttribute('title') || el.textContent.trim() || 'Image';
    };

    const collectGallery = () => {
      const items = [];
      const seen = new Set();
      const root = document.querySelector('main') || document.body;
      root.querySelectorAll('a[href], .sdetail-img img, .ltc-pic img').forEach((el) => {
        if (el.closest('.sss-lb, .pv-tip, .sref-tip, nav, .rsign-grid')) return;
        let src = '';
        if (el.tagName === 'A') {
          const href = el.getAttribute('href') || '';
          if (!IMG_EXT.test(href)) return;
          src = el.href;
        } else {
          if (el.closest('a[href]')) return;
          src = el.currentSrc || el.src;
        }
        if (!src || seen.has(src)) return;
        seen.add(src);
        items.push({ src, cap: captionFor(el), el });
      });
      return items;
    };

    const renderItem = () => {
      const item = gallery[index];
      if (!item) return;
      resetZoom();
      imgEl.src = item.src;
      imgEl.alt = item.cap;
      capEl.textContent = item.cap;
      cntEl.textContent = gallery.length > 1 ? `${index + 1} / ${gallery.length}` : '';
      prevBtn.hidden = gallery.length <= 1;
      nextBtn.hidden = gallery.length <= 1;
      prevBtn.disabled = index <= 0;
      nextBtn.disabled = index >= gallery.length - 1;
    };

    const openAt = (src, fallbackEl) => {
      gallery = collectGallery();
      index = gallery.findIndex((x) => x.src === src);
      if (index < 0) {
        gallery.unshift({ src, cap: captionFor(fallbackEl), el: fallbackEl });
        index = 0;
      }
      lastFocus = document.activeElement;
      lb.hidden = false;
      lb.classList.add('open');
      document.documentElement.classList.add('sss-lb-lock');
      renderItem();
      lb.querySelector('[data-lb="close"]').focus();
    };

    const closeLb = () => {
      if (lb.hidden) return;
      lb.classList.remove('open');
      lb.hidden = true;
      document.documentElement.classList.remove('sss-lb-lock');
      imgEl.removeAttribute('src');
      if (lastFocus && lastFocus.focus) try { lastFocus.focus(); } catch (e) {}
    };

    const zoomBy = (factor) => {
      scale = Math.max(1, Math.min(6, +(scale * factor).toFixed(3)));
      if (scale === 1) { tx = 0; ty = 0; }
      applyTransform();
    };

    // Intercept clicks on any image link or standalone figure image inside main
    document.addEventListener('click', (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      if (e.target.closest('.sss-lb')) return;
      const a = e.target.closest('a[href]');
      if (a) {
        const href = a.getAttribute('href') || '';
        if (IMG_EXT.test(href)) {
          e.preventDefault();
          openAt(a.href, a);
          return;
        }
        return;
      }
      const im = e.target.closest('.sdetail-img img, .ltc-pic img, .dfig img, .mfig img');
      if (im && (im.currentSrc || im.src)) {
        e.preventDefault();
        openAt(im.currentSrc || im.src, im);
      }
    });

    // Toolbar actions
    lb.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-lb]');
      if (btn) {
        const act = btn.dataset.lb;
        if (act === 'close') closeLb();
        else if (act === 'prev' && index > 0) { index--; renderItem(); }
        else if (act === 'next' && index < gallery.length - 1) { index++; renderItem(); }
        else if (act === 'zin') zoomBy(1.35);
        else if (act === 'zout') zoomBy(1 / 1.35);
        else if (act === 'fit') resetZoom();
        return;
      }
      // Click on backdrop closes viewer (not when finishing a pan drag)
      if (didDrag) { didDrag = false; return; }
      if (e.target === stage) closeLb();
    });

    // Double-click toggles Fit <-> 220% zoom
    stage.addEventListener('dblclick', (e) => {
      if (e.target !== imgEl && e.target !== stage) return;
      if (scale > 1.05) resetZoom();
      else { scale = 2.2; tx = 0; ty = 0; applyTransform(); }
    });

    // Wheel zoom
    stage.addEventListener('wheel', (e) => {
      if (lb.hidden) return;
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? 1.18 : 1 / 1.18);
    }, { passive: false });

    // Drag to pan when zoomed
    stage.addEventListener('pointerdown', (e) => {
      if (scale <= 1.02 || e.button !== 0) return;
      dragging = true;
      didDrag = false;
      sx = e.clientX; sy = e.clientY; stx = tx; sty = ty;
      stage.classList.add('dragging');
      stage.setPointerCapture && stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (Math.hypot(dx, dy) > 4) didDrag = true;
      tx = stx + dx;
      ty = sty + dy;
      applyTransform();
    });
    const endDrag = () => { dragging = false; stage.classList.remove('dragging'); };
    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);

    // Keyboard controls inside lightbox
    document.addEventListener('keydown', (e) => {
      if (lb.hidden) return;
      if (e.key === 'Escape') { e.preventDefault(); closeLb(); }
      else if (e.key === 'ArrowLeft' && index > 0) { e.preventDefault(); index--; renderItem(); }
      else if (e.key === 'ArrowRight' && index < gallery.length - 1) { e.preventDefault(); index++; renderItem(); }
      else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoomBy(1.3); }
      else if (e.key === '-') { e.preventDefault(); zoomBy(1 / 1.3); }
      else if (e.key === '0') { e.preventDefault(); resetZoom(); }
    });
  });
})();

