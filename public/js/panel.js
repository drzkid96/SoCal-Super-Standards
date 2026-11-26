// Mount reference checks and engineering calculators when the reader opens them.
(() => {
  if(window.SSSAgency?.active && !location.pathname.endsWith('/tools/')) return;
  const BASE = '/SoCal-Super-Standards';
  const TAB_KEY = 'sss-panel-tab';
  const ls = { get: (k, d = '') => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : '#');

  const path = location.pathname.replace(/index\.html$/, '').replace(/\/?$/, '/');
  const kind = path.includes('/details/') ? 'detail' : path.includes('/signs/') && !path.endsWith('/signs/') ? 'sign'
    : path.includes('/bulletins/') ? 'bulletin' : /\/(mutcd|ca-mutcd)\//.test(path) ? 'manual' : 'page';

  const trigger=document.querySelector('[data-open-checks]');
  function mount(){
  let checks = [];
  const ui = document.createElement('aside');
  ui.className = 'sp';
  ui.setAttribute('aria-label', 'Checks and calculators');
  ui.innerHTML = `

    <div class="sp-body" hidden>
      <div class="sp-head">
        <div class="sp-tabs" role="tablist">
          <button role="tab" data-t="checks" type="button">Checks</button>
          <button role="tab" data-t="calc" type="button">Calc</button>
        </div>
        <button class="sp-x" type="button" aria-label="Close panel">&times;</button>
      </div>

      <section class="sp-pane" data-p="checks"></section>

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
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">1. Work-Zone Taper &amp; Buffer (CA MUTCD 6B &amp; 6K)</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Speed (mph)<select id="c-spd">${[20,25,30,35,40,45,50,55,60,65,70,75].map(v => `<option ${v === 35 ? "selected" : ""}>${v}</option>`).join("")}</select></label>
              <label>Lateral offset (ft)<input id="c-lw" type="number" value="12" min="0.01" step="any" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-tcp-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">2. Curb ramp horizontal run</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Curb Ht (in)<input id="c-ch" type="number" value="6" min="0.01" step="any" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Slope (%)<input id="c-sl" type="number" value="7.5" min="0.01" step="any" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
            </div>
            <div id="c-ramp-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">3. Pedestrian signal timing (CA MUTCD 4I.06)</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Curb to far side (ft)<input id="c-cd" type="number" value="56" min="0.01" step="any" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Requested WALK (s)<input id="c-wk" type="number" value="7" min="4" step="1" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
              <label>Clearance speed (ft/s)<input id="c-ped-speed" type="number" value="3.5" min="0.01" max="3.5" step="any"></label>
              <label>Steady hand buffer (s)<input id="c-buffer" type="number" value="2" min="2" step="1"></label>
              <label>Starting point<select id="c-start"><option value="curb">No detector (6 ft behind curb)</option><option value="detector">Pedestrian detector</option></select></label>
              <label id="c-offset-label" hidden>Detector to curb (ft)<input id="c-offset" type="number" value="6" min="0" step="any"></label>
            </div>
            <div id="c-ped-out" style="background:var(--fp-band,#F2F2F2);padding:0.45rem 0.55rem;border-radius:6px;line-height:1.45"></div>
          </div>

          <div style="border:1px solid var(--fp-grid,#E7E8E8);border-radius:10px;padding:0.65rem;background:#fff">
            <strong style="color:var(--fp-emerald,#00574A);display:block;margin-bottom:0.35rem">4. Level-road stopping sight distance</strong>
            <div style="display:grid;grid-template-columns:1fr;gap:0.4rem;margin-bottom:0.45rem">
              <label>Approach Speed (mph)<input id="c-ssd-v" type="number" value="35" min="20" max="75" step="5" style="width:100%;padding:0.25rem;border:1px solid #D0D4D4;border-radius:6px"></label>
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
    trigger?.setAttribute('aria-expanded',String(o));
    ui.classList.toggle('open', o);
    document.documentElement.classList.toggle('sp-open', o);
    if(o)$('.sp-x').focus();else trigger?.closest('details')?.querySelector('summary')?.focus();
  }
  function setTab(t) {
    if(t!=='calc')t='checks';
    ui.querySelectorAll('.sp-tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.t === t)));
    ui.querySelectorAll('.sp-pane').forEach((p) => (p.hidden = p.dataset.p !== t));
    ls.set(TAB_KEY, t);
  }

  window.SSSPanel = {
    open: (tab) => { setOpen(true); if (tab) setTab(tab); },
    close: () => setOpen(false),
  };

  function updateCalcs() {
    const input = (id) => $(id).value.trim() === '' ? NaN : Number($(id).value);
    const zone = window.SSSCalculations.workZone(input('#c-spd'), input('#c-lw'));
    $('#c-tcp-out').innerHTML = zone ? `Merge <b>${zone.merge} ft</b> · Shift <b>${zone.shift} ft</b> · Shoulder <b>${zone.shoulder} ft</b><br>
      Level-road longitudinal buffer <b>${zone.buffer} ft</b><br>
      Maximum device spacing · ordinary taper <b>${zone.taper} ft</b> · tangent <b>${zone.tangent} ft</b><br>
      Conflicting or absent markings on intermediate- or short-term work · taper and tangent <b>${zone.conflict} ft</b><br>
      One-lane, two-way or downstream taper · length <b>50–100 ft</b> · device spacing <b>${zone.specialSpacing} ft maximum</b><br>
      <a href="https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/2026-camutcd-2026-6b-a11y.pdf#page=13">Taper criteria</a> · <a href="${BASE}/ca-mutcd/6k/#6k01">Device spacing</a>`
      : 'Enter a positive lateral offset and a listed speed.';
    // 2. ADA Curb Ramp Run
    const run = window.SSSCalculations.rampRun(input('#c-ch'), input('#c-sl'));
    $('#c-ramp-out').innerHTML = run === null ? 'Enter a positive rise and slope.' :
      `Horizontal run <b>${run.toFixed(2)} ft</b>. Landing length is additional.
      <a href="https://www.access-board.gov/ada/guides/chapter-4-ramps-and-curb-ramps/">Ramp and landing criteria</a> ·
      <a href="${BASE}/santa-monica/standard-plans/">Santa Monica design criteria</a>`;

    const detector = $('#c-start').value === 'detector';
    $('#c-offset-label').hidden = !detector;
    const ped = window.SSSCalculations.pedestrian(input('#c-cd'), input('#c-wk'), input('#c-ped-speed'), input('#c-buffer'), detector ? input('#c-offset') : 6);
    $('#c-ped-out').innerHTML = ped ? `WALK <b>${ped.walk} s</b> · flashing hand <b>${ped.change} s</b> · steady buffer <b>${ped.buffer} s</b><br>
      Clearance <b>${ped.clearance} s</b> · total <b>${ped.total} s</b> · minimum at 3 ft/s from starting point <b>${ped.totalMinimum} s</b><br>
      WALK is normally at least 7 s. A 4 s minimum applies where pedestrian volumes and characteristics permit. Consider a lower clearance speed where slower pedestrians routinely cross.
      <a href="${BASE}/ca-mutcd/4i/#4i06">CA MUTCD §4I.06</a>`
      : 'Enter a positive distance and clearance speed up to 3.5 ft/s, a whole WALK of at least 4 s, a whole buffer of at least 2 s and a nonnegative offset.';
    // 4. Red Curb / SSD
    const distance = window.SSSCalculations.levelRoadSightDistance(input('#c-ssd-v'));
    $('#c-ssd-out').innerHTML = distance === null ? 'Choose a speed from 20 to 75 mph in 5 mph increments.' :
      `Stopping sight distance <b>${distance} ft</b> on a level road.
      <a href="${BASE}/ca-mutcd/6b/#6b06">CA MUTCD §6B.06, Table 6B-2</a>`;
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
    const deck = document.querySelector('.sss-ms-wrap:not(.is-compact)');
    const frames = deck?.querySelectorAll('.sheet-stage > .sheet-frame');
    let active = frames?.[deck.querySelector('.sc-select').selectedIndex];
    if (deck?.classList.contains('is-all')) {
      const top = Math.max(0, deck.querySelector('.sheet-controls').getBoundingClientRect().bottom);
      active = [...frames].find(frame => {
        const rect = frame.getBoundingClientRect();
        return rect.bottom > top && rect.top < innerHeight;
      }) || active;
    }
    const button = (active || document).querySelector('.agency-copy');
    if (button) return button.dataset.citation + new URL(button.dataset.url, location.href).href;
    const h1 = (document.querySelector('h1')?.innerText || document.title).trim();
    const date = [...document.querySelectorAll('.sl-markdown-content td, .sl-markdown-content p')].map((e) => e.innerText).join(' ').match(/\b(?:dated|Date[d:]?)\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})/i);
    return `${h1}${date ? ` (sheet dated ${date[1]})` : ''}. SoCal Super Standards, accessed ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}. ${location.href}`;
  }

  window.__ready(async () => {
    document.body.append(ui);
    // Wire live calculators
    ['#c-ped-speed', '#c-buffer', '#c-start', '#c-offset', '#c-spd', '#c-lw', '#c-ch', '#c-sl', '#c-cd', '#c-wk', '#c-ssd-v'].forEach((id) => {
      const el = $(id);
      if (el) el.addEventListener('input', updateCalcs);
    });
    updateCalcs();

    $('[data-p="checks"]').addEventListener('click', async (e) => {
      const b = e.target.closest('.sp-cite'); if (!b) return;
      try { await navigator.clipboard.writeText(citation()); b.textContent = 'Copied'; } catch { b.textContent = citation(); }
      setTimeout(() => (b.textContent = 'Copy citation'), 1800);
    });

    $('.sp-x').addEventListener('click', () => setOpen(false));
    ui.querySelector('.sp-tabs').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) setTab(b.dataset.t); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ui.classList.contains('open')) setOpen(false); });
    setTab(ls.get(TAB_KEY, 'checks'));
    if ((kind !== 'page' || !path.includes('/regions/'))) try {
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
  });
  }
  function openTools(tab){
    mount();
    window.SSSPanel.open(tab);
  }
  window.SSSPanel={open:openTools,close:()=>{}};
  window.__ready(()=>{
    if(trigger){
      trigger.hidden=false;
      trigger.onclick=()=>{trigger.closest('details').open=false;window.SSSPanel.open();};
    }
    const calculators = document.querySelector('[data-show-calculators]');
    if (calculators) {
      calculators.onclick = event => { event.preventDefault(); window.SSSPanel.open('calc'); };
      if (location.hash === '#calculators') window.SSSPanel.open('calc');
    }
    if(path.endsWith('/ask/'))window.SSSPanel.open('checks');
  });
})();

document.addEventListener('click', async (event) => {
  const button = event.target.closest('.agency-copy');
  if (!button) return;
  const citation = button.dataset.citation + new URL(button.dataset.url, location.href).href;
  try { await navigator.clipboard.writeText(citation); button.textContent = 'Copied'; }
  catch { button.textContent = citation; }
});
