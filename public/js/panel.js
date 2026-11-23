// Right-edge panel on every page: Checks (supersedence & currency) + unified zero-key Ask drawer.
// Uses the exact same window.SSSAsk engine as /ask/ — zero API key required, and hides duplicate Ask tab on /ask/.
(() => {
  const BASE = '/SoCal-Super-Standards';
  const OPEN_KEY = 'sss-panel-open', TAB_KEY = 'sss-panel-tab';
  const ls = { get: (k, d = '') => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  const path = location.pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
  const isAskPage = path.endsWith('/ask/');
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
  ui.setAttribute('aria-label', isAskPage ? 'Checks' : 'Checks and Ask');
  ui.innerHTML = `
    <button class="sp-tab" type="button" aria-expanded="false" title="${isAskPage ? 'Checks' : 'Checks and Ask'}"><span class="sp-tab-t">Checks</span><span class="sp-n"></span></button>
    <div class="sp-body" hidden>
      <div class="sp-head">
        <div class="sp-tabs" role="tablist">
          <button role="tab" data-t="checks" type="button">Checks</button>
          ${isAskPage ? '' : '<button role="tab" data-t="ask" type="button">Ask</button>'}
        </div>
        <button class="sp-x" type="button" aria-label="Close panel">&times;</button>
      </div>
      <section class="sp-pane" data-p="checks"></section>
      ${isAskPage ? '' : `
      <section class="sp-pane" data-p="ask" hidden>
        <div class="sp-pre"></div>
        <textarea rows="2" placeholder="Ask about this page or any standard..."></textarea>
        <div class="sp-row">
          <button type="button" class="sp-send">Ask</button>
          <button type="button" class="sp-clear">Clear</button>
          <a href="${BASE}/ask/" style="margin-left:auto;font-size:0.76rem;align-self:center">Full page &rarr;</a>
        </div>
        <div class="sp-out" aria-live="polite"></div>
      </section>`}
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
    const target = isAskPage ? 'checks' : t;
    ui.querySelectorAll('.sp-tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.t === target)));
    ui.querySelectorAll('.sp-pane').forEach((p) => (p.hidden = p.dataset.p !== target));
    if (!isAskPage) ls.set(TAB_KEY, target);
  }

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
        compact: true,
        pageText: pageText(),
        pageChecks: checks,
        onLog: (m) => { item.querySelector('.sp-r').textContent = m; },
      });
      item.querySelector('.sp-r').innerHTML = window.SSSAsk.renderResultHTML(r, true);
    } catch (e) {
      item.querySelector('.sp-r').textContent = e.message;
    }
  }

  window.__ready(async () => {
    document.body.append(ui);
    if (!isAskPage) {
      $('.sp-pre').innerHTML = (PRESETS[kind] || PRESETS.page).map(([t], i) => `<button type="button" data-i="${i}">${esc(t)}</button>`).join('');
      $('.sp-pre').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) ask((PRESETS[kind] || PRESETS.page)[b.dataset.i][1]); });
      $('.sp-send').addEventListener('click', () => { const t = $('textarea').value.trim(); if (t) ask(t); });
      $('textarea').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const t = $('textarea').value.trim(); if (t) ask(t); } });
      $('.sp-clear').addEventListener('click', () => { $('.sp-out').innerHTML = ''; $('textarea').value = ''; });
    }
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
    setOpen(!isAskPage && (ls.get(OPEN_KEY) === '1' || (ls.get(OPEN_KEY) === '' && checks.some((c) => c.sev === 'warn') && innerWidth > 1300)));
  });
})();
