// Perilaku halaman: tirai pembuka, teka-teki bata kunci, gulir halus, muncul saat digulir, menara terkunci,
// QRIS, tooltip. Adegan 3D dimuat terpisah (kingdom.js); bila gagal, halaman tetap utuh tanpa 3D.
import { noiseCloud, DARK_PAL } from './cloud.js';
import { drawWall, drawKeyBrick } from './brick.js';

const html = document.documentElement;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const coarse = matchMedia('(pointer: coarse)').matches;
const mobile = coarse || innerWidth < 760;
if (mobile) html.classList.add('lite');

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const dpr = Math.min(devicePixelRatio || 1, 2);

// ------------------------------------------------------------------ tirai pembuka
const veil = $('#veil');
let veilOpened = false;
function openVeil() {
  if (veilOpened) return;
  veilOpened = true;
  veil.classList.add('open');
  setTimeout(() => veil.classList.add('gone'), 3000);
  if (kingdom) kingdom.intro();
}
if (reduced) {
  veil.classList.add('gone');
  veilOpened = true;
} else {
  [11, 23, 37, 41, 53, 67].forEach((seed, i) => {
    const c = noiseCloud(300, 170, seed, DARK_PAL);
    c.className = 'v' + (i + 1);
    veil.appendChild(c);
  });
  setTimeout(openVeil, 2600); // batas atas: jangan pernah menahan halaman
}

// ------------------------------------------------------------------ gulir halus (pelan)
let lenis = null;
if (!reduced && !coarse) {
  import('lenis').then(({ default: Lenis }) => {
    lenis = new Lenis({ lerp: 0.07, smoothWheel: true, wheelMultiplier: 0.9 });
    const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  }).catch(() => { /* gulir bawaan peramban tetap jalan */ });
}
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const el = document.getElementById(a.getAttribute('href').slice(1));
  if (!el) return;
  e.preventDefault();
  if (lenis) lenis.scrollTo(el, { duration: 2.2 });
  else el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
  history.replaceState(null, '', a.getAttribute('href'));
});

// ------------------------------------------------------------------ muncul saat digulir + menu aktif
const io = new IntersectionObserver((ents) => {
  for (const en of ents) if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
}, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
$$('.reveal').forEach((el) => io.observe(el));

const navLinks = new Map($$('.topbar .links a').map((a) => [a.getAttribute('href').slice(1), a]));
const navIO = new IntersectionObserver((ents) => {
  for (const en of ents) {
    if (!en.isIntersecting) continue;
    navLinks.forEach((a) => a.classList.remove('on'));
    const a = navLinks.get(en.target.id);
    if (a) a.classList.add('on');
  }
}, { threshold: 0.45 });
$$('main > section').forEach((s) => navIO.observe(s));

// ------------------------------------------------------------------ toast & tooltip
const toast = $('#toast');
let toastT = 0;
function showToast(htmlText, ms = 4600) {
  toast.innerHTML = htmlText;
  toast.classList.add('show');
  clearTimeout(toastT);
  toastT = setTimeout(() => toast.classList.remove('show'), ms);
}
const tip = $('#tip');
let tipT = 0;
let tipY = 0;
function showTip(info, x, y) {
  if (!info) { tip.classList.remove('show'); return; }
  tip.querySelector('h4').textContent = info.title;
  tip.querySelector('p').textContent = info.text;
  tip.classList.add('show');
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let left = x + 18, top = y + 18;
  if (left + w > innerWidth - 12) left = x - w - 18;
  if (top + h > innerHeight - 12) top = y - h - 18;
  tip.style.left = clamp(left, 12, innerWidth - w - 12) + 'px';
  tip.style.top = clamp(top, 12, innerHeight - h - 12) + 'px';
  tipY = scrollY;
  clearTimeout(tipT);
  tipT = setTimeout(() => tip.classList.remove('show'), 9000);
}
addEventListener('scroll', () => { if (Math.abs(scrollY - tipY) > 140) tip.classList.remove('show'); }, { passive: true });

// ------------------------------------------------------------------ teka-teki bata kunci
const forge = $('#forge');
const wallCv = $('#wall');
const brick = $('#dl');
const brickCv = $('#brickCanvas');
const slotGlow = $('#slotGlow');
let geo = null;
let placed = false;
let pos = { x: 0, y: 0, r: 0 };

function setPos(x, y, r) {
  pos = { x, y, r };
  brick.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) rotate(${r.toFixed(2)}deg)`;
}
let lastAvail = 0;
function layoutForge(force) {
  const avail = forge.parentElement.clientWidth;
  if (!force && Math.abs(avail - lastAvail) < 2) return;
  lastAvail = avail;
  const L = clamp(Math.floor(avail / 4), 64, 124);
  const H = Math.round(L * 0.38);
  geo = drawWall(wallCv, L, H, dpr);
  forge.style.width = geo.W + 'px';
  forge.style.height = geo.Hc + 'px';
  wallCv.style.width = geo.W + 'px';
  wallCv.style.height = geo.Hc + 'px';
  const s = geo.slot;
  brick.style.width = s.w + 'px';
  brick.style.height = s.h + 'px';
  drawKeyBrick(brickCv, s.w, s.h, dpr);
  Object.assign(slotGlow.style, { left: s.x + 'px', top: s.y + 'px', width: s.w + 'px', height: s.h + 'px' });
  brick.style.setProperty('--lf', clamp(Math.round(s.h * 0.4), 12, 18) + 'px');
  $('#dlText').textContent = s.w >= 150 ? 'Download' : 'Unduh';
  brick.classList.remove('anim');
  if (placed) setPos(s.x, s.y, 0); else setPos(geo.rest.x, geo.rest.y, geo.rest.rot);
  // panah petunjuk dari bata tergeletak ke lubang, dan balon perintah di sebelah kiri bata
  const r = geo.rest;
  const guide = $('#guide');
  guide.setAttribute('width', geo.W);
  guide.setAttribute('height', geo.Hc);
  guide.setAttribute('viewBox', `0 0 ${geo.W} ${geo.Hc}`);
  const x0 = r.x + s.w * 0.5, y0 = r.y - 4;
  const x1 = s.x + s.w * 0.5, y1 = s.y + s.h + 6;
  $('#guidePath').setAttribute('d', `M${x0},${y0} Q${x0 + geo.L * 0.2},${(y0 + y1) / 2} ${x1 + geo.L * 0.25},${y1}`);
  Object.assign($('#brickCall').style, { left: '0px', top: r.y - 4 + 'px', width: Math.max(96, r.x - 14) + 'px', minHeight: s.h + 8 + 'px' });
  forge.classList.toggle('tight', r.x < 150);
}
function nearSlot() {
  const s = geo.slot;
  return Math.hypot(pos.x - s.x, pos.y - s.y) < geo.L * 0.45;
}
function dust() {
  const s = geo.slot;
  for (let i = 0; i < 18; i++) {
    const d = document.createElement('i');
    d.className = 'dust';
    const onTop = i % 2 === 0;
    const x = s.x + Math.random() * s.w, y = onTop ? s.y : s.y + s.h;
    d.style.left = x + 'px';
    d.style.top = y + 'px';
    forge.appendChild(d);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      d.style.transform = `translate(${(Math.random() - 0.5) * 70}px, ${(onTop ? -1 : 1) * (14 + Math.random() * 30)}px) scale(${0.4 + Math.random()})`;
      d.style.opacity = '0';
    }));
    setTimeout(() => d.remove(), 1100);
  }
}
function place() {
  if (placed || !geo) return;
  placed = true;
  forge.classList.remove('near');
  forge.classList.add('done');
  brick.classList.add('anim');
  setPos(geo.slot.x, geo.slot.y, 0);
  setTimeout(() => {
    brick.classList.add('placed');
    brick.classList.remove('anim');
    if (!reduced) dust();
    $('#foundPill').classList.add('show');
    $('#forgeHint').textContent = 'Pas! Sekarang klik bata emasnya untuk mengunduh.';
    $('#autoPlace').hidden = true;
    if (kingdom) kingdom.celebrate();
  }, reduced ? 0 : 430);
}
let drag = null;
let swallowClick = false; // klik penutup seretan tidak boleh langsung mengunduh
brick.addEventListener('pointerdown', (e) => {
  swallowClick = !placed && e.button === 0;
  if (!swallowClick) return;
  e.preventDefault();
  brick.setPointerCapture(e.pointerId);
  brick.classList.remove('anim');
  brick.classList.add('drag');
  forge.classList.add('busy');
  drag = { ox: e.clientX - pos.x, oy: e.clientY - pos.y };
});
brick.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const x = clamp(e.clientX - drag.ox, -geo.L * 0.6, geo.W - geo.slot.w + geo.L * 0.6);
  const y = clamp(e.clientY - drag.oy, -geo.H * 2, geo.Hc + geo.H);
  setPos(x, y, pos.r * 0.85);
  forge.classList.toggle('near', nearSlot());
});
const endDrag = (e) => {
  if (!drag) return;
  drag = null;
  setTimeout(() => { swallowClick = false; }, 400);
  brick.classList.remove('drag');
  forge.classList.remove('busy');
  if (brick.hasPointerCapture(e.pointerId)) brick.releasePointerCapture(e.pointerId);
  if (nearSlot()) { place(); return; }
  forge.classList.remove('near');
  brick.classList.add('anim'); // belum pas: bata kembali tergeletak
  setPos(geo.rest.x, geo.rest.y, geo.rest.rot);
};
brick.addEventListener('pointerup', endDrag);
brick.addEventListener('pointercancel', endDrag);
brick.addEventListener('click', (e) => {
  if (swallowClick) { swallowClick = false; e.preventDefault(); return; }
  if (placed) return; // bata sudah terpasang: tautan unduh jalan biasa
  e.preventDefault();
  if (e.detail === 0) place(); // Enter dari keyboard memasang bata dulu
});
brick.addEventListener('focus', () => { if (brick.matches(':focus-visible')) place(); });
$('#autoPlace').addEventListener('click', place);

(document.fonts ? document.fonts.ready : Promise.resolve()).then(() => layoutForge(true));
let rsT = 0;
addEventListener('resize', () => { clearTimeout(rsT); rsT = setTimeout(() => layoutForge(false), 120); });

// ------------------------------------------------------------------ menara terkunci
$$('.locked').forEach((w) => {
  const open = () => {
    w.classList.remove('shake');
    void w.offsetWidth;
    w.classList.add('shake');
    showToast(`🔒 <b>${w.dataset.name}</b> masih terkunci. Pantau <a href="https://github.com/naufaldm7-droid/Gesture-3D-View-" target="_blank" rel="noopener">repo di GitHub</a> biar tahu kapan dibuka.`);
  };
  w.addEventListener('click', open);
  w.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
});

// ------------------------------------------------------------------ QRIS
const qris = $('#qris');
const qsrc = qris.dataset.qris;
if (qsrc) {
  const img = qris.querySelector('img');
  img.addEventListener('error', () => qris.classList.add('empty'));
  img.src = qsrc;
} else {
  qris.classList.add('empty');
}

// ------------------------------------------------------------------ adegan 3D
let kingdom = null;
const UI_SEL = 'a, button, input, summary, details, table, .panel, .forge, .topbar, .tip, .toast, .lead, .hint, h1, h2';
import('./kingdom.js').then((m) => m.start({
  canvas: $('#world'),
  reduced, mobile,
  sections: $$('main > section').map((s) => s.id),
  isUI: (target) => !!(target && target.closest && target.closest(UI_SEL)),
  onPick: showTip,
  onReady: () => {
    html.classList.add('ready3d');
    if (!reduced) setTimeout(openVeil, 400);
  },
})).then((k) => {
  kingdom = k;
  if (veilOpened) k.intro();
}).catch((err) => {
  console.warn('Adegan 3D tidak dimuat, halaman tetap jalan:', err && err.message);
  html.classList.add('no3d');
  openVeil();
});
