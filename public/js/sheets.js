// Multi-sheet viewer for standard drawings, multi-page chapter sheets, and multi-sheet MUTCD figures.
// Preserves full printability and keeps multi-item visual galleries (.mfig-grid, .mgrid, .thumbgrid) as browsable grids.
(() => {
  const article = document.querySelector('.sl-markdown-content');
  if (!article) return;

  const viewers = [];
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  function getThumbSrc(frame) {
    const img = frame.querySelector('img');
    if (!img) return '';
    return img.getAttribute('src') || img.currentSrc || '';
  }

  function shortLabel(full, idx) {
    const m = full.match(/Sheet\s+(\d+)\s+of\s+\d+/i);
    if (m) return 'Sheet ' + m[1];
    const p = full.match(/Page\s+(\d+)/i);
    if (p) return 'p. ' + p[1];
    const pg = full.match(/\bp\s*(\d+)\b/i);
    if (pg) return 'Sheet ' + (idx + 1) + ' · p.' + pg[1];
    return 'Sheet ' + (idx + 1);
  }

  function buildViewer(container, pages, labels, ids, opts = {}) {
    if (pages.length < 2) return;
    const compact = Boolean(opts.compact);

    const wrap = el('div', 'sss-ms-wrap' + (compact ? ' is-compact' : ''));
    const bar = el('nav', 'sheet-controls not-content');
    bar.setAttribute('aria-label', 'Multi-sheet navigation');

    const prev = el('button', 'sc-btn sc-prev', '‹ Prev');
    prev.type = 'button';
    const badge = el('span', 'sc-badge');
    badge.setAttribute('aria-live', 'polite');
    const next = el('button', 'sc-btn sc-next', 'Next ›');
    next.type = 'button';

    const select = el('select', 'sc-select');
    select.setAttribute('aria-label', 'Select sheet');
    labels.forEach((lbl, i) => {
      const clean = lbl.length > 90 ? lbl.slice(0, 87) + '…' : lbl;
      select.add(new Option(clean || 'Sheet ' + (i + 1), String(i)));
    });

    const toggleAll = el('button', 'sc-btn sc-mode', compact ? 'Grid View' : 'All Sheets');
    toggleAll.type = 'button';
    toggleAll.setAttribute('aria-pressed', 'false');

    const zoomBtn = el('button', 'sc-btn sc-zoom', 'Zoom ⤢');
    zoomBtn.type = 'button';
    zoomBtn.title = 'Open active sheet in fullscreen zoom viewer';

    bar.append(prev, badge, next, select, toggleAll, zoomBtn);

    // Filmstrip of clickable thumbnails (up to 32 sheets)
    let strip = null;
    const thumbs = [];
    if (pages.length <= 32) {
      strip = el('div', 'sheet-strip not-content');
      strip.setAttribute('role', 'tablist');
      strip.setAttribute('aria-label', 'Sheet thumbnails');
      pages.forEach((p, i) => {
        const btn = el('button', 'sc-thumb');
        btn.type = 'button';
        btn.setAttribute('role', 'tab');
        btn.title = labels[i] || 'Sheet ' + (i + 1);
        const src = getThumbSrc(p);
        if (src) {
          const im = document.createElement('img');
          im.src = src;
          im.alt = shortLabel(labels[i] || '', i);
          im.loading = 'lazy';
          btn.append(im);
        }
        btn.append(el('span', '', shortLabel(labels[i] || '', i)));
        btn.addEventListener('click', () => {
          if (showAll) setAll(false);
          show(i, true);
        });
        strip.append(btn);
        thumbs.push(btn);
      });
    }

    const stage = el('div', 'sheet-stage');
    pages[0].before(wrap);
    wrap.append(bar);
    if (strip) wrap.append(strip);
    wrap.append(stage);
    pages.forEach((p) => {
      p.classList.add('sheet-frame');
      stage.append(p);
    });

    let index = 0;
    let showAll = false;

    const upgradeActiveScan = (frame) => {
      frame.querySelectorAll('img[data-full-scan]').forEach((img) => {
        if (img.dataset.fullScan) {
          img.src = img.dataset.fullScan;
          delete img.dataset.fullScan;
        }
      });
    };

    const show = (i, updateHash = false) => {
      if (i < 0 || i >= pages.length) return;
      index = i;
      if (!showAll) {
        pages.forEach((p, n) => { p.hidden = n !== i; });
      }
      upgradeActiveScan(pages[i]);
      select.selectedIndex = i;
      prev.disabled = !showAll && i === 0;
      next.disabled = !showAll && i === pages.length - 1;
      badge.textContent = showAll ? `${pages.length} sheets` : `${i + 1} / ${pages.length}`;
      thumbs.forEach((t, n) => {
        const active = !showAll && n === i;
        t.classList.toggle('is-active', active);
        t.setAttribute('aria-selected', String(active));
      });
      if (thumbs[i] && !showAll) {
        try { thumbs[i].scrollIntoView({ inline: 'nearest', block: 'nearest' }); } catch {}
      }
      if (updateHash && ids[i]) {
        history.replaceState(history.state, '', '#' + encodeURIComponent(ids[i]));
      }
    };

    const setAll = (all) => {
      showAll = all;
      wrap.classList.toggle('is-all', all);
      toggleAll.setAttribute('aria-pressed', String(all));
      toggleAll.textContent = all ? 'Single Sheet' : (compact ? 'Grid View' : 'All Sheets');
      if (all) {
        pages.forEach((p) => { p.hidden = false; upgradeActiveScan(p); });
        prev.disabled = true;
        next.disabled = true;
        badge.textContent = `${pages.length} sheets`;
        thumbs.forEach((t) => { t.classList.remove('is-active'); t.setAttribute('aria-selected', 'false'); });
      } else {
        show(index, false);
      }
    };

    prev.onclick = () => { if (showAll) setAll(false); show(index - 1, true); };
    next.onclick = () => { if (showAll) setAll(false); show(index + 1, true); };
    select.onchange = () => { if (showAll) setAll(false); show(select.selectedIndex, true); };
    toggleAll.onclick = () => setAll(!showAll);
    zoomBtn.onclick = () => {
      const targetImg = pages[index]?.querySelector('figure.dfig img, figure.mfig img, img');
      if (targetImg) targetImg.click();
    };

    if (container) container.classList.add('sheet-deck');
    viewers.push({ pages, show, setAll });
    show(0, false);
  }

  // 1. Multi-sheet detail & chapter pages (### Sheet X of Y or ### Page N with figure.dfig)
  const heads = [...article.children].filter(
    (e) => /^H[23]$/.test(e.tagName) && /^(Sheet \d+ of \d+|Page \d+\b)/i.test(e.textContent.trim())
  );
  if (heads.length > 1 && article.querySelector('figure.dfig')) {
    const starts = heads.map((h) =>
      h.previousElementSibling?.matches('p:has(> .anchor:only-child), span.anchor')
        ? h.previousElementSibling
        : h
    );
    const frames = starts.map((start, i) => {
      const frame = el('section');
      start.before(frame);
      let cur = start;
      while (cur && cur !== starts[i + 1]) {
        if (cur !== start && cur !== heads[i] && cur.matches('h2,h3,.xidx-wrap,.tsigns,nav,section')) break;
        const after = cur.nextElementSibling;
        frame.append(cur);
        cur = after;
      }
      return frame;
    });
    const labels = heads.map((h) => h.textContent.trim());
    const ids = heads.map((h, i) => frames[i].querySelector('.anchor[id],figure[id]')?.id || h.id || 'sheet-' + (i + 1));
    buildViewer(null, frames, labels, ids, { compact: false });
    document.querySelectorAll('.sss-sheetbar').forEach((b) => b.remove());
    document.documentElement.classList.add('has-sheet-deck');
  }

  // 2. Multi-sheet inline MUTCD figures (.mfig-inline.multi) & multi-sheet sign details (.sdetail-img)
  for (const group of article.querySelectorAll('.mfig-inline.multi, .sdetail-img')) {
    const isSign = group.matches('.sdetail-img');
    const pages = [...group.children].filter((c) => c.matches(isSign ? 'img' : 'figure'));
    if (pages.length < 2) continue;
    const ids = pages.map((p, i) => {
      const id = p.querySelector('[id]')?.id || p.id;
      if (id) return id;
      p.id = 'sheet-view-' + (viewers.length + 1) + '-' + (i + 1);
      return p.id;
    });
    const labels = pages.map((p, i) =>
      p.querySelector('figcaption')?.textContent.trim() || p.getAttribute('alt') || 'Sheet ' + (i + 1)
    );
    buildViewer(group, pages, labels, ids, { compact: true });
  }

  function reveal(scroll) {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    for (const { pages, show, setAll } of viewers) {
      const n = pages.findIndex((p) => p === target || p.contains(target));
      if (n >= 0) {
        setAll(false);
        show(n, false);
      }
    }
    const details = target.closest('details');
    if (details) details.open = true;
    if (scroll && target.closest('.sheet-frame')) {
      target.scrollIntoView({ block: 'start' });
    }
  }
  window.addEventListener('hashchange', () => reveal(true));
  reveal(true);
})();
