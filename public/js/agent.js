window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));
// Unified SoCal Super Standards Assistant (window.SSSAsk)
// Powers: (1) /ask/ page, (2) Right-side Ask drawer (panel.js), (3) MUTCD section summarizer.
// Zero API keys, zero setup. Instant built-in standards engine + optional 1-click in-browser AI model.
(() => {
  const BASE = '/SoCal-Super-Standards';
  let pagefind = null;
  let signs = null;
  let details = null;
  let checks = null;

  // Optional built-in browser AI (Chrome built-in LanguageModel or lazy Transformers.js Qwen2.5-0.5B)
  let localPipe = null;
  let localMode = 'instant'; // 'instant' | 'chrome-ai' | 'web-ai'
  let localLoading = false;

  const strip = (h) => (h || '').replace(/<[^>]+>/g, '');
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  function md(text) {
    let h = esc(text);
    h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => `<a href="${safeUrl(u.replace(/&amp;/g, '&'))}">${t}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    return h.split(/\n{2,}/).map((p) => {
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

  // Detect Chrome/Edge built-in on-device AI automatically (zero download, zero key)
  async function detectChromeAI() {
    try {
      if (typeof LanguageModel !== 'undefined' && LanguageModel.availability) {
        const av = await LanguageModel.availability();
        if (av === 'available' || av === 'readily') {
          localMode = 'chrome-ai';
          return true;
        }
      }
    } catch {}
    return false;
  }

  // Lazy-load lightweight in-browser AI model (Qwen2.5-0.5B-Instruct via Transformers.js, cached in browser)
  async function enableBrowserAI(onProgress) {
    if (localMode === 'chrome-ai') return 'chrome-ai';
    if (localPipe) { localMode = 'web-ai'; return 'web-ai'; }
    if (localLoading) return localMode;
    localLoading = true;
    try {
      if (await detectChromeAI()) {
        if (onProgress) onProgress('Using built-in browser AI (ready).');
        return 'chrome-ai';
      }
      if (onProgress) onProgress('Loading free in-browser AI model (first time ~250 MB, cached afterward)...');
      const { pipeline } = await import(/* @vite-ignore */ 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.4.0');
      localPipe = await pipeline('text-generation', 'onnx-community/Qwen2.5-0.5B-Instruct', {
        dtype: 'q4',
        progress_callback: (p) => {
          if (onProgress && p && p.status === 'progress' && typeof p.progress === 'number') {
            onProgress(`Loading in-browser AI: ${Math.round(p.progress)}%`);
          }
        },
      });
      localMode = 'web-ai';
      if (onProgress) onProgress('In-browser AI ready (runs locally, no API key).');
      return 'web-ai';
    } catch (e) {
      localMode = 'instant';
      if (onProgress) onProgress('Using Instant Built-in Engine (browser AI unavailable here).');
      throw e;
    } finally {
      localLoading = false;
    }
  }

  async function runLocalLLM(system, prompt) {
    if (localMode === 'chrome-ai' && typeof LanguageModel !== 'undefined') {
      const sess = await LanguageModel.create({ systemPrompt: system });
      try { return await sess.prompt(prompt); } finally { sess.destroy && sess.destroy(); }
    }
    if (localMode === 'web-ai' && localPipe) {
      const out = await localPipe(
        [{ role: 'system', content: system }, { role: 'user', content: prompt.slice(0, 3200) }],
        { max_new_tokens: 320, temperature: 0.2, do_sample: false }
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

  // Page-aware instant summary / checklist / Q&A (used by right-side drawer on any page)
  function extractPageAnswer(q, pageText, pageChecks) {
    const ql = (q || '').toLowerCase();
    const sents = (pageText || '').replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/).filter((s) => s.length > 18 && s.length < 340);
    const out = [];

    if (/supersed|current|check|govern|flag/.test(ql)) {
      if (pageChecks && pageChecks.length) {
        out.push('### Status & Supersedence Checks on This Page');
        pageChecks.forEach((c) => out.push(`- **${c.sev === 'warn' ? 'Check' : 'In effect'} — ${c.title}:** ${c.text}`));
      } else {
        out.push('No supersedence warnings are flagged on this page. In LA County, **CA MUTCD 2026** is the legal baseline, **Caltrans 2026 / HDM Ch. 1000** govern state design, and local city standard plans govern local right-of-way.');
      }
      return out.join('\n');
    }

    if (/checklist|requirement|shall|dimension|plan review/.test(ql)) {
      const reqs = sents.filter((s) => /\b(shall|must|minimum|maximum|min\.|max\.|\d+\s*(?:ft|in\.|mph|%))\b/i.test(s)).slice(0, 7);
      out.push('### Plan Review Checklist (from this page)');
      if (reqs.length) reqs.forEach((s) => out.push('- ' + s));
      else sents.slice(0, 5).forEach((s) => out.push('- ' + s));
      return out.join('\n');
    }

    if (/summar|explain|key value|what/.test(ql) && tokenize(ql).length <= 4) {
      const shalls = sents.filter((s) => /\bshall\b/i.test(s)).slice(0, 3);
      const shoulds = sents.filter((s) => /\bshould\b/i.test(s) && !/\bshall\b/i.test(s)).slice(0, 2);
      const dims = sents.filter((s) => /\d+\s*(?:ft|in\.|mph|%)/i.test(s)).slice(0, 3);
      const picked = [...new Set([...shalls, ...dims, ...shoulds, ...sents.slice(0, 3)])].slice(0, 6);
      out.push('### Quick Summary of This Page');
      picked.forEach((s) => out.push('- ' + s));
      return out.join('\n');
    }

    // Keyword match on current page first
    const toks = tokenize(ql);
    const scored = sents.map((s) => ({
      s,
      n: toks.reduce((acc, t) => acc + (s.toLowerCase().includes(t) ? 1 : 0), 0),
    })).filter((x) => x.n > 0).sort((a, b) => b.n - a.n).slice(0, 4);

    if (scored.length) {
      out.push('### On This Page');
      scored.forEach((x) => out.push('- ' + x.s));
    }
    return out.join('\n');
  }

  // Unified Ask function used by BOTH /ask/ and the right-side drawer
  async function askSite(query, opts = {}) {
    const cleanText = (query || '').trim();
    if (!cleanText) throw new Error('Type a question, sign code, detail number, or city name.');
    const onLog = opts.onLog || (() => {});
    const pageContext = opts.pageText || '';
    const pageChecks = opts.pageChecks || [];

    onLog('Searching standards...');
    const [sx, det, chk] = await Promise.all([loadSigns(), loadDetails(), loadChecks()]);

    // 1. Page-local answer if called from a specific page drawer
    let pageAns = '';
    if (pageContext) {
      pageAns = extractPageAnswer(cleanText, pageContext, pageChecks);
    }

    // 2. Match signs
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
        if (foundSignsMap.size >= 6) break;
        const hay = ((s.code || '') + ' ' + (s.descriptor || '') + ' ' + (s.name || '')).toLowerCase();
        if (tokens.filter((t) => hay.includes(t)).length >= Math.min(2, tokens.length)) foundSignsMap.set(s.code, s);
      }
    }
    const found = [...foundSignsMap.values()].slice(0, 6);

    // 3. Match standard drawings & figures
    const qLower = cleanText.toLowerCase();
    const matchedDetails = det
      .map((d) => ({ d, s: scoreDetail(d, qLower, tokens) }))
      .filter((x) => x.s >= 16)
      .sort((a, b) => b.s - a.s)
      .slice(0, opts.compact ? 4 : 6)
      .map((x) => x.d);

    // 4. Full-site Pagefind search (skip if it's purely a "summarize/checklist/supersede this page" button)
    const isPageOnly = pageContext && /^(explain this|summarize|plan review checklist|what could supersede|is it current|key values)/i.test(cleanText);
    const hits = new Map();
    if (!isPageOnly) {
      const queries = [cleanText];
      if (tokens.length > 3) queries.push(tokens.slice(0, 4).join(' '));
      for (const q of queries) {
        for (const h of await pfSearch(q, opts.compact ? 5 : 10)) {
          if (!hits.has(h.url)) hits.set(h.url, h);
        }
      }
    }
    const hitList = [...hits.values()].sort((a, b) => classifyAuthority(a.url).rank - classifyAuthority(b.url).rank);

    // 5. If in-browser AI is enabled, synthesize a concise plain-English answer grounded in the hits
    let llmSummary = '';
    if (localMode !== 'instant') {
      try {
        onLog('Writing plain-English answer with in-browser AI...');
        const snippetCtx = [
          pageContext ? 'CURRENT PAGE:\n' + pageContext.slice(0, 1400) : '',
          hitList.slice(0, 5).map((h) => `- ${h.title}: ${h.excerpt}`).join('\n'),
          matchedDetails.slice(0, 4).map((d) => `- ${d.num} ${d.title} (${d.src}): ${d.sum}`).join('\n'),
        ].filter(Boolean).join('\n\n');
        llmSummary = await runLocalLLM(
          'You are a concise California traffic engineering assistant. Answer in 3-5 short plain-English bullets using ONLY the supplied standards excerpts. Name CA MUTCD 2026, Caltrans 2026, LADOT, or the specific city.',
          `Question: ${cleanText}\n\nExcerpts:\n${snippetCtx}`
        );
      } catch {}
    }

    // 6. Compose clean markdown answer
    const lines = [];
    if (llmSummary) {
      lines.push('### AI Summary');
      lines.push(llmSummary.trim());
      lines.push('');
    }
    if (pageAns) {
      lines.push(pageAns);
      lines.push('');
    }

    const flagText = (u) => {
      try {
        const k = new URL(u, location.origin).pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
        return (chk[k] || []).filter((c) => c.sev === 'warn').map((c) => `${c.title}: ${c.text}`).join(' | ');
      } catch { return ''; }
    };

    if (!isPageOnly) {
      const grouped = new Map();
      const warnings = [];
      for (const h of hitList.slice(0, opts.compact ? 6 : 12)) {
        const b = classifyAuthority(h.url).bucket;
        if (!grouped.has(b)) grouped.set(b, []);
        if (grouped.get(b).length < (opts.compact ? 2 : 3)) grouped.get(b).push(h);
        const fl = flagText(h.url);
        if (fl) warnings.push(`**Check [${h.title}](${h.url}):** ${fl}`);
      }
      if (warnings.length) {
        lines.push('### Supersedence Alerts');
        warnings.slice(0, 2).forEach((w) => lines.push('- ' + w));
        lines.push('');
      }
      for (const [bucket, items] of grouped.entries()) {
        lines.push(`### ${bucket}`);
        for (const h of items) {
          const ex = (h.excerpt || '').trim().slice(0, opts.compact ? 140 : 210);
          lines.push(`- **[${h.title}](${h.url})** — ${ex}${ex.length >= (opts.compact ? 140 : 210) ? '…' : ''}`);
        }
        lines.push('');
      }
    }

    if (!lines.length && !matchedDetails.length && !found.length) {
      lines.push('No direct matches found. Try a sign code (`R3-17`, `W11-2`), a Caltrans sheet (`A24F`, `A88A`), an LADOT drawing (`S-481.0`), or a city name (`Long Beach`, `Torrance`).');
    }

    return {
      found: isPageOnly ? [] : found,
      matchedDetails: isPageOnly ? [] : matchedDetails,
      answer: lines.join('\n'),
      hits: hitList,
      mode: localMode,
    };
  }

  function renderResultHTML(r, compact = false) {
    const signsHtml = r.found.length ? '<div class="ai-signs">' + r.found.map((s) =>
      `<a class="scard" href="${esc(s.url)}"><span class="simg"><img src="${esc(s.svg)}" alt=""></span><span class="scode">${esc(s.code)}</span><span class="sname">${esc(s.descriptor || s.name || '')}</span></a>`).join('') + '</div>' : '';
    const detHtml = r.matchedDetails.length ? '<div class="vis-strip" style="margin:0.6rem 0">' + r.matchedDetails.map((d) =>
      `<a class="vis-card" href="${esc(d.url)}">${d.img ? `<img loading="lazy" src="${esc(d.img)}" alt="${esc(d.num)}">` : ''}<span><b>${esc(d.num)}</b>${esc((d.title || '').slice(0, compact ? 32 : 48))}</span></a>`).join('') + '</div>' : '';
    const srcHtml = !compact && r.hits.length ? '<details class="ai-src"><summary>All matching pages (' + r.hits.length + ')</summary><ul>' + r.hits.map((h) => `<li><a href="${esc(h.url)}">${esc(h.title)}</a></li>`).join('') + '</ul></details>' : '';
    return signsHtml + detHtml + '<div class="ai-answer">' + md(r.answer) + '</div>' + srcHtml;
  }

  // Expose unified global API for panel.js
  window.SSSAsk = { askSite, renderResultHTML, enableBrowserAI, getMode: () => localMode, md, esc };

  // ------------------------------------------------------------------ MUTCD SECTION SUMMARIZER
  function sectionText(root, anchorId) {
    const a = root.getElementById ? root.getElementById(anchorId) : root.querySelector('#' + anchorId);
    if (!a) return '';
    let el = a.nextElementSibling, out = [], seenHeading = false;
    while (el) {
      if (el.matches && el.matches('span.anchor')) break;
      if (/H2/.test(el.tagName)) { if (seenHeading) break; seenHeading = true; }
      out.push(el.innerText || el.textContent || '');
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
    const mays = sents.filter((s) => /\bmay\b/i.test(s) && !/\bshall\b|\bshould\b/i.test(s)).slice(0, 3);
    const out = ['### Standards (Shall — Mandatory)'];
    if (shalls.length) shalls.forEach((s) => out.push('- ' + s.slice(0, 260)));
    else out.push('- No explicit `shall` statement in this section.');
    out.push('', '### Guidance (Should — Recommended)');
    if (shoulds.length) shoulds.forEach((s) => out.push('- ' + s.slice(0, 240)));
    else out.push('- None detected.');
    if (mays.length) {
      out.push('', '### Options (May — Permissive)');
      mays.forEach((s) => out.push('- ' + s.slice(0, 220)));
    }
    out.push('', '### California vs. Federal');
    if (!other) out.push(`- No matching ${isCA ? 'Federal' : 'CA'} section found — likely California-specific or renumbered.`);
    else {
      const norm = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      out.push(norm(here) === norm(other)
        ? '- Substantively identical between CA MUTCD 2026 and Federal MUTCD 11th Ed. R1.'
        : '- **California modifies this section.** In California, **CA MUTCD 2026 governs**.');
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

  // ------------------------------------------------------------------ /ask/ PAGE UI
  async function mountAsk() {
    const root = document.getElementById('sss-ask');
    if (!root) return;
    const $ = (s) => root.querySelector(s);
    const status = $('#ai-status');
    const localBtn = $('#ai-local-btn');

    if (await detectChromeAI()) {
      status.textContent = 'Built-in browser AI active';
      localBtn.hidden = true;
    }

    localBtn.onclick = async () => {
      localBtn.disabled = true;
      try {
        await enableBrowserAI((m) => { status.textContent = m; });
        localBtn.textContent = 'In-Browser AI Active';
      } catch {
        localBtn.disabled = false;
      }
    };

    try { const q0 = new URLSearchParams(location.search).get('q'); if (q0) $('#ai-text').value = q0; } catch {}

    const run = async () => {
      const out = $('#ai-out');
      const q = $('#ai-text').value.trim();
      if (!q) return;
      out.innerHTML = '<p class="ai-wait">Searching standards...</p>';
      try {
        const r = await askSite(q, { onLog: (m) => { out.innerHTML = '<p class="ai-wait">' + esc(m) + '</p>'; } });
        out.innerHTML = renderResultHTML(r, false);
      } catch (e) {
        out.innerHTML = '<p class="ai-err">' + esc(e.message) + '</p>';
      }
    };

    $('#ai-go').onclick = run;
    $('#ai-clear').onclick = () => { $('#ai-text').value = ''; $('#ai-out').innerHTML = ''; };
    $('#ai-text').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run(); } });
    root.querySelectorAll('.ask-ex').forEach((b) => {
      b.onclick = () => { $('#ai-text').value = b.dataset.q || b.textContent; run(); };
    });
  }

  window.__ready(() => { mountAsk(); addExplainButtons(); });
})();
