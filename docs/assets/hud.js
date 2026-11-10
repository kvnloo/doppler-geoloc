// Shared page behaviour: theme toggle (button or "t"), scroll reveal, CSS token reader.
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
(() => {
  const root = document.documentElement, KEY = 'dg.theme';
  const set = t => { root.dataset.theme = t; localStorage.setItem(KEY, t);
    document.querySelectorAll('.theme').forEach(b => b.textContent = t === 'dark' ? 'light' : 'dark');
    dispatchEvent(new Event('themechange')); };
  document.querySelectorAll('.theme').forEach(b => {
    b.textContent = root.dataset.theme === 'dark' ? 'light' : 'dark';
    b.onclick = () => set(root.dataset.theme === 'dark' ? 'light' : 'dark'); });
  addEventListener('keydown', e => {
    if (e.key === 't' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !e.metaKey && !e.ctrlKey)
      set(root.dataset.theme === 'dark' ? 'light' : 'dark'); });
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('on'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -8% 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
})();
