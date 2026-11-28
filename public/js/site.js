window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));

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
  document.addEventListener('focusin', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a?.dataset.svg) show(a); });
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
    hideP(); pvCur = a;
    pvTimer = setTimeout(() => showP(a), 220);
  });
  document.addEventListener('mouseout', (ev) => { if (pvCur && !(ev.relatedTarget && pvCur.contains(ev.relatedTarget))) hideP(); });
  document.addEventListener('scroll', hideP, { passive: true });

  // Back-to-top button, reading progress, sidebar active scroll, and '/' search shortcut
  window.__ready(() => {
    const b = document.createElement('button');
    b.className = 'to-top'; b.type = 'button'; b.setAttribute('aria-label', 'Back to top'); b.textContent = 'Top';
    b.onclick = () => scrollTo({ top: 0, behavior: 'smooth' });
    const footer = document.querySelector('main footer') || document.querySelector('main') || document.body;
    footer.appendChild(b);
    const bar = document.createElement('div'); bar.className = 'read-bar'; document.body.appendChild(bar);
    addEventListener('scroll', () => {
      const h = document.documentElement; const p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
      bar.style.transform = `scaleX(${p})`; b.classList.toggle('show', h.scrollTop > 600);
    }, { passive: true });

    // Auto-expand and jump sidebar to current page (or closest parent section on deep pages)
    const side = document.getElementById('starlight__sidebar');
    if (side) {
      let curSide = side.querySelector('a[aria-current="page"]');
      if (!curSide) {
        const curPath = location.pathname.replace(/\/?$/, '/');
        let best = null, bestLen = 0;
        side.querySelectorAll('a[href]').forEach((a) => {
          try {
            const p = new URL(a.href, location.href).pathname.replace(/\/?$/, '/');
            if (p !== BASEP + '/' && curPath.startsWith(p) && p.length > bestLen) {
              best = a;
              bestLen = p.length;
            }
          } catch (e) {}
        });
        if (best) {
          curSide = best;
          curSide.classList.add('sss-side-parent');
        }
      }
      if (curSide) {
        let det = curSide.closest('details');
        while (det) {
          det.open = true;
          det = det.parentElement && det.parentElement.closest('details');
        }
        function revealCurrentInSidebar() {
          const panel = side.getBoundingClientRect(), link = curSide.getBoundingClientRect();
          if (panel.height && (link.top < panel.top || link.bottom > panel.bottom)) {
            side.scrollTop += link.top - panel.top - (panel.height - link.height) / 2;
          }
        }
        requestAnimationFrame(revealCurrentInSidebar);
        side.addEventListener('toggle', event => {
          if (event.target === side && event.newState === 'open') revealCurrentInSidebar();
        });
      }
    }

    // Pressing '/' focuses the primary on-page filter/lookup input (or opens site search)
    document.addEventListener('keydown', (e) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      const target = document.querySelector('#standards-query, .quick-lookup input, #dx-q, #sq, #mq, #ltq, #kq, #dwq');
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
  const search = raw => window.SSSSearch.direct(raw);

  function mount(el) {
    const inp = el.querySelector('input');
    const res = el.querySelector('.ql-res');
    const clearBtn = el.querySelector('.ql-clear');
    const fullBtn = el.querySelector('[data-open-search]');
    let t, idx = -1, items = [], renderedQuery = '', request = 0;
    res.id ||= 'lookup-list-' + [...document.querySelectorAll('.quick-lookup')].indexOf(el);
    inp.setAttribute('role', 'combobox');
    inp.setAttribute('aria-autocomplete', 'list');
    inp.setAttribute('aria-controls', res.id);
    inp.setAttribute('aria-expanded', 'false');
    const close = () => {
      request++;
      clearTimeout(t);
      idx = -1;
      res.classList.remove('open');
      inp.setAttribute('aria-expanded', 'false');
      inp.removeAttribute('aria-activedescendant');
    };

    const setActive = (next) => {
      const links = [...res.querySelectorAll('a.ql-item, button.ql-all')];
      if (!links.length) { idx = -1; return; }
      idx = ((next % links.length) + links.length) % links.length;
      links.forEach((a, i) => {
        a.classList.toggle('active', i === idx);
        a.setAttribute('aria-selected', String(i === idx));
      });
      inp.setAttribute('aria-activedescendant', links[idx].id);
      links[idx].scrollIntoView({ block: 'nearest' });
    };

    const render = (list, raw) => {
      renderedQuery = raw;
      inp.removeAttribute('aria-activedescendant');
      items = list;
      idx = -1;
      if (!raw.trim()) {
        res.innerHTML = '';
        close();
        return;
      }
      const rows = list.map((r, i) =>
        `<a class="ql-item" id="${res.id}-${i}" role="option" aria-selected="false" href="${r.url}"><span class="ql-tag ${r.cls}">${esc(r.tag)}</span><span class="ql-lbl">${esc(r.label)}</span></a>`
      ).join('');
      const empty = !list.length ? `<div class="ql-empty">No direct code or title match for &ldquo;${esc(raw.trim())}&rdquo;.</div>` : '';
      const footer = `<button type="button" class="ql-all" id="${res.id}-full" role="option" aria-selected="false">See all results for &ldquo;${esc(raw.trim())}&rdquo; &rarr;</button>`;
      res.innerHTML = rows + empty + footer;
      res.classList.add('open');
      inp.setAttribute('aria-expanded', 'true');
      const allBtn = res.querySelector('.ql-all');
      if (allBtn) allBtn.onclick = () => window.__openSiteSearch(inp.value);
    };

    const runQuery = async () => {
      const raw = inp.value;
      if (clearBtn) clearBtn.hidden = !raw;
      if (!raw.trim()) { render([], ''); return; }
      const sequence = ++request;
      try {
        const r = await search(raw);
        if (sequence === request && inp.value === raw) render(r, raw);
      } catch {
        if (sequence === request && inp.value === raw) {
          render([], raw);
          res.querySelector('.ql-empty').textContent = 'Quick lookup is unavailable. Try full-text search.';
        }
      }
    };

    inp.addEventListener('input', () => {
      if (clearBtn) clearBtn.hidden = !inp.value;
      close();
      if (inp.value.trim()) t = setTimeout(runQuery, 110);
    });
    inp.addEventListener('focus', () => { if (inp.value.trim() && !res.classList.contains('open')) runQuery(); });
    inp.addEventListener('keydown', async (e) => {
      if (e.key === 'Tab') { close(); return; }
      if (['ArrowUp','ArrowDown'].includes(e.key) && !res.classList.contains('open')) {
        if (!inp.value.trim()) return;
        e.preventDefault();
        await runQuery();
        if (res.classList.contains('open')) setActive(e.key === 'ArrowUp' ? -1 : 0);
        return;
      }
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(idx + 1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActive(idx < 0 ? -1 : idx - 1); return; }
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const links = [...res.querySelectorAll('a.ql-item, button.ql-all')];
      if (idx >= 0 && links[idx]) { links[idx].click(); return; }
      const query = inp.value;
      if (!query.trim()) return;
      const r = renderedQuery === query ? items : await search(query).catch(() => []);
      if (inp.value !== query) return;
      if (r.length && !r[0].missingSheet && !(r.length > 1 && r[0].sheetMatch)) location.href = r[0].url;
      else window.__openSiteSearch(query);
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
      if (!el.contains(ev.target) && !(wrap && wrap.contains(ev.target))) close();
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
    const agency = p.get('sg') || p.get('agency');
    if (agency) $('dx-sg').value = agency;
    populateSrcs($('dx-sg').value, p.get('src') || '');
    for (const [k, id] of [['q', 'dx-q'], ['type', 'dx-type'], ['topic', 'dx-topic'], ['sort', 'dx-sort']]) {
      if (p.get(k) && $(id)) $(id).value = p.get(k);
    }
    if (p.get('noFed') === '1') $('dx-noFed').checked = true;

    let shown = 0, list = [];
    const card = (i) => `<a class="dx-card" href="${i.url}">${i.img ? `<div class="dx-img"><img loading="lazy" src="${i.img}" alt=""></div>` : ''}
      <div class="dx-body"><div class="dx-tags"><span class="dx-tag ${i.sg === 'MUTCD' ? (i.src.startsWith('CA') ? 'c' : 'f') : 'l'}">${esc(i.src)}</span></div>
      <b>${i.type === 'Figure page' ? '' : (i.type === 'Standard drawing' ? '' : esc(i.type) + ' ') + esc(i.num)}</b> ${esc(i.title || '')}
      ${i.date ? `<div class="dx-meta">${esc(i.date)}</div>` : ''}</div></a>`;

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
      return sc;
    }

    function run(reset = true) {
      const rawQ = $('dx-q').value;
      const pq = parse(rawQ);
      const sg = $('dx-sg').value, src = $('dx-src').value, ty = $('dx-type').value, tp = $('dx-topic').value;
      const nf = $('dx-noFed').checked;
      const sort = $('dx-sort') ? $('dx-sort').value : 'rel';

      const anyFilter = !!(rawQ.trim() || sg || src || ty || tp || nf);
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
        populateSrcs('');
        run();
      };
    }
    $('dx-more').onclick = () => run(false);
    run();
  });
})();

/* ---------- chapter sheet navigation and keyboard shortcuts ---------- */
(() => {
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('"','&quot;')
    .replaceAll('<','&lt;').replaceAll('>','&gt;');
  window.__ready(() => {
    // 2. Multi-page chapter sheet jumper (pages with 2+ <span id="pN" class="anchor"> that do NOT already use the full sheet deck)
    const anchors = Array.from(document.querySelectorAll('main span.anchor[id^="p"]'));
    if (anchors.length >= 2 && !document.querySelector('.sheet-controls')) {
      const bar = document.createElement('nav');
      bar.className = 'sss-sheetbar not-content print:hidden';
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


window.__ready(() => {
  const input = document.getElementById('boe-filter');
  if (!input) return;
  const groups = [...document.querySelectorAll('.boe-group')];
  const count = document.getElementById('boe-count');
  const clean = value => value.toLowerCase().replace(/\be[\s-]*(?=\d)/g, 'e').replace(/[^a-z0-9]+/g, ' ').trim();
  let prior = null;
  input.addEventListener('input', () => {
    const terms = clean(input.value).split(' ').filter(Boolean);
    if (terms.length && !prior) prior = groups.map(group => group.open);
    let matches = 0;
    groups.forEach((group,i) => {
      let found = 0;
      group.querySelectorAll('li').forEach(row => {
        row.hidden = !terms.every(t => clean(row.textContent).includes(t));
        if (!row.hidden) found++;
      });
      group.hidden = !found;
      if (terms.length || prior) group.open = terms.length ? !!found : prior[i];
      matches += found;
    });
    count.textContent = terms.length ? (matches ? matches+' matching sections' : 'No matching sections. Try a shorter term or a section number.') : '';
    if (!terms.length) prior = null;
  });
});

// Use the published anchors, including raw publisher headings whose IDs live on a parent.
window.__ready(() => {
  const control=document.querySelector('.section-jump');
  const article=document.querySelector('.sl-markdown-content');
  if(!control || !article || article.querySelector('[data-atlas]'))return;
  const select=control.querySelector('select');
  const groups=[...article.querySelectorAll('h2')].filter(h=>!h.closest('details,.reg-page,.operator-book,.publication,.dfig,[hidden]'));
  for(const h of groups){
    const name=h.textContent.replace(/\s+/g,' ').trim();
    if(!name)continue;
    const section=h.closest('section[id]');
    let target=h.id || (section?.querySelector('h2')===h ? section.id : '');
    if(!target){
      let i=1;do{target='read-section-'+i++;}while(document.getElementById(target));
      h.id=target;
    }
    select.add(new Option(name,target));
  }
  if(select.options.length<3)return;
  control.hidden=false;
  select.onchange=()=>{
    const target=document.getElementById(select.value);
    if(!target)return;
    const menu=control.closest('details');
    if(menu)menu.open=false;
    if(location.hash==='#'+encodeURIComponent(target.id))target.scrollIntoView();
    else location.hash=encodeURIComponent(target.id);
    if(!target.hasAttribute('tabindex'))target.tabIndex=-1;
    target.focus({preventScroll:true});
  };
  const sync=()=>{let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}select.value=[...select.options].some(opt=>opt.value===id)?id:'';};
  sync();window.addEventListener('hashchange',sync);
});

window.__ready(() => {
  const reader=document.querySelector('[data-publisher-pdf]');
  if(!reader)return;
  const input=reader.querySelector('input'),frame=document.createElement('iframe');
  frame.title='Riverside Transit Agency Bus Stop Design Guidelines';
  reader.querySelector('button').onclick=()=>{
    const page=Math.max(1,Math.min(Number(reader.dataset.pages),Number.parseInt(input.value,10)||1));
    input.value=String(page);frame.src=reader.dataset.publisherPdf+'#page='+page+'&view=FitH';
    reader.querySelector('div').replaceChildren(frame);
  };
});

// Dismiss navigation menus without moving a reader's scroll position.
window.__ready(() => {
  const menus=[...document.querySelectorAll('.nav-menu,.page-navigation')];
  document.addEventListener('click',event=>{
    for(const menu of menus)if(menu.open&&!menu.contains(event.target))menu.open=false;
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const menu=menus.find(item=>item.open&&item.contains(document.activeElement))||menus.find(item=>item.open);
    if(menu){menu.open=false;menu.querySelector('summary')?.focus({preventScroll:true});}
  });
});

/* Every download takes two clicks: the first click asks, the second one downloads (or builds the PDF). */
(() => {
  const FILE = /\.(dwg|dxf|zip|lsp|lin|ctb|dwt|scr|dgn|xlsx|csv|svg)(\?|#|$)/i;
  const LABEL = /\b(pdf|download|dwg|zip|dxf)\b/i;
  const isDownload = el => {
    if (el.matches('a[href]')) return el.hasAttribute('download') || FILE.test(el.getAttribute('href'));
    return el.matches('button') && LABEL.test(el.textContent) && !/^\s*copy\b/i.test(el.textContent) && !el.closest('[data-no-confirm]');
  };
  const disarm = el => {
    if (!el.dataset.dlArmed) return;
    el.innerHTML = el.dataset.dlHtml;
    delete el.dataset.dlArmed; delete el.dataset.dlHtml;
    el.classList.remove('dl-armed');
  };
  document.addEventListener('click', e => {
    if (!e.isTrusted || e.button !== 0 || e.ctrlKey || e.metaKey) return;
    const el = e.target.closest('a[href], button');
    if (!el || el.matches('[data-block-add], .block-zoom') || !isDownload(el)) return;
    if (el.dataset.dlArmed) { disarm(el); return; }        // second click: download
    e.preventDefault(); e.stopImmediatePropagation();
    for (const other of document.querySelectorAll('[data-dl-armed]')) disarm(other);
    el.dataset.dlArmed = '1';
    el.dataset.dlHtml = el.innerHTML;
    el.classList.add('dl-armed');
    el.textContent = 'Click again to download';
    setTimeout(() => disarm(el), 6000);
  }, true);
})();
