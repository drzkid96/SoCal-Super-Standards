// Right-edge panel on every page: Checks (supersedence and guidance in effect) and Ask Claude (page-aware prompts).
// Ask Claude uses the visitor's own Anthropic API key, stored only in this browser (same key as the site agent).
(() => {
  const BASE = '/SoCal-Super-Standards';
  const KEY = 'sss-anthropic-key', MODEL_KEY = 'sss-model', OPEN_KEY = 'sss-panel-open', TAB_KEY = 'sss-panel-tab';
  const ls = { get: (k, d = '') => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  function md(text) {
    let h = esc(text);
    h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => `<a href="${safeUrl(u.replace(/&amp;/g, '&'))}">${t}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/^#{1,4} (.+)$/gm, '<strong>$1</strong>');
    return h.split(/\n{2,}/).map((p) => /^\s*([-*]|\d+\.) /m.test(p)
      ? '<ul>' + p.split('\n').filter((l) => l.trim()).map((l) => '<li>' + l.replace(/^\s*([-*]|\d+\.) /, '') + '</li>').join('') + '</ul>'
      : '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
  }

  const path = location.pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
  const kind = path.includes('/details/') ? 'detail' : path.includes('/signs/') && !path.endsWith('/signs/') ? 'sign'
    : path.includes('/bulletins/') ? 'bulletin' : /\/(mutcd|ca-mutcd)\//.test(path) ? 'manual' : 'page';

  const PRESETS = {
    detail: [
      ['Explain this sheet', 'Explain this drawing in plain language for a designer: what it shows, when to use it, and the key dimensions and notes.'],
      ['Requirements and dimensions', 'List every requirement and dimension on this drawing as a checklist I can use in plan review.'],
      ['What could supersede it?', 'Using the checks provided and the page text, explain what newer standards, bulletins or other sheets may control over this drawing, and what to verify.'],
      ['Draft plan notes', 'Draft signing and striping plan notes that cite this drawing correctly. Keep them short and in standard plan-note style.'],
    ],
    sign: [
      ['Where and how to use it', 'Explain where this sign is used, its placement and size rules, and any plaques that go with it.'],
      ['Is it current?', 'Using the checks provided, say whether this sign is current in California and what replaces it if not.'],
      ['Plan sign legend entry', 'Write a sign legend entry for a signing and striping plan for this sign (code, description, size).'],
    ],
    manual: [
      ['Summarize this chapter', 'Summarize the standards (shall), guidance (should) and options (may) on this page as short bullets.'],
      ['Federal vs California', 'Point out where this page differs between the federal MUTCD and the CA MUTCD 2026, using only what the page and checks show.'],
      ['Plan review checklist', 'Turn this page into a plan review checklist.'],
    ],
    bulletin: [
      ['Key values', 'List the key design values in this bulletin and when they apply.'],
      ['What it changes', 'Explain what this bulletin changes compared with the manual or drawing it updates.'],
    ],
    page: [
      ['Summarize', 'Summarize this page for a designer in short bullets.'],
      ['Plan review checklist', 'Turn the requirements on this page into a plan review checklist.'],
      ['Compare agencies', 'Where this page touches Caltrans, LADOT and other agency rules, compare them in a short table.'],
    ],
  };

  let checks = [];
  const ui = document.createElement('aside');
  ui.className = 'sp';
  ui.setAttribute('aria-label', 'Checks and Ask Claude');
  ui.innerHTML = `
    <button class="sp-tab" type="button" aria-expanded="false" title="Checks and Ask Claude"><span class="sp-tab-t">Checks</span><span class="sp-n"></span></button>
    <div class="sp-body" hidden>
      <div class="sp-head">
        <div class="sp-tabs" role="tablist">
          <button role="tab" data-t="checks" type="button">Checks</button>
          <button role="tab" data-t="ask" type="button">Ask Claude</button>
        </div>
        <button class="sp-x" type="button" aria-label="Close panel">&times;</button>
      </div>
      <section class="sp-pane" data-p="checks"></section>
      <section class="sp-pane" data-p="ask" hidden>
        <div class="sp-key" hidden>
          <p>Ask Claude about this page with your own Anthropic API key. It is stored only in this browser.</p>
          <input type="password" placeholder="sk-ant-..." autocomplete="off"><button type="button" class="sp-save">Save key</button>
        </div>
        <div class="sp-pre"></div>
        <textarea rows="3" placeholder="Ask anything about this page..."></textarea>
        <div class="sp-row"><button type="button" class="sp-send">Ask</button><button type="button" class="sp-clear">Clear</button></div>
        <div class="sp-out" aria-live="polite"></div>
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
    if (t === 'ask') $('.sp-key').hidden = !!ls.get(KEY);
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
    const key = ls.get(KEY);
    if (!key) { $('.sp-key').hidden = false; return; }
    const out = $('.sp-out');
    const item = document.createElement('div');
    item.className = 'sp-a';
    item.innerHTML = `<div class="sp-q">${esc(q)}</div><div class="sp-r">Thinking...</div>`;
    out.prepend(item);
    const sys = 'You help traffic engineers and planners in Southern California use the SoCal Super Standards site. Answer from the page text and checks supplied. Say so plainly when the page does not cover something. Keep CA MUTCD, federal MUTCD, Caltrans and LADOT direction separate and name which one you mean. Be concise. Link only to URLs that appear in the supplied checks or to the current page.';
    const ctx = `Page: ${document.title}\nURL: ${location.href}\n\nChecks for this page (supersedence and guidance in effect):\n${checks.map((c) => `- [${c.sev}] ${c.title}: ${c.text} Links: ${c.links.map((l) => `${l[0]} ${location.origin}${l[1]}`).join('; ')}`).join('\n') || '- none'}\n\nPage text:\n${pageText()}`;
    try {
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' },
        body: JSON.stringify({ model: ls.get(MODEL_KEY, 'claude-sonnet-5-5'), max_tokens: 1500, system: sys, messages: [{ role: 'user', content: ctx + '\n\nQuestion: ' + q }] }),
      });
      if (!r.ok) throw new Error('Claude API error ' + r.status + ': ' + (await r.text()).slice(0, 200));
      const j = await r.json();
      item.querySelector('.sp-r').innerHTML = md(j.content.filter((c) => c.type === 'text').map((c) => c.text).join('\n'));
    } catch (e) {
      item.querySelector('.sp-r').textContent = e.message;
    }
  }

  window.__ready(async () => {
    document.body.append(ui);
    $('.sp-pre').innerHTML = (PRESETS[kind] || PRESETS.page).map(([t], i) => `<button type="button" data-i="${i}">${esc(t)}</button>`).join('');
    $('.sp-pre').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) ask((PRESETS[kind] || PRESETS.page)[b.dataset.i][1]); });
    $('[data-p="checks"]').addEventListener('click', async (e) => {
      const b = e.target.closest('.sp-cite'); if (!b) return;
      try { await navigator.clipboard.writeText(citation()); b.textContent = 'Copied'; } catch { b.textContent = citation(); }
      setTimeout(() => (b.textContent = 'Copy citation'), 1800);
    });
    $('.sp-tab').addEventListener('click', () => setOpen($('.sp-body').hidden));
    $('.sp-x').addEventListener('click', () => setOpen(false));
    ui.querySelector('.sp-tabs').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setTab(b.dataset.t); });
    $('.sp-send').addEventListener('click', () => { const t = $('textarea').value.trim(); if (t) ask(t); });
    $('textarea').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) $('.sp-send').click(); });
    $('.sp-clear').addEventListener('click', () => { $('.sp-out').innerHTML = ''; $('textarea').value = ''; });
    $('.sp-save').addEventListener('click', () => { const v = $('.sp-key input').value.trim(); if (v) { ls.set(KEY, v); $('.sp-key').hidden = true; } });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ui.classList.contains('open')) setOpen(false); });
    setTab(ls.get(TAB_KEY, 'checks'));
    try {
      const all = await (await fetch(BASE + '/data/checks.json')).json();
      checks = all[path] || all[decodeURI(path)] || [];
    } catch { checks = []; }
    renderChecks();
    setOpen(ls.get(OPEN_KEY) === '1' || (ls.get(OPEN_KEY) === '' && checks.some((c) => c.sev === 'warn') && innerWidth > 1300));
  });
})();
