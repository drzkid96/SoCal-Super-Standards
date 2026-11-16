// SoCal Super Standards AI: Ask (text + screenshot), Explain, Add reference.
// Uses the visitor's own Anthropic API key, stored only in this browser (localStorage).
(() => {
  const BASE = '/SoCal-Super-Standards';
  const KEY = 'sss-anthropic-key';
  const MODEL_KEY = 'sss-model';
  const API = 'https://api.anthropic.com/v1/messages';
  let pagefind = null;
  let signs = null;

  const getKey = () => { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } };
  const setKey = (k) => { try { localStorage.setItem(KEY, k); } catch {} };
  const getModel = () => { try { return localStorage.getItem(MODEL_KEY) || 'claude-sonnet-5-5'; } catch { return 'claude-sonnet-5-5'; } };

  async function claude(messages, system, maxTokens = 1800) {
    const key = getKey();
    if (!key) throw new Error('Add your Anthropic API key first (it stays in this browser).');
    const r = await fetch(API, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({ model: getModel(), max_tokens: maxTokens, system, messages }),
    });
    if (!r.ok) throw new Error('Claude API error ' + r.status + ': ' + (await r.text()).slice(0, 300));
    const j = await r.json();
    return j.content.filter((c) => c.type === 'text').map((c) => c.text).join('\n');
  }

  async function loadPagefind() {
    if (!pagefind) {
      pagefind = await import(/* @vite-ignore */ BASE + '/pagefind/pagefind.js');
      await pagefind.init();
    }
    return pagefind;
  }
  async function loadSigns() {
    if (!signs) signs = await (await fetch(BASE + '/data/signs-index.json')).json();
    return signs;
  }

  async function search(q, n = 6) {
    const pf = await loadPagefind();
    const res = await pf.search(q);
    const out = [];
    for (const r of res.results.slice(0, n)) {
      const d = await r.data();
      // prefer sub-results (section anchors) when present
      const subs = (d.sub_results || []).slice(0, 2);
      if (subs.length) subs.forEach((s) => out.push({ title: s.title || d.meta.title, url: s.url, excerpt: strip(s.excerpt) }));
      else out.push({ title: d.meta.title, url: d.url, excerpt: strip(d.excerpt) });
    }
    return out;
  }
  const strip = (h) => (h || '').replace(/<[^>]+>/g, '');

  function md(text) {
    // minimal markdown: links, bold, bullets, paragraphs
    let h = text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
    h = h.replace(/\[([^\]]+)\]\((\/?[^)\s]+)\)/g, (m, t, u) => `<a href="${u}">${t}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.split(/\n{2,}/).map((p) => /^\s*[-*] /m.test(p)
      ? '<ul>' + p.split('\n').filter((l) => l.trim()).map((l) => '<li>' + l.replace(/^\s*[-*] /, '') + '</li>').join('') + '</ul>'
      : '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
    return h;
  }

  function fileToB64(file) {
    return new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res({ media: file.type || 'image/png', data: String(fr.result).split(',')[1] });
      fr.onerror = rej;
      fr.readAsDataURL(file);
    });
  }

  // ------------------------------------------------------------------ ASK
  async function ask(text, images, log) {
    log('Reading your input...');
    const content = [];
    for (const im of images) content.push({ type: 'image', source: { type: 'base64', media_type: im.media, data: im.data } });
    content.push({ type: 'text', text: (text || '(no text, see image)') + `

Identify what this is about for a California traffic engineer. Return ONLY JSON:
{"summary":"one sentence","sign_codes":["MUTCD codes you can see or that are named, e.g. R3-17"],"topics":["short topics"],"drawings":["LADOT standard drawing numbers seen or named, e.g. S-481.0"],"queries":["4-8 short search queries for a standards site (section numbers, sign codes, terms)"]}` });
    const plan = await claude([{ role: 'user', content }],
      'You read screenshots of plans, photos, and messy notes and turn them into precise MUTCD / CA MUTCD / LADOT search terms. Output JSON only.', 800);
    let p;
    try { p = JSON.parse(plan.replace(/^[^{]*/, '').replace(/[^}]*$/, '')); } catch { p = { summary: '', sign_codes: [], topics: [], queries: [text] }; }
    log('Searching ' + (p.queries || []).length + ' queries across all sources...');
    const hits = new Map();
    for (const q of (p.queries || []).slice(0, 8)) {
      for (const h of await search(q, 4)) if (!hits.has(h.url)) hits.set(h.url, h);
    }
    const sx = await loadSigns();
    const found = (p.sign_codes || []).map((c) => sx[c.toUpperCase()] || sx[c]).filter(Boolean);
    // LADOT standard drawings and sign references by number
    try {
      const li = await (await fetch(BASE + '/data/ladot-index.json')).json();
      const want = new Set([...(p.drawings || []), ...((text || '').match(/S-\d{2,3}(?:\.\d+)*/g) || [])].map((d) => d.includes('.') ? d : d + '.0'));
      const codes = new Set((p.sign_codes || []).map((c) => c.toUpperCase()));
      for (const r of li) {
        if (hits.size > 30) break;
        if (r.drawings.some((d) => want.has(d)) || r.signs.some((c) => codes.has(c))) {
          if (!hits.has(r.url)) hits.set(r.url, { url: r.url, title: `${r.doc} page ${r.page} ${r.title}`, excerpt: `LADOT ${r.doc}, page ${r.page}. Drawings: ${r.drawings.join(', ')}. Signs: ${r.signs.join(', ')}. Topics: ${r.topics.join(', ')}` });
        }
      }
    } catch (e) { /* index optional */ }
    const ctx = [...hits.values()].slice(0, 18).map((h, i) => `[${i + 1}] ${h.title}\nURL: ${h.url}\n${h.excerpt}`).join('\n\n');
    log('Writing the answer...');
    const answer = await claude([{ role: 'user', content: [
      ...images.map((im) => ({ type: 'image', source: { type: 'base64', media_type: im.media, data: im.data } })),
      { type: 'text', text: `User input: ${text || '(see image)'}\n\nSite search results (use these and cite them by linking their URL):\n${ctx}\n\nSigns identified: ${found.map((s) => s.code + ' ' + s.descriptor).join('; ') || 'none'}` },
    ] }],
    `You are the SoCal Super Standards assistant for traffic engineers in Southern California.
Answer using ONLY the provided search results, and link every claim to its URL with markdown links like [CA MUTCD 4I.06](url).
Order of authority: CA MUTCD 2026 is the legal standard in California; federal MUTCD 11th Ed. Rev. 1 is the national baseline; LADOT documents add City of Los Angeles requirements; FHWA/NACTO/others are guidance.
Say whether each item is a Standard (shall), Guidance (should), or Option (may) when the excerpt shows it. If sources overlap or conflict, say which governs and why.
Be concise: a short answer, then "Where to look" bullets. If the results don't answer it, say so.`, 1800);
    return { p, found, answer, hits: [...hits.values()] };
  }

  // ------------------------------------------------------------------ EXPLAIN (manual sections)
  function sectionText(root, anchorId) {
    const a = root.getElementById ? root.getElementById(anchorId) : root.querySelector('#' + anchorId);
    if (!a) return '';
    let el = a.nextElementSibling, out = [];
    let seenHeading = false;
    while (el) {
      if (el.matches && el.matches('span.anchor')) break;
      if (/H2/.test(el.tagName)) { if (seenHeading) break; seenHeading = true; }
      out.push(el.innerText || el.textContent || '');
      el = el.nextElementSibling;
    }
    return out.join('\n').slice(0, 9000);
  }

  async function explain(anchorId, title, box) {
    const here = sectionText(document, anchorId);
    const isCA = location.pathname.includes('/ca-mutcd/');
    const ch = location.pathname.split('/').filter(Boolean).pop();
    let other = '';
    try {
      const url = BASE + (isCA ? '/mutcd/' : '/ca-mutcd/') + ch + '/';
      const html = await (await fetch(url)).text();
      const doc = new DOMParser().parseFromString(html, 'text/html');
      other = sectionText(doc, anchorId);
    } catch {}
    box.innerHTML = '<p class="ai-wait">Asking Claude...</p>';
    try {
      const out = await claude([{ role: 'user', content: `Section: ${title}\n\n${isCA ? 'CA MUTCD 2026' : 'Federal MUTCD 11th Ed. Rev. 1'} text:\n${here}\n\n${isCA ? 'Federal MUTCD 11th Ed. Rev. 1' : 'CA MUTCD 2026'} text of the same section:\n${other || '(not found)'}` }],
        `Explain this MUTCD section to a practicing traffic engineer in plain language.
1) What it requires: list Standards (shall), then Guidance (should), then Options (may), each one line.
2) California vs federal: list every substantive difference (added, removed, stricter, looser). If identical, say so.
3) Practical notes for signing/striping plans and plan review in LA. Flag anything that overlaps or conflicts with other sources and say which governs.
Keep it tight. Do not invent requirements not in the text.`, 1500);
      box.innerHTML = md(out);
    } catch (e) { box.innerHTML = '<p class="ai-err">' + e.message + '</p>'; }
  }

  function addExplainButtons() {
    if (!/\/(ca-mutcd|mutcd)\/[a-z0-9]+\/$/.test(location.pathname)) return;
    document.querySelectorAll('span.anchor').forEach((a) => {
      const h = a.nextElementSibling && a.nextElementSibling.querySelector ? (a.nextElementSibling.matches('h2') ? a.nextElementSibling : a.nextElementSibling.querySelector('h2')) : null;
      const target = h || a.nextElementSibling;
      if (!target) return;
      const btn = document.createElement('button');
      btn.className = 'ai-explain'; btn.type = 'button'; btn.textContent = 'Explain with Claude';
      const box = document.createElement('div'); box.className = 'ai-box'; box.hidden = true;
      btn.onclick = () => { box.hidden = false; if (!box.dataset.done) { box.dataset.done = 1; explain(a.id, (h && h.textContent) || a.id, box); } };
      target.insertAdjacentElement('afterend', box);
      target.insertAdjacentElement('afterend', btn);
    });
  }

  // ------------------------------------------------------------------ ASK PAGE UI
  function mountAsk() {
    const root = document.getElementById('sss-ask');
    if (!root) return;
    const $ = (s) => root.querySelector(s);
    $('#ai-key').value = getKey() ? '••••••••••••' : '';
    $('#ai-model').value = getModel();
    $('#ai-save').onclick = () => {
      const v = $('#ai-key').value.trim();
      if (v && !v.startsWith('••')) setKey(v);
      try { localStorage.setItem(MODEL_KEY, $('#ai-model').value); } catch {}
      $('#ai-keymsg').textContent = getKey() ? 'Saved in this browser only.' : 'No key saved.';
    };
    $('#ai-forget').onclick = () => { try { localStorage.removeItem(KEY); } catch {} $('#ai-key').value = ''; $('#ai-keymsg').textContent = 'Key removed.'; };
    let images = [];
    const thumbs = $('#ai-thumbs');
    async function addFiles(files) {
      for (const f of files) if (f.type.startsWith('image/')) {
        images.push(await fileToB64(f));
        const im = document.createElement('img'); im.src = URL.createObjectURL(f); thumbs.appendChild(im);
      }
    }
    $('#ai-file').onchange = (e) => addFiles(e.target.files);
    root.addEventListener('paste', (e) => addFiles([...e.clipboardData.files]));
    const drop = $('#ai-drop');
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); addFiles([...e.dataTransfer.files]); };
    $('#ai-clear').onclick = () => { images = []; thumbs.innerHTML = ''; $('#ai-text').value = ''; $('#ai-out').innerHTML = ''; };
    $('#ai-go').onclick = async () => {
      const out = $('#ai-out');
      const log = (m) => { out.innerHTML = '<p class="ai-wait">' + m + '</p>'; };
      try {
        const r = await ask($('#ai-text').value.trim(), images, log);
        const signsHtml = r.found.length ? '<div class="ai-signs">' + r.found.map((s) =>
          `<a class="scard" href="${s.url}"><span class="simg"><img src="${s.svg}" alt=""></span><span class="scode">${s.code}</span><span class="sname">${s.descriptor}</span></a>`).join('') + '</div>' : '';
        out.innerHTML = (r.p.summary ? '<p class="ai-sum">' + r.p.summary + '</p>' : '') + signsHtml + '<div class="ai-answer">' + md(r.answer) + '</div>'
          + '<details class="ai-src"><summary>Search results used (' + r.hits.length + ')</summary><ul>' + r.hits.map((h) => `<li><a href="${h.url}">${h.title}</a></li>`).join('') + '</ul></details>';
      } catch (e) { out.innerHTML = '<p class="ai-err">' + e.message + '</p>'; }
    };
    // Add a reference
    $('#ref-go').onclick = async () => {
      const box = $('#ref-out');
      const src = $('#ref-src').value.trim();
      if (!src) return;
      box.innerHTML = '<p class="ai-wait">Drafting...</p>';
      try {
        const out = await claude([{ role: 'user', content: `New reference to add to SoCal Super Standards: ${src}\nNotes: ${$('#ref-notes').value}` }],
          `Draft a GitHub issue body to add a new reference to a traffic-standards website. Include: Title, Publisher, Edition/date, Official URL (if given), Status (current/superseded, if known), Copyright/licensing note (public domain, government, or copyrighted - if copyrighted, summaries and page references only), Topics it belongs to (from: Signs, Markings, Crosswalks, Bikeways, Transit/Bus lanes, Intersections, Signals, School zones, Curb/Parking, Speed/Calming, Accessibility, TTC, Rail/LRT, LA28), and what to extract (sections, figures, tables). Markdown. Do not invent facts; mark unknowns.`, 900);
        const title = 'New reference: ' + src.slice(0, 80);
        const url = 'https://github.com/drzkid96/SoCal-Super-Standards/issues/new?labels=new-reference&title=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(out + '\n\n_Drafted with Claude on the site._');
        box.innerHTML = md(out) + `<p><a class="ai-btn" href="${url}" target="_blank" rel="noopener">Open GitHub issue to add it</a></p><p class="note">Attach the PDF to the issue. It will be processed into the site and reviewed before publishing.</p>`;
      } catch (e) { box.innerHTML = '<p class="ai-err">' + e.message + '</p>'; }
    };
  }

  document.addEventListener('DOMContentLoaded', () => { mountAsk(); addExplainButtons(); });
})();
