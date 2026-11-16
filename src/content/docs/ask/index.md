---
title: Ask the standards
description: Paste a screenshot, a plan snip, or messy notes. Claude finds the signs and topics, searches every source on this site, and answers with linked sections.
tableOfContents: false
---

<div id="sss-ask">

<div class="ai-panel">
<h2>1. Your Claude key</h2>
<p class="note">Your Anthropic API key is stored only in this browser (localStorage) and sent only to Anthropic. Get one at console.anthropic.com. Usage is billed to your account.</p>
<div class="ai-row">
<input id="ai-key" type="password" placeholder="sk-ant-..." autocomplete="off">
<select id="ai-model"><option value="claude-sonnet-5-5">Claude Sonnet 5.5 (fast)</option><option value="claude-opus-5-5">Claude Opus 5.5 (best)</option><option value="claude-haiku-5-5">Claude Haiku 5.5 (cheapest)</option></select>
<button id="ai-save" class="ai-btn" type="button">Save</button>
<button id="ai-forget" class="ai-btn ghost" type="button">Forget key</button>
<span id="ai-keymsg" class="note"></span>
</div>
</div>

<div class="ai-panel">
<h2>2. Ask</h2>
<div id="ai-drop" class="ai-drop">
<textarea id="ai-text" rows="5" placeholder="Paste text, notes, a comment to respond to, or a question. You can also paste or drop a screenshot here (Ctrl+V)."></textarea>
<div class="ai-row"><label class="ai-btn ghost">Add screenshot<input id="ai-file" type="file" accept="image/*" multiple hidden></label><div id="ai-thumbs" class="ai-thumbs"></div></div>
</div>
<div class="ai-row"><button id="ai-go" class="ai-btn" type="button">Find the right sections</button><button id="ai-clear" class="ai-btn ghost" type="button">Clear</button></div>
<div id="ai-out" class="ai-out"></div>
</div>

<div class="ai-panel">
<h2>3. Add a reference</h2>
<p class="note">Name a document or paste its link. Claude drafts the entry, and you open it as a GitHub issue with the PDF attached for processing.</p>
<div class="ai-row"><input id="ref-src" type="text" placeholder="e.g. LADOT MPP 521 Traffic Signal Design Guidelines, https://..."></div>
<div class="ai-row"><input id="ref-notes" type="text" placeholder="Notes (optional): which parts matter, edition, etc."></div>
<div class="ai-row"><button id="ref-go" class="ai-btn" type="button">Draft entry</button></div>
<div id="ref-out" class="ai-out"></div>
</div>

</div>

Tip: every section of both MUTCD readers has an **Explain with Claude** button that summarizes the shall / should / may items and lists California vs federal differences.
