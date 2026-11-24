"""Klasifikasi pose tangan dari 21 titik landmark MediaPipe.

Semua fungsi di sini murni (tanpa kamera, tanpa Windows) supaya bisa diuji dengan tangan sintetis.

Indeks landmark MediaPipe:
  0 pergelangan | ibu jari 1-4 | telunjuk 5-8 | tengah 9-12 | manis 13-16 | kelingking 17-20
  (urutan per jari: MCP/pangkal, PIP, DIP, TIP/ujung; ibu jari: CMC, MCP, IP, TIP)

Koordinat `iso` = piksel isotropik (x ke kanan, y ke bawah, z kedalaman relatif dalam skala x),
sehingga jarak dan sudut tidak terdistorsi rasio aspek kamera.
"""

import math

WRIST = 0
THUMB = (1, 2, 3, 4)
INDEX = (5, 6, 7, 8)
MIDDLE = (9, 10, 11, 12)
RING = (13, 14, 15, 16)
PINKY = (17, 18, 19, 20)
FINGERS = {"index": INDEX, "middle": MIDDLE, "ring": RING, "pinky": PINKY}

# Nama pose (dipakai di config.json)
POINT = "POINT"          # telunjuk saja
PINCH = "PINCH"          # ujung ibu jari menyentuh ujung telunjuk
FIST = "FIST"            # mengepal
OPEN = "OPEN"            # telapak terbuka (4 jari lurus)
VICTORY = "VICTORY"      # telunjuk + tengah
THREE = "THREE"          # telunjuk + tengah + manis
ROCK = "ROCK"            # telunjuk + kelingking
SHAKA = "SHAKA"          # ibu jari + kelingking
THUMB_UP = "THUMB_UP"
THUMB_DOWN = "THUMB_DOWN"
UNKNOWN = "UNKNOWN"

ALL_POSES = (POINT, PINCH, FIST, OPEN, VICTORY, THREE, ROCK, SHAKA, THUMB_UP, THUMB_DOWN)

DEFAULT_THRESHOLDS = {
    "finger_ratio": 1.12,      # jarak pergelangan->ujung / pergelangan->PIP di atas ini = jari lurus
    "finger_cos": 0.2,         # kelurusan sendi PIP (cos sudut antar ruas)
    "thumb_reach": 0.5,        # ujung ibu jari ke pangkal telunjuk / ukuran tangan
    "thumb_vertical": 0.7,     # komponen vertikal arah ibu jari untuk jempol atas/bawah (~45 derajat)
    "pinch_on": 0.25,          # jarak ujung ibu jari ke ujung/ruas atas telunjuk / ukuran tangan (mulai jepit)
    "pinch_off": 0.38,         # histeresis: lepas jepit di atas ini
    "pinch_min_reach": 1.0,    # ujung telunjuk harus jauh dari pergelangan (bukan kepalan)
    "edge_margin": 0.025,      # jari sedekat ini ke tepi gambar = posisinya tebakan -> pose diabaikan
}


def fingers_near_edge(norm, margin):
    """True bila ada titik jari (bukan pergelangan) di luar/menempel tepi gambar.

    MediaPipe tetap mengembalikan titik untuk jari yang terpotong frame, tetapi posisinya tebakan
    (sering dianggap menekuk). Pergelangan + pangkal ibu jari dikecualikan karena wajar terpotong di bawah frame.
    """
    lo, hi = margin, 1.0 - margin
    return any(not (lo <= x <= hi and lo <= y <= hi) for (x, y, _z) in norm[2:])


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(a))))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(len(a)))


def _cos(u, v):
    nu = math.sqrt(sum(c * c for c in u))
    nv = math.sqrt(sum(c * c for c in v))
    if nu < 1e-9 or nv < 1e-9:
        return 1.0
    return sum(u[i] * v[i] for i in range(len(u))) / (nu * nv)


def hand_size(p):
    """Jarak pergelangan ke pangkal jari tengah — skala acuan semua ambang."""
    return max(dist(p[WRIST], p[MIDDLE[0]]), 1e-6)


def finger_extended(p, finger, th):
    mcp, pip, dip, tip = finger
    ratio = dist(p[WRIST], p[tip]) / max(dist(p[WRIST], p[pip]), 1e-6)
    straight = _cos(_sub(p[pip], p[mcp]), _sub(p[tip], p[pip]))
    return ratio > th["finger_ratio"] and straight > th["finger_cos"]


def thumb_extended(p, th):
    size = hand_size(p)
    reach = dist(p[THUMB[3]], p[INDEX[0]]) / size
    outward = dist(p[THUMB[3]], p[PINKY[0]]) > dist(p[THUMB[2]], p[PINKY[0]])
    return reach > th["thumb_reach"] and outward


def thumb_direction(p):
    """Vektor satuan arah ibu jari (pangkal MCP -> ujung) dalam bidang gambar."""
    d = _sub(p[THUMB[3]], p[THUMB[1]])[:2]
    n = math.hypot(d[0], d[1])
    if n < 1e-9:
        return (0.0, 0.0)
    return (d[0] / n, d[1] / n)


def finger_states(p, th=None):
    th = th or DEFAULT_THRESHOLDS
    s = {name: finger_extended(p, f, th) for name, f in FINGERS.items()}
    s["thumb"] = thumb_extended(p, th)
    return s


def pinch_ratio(p):
    """Jarak ujung ibu jari ke ujung ATAU ruas atas (DIP) telunjuk, dibagi ukuran tangan.

    Menerima ruas atas supaya "menekan jempol ke sisi telunjuk" juga dihitung klik: ujung telunjuk
    tidak perlu bergerak, sehingga kursor tidak ikut tergeser saat mengklik.
    """
    tip = p[THUMB[3]]
    return min(dist(tip, p[INDEX[3]]), dist(tip, p[INDEX[2]])) / hand_size(p)


def classify(p, was_pinching=False, th=None):
    """Kembalikan (pose, info). `was_pinching` memberi histeresis supaya klik tidak berkedip."""
    th = th or DEFAULT_THRESHOLDS
    s = finger_states(p, th)
    size = hand_size(p)
    pr = pinch_ratio(p)
    reach = dist(p[WRIST], p[INDEX[3]]) / size
    info = {"fingers": s, "pinch": pr, "size": size}

    limit = th["pinch_off"] if was_pinching else th["pinch_on"]
    if pr < limit and reach > th["pinch_min_reach"]:
        return PINCH, info

    i, m, r, k, t = s["index"], s["middle"], s["ring"], s["pinky"], s["thumb"]
    if i and m and r and k:
        return OPEN, info
    if not (i or m or r or k):
        if t:
            dy = thumb_direction(p)[1]
            if dy < -th["thumb_vertical"]:
                return THUMB_UP, info
            if dy > th["thumb_vertical"]:
                return THUMB_DOWN, info
            return UNKNOWN, info
        return FIST, info
    if i and not m and not r and not k:
        return POINT, info
    if i and m and not r and not k:
        return VICTORY, info
    if i and m and r and not k:
        return THREE, info
    if i and k and not m and not r:
        return ROCK, info
    if k and t and not i and not m and not r:
        return SHAKA, info
    return UNKNOWN, info


def palm_center(p):
    idx = (WRIST, INDEX[0], MIDDLE[0], RING[0], PINKY[0])
    return (sum(p[i][0] for i in idx) / 5.0, sum(p[i][1] for i in idx) / 5.0)


class Hand:
    """Satu tangan terdeteksi.

    label : "Left"/"Right" (sudah benar untuk gambar yang dicerminkan)
    norm  : 21 titik (x, y, z) ternormalisasi 0..1 terhadap frame
    iso   : 21 titik dalam piksel isotropik (untuk klasifikasi)
    """

    def __init__(self, label, score, norm, iso, width=640, height=480):
        self.label = label
        self.score = score
        self.norm = norm
        self.iso = iso
        self.aspect = float(height) / float(width)  # ubah dy ternormalisasi ke satuan lebar frame

    @classmethod
    def from_norm(cls, label, score, norm, width, height):
        iso = [(x * width, y * height, z * width) for (x, y, z) in norm]
        return cls(label, score, norm, iso, width, height)
