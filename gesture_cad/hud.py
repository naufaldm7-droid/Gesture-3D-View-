"""Tampilan HUD (OpenCV): gambar kamera, kerangka tangan, mode, cincin tahan, menu udara, dan contekan gestur."""

import math

import cv2
import numpy as np

from . import controller as C
from . import gestures as G

FONT = cv2.FONT_HERSHEY_SIMPLEX
PANEL_W = 270

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (150, 150, 150)
GREEN = (90, 200, 90)
RED = (60, 60, 230)
AMBER = (40, 180, 250)
CYAN = (230, 200, 60)

MODE_COLOR = {
    C.DISARMED: GREY, C.IDLE: WHITE, C.POINTER: GREEN, C.DRAG: RED,
    C.ORBIT: (230, 120, 60), C.PAN: CYAN, C.ZOOM: (200, 90, 220), C.MENU: AMBER,
}

POSE_TEXT = {
    G.POINT: "telunjuk", G.PINCH: "jepit jempol+telunjuk", G.FIST: "kepal",
    G.VICTORY: "2 jari (V)", G.THREE: "3 jari", G.OPEN: "telapak terbuka",
    G.THUMB_UP: "jempol ke atas", G.THUMB_DOWN: "jempol ke bawah",
    G.ROCK: "telunjuk+kelingking", G.SHAKA: "jempol+kelingking",
}
MODE_TEXT = {
    "pointer": "kursor", "drag": "klik/drag", "orbit": "orbit 3D",
    "pan": "pan", "zoom": "zoom naik/turun", "idle": "berhenti",
}

BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
         (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def _text(img, s, org, scale=0.5, color=WHITE, thick=1):
    cv2.putText(img, s, org, FONT, scale, BLACK, thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, FONT, scale, color, thick, cv2.LINE_AA)


def _px(p, w, h):
    return (int(p[0] * w), int(p[1] * h))


def _blend_rect(img, p0, p1, color, alpha):
    x0, y0 = max(p0[0], 0), max(p0[1], 0)
    x1, y1 = min(p1[0], img.shape[1]), min(p1[1], img.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    overlay = np.empty_like(roi)
    overlay[:] = color
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def _ring(img, center, radius, progress, color, label=None):
    cv2.circle(img, center, radius, (60, 60, 60), 4, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(img, center, (radius, radius), -90, 0, int(360 * progress), color, 5, cv2.LINE_AA)
    if label:
        (tw, _), _ = cv2.getTextSize(label, FONT, 0.6, 2)
        _text(img, label, (center[0] - tw // 2, center[1] + 6), 0.6, color, 2)


def draw_hands(img, hands, primary, color):
    h, w = img.shape[:2]
    for hand in hands:
        main = hand is primary
        col = color if main else GREY
        pts = [_px(p, w, h) for p in hand.norm]
        for a, b in BONES:
            cv2.line(img, pts[a], pts[b], col, 2 if main else 1, cv2.LINE_AA)
        for i, p in enumerate(pts):
            cv2.circle(img, p, 4 if i in (4, 8) else 2, col, -1, cv2.LINE_AA)
        _text(img, hand.label, (pts[0][0] - 20, pts[0][1] + 22), 0.45, col)


def draw_menu(img, view):
    h, w = img.shape[:2]
    menu = view["menu"]
    hover = view["hover"]
    _blend_rect(img, (0, 0), (w, h), (20, 20, 20), 0.35)
    for b in menu.buttons():
        x0, y0, x1, y1 = b.rect
        p0, p1 = (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h))
        active = b.kind == "tab" and b.payload == menu.page
        is_hover = hover is not None and hover.id == b.id
        base = (70, 140, 230) if active else ((60, 60, 200) if b.kind == "close" else (60, 60, 60))
        _blend_rect(img, p0, p1, base, 0.75 if (is_hover or active) else 0.55)
        if is_hover and view["dwell_progress"] > 0:
            fill_x = p0[0] + int((p1[0] - p0[0]) * view["dwell_progress"])
            _blend_rect(img, p0, (fill_x, p1[1]), (60, 200, 90), 0.6)
        cv2.rectangle(img, p0, p1, AMBER if is_hover else (200, 200, 200), 2 if is_hover else 1, cv2.LINE_AA)
        scale = 0.5 if b.kind != "item" else 0.55
        (tw, th), _ = cv2.getTextSize(b.label, FONT, scale, 1)
        _text(img, b.label, ((p0[0] + p1[0] - tw) // 2, (p0[1] + p1[1] + th) // 2), scale, WHITE, 1)
    cur = view.get("menu_cursor")
    if cur is not None and view["primary"] is not None:
        c = _px(cur, w, h)
        cv2.circle(img, c, 11, AMBER, 2, cv2.LINE_AA)
        cv2.circle(img, c, 3, AMBER, -1, cv2.LINE_AA)
    x0, y0, x1, y1 = view["zone"]
    cv2.rectangle(img, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (120, 120, 120), 1, cv2.LINE_AA)
    _text(img, "Tunjuk = sorot | tahan diam / jepit = pilih | telunjuk+kelingking = tutup",
          (10, h - 10), 0.42, WHITE)


def draw_panel(view, height, acad_status, gate_text, fps, hold_ms=600):
    panel = np.full((height, PANEL_W, 3), 32, np.uint8)
    y = 24

    def line(s, color=WHITE, scale=0.45, dy=19):
        nonlocal y
        _text(panel, s, (10, y), scale, color)
        y += dy

    line("GESTURE CAD", AMBER, 0.6, 24)
    line("AKTIF" if view["armed"] else "DIJEDA", GREEN if view["armed"] else RED, 0.55, 22)
    line("Mode : %s" % view["mode"], MODE_COLOR.get(view["mode"], WHITE))
    line("Pose : %s" % (view["pose"] or "-"))
    line(acad_status, GREEN if "terhubung" in acad_status else AMBER, 0.42)
    line(gate_text, GREEN if gate_text.startswith("Target") else AMBER, 0.42)
    line("FPS  : %.0f" % fps, GREY, 0.42, 26)

    line("GERAK (terus)", AMBER, 0.48)
    for pose, mode in view["continuous"].items():
        line("%s > %s" % (POSE_TEXT.get(pose, pose), MODE_TEXT.get(mode, mode)), WHITE, 0.4, 17)
    y += 6
    line("TAHAN %.1f s (sekali)" % (hold_ms / 1000.0), AMBER, 0.48)
    for pose, label in view["discrete"].items():
        line("%s > %s" % (POSE_TEXT.get(pose, pose), label), WHITE, 0.4, 17)
    y += 6
    line("2 telapak 1.5 s = aktif/jeda", AMBER, 0.4, 17)
    line("Ctrl+Alt+G = aktif/jeda", AMBER, 0.4, 17)
    line("Q / Esc (di jendela ini) = keluar", GREY, 0.4, 17)
    line("H = sembunyikan panel", GREY, 0.4, 17)
    return panel


def render(frame, hands, view, acad_status, gate_text, fps, show_help=True, hold_ms=600):
    img = frame
    h, w = img.shape[:2]
    mode = view["mode"]
    color = MODE_COLOR.get(mode, WHITE)

    if mode in (C.IDLE, C.POINTER, C.DRAG):
        x0, y0, x1, y1 = view["zone"]
        cv2.rectangle(img, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (90, 90, 90), 1, cv2.LINE_AA)

    draw_hands(img, hands, view["primary"], color)

    if view["menu"] is not None:
        draw_menu(img, view)

    prim = view["primary"]
    pose, prog = view["hold"]
    if prim is not None and pose and prog > 0:
        c = _px(G.palm_center(prim.norm), w, h)
        _ring(img, c, 42, prog, AMBER, view["discrete"].get(pose, pose))

    if view["arm_progress"] > 0:
        bw = int(w * 0.6)
        x0 = (w - bw) // 2
        _blend_rect(img, (x0, h // 2 - 14), (x0 + bw, h // 2 + 14), (40, 40, 40), 0.7)
        _blend_rect(img, (x0, h // 2 - 14), (x0 + int(bw * view["arm_progress"]), h // 2 + 14), (60, 180, 90), 0.8)
        _text(img, "JEDA" if view["armed"] else "AKTIFKAN", (x0 + 8, h // 2 + 7), 0.55, WHITE, 1)

    # bar status atas
    _blend_rect(img, (0, 0), (w, 30), (0, 0, 0), 0.5)
    _text(img, "%s  |  %s" % ("AKTIF" if view["armed"] else "DIJEDA", mode), (10, 21), 0.6, color, 2)
    raw = view["raw_pose"] or "-"
    _text(img, raw, (w - 140, 21), 0.5, GREY)

    if view.get("edge"):
        _blend_rect(img, (0, 30), (w, 56), (0, 0, 120), 0.6)
        _text(img, "Jari terpotong tepi kamera - geser tangan ke tengah", (10, 49), 0.5, WHITE)

    toasts = view["toasts"]
    if toasts:
        msg = toasts[-1][0]
        (tw, th), _ = cv2.getTextSize(msg, FONT, 1.0, 2)
        org = ((w - tw) // 2, h - 40)
        _blend_rect(img, (org[0] - 12, org[1] - th - 12), (org[0] + tw + 12, org[1] + 12), (0, 0, 0), 0.6)
        _text(img, msg, org, 1.0, AMBER, 2)

    if not show_help:
        return img
    panel = draw_panel(view, h, acad_status, gate_text, fps, hold_ms)
    return np.hstack([img, panel])
