// Dinding bata senja digambar di <canvas>: satu lubang di tengah, satu bata kunci tergeletak di atas dinding.
import { mulberry32 } from './cloud.js';

const CLAY = [[128, 64, 44], [142, 74, 50], [112, 56, 40], [150, 84, 56], [100, 50, 38], [134, 70, 52], [120, 72, 54]];

function paintBrick(ctx, x, y, w, h, rnd, color) {
  const c = color || CLAY[Math.floor(rnd() * CLAY.length)];
  const v = 0.82 + rnd() * 0.28;
  ctx.save();
  const ch = Math.min(w, h) * 0.12;
  const cut = () => rnd() * ch;
  ctx.beginPath();
  ctx.moveTo(x + cut(), y); ctx.lineTo(x + w - cut(), y); ctx.lineTo(x + w, y + cut());
  ctx.lineTo(x + w, y + h - cut()); ctx.lineTo(x + w - cut(), y + h); ctx.lineTo(x + cut(), y + h);
  ctx.lineTo(x, y + h - cut()); ctx.lineTo(x, y + cut()); ctx.closePath();
  ctx.fillStyle = `rgb(${(c[0] * v) | 0},${(c[1] * v) | 0},${(c[2] * v) | 0})`;
  ctx.fill();
  ctx.clip();
  // cahaya senja dari kiri atas
  const gr = ctx.createLinearGradient(x, y, x + w * 0.35, y + h);
  gr.addColorStop(0, 'rgba(255,165,95,.30)');
  gr.addColorStop(0.55, 'rgba(0,0,0,0)');
  gr.addColorStop(1, 'rgba(0,0,0,.38)');
  ctx.fillStyle = gr;
  ctx.fillRect(x, y, w, h);
  for (let k = 0; k < 3; k++) {
    const px = x + rnd() * w, py = y + rnd() * h, pr = h * (0.3 + rnd() * 0.6);
    const g = ctx.createRadialGradient(px, py, 0, px, py, pr);
    g.addColorStop(0, rnd() > 0.5 ? 'rgba(30,12,6,.28)' : 'rgba(255,200,150,.12)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(px - pr, py - pr, pr * 2, pr * 2);
  }
  const n = ((w * h) / 7) | 0;
  for (let i = 0; i < n; i++) {
    ctx.fillStyle = rnd() > 0.5 ? `rgba(255,214,170,${rnd() * 0.13})` : `rgba(18,8,4,${rnd() * 0.24})`;
    ctx.fillRect(x + rnd() * w, y + rnd() * h, 0.8 + rnd() * 1.6, 0.8 + rnd() * 1.6);
  }
  ctx.fillStyle = 'rgba(255,190,125,.38)';
  ctx.fillRect(x, y, w, Math.max(1, h * 0.06));
  ctx.fillStyle = 'rgba(0,0,0,.5)';
  ctx.fillRect(x, y + h - Math.max(1.5, h * 0.09), w, h);
  ctx.fillStyle = 'rgba(0,0,0,.32)';
  ctx.fillRect(x + w - Math.max(1.5, w * 0.02), y, w, h);
  ctx.restore();
}

function mortar(ctx, x, y, w, h, rnd) {
  ctx.fillStyle = '#2b2019';
  ctx.fillRect(x, y, w, h);
  const n = ((w * h) / 10) | 0;
  for (let i = 0; i < n; i++) {
    ctx.fillStyle = rnd() > 0.5 ? `rgba(200,170,130,${rnd() * 0.12})` : `rgba(0,0,0,${rnd() * 0.3})`;
    ctx.fillRect(x + rnd() * w, y + rnd() * h, 1.2, 1.2);
  }
}

function moss(ctx, x, y, w, rnd) {
  for (let i = 0; i < w / 3; i++) {
    const px = x + rnd() * w, py = y + rnd() * 4, r = 1.5 + rnd() * 3.5;
    ctx.fillStyle = `rgba(${60 + rnd() * 30 | 0},${80 + rnd() * 40 | 0},${34 + rnd() * 20 | 0},${0.5 + rnd() * 0.4})`;
    ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  }
}

// L = panjang satu bata, H = tinggi satu baris. Dinding rapi 4 baris dengan satu lubang; bata kunci tergeletak
// di tanah di bawah dinding. Kembalikan ukuran, lubang (slot), dan posisi bata tergeletak.
export function drawWall(cv, L, H, dpr, seed = 7) {
  const rnd = mulberry32(seed);
  const W = 4 * L;
  const wallH = 4 * H;
  const groundY = wallH + H * 0.55; // garis tanah tempat bata tergeletak
  const Hc = Math.round(groundY + H * 0.35);
  const m = Math.max(2.5, L * 0.035);
  cv.width = Math.round(W * dpr);
  cv.height = Math.round(Hc * dpr);
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, Hc);
  const slot = { x: L, y: H, w: 2 * L, h: H };
  mortar(ctx, 0, 0, W, wallH, rnd);
  // lubang: ceruk gelap dengan bayangan dalam
  const g = ctx.createLinearGradient(0, slot.y, 0, slot.y + slot.h);
  g.addColorStop(0, '#030201'); g.addColorStop(1, '#170f0b');
  ctx.fillStyle = g;
  ctx.fillRect(slot.x + m / 2, slot.y + m / 2, slot.w - m, slot.h - m);
  ctx.fillStyle = 'rgba(0,0,0,.65)';
  ctx.fillRect(slot.x + m / 2, slot.y + m / 2, slot.w - m, H * 0.2);
  for (let row = 0; row < 4; row++) {
    const y = row * H;
    const off = row % 2 === 0 ? L / 2 : 0;
    for (let x = -off; x < W; x += L) {
      const x0 = Math.max(0, x), x1 = Math.min(W, x + L);
      if (row === 1 && x0 >= L - 1 && x1 <= 3 * L + 1) continue; // lubang (dua bata di baris kedua)
      paintBrick(ctx, x0 + m / 2, y + m / 2, x1 - x0 - m, H - m, rnd);
    }
  }
  moss(ctx, 0, -1, W, rnd);
  const kw = slot.w - m, kh = slot.h - m;
  // tanah & bayangan tempat bata tergeletak
  const rx = W - kw - L * 0.12;
  const sh = ctx.createRadialGradient(rx + kw / 2, groundY, 2, rx + kw / 2, groundY, kw * 0.62);
  sh.addColorStop(0, 'rgba(0,0,0,.55)'); sh.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = sh;
  ctx.fillRect(rx - kw * 0.2, groundY - H * 0.5, kw * 1.4, H);
  return {
    W, Hc, L, H, m,
    slot: { x: slot.x + m / 2, y: slot.y + m / 2, w: kw, h: kh },
    rest: { x: rx, y: groundY - kh, rot: -1.5 },
  };
}

// Bata kunci: tanah liat lebih gelap dengan ukiran rune samar.
export function drawKeyBrick(cv, w, h, dpr) {
  const rnd = mulberry32(99);
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(h * dpr);
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  paintBrick(ctx, 0, 0, w, h, rnd, [176, 98, 50]);
  ctx.save();
  ctx.strokeStyle = 'rgba(255,214,140,.75)';
  ctx.lineWidth = 1.2;
  ctx.lineCap = 'round';
  for (const cx of [h * 0.6, w - h * 0.6]) {
    ctx.beginPath(); ctx.arc(cx, h / 2, h * 0.26, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, h * 0.24); ctx.lineTo(cx, h * 0.76); ctx.moveTo(cx - h * 0.2, h / 2); ctx.lineTo(cx + h * 0.2, h / 2); ctx.stroke();
  }
  ctx.restore();
}
