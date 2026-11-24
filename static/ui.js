// Small, original SVG icon set. No remote scripts or icon font requests.
const iconPaths = {
  check: '<path d="m5 12 4 4L19 6"/>',
  space: '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6M7 12h10m-4-4 4 4-4 4"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
  file: '<path d="M14 2H5v20h14V7zM14 2v5h5M8 12h8m-8 4h6"/>',
  link: '<path d="m10 13 4-4m-6 7-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1" transform="translate(0 -1)"/>',
  text: '<path d="M4 5h16M4 10h16M4 15h10M4 20h7"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  users: '<circle cx="9" cy="7" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3m0-17a3 3 0 0 1 0 6m3 4a6 6 0 0 1 3 5v2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
  shield: '<path d="m12 2 8 3v6c0 6-8 11-8 11S4 17 4 11V5zM8 11l3 3 5-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
  laptop: '<rect x="4" y="3" width="16" height="13" rx="2"/><path d="m4 16-3 4h22l-3-4"/>',
  phone: '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4"/>',
  refresh: '<path d="M20 8a9 9 0 1 0 1 8M20 2v6h-6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
  logout: '<path d="M9 3H3v18h6m0-9h12m-5-5 5 5-5 5"/>',
};
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('icon');
  svg.innerHTML = iconPaths[name] || iconPaths.file;
  return svg;
}
function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach(el => el.replaceChildren(icon(el.dataset.icon)));
}
function formatBytes(size) {
  if (size < 1000) return `${size} B`;
  const unit = size < 1e6 ? 'KB' : size < 1e9 ? 'MB' : 'GB';
  return `${(size / (unit === 'KB' ? 1e3 : unit === 'MB' ? 1e6 : 1e9)).toFixed(1)} ${unit}`;
}
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('netdrop-theme', theme); } catch (_) { /* Storage may be disabled. */ }
  document.getElementById('theme-toggle').setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
}
function motion(element, frames, duration = 180) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return Promise.resolve();
  return element.animate(frames, {duration, easing:'cubic-bezier(.2,.7,.2,1)'}).finished.catch(() => {});
}
async function dismissDialog(dialog) {
  if (dialog.dataset.closing) return;
  dialog.dataset.closing = 'true';
  await motion(dialog, [{opacity:1, transform:'translateY(0)'}, {opacity:0, transform:'translateY(8px)'}]);
  dialog.close();
  delete dialog.dataset.closing;
}
document.addEventListener('DOMContentLoaded', () => {
  hydrateIcons();
  let theme = 'dark';
  try { theme = localStorage.getItem('netdrop-theme') || theme; } catch (_) {}
  setTheme(theme === 'light' ? 'light' : 'dark');
  document.getElementById('theme-toggle').onclick = () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  document.querySelectorAll('[data-dialog]').forEach(button => button.onclick = () => document.getElementById(button.dataset.dialog).showModal());
  document.querySelectorAll('[data-dismiss]').forEach(button => button.onclick = () => dismissDialog(button.closest('dialog')));
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('cancel', event => { event.preventDefault(); dismissDialog(dialog); }));
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => { if (event.target === dialog && (event.clientX < dialog.getBoundingClientRect().left || event.clientX > dialog.getBoundingClientRect().right || event.clientY < dialog.getBoundingClientRect().top || event.clientY > dialog.getBoundingClientRect().bottom)) dismissDialog(dialog); }));
  document.querySelectorAll('[data-room-action]').forEach(button => button.onclick = () => {
    setRoomAction(button.dataset.roomAction);
    document.getElementById('lobby').scrollIntoView({block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    document.getElementById(button.dataset.roomAction === 'create' ? 'room-name' : 'room-id').focus({preventScroll:true});
  });
  document.querySelectorAll('[data-network-device]').forEach(button => button.onclick = () => {
    document.querySelectorAll('[data-network-device]').forEach(el => el.setAttribute('aria-pressed', String(el === button)));
    document.getElementById('network-caption').textContent = `${button.dataset.networkDevice} · Share through your browser`;
  });
});
