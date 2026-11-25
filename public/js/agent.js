window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));
// Unified SoCal Super Standards Assistant (window.SSSAsk)
// Lives in the right-side drawer (panel.js) + homepage 1-click AI loader + MUTCD section summarizer.
// Zero API keys. Instant built-in search engine + optional 1-click free in-browser AI model.
(() => {
  if(window.SSSAgency?.active) return;
  const BASE = '/SoCal-Super-Standards';
  const AI_PREF_KEY = 'sss-web-ai-enabled';
  const OR_KEY = 'sss-or-key';
  let pagefind = null;
  let signs = null;
  let details = null;
  let checks = null;

  let localPipe = null;
  let localMode = 'instant'; // 'instant' | 'openrouter' | 'chrome-ai' | 'web-ai'
  let localLoading = false;
  let lastStatus = 'Instant search ready';
  const listeners = new Set();

  function emitStatus(msg, pct = null) {
    lastStatus = msg;
    listeners.forEach((fn) => { try { fn({ mode: localMode, loading: localLoading, msg, pct }); } catch {} });
  }

  // 1-Click OpenRouter OAuth PKCE (no client secret, works natively on GitHub Pages)
  async function startOAuth() {
    const arr = new Uint8Array(32);
    crypto.getRandomValues(arr);
    const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const verifier = b64u(arr);
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
    const challenge = b64u(digest);
    try { sessionStorage.setItem('sss_or_ver', verifier); } catch {}
    const cb = location.origin + location.pathname;
    location.href = `https://openrouter.ai/auth?callback_url=${encodeURIComponent(cb)}&code_challenge=${encodeURIComponent(challenge)}&code_challenge_method=S256`;
  }

  async function completeOAuthIfPresent() {
    try {
      const sp = new URLSearchParams(location.search);
      const code = sp.get('code');
      const verifier = sessionStorage.getItem('sss_or_ver');
      if (!code || !verifier) return false;
      emitStatus('Finishing 1-click AI sign-in...', 50);
      const r = await fetch('https://openrouter.ai/api/v1/auth/keys', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ code, code_verifier: verifier, code_challenge_method: 'S256' }),
      });
      if (r.ok) {
        const j = await r.json();
        if (j.key) {
          localStorage.setItem(OR_KEY, j.key);
          sessionStorage.removeItem('sss_or_ver');
          localMode = 'openrouter';
          sp.delete('code');
          const clean = location.pathname + (sp.toString() ? '?' + sp.toString() : '') + location.hash;
          history.replaceState(null, '', clean);
          emitStatus('Connected via OpenRouter (free models)', 100);
          return true;
        }
      }
    } catch {}
    return false;
  }

  function disconnectOAuth() {
    try { localStorage.removeItem(OR_KEY); localStorage.removeItem(AI_PREF_KEY); } catch {}
    localMode = 'instant';
    emitStatus('Instant search ready', null);
  }

  const strip = (h) => (h || '').replace(/<[^>]+>/g, '');
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  function md(text) {
    let h = esc(text);
    h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => `<a href="${safeUrl(u.replace(/&amp;/g, '&'))}">${t}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    return h.replace(/^(### [^\n]+)\n/gm, '$1\n\n').split(/\n{2,}/).map((p) => {
      if (/^###\s+/.test(p)) return '<h4>' + p.replace(/^###\s+/, '') + '</h4>';
      if (/^\s*[-*] /m.test(p)) {
        return '<ul>' + p.split('\n').filter((l) => l.trim()).map((l) => '<li>' + l.replace(/^\s*[-*] /, '') + '</li>').join('') + '</ul>';
      }
      return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    }).join('');
  }

  async function loadPagefind() {
    if (!pagefind) {
      pagefind = await import(/* @vite-ignore */ BASE + '/pagefind/pagefind.js');
      await pagefind.init();
    }
    return pagefind;
  }
  async function loadSigns() {
    if (!signs) { try { signs = await (await fetch(BASE + '/data/signs-index.json')).json(); } catch { signs = {}; } }
    return signs;
  }
  async function loadDetails() {
    if (!details) { try { details = await (await fetch(BASE + '/data/details.json')).json(); } catch { details = []; } }
    return details;
  }
  async function loadChecks() {
    if (!checks) { try { checks = await (await fetch(BASE + '/data/checks.json')).json(); } catch { checks = {}; } }
    return checks;
  }

  async function detectChromeAI() {
    try {
      if (typeof LanguageModel !== 'undefined' && LanguageModel.availability) {
        const av = await LanguageModel.availability();
        if (av === 'available' || av === 'readily') {
          localMode = 'chrome-ai';
          emitStatus('Built-in browser AI ready', 100);
          return true;
        }
      }
    } catch {}
    return false;
  }

  async function enableBrowserAI() {
    if (localMode === 'chrome-ai') { emitStatus('Built-in browser AI ready', 100); return 'chrome-ai'; }
    if (localPipe) { localMode = 'web-ai'; emitStatus('In-browser AI ready (free, local)', 100); return 'web-ai'; }
    if (localLoading) return localMode;
    localLoading = true;
    try {
      if (await detectChromeAI()) {
        try { localStorage.setItem(AI_PREF_KEY, '1'); } catch {}
        return 'chrome-ai';
      }
      emitStatus('Loading free in-browser AI (cached after first load)...', 5);
      const { pipeline } = await import(/* @vite-ignore */ 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.4.0');
      localPipe = await pipeline('text-generation', 'onnx-community/Qwen2.5-0.5B-Instruct', {
        dtype: 'q4',
        progress_callback: (p) => {
          if (p && p.status === 'progress' && typeof p.progress === 'number') {
            const pct = Math.round(p.progress);
            emitStatus(`Loading in-browser AI: ${pct}%`, pct);
          }
        },
      });
      localMode = 'web-ai';
      try { localStorage.setItem(AI_PREF_KEY, '1'); } catch {}
      emitStatus('In-browser AI ready (free, local)', 100);
      return 'web-ai';
    } catch (e) {
      localMode = 'instant';
      emitStatus('Using Instant Engine (browser AI unavailable here)', null);
      throw e;
    } finally {
      localLoading = false;
    }
  }

  async function runLocalLLM(system, prompt) {
    if (localMode === 'openrouter') {
      const k = (() => { try { return localStorage.getItem(OR_KEY) || ''; } catch { return ''; } })();
      if (k) {
        const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: { 'content-type': 'application/json', 'authorization': 'Bearer ' + k, 'HTTP-Referer': location.origin, 'X-Title': 'SoCal Super Standards' },
          body: JSON.stringify({ model: 'meta-llama/llama-3.3-70b-instruct:free', max_tokens: 450, messages: [{ role: 'system', content: system }, { role: 'user', content: prompt.slice(0, 5000) }] }),
        });
        if (r.ok) { const j = await r.json(); return j.choices?.[0]?.message?.content || ''; }
      }
    }
    if (localMode === 'chrome-ai' && typeof LanguageModel !== 'undefined') {
      const sess = await LanguageModel.create({ systemPrompt: system });
      try { return await sess.prompt(prompt); } finally { sess.destroy && sess.destroy(); }
    }
    if (localMode === 'web-ai' && localPipe) {
      const out = await localPipe(
        [{ role: 'system', content: system }, { role: 'user', content: prompt.slice(0, 3200) }],
        { max_new_tokens: 300, temperature: 0.2, do_sample: false }
      );
      const gen = out?.[0]?.generated_text;
      if (Array.isArray(gen)) return gen[gen.length - 1]?.content || '';
      return String(gen || '');
    }
    return '';
  }

  async function pfSearch(q, n = 8) {
    const pf = await loadPagefind();
    const res = await pf.search(q);
    const out = [];
    for (const r of res.results.slice(0, n)) {
      const d = await r.data();
      const subs = (d.sub_results || []).slice(0, 2);
      if (subs.length) subs.forEach((s) => out.push({ title: s.title || d.meta.title, url: s.url, excerpt: strip(s.excerpt) }));
      else out.push({ title: d.meta.title, url: d.url, excerpt: strip(d.excerpt) });
    }
    return out;
  }

  function classifyAuthority(url) {
    if (url.includes('/ca-mutcd/') || url.includes('/caltrans/la28-supplement/')) return { rank: 1, bucket: 'CA MUTCD 2026 (Legal Standard)' };
    if (url.includes('/caltrans/standard-plans-2026/') || url.includes('/details/caltrans/') || url.includes('/bulletins/caltrans-') || url.includes('/markings/')) return { rank: 2, bucket: 'Caltrans 2026 & State Bulletins' };
    if (url.includes('/ladot/') || url.includes('/details/ladot/') || url.includes('/bulletins/ladot-')) return { rank: 3, bucket: 'City of Los Angeles (LADOT)' };
    if (/\/(long-beach|palmdale|torrance|gardena|glendora|burbank|pasadena|santa-monica|west-hollywood|culver-city|cities)\//.test(url)) return { rank: 4, bucket: 'LA County Municipal Standards' };
    if (url.includes('/topics/') || url.includes('/bulletins/')) return { rank: 5, bucket: 'Design Summaries & Comparisons' };
    return { rank: 6, bucket: 'Federal Baseline & National Guides' };
  }

  function tokenize(q) {
    return (q || '').toLowerCase().replace(/[^a-z0-9.-]+/g, ' ').split(/\s+/)
      .filter((t) => t.length >= 2 && !/^(the|and|for|with|what|how|does|are|can|use|per|in|of|to|on|at|is|a|an|this|page|about)$/.test(t));
  }

  function scoreDetail(d, qLower, tokens) {
    const num = (d.num || '').toLowerCase();
    const title = (d.title || '').toLowerCase();
    const sum = (d.sum || '').toLowerCase();
    const src = (d.src || '').toLowerCase();
    const sg = (d.sg || '').toLowerCase();
    let s = 0;
    if (num && qLower.includes(num)) s += 60;
    if (sg && qLower.includes(sg)) s += 25;
    for (const t of tokens) {
      if (num.includes(t)) s += 22;
      if (title.includes(t)) s += 14;
      if (sg.includes(t) || src.includes(t)) s += 10;
      if (sum.includes(t)) s += 6;
    }
    if (d.type === 'Standard drawing') s += 4;
    if (d.img) s += 3;
    return s;
  }

  function extractPageAnswer(q, pageText, pageChecks) {
    const ql = (q || '').toLowerCase();
    const sents = (pageText || '').replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/).filter((s) => s.length > 18 && s.length < 340);
    const out = [];
    if (/supersed|current|check|govern|flag/.test(ql)) {
      if (pageChecks && pageChecks.length) {
        out.push('### Status & Supersedence Checks');
        pageChecks.forEach((c) => out.push(`- **${c.sev === 'warn' ? 'Check' : 'In effect'} — ${c.title}:** ${c.text}`));
      } else {
        out.push('No supersedence flags on this page. **CA MUTCD 2026** is the legal baseline, **Caltrans 2026 / HDM Ch. 1000** govern state design, and local city standard plans govern local ROW.');
      }
      return out.join('\n');
    }
    if (/checklist|requirement|shall|dimension|plan review/.test(ql)) {
      const reqs = sents.filter((s) => /\b(shall|must|minimum|maximum|min\.|max\.|\d+\s*(?:ft|in\.|mph|%))\b/i.test(s)).slice(0, 6);
      out.push('### Plan Review Checklist');
      (reqs.length ? reqs : sents.slice(0, 5)).forEach((s) => out.push('- ' + s));
      return out.join('\n');
    }
    if (/summar|explain|key value/.test(ql) && tokenize(ql).length <= 4) {
      const shalls = sents.filter((s) => /\bshall\b/i.test(s)).slice(0, 3);
      const dims = sents.filter((s) => /\d+\s*(?:ft|in\.|mph|%)/i.test(s)).slice(0, 3);
      const picked = [...new Set([...shalls, ...dims, ...sents.slice(0, 3)])].slice(0, 5);
      out.push('### Quick Summary');
      picked.forEach((s) => out.push('- ' + s));
      return out.join('\n');
    }
    const toks = tokenize(ql);
    const scored = sents.map((s) => ({
      s,
      n: toks.reduce((acc, t) => acc + (s.toLowerCase().includes(t) ? 1 : 0), 0),
    })).filter((x) => x.n > 0).sort((a, b) => b.n - a.n).slice(0, 3);
    if (scored.length) {
      out.push('### On This Page');
      scored.forEach((x) => out.push('- ' + x.s));
    }
    return out.join('\n');
  }

  async function askSite(query, opts = {}) {
    const cleanText = (query || '').trim();
    if (!cleanText) throw new Error('Type a question, sign code, detail number, or city name.');
    const onLog = opts.onLog || (() => {});
    const pageContext = opts.pageText || '';
    const pageChecks = opts.pageChecks || [];

    if (opts.action === 'checklist' || /checklist|plan review/i.test(cleanText)) {
      const entries = [...document.querySelectorAll('ol.dwg-notes li[id], .prov p[id]')];
      const lines = entries.map(el => {
        const copy = el.cloneNode(true);
        copy.querySelectorAll('del,.pn').forEach(node => node.remove());
        return '- [' + el.id.replaceAll('-', ' ') + '](' + location.pathname + '#' + el.id + ') ' + copy.textContent.trim();
      });
      return {found: [], matchedDetails: [], hits: [], answer: '### Plan review checklist' + '\n\n' + (lines.join('\n') || 'This page has no indexed sheet notes. Open the source sheet to review its requirements.')};
    }
    const code = cleanText.toUpperCase().match(/\b[A-Z]+\d[\w-]*\s*\(CA\)/)?.[0].replace(/\s/g,'');
    if (code) {
      const retired = await (await fetch(BASE+'/data/retired.json')).json();
      if (retired.codes[code]) return { found: [], matchedDetails: [], hits: [], answer: code+' · '+retired.codes[code]+'. Caltrans deleted this sign on '+retired.date+'. [Official notice]('+retired.source+')' };
    }
    onLog('Searching standards...');
    const [sx, det, chk] = await Promise.all([loadSigns(), loadDetails(), loadChecks()]);

    const pageAns = pageContext ? extractPageAnswer(cleanText, pageContext, pageChecks) : '';

    const rawCodes = cleanText.match(/\b(?:R|W|G|S|D|E|M|C|OM|SR|SW|SG)\d+[A-Z0-9-]*(?:\(CA\))?\b/gi) || [];
    const foundSignsMap = new Map();
    for (const c of rawCodes) {
      const up = c.toUpperCase();
      const hit = sx[up] || sx[up.replace(/\(CA\)$/, '')] || sx[up + '(CA)'];
      if (hit && !foundSignsMap.has(hit.code)) foundSignsMap.set(hit.code, hit);
    }
    const tokens = tokenize(cleanText);
    if (foundSignsMap.size < 4 && tokens.length) {
      for (const s of Object.values(sx)) {
        if (foundSignsMap.size >= 4) break;
        const hay = ((s.code || '') + ' ' + (s.descriptor || '') + ' ' + (s.name || '')).toLowerCase();
        if (tokens.filter((t) => hay.includes(t)).length >= Math.min(2, tokens.length)) foundSignsMap.set(s.code, s);
      }
    }
    const found = [...foundSignsMap.values()].slice(0, 4);

    const qLower = cleanText.toLowerCase();
    const matchedDetails = det
      .map((d) => ({ d, s: scoreDetail(d, qLower, tokens) }))
      .filter((x) => x.s >= 16)
      .sort((a, b) => b.s - a.s)
      .slice(0, 4)
      .map((x) => x.d);

    const isPageOnly = pageContext && /^(explain this|summarize|plan review checklist|what could supersede|is it current|key values)/i.test(cleanText);
    const hits = new Map();
    if (!isPageOnly) {
      const queries = [cleanText];
      if (tokens.length > 3) queries.push(tokens.slice(0, 4).join(' '));
      for (const q of queries) {
        for (const h of await pfSearch(q, 6)) if (!hits.has(h.url)) hits.set(h.url, h);
      }
    }
    const hitList = [...hits.values()].sort((a, b) => classifyAuthority(a.url).rank - classifyAuthority(b.url).rank);

    let llmSummary = '';
    if (localMode !== 'instant') {
      try {
        onLog('Writing answer with in-browser AI...');
        const snippetCtx = [
          pageContext ? 'CURRENT PAGE:\n' + pageContext.slice(0, 1400) : '',
          hitList.slice(0, 4).map((h) => `- ${h.title}: ${h.excerpt}`).join('\n'),
          matchedDetails.slice(0, 3).map((d) => `- ${d.num} ${d.title} (${d.src}): ${d.sum}`).join('\n'),
        ].filter(Boolean).join('\n\n');
        llmSummary = await runLocalLLM(
          'You are a concise California traffic engineering assistant. Answer in 3-4 short plain-English bullets using ONLY the supplied excerpts. Name CA MUTCD 2026, Caltrans 2026, LADOT, or the specific city.',
          `Question: ${cleanText}\n\nExcerpts:\n${snippetCtx}`
        );
      } catch {}
    }

    const lines = [];
    if (llmSummary) { lines.push('### AI Answer', llmSummary.trim(), ''); }
    if (pageAns) { lines.push(pageAns, ''); }

    if (!isPageOnly) {
      const grouped = new Map();
      for (const h of hitList.slice(0, 6)) {
        const b = classifyAuthority(h.url).bucket;
        if (!grouped.has(b)) grouped.set(b, []);
        if (grouped.get(b).length < 2) grouped.get(b).push(h);
      }
      for (const [bucket, items] of grouped.entries()) {
        lines.push(`### ${bucket}`);
        for (const h of items) {
          const ex = (h.excerpt || '').trim().slice(0, 140);
          lines.push(`- **[${h.title}](${h.url})** — ${ex}${ex.length >= 140 ? '…' : ''}`);
        }
        lines.push('');
      }
    }

    if (!lines.length && !matchedDetails.length && !found.length) {
      lines.push('No direct matches found. Try a sign code (`R3-17`), Caltrans sheet (`A88A`), LADOT drawing (`S-481.0`), or city (`Long Beach`, `Torrance`).');
    }

    return { found: isPageOnly ? [] : found, matchedDetails: isPageOnly ? [] : matchedDetails, answer: lines.join('\n'), hits: hitList, mode: localMode };
  }

  function renderResultHTML(r) {
    const signsHtml = r.found.length ? '<div class="ai-signs">' + r.found.map((s) =>
      `<a class="scard" href="${esc(s.url)}"><span class="simg"><img src="${esc(s.svg)}" alt=""></span><span class="scode">${esc(s.code)}</span></a>`).join('') + '</div>' : '';
    const detHtml = r.matchedDetails.length ? '<div class="vis-strip" style="margin:0.5rem 0;grid-template-columns:repeat(2,1fr)">' + r.matchedDetails.map((d) =>
      `<a class="vis-card" href="${esc(d.url)}">${d.img ? `<img loading="lazy" src="${esc(d.img)}" alt="${esc(d.num)}">` : ''}<span><b>${esc(d.num)}</b>${esc((d.title || '').slice(0, 30))}</span></a>`).join('') + '</div>' : '';
    return signsHtml + detHtml + '<div class="ai-answer">' + md(r.answer) + '</div>';
  }

  window.SSSAsk = {
    askSite,
    renderResultHTML,
    enableBrowserAI,
    startOAuth,
    disconnectOAuth,
    getState: () => ({ mode: localMode, loading: localLoading, msg: lastStatus }),
    onStatus: (fn) => { listeners.add(fn); fn({ mode: localMode, loading: localLoading, msg: lastStatus, pct: localMode !== 'instant' ? 100 : null }); },
    md,
    esc,
  };

  // MUTCD Section Summarizer
  function sectionText(root, anchorId) {
    const a = root.getElementById ? root.getElementById(anchorId) : root.querySelector('#' + anchorId);
    if (!a) return '';
    let el = a.nextElementSibling, out = [], seenHeading = false;
    while (el) {
      if (el.matches && el.matches('span.anchor')) break;
      if (/H2/.test(el.tagName)) { if (seenHeading) break; seenHeading = true; }
      const copy = el.cloneNode(true); copy.querySelectorAll('del,.pn').forEach(n => n.remove()); out.push(copy.textContent || '');
      el = el.nextElementSibling;
    }
    return out.join('\n').slice(0, 9000);
  }

  async function explainSection(anchorId, box) {
    const here = sectionText(document, anchorId);
    const isCA = location.pathname.includes('/ca-mutcd/');
    const ch = location.pathname.split('/').filter(Boolean).pop();
    let other = '';
    try {
      const url = BASE + (isCA ? '/mutcd/' : '/ca-mutcd/') + ch + '/';
      const doc = new DOMParser().parseFromString(await (await fetch(url)).text(), 'text/html');
      other = sectionText(doc, anchorId);
    } catch {}
    const sents = here.replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/).filter((s) => s.length > 20);
    const shalls = sents.filter((s) => /\bshall\b/i.test(s)).slice(0, 5);
    const shoulds = sents.filter((s) => /\bshould\b/i.test(s) && !/\bshall\b/i.test(s)).slice(0, 4);
    const out = ['### Standards (Shall)'];
    if (shalls.length) shalls.forEach((s) => out.push('- ' + s.slice(0, 250)));
    else out.push('- No explicit `shall` statement detected.');
    out.push('', '### Guidance (Should)');
    if (shoulds.length) shoulds.forEach((s) => out.push('- ' + s.slice(0, 230)));
    else out.push('- None detected.');
    out.push('', '### California vs. Federal');
    if (!other) out.push(`- No matching ${isCA ? 'Federal' : 'CA'} section found — likely CA-specific or renumbered.`);
    else {
      const norm = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      out.push(norm(here) === norm(other) ? '- Identical to Federal MUTCD 11th Ed. R1.' : '- **California modifies this section** — CA MUTCD 2026 governs.');
    }
    box.innerHTML = md(out.join('\n'));
  }

  function addExplainButtons() {
    if (!/\/(ca-mutcd|mutcd)\/[a-z0-9]+\/$/.test(location.pathname)) return;
    document.querySelectorAll('span.anchor').forEach((a) => {
      const h = a.nextElementSibling && a.nextElementSibling.querySelector ? (a.nextElementSibling.matches('h2') ? a.nextElementSibling : a.nextElementSibling.querySelector('h2')) : null;
      const target = h || a.nextElementSibling;
      if (!target) return;
      const btn = document.createElement('button');
      btn.className = 'ai-explain'; btn.type = 'button'; btn.textContent = 'Summarize (shall / should / may)';
      const box = document.createElement('div'); box.className = 'ai-box'; box.hidden = true;
      btn.onclick = () => { box.hidden = false; if (!box.dataset.done) { box.dataset.done = 1; explainSection(a.id, box); } };
      target.insertAdjacentElement('afterend', box);
      target.insertAdjacentElement('afterend', btn);
    });
  }

  // Homepage 1-click AI prompt wiring
  function mountHomePrompt() {
    const box = document.getElementById('home-ai-prompt');
    if (!box) return;
    const oauthBtn = box.querySelector('#home-ai-oauth');
    const btn = box.querySelector('#home-ai-enable');
    const openBtn = box.querySelector('#home-ai-open');
    const calcBtn = box.querySelector('#home-calc-open');
    const dismiss = box.querySelector('#home-ai-dismiss');
    const statusEl = box.querySelector('#home-ai-status');
    const bar = box.querySelector('#home-ai-bar');

    try { if (localStorage.getItem('sss-ai-prompt-dismissed') === '1') box.hidden = true; } catch {}

    window.SSSAsk.onStatus(({ mode, loading, msg, pct }) => {
      if (statusEl) statusEl.textContent = msg;
      if (bar) {
        bar.hidden = pct === null || pct >= 100;
        if (pct !== null) bar.value = pct;
      }
      if (oauthBtn) {
        oauthBtn.textContent = mode === 'openrouter' ? 'Connected (Disconnect)' : 'Connect AI (1-Click)';
      }
      if (btn) {
        if (mode === 'web-ai' || mode === 'chrome-ai') { btn.textContent = 'Local AI Ready'; btn.disabled = true; }
        else if (loading) { btn.textContent = 'Loading AI...'; btn.disabled = true; }
        else { btn.textContent = 'Use Free Local AI'; btn.disabled = false; }
      }
    });

    if (oauthBtn) oauthBtn.onclick = () => { if (localMode === 'openrouter') disconnectOAuth(); else startOAuth(); };
    if (btn) btn.onclick = () => { enableBrowserAI().catch(() => {}); };
    if (openBtn) openBtn.onclick = () => { window.SSSPanel && window.SSSPanel.open('ask'); };
    if (calcBtn) calcBtn.onclick = () => { window.SSSPanel && window.SSSPanel.open('calc'); };
    if (dismiss) dismiss.onclick = () => { box.hidden = true; try { localStorage.setItem('sss-ai-prompt-dismissed', '1'); } catch {} };
  }

  window.__ready(async () => {
    addExplainButtons();
    mountHomePrompt();
    if (await completeOAuthIfPresent()) return;
    try {
      if (localStorage.getItem(OR_KEY)) {
        localMode = 'openrouter';
        emitStatus('Connected via OpenRouter (free models)', 100);
        return;
      }
    } catch {}
    await detectChromeAI();
    try {
      if (localStorage.getItem(AI_PREF_KEY) === '1' && localMode === 'instant') {
        enableBrowserAI().catch(() => {});
      }
    } catch {}
  });
})();
