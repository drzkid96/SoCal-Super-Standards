// Enhance the static sheets in place. Original links and all print pages remain available.
(() => {
  const article = document.querySelector('.sl-markdown-content');
  if (!article) return;
  // Use the full scan even when an editorial grid originally supplied a thumbnail.
  for (const img of article.querySelectorAll('.mfig a[href*="/figs/"] > img[src*="/thumbs/figs/"]')) {
    img.src = img.parentElement.href;
  }
  const viewers = [];
  const create = (tag, text) => Object.assign(document.createElement(tag), {textContent: text || ''});

  function viewer(pages, labels, ids) {
    if (pages.length < 2) return;
    const bar = create('nav');
    bar.className = 'sheet-controls';
    bar.setAttribute('aria-label', 'Sheet navigation');
    const prev = create('button', 'Previous');
    const next = create('button', 'Next');
    const select = create('select');
    const count = create('span');
    count.setAttribute('aria-live', 'polite');
    select.setAttribute('aria-label', 'Choose sheet');
    for (const label of labels) select.add(new Option(label));
    prev.type = next.type = 'button';
    bar.append(prev, select, next, count);
    pages[0].before(bar);
    let index = 0;
    const show = (i, updateHash = false) => {
      if (i < 0 || i >= pages.length) return;
      index = i;
      pages.forEach((p,n) => { p.classList.add('sheet-frame'); p.hidden = n !== i; });
      pages[i].querySelectorAll('img[data-full-scan]').forEach(img => { img.src = img.dataset.fullScan; });
      select.selectedIndex = i;
      prev.disabled = i === 0;
      next.disabled = i === pages.length - 1;
      count.textContent = (i+1)+' of '+pages.length;
      if (updateHash && ids[i]) history.replaceState(history.state,'','#'+encodeURIComponent(ids[i]));
    };
    prev.onclick = () => show(index - 1,true);
    next.onclick = () => show(index + 1,true);
    select.onchange = () => show(select.selectedIndex,true);
    viewers.push({pages,show});
    show(0);
  }

  // Keep each scan together with its original heading, notes, and local anchors.
  const heads = [...article.children].filter(e => /^H[23]$/.test(e.tagName) && /^(Sheet \d+ of \d+|Page \d+\b)/i.test(e.textContent.trim()));
  if (heads.length > 1 && article.querySelector('figure.dfig')) {
    const starts = heads.map(h => h.previousElementSibling?.matches('p:has(> .anchor:only-child), span.anchor') ? h.previousElementSibling : h);
    const frames = starts.map((start,i) => {
      const frame = create('section');
      start.before(frame);
      let el = start;
      while (el && el !== starts[i+1]) {
        if (el !== start && el !== heads[i] && (el.matches('h2,h3,.xidx-wrap,.tsigns,nav,section'))) break;
        const after = el.nextElementSibling;
        frame.append(el); el = after;
      }
      return frame;
    });
    viewer(frames,heads.map(h=>h.textContent.trim()),heads.map((h,i)=>frames[i].querySelector('.anchor[id],figure[id]')?.id || h.id));
  }

  for (const group of article.querySelectorAll('.mfig-inline,.mfig-grid,.thumbgrid,.sdetail-img')) {
    const thumb = group.matches('.thumbgrid');
    const sign = group.matches('.sdetail-img');
    const pages = [...group.children].filter(el => el.matches(thumb ? 'a' : sign ? 'img' : 'figure'));
    if (!pages.length) continue;
    if (thumb) {
      for (const a of pages) {
        const img = a.querySelector('img[src*="/thumbs/figs/"]');
        if (img) img.dataset.fullScan = img.getAttribute('src').replace('/thumbs/figs/','/figs/');
      }
    }
    if (pages.length === 1 && !sign) {
      const img=pages[0].querySelector('img[data-full-scan]');
      if (img) img.src=img.dataset.fullScan;
    }
    if (pages.length < 2) continue;
    group.classList.add('sheet-deck');
    const ids = pages.map((p,i) => {
      const id = p.querySelector('[id]')?.id || p.id;
      if (id) return id;
      p.id = 'sheet-view-'+(viewers.length+1)+'-'+(i+1);
      return p.id;
    });
    viewer(pages,pages.map((p,i)=>p.querySelector('figcaption,span:not([id])')?.textContent.trim() || 'Sheet '+(i+1)),ids);
  }

  function reveal(scroll) {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    for (const {pages,show} of viewers) {
      const n = pages.findIndex(p => p === target || p.contains(target));
      if (n >= 0) show(n);
    }
    const details = target.closest('details');
    if (details) details.open = true;
    if (scroll && target.closest('.sheet-frame')) target.scrollIntoView({block:'start'});
  }
  window.addEventListener('hashchange',()=>reveal(true));
  reveal(true);
})();
