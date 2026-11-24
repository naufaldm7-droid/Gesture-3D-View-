// Awan gaya anime digambar di <canvas>: dipakai oleh awan yang bisa digeser (DOM) dan awan 3D (sprite).
// Tidak ada gambar eksternal, jadi halaman tetap ringan.
import { makeNoise } from './noise.js';

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Gambar satu awan cumulus: bayangan lembayung di bawah, badan putih, kilau hangat di kiri atas, dasar rata.
export function drawCloud(cv, seed, o = {}) {
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  const rnd = mulberry32(seed * 7919 + 13);
  const shade = o.shade || '200,204,242';
  const light = o.light || '255,255,255';
  const rim = o.rim || '255,236,214';
  ctx.clearRect(0, 0, W, H);

  const puffs = [];
  const baseY = H * 0.8;
  const n = 6 + Math.floor(rnd() * 4);
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    const bell = Math.sin(Math.PI * t);
    const rad = H * (0.13 + 0.15 * bell) * (0.85 + 0.3 * rnd());
    const x = W * (0.13 + 0.74 * t);
    const y = baseY - rad * 0.55 - bell * H * 0.16 * rnd();
    puffs.push({ x, y, rad });
  }
  const m = 2 + Math.floor(rnd() * 3);
  for (let i = 0; i < m; i++) {
    const x = W * (0.32 + 0.36 * rnd());
    const rad = H * (0.17 + 0.1 * rnd());
    const y = baseY - H * 0.3 - rnd() * H * 0.08;
    puffs.push({ x, y, rad });
  }

  const blob = (x, y, r, rgb, a, soft) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rgb},${a})`);
    g.addColorStop(soft, `rgba(${rgb},${a})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  };
  const s1 = o.soft1 === undefined ? 0.84 : o.soft1, s2 = o.soft2 === undefined ? 0.8 : o.soft2;
  const rimA = o.rimA === undefined ? 0.55 : o.rimA, rimX = o.rimX === undefined ? -0.3 : o.rimX;
  for (const p of puffs) blob(p.x, p.y + p.rad * 0.12, p.rad, shade, 1, s1);
  for (const p of puffs) blob(p.x - p.rad * 0.05, p.y - p.rad * 0.13, p.rad * 0.88, light, 1, s2);
  for (const p of puffs) blob(p.x + p.rad * rimX, p.y - p.rad * 0.38, p.rad * 0.55, rim, rimA, 0.2);

  // dasar rata khas awan cumulus
  ctx.globalCompositeOperation = 'destination-out';
  const g = ctx.createLinearGradient(0, baseY - H * 0.04, 0, baseY + H * 0.05);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,0,0,1)');
  ctx.fillStyle = g;
  ctx.fillRect(0, baseY - H * 0.04, W, H);
  ctx.globalCompositeOperation = 'source-over';
  return cv;
}

// Palet awan senja: badan gelap keunguan, tepi atas tersulut matahari jingga.
export const DUSK = { shade: '20,12,14', light: '66,40,38', rim: '255,140,70', soft1: 0.55, soft2: 0.5, rimA: 0.5 };
export const DUSK_LIT = { shade: '40,22,22', light: '122,62,44', rim: '255,178,96', soft1: 0.55, soft2: 0.5, rimA: 0.75, rimX: 0.1 };

// Awan "volumetrik" palsu: kerapatan dari gumpalan + noise fbm (tepi berserabut), lalu diterangi dengan
// menghitung kerapatan ke arah cahaya (bayangan diri). Jauh lebih nyata dibanding gumpalan lingkaran.
export const DARK_PAL = { shade: [16, 11, 15], light: [96, 60, 54], rim: [255, 146, 78], rimA: 0.55, lx: -0.35, ly: -1, k: 2.2 };
export const LIT_PAL = { shade: [44, 24, 26], light: [196, 104, 62], rim: [255, 196, 120], rimA: 0.9, lx: -0.2, ly: -1, k: 1.6 };
export const FOG_PAL = { shade: [52, 38, 44], light: [118, 88, 86], rim: [0, 0, 0], rimA: 0, lx: 0, ly: -1, k: 1.2, mist: true };
export function noiseCloud(w, h, seed, pal) {
  const nz = makeNoise(seed);
  const rnd = mulberry32(seed * 31 + 7);
  const puffs = [];
  const baseY = pal.mist ? 0.62 : 0.78;
  const n = pal.mist ? 5 : 7 + Math.floor(rnd() * 4);
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n, bell = Math.sin(Math.PI * t);
    const r = pal.mist ? 0.2 + rnd() * 0.1 : (0.12 + 0.17 * bell) * (0.8 + 0.4 * rnd());
    puffs.push({ x: 0.12 + 0.76 * t + (rnd() - 0.5) * 0.06, y: baseY - r * (pal.mist ? 0.3 : 0.6) - bell * 0.1 * rnd(), r });
  }
  const asp = w / h;
  const D = new Float32Array(w * h);
  for (let y = 0; y < h; y++) {
    const v = y / h;
    for (let x = 0; x < w; x++) {
      const u = x / w;
      let s = 0;
      for (const p of puffs) {
        const dx = (u - p.x) * asp * (pal.mist ? 0.35 : 0.56), dy = v - p.y;
        const q = 1 - Math.sqrt(dx * dx + dy * dy) / p.r;
        if (q > s) s = q;
      }
      if (s <= -0.3) continue;
      const f = nz.fbm(u * asp * 0.5, v, 3, 5, false);
      let d = s * 1.7 - 0.15 + (f - 0.5) * 1.3;
      if (!pal.mist) d *= Math.min(1, Math.max(0, (baseY + 0.04 - v) / 0.1)); // dasar rata
      else d *= Math.min(1, Math.max(0, (0.95 - v) / 0.3)) * Math.min(1, v / 0.25);
      D[y * w + x] = Math.max(0, Math.min(1.4, d));
    }
  }
  const img = new Uint8ClampedArray(w * h * 4);
  const sx = pal.lx * w * 0.012, sy = pal.ly * h * 0.02;
  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : D[(y | 0) * w + (x | 0)]);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const d = D[y * w + x];
    const i = (y * w + x) * 4;
    if (d <= 0.02) continue;
    const occ = at(x + sx, y + sy) + at(x + 2 * sx, y + 2 * sy) * 0.8 + at(x + 4 * sx, y + 4 * sy) * 0.6;
    const lit = Math.exp(-pal.k * occ);
    const edge = Math.max(0, 1 - d * 2.2) * lit;
    const c = (a, b, r) => a + (b - a) * lit + r * edge * pal.rimA;
    img[i] = c(pal.shade[0], pal.light[0], pal.rim[0]);
    img[i + 1] = c(pal.shade[1], pal.light[1], pal.rim[1]);
    img[i + 2] = c(pal.shade[2], pal.light[2], pal.rim[2]);
    const al = Math.min(1, Math.max(0, (d - 0.04) / 0.5));
    img[i + 3] = al * al * (3 - 2 * al) * (pal.mist ? 150 : 255);
  }
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  cv.getContext('2d').putImageData(new ImageData(img, w, h), 0, 0);
  return cv;
}

export function cloudCanvas(w, h, seed, o) {
  const cv = document.createElement('canvas');
  cv.width = w;
  cv.height = h;
  return drawCloud(cv, seed, o);
}
