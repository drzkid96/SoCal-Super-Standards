window.__ready = window.__ready || ((f) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', f) : f()));
// SoCal Super Standards Assistant:
// - Works out-of-the-box with ZERO API key using built-in Pagefind + details.json + signs-index + checks.json synthesis
// - Optional upgrade: Google Gemini (free tier, supports screenshots), OpenRouter (free models), Local Ollama (no key), or Anthropic Claude
(() => {
  const BASE = '/SoCal-Super-Standards';
  const PROV_KEY = 'sss-ai-provider';
  const KEY_STORE = 'sss-ai-key';
  const LEGACY_KEY = 'sss-anthropic-key';
  const MODEL_KEY = 'sss-ai-model';

  const DEFAULT_MODELS = {
    builtin: '',
    gemini: 'gemini-2.5-flash',
    openrouter: 'meta-llama/llama-3.3-70b-instruct:free',
    ollama: 'llama3.2',
    anthropic: 'claude-sonnet-4-5',
  };
  const PROVIDER_LABELS = {
    builtin: 'Built-in Instant Engine (Free)',
    gemini: 'Google Gemini (Free Tier)',
    openrouter: 'OpenRouter',
    ollama: 'Local Ollama',
    anthropic: 'Anthropic Claude',
  };

  let pagefind = null;
  let signs = null;
  let details = null;
  let checks = null;

  const getProv = () => {
    try {
      const p = localStorage.getItem(PROV_KEY);
      if (p && DEFAULT_MODELS[p] !== undefined) return p;
      if (localStorage.getItem(LEGACY_KEY)) return 'anthropic';
    } catch {}
    return 'builtin';
  };
  const getKey = () => {
    try { return localStorage.getItem(KEY_STORE) || localStorage.getItem(LEGACY_KEY) || ''; } catch { return ''; }
  };
  const getModel = (prov = getProv()) => {
    try { return localStorage.getItem(MODEL_KEY) || DEFAULT_MODELS[prov] || ''; } catch { return DEFAULT_MODELS[prov] || ''; }
  };

  const strip = (h) => (h || '').replace(/<[^>]+>/g, '');
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function md(text) {
    let h = String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
    h = h.replace(/\[([^\]]+)\]\((\/?[^)\s]+)\)/g, (m, t, u) => `<a href="${/^(https?:\/\/|\/)/.test(u) ? u : '#'}">${t}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    h = h.split(/\n{2,}/).map((p) => {
      if (/^###\s+/.test(p)) return '<h4>' + p.replace(/^###\s+/, '') + '</h4>';
      if (/^\s*[-*] /m.test(p)) {
        return '<ul>' + p.split('\n').filter((l) => l.trim()).map((l) => '<li>' + l.replace(/^\s*[-*] /, '') + '</li>').join('') + '</ul>';
      }
      return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    }).join('');
    return h;
  }

  async function loadPagefind() {
    if (!pagefind) {
      pagefind = await import(/* @vite-ignore */ BASE + '/pagefind/pagefind.js');
      await pagefind.init();
    }
    return pagefind;
  }
  async function loadSigns() {
    if (!signs) {
      try { signs = await (await fetch(BASE + '/data/signs-index.json')).json(); } catch { signs = {}; }
    }
    return signs;
  }
  async function loadDetails() {
    if (!details) {
      try { details = await (await fetch(BASE + '/data/details.json')).json(); } catch { details = []; }
    }
    return details;
  }
  async function loadChecks() {
    if (!checks) {
      try { checks = await (await fetch(BASE + '/data/checks.json')).json(); } catch { checks = {}; }
    }
    return checks;
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

  // Multi-provider cloud/local LLM call (only used when user explicitly selects a provider other than builtin)
  async function callLLM(promptText, system, images = [], maxTokens = 1600) {
    const prov = getProv();
    const key = getKey();
    const model = getModel(prov);

    if (prov === 'gemini') {
      if (!key) throw new Error('Add your free Google Gemini API key (aistudio.google.com/apikey) or switch to Built-in Instant Engine.');
      const parts = [{ text: promptText }];
      for (const im of images) parts.push({ inline_data: { mime_type: im.media, data: im.data } });
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model || 'gemini-2.5-flash')}:generateContent?key=${encodeURIComponent(key)}`;
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: system }] },
          contents: [{ role: 'user', parts }],
          generationConfig: { maxOutputTokens: maxTokens },
        }),
      });
      if (!r.ok) throw new Error('Gemini API error ' + r.status + ': ' + (await r.text()).slice(0, 240));
      const j = await r.json();
      return (j.candidates?.[0]?.content?.parts || []).map((p) => p.text || '').join('\n');
    }

    if (prov === 'openrouter') {
      if (!key) throw new Error('Add your OpenRouter API key (openrouter.ai/keys) or switch to Built-in Instant Engine.');
      const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'authorization': 'Bearer ' + key,
          'HTTP-Referer': location.origin,
          'X-Title': 'SoCal Super Standards',
        },
        body: JSON.stringify({
          model: model || 'meta-llama/llama-3.3-70b-instruct:free',
          max_tokens: maxTokens,
          messages: [{ role: 'system', content: system }, { role: 'user', content: promptText }],
        }),
      });
      if (!r.ok) throw new Error('OpenRouter error ' + r.status + ': ' + (await r.text()).slice(0, 240));
      const j = await r.json();
      return j.choices?.[0]?.message?.content || '';
    }

    if (prov === 'ollama') {
      const r = await fetch('http://localhost:11434/api/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          model: model || 'llama3.2',
          stream: false,
          messages: [{ role: 'system', content: system }, { role: 'user', content: promptText }],
        }),
      });
      if (!r.ok) throw new Error('Local Ollama error ' + r.status + ' (make sure Ollama is running with OLLAMA_ORIGINS=*).');
      const j = await r.json();
      return j.message?.content || '';
    }

    if (prov === 'anthropic') {
      if (!key) throw new Error('Add your Anthropic API key or switch to Built-in Instant Engine.');
      const content = [];
      for (const im of images) content.push({ type: 'image', source: { type: 'base64', media_type: im.media, data: im.data } });
      content.push({ type: 'text', text: promptText });
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify({ model: model || 'claude-sonnet-4-5', max_tokens: maxTokens, system, messages: [{ role: 'user', content }] }),
      });
      if (!r.ok) throw new Error('Claude API error ' + r.status + ': ' + (await r.text()).slice(0, 240));
      const j = await r.json();
      return j.content.filter((c) => c.type === 'text').map((c) => c.text).join('\n');
    }

    throw new Error('Unknown provider.');
  }

  function fileToB64(file) {
    return new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res({ media: file.type || 'image/png', data: String(fr.result).split(',')[1] });
      fr.onerror = rej;
      fr.readAsDataURL(file);
    });
  }

  function classifyAuthority(url) {
    if (url.includes('/ca-mutcd/') || url.includes('/caltrans/la28-supplement/')) return { rank: 1, bucket: 'CA MUTCD 2026 (Legal Standard)' };
    if (url.includes('/caltrans/standard-plans-2026/') || url.includes('/details/caltrans/') || url.includes('/bulletins/caltrans-') || url.includes('/markings/')) return { rank: 2, bucket: 'Caltrans 2026 & State Bulletins' };
    if (url.includes('/ladot/') || url.includes('/details/ladot/') || url.includes('/bulletins/ladot-')) return { rank: 3, bucket: 'City of Los Angeles (LADOT)' };
    if (/\/(long-beach|palmdale|torrance|gardena|glendora|burbank|pasadena|santa-monica|west-hollywood|culver-city|cities)\//.test(url)) return { rank: 4, bucket: 'LA County Municipal Standards' };
    if (url.includes('/topics/') || url.includes('/bulletins/')) return { rank: 5, bucket: 'Design Summaries & Comparisons' };
    return { rank: 6, bucket: 'Federal Baseline & National Guides' };
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

  // ------------------------------------------------------------------ ASK (Zero-Key Built-in + Optional LLM)
  async function ask(text, images, log) {
    const prov = getProv();
    const cleanText = (text || '').trim();
    if (!cleanText && !images.length) throw new Error('Type a question, sign code, detail number, or topic first.');

    if (images.length && (prov === 'builtin' || prov === 'openrouter' || prov === 'ollama')) {
      throw new Error('Screenshot vision requires Google Gemini (free API key) or Anthropic Claude. Expand the Optional AI panel below to connect free Gemini in 15 seconds, or type your question in text.');
    }

    log('Searching CA MUTCD 2026, Caltrans 2026, LADOT, 10 LA County cities & libraries...');
    const [sx, det, chk] = await Promise.all([loadSigns(), loadDetails(), loadChecks()]);

    // Extract sign codes & drawing numbers directly from query
    const rawCodes = cleanText.match(/\b(?:R|W|G|S|D|E|M|C|OM|SR|SW|SG)\d+[A-Z0-9-]*(?:\(CA\))?\b/gi) || [];
    const foundSignsMap = new Map();
    for (const c of rawCodes) {
      const up = c.toUpperCase();
      const hit = sx[up] || sx[up.replace(/\(CA\)$/, '')] || sx[up + '(CA)'];
      if (hit && !foundSignsMap.has(hit.code)) foundSignsMap.set(hit.code, hit);
    }

    // Also match signs by keyword if fewer than 4 matched by code
    const tokens = cleanText.toLowerCase().replace(/[^a-z0-9.-]+/g, ' ').split(/\s+/).filter((t) => t.length >= 2 && !/^(the|and|for|with|what|how|does|are|can|use|per|in|of|to|on|at|is|a|an)$/.test(t));
    if (foundSignsMap.size < 4 && tokens.length) {
      for (const s of Object.values(sx)) {
        if (foundSignsMap.size >= 6) break;
        const hay = ((s.code || '') + ' ' + (s.descriptor || '') + ' ' + (s.name || '')).toLowerCase();
        if (tokens.filter((t) => hay.includes(t)).length >= Math.min(2, tokens.length)) {
          foundSignsMap.set(s.code, s);
        }
      }
    }
    const found = [...foundSignsMap.values()].slice(0, 6);

    // Match visual standard drawings & figures from details.json
    const qLower = cleanText.toLowerCase();
    const matchedDetails = det
      .map((d) => ({ d, s: scoreDetail(d, qLower, tokens) }))
      .filter((x) => x.s >= 16)
      .sort((a, b) => b.s - a.s)
      .slice(0, 6)
      .map((x) => x.d);

    // Pagefind full-text search
    const hits = new Map();
    const queries = [cleanText];
    if (tokens.length > 3) queries.push(tokens.slice(0, 4).join(' '));
    for (const q of queries) {
      for (const h of await pfSearch(q, 10)) {
        if (!hits.has(h.url)) hits.set(h.url, h);
      }
    }

    // Supersedence flags
    const flagText = (u) => {
      try {
        const k = new URL(u, location.origin).pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
        return (chk[k] || []).filter((c) => c.sev === 'warn').map((c) => `${c.title}: ${c.text}`).join(' | ');
      } catch { return ''; }
    };

    const hitList = [...hits.values()].sort((a, b) => classifyAuthority(a.url).rank - classifyAuthority(b.url).rank);

    // If user connected an optional LLM, synthesize with it
    if (prov !== 'builtin') {
      log(`Synthesizing answer with ${PROVIDER_LABELS[prov] || prov}...`);
      const ctx = hitList.slice(0, 14).map((h, i) => {
        const fl = flagText(h.url);
        return `[${i + 1}] ${h.title}\nURL: ${h.url}\n${h.excerpt}${fl ? '\nSUPERSEDENCE FLAG: ' + fl : ''}`;
      }).join('\n\n');
      const detCtx = matchedDetails.map((d) => `- ${d.num} ${d.title} (${d.src}): ${d.sum} [Link](${d.url})`).join('\n');
      const answer = await callLLM(
        `Question: ${cleanText || '(see attached image)'}\n\nMatched drawings:\n${detCtx || 'none'}\n\nMatched signs: ${found.map((s) => s.code + ' ' + s.descriptor).join('; ') || 'none'}\n\nSite search results:\n${ctx}`,
        `You are the SoCal Super Standards assistant for California traffic engineers.
Answer concisely using ONLY the provided results. Cite every claim with markdown links like [CA MUTCD 3C.05](url).
Order of authority: CA MUTCD 2026 is the legal standard in California; Caltrans 2026 Standard Plans & HDM/DIBs govern state design; LADOT and LA County city plans govern local ROW; FHWA/AASHTO/NACTO are guidance.
Call out Standards (shall), Guidance (should), Options (may), and any SUPERSEDENCE FLAG.`,
        images,
        1600
      );
      return { summary: `Answered via ${PROVIDER_LABELS[prov]}`, found, matchedDetails, answer, hits: hitList };
    }

    // Built-in Instant Zero-Key Engineering Synthesis
    const grouped = new Map();
    const warnings = [];
    for (const h of hitList.slice(0, 14)) {
      const b = classifyAuthority(h.url).bucket;
      if (!grouped.has(b)) grouped.set(b, []);
      if (grouped.get(b).length < 4) grouped.get(b).push(h);
      const fl = flagText(h.url);
      if (fl) warnings.push(`**Supersedence flag on [${h.title}](${h.url}):** ${fl}`);
    }

    const lines = [];
    if (warnings.length) {
      lines.push('### Supersedence & Currency Alerts');
      warnings.slice(0, 3).forEach((w) => lines.push('- ' + w));
      lines.push('');
    }
    if (!hitList.length && !matchedDetails.length && !found.length) {
      lines.push('No direct matches found for that phrasing. Try shorter engineering terms, a sign code (`R3-17`, `W11-2`), a Caltrans sheet (`A24F`, `A88A`, `Detail 22`), or a city name (`Long Beach`, `Torrance`, `Palmdale`).');
    } else {
      lines.push('**Order of authority in LA County:** **CA MUTCD 2026** (legal baseline) → **Caltrans 2026 Plans / HDM Ch. 1000 / DIBs** (statewide design criteria) → **LADOT or local LA County city standard plans** (local ROW) → **Federal MUTCD / AASHTO / FHWA / NACTO** (guidance).');
      lines.push('');
      for (const [bucket, items] of grouped.entries()) {
        lines.push(`### ${bucket}`);
        for (const h of items) {
          const ex = (h.excerpt || '').trim().slice(0, 220);
          lines.push(`- **[${h.title}](${h.url})** — ${ex}${ex.length >= 220 ? '…' : ''}`);
        }
        lines.push('');
      }
    }

    return {
      summary: `Instant lookup across ${hitList.length} sections, ${matchedDetails.length} drawings, and ${found.length} signs (no API key needed).`,
      found,
      matchedDetails,
      answer: lines.join('\n'),
      hits: hitList,
    };
  }

  // ------------------------------------------------------------------ EXPLAIN (Zero-Key + Optional LLM)
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

  function localExplain(here, other, isCA) {
    const sents = here.replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/).filter((s) => s.length > 20);
    const shalls = sents.filter((s) => /\bshall\b/i.test(s)).slice(0, 5);
    const shoulds = sents.filter((s) => /\bshould\b/i.test(s) && !/\bshall\b/i.test(s)).slice(0, 4);
    const mays = sents.filter((s) => /\bmay\b/i.test(s) && !/\bshall\b|\bshould\b/i.test(s)).slice(0, 3);
    const out = [];
    out.push('### Standards (Shall — Mandatory)');
    if (shalls.length) shalls.forEach((s) => out.push('- ' + s.slice(0, 260)));
    else out.push('- No explicit `shall` statement detected in this excerpt.');
    out.push('');
    out.push('### Guidance (Should — Recommended)');
    if (shoulds.length) shoulds.forEach((s) => out.push('- ' + s.slice(0, 240)));
    else out.push('- None detected.');
    out.push('');
    if (mays.length) {
      out.push('### Options (May — Permissive)');
      mays.forEach((s) => out.push('- ' + s.slice(0, 220)));
      out.push('');
    }
    out.push('### California vs. Federal Check');
    if (!other) {
      out.push(`- Matching ${isCA ? 'Federal MUTCD' : 'CA MUTCD'} section was not found — likely a California-specific or renumbered section.`);
    } else {
      const norm = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      if (norm(here) === norm(other)) {
        out.push('- Text is substantively identical between CA MUTCD 2026 and Federal MUTCD 11th Ed. R1.');
      } else {
        const diffLen = here.length - other.length;
        out.push(`- **California modifies this section** (${diffLen >= 0 ? '+' : ''}${diffLen} chars vs. ${isCA ? 'Federal' : 'CA'} counterpart). In California, **CA MUTCD 2026 governs** over Federal MUTCD.`);
      }
    }
    return out.join('\n');
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
    const prov = getProv();
    if (prov === 'builtin') {
      box.innerHTML = md(localExplain(here, other, isCA));
      return;
    }
    box.innerHTML = `<p class="ai-wait">Summarizing with ${esc(PROVIDER_LABELS[prov])}...</p>`;
    try {
      const out = await callLLM(
        `Section: ${title}\n\n${isCA ? 'CA MUTCD 2026' : 'Federal MUTCD 11th Ed. Rev. 1'} text:\n${here}\n\n${isCA ? 'Federal MUTCD 11th Ed. Rev. 1' : 'CA MUTCD 2026'} text:\n${other || '(not found)'}`,
        `Explain this MUTCD section to a practicing California traffic engineer:
1) Standards (shall), Guidance (should), Options (may) — concise bullets.
2) California vs. federal differences.
3) Practical signing/striping plan review notes for Southern California.`,
        [],
        1400
      );
      box.innerHTML = md(out);
    } catch (e) {
      box.innerHTML = md(localExplain(here, other, isCA)) + '<p class="note">Cloud AI fallback note: ' + esc(e.message) + '</p>';
    }
  }

  function addExplainButtons() {
    if (!/\/(ca-mutcd|mutcd)\/[a-z0-9]+\/$/.test(location.pathname)) return;
    document.querySelectorAll('span.anchor').forEach((a) => {
      const h = a.nextElementSibling && a.nextElementSibling.querySelector ? (a.nextElementSibling.matches('h2') ? a.nextElementSibling : a.nextElementSibling.querySelector('h2')) : null;
      const target = h || a.nextElementSibling;
      if (!target) return;
      const btn = document.createElement('button');
      btn.className = 'ai-explain'; btn.type = 'button'; btn.textContent = 'Summarize section (shall/should/may)';
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

    function syncUI() {
      const p = getProv();
      $('#ai-provider').value = p;
      $('#ai-key').value = getKey() ? '••••••••••••' : '';
      $('#ai-model').value = getModel(p);
      $('#ai-mode-badge').innerHTML = 'Mode: <strong>' + esc(PROVIDER_LABELS[p] || p) + '</strong>';
    }
    syncUI();

    try { const q0 = new URLSearchParams(location.search).get('q'); if (q0) $('#ai-text').value = q0; } catch {}

    $('#ai-provider').onchange = () => {
      const p = $('#ai-provider').value;
      $('#ai-model').value = DEFAULT_MODELS[p] || '';
    };
    $('#ai-save').onclick = () => {
      const p = $('#ai-provider').value;
      const v = $('#ai-key').value.trim();
      const m = $('#ai-model').value.trim() || DEFAULT_MODELS[p] || '';
      try {
        localStorage.setItem(PROV_KEY, p);
        if (v && !v.startsWith('••')) localStorage.setItem(KEY_STORE, v);
        localStorage.setItem(MODEL_KEY, m);
      } catch {}
      syncUI();
      $('#ai-keymsg').textContent = p === 'builtin' ? 'Using Built-in Instant Engine (free, no key).' : 'Saved in this browser only.';
    };
    $('#ai-forget').onclick = () => {
      try {
        localStorage.setItem(PROV_KEY, 'builtin');
        localStorage.removeItem(KEY_STORE);
        localStorage.removeItem(LEGACY_KEY);
        localStorage.removeItem(MODEL_KEY);
      } catch {}
      syncUI();
      $('#ai-keymsg').textContent = 'Reset to Built-in Instant Engine (free, no key).';
    };

    root.querySelectorAll('.ask-ex').forEach((b) => {
      b.onclick = () => {
        $('#ai-text').value = b.dataset.q || b.textContent;
        $('#ai-go').click();
      };
    });

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
      const log = (m) => { out.innerHTML = '<p class="ai-wait">' + esc(m) + '</p>'; };
      try {
        const r = await ask($('#ai-text').value.trim(), images, log);
        const signsHtml = r.found.length ? '<div class="ai-signs">' + r.found.map((s) =>
          `<a class="scard" href="${esc(s.url)}"><span class="simg"><img src="${esc(s.svg)}" alt=""></span><span class="scode">${esc(s.code)}</span><span class="sname">${esc(s.descriptor || s.name || '')}</span></a>`).join('') + '</div>' : '';
        const detHtml = r.matchedDetails.length ? '<div class="vis-strip" style="margin:0.75rem 0">' + r.matchedDetails.map((d) =>
          `<a class="vis-card" href="${esc(d.url)}">${d.img ? `<img loading="lazy" src="${esc(d.img)}" alt="${esc(d.num)}">` : ''}<span><b>${esc(d.num)}</b>${esc((d.title || '').slice(0, 48))}</span></a>`).join('') + '</div>' : '';
        out.innerHTML = (r.summary ? '<p class="ai-sum">' + esc(r.summary) + '</p>' : '') + signsHtml + detHtml + '<div class="ai-answer">' + md(r.answer) + '</div>'
          + '<details class="ai-src"><summary>All matching pages (' + r.hits.length + ')</summary><ul>' + r.hits.map((h) => `<li><a href="${esc(h.url)}">${esc(h.title)}</a></li>`).join('') + '</ul></details>';
      } catch (e) { out.innerHTML = '<p class="ai-err">' + esc(e.message) + '</p>'; }
    };

    $('#ai-text').addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') $('#ai-go').click();
    });

    // Add a reference (works with or without API key)
    $('#ref-go').onclick = async () => {
      const box = $('#ref-out');
      const src = $('#ref-src').value.trim();
      if (!src) return;
      const notes = $('#ref-notes').value.trim();
      const body = `## New Standard / Reference Request\n\n- **Source / Document:** ${src}\n- **Notes:** ${notes || '(none provided)'}\n- **Status:** Please verify current edition & licensing before embedding.\n- **Requested extraction:** Key standard drawings, governing tables, and local deviations from CA MUTCD 2026 / Caltrans 2026.\n`;
      const title = 'New reference: ' + src.slice(0, 80);
      const url = 'https://github.com/drzkid96/SoCal-Super-Standards/issues/new?labels=new-reference&title=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(body);
      box.innerHTML = md(body) + `<p><a class="ai-btn" href="${url}" target="_blank" rel="noopener">Open GitHub issue to add it</a></p>`;
    };
  }

  window.__ready(() => { mountAsk(); addExplainButtons(); });
})();
