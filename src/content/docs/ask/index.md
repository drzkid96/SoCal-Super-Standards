---
title: Ask the standards
description: Ask any Southern California traffic engineering question — works immediately for free with no API key, or optionally connect free Gemini / OpenRouter / Ollama / Claude for plan screenshots.
tableOfContents: false
---

<div id="sss-ask">

<div class="ai-panel">
<h2>Ask a traffic engineering question <span style="font-size:0.78rem;font-weight:600;color:var(--sss-accent);margin-left:0.4rem">Works immediately &middot; Free &middot; No API key needed</span></h2>
<p class="note">Searches all <strong>1,647 details &amp; figures</strong>, <strong>1,148 signs</strong>, <strong>CA MUTCD 2026</strong>, <strong>Caltrans 2026</strong>, <strong>LADOT</strong>, and <strong>10 LA County cities</strong>, returning governing rules, matching sign artwork, standard drawing thumbnails, and supersedence flags.</p>
<div class="ql-samples" style="margin:0.5rem 0 0.75rem" aria-label="Sample questions">
  <span>Try:</span>
  <button type="button" class="ask-ex" data-q="Class IV separated bikeway minimum width and buffer">Class IV bikeway width</button>
  <button type="button" class="ask-ex" data-q="S-481.0 red curb sight distance daylighting">S-481.0 red curb</button>
  <button type="button" class="ask-ex" data-q="R3-17 bike lane sign California">R3-17(CA) bike sign</button>
  <button type="button" class="ask-ex" data-q="A88A curb ramp maximum slope flare landing">A88A curb ramp slopes</button>
  <button type="button" class="ask-ex" data-q="Torrance arterial merge taper 40 mph T1004">Torrance 40 mph taper</button>
  <button type="button" class="ask-ex" data-q="Long Beach turn pocket arrows LB 308">Long Beach turn arrows</button>
</div>
<div id="ai-drop" class="ai-drop">
<textarea id="ai-text" rows="4" placeholder="Ask a question, paste plan review comments, or type sign/detail codes (e.g. R3-17, A24F, S-481.0, Detail 22, DIB 94, ST-16). Paste or drop a screenshot if using Gemini or Claude."></textarea>
<div class="ai-row"><label class="ai-btn ghost">Add screenshot (optional)<input id="ai-file" type="file" accept="image/*" multiple hidden></label><div id="ai-thumbs" class="ai-thumbs"></div></div>
</div>
<div class="ai-row">
  <button id="ai-go" class="ai-btn" type="button">Find governing standards</button>
  <button id="ai-clear" class="ai-btn ghost" type="button">Clear</button>
  <span id="ai-mode-badge" class="note" style="margin-left:auto">Mode: <strong>Built-in Instant Engine (Free)</strong></span>
</div>
<div id="ai-out" class="ai-out"></div>
</div>

<details class="ai-panel" id="ai-settings-wrap">
<summary style="cursor:pointer;font-weight:700;font-size:0.98rem">Optional: Connect a free Cloud AI or Local Ollama (for plan screenshots &amp; conversational summaries)</summary>
<p class="note" style="margin-top:0.6rem">Not required for normal lookups. If you want AI vision for plan screenshots or conversational answers, pick a free provider below—keys stay only in your browser (<code>localStorage</code>).</p>
<div class="ai-row" style="flex-wrap:wrap;gap:0.5rem;margin-top:0.5rem">
  <select id="ai-provider" aria-label="AI provider">
    <option value="builtin">Built-in Instant Engine (Free, No Key)</option>
    <option value="gemini">Google Gemini 2.5 Flash (Free API Key · Vision)</option>
    <option value="openrouter">OpenRouter (Free Llama / Gemini Models)</option>
    <option value="ollama">Local Ollama (Free, No Key · localhost:11434)</option>
    <option value="anthropic">Anthropic Claude (API Key · Vision)</option>
  </select>
  <input id="ai-key" type="password" placeholder="API key (not needed for Built-in or Ollama)" autocomplete="off">
  <input id="ai-model" type="text" placeholder="Model (optional override)" style="max-width:240px">
  <button id="ai-save" class="ai-btn" type="button">Save</button>
  <button id="ai-forget" class="ai-btn ghost" type="button">Reset to Free Built-in</button>
</div>
<p class="note" id="ai-provider-help" style="margin-top:0.45rem">Free Gemini key takes ~15 seconds at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> (no credit card). Free OpenRouter models at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai/keys</a>.</p>
<span id="ai-keymsg" class="note"></span>
</details>

<details class="ai-panel">
<summary style="cursor:pointer;font-weight:700;font-size:0.98rem">Suggest a new standard or city manual to add</summary>
<p class="note" style="margin-top:0.5rem">Name a document or paste its link. Drafts a ready-to-submit GitHub issue (works with or without an AI key).</p>
<div class="ai-row"><input id="ref-src" type="text" placeholder="e.g. City of Santa Clarita Traffic Standards, https://..."></div>
<div class="ai-row"><input id="ref-notes" type="text" placeholder="Notes (optional): which sheets matter, edition, etc."></div>
<div class="ai-row"><button id="ref-go" class="ai-btn" type="button">Draft GitHub issue</button></div>
<div id="ref-out" class="ai-out"></div>
</details>

</div>

Tip: Every section of both MUTCD readers also has a **Summarize section** button that extracts **Standards (`shall`)**, **Guidance (`should`)**, **Options (`may`)**, and **California vs. Federal differences**—instantly, with no API key required.
