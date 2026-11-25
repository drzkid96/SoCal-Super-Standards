(() => {
  const base = '/SoCal-Super-Standards/';
  const path = location.pathname;
  if (!path.startsWith(base)) return;
  try {
    const key = 'sss-recent-pages';
    const saved = JSON.parse(localStorage.getItem(key) || '[]');
    const pages = Array.isArray(saved) ? saved.filter(item =>
      typeof item?.title === 'string' && typeof item.path === 'string' &&
      item.path.startsWith(base) && new URL(item.path, location.origin).origin === location.origin
    ).slice(0, 5) : [];
    const section = document.getElementById('recent-standards');
    if (section) {
      for (const item of pages) {
        const link = document.createElement('a');
        link.href = item.path;
        link.textContent = item.title;
        section.querySelector('.recent-entries').append(link);
      }
      section.hidden = !pages.length;
    } else if (path !== base && !path.startsWith(base + 's/') && document.querySelector('main h1')) {
      const title = document.querySelector('main h1').textContent.trim();
      localStorage.setItem(key, JSON.stringify([{title, path}, ...pages.filter(p => p.path !== path)].slice(0, 5)));
    }
  } catch { /* Browsing still works with unavailable storage. */ }
})();
