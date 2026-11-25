// Pemilih aplikasi di logo mahkota + kartu apresiasi kecil yang melayang.
// Dipakai semua halaman kerajaan (Gesture Control, Steel Kit, dan aplikasi berikutnya).
// Menambah aplikasi baru: cukup tambahkan satu baris di APPS.

const ICON = {
  crown: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M4 26h24l-2-14-5 5-5-11-5 11-5-5z" fill="#e0a94a" stroke="#ffe7a8" stroke-width="1.2" stroke-linejoin="round"/><circle cx="16" cy="4" r="2" fill="#ffe7a8"/></svg>',
  beam: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 2l12 7v14l-12 7-12-7V9z" fill="#e0a94a" stroke="#ffe7a8" stroke-width="1.2" stroke-linejoin="round"/><path d="M10 9h12v3h-4.5v8H22v3H10v-3h4.5v-8H10z" fill="#2a1606"/></svg>',
  anvil: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 11h18c0 4 4 4 4 4v2H19l-2 4h3v4H10v-4h3l-2-4H5z" fill="#6a5a48" stroke="#9a8670" stroke-width="1.2" stroke-linejoin="round"/></svg>',
};

// href relatif terhadap akar situs
export const APPS = [
  { id: 'gesture', name: 'Gesture Control', desc: 'Kendalikan AutoCAD dengan gerakan tangan', href: '', icon: ICON.crown },
  { id: 'steelkit', name: 'Steel Kit', desc: 'Profil, sambungan & rangka baja untuk AutoCAD', href: 'steelkit/', icon: ICON.beam },
  { id: 'soon', name: 'Segera hadir', desc: 'Aplikasi berikutnya sedang ditempa…', soon: true, icon: ICON.anvil },
];

/**
 * Logo mahkota jadi tombol: klik -> jendela kecil di bawah logo berisi daftar aplikasi.
 * @param {{crest: HTMLElement, current: string, base: string, go?: (app) => boolean|void}} o
 *   base = jalur ke akar situs ('' di halaman Gesture, '../' di halaman Steel Kit).
 *   go(app) boleh menangani perpindahan sendiri (mis. terbang masuk gerbang); kembalikan true bila sudah ditangani.
 */
export function mountAppSwitcher(o) {
  const crest = o.crest;
  if (!crest || crest.dataset.switcher) return;
  crest.dataset.switcher = '1';
  crest.setAttribute('aria-haspopup', 'menu');
  crest.setAttribute('aria-expanded', 'false');
  crest.insertAdjacentHTML('beforeend', '<i class="caret" aria-hidden="true">▾</i>');
  const menu = document.createElement('div');
  menu.className = 'app-menu';
  menu.setAttribute('role', 'menu');
  menu.innerHTML = '<div class="app-menu-title">Pilih aplikasi</div>' + APPS.map((a) =>
    `<button type="button" role="menuitem" class="app-item${a.id === o.current ? ' on' : ''}${a.soon ? ' soon' : ''}" data-app="${a.id}"${a.soon ? ' disabled' : ''}>
      <span class="app-ico">${a.icon}</span><span class="app-txt"><b>${a.name}</b><small>${a.desc}</small></span>${a.id === o.current ? '<em>di sini</em>' : ''}
    </button>`).join('');
  crest.parentElement.appendChild(menu);
  const set = (open) => {
    menu.classList.toggle('open', open);
    crest.setAttribute('aria-expanded', String(open));
    if (open) (menu.querySelector('.app-item.on') || menu.querySelector('.app-item')).focus({ preventScroll: true });
  };
  crest.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); set(!menu.classList.contains('open')); });
  document.addEventListener('click', (e) => { if (!menu.contains(e.target)) set(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') set(false); });
  menu.addEventListener('click', (e) => {
    const b = e.target.closest('.app-item');
    if (!b || b.disabled) return;
    const app = APPS.find((a) => a.id === b.dataset.app);
    set(false);
    if (o.go && o.go(app)) return;
    if (app.id === o.current) { window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    location.href = (o.base || '') + app.href;
  });
}

/**
 * Kartu apresiasi kecil yang melayang di atas (di bawah bilah menu). Klik -> gulir ke bagian apresiasi.
 * Disembunyikan selama intro dan saat bagian apresiasi sudah terlihat.
 */
export function mountAppreciationHook(o) {
  const target = document.querySelector(o.target || '#apresiasi');
  if (!target) return null;
  const hook = document.createElement('button');
  hook.type = 'button';
  hook.className = 'appre-hook';
  hook.innerHTML = '<span class="qr" aria-hidden="true"></span><span><b>Suka aplikasinya?</b><small>Kirim apresiasi lewat QRIS</small></span>';
  document.body.appendChild(hook);
  hook.addEventListener('click', () => (o.scrollTo ? o.scrollTo(target) : target.scrollIntoView({ behavior: 'smooth' })));
  new IntersectionObserver((es) => es.forEach((e) => hook.classList.toggle('away', e.isIntersecting)), { threshold: 0.15 }).observe(target);
  return { show(v) { hook.classList.toggle('hidden', !v); } };
}
