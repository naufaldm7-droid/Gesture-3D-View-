// Awan gaya anime digambar di <canvas>: dipakai oleh awan yang bisa digeser (DOM) dan awan 3D (sprite).
// Tidak ada gambar eksternal, jadi halaman tetap ringan.

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

export function cloudCanvas(w, h, seed, o) {
  const cv = document.createElement('canvas');
  cv.width = w;
  cv.height = h;
  return drawCloud(cv, seed, o);
}
