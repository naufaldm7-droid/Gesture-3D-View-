"""Pembuat tangan sintetis (21 landmark) untuk menguji klasifikasi dan state machine tanpa kamera."""

import math

from gesture_cad.gestures import Hand

W, H = 640, 480
SIZE_PX = 100.0  # ukuran tangan (pergelangan -> pangkal jari tengah) dalam piksel

_MCP = {"index": (-0.3, -1.0), "middle": (0.0, -1.0), "ring": (0.25, -0.95), "pinky": (0.48, -0.85)}
_ORDER = ("index", "middle", "ring", "pinky")


def _finger(name, extended):
    x, y = _MCP[name]
    if extended:
        return [(x, y, 0.0), (x, y - 0.4, 0.0), (x, y - 0.65, 0.0), (x, y - 0.85, 0.0)]
    return [(x, y, 0.0), (x, y - 0.25, -0.2), (x, y - 0.05, -0.35), (x, y + 0.15, -0.25)]


def base_points(thumb=False, index=False, middle=False, ring=False, pinky=False, pinch=False):
    pts = [(0.0, 0.0, 0.0), (-0.3, -0.2, 0.0), (-0.55, -0.4, 0.0)]
    if pinch:
        pts += [(-0.65, -0.95, 0.0), (-0.62, -1.45, 0.0)]
    elif thumb:
        pts += [(-0.78, -0.58, 0.0), (-0.98, -0.74, 0.0)]
    else:
        pts += [(-0.4, -0.62, -0.1), (-0.12, -0.72, -0.15)]
    flags = {"index": index, "middle": middle, "ring": ring, "pinky": pinky}
    for name in _ORDER:
        if name == "index" and pinch:
            pts += [(-0.3, -1.0, 0.0), (-0.38, -1.35, 0.0), (-0.48, -1.5, 0.0), (-0.6, -1.52, 0.0)]
        else:
            pts += _finger(name, flags[name])
    return pts


def rotate(pts, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c, z) for (x, y, z) in pts]


def thumb_pointing(pts, up=True):
    """Putar tangan supaya ibu jari menunjuk lurus ke atas (atau ke bawah)."""
    dx, dy = pts[4][0] - pts[2][0], pts[4][1] - pts[2][1]
    cur = math.degrees(math.atan2(dy, dx))
    want = -90.0 if up else 90.0
    return rotate(pts, want - cur)


def make_hand(pts, center=(0.5, 0.6), label="Right", anchor=None, at=None):
    """Ubah titik satuan-tangan ke Hand. `anchor`+`at`: geser supaya landmark `anchor` berada di `at` (norm)."""
    cx, cy = center
    norm = [(cx + x * SIZE_PX / W, cy + y * SIZE_PX / H, z * SIZE_PX / W) for (x, y, z) in pts]
    if anchor is not None and at is not None:
        ox, oy = at[0] - norm[anchor][0], at[1] - norm[anchor][1]
        norm = [(x + ox, y + oy, z) for (x, y, z) in norm]
    return Hand.from_norm(label, 0.99, norm, W, H)


POSES = {
    "POINT": dict(index=True),
    "PINCH": dict(pinch=True),
    "FIST": dict(),
    "OPEN": dict(thumb=True, index=True, middle=True, ring=True, pinky=True),
    "VICTORY": dict(index=True, middle=True),
    "THREE": dict(index=True, middle=True, ring=True),
    "ROCK": dict(index=True, pinky=True),
    "SHAKA": dict(thumb=True, pinky=True),
}


def pose_points(name):
    if name == "THUMB_UP":
        return thumb_pointing(base_points(thumb=True), up=True)
    if name == "THUMB_DOWN":
        return thumb_pointing(base_points(thumb=True), up=False)
    return base_points(**POSES[name])


def hand(name, center=(0.5, 0.6), label="Right", **kw):
    return make_hand(pose_points(name), center, label, **kw)


def hand_aim(name, target, zone, tip_weight, label="Right"):
    """Tangan yang titik tunjuknya (dipetakan lewat zona kursor) jatuh tepat di `target` (0..1)."""
    h = hand(name, label=label)
    mcp, tip = h.norm[5], h.norm[8]
    a = (mcp[0] + (tip[0] - mcp[0]) * tip_weight, mcp[1] + (tip[1] - mcp[1]) * tip_weight)
    x0, y0, x1, y1 = zone
    want = (x0 + target[0] * (x1 - x0), y0 + target[1] * (y1 - y0))
    ox, oy = want[0] - a[0], want[1] - a[1]
    norm = [(x + ox, y + oy, z) for (x, y, z) in h.norm]
    return Hand.from_norm(label, 0.99, norm, W, H)
