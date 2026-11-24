"""Pengelola overlay kaca: menempatkan komponen di layar, animasi, latar buram, dan pembaruan hemat.

Komponen (masing-masing satu jendela overlay; semua tembus-klik KECUALI tombol kontrol):
  pulau dinamis (atas tengah) | kartu kamera (kanan bawah) + tombol Jeda/Tutup di atasnya |
  panduan gestur (kiri) | halo kursor | menu kaca (tengah) + titik kursor menu
"""

import time

import cv2
from PIL import Image, ImageFilter

from . import glass
from . import hud
from .overlay import OverlayWindow, grab_region, pump_messages, work_area


class GlassUI:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        uc = cfg["ui"]
        self.log = log
        self.blur = bool(uc["blur"])
        ex = self.blur  # kaca buram mensyaratkan overlay tak ikut tertangkap layar
        self.w_island = OverlayWindow(ex)
        self.w_cam = OverlayWindow(ex)
        self.w_guide = OverlayWindow(ex)
        self.w_halo = OverlayWindow(ex)
        self.w_menu = OverlayWindow(ex)
        self.w_mcur = OverlayWindow(ex)
        self.w_ctrl = OverlayWindow(ex, on_click=self._on_ctrl_click)  # satu-satunya yang bisa diklik
        self.windows = [self.w_island, self.w_cam, self.w_guide, self.w_halo, self.w_menu, self.w_mcur,
                        self.w_ctrl]
        self.ctrl_boxes = {}
        self.request = None
        self.cam_top = None
        self.wa = work_area()
        x0, y0, x1, y1 = self.wa  # ukuran menu dari layar penuh; posisi komponen mengikuti jendela AutoCAD
        self.mw = int(min(1180, (x1 - x0) * 0.62))
        self.mh = int(self.mw * 0.56)
        self.menu_painter = glass.MenuPainter(self.mw, self.mh)
        self.show_cam = bool(uc["camera_card"])
        self.show_guide = bool(uc["guide"])
        self.show_halo = bool(uc["cursor_halo"])
        self.cam_w = int(uc["camera_width"])
        self.island_w = 260.0
        self.keys = {}
        self.bg = {}
        self.bg_seq = 0
        self.menu_was_open = False
        self.ripples = []
        self.last_raise = 0.0
        self.last_cam = 0.0

    # ------------------------------------------------------------ util
    def prewarm(self, menu):
        """Siapkan cache gambar menu & efek kaca saat mulai, supaya menu pertama terbuka instan."""
        t0 = time.perf_counter()
        self.menu_painter.render({"menu": menu, "hover": None})
        self.log("UI kaca siap (%.1f s); font: %s" % (time.perf_counter() - t0,
                                                      "Artifakt Element" if glass.artifakt() else "Segoe UI"))

    def _on_ctrl_click(self, x, y):
        for name, (bx0, by0, bx1, by1) in self.ctrl_boxes.items():
            if bx0 <= x <= bx1 and by0 <= y <= by1:
                self.request = name

    def take_request(self):
        """'quit' / 'pause' dari tombol kontrol (diklik mouse atau jepitan), sekali baca."""
        r, self.request = self.request, None
        return r

    def toggle_guide(self):
        self.show_guide = not self.show_guide

    def toggle_camera(self):
        self.show_cam = not self.show_cam

    def _changed(self, name, key):
        if self.keys.get(name) == key:
            return False
        self.keys[name] = key
        return True

    def _backdrop(self, name, box, interval=0.2, force=False):
        """Latar buram di bawah komponen (diambil dari layar; overlay sendiri tidak ikut tertangkap)."""
        if not self.blur:
            return None, 0
        now = time.monotonic()
        hit = self.bg.get(name)
        if hit and not force and now - hit[0] < interval and hit[3] == box:
            return hit[1], hit[2]
        try:
            shot = grab_region(box)
        except OSError:
            return (hit[1], hit[2]) if hit else (None, 0)
        small = shot.resize((max(1, shot.width // 4), max(1, shot.height // 4)), Image.BILINEAR)
        img = small.filter(ImageFilter.GaussianBlur(3))
        self.bg_seq += 1
        self.bg[name] = (now, img, self.bg_seq, box)
        return img, self.bg_seq

    def close(self):
        for w in self.windows:
            w.destroy()

    # ------------------------------------------------------------ per frame
    def _anchor(self, rect):
        """Tempelkan overlay ke jendela AutoCAD (dipotong ke area kerja layar)."""
        full = work_area()
        if rect:
            r = (max(rect[0], full[0]), max(rect[1], full[1]), min(rect[2], full[2]), min(rect[3], full[3]))
            if r[2] - r[0] < 500 or r[3] - r[1] < 400:
                r = full
        else:
            r = full
        if r != self.wa:
            self.wa = r
            self.keys.clear()  # posisi berubah: gambar & tempatkan ulang semua komponen

    def frame(self, frame_bgr, hands, view, status, cursor, clicks, t):
        pump_messages()
        self._anchor(status.get("rect"))
        x0, y0, x1, y1 = self.wa
        now = time.monotonic()
        if now - self.last_raise > 2.0:  # palet AutoCAD juga bisa "topmost": naikkan berkala
            for w in self.windows:
                if w.visible:
                    w.raise_top()
            self.last_raise = now

        menu_open = view.get("menu") is not None

        # --- pulau dinamis
        c = glass.island_content(view, status, t)
        target = glass.island_width(c)
        self.island_w += (target - self.island_w) * 0.35
        if abs(target - self.island_w) < 1.0:
            self.island_w = float(target)
        w = int(round(self.island_w / 16.0)) * 16  # ukuran diskret -> efek kaca ter-cache, animasi tetap halus
        hold_pose, prog = view["hold"]
        ikey = (c["title"], c["sub"], c["icon"], c["expanded"], w, view.get("pose"), view["armed"], view["mode"],
                hold_pose, round(prog, 2), round(view.get("arm_progress", 0), 2), status.get("gate_ok"))
        if self._changed("island", ikey):
            ix, iy = (x0 + x1) // 2 - w // 2, y0 + 6
            bg, _ = self._backdrop("island", (ix, iy, ix + w, iy + 60), interval=0.5)
            img, pad = glass.draw_island(view, status, t, w, bg=bg)
            self.w_island.update(_np(img), ix - pad, iy - pad)

        # --- kartu kamera (maks ~20 fps)
        if self.show_cam and frame_bgr is not None:
            if now - self.last_cam >= 0.05:
                self.last_cam = now
                f = frame_bgr.copy()
                hud.draw_hands(f, hands, view.get("primary"), _bgr(glass.MODE_COLOR.get(view["mode"], glass.SOFT)))
                two = view.get("two")
                if two and two.get("pts"):  # garis pegangan antar-tangan (umpan balik, bukan hiasan)
                    h_, w_ = f.shape[:2]
                    a, b = [(int(p[0] * w_), int(p[1] * h_)) for p in two["pts"]]
                    mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
                    cv2.line(f, a, b, (255, 224, 64), 3, cv2.LINE_AA)
                    for q in (a, b):
                        cv2.circle(f, q, 10, (255, 224, 64), 2, cv2.LINE_AA)
                    cv2.circle(f, mid, 6, (255, 255, 255), -1, cv2.LINE_AA)
                if menu_open:
                    zx0, zy0, zx1, zy1 = view["zone"]
                    h_, w_ = f.shape[:2]
                    cv2.rectangle(f, (int(zx0 * w_), int(zy0 * h_)), (int(zx1 * w_), int(zy1 * h_)),
                                  (64, 179, 255), 2, cv2.LINE_AA)
                rgb = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
                img, pad = glass.draw_camera_card(rgb, view, status, self.cam_w)
                cy0 = y1 - img.height + pad - 34
                self.w_cam.update(_np(img), x1 - img.width + pad - 16, cy0)
                self.cam_top = cy0 + pad
        else:
            self.w_cam.hide()
            self.cam_top = None

        # --- tombol kontrol Jeda / Tutup (di atas kartu kamera, rata kanan)
        cw = 2 * glass.CTRL_BTN[0] + 6 + 10
        ch = glass.CTRL_BTN[1] + 10
        bx = x1 - 16 - cw
        by = (self.cam_top if self.cam_top is not None else y1 - 40) - ch - 8
        hover = None
        if cursor is not None:
            for name, (bx0, by0, bx1, by1) in self.ctrl_boxes.items():
                off = self.w_ctrl.pos
                if bx0 <= cursor[0] - off[0] <= bx1 and by0 <= cursor[1] - off[1] <= by1:
                    hover = name
        if self._changed("ctrl", (view["armed"], hover, bx, by)):
            img, pad, boxes = glass.draw_controls(view["armed"], hover)
            self.ctrl_boxes = boxes
            self.w_ctrl.update(_np(img), bx - pad, by - pad)

        # --- panduan
        if self.show_guide and not menu_open:
            gkey = (view.get("pose"), tuple(view["continuous"].items()), tuple(view["discrete"].items()))
            if self._changed("guide", gkey) or not self.w_guide.visible:
                gx, gy = x0 + 14, y0 + int((y1 - y0) * 0.26)
                bg, _ = self._backdrop("guide", (gx, gy, gx + 236, gy + 400), interval=1.0)
                img, pad = glass.draw_guide(view, bg=bg)
                self.w_guide.update(_np(img), gx - pad, gy - pad)
        else:
            self.w_guide.hide()
            self.keys.pop("guide", None)

        # --- halo kursor + riak klik
        for kind in clicks:
            self.ripples.append((t, kind))
        self.ripples = [r for r in self.ripples if t - r[0] < 0.4]
        active = view["armed"] and status.get("gate_ok", True) and not menu_open and \
            view["mode"] in ("KURSOR", "KLIK/DRAG", "ORBIT", "PAN", "ZOOM")
        if self.show_halo and cursor is not None and (active or self.ripples):
            hkey = (view["mode"], view.get("ptr_state"), round(view.get("preclick", 0), 1),
                    view.get("press_t") is not None and round(t - view["press_t"], 1), len(self.ripples) > 0,
                    round(t, 2) if self.ripples else 0)
            if self._changed("halo", hkey):
                img = glass.draw_halo(view, self.ripples, t)
                self.w_halo.update(_np(img), cursor[0] - img.width // 2, cursor[1] - img.height // 2)
            else:
                self.w_halo.move(cursor[0] - 48, cursor[1] - 48)
        else:
            self.w_halo.hide()
            self.keys.pop("halo", None)

        # --- menu kaca
        if menu_open:
            mx, my = (x0 + x1) // 2 - self.mw // 2, (y0 + y1) // 2 - self.mh // 2
            if not self.menu_was_open:
                self._backdrop("menu", (mx, my, mx + self.mw, my + self.mh), force=True)
            bg_hit = self.bg.get("menu")
            bg, bg_id = (bg_hit[1], bg_hit[2]) if (bg_hit and self.blur) else (None, 0)
            hv = view.get("hover")
            mkey = (view["menu"].page, hv.id if hv else None, bg_id)
            if self._changed("menu", mkey) or not self.w_menu.visible:
                img, pad = self.menu_painter.render(view, bg=bg, bg_id=bg_id)
                self.w_menu.update(_np(img), mx - pad, my - pad)
            cur = view.get("menu_cursor")
            if cur is not None:
                dw = round(view.get("dwell_progress", 0), 2)
                cx, cy = mx + int(cur[0] * self.mw), my + int(cur[1] * self.mh)
                if self._changed("mcur", dw):
                    self.w_mcur.update(_np(glass.draw_menu_cursor(dw)), cx - 32, cy - 32)
                else:
                    self.w_mcur.move(cx - 32, cy - 32)
            else:
                self.w_mcur.hide()
        else:
            self.w_menu.hide()
            self.w_mcur.hide()
            self.keys.pop("menu", None)
            self.keys.pop("mcur", None)
        self.menu_was_open = menu_open


def _np(img):
    import numpy as np

    return np.asarray(img.convert("RGBA"))


def _bgr(rgba):
    return (rgba[2], rgba[1], rgba[0])
