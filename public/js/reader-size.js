// Display preferences affect illustrations and chart cards only. Both readers work without storage.
(() => {
  const article = document.querySelector('.sl-markdown-content');
  if (!article) return;

  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
    catch { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
  }
  function make(tag, cls, text) {
    const element = document.createElement(tag);
    if (cls) element.className = cls;
    if (text) element.textContent = text;
    return element;
  }
  function button(text, title) {
    const b = make('button', '', text);
    b.type = 'button';
    b.title = title;
    return b;
  }
  function range(label, min, max, step) {
    const input = make('input');
    input.type = 'range';
    input.min = min;
    input.max = max;
    input.step = step;
    input.setAttribute('aria-label', label);
    return input;
  }
  const sheetKey = 'sss-sheet-size-v1';
  const saved = read(sheetKey, null);
  let preference = saved === 'fit' || (Number.isInteger(saved) && saved >= 10 && saved <= 100) ? saved : null;
  const groups = [];
  const allScans = [...article.querySelectorAll('figure.dfig img, figure.mfig a > img, figure.type-example a > img, .sdetail-img img.sheet')].filter(
    img => !img.closest('.vibe-hero, .sheet-strip, .sgrid, .thumbgrid') && !/\/vibes\/|\/photo[-/]/i.test(img.src)
  );
  const decks = new Map();
  for (const img of allScans) {
    const deck = img.closest('.sss-ms-wrap');
    if (!decks.has(deck)) decks.set(deck, []);
    decks.get(deck).push(img);
    img.classList.add('sized-scan');
  }

  function setSize(value) {
    preference = value;
    save(sheetKey, value);
    for (const update of groups) update();
  }
  for (const [deck, images] of decks) {
    const scope = deck || article;
    const controls = make('div', 'reader-size not-content');
    controls.setAttribute('role','group');
    controls.setAttribute('aria-label','Sheet display size');
    const label = make('span', 'size-label', 'Sheet size');
    const slider = range('Sheet size in percent of available width', 10, 100, 1);
    const output = make('span', 'size-value');
    output.setAttribute('aria-hidden', 'true');
    const fit = button('Fit page', 'Fit the entire original sheet on screen');
    const full = button('Full width', 'Use the full reading width');
    controls.append(label, slider, output, fit, full);
    if (deck) {
      deck.querySelector('.sheet-controls').append(controls);
    } else {
      let first = images[0];
      while (first.parentElement !== article) first = first.parentElement;
      first.before(controls);
      controls.classList.add('loose-size');
      if (!article.querySelector('.sheet-controls,.sfilter,.sss-sheetbar')) controls.classList.add('sticky-size');
    }
    const update = () => {
      const mode = preference ?? (deck ? 'fit' : 100);
      const auto = mode === 'fit';
      // A deck sets its own sizing variables, including when it sits inside a mixed article.
      scope.style.setProperty('--scan-width', auto ? 'auto' : mode + '%');
      scope.style.setProperty('--scan-height', auto ? 'min(74dvh, max(6rem, calc(100dvh - var(--sl-nav-height, 4rem) - var(--reader-controls-height, 3rem) - 4rem)))' : 'none');
      fit.setAttribute('aria-pressed',String(auto));
      full.setAttribute('aria-pressed',String(mode === 100));
      const measured = auto ? images.find(img => img.clientWidth && img.naturalWidth) : null;
      const percent = measured ? Math.round(100 * measured.clientWidth / (measured.closest('figure') || measured.parentElement).clientWidth) : 100;
      slider.value = auto ? Math.min(100, Math.max(10, percent)) : mode;
      output.textContent = auto ? 'Fit' : mode + '%';
      slider.setAttribute('aria-valuetext',auto ? 'Fit page' : mode + ' percent');
    };
    groups.push(update);
    fit.onclick = () => setSize('fit');
    full.onclick = () => setSize(100);
    slider.oninput = () => setSize(Number(slider.value));
    update();
    const toolbar = deck?.querySelector('.sheet-controls') || controls;
    if (window.ResizeObserver) new ResizeObserver(() => {
      scope.style.setProperty('--reader-controls-height',toolbar.offsetHeight+'px');
      update();
    }).observe(toolbar);
    scope.addEventListener('load', e => {
      if (preference !== null && preference !== 'fit') return;
      if (e.target.matches?.('.sized-scan') && e.target.closest('.sss-ms-wrap') === deck) update();
    },true);
    if (deck) toolbar.addEventListener('click', () => requestAnimationFrame(update));
  }

  const filter = article.querySelector('.sfilter');
  const sign = Boolean(filter?.querySelector('#sq'));
  if (!filter || (!sign && !article.querySelector('.mcat-sec .mgrid'))) return;
  const chartKey = 'sss-chart-size-' + (sign ? 'signs' : 'markings');
  const presets = [
    ['Wall chart',48,68], ['Extra compact',62,90], ['Compact',82,122],
    ['Small',100,170], ['Standard',118,250], ['Large',162,310], ['Extra large',214,410]
  ];
  const prefs = read(chartKey, {});
  const sizes = prefs && typeof prefs === 'object' && !Array.isArray(prefs) ? prefs : {};
  const gridGroups = new Map();
  const names = new Map();
  for (const grid of article.querySelectorAll(sign ? '.sseries .sgrid' : '.mcat-sec .mgrid')) {
    const section = grid.closest(sign ? '.sseries' : '.mcat-sec');
    const title = sign ? document.getElementById(section.dataset.cat) : section.querySelector('h2');
    if (!title) continue;
    const key = title.id;
    if (!gridGroups.has(key)) {
      gridGroups.set(key, []);
      names.set(key, title.textContent.replace(/\s*\d+\s*$/, '').trim());
    }
    gridGroups.get(key).push(grid);
  }
  if (!gridGroups.size) return;
  const controls = make('div','chart-size reader-size not-content');
  controls.setAttribute('role','group');
  controls.setAttribute('aria-label','Chart display size');
  const category = make('select');
  category.setAttribute('aria-label','Category to resize');
  category.add(new Option('All categories','*'));
  for (const [key,name] of names) category.add(new Option(name,key));
  const slider = range('Chart size',1,presets.length,1);
  const output = make('span','chart-size-value');
  const reset = button('Reset','Restore the standard size for the selected categories');
  controls.append(make('span','size-label','Chart size'),category,slider,output,reset);
  filter.append(controls);
  const valid = n => Number.isInteger(n) && n >= 0 && n < presets.length;
  function level(key) { return valid(sizes[key]) ? sizes[key] : valid(sizes['*']) ? sizes['*'] : 4; }
  function draw() {
    for (const [key,grids] of gridGroups) {
      const n = level(key);
      const width = presets[n][sign ? 1 : 2];
      for (const grid of grids) {
        grid.dataset.chartLevel = String(n);
        grid.style.setProperty('--card-size',width+'px');
        grid.style.setProperty('--art-size',(sign ? width * .70 : width * .60)+'px');
      }
    }
    const key = category.value;
    const n = level(key);
    const mixed = key === '*' && [...gridGroups.keys()].some(k => level(k) !== n);
    slider.value = n+1;
    output.textContent = mixed ? 'Mixed sizes' : presets[n][0];
    slider.setAttribute('aria-valuetext',output.textContent);
  }
  function change(n) {
    if (category.value === '*') for (const key of Object.keys(sizes)) delete sizes[key];
    sizes[category.value] = n;
    save(chartKey,sizes);
    draw();
  }
  category.onchange = draw;
  slider.oninput = () => change(Number(slider.value)-1);
  reset.onclick = () => change(4);
  draw();
})();