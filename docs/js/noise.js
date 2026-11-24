// Noise nilai 2D yang bisa berulang (tileable) + fbm, dan pembuat normal map dari peta tinggi.
// Dipakai untuk tekstur batu, atap, tebing, awan, dan kabut. Semua dibangkitkan di peramban, tanpa gambar eksternal.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function makeNoise(seed) {
  const r = mulberry32(seed * 977 + 3);
  const P = new Uint8Array(512);
  const V = new Float32Array(256);
  for (let i = 0; i < 256; i++) { P[i] = i; V[i] = r(); }
  for (let i = 255; i > 0; i--) { const j = Math.floor(r() * (i + 1)); const t = P[i]; P[i] = P[j]; P[j] = t; }
  for (let i = 0; i < 256; i++) P[i + 256] = P[i];
  const h = (x, y) => V[P[P[x & 255] + (y & 255)]];
  // n(x, y, px, py): px/py = periode (bilangan bulat) supaya tekstur menyambung di tepi; 0 = tanpa periode
  function n(x, y, px = 0, py = 0) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    let x0 = xi, y0 = yi, x1 = xi + 1, y1 = yi + 1;
    if (px) { x0 = ((x0 % px) + px) % px; x1 = (x0 + 1) % px; }
    if (py) { y0 = ((y0 % py) + py) % py; y1 = (y0 + 1) % py; }
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = h(x0, y0), b = h(x1, y0), c = h(x0, y1), d = h(x1, y1);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  }
  // fbm dengan frekuensi dasar f (sel per tekstur) -> berulang mulus bila tile = true
  function fbm(x, y, f, oct = 4, tile = true, gain = 0.5) {
    let s = 0, a = 0.5, norm = 0, ff = f;
    for (let o = 0; o < oct; o++) {
      s += a * n(x * ff, y * ff, tile ? ff : 0, tile ? ff : 0);
      norm += a; a *= gain; ff *= 2;
    }
    return s / norm;
  }
  // fbm dengan frekuensi berbeda per sumbu (untuk lapisan batuan, guratan kayu)
  function fbm2(x, y, fx, fy, oct = 4) {
    let s = 0, a = 0.5, norm = 0;
    for (let o = 0; o < oct; o++) {
      s += a * n(x * fx, y * fy, fx, fy);
      norm += a; a *= 0.5; fx *= 2; fy *= 2;
    }
    return s / norm;
  }
  return { n, fbm, fbm2 };
}

// Peta tinggi (Float32Array, 0..1) -> normal map RGB (tangent space), dibungkus di tepi.
export function normalFromHeight(hgt, w, h, strength) {
  const out = new Uint8ClampedArray(w * h * 4);
  const at = (x, y) => hgt[((y + h) % h) * w + ((x + w) % w)];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const dx = (at(x + 1, y - 1) + 2 * at(x + 1, y) + at(x + 1, y + 1)) - (at(x - 1, y - 1) + 2 * at(x - 1, y) + at(x - 1, y + 1));
      const dy = (at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1)) - (at(x - 1, y - 1) + 2 * at(x, y - 1) + at(x + 1, y - 1));
      let nx = -dx * strength, ny = dy * strength, nz = 1;
      const l = Math.hypot(nx, ny, nz);
      nx /= l; ny /= l; nz /= l;
      const i = (y * w + x) * 4;
      out[i] = (nx * 0.5 + 0.5) * 255;
      out[i + 1] = (ny * 0.5 + 0.5) * 255;
      out[i + 2] = (nz * 0.5 + 0.5) * 255;
      out[i + 3] = 255;
    }
  }
  return out;
}

export function toCanvas(rgba, w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  c.getContext('2d').putImageData(new ImageData(rgba, w, h), 0, 0);
  return c;
}
