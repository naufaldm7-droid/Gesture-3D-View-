// Steel Kit: aula baja di dalam istana kerajaan Gesture Control.
// Lorong gerbang -> pintu terbuka -> aula berangka portal baja dengan jendela lengkung besar ke dunia senja.
// Di meja: potongan sambungan balok-kolom (H-beam + pelat ujung) yang kurang satu baut. Baut diseret dengan
// kursor ke lubangnya; begitu terpasang, tombol unduh terbuka.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { makeNoise, normalFromHeight, toCanvas } from '../js/noise.js';
import { noiseCloud, DARK_PAL, LIT_PAL, FOG_PAL } from '../js/cloud.js';
import { mountAppSwitcher, mountAppreciationHook } from '../js/apps.js';

const DOWNLOAD = 'https://github.com/naufaldm7-droid/STEEL-KIT/releases/latest/download/SteelKitSetup.exe';
const Q = new URLSearchParams(location.search);
const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
const COARSE = matchMedia('(pointer: coarse)').matches;
const MOBILE = COARSE || innerWidth < 760;
const TEX = MOBILE ? 256 : 512;
const TABLE = new THREE.Vector3(0, 0, -6);
var _thread = null;
const flames = [];
const clamp01 = v => Math.max(0, Math.min(1, v));
const smooth = t => t * t * (3 - 2 * t);
const mix = (a, b, t) => a + (b - a) * t;
const $ = s => document.querySelector(s);

// ------------------------------------------------------------------ gulir halus (sama dengan halaman Gesture)
let lenis = null;
function scrollToEl(el, dur = 2) {
  if (lenis) lenis.scrollTo(el, { duration: dur });
  else el.scrollIntoView({ behavior: REDUCE ? 'auto' : 'smooth' });
}
if (!REDUCE && !COARSE) {
  import('lenis').then(({ default: Lenis }) => {
    lenis = new Lenis({ lerp: 0.08, smoothWheel: true, wheelMultiplier: 0.9 });
    if (introOn) lenis.stop();
    const raf = t => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  }).catch(() => {});
}
document.addEventListener('click', e => {
  const a = e.target.closest('a[href^="#"]');
  if (!a || a.id === 'dl') return;
  const el = document.getElementById(a.getAttribute('href').slice(1));
  if (!el) return;
  e.preventDefault();
  scrollToEl(el, 2.2);
});

// pemilih aplikasi di logo + kartu apresiasi kecil
mountAppSwitcher({
  crest: $('.topbar .crest'), current: 'steelkit', base: '../',
  go: app => { if (app.id === 'steelkit') { scrollToEl($('#masuk'), 1.6); return true; } return false; },
});
mountAppreciationHook({ target: '#apresiasi', scrollTo: el => scrollToEl(el, 2.2) });
{
  const q = $('#qris'), img = q && q.querySelector('img');
  if (img) { img.addEventListener('error', () => q.classList.add('empty')); img.src = q.dataset.qris; }
}

// ------------------------------------------------------------------ renderer (lembut, kualitas menyesuaikan)
const canvas = document.getElementById('world');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !MOBILE, powerPreference: 'high-performance' });
const MAX_PR = Math.min(devicePixelRatio || 1, MOBILE ? 1.4 : 1.75), MIN_PR = MOBILE ? 0.75 : 1;
let pr = MAX_PR;
renderer.setPixelRatio(pr);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.02;
renderer.shadowMap.enabled = !MOBILE;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;             // bayangan dihitung ulang hanya bila ada yang bergerak
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2('#6a3a2c', 0.0022);
const camera = new THREE.PerspectiveCamera(MOBILE ? 58 : 44, 1, 0.05, 2600);
const pmrem = new THREE.PMREMGenerator(renderer);
const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.22, 0.45, 0.9);
if (!MOBILE) composer.addPass(bloom);
composer.addPass(new OutputPass());

// ------------------------------------------------------------------ tekstur prosedural
function proc(size, seed, fn, normalStrength = 2) {
  const N = makeNoise(seed);
  const col = new Uint8ClampedArray(size * size * 4), hgt = new Float32Array(size * size), rough = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const o = fn(x / size, y / size, N), i = y * size + x;
    col[i * 4] = o.c[0]; col[i * 4 + 1] = o.c[1]; col[i * 4 + 2] = o.c[2]; col[i * 4 + 3] = 255;
    hgt[i] = o.h;
    const r = Math.round((o.r ?? 0.8) * 255); rough[i * 4] = rough[i * 4 + 1] = rough[i * 4 + 2] = r; rough[i * 4 + 3] = 255;
  }
  const mk = (cv, srgb) => { const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; if (srgb) t.colorSpace = THREE.SRGBColorSpace; return t; };
  return { map: mk(toCanvas(col, size, size), true), normalMap: mk(toCanvas(normalFromHeight(hgt, size, size, normalStrength), size, size)), roughnessMap: mk(toCanvas(rough, size, size)) };
}
const T = {
  stone: proc(TEX, 11, (u, v, N) => {
    const rows = 8, row = Math.floor(v * rows), off = (row % 2) * 0.5, cu = (u * 4 + off) % 4, cell = Math.floor(cu);
    const fx = cu - cell, fy = v * rows - row;
    const g = N.fbm(u, v, 16, 5), d = N.fbm(u + .3, v, 64, 3), tone = N.n(cell * 7.1 + row * 3.3, row * 1.7) * 0.22 - 0.08;
    if (Math.min(fx, 1 - fx) * 4 < 0.07 || Math.min(fy, 1 - fy) < 0.045) return { c: [70, 60, 52].map(x => x * (0.8 + g * 0.4)), h: 0.05, r: 0.95 };
    const k = 0.78 + tone + g * 0.28 + d * 0.1;
    return { c: [232 * k, 214 * k, 186 * k], h: 0.6 + g * 0.3 + d * 0.15, r: 0.85 };
  }, 3),
  wood: proc(TEX, 7, (u, v, N) => {
    const plank = Math.floor(u * 5), fu = u * 5 - plank, grain = N.fbm2(u * 5 + plank * 0.37, v, 1, 22, 5);
    if (Math.min(fu, 1 - fu) < 0.025) return { c: [22, 13, 8], h: 0, r: 0.8 };
    const k = 0.55 + grain * 0.55 + N.n(plank * 9.1, 3) * 0.18;
    return { c: [96 * k, 58 * k, 34 * k], h: 0.5 + grain * 0.4, r: 0.62 };
  }, 2.2),
  floor: proc(TEX, 3, (u, v, N) => {
    const tu = (u * 2) % 1, tv = (v * 2) % 1, g = N.fbm(u, v, 8, 4), d = N.fbm(u + 2, v, 40, 3);
    if (Math.min(tu, 1 - tu, tv, 1 - tv) < 0.008) return { c: [30, 24, 20], h: 0, r: 0.8 };
    const k = 0.5 + g * 0.3 + d * 0.1;
    return { c: [150 * k, 132 * k, 112 * k], h: 0.5 + g * 0.2, r: 0.42 + d * 0.2 };
  }, 0.8),
  steel: proc(TEX, 5, (u, v, N) => {
    const s = N.fbm2(u, v, 2, 128, 4), w = N.fbm(u, v, 8, 3), k = 0.8 + s * 0.25;
    return { c: [180 * k, 186 * k, 194 * k], h: s * 0.5, r: 0.28 + s * 0.15 + w * 0.08 };
  }, 1.1),
  primer: proc(TEX, 17, (u, v, N) => {
    const g = N.fbm(u, v, 10, 5), s = N.fbm2(u, v, 3, 60, 3), k = 0.78 + g * 0.3;
    return { c: [150 * k, 58 * k, 38 * k], h: g * 0.4 + s * 0.2, r: 0.55 + g * 0.2 };
  }, 1.0),
  rock: proc(TEX, 21, (u, v, N) => {
    const g = N.fbm(u, v, 6, 5), l = N.fbm2(u, v, 2, 14, 4), k = 0.45 + g * 0.4 + l * 0.2;
    return { c: [118 * k, 92 * k, 80 * k], h: g * 0.6 + l * 0.4, r: 0.95 };
  }, 2.5),
  grass: proc(TEX, 9, (u, v, N) => {
    const g = N.fbm(u, v, 6, 5), d = N.fbm(u + 3, v, 32, 3), k = 0.45 + g * 0.5;
    return { c: [mix(52, 74, d) * k, mix(62, 70, g) * k, 36 * k], h: g * 0.6 + d * 0.3, r: 0.95 };
  }, 1.5),
};
function rep(m, x, y) { for (const t of [m.map, m.normalMap, m.roughnessMap]) if (t) t.repeat.set(x, y); return m; }
const std = (c, x = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 1, metalness: 0, ...x });
const M = {
  wall: std('#e8dcc6', { map: T.stone.map, normalMap: T.stone.normalMap, roughnessMap: T.stone.roughnessMap }),
  trim: std('#c8b89c', { map: T.stone.map, normalMap: T.stone.normalMap }),
  floor: new THREE.MeshPhysicalMaterial({ ...T.floor, color: '#ffffff', roughness: 1, clearcoat: 0.35, clearcoatRoughness: 0.35, envMap: envTex, envMapIntensity: 0.35 }),
  wood: std('#ffffff', { ...T.wood, side: THREE.DoubleSide }),
  iron: new THREE.MeshStandardMaterial({ color: '#4a403a', roughness: 0.62, metalness: 0.85, envMap: envTex, envMapIntensity: 0.5 }),
  gold: new THREE.MeshStandardMaterial({ color: '#e0a94a', roughness: 0.3, metalness: 1, envMap: envTex, envMapIntensity: 0.55 }),
  frame: new THREE.MeshStandardMaterial({ color: '#3a3430', roughness: 0.55, metalness: 0.6, envMap: envTex, envMapIntensity: 0.4 }),
  primer: new THREE.MeshStandardMaterial({ ...T.primer, color: '#ffffff', roughness: 1, metalness: 0.3, envMap: envTex, envMapIntensity: 0.4 }),
  galv: new THREE.MeshStandardMaterial({ ...T.steel, color: '#d6dbe0', metalness: 1, roughness: 1, envMap: envTex, envMapIntensity: 0.8 }),
  velvet: std('#6e1414', { roughness: 0.95 }),
  carpet: std('#5a1212', { roughness: 0.98 }),
  rock: std('#ffffff', { map: T.rock.map, normalMap: T.rock.normalMap }),
  grass: std('#ffffff', { map: T.grass.map, normalMap: T.grass.normalMap }),
  glass: new THREE.MeshStandardMaterial({ color: '#ffd9a8', transparent: true, opacity: 0.07, roughness: 0.05, metalness: 0, envMap: envTex, envMapIntensity: 1, depthWrite: false, side: THREE.DoubleSide }),
  flame: new THREE.MeshBasicMaterial({ color: new THREE.Color(1.5, 0.78, 0.32), toneMapped: false }),
  candle: std('#e9dfc8', { roughness: 0.7 }),
  holeGlow: new THREE.MeshBasicMaterial({ color: new THREE.Color(1.6, 1.05, 0.4), toneMapped: false, transparent: true }),
  pickGlow: new THREE.MeshBasicMaterial({ color: new THREE.Color(1.3, 0.85, 0.35), toneMapped: false, transparent: true, opacity: 0.8, depthWrite: false }),
};
rep(M.floor, 9, 11);

function worldUV(geo, s) {
  const p = geo.attributes.position, n = geo.attributes.normal, uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
    let a, b;
    if (ax >= ay && ax >= az) { a = p.getZ(i); b = p.getY(i); } else if (ay >= az) { a = p.getX(i); b = p.getZ(i); } else { a = p.getX(i); b = p.getY(i); }
    uv.setXY(i, a * s, b * s);
  }
  uv.needsUpdate = true;
  return geo;
}
function mesh(geo, mat, x = 0, y = 0, z = 0, parent = scene) {
  const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; parent.add(m); return m;
}
const box = (w, h, d, mat, x, y, z, parent, s = 0.3) => mesh(worldUV(new THREE.BoxGeometry(w, h, d), s), mat, x, y, z, parent);

// ------------------------------------------------------------------ langit senja (sama dengan istana)
const SUN = new THREE.Vector3(-0.19, 0.075, -0.98).normalize();
{
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1500, 40, 20), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false, toneMapped: false,
    uniforms: {
      top: { value: new THREE.Color('#06050c') }, mid: { value: new THREE.Color('#2c1828') },
      hor: { value: new THREE.Color('#d0602c') }, low: { value: new THREE.Color('#3e1c16') },
      deep: { value: new THREE.Color('#08050a') }, sun: { value: SUN }, sunCol: { value: new THREE.Color('#ffb868') },
    },
    vertexShader: 'varying vec3 vD; void main(){ vD = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec3 top, mid, hor, low, deep, sun, sunCol; varying vec3 vD;
      void main(){ vec3 d = normalize(vD); float h = d.y; vec3 sd = normalize(sun);
        float az = max(dot(normalize(vec2(d.x, d.z) + 1e-5), normalize(vec2(sd.x, sd.z))), 0.0);
        vec3 horizon = mix(hor * 0.55, hor, pow(az, 3.0));
        vec3 c = mix(horizon, mid, smoothstep(0.0, 0.22, h));
        c = mix(c, top, smoothstep(0.22, 0.8, h));
        c = mix(c, low, smoothstep(0.0, -0.08, h));
        c = mix(c, deep, smoothstep(-0.08, -0.5, h));
        float s = max(dot(d, sd), 0.0);
        c += sunCol * (pow(s, 1800.0) * 3.0 + pow(s, 90.0) * 0.6 + pow(s, 9.0) * 0.25 + pow(s, 2.5) * 0.06);
        gl_FragColor = vec4(c * 0.9, 1.0);
        #include <colorspace_fragment>
      }`,
  }));
  sky.renderOrder = -10; scene.add(sky);
}
scene.add(new THREE.HemisphereLight('#e0c4b0', '#2a1a12', 0.95));
const sunL = new THREE.DirectionalLight('#ffa860', 2.4);
sunL.position.set(-80, 40, 20);
sunL.target.position.set(0, 0, -6); scene.add(sunL.target);
if (!MOBILE) {
  sunL.castShadow = true; sunL.shadow.mapSize.set(2048, 2048);
  Object.assign(sunL.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 20, far: 220 });
  sunL.shadow.bias = -0.0005; sunL.shadow.normalBias = 0.04;
}
scene.add(sunL);
const fillL = new THREE.DirectionalLight('#b8a4c8', 0.7); fillL.position.set(60, 26, 30); scene.add(fillL);

// ------------------------------------------------------------------ dunia di luar jendela: pulau melayang & lautan awan
{
  mesh(new THREE.CylinderGeometry(70, 66, 2, 64), M.grass, 0, -1.05, -6);
  rep(M.grass, 14, 14);
  const cliff = mesh(new THREE.ConeGeometry(66, 95, 48, 8, true), M.rock, 0, -49, -6); cliff.rotation.x = Math.PI; cliff.castShadow = false;
  rep(M.rock, 10, 6);
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const towerMat = std('#d8cbb5', { map: T.stone.map }), roofMat = std('#3a2a38', { roughness: 0.6 });
  const nFar = MOBILE ? 8 : 14;
  for (let i = 0; i < nFar; i++) {
    const g = new THREE.Group(), a = i / nFar * Math.PI * 2 + rnd() * 0.3, rad = 150 + rnd() * 230, s = 0.8 + rnd() * 2;
    g.position.set(Math.cos(a) * rad, -20 + rnd() * 45, -6 + Math.sin(a) * rad);
    const topR = 8 * s;
    const rock = new THREE.Mesh(new THREE.ConeGeometry(topR, topR * 2.2, 10, 3), M.rock); rock.rotation.x = Math.PI; rock.position.y = -topR * 1.1; g.add(rock);
    g.add(new THREE.Mesh(new THREE.CylinderGeometry(topR * 1.04, topR, 0.8, 16), M.grass));
    for (let k = 0; k < 2 + Math.floor(rnd() * 3); k++) {
      const ta = rnd() * 6.28, tr = rnd() * topR * 0.5, th = (5 + rnd() * 9) * s, trr = (0.6 + rnd() * 0.8) * s;
      const t = new THREE.Mesh(new THREE.CylinderGeometry(trr, trr * 1.05, th, 10), towerMat); t.position.set(Math.cos(ta) * tr, th / 2, Math.sin(ta) * tr); g.add(t);
      const r = new THREE.Mesh(new THREE.ConeGeometry(trr * 1.3, trr * 2.6, 10), roofMat); r.position.set(t.position.x, th + trr * 1.3, t.position.z); g.add(r);
    }
    scene.add(g);
  }
  const cloudMats = [DARK_PAL, LIT_PAL, FOG_PAL].map((pal, k) => {
    const t = new THREE.CanvasTexture(noiseCloud(256, 128, 31 + k, pal)); t.colorSpace = THREE.SRGBColorSpace;
    return new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false, fog: true, opacity: 0.9 });
  });
  for (let i = 0; i < (MOBILE ? 22 : 40); i++) {
    const s = new THREE.Sprite(cloudMats[i % 3]);
    const a = rnd() * Math.PI * 2, rad = 110 + rnd() * 380, below = i % 3 === 2;
    s.position.set(Math.cos(a) * rad, below ? -60 - rnd() * 30 : -10 + rnd() * 50, -6 + Math.sin(a) * rad);
    const w = (below ? 160 : 90) + rnd() * 120; s.scale.set(w, w * 0.5, 1);
    scene.add(s);
  }
}

// ------------------------------------------------------------------ aula: dinding batu dengan jendela lengkung besar
const W = 30, D = 38, H = 13, FZ = 13, T_W = 1.4, DOORW = 5.2, DOORH = 6.0, AR = DOORW / 2;
const WIN = { w: 3.6, sill: 1.1, h: 6.6 };
const winZ = [FZ - 8, FZ - 18.5, FZ - 29];
function archHole(path, cx, sill, w, h) {
  const r = w / 2;
  path.moveTo(cx - r, sill); path.lineTo(cx + r, sill); path.lineTo(cx + r, sill + h);
  path.absarc(cx, sill + h, r, 0, Math.PI, false); path.lineTo(cx - r, sill);
}
function wallWithHoles(len, height, holes, mat) {
  const s = new THREE.Shape(); s.moveTo(0, 0); s.lineTo(len, 0); s.lineTo(len, height); s.lineTo(0, height); s.lineTo(0, 0);
  for (const fn of holes) { const p = new THREE.Path(); fn(p); s.holes.push(p); }
  const g = new THREE.ExtrudeGeometry(s, { depth: T_W, bevelEnabled: false, curveSegments: 28 });
  g.computeVertexNormals(); worldUV(g, 0.3);
  const m = new THREE.Mesh(g, mat); m.castShadow = m.receiveShadow = true; return m;
}
function windowDressing(parent, cx, sill, w, h) {
  const r = w / 2, g = new THREE.Group(); parent.add(g);
  for (const zf of [-0.05, T_W + 0.05]) {
    const arch = new THREE.Mesh(new THREE.TorusGeometry(r + 0.18, 0.18, 10, 40, Math.PI), M.trim); arch.position.set(cx, sill + h, zf); g.add(arch);
    for (const sx of [-1, 1]) { const j = new THREE.Mesh(worldUV(new THREE.BoxGeometry(0.36, h, 0.36), 0.3), M.trim); j.position.set(cx + sx * (r + 0.18), sill + h / 2, zf); g.add(j); }
  }
  const sillB = new THREE.Mesh(worldUV(new THREE.BoxGeometry(w + 0.8, 0.25, T_W + 0.6), 0.3), M.trim); sillB.position.set(cx, sill - 0.12, T_W / 2); g.add(sillB);
  const bar = (x0, y0, x1, y1) => { const len = Math.hypot(x1 - x0, y1 - y0); const b = new THREE.Mesh(new THREE.BoxGeometry(len, 0.07, 0.07), M.iron); b.position.set((x0 + x1) / 2, (y0 + y1) / 2, T_W / 2); b.rotation.z = Math.atan2(y1 - y0, x1 - x0); g.add(b); };
  bar(cx, sill, cx, sill + h + r);
  for (const k of [0.33, 0.66, 1]) bar(cx - r, sill + h * k, cx + r, sill + h * k);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(r * 0.48, 0.04, 8, 32), M.iron); ring.position.set(cx, sill + h + r * 0.38, T_W / 2); g.add(ring);
  const archBar = new THREE.Mesh(new THREE.TorusGeometry(r - 0.02, 0.04, 8, 32, Math.PI), M.iron); archBar.position.set(cx, sill + h, T_W / 2); g.add(archBar);
  const glassS = new THREE.Shape(); archHole(glassS, cx, sill, w, h);
  const glass = new THREE.Mesh(new THREE.ShapeGeometry(glassS, 24), M.glass); glass.position.z = T_W / 2; g.add(glass);
}
const hall = new THREE.Group(); scene.add(hall);
const swayers = [];
{
  for (const sx of [-1, 1]) {
    const g = new THREE.Group();
    g.add(wallWithHoles(D, H, winZ.map(z => p => archHole(p, FZ - z, WIN.sill, WIN.w, WIN.h)), M.wall));
    winZ.forEach(z => windowDressing(g, FZ - z, WIN.sill, WIN.w, WIN.h));
    g.rotation.y = Math.PI / 2; g.position.set(sx < 0 ? -W / 2 + T_W : W / 2, 0, FZ);
    hall.add(g);
  }
  {
    const g = new THREE.Group();
    g.add(wallWithHoles(W, H, [-8, 8].map(x => p => archHole(p, x + W / 2, WIN.sill, WIN.w, WIN.h + 1.2)), M.wall));
    [-8, 8].forEach(x => windowDressing(g, x + W / 2, WIN.sill, WIN.w, WIN.h + 1.2));
    g.position.set(-W / 2, 0, FZ - D); hall.add(g);
  }
  {
    const wall = wallWithHoles(W, H, [p => archHole(p, W / 2, 0, DOORW, DOORH)], M.wall);
    wall.position.set(-W / 2, 0, FZ - T_W); hall.add(wall);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(AR + 0.3, 0.3, 12, 48, Math.PI), M.trim); ring.position.set(0, DOORH, FZ - T_W - 0.12); hall.add(ring);
  }
  mesh(new THREE.PlaneGeometry(W, D).rotateX(-Math.PI / 2), M.floor, 0, 0.01, FZ - D / 2, hall).castShadow = false;
  mesh(new THREE.PlaneGeometry(3.4, 14).rotateX(-Math.PI / 2), M.carpet, 0, 0.03, FZ - 8.5, hall).castShadow = false;
  for (const sx of [-1, 1]) mesh(new THREE.PlaneGeometry(0.1, 14).rotateX(-Math.PI / 2), M.gold, sx * 1.62, 0.035, FZ - 8.5, hall).castShadow = false;
  const prof = iShape(0.42, 0.22, 0.03, 0.04), ext = len => new THREE.ExtrudeGeometry(prof, { depth: len, bevelEnabled: false });
  const span = W - 2.4, colH = H - 1.2, rise = 3.0, half = span / 2, a = Math.atan2(rise, half), rl = Math.hypot(half, rise);
  for (let z = FZ - 4; z > FZ - D + 2; z -= 7) {
    for (const s of [-1, 1]) {
      const raf = mesh(ext(rl), M.frame, s * half, colH, z, hall); raf.rotation.set(0, -s * Math.PI / 2, 0); raf.rotateX(-a);
      const hs = new THREE.Shape(); hs.moveTo(0, 0); hs.lineTo(2.2, 2.2 * Math.tan(a)); hs.lineTo(0, -1.0); hs.lineTo(0, 0);
      const hg = mesh(new THREE.ExtrudeGeometry(hs, { depth: 0.03, bevelEnabled: false }), M.frame, s * (half - 0.21), colH - 0.21, z - 0.015, hall);
      if (s > 0) hg.rotation.y = Math.PI;
      box(0.6, 0.9, 0.6, M.trim, s * (half + 0.3), colH - 0.45, z, hall);
    }
  }
  for (let i = 1; i < 7; i++) for (const s of [-1, 1]) box(0.1, 0.22, D - 2, M.frame, s * half * i / 7, colH + rise * (1 - i / 7) + 0.36, FZ - D / 2, hall, 0.5);
  const roofMat = std('#2a2026', { roughness: 0.9 });
  for (const s of [-1, 1]) { const r = box(rl + 1, 0.2, D + 0.5, roofMat, s * half / 2, colH + rise / 2 + 0.55, FZ - D / 2, hall); r.rotation.z = -s * a; }
  for (const z of [FZ - 9, FZ - 21]) {
    const ringC = mesh(new THREE.TorusGeometry(1.4, 0.05, 8, 40), M.iron, 0, 7.2, z, hall); ringC.rotation.x = Math.PI / 2;
    mesh(new THREE.CylinderGeometry(0.02, 0.02, colH + rise - 7.2, 6), M.iron, 0, 7.2 + (colH + rise - 7.2) / 2, z, hall);
    for (let k = 0; k < 8; k++) {
      const an = k / 8 * Math.PI * 2, x = Math.cos(an) * 1.4, zz = z + Math.sin(an) * 1.4;
      mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.22, 8), M.candle, x, 7.33, zz, hall);
      const f = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), M.flame); f.position.set(x, 7.48, zz); f.scale.y = 1.6; hall.add(f); flames.push(f);
    }
    const l = new THREE.PointLight('#ffb070', 10, 16, 2); l.position.set(0, 7.0, z); hall.add(l);
  }
  for (const x of [-3.6, 3.6]) {
    const ban = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 5.0, 2, 8), new THREE.MeshStandardMaterial({ map: bannerTexture(), roughness: 0.85, side: THREE.DoubleSide, transparent: true, alphaTest: 0.5 }));
    ban.position.set(x, 7.4, FZ - D + T_W + 0.08); hall.add(ban); swayers.push(ban);
  }
}
// lorong gerbang
{
  const vz = FZ + 6, len = 12;
  for (const sx of [-1, 1]) box(1.2, 5.6, len, M.wall, sx * 3.6, 2.8, vz, hall);
  const vault = mesh(worldUV(new THREE.CylinderGeometry(4.2, 4.2, len, 24, 1, true, -Math.PI / 2, Math.PI), 0.3), M.wall, 0, 5.6, vz, hall);
  vault.rotation.x = -Math.PI / 2;
  mesh(new THREE.PlaneGeometry(6, len).rotateX(-Math.PI / 2), M.floor, 0, 0.01, vz, hall).castShadow = false;
  for (const sx of [-1, 1]) for (const z of [FZ + 2.5, FZ + 8]) {
    mesh(new THREE.CylinderGeometry(0.07, 0.05, 0.6, 8), M.iron, sx * 2.9, 3.0, z, hall);
    const f = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 8), M.flame); f.position.set(sx * 2.85, 3.4, z); f.scale.y = 1.5; hall.add(f); flames.push(f);
  }
  const tl = new THREE.PointLight('#ff9a50', 9, 12, 2); tl.position.set(0, 3.6, FZ + 4); hall.add(tl);
}
const doors = [];
for (const s of [-1, 1]) {
  const sh = new THREE.Shape(); sh.moveTo(0, 0); sh.lineTo(AR, 0);
  for (let i = 0; i <= 16; i++) { const a = Math.PI / 2 * (i / 16); sh.lineTo(Math.cos(a) * AR, DOORH + Math.sin(a) * AR); }
  sh.lineTo(0, 0);
  const g = new THREE.ExtrudeGeometry(sh, { depth: 0.2, bevelEnabled: false }); g.computeVertexNormals(); worldUV(g, 0.45);
  const leaf = new THREE.Mesh(g, M.wood); leaf.castShadow = true;
  const pivot = new THREE.Group(); pivot.position.set(s * AR, 0, FZ - T_W / 2);
  if (s < 0) leaf.scale.x = -1;
  leaf.position.x = s > 0 ? -AR : AR;
  pivot.add(leaf);
  for (const y of [1.0, 3.2, 5.4]) { const b = new THREE.Mesh(new THREE.BoxGeometry(AR * 0.94, 0.14, 0.05), M.iron); b.position.set(s > 0 ? -AR / 2 : AR / 2, y, 0.23); pivot.add(b); }
  const knock = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.025, 8, 20), M.gold); knock.position.set(s > 0 ? -0.45 : 0.45, 3.0, 0.27); pivot.add(knock);
  hall.add(pivot); doors.push({ pivot, s });
}

// ------------------------------------------------------------------ meja + potongan sambungan balok-kolom
const piece = new THREE.Group(); piece.position.copy(TABLE); scene.add(piece);
const TOP = 0.95;
const holeWorld = new THREE.Vector3();
let holeHit, holeRing;
const BOLT_D = 0.034;
const colX = -0.55, Hc = 0.34, Bc = 0.34, tfc = 0.026, twc = 0.018;
const TRAY = new THREE.Vector3(-0.08, TOP + BOLT_D * 0.95 + 0.004, 0.66);   // tempat baut tergeletak (lokal meja)
{
  box(3.8, 0.12, 1.9, M.wood, 0, TOP - 0.06, 0, piece, 0.5);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const lp = [[0.1, 0], [0.12, 0.08], [0.07, 0.22], [0.09, 0.45], [0.06, 0.7], [0.09, 0.82], [0.1, TOP - 0.12]].map(([r, y]) => new THREE.Vector2(r, y));
    mesh(new THREE.LatheGeometry(lp, 16), M.wood, sx * 1.7, 0, sz * 0.78, piece);
    box(0.16, 0.03, 0.16, M.gold, sx * 1.84, TOP - 0.005, sz * 0.89, piece);
  }
  box(3.9, 0.012, 0.9, M.velvet, 0, TOP + 0.006, 0, piece);
  for (const sz of [-1, 1]) box(3.9, 0.014, 0.03, M.gold, 0, TOP + 0.008, sz * 0.45, piece);
  const colTop = TOP + 1.45;
  mesh(new THREE.BoxGeometry(0.62, 0.03, 0.62), M.primer, colX, TOP + 0.03, 0, piece);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const n = hexPrism(0.03, 0.026, M.galv); n.position.set(colX + sx * 0.23, TOP + 0.058, sz * 0.23); piece.add(n); }
  mesh(vert(iShape(Hc, Bc, twc, tfc), colTop - TOP - 0.045), M.primer, colX, TOP + 0.045, 0, piece);
  mesh(new THREE.BoxGeometry(Hc + 0.04, 0.02, Bc + 0.04), M.primer, colX, colTop + 0.01, 0, piece);
  const Hb = 0.4, Bb = 0.2, tfb = 0.022, twb = 0.014, yb = TOP + 0.85, tp = 0.028, px0 = colX + Hc / 2;
  const beam = mesh(new THREE.ExtrudeGeometry(iShape(Hb, Bb, twb, tfb), { depth: 1.25, bevelEnabled: false }), M.primer, px0 + tp, yb, 0, piece);
  beam.rotation.y = Math.PI / 2;
  mesh(new THREE.BoxGeometry(tp, 0.66, 0.24), M.primer, px0 + tp / 2, yb + 0.06, 0, piece);
  for (const yy of [yb + Hb / 2 - tfb / 2, yb - Hb / 2 + tfb / 2]) for (const sz of [-1, 1])
    mesh(new THREE.BoxGeometry(Hc - 2 * tfc, 0.016, (Bc - twc) / 2), M.primer, colX, yy, sz * (twc / 2 + (Bc - twc) / 4), piece);
  for (const yy of [yb + Hb / 2, yb - Hb / 2]) mesh(new THREE.BoxGeometry(0.012, 0.012, Bb), M.iron, px0 + tp + 0.006, yy, 0, piece);
  const plaque = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.14), new THREE.MeshStandardMaterial({ map: plaqueTexture(), metalness: 0.6, roughness: 0.4, envMap: envTex }));
  plaque.rotation.x = -Math.PI / 2 + 0.35; plaque.position.set(1.3, TOP + 0.04, 0.62); piece.add(plaque);
  const rows = [yb + 0.31, yb + 0.12, yb - 0.12, yb - 0.26], g = 0.07;
  rows.forEach((y, ri) => [-g, g].forEach(z => {
    const p = new THREE.Vector3(px0 + tp, y, z);
    if (ri === 1 && z > 0) {
      const hole = new THREE.Mesh(new THREE.CylinderGeometry(BOLT_D * 0.62, BOLT_D * 0.62, 0.004, 16), new THREE.MeshBasicMaterial({ color: '#050302' }));
      hole.rotation.z = Math.PI / 2; hole.position.copy(p).add(new THREE.Vector3(0.002, 0, 0)); piece.add(hole);
      holeRing = new THREE.Mesh(new THREE.TorusGeometry(BOLT_D * 0.9, 0.006, 8, 28), M.holeGlow); holeRing.rotation.y = Math.PI / 2; holeRing.position.copy(p).add(new THREE.Vector3(0.004, 0, 0)); piece.add(holeRing);
      holeHit = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), new THREE.MeshBasicMaterial({ visible: false })); holeHit.position.copy(p); piece.add(holeHit);
      holeWorld.copy(p).add(TABLE);
    } else {
      const b = horizBolt(); b.position.copy(p); piece.add(b);
      const n = hexPrism(BOLT_D * 0.95, BOLT_D * 0.85, M.galv); n.rotation.z = Math.PI / 2; n.position.set(px0 - tfc - BOLT_D * 0.42, y, z); piece.add(n);
    }
  }));
  // tatakan kayu kecil tempat baut terakhir tergeletak + cincin cahaya penanda
  box(0.34, 0.012, 0.22, M.wood, TRAY.x, TOP + 0.006, TRAY.z, piece);
  const roll = mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.75, 16), std('#e9e0cc', { roughness: 0.9 }), -1.35, TOP + 0.05, 0.45, piece); roll.rotation.set(0, 0.4, Math.PI / 2);
  mesh(new THREE.BoxGeometry(0.42, 0.012, 0.045), M.galv, 1.25, TOP + 0.012, -0.45, piece).rotation.y = 0.5;
  const spot = new THREE.SpotLight('#ffe2b8', 34, 16, 0.5, 0.6, 1.5);
  spot.position.set(2.2, 8.5, TABLE.z + 3.5); spot.target = piece; spot.castShadow = !MOBILE; spot.shadow.mapSize.set(1024, 1024); spot.shadow.bias = -0.0005;
  scene.add(spot);
}
const H0 = holeWorld.clone();
const NUT_X = TABLE.x + colX + Hc / 2 - tfc - BOLT_D * 0.42;
function iShape(Hh, B, tw, tf) {
  const s = new THREE.Shape();
  s.moveTo(-B / 2, -Hh / 2); s.lineTo(B / 2, -Hh / 2); s.lineTo(B / 2, -Hh / 2 + tf); s.lineTo(tw / 2, -Hh / 2 + tf); s.lineTo(tw / 2, Hh / 2 - tf);
  s.lineTo(B / 2, Hh / 2 - tf); s.lineTo(B / 2, Hh / 2); s.lineTo(-B / 2, Hh / 2); s.lineTo(-B / 2, Hh / 2 - tf); s.lineTo(-tw / 2, Hh / 2 - tf);
  s.lineTo(-tw / 2, -Hh / 2 + tf); s.lineTo(-B / 2, -Hh / 2 + tf); s.lineTo(-B / 2, -Hh / 2);
  return s;
}
function vert(shape, len) { const g = new THREE.ExtrudeGeometry(shape, { depth: len, bevelEnabled: false }); g.rotateX(-Math.PI / 2); g.rotateY(Math.PI / 2); return g; }
function hexPrism(r, h, mat) { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 6), mat); m.castShadow = true; return m; }
function threadMat() {
  if (_thread) return _thread;
  const c = document.createElement('canvas'); c.width = 16; c.height = 64; const x = c.getContext('2d');
  for (let i = 0; i < 64; i++) { const v = 128 + Math.sin(i / 64 * Math.PI * 2 * 8) * 110; x.fillStyle = `rgb(128,${v},255)`; x.fillRect(0, i, 16, 1); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 3);
  return (_thread = new THREE.MeshStandardMaterial({ color: '#c8ced4', metalness: 1, roughness: 0.32, normalMap: t, envMap: envTex }));
}
function horizBolt() {
  const outer = new THREE.Group(), spin = new THREE.Group(); outer.add(spin); outer.userData.spin = spin;
  const head = hexPrism(BOLT_D * 0.95, BOLT_D * 0.65, M.galv); head.position.y = BOLT_D * 0.33 + 0.004; spin.add(head);
  const washer = new THREE.Mesh(new THREE.CylinderGeometry(BOLT_D * 1.1, BOLT_D * 1.1, 0.004, 20), M.galv); washer.position.y = 0.002; spin.add(washer);
  const shank = new THREE.Mesh(new THREE.CylinderGeometry(BOLT_D / 2, BOLT_D / 2, 0.11, 14), threadMat()); shank.position.y = -0.055; spin.add(shank);
  outer.rotation.z = -Math.PI / 2;
  return outer;
}
function plaqueTexture() {
  const c = document.createElement('canvas'); c.width = 512; c.height = 144; const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 512, 144); g.addColorStop(0, '#b8862e'); g.addColorStop(0.5, '#f0c870'); g.addColorStop(1, '#a87424');
  x.fillStyle = g; x.fillRect(0, 0, 512, 144); x.strokeStyle = '#5a3a10'; x.lineWidth = 6; x.strokeRect(8, 8, 496, 128);
  x.fillStyle = '#3a2408'; x.textAlign = 'center'; x.font = '700 40px Cinzel, serif'; x.fillText('STEEL KIT', 256, 66);
  x.font = '500 24px Cinzel, serif'; x.fillText('Sambungan pelat ujung · 8 baut', 256, 106);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function bannerTexture() {
  const c = document.createElement('canvas'); c.width = 256; c.height = 640; const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 640); g.addColorStop(0, '#8e1c1c'); g.addColorStop(1, '#5a0f0f'); x.fillStyle = g; x.fillRect(0, 0, 256, 640);
  x.strokeStyle = '#e0a94a'; x.lineWidth = 8; x.strokeRect(16, 16, 224, 560);
  x.fillStyle = '#e0a94a'; x.beginPath(); x.moveTo(128, 170); x.lineTo(196, 200); x.lineTo(188, 300); x.lineTo(128, 350); x.lineTo(68, 300); x.lineTo(60, 200); x.closePath(); x.fill();
  x.fillStyle = '#5a0f0f'; x.fillRect(96, 214, 64, 14); x.fillRect(96, 290, 64, 14); x.fillRect(121, 228, 14, 62);
  x.fillStyle = '#ffe7a8'; x.font = '700 30px Cinzel, serif'; x.textAlign = 'center'; x.fillText('STEEL KIT', 128, 440);
  x.globalCompositeOperation = 'destination-out';
  x.beginPath(); x.moveTo(0, 600); x.lineTo(128, 640); x.lineTo(256, 600); x.lineTo(256, 640); x.lineTo(0, 640); x.closePath(); x.fill();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// ------------------------------------------------------------------ lukisan (gambar fitur) + keterangannya
const PAPER = new Set(['layout_struktur', 'layout_detail', 'fabrikasi']);
function drawShot(ctx, img, name, x, y, w, h) {
  ctx.save();
  if (PAPER.has(name)) ctx.filter = 'invert(1) hue-rotate(185deg) sepia(.25) brightness(.92)';
  ctx.drawImage(img, x, y, w, h); ctx.restore();
  ctx.fillStyle = 'rgba(20,10,4,.12)'; ctx.fillRect(x, y, w, h);
}
// x, y dalam persen gambar penuh
const CARDS = [
  { img: 'installer', step: 'Mulai · pasang sekali klik', title: 'Pasang sekali klik', lead: 'Penginstal ±2 MB, tanpa hak admin. Mendeteksi AutoCAD 2021–2027 dan bisa sekalian memasang suara offline.',
    notes: [[18, 18, 'Logo dan versi yang terpasang.'], [50, 40, 'Versi AutoCAD yang ditemukan di komputer Anda.'], [80, 90, 'Klik Pasang. Selesai.']] },
  { img: 'profil', step: 'Langkah 1 · SKPROFIL', title: '476 profil baja', lead: 'Pustaka profil lengkap. Semua dimensi bisa diubah, propertinya dihitung langsung.',
    notes: [[12, 50, 'Pilih jenis profil dan ukurannya (476 ukuran bawaan).'], [46, 44, 'Gambar penampang dengan dimensi dan titik berat.'],
      [84, 20, 'Dimensi bisa diubah; nama profil ikut otomatis.'], [84, 60, 'Properti dihitung langsung: luas, berat, Ix, Sx, Zx, dan lainnya.'],
      [92, 96, 'Gambar batang 3D/2D, penampang, atau tabel properti.']] },
  { img: 'asisten', step: 'Langkah 2 · SKASISTEN', title: 'Asisten berbahasa Indonesia', lead: 'Ceritakan rangka yang Anda mau dengan kalimat biasa. Steel Kit menyusun usulannya; Anda periksa dulu sebelum dipasang.',
    notes: [[6, 13, 'Tombol mikrofon: klik lalu bicara. Rekaman berhenti sendiri saat Anda diam; suara diproses di laptop Anda.'],
      [47, 14, 'Kalimat maksud Anda, hasil ketikan atau suara.'], [91, 11, 'Baca maksud: kalimat diubah menjadi usulan batang.'],
      [30, 42, 'Ringkasan usulan dan asumsi yang perlu Anda periksa.'], [31, 75, 'Daftar batang: profil, koordinat, dan putaran. Semua sel bisa diedit.'],
      [82, 41, 'Jumlah batang, panjang total, dan perkiraan berat baja.'], [80, 68, 'Pratinjau 3D: seret untuk memutar, gulir untuk zoom.'],
      [91, 96, 'Pasang ke gambar AutoCAD, sekaligus sambungan otomatis bila sakelarnya menyala.']] },
  { img: 'lutut_puncak_3d', step: 'Langkah 3 · SKUBAH / SKBROWSER', title: 'Model 3D di AutoCAD', lead: 'Batang, pelat, baut, dan angkur menjadi solid 3D. Ubah lewat grip atau Browser; sambungan ikut diperbarui.',
    notes: [[25, 28, 'Lutut tampak samping: rafter dipotong tegak, haunch tepat di bawahnya.'], [75, 24, 'Puncak: dua pelat ujung tegak dibaut.'],
      [25, 76, 'Lutut 3D lengkap dengan gording dan cleat-nya.'], [75, 76, 'Puncak 3D: sambungan rapat tanpa celah.']] },
  { img: 'sambungan', step: 'Langkah 4 · SKSAMBUNGAUTO / SKSAMBUNG', title: '28 jenis sambungan', lead: 'Pilih sambungan lewat gambar teknik, atur pelat, baut, angkur, dan las, lalu lihat hasil ceknya seketika.',
    notes: [[12, 49, 'Galeri 28 jenis sambungan bergambar, lengkap dengan pencarian.'], [48, 38, 'Pratinjau dua tampak berdimensi, dibangkitkan dari geometri sebenarnya.'],
      [36, 82, 'Kapan sambungan ini dipakai (praktik umum).'], [60, 82, 'Cek jarak & ukuran minimum. Ini bukan cek kekuatan.'],
      [85, 46, 'Parameter: profil, pelat, baut, las. Ubah, pratinjau ikut berubah.'], [91, 96, 'Buat sambungan 3D sekaligus detail 2D-nya.']] },
  { img: 'potongan_rapat', step: 'Langkah 5 · SKBENTROK', title: 'Potongan rapat & aktual', lead: 'Ujung batang miring dipotong tegak rapat ke pelat. Tidak menembus, tidak bercelah: sama di pratinjau, detail 2D, dan model 3D.',
    notes: [[17, 30, 'Puncak: kedua rafter dipotong tegak rapat ke pelat ujung.'], [50, 30, 'Lutut + haunch: rafter dan sayap haunch rapat ke pelat.'],
      [83, 30, 'Kolom angin: ujung kolom mengikuti kemiringan pelat kepala.'], [17, 78, 'Balok anak ke badan balok induk (fin plate).'],
      [50, 78, 'Las langsung hollow: cabang rapat ke muka batang tepi.'], [83, 78, 'Las langsung pipa (potongan mulut ikan).']] },
  { img: 'layout_struktur', step: 'Langkah 6 · SKLAYOUT', title: 'Lembar struktur otomatis', lead: 'Satu perintah menghasilkan lembar A3 berisi isometrik, denah, dan tampak: grid as, elevasi, marking, catatan umum, dan kotak judul lengkap.',
    notes: [[26, 22, 'Isometrik dengan garis tersembunyi.'], [67, 10, 'Grid as A–B dan 1–6 dari titik dasar kolom, dengan dimensi antar as.'],
      [18, 56, 'Marking batang sama dengan daftar Excel, mis. C1–C6 WF400.'], [43, 54, 'Penanda elevasi: ±0.000 dasar kolom sampai puncak rangka.'],
      [72, 62, 'Tampak samping: jarak bay dan bracing dinding.'], [16, 87, 'Catatan umum: mutu dan prosedur ditulis sesuai spesifikasi proyek.'],
      [78, 91, 'Kotak judul: proyek, no. gambar, lembar x/n, revisi, penanggung jawab.']] },
  { img: 'layout_detail', step: 'Langkah 6 · SKLAYOUT', title: 'Lembar detail sambungan', lead: 'Setiap jenis sambungan mendapat lembar detail berskala dengan simbol las dan daftar bahan.',
    notes: [[22, 14, 'Nama detail dan hasil cek jarak/ukuran minimum.'], [22, 44, 'Tampak samping lutut: pelat ujung, baut, haunch.'],
      [27, 50, 'Simbol las: ukuran leher a8/a5 untuk sayap dan badan.'], [57, 47, 'Tampak muka pelat: jarak baut berdimensi, angka tidak bertumpuk.'],
      [81, 27, 'Daftar bahan: pelat, baut, berat (kg).'], [78, 91, 'Kotak judul lembar.']] },
  { img: 'fabrikasi', step: 'Langkah 7 · SKFABRIKASI', title: 'Gambar fabrikasi per marking', lead: 'Satu lembar untuk tiap marking batang, siap dibawa ke bengkel: posisi lubang, panjang potong, dan jumlahnya.',
    notes: [[33, 19, 'Tampak samping dari batang sebenarnya: lubang lonjong rod ikut terlihat.'], [40, 54, 'Lubang baut dari ujung kiri; jarak sama digabung 4x110=440.'],
      [80, 17, 'Data marking: profil, jumlah, panjang potong, berat.'], [78, 46, 'Daftar lubang: koordinat setiap lubang untuk bengkel.'],
      [78, 91, 'Nomor gambar SK-FB per marking.']] },
];
function goldFrame(x, X, Y, w, h, t) {
  const g = x.createLinearGradient(X, Y, X + w, Y + h); g.addColorStop(0, '#ffe7a8'); g.addColorStop(0.45, '#c08a2a'); g.addColorStop(0.55, '#e0a94a'); g.addColorStop(1, '#7a4a14');
  x.strokeStyle = g; x.lineWidth = t; x.strokeRect(X + t / 2, Y + t / 2, w - t, h - t);
  x.strokeStyle = 'rgba(40,22,6,.9)'; x.lineWidth = 2; x.strokeRect(X + t, Y + t, w - 2 * t, h - 2 * t);
}
const CARD_ASPECT = 440 / 640;
const cardMeshes = CARDS.map((c, i) => {
  const cv = document.createElement('canvas'); cv.width = 640; cv.height = 440;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const img = new Image(); img.src = 'img/' + c.img + '.webp';
  img.onload = () => {
    const x = cv.getContext('2d');
    x.fillStyle = '#140d09'; x.fillRect(0, 0, 640, 440);
    const s = Math.max(600 / img.width, 340 / img.height);
    x.save(); x.beginPath(); x.rect(20, 20, 600, 340); x.clip(); drawShot(x, img, c.img, 320 - img.width * s / 2, 190 - img.height * s / 2, img.width * s, img.height * s); x.restore();
    x.fillStyle = 'rgba(14,9,7,.95)'; x.fillRect(20, 360, 600, 60);
    x.fillStyle = '#ffe7a8'; x.font = '700 27px Cinzel, serif'; x.textAlign = 'center'; x.fillText(c.title, 320, 400);
    goldFrame(x, 0, 0, 640, 440, 18);
    tex.needsUpdate = true;
  };
  // tampil seperti lukisan di depan kamera: selalu di atas adegan, tidak tertutup / menembus benda
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, CARD_ASPECT), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, opacity: 0 }));
  m.renderOrder = 10; m.userData = { card: i }; m.visible = false;
  scene.add(m);
  return m;
});

// ------------------------------------------------------------------ cermin video pengenalan
const SLIDES = [
  { img: 'installer', cap: 'Mulai: pasang sekali klik, buka tab ribbon Steel Kit di AutoCAD' },
  { img: 'profil', cap: '1 · SKPROFIL: pilih ukuran profil (boleh dilewati)' },
  { img: 'asisten', cap: '2 · SKASISTEN: ketik atau ucapkan rangkanya, periksa, lalu Pasang' },
  { img: 'lutut_puncak_3d', cap: '3 · Model 3D: rapikan dengan grip, SKUBAH, atau SKBROWSER' },
  { img: 'sambungan', cap: '4 · SKSAMBUNGAUTO lalu SKSAMBUNG: sambungan & opsinya' },
  { img: 'potongan_rapat', cap: '5 · SKBENTROK: rapat, tidak ada yang saling menembus' },
  { img: 'layout_struktur', cap: '6 · SKLAYOUT: lembar struktur berdimensi, grid, marking' },
  { img: 'layout_detail', cap: '6 · SKLAYOUT: lembar detail sambungan, simbol las, daftar bahan' },
  { img: 'fabrikasi', cap: '7 · SKFABRIKASI: satu lembar per marking untuk bengkel' },
  { img: null, cap: '8 · SKEXCEL: daftar bahan & berat ke Excel. Selesai!' },
];
// slide penutup tanpa gambar: ringkasan urutan perintah
const FLOW = [['1', 'SKPROFIL', 'pilih profil'], ['2', 'SKASISTEN', 'susun rangka'], ['3', 'SKUBAH', 'rapikan batang'], ['4', 'SKSAMBUNGAUTO', 'sambung'],
  ['5', 'SKBENTROK', 'cek tabrakan'], ['6', 'SKLAYOUT', 'gambar kerja'], ['7', 'SKFABRIKASI', 'gambar bengkel'], ['8', 'SKEXCEL', 'hitung bahan']];
function drawFlow(ctx, w, h, alpha) {
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.fillStyle = '#ffe7a8'; ctx.textAlign = 'center'; ctx.font = `700 ${Math.round(h * 0.06)}px Cinzel, serif`;
  ctx.fillText('Urutan Desain Steel Kit', w / 2, h * 0.13);
  const cols = 4, cw = w * 0.21, chh = h * 0.27, gx = w * 0.02, x0 = (w - cols * cw - (cols - 1) * gx) / 2;
  FLOW.forEach(([n, c, t], i) => {
    const x = x0 + (i % cols) * (cw + gx), y = h * 0.2 + Math.floor(i / cols) * (chh + h * 0.04);
    ctx.fillStyle = 'rgba(0,0,0,.4)'; ctx.fillRect(x, y, cw, chh);
    ctx.strokeStyle = 'rgba(224,169,74,.55)'; ctx.lineWidth = 2; ctx.strokeRect(x, y, cw, chh);
    ctx.fillStyle = '#e0a94a'; ctx.beginPath(); ctx.arc(x + cw / 2, y + chh * 0.25, h * 0.032, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#2a1606'; ctx.font = `700 ${Math.round(h * 0.034)}px Cinzel, serif`; ctx.fillText(n, x + cw / 2, y + chh * 0.25 + h * 0.012);
    ctx.fillStyle = '#ffe7a8'; ctx.font = `600 ${Math.round(h * 0.034)}px Consolas, monospace`; ctx.fillText(c, x + cw / 2, y + chh * 0.6);
    ctx.fillStyle = '#d9c6a2'; ctx.font = `italic ${Math.round(h * 0.034)}px "EB Garamond", serif`; ctx.fillText(t, x + cw / 2, y + chh * 0.82);
  });
  ctx.restore();
}
const slideImgs = SLIDES.map(s => { const im = new Image(); if (s.img) im.src = 'img/' + s.img + '.webp'; return im; });
const SLIDE_T = 4.5;
function drawDemo(ctx, w, h, t) {
  const n = SLIDES.length, total = n * SLIDE_T, tt = ((t % total) + total) % total;
  const i = Math.floor(tt / SLIDE_T), f = (tt - i * SLIDE_T) / SLIDE_T;
  ctx.fillStyle = '#100a07'; ctx.fillRect(0, 0, w, h);
  const draw = (k, alpha, prog) => {
    if (!SLIDES[k].img) { drawFlow(ctx, w, h * 0.86, alpha); return; }
    const im = slideImgs[k]; if (!im.complete || !im.naturalWidth) return;
    const s = Math.min(w / im.width, (h * 0.84) / im.height) * (1 + prog * 0.05);
    ctx.globalAlpha = alpha; drawShot(ctx, im, SLIDES[k].img, (w - im.width * s) / 2, (h * 0.84 - im.height * s) / 2 + h * 0.02, im.width * s, im.height * s); ctx.globalAlpha = 1;
  };
  draw(i, 1, f); if (f > 0.85) draw((i + 1) % n, (f - 0.85) / 0.15, 0);
  ctx.fillStyle = 'rgba(14,9,7,.94)'; ctx.fillRect(0, h * 0.86, w, h * 0.14);
  ctx.fillStyle = '#ffe7a8'; ctx.font = `600 ${Math.round(h * 0.04)}px "EB Garamond", serif`; ctx.textAlign = 'left';
  ctx.fillText(SLIDES[i].cap, w * 0.04, h * 0.94);
  ctx.fillStyle = 'rgba(224,169,74,.25)'; ctx.fillRect(0, h - 5, w, 5);
  ctx.fillStyle = '#e0a94a'; ctx.fillRect(0, h - 5, w * tt / total, 5);
}
function rrShape(s, x, y, w, h, r) { s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y); }
const demoCv = document.createElement('canvas'); demoCv.width = 1024; demoCv.height = 576;
const demoTex = new THREE.CanvasTexture(demoCv); demoTex.colorSpace = THREE.SRGBColorSpace;
const mirror = new THREE.Group(); mirror.position.set(0, 5.6, TABLE.z - 6.5); scene.add(mirror);
let demoPlane;
{
  const fr = new THREE.Shape(); rrShape(fr, -2.75, -1.7, 5.5, 3.4, 0.4);
  const hole = new THREE.Path(); rrShape(hole, -2.45, -1.4, 4.9, 2.8, 0.15); fr.holes.push(hole);
  mesh(new THREE.ExtrudeGeometry(fr, { depth: 0.14, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 2 }), M.gold, 0, 0, -0.07, mirror);
  demoPlane = new THREE.Mesh(new THREE.PlaneGeometry(4.9, 2.76), new THREE.MeshBasicMaterial({ map: demoTex, color: new THREE.Color(0.85, 0.82, 0.78) }));
  demoPlane.userData.demo = true; mirror.add(demoPlane);
  const crest = new THREE.Mesh(new THREE.ConeGeometry(0.35, 0.5, 4), M.gold); crest.position.y = 1.95; crest.rotation.y = Math.PI / 4; mirror.add(crest);
}

// ------------------------------------------------------------------ kamera
const introPath = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0, 2.4, FZ + 11), new THREE.Vector3(0, 2.5, FZ + 6), new THREE.Vector3(0, 2.7, FZ + 1.5),
  new THREE.Vector3(0, 3.0, FZ - 4), new THREE.Vector3(0, 3.0, TABLE.z + 12),
]);
const introLook = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0, 2.8, FZ), new THREE.Vector3(0, 2.8, FZ - 2), new THREE.Vector3(0, 2.6, FZ - 8),
  new THREE.Vector3(0, 2.2, TABLE.z), new THREE.Vector3(0, 2.0, TABLE.z),
]);
// s = geser bingkai: benda condong ke sisi yang berlawanan dengan panel teks
const KEYS = {
  masuk: { p: [0, 3.0, TABLE.z + 12], l: [0, 2.0, TABLE.z], s: -0.16 },
  fitur: { p: [-5.2, 3.2, TABLE.z + 5.2], l: [0.4, 2.0, TABLE.z], s: 0 },
  pengenalan: { p: [0.6, 3.6, TABLE.z + 4.2], l: [0, 5.2, TABLE.z - 6.5], s: -0.2 },
  urutan: { p: [-3.6, 4.4, TABLE.z + 10.5], l: [0.2, 2.6, TABLE.z - 2], s: 0 },
  pasang: { p: [4.8, 3.6, TABLE.z + 7.2], l: [-0.6, 1.6, TABLE.z], s: 0 },
  unduh: { p: [TABLE.x + 0.55, 2.95, TABLE.z + 3.9], l: [TABLE.x + 0.35, 1.45, TABLE.z + 0.1], s: -0.12, sy: 0.14 },
  apresiasi: { p: [6.5, 3.8, TABLE.z + 9], l: [-6, 4.4, TABLE.z - 5], s: 0 },
};
const FOCUS = {
  masuk: TABLE.clone().setY(1.6), fitur: TABLE.clone().setY(2.2), pengenalan: mirror.position.clone(), urutan: TABLE.clone().setY(2.4), pasang: TABLE.clone().setY(1.5),
  unduh: TABLE.clone().add(new THREE.Vector3(0.4, 1.4, 0.2)), apresiasi: new THREE.Vector3(0, 3.5, TABLE.z),
};
const SECS = Object.keys(KEYS);
const secEls = SECS.map(id => document.getElementById(id));
const camPos = new THREE.Vector3(), camLook = new THREE.Vector3(), tgtPos = new THREE.Vector3(), tgtLook = new THREE.Vector3();
const secW = {};
let viewShift = 0, tgtShift = 0, galleryOn = 0, viewShiftY = 0, tgtShiftY = 0;
const focusPt = new THREE.Vector3(), tgtFocus = new THREE.Vector3(), kp = new THREE.Vector3(), kl = new THREE.Vector3();

let introOn = true, introStart = 0, introT = 0;
const INTRO_DUR = REDUCE ? 0.01 : 7.5;
const FREEZE = Q.get('intro');
const titleEl = $('#introTitle');
function endIntro() {
  if (!introOn) return;
  introOn = false;
  document.body.classList.remove('intro-on');
  titleEl.classList.remove('show');
  camPos.copy(introPath.getPointAt(1)); camLook.copy(introLook.getPointAt(1));
  scrollTo(0, 0);
  if (lenis) { lenis.start(); lenis.scrollTo(0, { immediate: true }); }
  reveal();
}
$('#skip').onclick = endIntro;
addEventListener('wheel', () => introOn && introT > 0.2 && endIntro(), { passive: true });
addEventListener('keydown', e => { if (introOn && (e.key === 'Escape' || e.key === ' ')) endIntro(); });

function scrollTargets() {
  const mid = innerHeight * 0.5;
  let sum = 0;
  for (let i = 0; i < SECS.length; i++) {
    const r = secEls[i].getBoundingClientRect();
    const w = Math.max(0, 1 - Math.abs(r.top + r.height / 2 - mid) / innerHeight);
    secW[SECS[i]] = w; sum += w;
  }
  if (sum < 1e-6) return;    // di luar semua bagian (mis. kaki halaman): kamera tetap
  tgtPos.set(0, 0, 0); tgtLook.set(0, 0, 0); tgtFocus.set(0, 0, 0); tgtShift = 0; tgtShiftY = 0;
  for (const id of SECS) {
    const w = secW[id] / sum, k = KEYS[id]; secW[id] = w;
    tgtPos.addScaledVector(kp.fromArray(k.p), w); tgtLook.addScaledVector(kl.fromArray(k.l), w);
    tgtFocus.addScaledVector(FOCUS[id], w); tgtShift += (MOBILE ? 0 : k.s) * w; tgtShiftY += (k.sy || 0) * w;
  }
}
const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) e.target.classList.add('in'); }), { threshold: 0.2 });
function reveal() {
  document.querySelectorAll('.reveal').forEach(c => io.observe(c));
  document.querySelectorAll('[data-count]').forEach(el => {
    const to = +el.dataset.count, t0 = performance.now();
    const step = now => { const k = Math.min(1, (now - t0) / 1600); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}

// ------------------------------------------------------------------ penataan lukisan: kisi di sisi panel, tidak bertumpuk
const ndc = new THREE.Vector3(), wp = new THREE.Vector3(), wq = new THREE.Vector3();
const toWorld = (px, py, dist, out) => {
  ndc.set(px / lastW * 2 - 1, -(py / lastH) * 2 + 1, 0.5).unproject(camera);
  return out.copy(ndc).sub(camera.position).normalize().multiplyScalar(dist).add(camera.position);
};
function layoutGallery(time, dt) {
  galleryOn += ((secW.fitur || 0) > 0.5 && !introOn ? 1 : 0) - galleryOn;
  const target = !introOn ? clamp01(((secW.fitur || 0) - 0.35) / 0.3) : 0;
  const panel = $('#fitur .sk-panel').getBoundingClientRect();
  let x0, x1, y0, y1;
  if (lastW > 760) {
    // mulai di bawah kartu apresiasi kecil (kanan atas) supaya tidak bertumpuk
    const hk = document.querySelector('.appre-hook'), hb = hk && !hk.classList.contains('away') ? hk.getBoundingClientRect().bottom : 70;
    x0 = Math.max(panel.right + 28, lastW * 0.42); x1 = lastW - 28; y0 = Math.max(84, hb + 16); y1 = lastH - 40;
  }
  else { x0 = 12; x1 = lastW - 12; y0 = 70; y1 = Math.max(200, panel.top - 14); }
  const n = cardMeshes.length, wide = (x1 - x0) > (y1 - y0) * 1.1;
  const cols = wide ? 4 : 2, rows = Math.ceil(n / cols);
  const cw = (x1 - x0) / cols, ch = (y1 - y0) / rows;
  const pw = Math.min(cw * 0.9, ch * 0.88 / CARD_ASPECT);
  const dist = 3;
  cardMeshes.forEach((m, i) => {
    const op = m.material.opacity + (target - m.material.opacity) * (1 - Math.exp(-dt * 6));
    m.material.opacity = op; m.visible = op > 0.02;
    if (!m.visible) return;
    const c = i % cols, r = Math.floor(i / cols);
    const cx = x0 + cw * (c + 0.5), cy = y0 + ch * (r + 0.5) + Math.sin(time * 0.8 + i) * 3 + (1 - op) * 24;
    toWorld(cx, cy, dist, wp);
    toWorld(cx + pw, cy, dist, wq);
    const hover = m === hovered ? 1.05 : 1;
    m.position.copy(wp); m.quaternion.copy(camera.quaternion);
    m.scale.setScalar(wp.distanceTo(wq) * hover);
  });
}

// ------------------------------------------------------------------ interaksi (lewat jendela: bagian halaman menutupi kanvas)
const UI_SEL = 'a, button, input, summary, details, .panel, .topbar, .app-menu, .appre-hook, .lead, .hint, h1, h2, .sub, .steps, .qris-altar, .sk-viewer, .sk-modal, footer';
const isUI = t => !!(t && t.closest && t.closest(UI_SEL));
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2(-9, -9);
let hovered = null, mouseMoved = true, dragging = false, pointerX = 0, pointerY = 0;
addEventListener('pointermove', e => { mouse.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); pointerX = e.clientX; pointerY = e.clientY; mouseMoved = true; });
function pick(e) {
  ray.setFromCamera(mouse.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  const objs = [...cardMeshes.filter(m => m.visible && m.material.opacity > 0.5), demoPlane, holeHit, boltHit];
  return ray.intersectObjects(objs, false)[0];
}
addEventListener('pointerdown', e => {
  if (introOn || isUI(e.target) || e.button > 0) return;
  const h = pick(e);
  if (!h) return;
  if (h.object === boltHit && !installed && !installing) { startDrag(e); return; }
  if (h.object === holeHit && !installed && !installing) { autoInstall(); return; }
  if (h.object.userData.demo) { openPlayer(); return; }
  if (h.object.userData.card !== undefined) openViewer(h.object.userData.card);
});

// ------------------------------------------------------------------ penampil lukisan satu layar penuh
const viewer = $('#viewer');
let vIndex = 0;
function openViewer(i) {
  vIndex = (i + CARDS.length) % CARDS.length;
  const c = CARDS[vIndex];
  const img = $('#viewerImg');
  img.src = 'img/full/' + c.img + '.webp'; img.alt = c.title;
  $('#viewerStep').textContent = c.step || '';
  $('#viewerTitle').textContent = c.title;
  $('#viewerLead').textContent = c.lead;
  const pins = $('#viewerPins'), list = $('#viewerNotes');
  pins.innerHTML = ''; list.innerHTML = '';
  c.notes.forEach(([x, y, t], k) => {
    const pin = document.createElement('span'); pin.className = 'sk-pin'; pin.textContent = k + 1;
    pin.style.left = x + '%'; pin.style.top = y + '%'; pins.appendChild(pin);
    const li = document.createElement('li'); li.textContent = t; list.appendChild(li);
    const on = v => { pin.classList.toggle('on', v); li.classList.toggle('on', v); };
    for (const el of [pin, li]) { el.addEventListener('mouseenter', () => on(true)); el.addEventListener('mouseleave', () => on(false)); }
  });
  viewer.hidden = false;
  if (lenis) lenis.stop();
}
function closeViewer() { viewer.hidden = true; if (lenis && !dragging) lenis.start(); }
viewer.querySelector('.sk-x').onclick = closeViewer;
$('#vPrev').onclick = () => openViewer(vIndex - 1);
$('#vNext').onclick = () => openViewer(vIndex + 1);
viewer.addEventListener('click', e => { if (e.target === viewer || e.target.classList.contains('sk-viewer-stage')) closeViewer(); });

// pemutar video pengenalan
const player = $('#player'), pcv = $('#playerCanvas'), pctx = pcv.getContext('2d');
let playerOn = false, playerT = 0, playerPlay = true;
function openPlayer() { player.hidden = false; playerOn = true; playerT = 0; playerPlay = true; $('#pPlay').textContent = '⏸'; if (lenis) lenis.stop(); }
function closePlayer() { player.hidden = true; playerOn = false; if (lenis) lenis.start(); }
player.addEventListener('click', e => { if (e.target === player || e.target.classList.contains('sk-x')) closePlayer(); });
$('#playDemo').onclick = openPlayer;
$('#pPlay').onclick = () => { playerPlay = !playerPlay; $('#pPlay').textContent = playerPlay ? '⏸' : '▶'; };
$('#pNext').onclick = () => { playerT = (Math.floor(playerT / SLIDE_T) + 1) * SLIDE_T; };
$('#pPrev').onclick = () => { playerT = Math.max(0, (Math.floor(playerT / SLIDE_T) - 1) * SLIDE_T); };
addEventListener('keydown', e => {
  if (e.key === 'Escape') { if (!viewer.hidden) closeViewer(); if (playerOn) closePlayer(); }
  if (!viewer.hidden && e.key === 'ArrowRight') openViewer(vIndex + 1);
  if (!viewer.hidden && e.key === 'ArrowLeft') openViewer(vIndex - 1);
});

// ------------------------------------------------------------------ baut terakhir: diseret kursor ke lubang, lalu terpasang otomatis
const bolt = horizBolt();                       // baut yang tergeletak di tatakan
const boltRest = new THREE.Vector3().copy(TRAY).add(TABLE);
const restRot = new THREE.Euler(0, 0.5, -Math.PI / 2);
bolt.position.copy(boltRest); bolt.rotation.copy(restRot);
scene.add(bolt);
const boltHit = new THREE.Mesh(new THREE.SphereGeometry(0.13, 8, 8), new THREE.MeshBasicMaterial({ visible: false }));
scene.add(boltHit);
const pickRing = new THREE.Mesh(new THREE.RingGeometry(0.09, 0.12, 40), M.pickGlow);
pickRing.rotation.x = -Math.PI / 2; pickRing.position.copy(boltRest).setY(TABLE.y + TOP + 0.014); scene.add(pickRing);
const nut = hexPrism(BOLT_D * 0.95, BOLT_D * 0.85, M.galv); nut.rotation.z = Math.PI / 2; nut.visible = false; scene.add(nut);
const sparks = makeSparks(); scene.add(sparks.points);
const dlBtn = $('#dl'), msg = $('#installMsg'), autoBtn = $('#autoBolt'), boltText = $('#boltText');
const guide = $('#boltGuide'), guidePath = $('#boltPath'), call = $('#boltCall');
let installing = null, installed = false, flash = 0, returning = null;
const dragPlane = new THREE.Plane(), dragHit = new THREE.Vector3(), camDir = new THREE.Vector3();
const INSERT = new THREE.Vector3(0.32, 0, 0);   // titik siap masuk: di luar lubang searah sumbu baut

function startDrag(e) {
  dragging = true;
  document.body.classList.add('dragging');
  if (lenis) lenis.stop();
  camera.getWorldDirection(camDir);
  dragPlane.setFromNormalAndCoplanarPoint(camDir.clone().negate(), H0.clone().add(INSERT));
  e.preventDefault();
}
addEventListener('pointermove', e => {
  if (!dragging) return;
  ray.setFromCamera(mouse.set(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  if (ray.ray.intersectPlane(dragPlane, dragHit)) {
    bolt.position.lerp(dragHit, 0.6);
    const near = clamp01(1 - bolt.position.distanceTo(H0.clone().add(INSERT)) / 0.6);
    bolt.rotation.set(mix(0.4, 0, near), mix(0.5, 0, near), -Math.PI / 2);
  }
});
addEventListener('pointerup', () => {
  if (!dragging) return;
  dragging = false;
  document.body.classList.remove('dragging');
  if (lenis && viewer.hidden) lenis.start();
  // cukup dekat dengan lubang (layar atau ruang): masuk otomatis
  const a = bolt.position.clone().project(camera), b = H0.clone().add(INSERT).project(camera);
  const px = Math.hypot((a.x - b.x) * lastW / 2, (a.y - b.y) * lastH / 2);
  if (px < 90 || bolt.position.distanceTo(H0.clone().add(INSERT)) < 0.25) startInstall(bolt.position.clone(), true);
  else returning = { t: 0, from: bolt.position.clone() };
});
autoBtn.onclick = () => { if (!installed && !installing) autoInstall(); };
function autoInstall() {
  if (!$('#unduh').getBoundingClientRect || Math.abs($('#unduh').getBoundingClientRect().top) > innerHeight * 0.4) scrollToEl($('#unduh'), 1.4);
  startInstall(bolt.position.clone(), false);
}
function startInstall(from, snapped) {
  if (installing || installed) return;
  const out = H0.clone().add(INSERT);
  installing = { t: snapped ? 0.6 : 0, snapped, curve: new THREE.CatmullRomCurve3([from, from.clone().lerp(out, 0.5).add(new THREE.Vector3(0, 0.5, 0.15)), out]) };
  autoBtn.disabled = true;
  boltText.textContent = 'Baut sedang dipasang…';
}
function updateInstall(dt) {
  if (returning) {
    returning.t = Math.min(1, returning.t + dt * 2.2);
    bolt.position.lerpVectors(returning.from, boltRest, smooth(returning.t));
    bolt.rotation.copy(restRot);
    if (returning.t >= 1) returning = null;
  }
  if (!installing) return;
  const s = installing; s.t += dt * (REDUCE ? 4 : 1);
  const tFly = 1.1, tThread = 1.3, tNut = 0.9, spin = bolt.userData.spin;
  if (s.t < tFly) {
    const k = smooth(s.t / tFly);
    bolt.position.copy(s.curve.getPointAt(k));
    bolt.rotation.set((1 - k) * 0.6, (1 - k) * 0.8, -Math.PI / 2);
  } else if (s.t < tFly + tThread) {
    const k = (s.t - tFly) / tThread;
    bolt.rotation.set(0, 0, -Math.PI / 2);
    spin.rotation.y = k * Math.PI * 8;
    bolt.position.copy(H0).add(new THREE.Vector3(INSERT.x * (1 - smooth(k)), 0, 0));
    M.holeGlow.opacity = 1 - k;
  } else if (s.t < tFly + tThread + tNut) {
    const k = (s.t - tFly - tThread) / tNut;
    bolt.position.copy(H0); holeRing.visible = false;
    nut.visible = true;
    nut.position.set(NUT_X - 0.25 * (1 - smooth(k)), H0.y, H0.z);
    nut.rotation.x = k * Math.PI * 6;
  } else {
    installing = null; installed = true;
    sparks.burst(H0); flash = 1;
    pickRing.visible = false;
    dlBtn.classList.remove('locked'); dlBtn.classList.add('ready');
    dlBtn.removeAttribute('aria-disabled'); dlBtn.href = DOWNLOAD; dlBtn.textContent = '⬇ Unduh SteelKitSetup.exe';
    autoBtn.hidden = true;
    boltText.textContent = 'Baut terpasang, sambungannya utuh. Tombol unduh sudah terbuka.';
    msg.textContent = 'SteelKitSetup.exe · sekitar 2 MB · AutoCAD 2021–2027 · Windows 10/11';
  }
}
function makeSparks() {
  const n = 180, g = new THREE.BufferGeometry(), pos = new Float32Array(n * 3), vel = new Float32Array(n * 3);
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const m = new THREE.PointsMaterial({ color: '#ffd08a', size: 0.018, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  const points = new THREE.Points(g, m); points.frustumCulled = false;
  let life = 0;
  return {
    points,
    burst(at) {
      for (let i = 0; i < n; i++) {
        pos[i * 3] = at.x + 0.02; pos[i * 3 + 1] = at.y; pos[i * 3 + 2] = at.z;
        const a = Math.random() * Math.PI * 2, u = Math.random();
        vel[i * 3] = 0.4 + Math.random() * 1.2; vel[i * 3 + 1] = Math.sin(a) * u * 1.4 + 0.6; vel[i * 3 + 2] = Math.cos(a) * u * 1.4;
      }
      life = 1.2; m.opacity = 1; g.attributes.position.needsUpdate = true;
    },
    update(dt) {
      if (life <= 0) return;
      life -= dt; m.opacity = Math.max(0, life / 1.2);
      for (let i = 0; i < n; i++) { vel[i * 3 + 1] -= 3.5 * dt; pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt; }
      g.attributes.position.needsUpdate = true;
    },
  };
}
// panah panduan dari baut ke lubang (gaya yang sama dengan bata kunci di halaman Gesture)
const sa = new THREE.Vector3(), sb = new THREE.Vector3();
function updateGuide() {
  const show = !introOn && !installed && !installing && (secW.unduh || 0) > 0.45 && viewer.hidden && !playerOn;
  guide.classList.toggle('on', show && !dragging);
  call.classList.toggle('on', show && !dragging);
  if (!show) return;
  sa.copy(bolt.position).project(camera); sb.copy(H0).add(INSERT).project(camera);
  const ax = (sa.x + 1) / 2 * lastW, ay = (1 - sa.y) / 2 * lastH, bx = (sb.x + 1) / 2 * lastW, by = (1 - sb.y) / 2 * lastH;
  const mx = (ax + bx) / 2, my = Math.min(ay, by) - Math.max(60, Math.abs(ax - bx) * 0.35);
  guidePath.setAttribute('d', `M${(ax - 6).toFixed(1)} ${(ay - 18).toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${(bx + 14).toFixed(1)} ${(by - 6).toFixed(1)}`);
  call.style.left = ax + 'px'; call.style.top = (ay - 26) + 'px';
}

// ------------------------------------------------------------------ ukuran & kualitas adaptif (FPS tinggi di laptop biasa)
let lastW = 0, lastH = 0;
function fitSize(force) {
  const w = innerWidth, h = innerHeight;
  if (w < 2 || h < 2 || (!force && w === lastW && h === lastH)) return;
  lastW = w; lastH = h;
  camera.aspect = w / h; camera.updateProjectionMatrix();
  renderer.setPixelRatio(pr);
  renderer.setSize(w, h); composer.setSize(w, h); bloom.setSize(w * 0.5, h * 0.5);
}
addEventListener('resize', () => fitSize());
let fpsAcc = 0, fpsN = 0, fpsT = 0;
function adapt(dt) {
  fpsAcc += dt; fpsN++; fpsT += dt;
  if (fpsT < 1.5) return;
  const avg = fpsAcc / fpsN; fpsAcc = fpsN = fpsT = 0;
  if (avg > 1 / 45 && pr > MIN_PR) { pr = Math.max(MIN_PR, pr - 0.25); fitSize(true); }
  else if (avg < 1 / 58 && pr < MAX_PR) { pr = Math.min(MAX_PR, pr + 0.125); fitSize(true); }
}

// ------------------------------------------------------------------ putaran animasi
const clock = new THREE.Clock(), focusEl = $('#focus'), tmpV = new THREE.Vector3();
let demoAcc = 0, demoT = 0, shadowFrames = 6;
function frame() {
  requestAnimationFrame(frame);
  fitSize(); if (lastW < 2) return;
  const dt = Math.min(clock.getDelta(), 0.05), time = clock.elapsedTime;
  if (!document.hidden) adapt(dt);
  if (introOn) {
    introT = FREEZE !== null ? +FREEZE : clamp01((performance.now() - introStart) / 1000 / INTRO_DUR);
    const k = introT < 0.18 ? 0 : smooth((introT - 0.18) / 0.82);
    camPos.copy(introPath.getPointAt(k)); camLook.copy(introLook.getPointAt(k));
    tgtShift = 0; tgtFocus.copy(camLook);
    titleEl.classList.toggle('show', introT > 0.05 && introT < 0.62);
    if (introT >= 1 && FREEZE === null) endIntro();
    shadowFrames = 2;
  } else {
    scrollTargets();
    const a = 1 - Math.exp(-dt * 3.2);
    camPos.lerp(tgtPos, a); camLook.lerp(tgtLook, a);
  }
  viewShift += (tgtShift - viewShift) * (1 - Math.exp(-dt * 3.2));
  viewShiftY += ((introOn ? 0 : tgtShiftY) - viewShiftY) * (1 - Math.exp(-dt * 3.2));
  focusPt.lerp(tgtFocus, 1 - Math.exp(-dt * 3));
  const open = introOn ? clamp01((introT - 0.12) / 0.3) : 1;
  for (const d of doors) d.pivot.rotation.y = d.s * -smooth(open) * 1.6;
  camera.position.copy(camPos);
  if (!introOn && !MOBILE && !dragging) { camera.position.x += mouse.x * 0.08; camera.position.y += mouse.y * 0.04; }
  camera.lookAt(camLook);
  camera.setViewOffset(lastW, lastH, -viewShift * lastW, viewShiftY * lastH, lastW, lastH);
  camera.updateMatrixWorld();

  tmpV.copy(focusPt).project(camera);
  focusEl.style.setProperty('--fx', (50 + tmpV.x * 50).toFixed(1) + '%');
  focusEl.style.setProperty('--fy', (50 - tmpV.y * 50).toFixed(1) + '%');

  layoutGallery(time, dt);
  if (mouseMoved && !dragging && !introOn) {
    mouseMoved = false;
    ray.setFromCamera(mouse, camera);
    const h = ray.intersectObjects([...cardMeshes.filter(m => m.visible), demoPlane, holeHit, boltHit], false)[0];
    hovered = h ? h.object : null;
    document.body.style.cursor = hovered ? (hovered === boltHit && !installed ? 'grab' : 'pointer') : '';
  }
  boltHit.position.copy(bolt.position);
  if (holeRing.visible) holeRing.scale.setScalar(1 + Math.sin(time * 4) * 0.18);
  if (pickRing.visible) { pickRing.material.opacity = 0.45 + Math.sin(time * 3.2) * 0.35; pickRing.position.x = bolt.position.x; pickRing.position.z = bolt.position.z; pickRing.visible = !dragging && !installing; }
  if (!installed && !installing && !dragging && !returning) bolt.position.y = boltRest.y + Math.max(0, Math.sin(time * 2.4)) * 0.012;
  mirror.position.y = 5.6 + Math.sin(time * 0.7) * 0.05;
  for (const f of flames) f.scale.x = f.scale.z = 1 + Math.sin(time * 11 + f.position.x * 5 + f.position.z) * 0.12;
  for (const b of swayers) b.rotation.y = Math.sin(time * 0.9 + b.position.x) * 0.05;

  // layar video: 24 fps saat dilihat, 8 fps saat jauh
  demoAcc += dt; demoT += dt;
  const fpsDemo = (secW.pengenalan || 0) > 0.2 || introOn ? 24 : 8;
  if (demoAcc > 1 / fpsDemo) { demoAcc = 0; drawDemo(demoCv.getContext('2d'), demoCv.width, demoCv.height, demoT); demoTex.needsUpdate = true; }
  if (playerOn) { if (playerPlay) playerT += dt; drawDemo(pctx, pcv.width, pcv.height, playerT); }
  updateInstall(dt); sparks.update(dt); updateGuide();
  if (flash > 0) { flash = Math.max(0, flash - dt * 0.8); bloom.strength = 0.22 + flash * 0.6; }
  if (installing || dragging || returning || shadowFrames > 0) { renderer.shadowMap.needsUpdate = true; if (shadowFrames > 0) shadowFrames--; }
  composer.render();
}

(document.fonts ? document.fonts.ready : Promise.resolve()).then(() => {
  fitSize();
  camPos.copy(introPath.getPointAt(0)); camLook.copy(introLook.getPointAt(0)); focusPt.copy(camLook);
  if (lastW > 1) renderer.compile(scene, camera);
  document.documentElement.classList.add('ready3d');
  const fromGate = Q.get('dari') === 'gerbang';
  setTimeout(() => $('#skVeil').classList.add('gone'), fromGate ? 200 : 600);
  introStart = performance.now() + (fromGate ? 300 : 800);
  const SEC = Q.get('sec');
  if (REDUCE || (SEC && KEYS[SEC])) {
    endIntro();
    if (SEC && KEYS[SEC]) {
      document.getElementById(SEC).scrollIntoView();
      const k = KEYS[SEC]; camPos.set(...k.p); camLook.set(...k.l); viewShift = MOBILE ? 0 : k.s; viewShiftY = k.sy || 0; focusPt.copy(FOCUS[SEC]);
      document.querySelectorAll('.reveal').forEach(c => c.classList.add('in'));
    }
  }
  requestAnimationFrame(frame);
});
