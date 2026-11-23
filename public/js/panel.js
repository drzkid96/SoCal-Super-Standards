// Right-edge utility drawer on every page: Checks | Ask (AI) | Calc (Traffic Engineering Calculators)
(() => {
  const BASE = '/SoCal-Super-Standards';
  const OPEN_KEY = 'sss-panel-open', TAB_KEY = 'sss-panel-tab';
  const ls = { get: (k, d = '') => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  const path = location.pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
  const kind = path.includes('/details/') ? 'detail' : path.includes('/signs/') && !path.endsWith('/signs/') ? 'sign'
    : path.includes('/bulletins/') ? 'bulletin' : /\/(mutcd|ca-mutcd)\//.test(path) ? 'manual' : 'page';

  const PRESETS = {
    detail: [
      ['Summarize sheet', 'Summarize this sheet and its key dimensions'],
      ['Checklist', 'Plan review checklist for this drawing'],
      ['What supersedes?', 'What could supersede this drawing?'],
    ],
    sign: [
      ['Summarize sign', 'Summarize where and how to use this sign'],
      ['Is it current?', 'Is this sign current in California or superseded?'],
    ],
    manual: [
      ['Summarize', 'Summarize this chapter'],
      ['Checklist', 'Plan review checklist'],
      ['What supersedes?', 'What could supersede this section?'],
    ],
    bulletin: [
      ['Key values', 'Key values and design criteria'],
      ['Checklist', 'Plan review checklist'],
    ],
    page: [
      ['Summarize', 'Summarize this page'],
      ['Checklist', 'Plan review checklist'],
      ['What supersedes?', 'What could supersede this page?'],
    ],
  };

  let checks = [];
  const ui = document.createElement('aside');
  ui.className = 'sp';
  ui.setAttribute('aria-label', 'Checks, Ask AI, and Calculators');
  ui.innerHTML = `
    <button class="sp-tab" type="button" aria-expanded="false" title="Checks, Ask AI &amp; Calculators"><span class="sp-tab-t">Tools</span><span class="sp-n"></span></button>
    <div class="sp-body" hidden>
      <div class="sp-head">
        <div class="sp-tabs" role="tablist">
          <button role="tab" data-t="checks" type="button">Checks</button>
          <button role="tab" data-t="ask" type="button">Ask AI</button>
          <button role="tab" data-t="calc" type="button">Calc</button>
        </div>
        <button class="sp-x" type="button" aria-label="Close panel">&times;</button>
      </div>

      <section class="sp-pane" data-p="checks"></section>

      <section class="sp-pane" data-p="ask" hidden>
        <div class="sp-ai-bar" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.35rem;margin-bottom:0.45rem;padding:0.4rem 0.5rem;background:var(--fp-cream,#EEEDE8);border-radius:8px;font-size:0.74rem">
          <span class="sp-ai-st" style="flex:1 1 120px">Instant search ready</span>
          <div style="display:flex;gap:0.3rem;align-items:center">
            <button type="button" class="sp-ai-oauth" style="font:inherit;font-weight:600;padding:0.15rem 0.45rem;border:1px solid var(--fp-emerald,#00574A);border-radius:6px;background:var(--fp-emerald,#00574A);color:#fff;cursor:pointer" title="1-click sign-in via OpenRouter (Google/GitHub)">Connect</button>
            <button type="button" class="sp-ai-load" style="font:inherit;font-weight:600;padding:0.15rem 0.45rem;border:1px solid var(--fp-emerald,#00574A);border-radius:6px;background:#fff;color:var(--fp-emerald,#00574A);cursor:pointer" title="Free local in-browser model (no account)">Local AI</button>
          </div>
        </div>
        <div class="sp-pre"></div>
        <textarea rows="2" placeholder="Ask about this page or any SoCal standard..."></textarea>
        <div class="sp-row">
          <button type="button" class="sp-send">Ask</button>
          <button type="button" class="sp-clear">Clear</button>
        </div>
        <div class="sp-out" aria-live="polite"></div>
      </section>

      <section class="sp-pane" data-p="calc" hidden>
        <div style="display:flex;flex-direction:column;gap:0.75rem;font-size:0.82rem">
          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">Quick Arithmetic Calculator</strong>
            <input id="c-arith-in" type="text" inputmode="decimal" placeholder="e.g. (44 - 12*2) / 2" aria-label="Calculator expression" style="width:100%;box-sizing:border-box;padding:0.4rem 0.55rem;border:1px solid #D0D4D4;border-radius:6px;font-family:ui-monospace,monospace;font-size:0.95rem;text-align:right;margin-bottom:0.35rem">
            <div id="c-arith-res" style="text-align:right;font-family:ui-monospace,monospace;font-weight:700;font-size:0.9rem;color:var(--fp-emerald,#00574A);min-height:1.25rem;margin-bottom:0.4rem"></div>
            <div id="c-arith-pad" style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.28rem">
              <button type="button" data-k="C" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#F2F2F2;font-weight:700;cursor:pointer">C</button>
              <button type="button" data-k="B" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#F2F2F2;font-weight:700;cursor:pointer">&larr;</button>
              <button type="button" data-k="(" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#F2F2F2;cursor:pointer">(</button>
              <button type="button" data-k=")" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#F2F2F2;cursor:pointer">)</button>
              <button type="button" data-k="7" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">7</button>
              <button type="button" data-k="8" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">8</button>
              <button type="button" data-k="9" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">9</button>
              <button type="button" data-k="/" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:var(--fp-pale-green,#D9F1D6);font-weight:700;cursor:pointer">&divide;</button>
              <button type="button" data-k="4" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">4</button>
              <button type="button" data-k="5" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">5</button>
              <button type="button" data-k="6" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">6</button>
              <button type="button" data-k="*" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:var(--fp-pale-green,#D9F1D6);font-weight:700;cursor:pointer">&times;</button>
              <button type="button" data-k="1" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">1</button>
              <button type="button" data-k="2" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">2</button>
              <button type="button" data-k="3" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">3</button>
              <button type="button" data-k="-" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:var(--fp-pale-green,#D9F1D6);font-weight:700;cursor:pointer">&minus;</button>
              <button type="button" data-k="0" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">0</button>
              <button type="button" data-k="." style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:#fff;cursor:pointer">.</button>
              <button type="button" data-k="=" style="padding:0.35rem;border:1px solid var(--fp-emerald,#00574A);border-radius:6px;background:var(--fp-emerald,#00574A);color:#fff;font-weight:700;cursor:pointer">=</button>
              <button type="button" data-k="+" style="padding:0.35rem;border:1px solid #D0D4D4;border-radius:6px;background:var(--fp-pale-green,#D9F1D6);font-weight:700;cursor:pointer">+</button>
            </div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">1. Work-Zone Taper &amp; Buffer (CA MUTCD 6C)</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Speed (mph)<input id="c-spd" type="number" value="35" min="15" max="70" step="5" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Lane W (ft)<input id="c-lw" type="number" value="12" min="8" max="16" step="1" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-tcp-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">2. ADA Curb Ramp Run (Caltrans A88A)</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Curb Ht (in)<input id="c-ch" type="number" value="6" min="2" max="12" step="0.5" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Slope (%)<input id="c-sl" type="number" value="7.5" min="4" max="8.33" step="0.25" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-ramp-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">3. Ped Signal Walk + FDW (CA MUTCD 4I.06)</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Cross Dist (ft)<input id="c-cd" type="number" value="56" min="15" max="160" step="2" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Walk (sec)<input id="c-wk" type="number" value="7" min="4" max="20" step="1" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-ped-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">4. Red Curb &amp; Stopping Sight Dist.</strong>
            <div style="display:grid;grid-template-columns:1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Approach Speed (mph)<input id="c-ssd-v" type="number" value="35" min="15" max="65" step="5" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-ssd-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
            <p style="margin:0.4rem 0 0;font-size:0.74rem"><a href="${BASE}/ladot/curb-paint/">Full LADOT S-481.0 Red Curb Calculator &rarr;</a></p>
          </div>
        </div>
      </section>
    </div>`;

  const $ = (s) => ui.querySelector(s);
  function setOpen(o) {
    $('.sp-body').hidden = !o;
    $('.sp-tab').setAttribute('aria-expanded', String(o));
    ui.classList.toggle('open', o);
    document.documentElement.classList.toggle('sp-open', o);
    ls.set(OPEN_KEY, o ? '1' : '0');
  }
  function setTab(t) {
    ui.querySelectorAll('.sp-tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.t === t)));
    ui.querySelectorAll('.sp-pane').forEach((p) => (p.hidden = p.dataset.p !== t));
    ls.set(TAB_KEY, t);
  }

  window.SSSPanel = {
    open: (tab) => { setOpen(true); if (tab) setTab(tab); },
    close: () => setOpen(false),
  };

  function updateCalcs() {
    // 1. Work-zone taper (CA MUTCD Table 6C-3/4)
    const S = Math.max(15, Number($('#c-spd')?.value) || 35);
    const W = Math.max(8, Number($('#c-lw')?.value) || 12);
    const L = S <= 40 ? Math.ceil((W * S * S) / 60) : Math.ceil(W * S);
    const shiftL = Math.ceil(L / 2);
    const shldL = Math.ceil(L / 3);
    const ssdBuf = Math.round(1.47 * S * 2.5 + (S * S) / (30 * 0.348));
    $('#c-tcp-out').innerHTML = `Merge taper <b>L = ${L} ft</b> · Shift <b>${shiftL} ft</b> · Shoulder <b>${shldL} ft</b><br>Buffer (SSD): <b>${ssdBuf} ft</b> · Cone spacing: <b>${S} ft</b> taper / <b>${Math.min(100, S * 2)} ft</b> tangent`;

    // 2. ADA Curb Ramp Run
    const ch = Math.max(1, Number($('#c-ch')?.value) || 6);
    const sl = Math.min(8.33, Math.max(2, Number($('#c-sl')?.value) || 7.5));
    const runFt = ((ch / 12) / (sl / 100)).toFixed(1);
    const minRunFt = ((ch / 12) / 0.0833).toFixed(1);
    $('#c-ramp-out').innerHTML = `Design run @ ${sl}%: <b>${runFt} ft</b> (8.33% abs min: <b>${minRunFt} ft</b>)<br>Landing: <b>4 ft min</b> (2% max) · Flare: <b>10% max</b>`;

    // 3. Ped Signal Timing (CA MUTCD 4I.06)
    const cd = Math.max(10, Number($('#c-cd')?.value) || 56);
    const wk = Math.max(4, Number($('#c-wk')?.value) || 7);
    const fdw = Math.ceil(cd / 3.5);
    const totalMin = Math.ceil(cd / 3.0);
    const total = Math.max(wk + fdw, totalMin);
    $('#c-ped-out').innerHTML = `FDW (@ 3.5 ft/s): <b>${fdw} sec</b> · Total Walk+FDW: <b>${total} sec</b><br><span style="opacity:0.8">(Checks 3.0 ft/s curb-to-curb min = ${totalMin} sec)</span>`;

    // 4. Red Curb / SSD
    const v = Math.max(15, Number($('#c-ssd-v')?.value) || 35);
    const ssd = Math.round(1.47 * v * 2.5 + (v * v) / (30 * 0.348));
    $('#c-ssd-out').innerHTML = `Stopping Sight Distance: <b>${ssd} ft</b><br>CA AB 413 Daylighting: <b>20 ft</b> min (<b>15 ft</b> w/ curb ext.)`;
  }

  function evalArith(commit) {
    const inp = $('#c-arith-in'), res = $('#c-arith-res');
    if (!inp || !res) return;
    const raw = inp.value.replace(/[×x]/gi, '*').replace(/÷/g, '/').replace(/−/g, '-').trim();
    if (!raw) { res.textContent = ''; return; }
    if (!/^[0-9+\-*/().\s%]+$/.test(raw)) { res.textContent = 'Invalid expression'; return; }
    try {
      const val = Function('"use strict"; return (' + raw + ')')();
      if (typeof val === 'number' && Number.isFinite(val)) {
        const fmt = Number(val.toFixed(6)).toString();
        res.textContent = '= ' + fmt;
        if (commit) inp.value = fmt;
      } else {
        res.textContent = 'Error';
      }
    } catch {
      if (commit) res.textContent = 'Error';
    }
  }
  $('#c-arith-in')?.addEventListener('input', () => evalArith(false));
  $('#c-arith-in')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); evalArith(true); } });
  $('#c-arith-pad')?.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-k]');
    const inp = $('#c-arith-in');
    if (!btn || !inp) return;
    const k = btn.dataset.k;
    if (k === 'C') { inp.value = ''; $('#c-arith-res').textContent = ''; }
    else if (k === 'B') { inp.value = inp.value.slice(0, -1); evalArith(false); }
    else if (k === '=') { evalArith(true); }
    else { inp.value += k; evalArith(false); }
    inp.focus();
  });

  function renderChecks() {
    const n = checks.filter((c) => c.sev === 'warn').length;
    $('.sp-n').textContent = checks.length ? String(checks.length) : '';
    ui.classList.toggle('has-warn', n > 0);
    $('[data-p="checks"]').innerHTML = checks.length
      ? checks.map((c) => `<div class="sp-c sp-${c.sev}">
          <div class="sp-ct"><span class="sp-b">${c.sev === 'warn' ? 'Check' : 'In effect'}</span>${esc(c.title)}</div>
          ${c.for ? `<div class="sp-for">Applies to ${esc(c.for)}</div>` : ''}
          <p>${esc(c.text)}</p>
          <div class="sp-links">${c.links.map(([t, u]) => `<a href="${esc(safeUrl(u))}">${esc(t)}</a>`).join('')}</div></div>`).join('')
        + cite() + `<p class="sp-foot"><a href="${BASE}/bulletins/standards-status/">How checks work and current editions</a></p>`
      : `<p class="sp-none">No supersedence flags for this page.</p>${cite()}<p class="sp-foot"><a href="${BASE}/bulletins/standards-status/">Current editions of each standard</a></p>`;
  }

  function cite() {
    return kind === 'detail' || kind === 'sign' ? `<p><button type="button" class="sp-cite">Copy citation</button></p>` : '';
  }
  function citation() {
    const h1 = (document.querySelector('h1')?.innerText || document.title).trim();
    const date = [...document.querySelectorAll('.sl-markdown-content td, .sl-markdown-content p')].map((e) => e.innerText).join(' ').match(/\b(?:dated|Date[d:]?)\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})/i);
    return `${h1}${date ? ` (sheet dated ${date[1]})` : ''}. SoCal Super Standards, accessed ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}. ${location.href}`;
  }

  function pageText() {
    const m = document.querySelector('.sl-markdown-content') || document.querySelector('main');
    return (m ? m.innerText : '').replace(/\n{3,}/g, '\n\n').slice(0, 14000);
  }

  async function ask(q) {
    const out = $('.sp-out');
    if (!out) return;
    const item = document.createElement('div');
    item.className = 'sp-a';
    item.innerHTML = `<div class="sp-q">${esc(q)}</div><div class="sp-r">Searching...</div>`;
    out.prepend(item);
    try {
      if (!window.SSSAsk) throw new Error('Search engine is still loading — try again in a moment.');
      const r = await window.SSSAsk.askSite(q, {
        pageText: pageText(),
        pageChecks: checks,
        onLog: (m) => { item.querySelector('.sp-r').textContent = m; },
      });
      item.querySelector('.sp-r').innerHTML = window.SSSAsk.renderResultHTML(r);
    } catch (e) {
      item.querySelector('.sp-r').textContent = e.message;
    }
  }

  window.__ready(async () => {
    document.body.append(ui);
    $('.sp-pre').innerHTML = (PRESETS[kind] || PRESETS.page).map(([t], i) => `<button type="button" data-i="${i}">${esc(t)}</button>`).join('');
    $('.sp-pre').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) ask((PRESETS[kind] || PRESETS.page)[b.dataset.i][1]); });
    $('.sp-send').addEventListener('click', () => { const t = $('textarea').value.trim(); if (t) ask(t); });
    $('textarea').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const t = $('textarea').value.trim(); if (t) ask(t); } });
    $('.sp-clear').addEventListener('click', () => { $('.sp-out').innerHTML = ''; $('textarea').value = ''; });

    // Sync AI loader & OAuth status into sidebar Ask tab
    const aiSt = $('.sp-ai-st'), aiLoad = $('.sp-ai-load'), aiOauth = $('.sp-ai-oauth');
    if (window.SSSAsk) {
      window.SSSAsk.onStatus(({ mode, loading, msg }) => {
        if (aiSt) aiSt.textContent = msg;
        if (aiOauth) aiOauth.textContent = mode === 'openrouter' ? 'Disconnect' : 'Connect';
        if (aiLoad) {
          if (mode === 'web-ai' || mode === 'chrome-ai') { aiLoad.textContent = 'Local Ready'; aiLoad.disabled = true; }
          else if (loading) { aiLoad.textContent = 'Loading...'; aiLoad.disabled = true; }
          else { aiLoad.textContent = 'Local AI'; aiLoad.disabled = false; }
        }
      });
    }
    if (aiOauth) aiOauth.onclick = () => {
      if (!window.SSSAsk) return;
      if (window.SSSAsk.getState().mode === 'openrouter') window.SSSAsk.disconnectOAuth();
      else window.SSSAsk.startOAuth();
    };
    if (aiLoad) aiLoad.onclick = () => { window.SSSAsk && window.SSSAsk.enableBrowserAI().catch(() => {}); };

    // Wire live calculators
    ['#c-spd', '#c-lw', '#c-ch', '#c-sl', '#c-cd', '#c-wk', '#c-ssd-v'].forEach((id) => {
      const el = $(id);
      if (el) el.addEventListener('input', updateCalcs);
    });
    updateCalcs();

    $('[data-p="checks"]').addEventListener('click', async (e) => {
      const b = e.target.closest('.sp-cite'); if (!b) return;
      try { await navigator.clipboard.writeText(citation()); b.textContent = 'Copied'; } catch { b.textContent = citation(); }
      setTimeout(() => (b.textContent = 'Copy citation'), 1800);
    });
    $('.sp-tab').addEventListener('click', () => setOpen($('.sp-body').hidden));
    $('.sp-x').addEventListener('click', () => setOpen(false));
    ui.querySelector('.sp-tabs').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setTab(b.dataset.t); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ui.classList.contains('open')) setOpen(false); });
    setTab(ls.get(TAB_KEY, 'checks'));
    try {
      const ckKey = 'sss_checks_' + ((document.querySelector('script[src*="panel.js"]')?.src || '').split('?v=')[1] || '1');
      let all = null;
      try { const cached = sessionStorage.getItem(ckKey); if (cached) all = JSON.parse(cached); } catch {}
      if (!all) {
        all = await (await fetch(BASE + '/data/checks.json')).json();
        try { sessionStorage.setItem(ckKey, JSON.stringify(all)); } catch {}
      }
      checks = all[path] || all[decodeURI(path)] || [];
    } catch { checks = []; }
    renderChecks();
    if (path.endsWith('/ask/')) {
      setOpen(true);
      setTab('ask');
    } else {
      setOpen(ls.get(OPEN_KEY) === '1' || (ls.get(OPEN_KEY) === '' && checks.some((c) => c.sev === 'warn') && innerWidth > 1300));
    }
  });
})();
