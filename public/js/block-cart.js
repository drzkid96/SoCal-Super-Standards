/* SSS block cart: pick blocks anywhere, review them in a side cart, edit simple blocks, and download one
   combined DWG library (sheet frames per group, title, scale, labels) plus the original files. */
(() => {
  if (window.SSSBlockCart) return;
  const base = '/SoCal-Super-Standards', key = 'sss-block-cart-v1', signKey = 'sss-sign-legends-v2';
  const G = () => window.SSSBlockGenerators;
  const el = (tag, attrs = {}, ...kids) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'text') node.textContent = v;
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) node.setAttribute(k, v === true ? '' : v);
    }
    node.append(...kids.filter(Boolean));
    return node;
  };
  const defaults = {title: '', scale: 20, sheets: true, labels: true, groupBy: 'group', sort: 'cart', dots: false, signs: true};
  let state = load(), index, busy = false;
  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(key) || '{}');
      return {items: Array.isArray(s.items) ? s.items : [], options: {...defaults, ...(s.options || {})}};
    } catch { return {items: [], options: {...defaults}}; }
  }
  function save() { try { localStorage.setItem(key, JSON.stringify(state)); } catch {} render(); }
  const keyOf = item => item.kind === 'custom' ? 'custom:' + item.gen + ':' + JSON.stringify(item.params) : item.code;
  const has = code => state.items.some(i => i.code === code);
  function signIds() {
    try { return [...new Set((JSON.parse(localStorage.getItem(signKey) || '[]')).flatMap(g => (g.records || []).map(r => typeof r === 'string' ? r : r?.id)).filter(Boolean))]; }
    catch { return []; }
  }
  async function meta() {
    if (index) return index;
    const r = await fetch(base + '/data/cad-block-entities/index.json');
    if (!r.ok) throw Error('The block list could not load. Try again.');
    return (index = await r.json());
  }
  function toggle(code) {
    if (has(code)) state.items = state.items.filter(i => i.code !== code);
    else state.items.push({kind: 'block', code});
    save();
  }
  function addCustom(gen, params) {
    const item = {kind: 'custom', gen, params: G().clean(gen, params)};
    if (!state.items.some(i => keyOf(i) === keyOf(item))) state.items.push(item);
    save(); openCart();
  }

  // ---- launcher and drawer -------------------------------------------------------------------------
  const count = el('span', {class: 'bc-count'});
  const launcher = el('button', {type: 'button', class: 'bc-launch', 'aria-haspopup': 'dialog', onclick: () => openCart()},
    el('span', {text: 'Block cart'}), count);
  const list = el('ul', {class: 'bc-items'});
  const status = el('p', {class: 'bc-status', role: 'status', 'aria-live': 'polite'});
  const field = (label, input) => el('label', {class: 'bc-field'}, el('span', {text: label}), input);
  const opt = (name, values) => {
    const s = el('select', {name}, ...values.map(([v, t]) => el('option', {value: v, text: t})));
    s.value = String(state.options[name]);
    s.addEventListener('change', () => { state.options[name] = isNaN(+s.value) || s.value === '' ? s.value : +s.value; save(); });
    return s;
  };
  const check = (name, text) => {
    const c = el('input', {type: 'checkbox', name});
    c.checked = Boolean(state.options[name]);
    c.addEventListener('change', () => { state.options[name] = c.checked; save(); });
    return el('label', {class: 'bc-check'}, c, el('span', {text}));
  };
  const title = el('input', {type: 'text', name: 'title', maxlength: 60, placeholder: 'SSS BLOCK LIBRARY'});
  title.value = state.options.title;
  title.addEventListener('input', () => { state.options.title = title.value; try { localStorage.setItem(key, JSON.stringify(state)); } catch {} });
  const signsCheck = check('signs', '');
  const download = el('button', {type: 'button', class: 'bc-primary', onclick: build}, 'Download library');
  const drawer = el('aside', {class: 'bc-drawer', 'aria-label': 'Block cart', hidden: true},
    el('header', {}, el('h2', {text: 'Block cart'}), el('button', {type: 'button', class: 'bc-close', 'aria-label': 'Close cart', onclick: () => closeCart()}, '×')),
    list,
    signsCheck,
    el('details', {class: 'bc-layout', open: true}, el('summary', {text: 'Library layout'}),
      field('Title', title),
      field('Plan scale', opt('scale', [[10, '1" = 10\''], [20, '1" = 20\''], [40, '1" = 40\''], [50, '1" = 50\'']])),
      field('Sheets', opt('groupBy', [['group', 'One 24 x 36 sheet per block group'], ['none', 'Fill sheets in cart order']])),
      field('Order', opt('sort', [['cart', 'Cart order'], ['code', 'By code']])),
      check('sheets', 'Sheet frames and title strip'),
      check('labels', 'Code under each block'),
      check('dots', 'Green fields as the LADOT dots hatch')),
    el('div', {class: 'bc-actions'}, download,
      el('button', {type: 'button', onclick: () => openEditor()}, 'Edit a block…'),
      el('button', {type: 'button', class: 'bc-quiet', onclick: () => { state.items = []; save(); }}, 'Clear')),
    status);
  document.body.append(launcher, drawer);
  function openCart() { drawer.hidden = false; launcher.setAttribute('aria-expanded', 'true'); render(); drawer.querySelector('.bc-close').focus(); }
  function closeCart() { drawer.hidden = true; launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !drawer.hidden) closeCart(); });

  async function render() {
    const signs = signIds();
    const total = state.items.length + (state.options.signs ? signs.length : 0);
    count.textContent = String(total);
    launcher.hidden = !total && !document.querySelector('[data-block-add]');
    signsCheck.hidden = !signs.length;
    signsCheck.querySelector('span').textContent = 'Include the ' + signs.length + ' sign' + (signs.length === 1 ? '' : 's') + ' in your sign legend';
    for (const b of document.querySelectorAll('[data-block-add]')) {
      const on = has(b.dataset.blockAdd);
      b.textContent = on ? 'In cart ✓' : 'Add';
      b.setAttribute('aria-pressed', String(on));
    }
    if (drawer.hidden) return;
    let m = {};
    try { m = await meta(); } catch (e) { status.textContent = e.message; }
    list.replaceChildren(...state.items.map((item, i) => {
      const remove = el('button', {type: 'button', class: 'bc-remove', 'aria-label': 'Remove', onclick: () => { state.items.splice(i, 1); save(); }}, '×');
      if (item.kind === 'custom') {
        const made = G().make(item.gen, item.params), pic = el('span', {class: 'bc-thumb'});
        pic.innerHTML = G().svg(made);
        return el('li', {}, pic, el('span', {class: 'bc-name'}, el('strong', {text: made.name}), el('small', {text: 'Edited · ' + made.label})), remove);
      }
      const info = m[item.code] || {};
      return el('li', {}, el('span', {class: 'bc-thumb'}, el('img', {src: base + '/' + (info.preview || ''), alt: ''})),
        el('span', {class: 'bc-name'}, el('strong', {text: (info.name || item.code).split(' · ')[0]}), info.route === 'markings/cad' ? null : el('small', {text: item.code})), remove);
    }));
    if (!state.items.length) list.append(el('li', {class: 'bc-empty', text: 'Add blocks with the Add button on any block card.'}));
    download.disabled = busy || !total;
  }

  async function build() {
    if (busy) return;
    const items = [...state.items];
    if (state.options.signs) for (const id of signIds()) items.push({kind: 'sign', id});
    if (!items.length) return;
    busy = true; render(); status.textContent = 'Building the library…';
    const worker = new Worker(base + '/js/block-library-worker.js');
    worker.onmessage = ({data}) => {
      if (data.progress) { status.textContent = 'Adding original drawings · ' + data.progress + ' of ' + data.total; return; }
      worker.terminate(); busy = false;
      if (data.error) { status.textContent = 'Download failed. ' + data.error; render(); return; }
      const name = ((state.options.title || 'SSS-BLOCK-LIBRARY').toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-|-$/g, '') || 'SSS-BLOCK-LIBRARY') + '.zip';
      const url = URL.createObjectURL(new Blob([data.buffer], {type: 'application/zip'})), a = el('a', {href: url, download: name});
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
      status.textContent = 'Downloaded ' + name + ': the library DWG, the original files and SSS-ASSEMBLE.scr.';
      render();
    };
    worker.postMessage({items, options: {...state.options, title: title.value}});
  }

  // ---- block editor --------------------------------------------------------------------------------
  let editor;
  function openEditor(kind = 'crosswalk') {
    if (!G()) return;
    editor ??= makeEditor();
    editor.show(kind);
  }
  // Common pavement legends offered in the text field; / starts the next line along travel.
  const LEGENDS = ['ONLY', 'BUS/ONLY', 'BIKE/ONLY', 'BUS/LANE', 'BIKE/LANE', 'KEEP/CLEAR', 'STOP', 'XING', 'PED/XING', 'SCHOOL/XING',
    'SLOW', 'YIELD', 'SIGNAL/AHEAD', 'STOP/AHEAD', 'LEFT/ONLY', 'RIGHT/ONLY', 'TURN/ONLY', 'TAXI/ONLY', 'FIRE/LANE', 'NO/PARKING', 'LOADING/ZONE'];
  function downloadOne(gen, params, status) {
    const made = G().make(gen, params);
    status.textContent = 'Building ' + made.name + '.dwg…';
    const worker = new Worker(base + '/js/block-library-worker.js');
    worker.onmessage = ({data}) => {
      worker.terminate();
      if (data.error) { status.textContent = 'Download failed. ' + data.error; return; }
      const url = URL.createObjectURL(new Blob([data.dwg], {type: 'application/acad'})), a = el('a', {href: url, download: made.name + '.dwg'});
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
      status.textContent = 'Downloaded ' + made.name + '.dwg: one block, inserted at 0,0 on P-PMARK (AutoCAD 2000).';
    };
    worker.postMessage({single: {kind: 'custom', gen, params}, options: {dots: state.options.dots}});
  }
  function makeEditor() {
    const dialog = el('dialog', {class: 'bc-editor', 'aria-label': 'Block editor'});
    const pick = el('select', {'aria-label': 'Block type'}, ...Object.entries(G().families).map(([k, f]) => el('option', {value: k, text: f.label})));
    const form = el('form', {class: 'bc-form', method: 'dialog'});
    const preview = el('div', {class: 'bc-preview'}), note = el('p', {class: 'bc-note'}), name = el('p', {class: 'bc-made'}), done = el('p', {class: 'bc-note', role: 'status'});
    let params = {};
    function draw() {
      const made = G().make(pick.value, params);
      preview.innerHTML = G().svg(made);
      name.textContent = made.name;
      note.textContent = made.note;
    }
    function fields() {
      params = G().defaults(pick.value);
      form.replaceChildren(...G().families[pick.value].fields.map(([k, label, type, d, range]) => {
        const input = type === 'select'
          ? el('select', {name: k}, ...range.map(v => el('option', {value: v, text: v})))
          : type === 'text'
            ? el('input', {type: 'text', name: k, maxlength: range[0] * 4, list: 'bc-legends', autocomplete: 'off', spellcheck: 'false', style: 'text-transform:uppercase'})
            : el('input', {type: 'number', name: k, min: range[0], max: range[1], step: range[2]});
        input.value = d;
        input.addEventListener('input', () => { params[k] = type === 'number' ? Number(input.value) : input.value; draw(); });
        if (type === 'text') { const f = field(label, input); f.append(el('datalist', {id: 'bc-legends'}, ...LEGENDS.map(v => el('option', {value: v})))); return f; }
        return field(label, input);
      }));
      draw();
    }
    pick.addEventListener('change', fields);
    form.addEventListener('submit', e => e.preventDefault());
    dialog.append(el('header', {}, el('h2', {text: 'Block editor'}), el('button', {type: 'button', class: 'bc-close', 'aria-label': 'Close editor', onclick: () => dialog.close()}, '×')),
      el('div', {class: 'bc-editor-body'}, el('div', {}, field('Block', pick), form), el('div', {}, preview, name, note, done)),
      el('div', {class: 'bc-actions'}, el('button', {type: 'button', class: 'bc-primary', onclick: () => { addCustom(pick.value, params); dialog.close(); }}, 'Add to cart'),
        el('button', {type: 'button', onclick: () => downloadOne(pick.value, {...params}, done)}, 'Download DWG')));
    document.body.append(dialog);
    return {show(kind) { pick.value = kind; done.textContent = ''; fields(); dialog.showModal(); }};
  }

  // A picture opens a larger view; only the DWG link downloads.
  let viewer;
  // Block details: base point, visibility states, filled area per color (pipeline/block_info.py)
  function specRows(info) {
    const rows = [], unit = info.unit || 'ft';
    const num = v => (+v).toFixed(2).replace(/\.?0+$/, '');
    const row = (label, ...cells) => rows.push(el('tr', {}, el('th', {scope: 'row'}, label), el('td', {}, el('div', {class: 'bv-cell'}, ...cells))));
    const colors = list => {
      if (!list.length) return [el('span', {class: 'bv-none'}, 'No filled area (line work)')];
      const out = list.map(([name, hex, a]) => el('span', {class: 'bv-area'},
        el('i', {class: 'bv-swatch', style: `background:${hex}`}), `${name} · ${num(a)} sq ${unit}`));
      if (list.length > 1) out.push(el('span', {class: 'bv-area bv-total'}, `Total · ${num(list.reduce((t, c) => t + c[2], 0))} sq ${unit}`));
      return out;
    };
    if (info.base) row('Base point', el('span', {}, info.base), ...(info.placement ? [el('small', {}, info.placement)] : []));
    if (info.states) row('Visibility states', ...(info.states.length
      ? info.states.map(s => el('span', {class: 'bv-chip'}, s)) : [el('span', {}, 'One state (static block)')]));
    if (info.area) row('Filled area', ...colors(info.area));
    if (info.areaByState) for (const [state, list] of info.areaByState) row(`Filled area · ${state}`, ...colors(list));
    if (info.size) row('Size', `${num(info.size[0])} × ${num(info.size[1])} ${unit}`);
    return rows;
  }

  function openViewer(card) {
    if (!viewer) {
      const img = el('img', {alt: ''}), title = el('strong'), name = el('span'), place = el('small', {class: 'block-place'});
      const add = el('button', {type: 'button', class: 'bc-primary'}), dwg = el('a', {download: true}, 'DWG');
      const close = el('button', {type: 'button', 'aria-label': 'Close', class: 'bv-close'}, '×');
      const spec = el('table', {class: 'bv-spec'});
      const box = el('dialog', {class: 'block-viewer', 'aria-label': 'Block details'},
        close, el('div', {class: 'bv-pic'}, img), el('div', {class: 'bv-text'}, title, name, place, spec, el('div', {class: 'bc-actions'}, add, dwg)));
      close.addEventListener('click', () => box.close());
      box.addEventListener('click', e => { if (e.target === box) box.close(); });
      add.addEventListener('click', () => { toggle(add.dataset.code); add.textContent = has(add.dataset.code) ? 'In cart · remove' : 'Add to cart'; });
      document.body.append(box);
      viewer = {box, img, title, name, place, spec, add, dwg};
    }
    const code = card.querySelector('[data-block-add]')?.dataset.blockAdd || '';
    viewer.img.src = card.querySelector('img').src;
    viewer.img.alt = card.querySelector('img').alt;
    viewer.title.textContent = card.querySelector('figcaption strong')?.textContent || code;
    viewer.name.textContent = card.querySelector('.block-code')?.textContent || '';
    viewer.place.hidden = true;
    let info = {};
    try { info = JSON.parse(card.dataset.info || '{}'); } catch (e) { info = {}; }
    viewer.spec.replaceChildren(...specRows(info));
    viewer.spec.hidden = !viewer.spec.children.length;
    viewer.add.dataset.code = code;
    viewer.add.hidden = !code;
    viewer.add.textContent = has(code) ? 'In cart · remove' : 'Add to cart';
    viewer.dwg.href = card.querySelector('.block-actions a[download]')?.href || '#';
    viewer.box.showModal();
  }

  document.addEventListener('click', e => {
    const zoom = e.target.closest('.block-zoom');
    if (zoom) { e.preventDefault(); openViewer(zoom.closest('.block-card')); return; }
    const b = e.target.closest('[data-block-add]');
    if (b) { e.preventDefault(); toggle(b.dataset.blockAdd); }
    const ed = e.target.closest('[data-block-editor]');
    if (ed) { e.preventDefault(); openEditor(ed.dataset.blockEditor || 'crosswalk'); }
  });
  window.addEventListener('storage', e => { if (e.key === key) { state = load(); render(); } if (e.key === signKey) render(); });
  window.SSSBlockCart = {open: openCart, add: toggle, edit: openEditor};
  render();
})();
