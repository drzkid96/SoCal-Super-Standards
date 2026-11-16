// Hover / focus previews for sign codes (a.sref) and keyboard helpers.
(() => {
  const tip = document.createElement('div');
  tip.className = 'sref-tip';
  tip.innerHTML = '<img alt=""><span></span>';
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(tip));
  let cur = null;
  function show(a) {
    cur = a;
    tip.querySelector('img').src = a.dataset.svg;
    tip.querySelector('span').textContent = a.textContent;
    const r = a.getBoundingClientRect();
    const top = r.bottom + 8 + 170 > innerHeight ? r.top - 178 : r.bottom + 8;
    tip.style.left = Math.min(innerWidth - 180, Math.max(8, r.left + r.width / 2 - 85)) + 'px';
    tip.style.top = top + 'px';
    tip.classList.add('on');
  }
  function hide() { cur = null; tip.classList.remove('on'); }
  document.addEventListener('mouseover', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a) show(a); else if (cur) hide(); });
  document.addEventListener('focusin', (e) => { const a = e.target.closest && e.target.closest('a.sref'); if (a) show(a); });
  document.addEventListener('scroll', hide, { passive: true });
  // back-to-top button and reading progress
  document.addEventListener('DOMContentLoaded', () => {
    const b = document.createElement('button');
    b.className = 'to-top'; b.type = 'button'; b.setAttribute('aria-label', 'Back to top'); b.textContent = 'Top';
    b.onclick = () => scrollTo({ top: 0, behavior: 'smooth' });
    document.body.appendChild(b);
    const bar = document.createElement('div'); bar.className = 'read-bar'; document.body.appendChild(bar);
    addEventListener('scroll', () => {
      const h = document.documentElement; const p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
      bar.style.transform = `scaleX(${p})`; b.classList.toggle('show', h.scrollTop > 600);
    }, { passive: true });
  });
})();
