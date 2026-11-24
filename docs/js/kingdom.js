// Adegan 3D "kerajaan senja": istana batu di pulau melayang, tanah bersigil, air terjun, konstruksi baja yang
// bisa diklik, pulau-pulau jauh berkabut, kapal udara, panji merah, bara api, dan awan senja.
// Kamera mengikuti gulir halaman.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { cloudCanvas, mulberry32, DUSK, DUSK_LIT } from './cloud.js';

const INFO = {
  castle: { title: 'Istana Gesture Control', text: 'Dibangun dari satu penginstal saja. Ketik GK di AutoCAD buat membuka gerbangnya, ketik lagi buat menutupnya.' },
  beam: { title: 'Balok WF', text: 'Profil sayap lebar, biasa dipakai buat balok dan rafter. Di AutoCAD, model seperti ini bisa Anda putar pakai dua kepalan ✊✊.' },
  column: { title: 'Kolom H', text: 'Berdiri di atas pelat dasar dengan empat baut angkur. Mau menggeser tampilan? Pakai dua cubitan 🤏🤏.' },
  truss: { title: 'Rangka batang', text: 'Batang atas, batang bawah, dan diagonalnya. Rentangkan dua tangan pelan-pelan untuk zoom.' },
  bolts: { title: 'Kelompok baut', text: 'Baut, mur, dan ring di pelat ujung. Jepit lalu lepas 🤏, itu sama dengan satu klik.' },
  plate: { title: 'Pelat buhul', text: 'Pelat sambungan berlubang. Tahan 🤙 sebentar, menu perintah AutoCAD langsung muncul.' },
  portal: { title: 'Rangka portal baja', text: 'Kolom, rafter, dan gordingnya lagi dirakit. Telunjuk ☝ menggerakkan kursor; makin pelan, makin presisi.' },
  crystal: { title: 'Kristal kamera', text: 'Sumber sihirnya kamera laptop Anda. Gambar tangan cuma diproses di komputer Anda, nggak dikirim ke mana-mana.' },
  airship: { title: 'Kapal udara kurir', text: 'Tugasnya mengantar penginstal ke laptop Anda. Sekitar 80 MB, gratis ongkos kirim.' },
};

// Posisi kamera per bagian halaman: p = posisi, l = titik pandang, f = fokus untuk layar tegak (ponsel).
const KEYS = {
  istana: { p: [19, 14, 66], l: [-12, 9, 0], f: [0, 10, 0] },
  tentang: { p: [-14, 12, 24], l: [-32, 8, -8], f: [-36, 9, -10] },
  pasang: { p: [46, 34, 46], l: [0, 4, 0] },
  gestur: { p: [40, 11, -24], l: [8, 11, -2], f: [0, 10, 0] },
  menara: { p: [-6, 70, 30], l: [0, 0, -2] },
  tanya: { p: [-48, 7, 30], l: [-4, 9, 0], f: [0, 9, 0] },
  apresiasi: { p: [0, 3, 76], l: [0, 14, 0] },
  privasi: { p: [0, -6, 88], l: [0, 12, 0] },
};
const INTRO = { p: [0, 46, 205], l: [0, 12, 0] };

export function start(o) {
  const reduced = !!o.reduced;
  const mobile = !!o.mobile;
  const canvas = o.canvas;
  const html = document.documentElement;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !mobile && devicePixelRatio < 2, powerPreference: 'high-performance' });
  const maxPR = Math.min(devicePixelRatio || 1, mobile ? 1.5 : 1.75);
  const minPR = mobile ? 0.75 : 1;
  let pr = maxPR;
  renderer.setPixelRatio(pr);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.3;
  const shadows = !mobile;
  if (shadows) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2('#8a4c34', 0.0034);
  const camera = new THREE.PerspectiveCamera(mobile ? 52 : 42, innerWidth / innerHeight, 0.5, 2400);

  // lingkungan pantul hanya untuk logam (batu & rumput tidak ikut, supaya suasana senja tetap gelap)
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  pmrem.dispose();

  const rnd = mulberry32(2024);
  const R = (a, b) => a + (b - a) * rnd();
  const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);

  // posisi kamera di semua bagian (desktop & ponsel): awan dan pulau jauh tidak boleh menutupinya
  const camSpots = [];
  for (const k of Object.values(KEYS)) for (const d of [1, 1.3, 1.7]) {
    const l = V(k.l);
    if (d > 1 && k.f) l.lerp(V(k.f), 0.75);
    camSpots.push(V(k.p).sub(l).multiplyScalar(d).add(l));
  }
  const tmpC = new THREE.Vector3();
  const clear = (x, y, z, rad) => camSpots.every((c) => c.distanceTo(tmpC.set(x, y, z)) > rad);

  // ------------------------------------------------------------ tekstur prosedural
  function canvasTex(w, h, draw, srgb = true, repeat = false) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    draw(c.getContext('2d'), w, h);
    const t = new THREE.CanvasTexture(c);
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; }
    return t;
  }
  const speck = (x, r, w, h, n, light, dark) => {
    for (let i = 0; i < n; i++) {
      x.fillStyle = r() > 0.5 ? `rgba(${light},${r() * 0.16})` : `rgba(${dark},${r() * 0.28})`;
      x.fillRect(r() * w, r() * h, 1 + r() * 2.5, 1 + r() * 2.5);
    }
  };
  const stoneTex = canvasTex(512, 512, (x, w, h) => {
    const r = mulberry32(11);
    x.fillStyle = '#4a3d32'; x.fillRect(0, 0, w, h);
    const rows = 8, rh = h / rows;
    for (let j = 0; j < rows; j++) {
      let px = -r() * 50;
      while (px < w) {
        const bw = 46 + r() * 56, v = 0.72 + r() * 0.36;
        const col = `rgb(${(178 * v) | 0},${(160 * v) | 0},${(136 * v) | 0})`;
        for (const sx of [px, px - w, px + w]) {
          x.fillStyle = col; x.fillRect(sx + 2, j * rh + 2, bw - 4, rh - 4);
          x.fillStyle = 'rgba(255,230,190,.12)'; x.fillRect(sx + 2, j * rh + 2, bw - 4, 3);
          x.fillStyle = 'rgba(0,0,0,.28)'; x.fillRect(sx + 2, j * rh + rh - 6, bw - 4, 4);
        }
        px += bw;
      }
    }
    speck(x, r, w, h, 5000, '255,235,200', '20,12,6');
    for (let i = 0; i < 70; i++) { x.fillStyle = `rgba(28,18,10,${r() * 0.14})`; x.fillRect(r() * w, r() * h, 2 + r() * 7, 20 + r() * 140); }
  }, true, true);
  const roofTex = canvasTex(256, 256, (x, w, h) => {
    const r = mulberry32(5);
    x.fillStyle = '#1e232c'; x.fillRect(0, 0, w, h);
    const th = 22, tw = 26;
    for (let j = 0; j * th < h + th; j++) {
      for (let i = -1; i * tw < w + tw; i++) {
        const cx = i * tw + (j % 2 ? tw / 2 : 0), cy = j * th;
        const v = 0.7 + r() * 0.45;
        x.fillStyle = `rgb(${(60 * v) | 0},${(70 * v) | 0},${(86 * v) | 0})`;
        x.beginPath(); x.moveTo(cx - tw / 2 + 1, cy); x.lineTo(cx + tw / 2 - 1, cy); x.lineTo(cx + tw / 2 - 1, cy + th * 0.6);
        x.quadraticCurveTo(cx, cy + th * 1.15, cx - tw / 2 + 1, cy + th * 0.6); x.closePath(); x.fill();
        x.strokeStyle = 'rgba(0,0,0,.45)'; x.lineWidth = 1.2; x.stroke();
      }
    }
    speck(x, r, w, h, 1200, '200,210,230', '0,0,0');
  }, true, true);
  const rockTex = canvasTex(512, 512, (x, w, h) => {
    const r = mulberry32(17);
    x.fillStyle = '#7a6656'; x.fillRect(0, 0, w, h);
    for (let i = 0; i < 26; i++) { x.fillStyle = `rgba(${r() > 0.5 ? '40,26,20' : '170,140,110'},${0.08 + r() * 0.12})`; x.fillRect(0, r() * h, w, 3 + r() * 16); }
    speck(x, r, w, h, 9000, '230,200,170', '15,8,5');
    x.strokeStyle = 'rgba(15,8,5,.45)'; x.lineWidth = 1.4;
    for (let i = 0; i < 40; i++) {
      let px = r() * w, py = r() * h;
      x.beginPath(); x.moveTo(px, py);
      for (let k = 0; k < 5; k++) { px += (r() - 0.5) * 30; py += r() * 26; x.lineTo(px, py); }
      x.stroke();
    }
  }, true, true);
  const grassTex = canvasTex(256, 256, (x, w, h) => {
    const r = mulberry32(23);
    x.fillStyle = '#3a4423'; x.fillRect(0, 0, w, h);
    for (let i = 0; i < 4000; i++) {
      const c = [[86, 98, 46], [44, 54, 26], [110, 104, 52], [62, 76, 34]][Math.floor(r() * 4)];
      x.fillStyle = `rgba(${c},${0.4 + r() * 0.5})`;
      x.fillRect(r() * w, r() * h, 1 + r() * 2, 1 + r() * 3);
    }
  }, true, true);
  const bannerTex = canvasTex(128, 384, (x, w, h) => {
    const g = x.createLinearGradient(0, 0, w, 0);
    g.addColorStop(0, '#4a0c0c'); g.addColorStop(0.3, '#9a1e1a'); g.addColorStop(0.55, '#7a1414'); g.addColorStop(0.8, '#a32420'); g.addColorStop(1, '#4a0c0c');
    x.fillStyle = g;
    x.beginPath(); x.moveTo(0, 0); x.lineTo(w, 0); x.lineTo(w, h); x.lineTo(w / 2, h * 0.86); x.lineTo(0, h); x.closePath(); x.fill();
    x.strokeStyle = '#d9a24a'; x.lineWidth = 6; x.stroke();
    x.fillStyle = '#e8b456'; x.strokeStyle = '#5a300c'; x.lineWidth = 2;
    const cy = h * 0.36;
    x.beginPath(); x.moveTo(24, cy + 30); x.lineTo(104, cy + 30); x.lineTo(96, cy - 14); x.lineTo(78, cy + 4); x.lineTo(64, cy - 30); x.lineTo(50, cy + 4); x.lineTo(32, cy - 14); x.closePath(); x.fill(); x.stroke();
    x.fillRect(24, cy + 30, 80, 10);
    x.fillStyle = 'rgba(0,0,0,.25)'; for (let i = 0; i < 6; i++) x.fillRect(10 + i * 20, 0, 3, h);
  });

  // ------------------------------------------------------------ bahan
  const std = (c, x = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.92, metalness: 0, ...x });
  const metal = (c, rough, met = 1) => new THREE.MeshStandardMaterial({ color: c, metalness: met, roughness: rough, envMap: envTex, envMapIntensity: 0.55 });
  const M = {
    wall: std('#d8c8ad', { map: stoneTex, bumpMap: stoneTex, bumpScale: 0.6 }),
    trim: std('#b9a586', { map: stoneTex }),
    stone: std('#9a8a74', { map: stoneTex, bumpMap: stoneTex, bumpScale: 0.6 }),
    roof: std('#ffffff', { map: roofTex, bumpMap: roofTex, bumpScale: 0.8, roughness: 0.7 }),
    roof2: std('#d0c0d0', { map: roofTex, roughness: 0.7 }),
    door: std('#24160f'),
    grassSide: std('#8a7060', { map: rockTex }),
    grass: std('#ffffff', { map: grassTex }),
    dirt: std('#4a3528'),
    hill: std('#d8e0c0', { map: grassTex }),
    leaf: std('#2c3d22'), leaf2: std('#3a4e2a'), trunk: std('#3a2a1e'),
    flag: std('#8e1c1c', { side: THREE.DoubleSide, roughness: 0.8 }),
    flag2: std('#c08a2a', { side: THREE.DoubleSide, roughness: 0.6 }),
    banner: std('#ffffff', { map: bannerTex, side: THREE.DoubleSide, alphaTest: 0.5, roughness: 0.8 }),
    rock: std('#ffffff', { map: rockTex, bumpMap: rockTex, bumpScale: 1.2, vertexColors: true }),
    path: std('#8a7458', { map: stoneTex }),
    concrete: std('#8f877c', { map: stoneTex }),
    leather: std('#6e4a30', { roughness: 0.65 }),
    wood: std('#3a2618', { roughness: 0.8 }),
    gold: metal('#e0a94a', 0.3),
    steel: metal('#8a94a2', 0.34, 0.88),
    primer: metal('#9a3a26', 0.55, 0.35),
    galv: metal('#c8cdd4', 0.24),
    water: metal('#3a6070', 0.08, 0.2),
    windowLit: new THREE.MeshBasicMaterial({ color: '#ffaa48', toneMapped: false }),
    crystal: new THREE.MeshBasicMaterial({ color: '#ffb35a', toneMapped: false }),
    bird: new THREE.MeshBasicMaterial({ color: '#140c0a', side: THREE.DoubleSide }),
  };

  const glowTex = canvasTex(128, 128, (x, w) => {
    const g = x.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.25, 'rgba(255,255,255,.55)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, w, w);
  });
  const glow = (color, size, opacity = 1) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    s.scale.set(size, size, 1);
    s.raycast = () => {};
    return s;
  };

  // ------------------------------------------------------------ langit senja
  const sunDir = new THREE.Vector3(-0.19, 0.075, -0.98).normalize();
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1500, 40, 20), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false, toneMapped: false,
    uniforms: {
      top: { value: new THREE.Color('#0d0a17') }, mid: { value: new THREE.Color('#3d2236') },
      hor: { value: new THREE.Color('#e0743a') }, low: { value: new THREE.Color('#5a2a1c') },
      deep: { value: new THREE.Color('#0e0806') }, sun: { value: sunDir }, sunCol: { value: new THREE.Color('#ffc078') },
    },
    vertexShader: 'varying vec3 vD; void main(){ vD = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform vec3 top, mid, hor, low, deep, sun, sunCol; varying vec3 vD;
      void main(){ vec3 d = normalize(vD); float h = d.y;
        vec3 sd = normalize(sun);
        float az = max(dot(normalize(vec2(d.x, d.z) + 1e-5), normalize(vec2(sd.x, sd.z))), 0.0);
        vec3 horizon = mix(hor * 0.55, hor, pow(az, 3.0));
        vec3 c = mix(horizon, mid, smoothstep(0.0, 0.22, h));
        c = mix(c, top, smoothstep(0.22, 0.8, h));
        c = mix(c, low, smoothstep(0.0, -0.08, h));
        c = mix(c, deep, smoothstep(-0.08, -0.5, h));
        float s = max(dot(d, sd), 0.0);
        c += sunCol * (pow(s, 1800.0) * 6.0 + pow(s, 90.0) * 0.9 + pow(s, 9.0) * 0.35 + pow(s, 2.5) * 0.08);
        gl_FragColor = vec4(c, 1.0);
        #include <colorspace_fragment>
      }`,
  }));
  sky.renderOrder = -10;
  scene.add(sky);

  scene.add(new THREE.HemisphereLight('#e0a088', '#3a2014', 1.15));
  // cahaya utama: matahari senja dari kiri depan agar sisi bangunan tersulut jingga (bola matahari tetap di belakang)
  const sunL = new THREE.DirectionalLight('#ffa860', 3.6);
  sunL.position.set(-80, 52, 34);
  if (shadows) {
    sunL.castShadow = true;
    sunL.shadow.mapSize.set(2048, 2048);
    const sc = sunL.shadow.camera;
    sc.left = -32; sc.right = 32; sc.top = 32; sc.bottom = -32; sc.near = 20; sc.far = 260;
    sunL.shadow.bias = -0.0005;
    sunL.shadow.normalBias = 0.05;
  }
  scene.add(sunL);
  const fillL = new THREE.DirectionalLight('#9a7ab0', 1.1);
  fillL.position.set(60, 26, 50);
  const backL = new THREE.DirectionalLight('#ff8a40', 1.6); // sinar tepi dari arah matahari
  backL.position.copy(sunDir).multiplyScalar(100).add(new THREE.Vector3(0, 20, 0));
  scene.add(backL);
  scene.add(fillL);

  // ------------------------------------------------------------ alat bantu geometri
  const UVS = 3.2; // satuan dunia per ulangan tekstur
  function autoUV(g) {
    const uv = g.attributes.uv;
    if (!uv || g.userData.uvDone) return;
    g.userData.uvDone = true;
    const p = g.parameters || {};
    const pos = g.attributes.position;
    if (g.type === 'BoxGeometry') {
      const n = g.attributes.normal;
      for (let i = 0; i < uv.count; i++) {
        const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
        let u, v;
        if (ax >= ay && ax >= az) { u = pos.getZ(i); v = pos.getY(i); } else if (ay >= az) { u = pos.getX(i); v = pos.getZ(i); } else { u = pos.getX(i); v = pos.getY(i); }
        uv.setXY(i, u / UVS, v / UVS);
      }
    } else if (g.type === 'CylinderGeometry' || g.type === 'ConeGeometry') {
      const r = Math.max(p.radiusTop === undefined ? p.radius : p.radiusTop, p.radiusBottom === undefined ? p.radius : p.radiusBottom) || 1;
      const circ = 2 * Math.PI * r * ((p.thetaLength || Math.PI * 2) / (Math.PI * 2));
      for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * circ) / UVS, (uv.getY(i) * p.height) / UVS);
    } else if (g.type === 'SphereGeometry') {
      for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * 2 * Math.PI * p.radius) / UVS, (uv.getY(i) * Math.PI * p.radius) / UVS);
    } else if (g.type === 'PlaneGeometry' || g.type === 'CircleGeometry') {
      const w = p.width || p.radius * 2, h = p.height || p.radius * 2;
      for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * w) / UVS, (uv.getY(i) * h) / UVS);
    }
    uv.needsUpdate = true;
  }
  function hash(a, b) { const s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return s - Math.floor(s); }
  function rockGeo(rTop, h, seg, hseg, seed) {
    const g = new THREE.CylinderGeometry(rTop, 0.01, h, seg, hseg, true);
    g.translate(0, -h / 2, 0);
    const p = g.attributes.position, uv = g.attributes.uv;
    const cols = [];
    const cTop = new THREE.Color('#b08a6a'), cMid = new THREE.Color('#6a4c4a'), cBot = new THREE.Color('#2a1e28');
    const c = new THREE.Color();
    for (let i = 0; i < p.count; i++) {
      let x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const t = -y / h;
      const a = Math.atan2(z, x);
      const ix = Math.round(((a + Math.PI) / (Math.PI * 2)) * seg) % seg;
      const iy = Math.round(t * hseg);
      const n = Math.sin(a * 5 + t * 4 + seed) * 0.5 + Math.sin(a * 13 - t * 7) * 0.25 + (hash(ix + seed, iy) - 0.5) * 0.7;
      if (t > 0.02) {
        const s = 1 + n * 0.14 * Math.min(1, t * 3);
        x *= s; z *= s; y += n * h * 0.03 * t;
      }
      p.setXYZ(i, x, y, z);
      uv.setXY(i, (uv.getX(i) * 2 * Math.PI * rTop) / (UVS * 2.5), (uv.getY(i) * h) / (UVS * 2.5));
      if (t < 0.5) c.copy(cTop).lerp(cMid, t / 0.5); else c.copy(cMid).lerp(cBot, (t - 0.5) / 0.5);
      c.multiplyScalar(0.88 + 0.2 * Math.sin(t * 30 + Math.sin(a * 3) * 2));
      cols.push(c.r, c.g, c.b);
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
    g.userData.uvDone = true;
    const ng = g.toNonIndexed();
    ng.userData.uvDone = true;
    ng.computeVertexNormals();
    return ng;
  }
  function mesh(geo, mat, x = 0, y = 0, z = 0, parent) {
    autoUV(geo);
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    if (parent) parent.add(m);
    return m;
  }
  // Satukan mesh statis per bahan: ratusan potongan istana jadi beberapa draw call saja.
  function bake(group) {
    group.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(group.matrixWorld).invert();
    const buckets = new Map();
    const victims = [];
    group.traverse((m) => {
      if (!m.isMesh || m.isInstancedMesh || m.userData.keep || Array.isArray(m.material)) return;
      const g = m.geometry;
      const key = m.material.uuid + (g.index ? 'i' : 'n') + Object.keys(g.attributes).sort().join(',');
      const geo = g.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld));
      if (!buckets.has(key)) buckets.set(key, { mat: m.material, geos: [], cast: m.castShadow });
      buckets.get(key).geos.push(geo);
      victims.push(m);
    });
    victims.forEach((m) => m.parent.remove(m));
    buckets.forEach((b) => {
      const merged = mergeGeometries(b.geos, false);
      if (!merged) return;
      const mm = new THREE.Mesh(merged, b.mat);
      mm.castShadow = b.cast;
      mm.receiveShadow = true;
      group.add(mm);
    });
  }
  const capMats = [M.grassSide, M.grass, M.dirt];

  // ------------------------------------------------------------ pulau utama
  const isle = new THREE.Group();
  scene.add(isle);
  const G = 1.0;
  mesh(rockGeo(17, 23, 46, 12, 3), M.rock, 0, 0.1, 0, isle).castShadow = false;
  mesh(new THREE.CylinderGeometry(17.7, 17.2, 1.4, 72, 1), capMats, 0, 0.3, 0, isle).castShadow = false;
  [[-11, 6, 4.2], [11.5, -8, 4.6], [-8.5, -11, 3.6], [6, 12.5, 3]].forEach(([x, z, r]) => {
    const h = mesh(new THREE.SphereGeometry(r, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), M.hill, x, G - 0.05, z, isle);
    h.scale.y = 0.38;
  });

  // ------------------------------------------------------------ istana
  const castle = new THREE.Group();
  castle.userData.pick = 'castle';
  isle.add(castle);
  const windows = [];
  const flags = [];
  const addWin = (x, y, z, nx, nz, s = 1) => windows.push({ x, y, z, nx, nz, s });

  function tower(x, z, r, h, roofH, opt = {}, parent = castle, ground = G) {
    mesh(new THREE.CylinderGeometry(r * 1.12, r * 1.18, 1.2, 20), M.stone, x, ground + 0.6, z, parent);
    mesh(new THREE.CylinderGeometry(r, r, h, 20), M.wall, x, ground + h / 2, z, parent);
    mesh(new THREE.CylinderGeometry(r * 1.18, r * 1.05, 0.6, 20), M.trim, x, ground + h - 0.3, z, parent);
    mesh(new THREE.ConeGeometry(r * 1.38, roofH, 20), opt.roof || M.roof, x, ground + h + roofH / 2, z, parent);
    mesh(new THREE.ConeGeometry(0.12, 1.4, 8), M.gold, x, ground + h + roofH + 0.6, z, parent);
    mesh(new THREE.SphereGeometry(0.24, 12, 8), M.gold, x, ground + h + roofH + 0.05, z, parent);
    const n = opt.win === undefined ? 4 : opt.win;
    for (let k = 0; k < n; k++) {
      const a = (k / n) * Math.PI * 2 + (opt.wa || 0.4);
      for (const fy of [0.48, 0.78]) addWin(x + Math.cos(a) * (r + 0.03), ground + h * fy, z + Math.sin(a) * (r + 0.03), Math.cos(a), Math.sin(a), r > 1.8 ? 1.2 : 0.9);
    }
    if (opt.flag) flags.push({ x, y: ground + h + roofH + 1.2, z, mat: opt.flag, parent });
  }
  const S = 8.6;
  const WH = 4.3;
  mesh(new THREE.BoxGeometry(2 * S, WH, 1.2), M.wall, 0, G + WH / 2, -S, castle);
  mesh(new THREE.BoxGeometry(1.2, WH, 2 * S), M.wall, -S, G + WH / 2, 0, castle);
  mesh(new THREE.BoxGeometry(1.2, WH, 2 * S), M.wall, S, G + WH / 2, 0, castle);
  mesh(new THREE.BoxGeometry(S - 1.9, WH, 1.2), M.wall, -(S + 1.9) / 2, G + WH / 2, S, castle);
  mesh(new THREE.BoxGeometry(S - 1.9, WH, 1.2), M.wall, (S + 1.9) / 2, G + WH / 2, S, castle);
  mesh(new THREE.BoxGeometry(3.8, 1.3, 1.2), M.wall, 0, G + WH - 0.65, S, castle);
  mesh(new THREE.BoxGeometry(3.4, 3.0, 0.5), M.door, 0, G + 1.5, S + 0.1, castle);
  mesh(new THREE.BoxGeometry(3.9, 0.25, 0.7), M.gold, 0, G + 3.05, S + 0.25, castle);
  const merl = [];
  for (let v = -S + 0.6; v <= S - 0.5; v += 1.15) {
    merl.push([v, -S - 0.35], [-S - 0.35, v], [S + 0.35, v]);
    if (Math.abs(v) > 0.2) merl.push([v, S + 0.35]);
  }
  const merlGeo = new THREE.BoxGeometry(0.6, 0.65, 0.5);
  autoUV(merlGeo);
  const merlM = new THREE.InstancedMesh(merlGeo, M.trim, merl.length);
  const dummy = new THREE.Object3D();
  merl.forEach(([x, z], i) => {
    dummy.position.set(x, G + WH + 0.32, z);
    dummy.rotation.set(0, Math.abs(x) > S ? Math.PI / 2 : 0, 0);
    dummy.updateMatrix();
    merlM.setMatrixAt(i, dummy.matrix);
  });
  merlM.castShadow = true;
  castle.add(merlM);
  tower(-S, -S, 1.8, 8.5, 4.2);
  tower(S, -S, 1.8, 8.5, 4.2);
  tower(-S, S, 1.8, 8, 4, { flag: M.flag2 });
  tower(S, S, 1.8, 8, 4, { flag: M.flag2 });
  tower(-2.6, S + 0.2, 1.05, 6.6, 2.8, { roof: M.roof2, win: 2, wa: 1.2 });
  tower(2.6, S + 0.2, 1.05, 6.6, 2.8, { roof: M.roof2, win: 2, wa: 1.2 });
  tower(-6, -5.6, 1.5, 12.5, 4.8, { flag: M.flag });
  tower(6, -5.6, 1.5, 12.5, 4.8, { flag: M.flag });
  mesh(new THREE.BoxGeometry(9.4, 8, 7), M.wall, 0, G + 4, -1.6, castle);
  mesh(new THREE.BoxGeometry(9.9, 0.6, 7.5), M.trim, 0, G + 7.9, -1.6, castle);
  const keepRoof = mesh(new THREE.ConeGeometry(7.1, 5.2, 4), M.roof, 0, G + 8.2 + 2.6, -1.6, castle);
  keepRoof.rotation.y = Math.PI / 4;
  keepRoof.scale.z = 7.4 / 9.8;
  for (const [x, z] of [[-4.7, 1.9], [4.7, 1.9]]) tower(x, z, 0.75, 9.6, 2.6, { roof: M.roof2, win: 0 });
  mesh(new THREE.BoxGeometry(2.4, 3.6, 0.4), M.door, 0, G + 1.8, 1.95, castle);
  mesh(new THREE.CylinderGeometry(1.2, 1.2, 0.4, 16, 1, false, 0, Math.PI), M.door, 0, G + 3.6, 1.95, castle).rotation.set(Math.PI / 2, 0, Math.PI / 2);
  for (const x of [-3.3, -1.7, 1.7, 3.3]) for (const y of [G + 2.6, G + 5.6]) addWin(x, y, 1.93, 0, 1, 1.1);
  for (const z of [-3.6, -0.4]) for (const y of [G + 3, G + 5.8]) { addWin(-4.73, y, z, -1, 0); addWin(4.73, y, z, 1, 0); }
  tower(0, -4.6, 2.4, 19, 7.6, { flag: M.flag, win: 6 });
  // panji merah di dinding depan
  const bannerGeo = new THREE.PlaneGeometry(1.3, 3.9);
  bannerGeo.userData.uvDone = true;
  for (const [x, y, z] of [[-4.3, G + 5.4, S + 0.62], [4.3, G + 5.4, S + 0.62], [-2.4, G + 5.2, 1.82], [2.4, G + 5.2, 1.82]]) {
    const b = mesh(bannerGeo, M.banner, x, y, z, castle);
    b.castShadow = false;
  }
  const winGeo = new THREE.PlaneGeometry(0.46, 0.86);
  const winM = new THREE.InstancedMesh(winGeo, M.windowLit, windows.length);
  windows.forEach((w, i) => {
    dummy.position.set(w.x, w.y, w.z);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(w.s, w.s, 1);
    dummy.lookAt(w.x + w.nx, w.y, w.z + w.nz);
    dummy.updateMatrix();
    winM.setMatrixAt(i, dummy.matrix);
  });
  castle.add(winM);
  const flagGeo = new THREE.PlaneGeometry(2.4, 1.3, 14, 4);
  flagGeo.translate(1.2, 0, 0);
  function makeFlags(list) {
    list.forEach((f) => {
      const pole = mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.6, 6), M.gold, f.x, f.y, f.z, f.parent);
      pole.userData.keep = true;
      const g = flagGeo.clone();
      const m = new THREE.Mesh(g, f.mat);
      m.position.set(f.x + 0.05, f.y + 0.6, f.z);
      m.rotation.y = -0.5;
      m.userData.keep = true;
      m.userData.base = Float32Array.from(g.attributes.position.array);
      m.userData.ph = R(0, 6);
      f.parent.add(m);
      f.mesh = m;
    });
  }
  makeFlags(flags);
  const path = mesh(new THREE.PlaneGeometry(3.2, 7.5), M.path, 0, G + 0.03, S + 4.4, isle);
  path.rotation.x = -Math.PI / 2;
  path.castShadow = false;
  bake(castle);
  // panji panjang yang menjuntai dari tepi pulau (berayun)
  const swayers = [];
  for (const a of [2.05, 2.5, 0.95]) {
    const b = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 6.2), M.banner);
    b.geometry.translate(0, -3.1, 0);
    const p = new THREE.Group();
    p.position.set(Math.cos(a) * 17.9, G - 0.2, Math.sin(a) * 17.9);
    p.rotation.y = -a + Math.PI / 2;
    p.add(b);
    isle.add(p);
    swayers.push({ m: b, ph: R(0, 6) });
  }

  // ------------------------------------------------------------ pohon
  const treeN = mobile ? 18 : 30;
  const tA = new THREE.InstancedMesh(new THREE.ConeGeometry(1.25, 2.6, 7), M.leaf, treeN);
  const tB = new THREE.InstancedMesh(new THREE.ConeGeometry(0.95, 2.1, 7), M.leaf2, treeN);
  const tT = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.18, 0.24, 1.1, 6), M.trunk, treeN);
  for (let i = 0; i < treeN; i++) {
    let a, r;
    const near = (aa, c) => Math.abs(Math.atan2(Math.sin(aa - c), Math.cos(aa - c)));
    do { a = R(0, Math.PI * 2); r = R(11.6, 16.2); }
    while (near(a, Math.PI / 2) < 0.32 || near(a, 0.15) < 0.3 || (r < 14.4 && Math.min(near(a, Math.PI / 4), near(a, 3 * Math.PI / 4), near(a, -Math.PI / 4), near(a, -3 * Math.PI / 4)) < 0.3));
    const x = Math.cos(a) * r, z = Math.sin(a) * r, s = R(0.7, 1.25);
    dummy.rotation.set(0, R(0, 6), 0);
    dummy.scale.set(s, s, s);
    dummy.position.set(x, G + 0.55 * s, z); dummy.updateMatrix(); tT.setMatrixAt(i, dummy.matrix);
    dummy.position.set(x, G + 2.0 * s, z); dummy.updateMatrix(); tA.setMatrixAt(i, dummy.matrix);
    dummy.position.set(x, G + 3.3 * s, z); dummy.updateMatrix(); tB.setMatrixAt(i, dummy.matrix);
  }
  [tA, tB, tT].forEach((t) => { t.castShadow = true; t.receiveShadow = true; isle.add(t); });

  // ------------------------------------------------------------ kolam, sungai, air terjun
  const pond = mesh(new THREE.CircleGeometry(2.3, 28), M.water, 12.4, G + 0.04, 2.2, isle);
  pond.rotation.x = -Math.PI / 2;
  const creek = mesh(new THREE.PlaneGeometry(4.6, 1.7), M.water, 15.2, G + 0.05, 2.2, isle);
  creek.rotation.x = -Math.PI / 2;
  const streak = canvasTex(64, 256, (x, w, h) => {
    x.fillStyle = 'rgb(150,170,175)'; x.fillRect(0, 0, w, h);
    const rr = mulberry32(5);
    for (let i = 0; i < 70; i++) {
      x.fillStyle = `rgba(255,236,210,${0.2 + rr() * 0.55})`;
      x.fillRect(rr() * w, rr() * h, 1 + rr() * 3, 20 + rr() * 90);
    }
  });
  streak.wrapS = streak.wrapT = THREE.RepeatWrapping;
  streak.repeat.set(1, 3);
  const fade = canvasTex(4, 128, (x, w, h) => {
    const g = x.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, '#fff'); g.addColorStop(0.55, '#ccc'); g.addColorStop(1, '#000');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
  }, false);
  const fallMat = new THREE.MeshBasicMaterial({ map: streak, alphaMap: fade, transparent: true, depthWrite: false, side: THREE.DoubleSide, color: '#e8d8c8' });
  function waterfall(len, width) {
    const g = new THREE.PlaneGeometry(width, len, 1, 24);
    g.translate(0, -len / 2, 0);
    g.rotateY(Math.PI / 2);
    const fp = g.attributes.position;
    for (let i = 0; i < fp.count; i++) fp.setX(i, 1.8 * (1 - Math.exp(fp.getY(i) / 2.6)));
    return new THREE.Mesh(g, fallMat);
  }
  const fall = waterfall(30, 1.7);
  fall.position.set(17.4, G - 0.05, 2.2);
  isle.add(fall);
  const mist = glow('#ffd2a8', 9, 0.35);
  mist.position.set(19.3, G - 24, 2.2);
  isle.add(mist);

  // ------------------------------------------------------------ sihir: kristal, lingkaran rune, cahaya bawah
  const crystals = new THREE.Group();
  crystals.userData.pick = 'crystal';
  isle.add(crystals);
  const crysGeo = new THREE.OctahedronGeometry(1, 0);
  const crysList = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2 + 0.9;
    const c = new THREE.Mesh(crysGeo, M.crystal);
    c.position.set(Math.cos(a) * 16.4, G + 0.9, Math.sin(a) * 16.4);
    c.scale.set(0.42, 1.25, 0.42);
    c.rotation.z = R(-0.25, 0.25);
    const gl = glow('#ff9a40', 4.2, 0.6);
    gl.position.copy(c.position);
    crystals.add(c, gl);
    crysList.push(gl);
  }
  for (let i = 0; i < 6; i++) {
    const c = new THREE.Mesh(crysGeo, M.crystal);
    const a = (i / 6) * Math.PI * 2;
    c.position.set(Math.cos(a) * 1.1 * (i ? 1 : 0), -22.6 - (i ? R(0, 1.5) : 1.2), Math.sin(a) * 1.1 * (i ? 1 : 0));
    c.scale.set(0.7, i ? 2.2 : 3.4, 0.7);
    c.rotation.set(R(-0.3, 0.3), 0, R(-0.3, 0.3));
    crystals.add(c);
  }
  const coreGlow = glow('#ffa850', 22, 0.85);
  coreGlow.position.set(0, -23, 0);
  crystals.add(coreGlow);
  const under = new THREE.PointLight('#ff9a4a', 1100, 70, 2);
  under.position.set(0, -26, 0);
  isle.add(under);

  function runeTex(seed) {
    return canvasTex(1024, 1024, (x, S2) => {
      const rr = mulberry32(seed);
      x.translate(S2 / 2, S2 / 2);
      x.strokeStyle = '#fff'; x.fillStyle = '#fff'; x.lineCap = 'round'; x.lineJoin = 'round';
      const ring = (r, w, a = 1) => { x.globalAlpha = a; x.lineWidth = w; x.beginPath(); x.arc(0, 0, r, 0, Math.PI * 2); x.stroke(); };
      ring(500, 7); ring(474, 3); ring(392, 4, 0.9); ring(312, 2, 0.7); ring(160, 6); ring(130, 2, 0.6);
      x.globalAlpha = 1;
      const N = 44;
      for (let i = 0; i < N; i++) {
        x.save(); x.rotate((i / N) * Math.PI * 2); x.translate(0, -433); x.lineWidth = 4;
        x.beginPath();
        let px = Math.floor(rr() * 3), py = Math.floor(rr() * 3);
        x.moveTo((px - 1) * 9, (py - 1) * 13);
        for (let k = 0; k < 3; k++) { px = Math.floor(rr() * 3); py = Math.floor(rr() * 3); x.lineTo((px - 1) * 9, (py - 1) * 13); }
        x.stroke(); x.restore();
      }
      x.lineWidth = 3;
      for (const off of [0, Math.PI]) {
        x.beginPath();
        for (let k = 0; k <= 3; k++) { const a = off + (k / 3) * Math.PI * 2 - Math.PI / 2; x[k ? 'lineTo' : 'moveTo'](Math.cos(a) * 392, Math.sin(a) * 392); }
        x.stroke();
      }
      for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI * 2 - Math.PI / 2; x.beginPath(); x.arc(Math.cos(a) * 392, Math.sin(a) * 392, 26, 0, Math.PI * 2); x.stroke(); }
      x.globalAlpha = 0.55;
      for (let k = 0; k < 24; k++) { const a = (k / 24) * Math.PI * 2; x.beginPath(); x.moveTo(Math.cos(a) * 160, Math.sin(a) * 160); x.lineTo(Math.cos(a) * 312, Math.sin(a) * 312); x.stroke(); }
      x.globalAlpha = 1;
      for (let k = 0; k < 72; k++) { const a = (k / 72) * Math.PI * 2; x.beginPath(); x.arc(Math.cos(a) * 352, Math.sin(a) * 352, 3.5, 0, Math.PI * 2); x.fill(); }
    });
  }
  const runeA = runeTex(9), runeB = runeTex(31);
  const runeMat = (map, color, opacity) => new THREE.MeshBasicMaterial({ map, color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false, fog: false });
  const runes = [];
  const addRune = (map, color, size, y, spin, opacity, parent = isle, x = 0, z = 0) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), runeMat(map, color, opacity));
    m.rotation.x = -Math.PI / 2;
    m.position.set(x, y, z);
    m.userData.spin = spin;
    m.raycast = () => {};
    parent.add(m);
    runes.push(m);
    return m;
  };
  addRune(runeA, '#ff9a40', 50, -27, 0.05, 0.9);
  addRune(runeB, '#ffd27a', 34, -12.5, -0.08, 0.6);
  addRune(runeB, '#ffc060', 6.4, G + 0.06, 0.25, 0.85, isle, 0, 5.4);

  // ------------------------------------------------------------ pulau-pulau kecil yang mengorbit
  const islets = new THREE.Group();
  scene.add(islets);
  const smallRocks = [];
  const nIslets = mobile ? 5 : 8;
  for (let i = 0; i < nIslets; i++) {
    const g = new THREE.Group();
    const r = R(1.6, 3.4);
    mesh(rockGeo(r, r * 2.2, 14, 4, i * 7 + 2), M.rock, 0, 0, 0, g).castShadow = false;
    mesh(new THREE.CylinderGeometry(r * 1.05, r, 0.5, 18), capMats, 0, 0.2, 0, g).castShadow = false;
    if (rnd() > 0.35) {
      const t1 = mesh(new THREE.ConeGeometry(0.7, 1.7, 7), M.leaf, 0, 1.3, 0, g);
      t1.position.x = R(-0.5, 0.5);
    }
    const a = (i / nIslets) * Math.PI * 2 + R(-0.3, 0.3);
    g.userData = { a, rad: R(25, 34), y: R(-8, 12), sp: R(0.02, 0.05) * (rnd() > 0.5 ? 1 : -1), ph: R(0, 6) };
    islets.add(g);
    smallRocks.push(g);
  }

  // ------------------------------------------------------------ kerajaan jauh berkabut
  const far = new THREE.Group();
  scene.add(far);
  const farN = mobile ? 7 : 12;
  for (let i = 0; i < farN; i++) {
    const g = new THREE.Group();
    const s = R(0.9, 2.4);
    const top = 8 * s;
    for (let tries = 0; tries < 30; tries++) {
      const a = (i / farN) * Math.PI * 2 + R(-0.25, 0.25), rad = R(120, 300);
      g.position.set(Math.cos(a) * rad, R(-24, 26), Math.sin(a) * rad);
      if (clear(g.position.x, g.position.y, g.position.z, top * 1.8 + 24)) break;
    }
    mesh(rockGeo(top, top * 1.6, 22, 6, 40 + i), M.rock, 0, 0, 0, g);
    mesh(new THREE.CylinderGeometry(top * 1.04, top, 0.8, 26), capMats, 0, 0.3, 0, g);
    const nt = 2 + Math.floor(rnd() * 4);
    for (let k = 0; k < nt; k++) {
      const ta = R(0, Math.PI * 2), tr = R(0, top * 0.55);
      tower(Math.cos(ta) * tr, Math.sin(ta) * tr, R(0.6, 1.4) * s, R(5, 14) * s, R(2.5, 5) * s, { win: 0 }, g, 0.7);
    }
    if (rnd() > 0.45) {
      const wf = waterfall(top * 3, 0.9 * s);
      wf.position.set(top * 0.98, 0.6, 0);
      g.add(wf);
      wf.userData.keep = true;
    }
    g.rotation.y = R(0, 6);
    g.traverse((m) => { if (m.isMesh) m.castShadow = false; });
    bake(g);
    far.add(g);
  }

  // ------------------------------------------------------------ kapal udara
  const airship = new THREE.Group();
  airship.userData.pick = 'airship';
  {
    const hull = mesh(new THREE.SphereGeometry(1, 28, 16), M.leather, 0, 0, 0, airship);
    hull.scale.set(5.2, 1.8, 1.8);
    for (const x of [-3, 0, 3]) {
      const ring = mesh(new THREE.TorusGeometry(1.0, 0.06, 6, 28), M.gold, x, 0, 0, airship);
      ring.rotation.y = Math.PI / 2;
      ring.scale.setScalar(Math.sqrt(1 - (x / 5.2) ** 2) * 1.83);
    }
    mesh(new THREE.BoxGeometry(3.4, 0.9, 1.2), M.wood, 0, -2.4, 0, airship);
    for (const x of [-1.4, 1.4]) mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.3, 4), M.wood, x, -1.7, 0, airship);
    const fin = new THREE.BoxGeometry(1.6, 1.6, 0.08);
    mesh(fin, M.leather, -5, 0.4, 0, airship).rotation.z = 0.3;
    const fin2 = mesh(fin, M.leather, -5, 0, 0, airship);
    fin2.rotation.set(Math.PI / 2, 0, 0.3);
  }
  const prop = mesh(new THREE.BoxGeometry(0.08, 1.4, 0.18), M.wood, 2.0, -2.4, 0, airship);
  prop.userData.keep = true;
  const lamp = glow('#ffb050', 2.6, 0.9);
  lamp.position.set(1.8, -2.4, 0);
  airship.add(lamp);
  airship.scale.setScalar(1.3);
  scene.add(airship);

  // ------------------------------------------------------------ konstruksi baja
  function iShape(h, b, tw, tf) {
    const s = new THREE.Shape();
    const hh = h / 2, hb = b / 2, ht = tw / 2;
    s.moveTo(-hb, -hh); s.lineTo(hb, -hh); s.lineTo(hb, -hh + tf); s.lineTo(ht, -hh + tf); s.lineTo(ht, hh - tf);
    s.lineTo(hb, hh - tf); s.lineTo(hb, hh); s.lineTo(-hb, hh); s.lineTo(-hb, hh - tf); s.lineTo(-ht, hh - tf);
    s.lineTo(-ht, -hh + tf); s.lineTo(-hb, -hh + tf); s.closePath();
    return s;
  }
  const extr = (shape, L) => { const g = new THREE.ExtrudeGeometry(shape, { depth: L, bevelEnabled: false }); g.translate(0, 0, -L / 2); return g; };
  function memberBetween(shape, a, b, mat, parent) {
    const m = mesh(extr(shape, a.distanceTo(b)), mat, (a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, parent);
    parent.updateWorldMatrix(true, false);
    m.lookAt(parent.localToWorld(b.clone()));
    return m;
  }
  function bar(a, b, t, mat, parent) {
    const L = a.distanceTo(b);
    const m = mesh(new THREE.BoxGeometry(t, t, L), mat, (a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, parent);
    parent.updateWorldMatrix(true, false);
    m.lookAt(parent.localToWorld(b.clone()));
    return m;
  }
  function boltSet(parent, x, y, z, s = 1) {
    mesh(new THREE.CylinderGeometry(0.075 * s, 0.075 * s, 0.06 * s, 6), M.galv, x, y + 0.03 * s, z, parent);
    mesh(new THREE.CylinderGeometry(0.1 * s, 0.1 * s, 0.015 * s, 14), M.galv, x, y + 0.005 * s, z, parent);
    mesh(new THREE.CylinderGeometry(0.035 * s, 0.035 * s, 0.22 * s, 8), M.galv, x, y + 0.1 * s, z, parent);
  }

  const site = new THREE.Group();
  site.position.set(-36, 3, -10);
  scene.add(site);
  mesh(rockGeo(9, 12, 30, 8, 21), M.rock, 0, 0, 0, site).castShadow = false;
  mesh(new THREE.CylinderGeometry(9.4, 9.1, 1.0, 44), capMats, 0, 0.2, 0, site).castShadow = false;
  const G2 = 0.7;
  const portal = new THREE.Group();
  portal.userData.pick = 'portal';
  site.add(portal);
  const colS = iShape(0.46, 0.3, 0.035, 0.05);
  const rafS = iShape(0.52, 0.24, 0.03, 0.045);
  const portalFrame = (z, full) => {
    for (const x of full ? [-4.6, 4.6] : [-4.6]) {
      mesh(new THREE.BoxGeometry(0.9, 0.5, 0.9), M.concrete, x, G2 + 0.25, z, portal);
      mesh(new THREE.BoxGeometry(0.7, 0.05, 0.7), M.primer, x, G2 + 0.52, z, portal);
      for (const dx of [-0.24, 0.24]) for (const dz of [-0.24, 0.24]) boltSet(portal, x + dx, G2 + 0.545, z + dz, 0.9);
      const c = mesh(extr(colS, 6.4), M.primer, x, G2 + 0.55 + 3.2, z, portal);
      c.rotation.x = Math.PI / 2;
      mesh(new THREE.BoxGeometry(0.34, 0.9, 0.02), M.primer, x + Math.sign(x) * -0.25, G2 + 6.55, z + 0.17, portal);
    }
    if (full) {
      memberBetween(rafS, new THREE.Vector3(-4.75, G2 + 7.1, z), new THREE.Vector3(0, G2 + 8.6, z), M.primer, portal);
      memberBetween(rafS, new THREE.Vector3(4.75, G2 + 7.1, z), new THREE.Vector3(0, G2 + 8.6, z), M.primer, portal);
      mesh(new THREE.BoxGeometry(0.05, 0.9, 0.3), M.primer, 0, G2 + 8.35, z, portal);
    }
  };
  portalFrame(2.6, true);
  portalFrame(-2.6, false);
  portal.updateMatrixWorld(true);
  for (let k = 0; k < 4; k++) {
    const t = 0.12 + k * 0.26;
    const x = -4.75 + t * 4.75, y = G2 + 7.1 + t * 1.5 + 0.36;
    bar(new THREE.Vector3(x, y, 2.9), new THREE.Vector3(x, y, -2.9), 0.16, M.galv, portal);
  }
  for (let k = 0; k < 2; k++) {
    const t = 0.18 + k * 0.4;
    const x = 4.75 - t * 4.75, y = G2 + 7.1 + t * 1.5 + 0.36;
    bar(new THREE.Vector3(x, y, 2.9), new THREE.Vector3(x, y, 1.0), 0.16, M.galv, portal);
  }
  bake(portal);
  const lift = new THREE.Group();
  lift.position.set(2.4, G2 + 11.5, -2.6);
  site.add(lift);
  memberBetween(rafS, new THREE.Vector3(-2.4, 0, 0), new THREE.Vector3(2.4, 1.5, 0), M.primer, lift);
  addRune(runeB, '#ffc060', 4.5, -1.2, 0.6, 0.9, lift);

  const pieces = [];
  function piece(key, pos, build, scale = 1) {
    const g = new THREE.Group();
    const inner = new THREE.Group();
    g.add(inner);
    build(inner);
    inner.scale.setScalar(scale);
    g.position.copy(pos);
    const ring = addRune(runeA, '#ffc060', 4.2 * Math.max(1, scale * 0.8), -2.6, 0.5, 0.75, g);
    const halo = glow('#ffb050', 6 * Math.max(1, scale * 0.7), 0);
    g.add(halo);
    g.userData = { pick: key, base: pos.clone(), ph: R(0, 6), inner, ring, halo, spin: 0, hover: 0 };
    scene.add(g);
    pieces.push(g);
    return g;
  }
  piece('beam', new THREE.Vector3(-40, 16, 4), (p) => {
    const m = mesh(extr(iShape(0.62, 0.3, 0.035, 0.05), 6.5), M.steel, 0, 0, 0, p);
    m.rotation.y = Math.PI / 2;
    for (const x of [-3.24, 3.24]) mesh(new THREE.BoxGeometry(0.02, 0.62, 0.3), M.steel, x, 0, 0, p);
  });
  piece('column', new THREE.Vector3(-52, 9, -2), (p) => {
    const c = mesh(extr(iShape(0.42, 0.42, 0.04, 0.055), 4.6), M.primer, 0, 0.05, 0, p);
    c.rotation.x = Math.PI / 2;
    mesh(new THREE.BoxGeometry(0.85, 0.06, 0.85), M.primer, 0, -2.3, 0, p);
    for (const dx of [-0.3, 0.3]) for (const dz of [-0.3, 0.3]) {
      boltSet(p, dx, -2.27, dz, 1);
      mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.9, 8), M.galv, dx, -2.7, dz, p);
    }
  });
  piece('truss', new THREE.Vector3(-42, 17.5, -22), (p) => {
    const L = 8, H = 1.3, n = 6;
    bar(new THREE.Vector3(-L / 2, H / 2, 0), new THREE.Vector3(L / 2, H / 2, 0), 0.14, M.galv, p);
    bar(new THREE.Vector3(-L / 2, -H / 2, 0), new THREE.Vector3(L / 2, -H / 2, 0), 0.14, M.galv, p);
    for (let i = 0; i < n; i++) {
      const x0 = -L / 2 + (i / n) * L, x1 = -L / 2 + ((i + 1) / n) * L;
      bar(new THREE.Vector3(x0, i % 2 ? H / 2 : -H / 2, 0), new THREE.Vector3(x1, i % 2 ? -H / 2 : H / 2, 0), 0.09, M.galv, p);
    }
    bar(new THREE.Vector3(-L / 2, -H / 2, 0), new THREE.Vector3(-L / 2, H / 2, 0), 0.1, M.galv, p);
    bar(new THREE.Vector3(L / 2, -H / 2, 0), new THREE.Vector3(L / 2, H / 2, 0), 0.1, M.galv, p);
  });
  piece('bolts', new THREE.Vector3(-47, 5, 1), (p) => {
    mesh(new THREE.BoxGeometry(0.9, 0.05, 1.3), M.primer, 0, 0, 0, p);
    for (const dx of [-0.25, 0.25]) for (const dz of [-0.42, 0, 0.42]) boltSet(p, dx, 0.025, dz, 1.2);
    const stub = mesh(extr(iShape(0.5, 0.25, 0.03, 0.045), 1.2), M.steel, 0, -0.62, 0, p);
    stub.rotation.x = Math.PI / 2;
  }, 2.2);
  piece('plate', new THREE.Vector3(-52, 14, -14), (p) => {
    const s = new THREE.Shape();
    s.moveTo(-0.7, -0.5); s.lineTo(0.7, -0.5); s.lineTo(0.7, 0.1); s.lineTo(0.1, 0.6); s.lineTo(-0.7, 0.6); s.closePath();
    for (const [hx, hy] of [[-0.45, -0.25], [-0.1, -0.25], [0.35, -0.25], [-0.45, 0.25], [-0.1, 0.25]]) {
      const hole = new THREE.Path();
      hole.absarc(hx, hy, 0.06, 0, Math.PI * 2, true);
      s.holes.push(hole);
    }
    mesh(extr(s, 0.04), M.primer, 0, 0, 0, p);
  }, 2.4);

  // bahan diklon per kelompok supaya sorotan hover tidak menular
  const pickables = [castle, crystals, portal, airship, ...pieces];
  pickables.forEach((grp) => {
    const map = new Map();
    const hl = [];
    grp.traverse((m) => {
      if (!m.isMesh || !m.material || Array.isArray(m.material)) return;
      if (!('emissive' in m.material)) return;
      if (!map.has(m.material)) { const c = m.material.clone(); map.set(m.material, c); hl.push(c); }
      m.material = map.get(m.material);
    });
    grp.userData.hl = hl;
    grp.userData.hover = 0;
  });

  // ------------------------------------------------------------ awan senja
  const mkCloudMat = (seed, pal, fog = true, w = 512, h = 296) => {
    const t = new THREE.CanvasTexture(cloudCanvas(w, h, seed, pal));
    t.colorSpace = THREE.SRGBColorSpace;
    return new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false, fog });
  };
  const darkMats = [0, 1, 2].map((i) => mkCloudMat(300 + i * 31, DUSK));
  const litMats = [0, 1].map((i) => mkCloudMat(400 + i * 17, DUSK_LIT));
  const bankDark = [0, 1].map((i) => mkCloudMat(500 + i * 13, DUSK, false, 768, 400));
  const bankLit = [0, 1].map((i) => mkCloudMat(600 + i * 19, DUSK_LIT, false, 768, 400));
  const clouds = [];
  const tmpD = new THREE.Vector3();
  const sunward = (x, y, z) => tmpD.set(x, 0, z).normalize().dot(tmpD.clone().set(sunDir.x, 0, sunDir.z).normalize());
  const addCloud = (x, y, z, w, sp, mats) => {
    const lit = sunward(x, y, z) > 0.55;
    const pool = mats || (lit ? litMats : darkMats);
    const s = new THREE.Sprite(pool[clouds.length % pool.length]);
    s.position.set(x, y, z);
    s.scale.set(w, w * 0.56, 1);
    s.userData = { sp, x0: x, ph: R(0, 6) };
    s.raycast = () => {};
    scene.add(s);
    clouds.push(s);
  };
  const nMid = mobile ? 16 : 30, nSea = mobile ? 20 : 38, nBank = mobile ? 10 : 18;
  for (let i = 0, tries = 0; i < nMid && tries < 400; tries++) {
    const a = R(0, Math.PI * 2), r = R(60, 260), y = R(-6, 38), w = R(36, 80);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (!clear(x, y, z, w * 0.9 + 28)) continue;
    addCloud(x, y, z, w, R(0.6, 1.8));
    i++;
  }
  for (let i = 0; i < nSea; i++) {
    const a = R(0, Math.PI * 2), r = Math.sqrt(rnd()) * 330;
    addCloud(Math.cos(a) * r, R(-58, -44), Math.sin(a) * r, R(80, 140), R(0.4, 1), darkMats);
  }
  for (let i = 0; i < nBank; i++) { // tumpukan awan raksasa di cakrawala, tidak terkena kabut
    const a = (i / nBank) * Math.PI * 2 + R(-0.15, 0.15), r = R(420, 620);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    addCloud(x, R(-10, 70), z, R(260, 420), R(0.2, 0.6), sunward(x, 0, z) > 0.5 ? bankLit : bankDark);
  }
  for (let i = 0; i < 14; i++) {
    const t = i / 13;
    const x = R(-28, 28) * (1 - t * 0.4), y = 42 - t * 16 + R(-6, 6), z = 190 - t * 80, w = R(36, 62);
    if (clear(x, y, z, w * 0.7 + 20)) addCloud(x, y, z, w, R(0.2, 0.6), darkMats);
  }

  // ------------------------------------------------------------ burung
  const birds = [];
  const wingGeo = new THREE.BufferGeometry();
  wingGeo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, -0.25, 0, 0, 0.3, 1.3, 0, 0.05], 3));
  for (let i = 0; i < (mobile ? 4 : 8); i++) {
    const b = new THREE.Group();
    const wl = new THREE.Mesh(wingGeo, M.bird), wr = new THREE.Mesh(wingGeo, M.bird);
    wr.scale.x = -1;
    b.add(wl, wr);
    b.userData = { wl, wr, rad: R(30, 52), y: R(16, 30), sp: R(0.12, 0.22), a: R(0, 6), ph: R(0, 6) };
    scene.add(b);
    birds.push(b);
  }

  // ------------------------------------------------------------ bara & debu emas (points)
  const sparkVS = `uniform float uTime, uPR, uTw, uRise, uRange, uBase;
    attribute float aSize, aPhase, aAlpha; attribute vec3 aColor;
    varying vec3 vC; varying float vA;
    void main(){
      vec3 p = position;
      if (uRise > 0.0) { p.y = uBase + mod(p.y - uBase + uTime * uRise * (0.6 + aPhase), uRange); p.x += sin(uTime * 0.7 + aPhase * 20.0) * 0.5; }
      else { p.y += sin(uTime * 0.6 + aPhase * 6.2831) * 0.6 * uTw; }
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      gl_Position = projectionMatrix * mv;
      float tw = mix(1.0, 0.4 + 0.6 * sin(uTime * 2.3 + aPhase * 40.0), uTw);
      vA = aAlpha * max(tw, 0.0);
      if (uRise > 0.0) { float f = (p.y - uBase) / uRange; vA *= smoothstep(0.0, 0.15, f) * smoothstep(1.0, 0.7, f); }
      vC = aColor;
      gl_PointSize = min(aSize * uPR * (300.0 / -mv.z), 70.0 * uPR);
    }`;
  const sparkFS = `varying vec3 vC; varying float vA;
    void main(){
      vec2 c = gl_PointCoord - 0.5; float d = length(c);
      float core = smoothstep(0.5, 0.0, d); core *= core;
      float star = max(0.0, 1.0 - abs(c.x) * 10.0) * max(0.0, 1.0 - abs(c.y) * 2.2) + max(0.0, 1.0 - abs(c.y) * 10.0) * max(0.0, 1.0 - abs(c.x) * 2.2);
      float a = (core + star * 0.5) * vA;
      if (a < 0.01) discard;
      gl_FragColor = vec4(vC, a);
    }`;
  function sparkles(n, place, opt) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(n * 3), size = new Float32Array(n), ph = new Float32Array(n), al = new Float32Array(n), col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const [x, y, z, s, c] = place(i);
      pos.set([x, y, z], i * 3); size[i] = s; ph[i] = rnd(); al[i] = opt.alpha === undefined ? 1 : opt.alpha; col.set(c, i * 3);
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    g.setAttribute('aPhase', new THREE.BufferAttribute(ph, 1));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(al, 1));
    g.setAttribute('aColor', new THREE.BufferAttribute(col, 3));
    const mat = new THREE.ShaderMaterial({
      vertexShader: sparkVS, fragmentShader: sparkFS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uPR: { value: pr }, uTw: { value: opt.tw }, uRise: { value: opt.rise || 0 }, uRange: { value: opt.range || 1 }, uBase: { value: opt.base || 0 } },
    });
    const pts = new THREE.Points(g, mat);
    pts.frustumCulled = false;
    pts.raycast = () => {};
    return pts;
  }
  const EMBER = [1, 0.5, 0.18], GOLD = [1, 0.78, 0.4], DIM = [0.8, 0.35, 0.15];
  const ambient = sparkles(mobile ? 220 : 520, () => {
    const a = R(0, Math.PI * 2), r = R(8, 75);
    return [Math.cos(a) * r, R(-24, 42), Math.sin(a) * r, R(0.5, 1.4), [EMBER, GOLD, DIM][Math.floor(rnd() * 3)]];
  }, { tw: 1 });
  scene.add(ambient);
  const motes = sparkles(mobile ? 120 : 260, () => {
    const a = R(0, Math.PI * 2), r = Math.sqrt(rnd()) * 16;
    return [Math.cos(a) * r, R(-34, -4), Math.sin(a) * r, R(0.5, 1.3), rnd() > 0.4 ? EMBER : GOLD];
  }, { tw: 1, rise: 2.2, range: 32, base: -36 });
  isle.add(motes);
  const BURST = 90;
  const burst = sparkles(BURST, () => [0, -999, 0, R(1.2, 2.6), rnd() > 0.5 ? GOLD : EMBER], { tw: 0, alpha: 0 });
  scene.add(burst);
  const bVel = new Float32Array(BURST * 3), bLife = new Float32Array(BURST);
  let bNext = 0;
  function spawnBurst(p, n = 40, spread = 9) {
    const pa = burst.geometry.attributes.position, aa = burst.geometry.attributes.aAlpha;
    for (let k = 0; k < n; k++) {
      const i = bNext; bNext = (bNext + 1) % BURST;
      pa.setXYZ(i, p.x, p.y, p.z);
      const th = R(0, Math.PI * 2), ph = Math.acos(R(-1, 1)), sp = R(0.3, 1) * spread;
      bVel[i * 3] = Math.sin(ph) * Math.cos(th) * sp;
      bVel[i * 3 + 1] = Math.cos(ph) * sp + 3;
      bVel[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * sp;
      bLife[i] = 1;
      aa.setX(i, 1);
    }
    pa.needsUpdate = aa.needsUpdate = true;
  }
  const sparkSets = [ambient, motes, burst];

  // ------------------------------------------------------------ kamera & gulir
  const ids = (o.sections || Object.keys(KEYS)).filter((id) => KEYS[id] && document.getElementById(id));
  let tops = [];
  const measure = () => { tops = ids.map((id) => document.getElementById(id).getBoundingClientRect().top + scrollY); };
  measure();
  if ('ResizeObserver' in window) new ResizeObserver(measure).observe(document.body);

  const camPos = V(INTRO.p), camLook = V(INTRO.l);
  const tgtPos = new THREE.Vector3(), tgtLook = new THREE.Vector3();
  const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();
  const smooth = (t) => t * t * (3 - 2 * t);
  function keyFor(id, outP, outL) {
    const k = KEYS[id];
    outL.fromArray(k.l);
    outP.fromArray(k.p);
    const asp = camera.aspect;
    if (asp < 1.2) {
      if (k.f) outL.lerp(tmpB.fromArray(k.f), 0.75);
      const d = asp < 0.8 ? 1.7 : 1.3;
      outP.sub(outL).multiplyScalar(d).add(outL);
    }
  }
  const kP = new THREE.Vector3(), kL = new THREE.Vector3();
  function scrollTarget() {
    const y = scrollY;
    let i = 0;
    while (i < tops.length - 1 && y >= tops[i + 1]) i++;
    keyFor(ids[i], tgtPos, tgtLook);
    if (i < tops.length - 1) {
      const t = smooth(Math.min(1, Math.max(0, (y - tops[i]) / Math.max(1, tops[i + 1] - tops[i]))));
      keyFor(ids[i + 1], kP, kL);
      tgtPos.lerp(kP, t);
      tgtLook.lerp(kL, t);
    }
  }

  let introT0 = reduced ? -2 : -1; // -1 = menunggu tirai dibuka
  const introDur = 4.2;
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  // ------------------------------------------------------------ pointer & klik
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const mouse = { x: 0, y: 0, sx: 0, sy: 0, over: false, dirty: false };
  let hovered = null;
  addEventListener('pointermove', (e) => {
    mouse.x = (e.clientX / innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / innerHeight) * 2 + 1;
    mouse.over = e.pointerType === 'mouse' && !o.isUI(e.target);
    mouse.dirty = true;
  }, { passive: true });
  function pickAt(x, y) {
    ndc.set(x, y);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(pickables, true);
    for (const h of hits) {
      let n = h.object;
      while (n && !(n.userData && n.userData.pick)) n = n.parent;
      if (n) return { grp: n, point: h.point };
    }
    return null;
  }
  addEventListener('click', (e) => {
    if (o.isUI(e.target)) return;
    const hit = pickAt((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    if (!hit) { o.onPick(null); return; }
    const key = hit.grp.userData.pick;
    hit.grp.userData.spin = (hit.grp.userData.spin || 0) + 7;
    hit.grp.userData.flash = 1;
    spawnBurst(hit.point, 46, 8);
    o.onPick(INFO[key], e.clientX, e.clientY);
  });

  // ------------------------------------------------------------ ukuran & kualitas adaptif
  let lastW = 0, lastH = 0;
  function resize(force) {
    const w = innerWidth, h = innerHeight;
    if (!force && w === lastW && Math.abs(h - lastH) < 120) return;
    lastW = w; lastH = h;
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w / h < 0.8 ? 58 : (mobile ? 52 : 42);
    camera.updateProjectionMatrix();
    sparkSets.forEach((s) => { s.material.uniforms.uPR.value = pr * (h / 900); });
    measure();
  }
  resize(true);
  addEventListener('resize', () => resize(false));

  let acc = 0, frames = 0, lastCheck = performance.now() + 3500;
  function adapt(now, dt) {
    if (now < lastCheck) return;
    acc += dt; frames++;
    if (now - lastCheck < 2000) return;
    const avg = (acc / frames) * 1000;
    if (avg > 26 && pr > minPR) {
      pr = Math.max(minPR, pr - 0.25); resize(true);
      if (pr <= 1) html.classList.add('lite');
    } else if (avg < 12 && pr < maxPR) {
      pr = Math.min(maxPR, pr + 0.25); resize(true);
    }
    acc = 0; frames = 0; lastCheck = now;
  }

  // ------------------------------------------------------------ putaran animasi
  const debug = /[?&]debug/.test(location.search) ? (window.__kingdom = { n: 0, ms: 0, max: 0 }) : null;
  if (debug) {
    debug.pickables = pickables;
    debug.where = (key) => {
      const g = pickables.find((x) => x.userData.pick === key);
      const v = new THREE.Vector3();
      g.getWorldPosition(v).project(camera);
      return { x: Math.round(((v.x + 1) / 2) * innerWidth), y: Math.round(((1 - v.y) / 2) * innerHeight) };
    };
  }
  const clock = new THREE.Clock();
  let time = 0;
  let readySent = false;
  const speed = reduced ? 0.25 : 0.8; // sengaja pelan: suasana senja yang tenang
  const upVec = new THREE.Vector3(0, 1, 0);
  const hlColor = new THREE.Color('#ffb060');

  function frame() {
    requestAnimationFrame(frame);
    const now = performance.now();
    const dtReal = Math.min(clock.getDelta(), 0.05);
    const dt = dtReal * speed;
    time += dt;
    adapt(now, dtReal);

    isle.position.y = Math.sin(time * 0.4) * 0.7;
    isle.rotation.y = Math.sin(time * 0.1) * 0.03;
    site.position.y = 3 + Math.sin(time * 0.45 + 1.3) * 0.6;
    far.children.forEach((g, i) => { g.position.y += Math.sin(time * 0.3 + i) * 0.004; });
    runes.forEach((r) => { r.rotation.z += r.userData.spin * dt; });
    crysList.forEach((g, i) => { g.material.opacity = 0.3 + 0.35 * (0.5 + 0.5 * Math.sin(time * 1.6 + i)); });
    coreGlow.material.opacity = 0.65 + 0.2 * Math.sin(time * 1.3);
    streak.offset.y += dt * 1.3;
    lift.position.y = G2 + 11.5 + Math.sin(time * 0.8) * 0.5;
    lift.rotation.y = Math.sin(time * 0.35) * 0.15;
    swayers.forEach((s) => { s.m.rotation.x = Math.sin(time * 0.9 + s.ph) * 0.06; s.m.rotation.z = Math.sin(time * 0.6 + s.ph) * 0.03; });
    smallRocks.forEach((g) => {
      const u = g.userData;
      const a = u.a + time * u.sp;
      g.position.set(Math.cos(a) * u.rad, u.y + Math.sin(time * 0.6 + u.ph) * 0.9, Math.sin(a) * u.rad);
      g.rotation.y = time * u.sp * 2;
    });
    {
      const a = time * 0.035 + 2.2;
      airship.position.set(Math.cos(a) * 92, 36 + Math.sin(time * 0.4) * 1.5, Math.sin(a) * 92);
      airship.rotation.y = -a + Math.PI;
      airship.rotation.z = Math.sin(time * 0.5) * 0.03;
      prop.rotation.x += dtReal * 14;
    }
    flags.forEach((f) => {
      const p = f.mesh.geometry.attributes.position, b = f.mesh.userData.base, ph = f.mesh.userData.ph;
      for (let i = 0; i < p.count; i++) {
        const x = b[i * 3];
        p.setZ(i, Math.sin(x * 2.3 - time * 5 + ph) * 0.2 * x);
        p.setY(i, b[i * 3 + 1] + Math.sin(x * 1.6 - time * 3) * 0.05 * x);
      }
      p.needsUpdate = true;
      f.mesh.geometry.computeVertexNormals();
    });
    clouds.forEach((c) => {
      const u = c.userData;
      c.position.x = u.x0 + Math.sin(time * 0.03 * u.sp + u.ph) * 14;
    });
    birds.forEach((b) => {
      const u = b.userData;
      const a = u.a + time * u.sp;
      b.position.set(Math.cos(a) * u.rad, u.y + Math.sin(time * 0.8 + u.ph) * 1.5, Math.sin(a) * u.rad);
      b.rotation.y = -a;
      const f = Math.sin(time * 9 + u.ph) * 0.6;
      u.wl.rotation.z = f; u.wr.rotation.z = -f;
    });
    pieces.forEach((g) => {
      const u = g.userData;
      g.position.y = u.base.y + Math.sin(time * 0.8 + u.ph) * 0.8;
      u.spin *= Math.pow(0.12, dt);
      u.inner.rotation.y += (0.15 + u.spin) * dt;
      u.inner.rotation.z = Math.sin(time * 0.5 + u.ph) * 0.12;
    });
    const bp = burst.geometry.attributes.position, ba = burst.geometry.attributes.aAlpha;
    let live = false;
    for (let i = 0; i < BURST; i++) {
      if (bLife[i] <= 0) continue;
      live = true;
      bLife[i] -= dtReal * 0.8;
      bVel[i * 3 + 1] -= 6 * dtReal;
      bp.setXYZ(i, bp.getX(i) + bVel[i * 3] * dtReal, bp.getY(i) + bVel[i * 3 + 1] * dtReal, bp.getZ(i) + bVel[i * 3 + 2] * dtReal);
      ba.setX(i, Math.max(0, bLife[i]));
    }
    if (live) { bp.needsUpdate = true; ba.needsUpdate = true; }
    sparkSets.forEach((s) => { s.material.uniforms.uTime.value = time; });

    scrollTarget();
    if (introT0 === -1) {
      tgtPos.fromArray(INTRO.p); tgtLook.fromArray(INTRO.l);
      camPos.copy(tgtPos); camLook.copy(tgtLook);
    } else if (introT0 >= 0) {
      const t = Math.min(1, (now - introT0) / 1000 / introDur);
      const e = ease(t);
      camPos.copy(tmpA.fromArray(INTRO.p)).lerp(tgtPos, e);
      camLook.copy(tmpB.fromArray(INTRO.l)).lerp(tgtLook, e);
      if (t >= 1) introT0 = -2;
    } else if (reduced && !readySent) {
      camPos.copy(tgtPos); camLook.copy(tgtLook);
    } else {
      const k = 1 - Math.exp(-dtReal * (reduced ? 6 : 1.8));
      camPos.lerp(tgtPos, k);
      camLook.lerp(tgtLook, k);
    }
    mouse.sx += (mouse.x - mouse.sx) * Math.min(1, dtReal * 1.8);
    mouse.sy += (mouse.y - mouse.sy) * Math.min(1, dtReal * 1.8);
    camera.position.copy(camPos);
    camera.lookAt(camLook);
    if (!reduced && !mobile) {
      tmpA.set(1, 0, 0).applyQuaternion(camera.quaternion).multiplyScalar(mouse.sx * 2.2);
      tmpB.copy(upVec).multiplyScalar(mouse.sy * 1.3);
      camera.position.add(tmpA).add(tmpB);
      camera.lookAt(camLook);
    }
    sky.position.copy(camera.position);

    if (mouse.dirty) {
      mouse.dirty = false;
      const hit = mouse.over ? pickAt(mouse.x, mouse.y) : null;
      const grp = hit ? hit.grp : null;
      if (grp !== hovered) {
        hovered = grp;
        html.classList.toggle('picking', !!grp);
      }
    }
    pickables.forEach((grp) => {
      const u = grp.userData;
      const target = grp === hovered ? 1 : 0;
      u.flash = Math.max(0, (u.flash || 0) - dtReal * 1.5);
      const v = Math.max(target, u.flash);
      if (Math.abs(u.hover - v) < 0.001) return;
      u.hover += (v - u.hover) * Math.min(1, dtReal * 8);
      u.hl.forEach((m) => { m.emissive.copy(hlColor); m.emissiveIntensity = u.hover * 0.4; });
      if (u.halo) u.halo.material.opacity = u.hover * 0.8;
      if (u.inner) u.inner.scale.setScalar((u.inner.userData.s0 || (u.inner.userData.s0 = u.inner.scale.x)) * (1 + u.hover * 0.06));
    });

    renderer.render(scene, camera);
    if (debug) {
      const ms = performance.now() - now;
      debug.n++; debug.ms += ms; debug.max = Math.max(debug.max, ms);
      debug.calls = renderer.info.render.calls; debug.tris = renderer.info.render.triangles; debug.pr = pr;
    }
    if (!readySent) { readySent = true; o.onReady && o.onReady(); }
  }
  renderer.compile(scene, camera);
  requestAnimationFrame(frame);

  return {
    intro() {
      if (introT0 !== -1) return;
      introT0 = performance.now();
    },
    celebrate() {
      spawnBurst(new THREE.Vector3(0, isle.position.y + 30, -4.6), 80, 12);
    },
  };
}
