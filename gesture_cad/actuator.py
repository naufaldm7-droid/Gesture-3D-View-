"""Menerjemahkan niat dari Controller menjadi mouse/keyboard Windows dan perintah ke aplikasi host
(AutoCAD lewat COM, SketchUp lewat jembatan Ruby).

Pengaman:
- Input mouse/keyboard hanya dikirim bila jendela di depan adalah AutoCAD (bisa dimatikan --any-window).
- Semua tombol yang sedang ditekan dicatat dan SELALU dilepas saat tangan hilang, jeda, atau keluar.
"""

from collections import deque

from .keys import VK, parse_combo

SHIFT = VK["SHIFT"]


class SimInput:
    """Pengganti WinInput untuk mode simulasi/uji: mencatat, tidak menyentuh sistem."""

    simulated = True

    def __init__(self, log=None, rect=(0, 0, 1920, 1080), foreground_name="acad.exe", window=None):
        self.log = log
        self.window = window      # kotak jendela AutoCAD (None = sama dengan layar)
        self.events = deque(maxlen=5000)
        self.rect = rect
        self.fg_name = foreground_name
        self.pos = ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)

    def _rec(self, *ev):
        self.events.append(ev)
        if self.log:
            self.log("SIM %s" % (ev,))

    def cursor(self):
        return self.pos

    def set_cursor(self, x, y):
        self.pos = (x, y)
        self.events.append(("cursor", int(round(x)), int(round(y))))  # tidak di-log: terlalu ramai

    def button(self, name, down):
        self._rec("button", name, down)

    def wheel(self, ticks):
        self._rec("wheel", ticks)

    def key(self, vk, down):
        self._rec("key", vk, down)

    def tap_combo(self, combo):
        self._rec("combo", combo)

    def type_text(self, text):
        self._rec("type", text)

    def key_down_now(self, vk):
        return False

    def foreground(self):
        return 1, self.fg_name

    def window_rect(self, hwnd):
        return self.window or self.rect

    def screen_rect(self):
        return self.rect

    def activate(self, hwnd):
        return True


class Actuator:
    def __init__(self, cfg, win, acad=None, gate=True, log=print):
        self.cfg = cfg
        self.win = win
        self.acad = acad
        self.bridge = None        # jembatan SketchUp (SketchUpLink), bila host = sketchup
        self.host_label = cfg["host"]["label"]
        nav = cfg["output"]["nav"]  # pengubah yang ditahan bersama tombol tengah, per jenis seret
        self.nav = {k: [VK[m.upper()] for m in v] for k, v in nav.items()}
        self.target_hwnd = None   # jendela host terakhir yang terlihat di depan (untuk keluar otomatis)
        self.gate = gate and cfg["output"]["require_foreground"]
        self.targets = [n.lower() for n in cfg["output"]["target_processes"]]
        self.log = log
        self.buttons = set()
        self.keys = set()
        self.drag_kind = None
        self.two_kind = None      # "object" | "view" | None
        self.two_drag = "orbit"   # "orbit" | "pan" (sesi tampilan)
        self.two_label = None     # mis. "3 objek" (untuk pulau dinamis)
        self.two_zoom = 0.0
        self.rel = [0.0, 0.0]
        self.sub = [0.0, 0.0]
        self.clicks = []          # klik yang terjadi (untuk animasi riak di overlay); dikosongkan oleh UI
        self.fg_ok = True
        self.fg_name = ""
        self.rect = win.screen_rect()
        self.notice = ""

    # ------------------------------------------------------------ keadaan
    def refresh_foreground(self):
        hwnd, name = self.win.foreground()
        self.fg_name = name
        is_target = name in self.targets
        if is_target:
            self.target_hwnd = hwnd
        self.fg_ok = (not self.gate) or is_target
        self.rect = self.win.window_rect(hwnd) if is_target else self.win.screen_rect()
        return self.fg_ok

    def _press_button(self, name):
        if name not in self.buttons:
            self.win.button(name, True)
            self.buttons.add(name)

    def _release_button(self, name):
        if name in self.buttons:
            self.win.button(name, False)
            self.buttons.discard(name)

    def _press_key(self, vk):
        if vk not in self.keys:
            self.win.key(vk, True)
            self.keys.add(vk)

    def _release_key(self, vk):
        if vk in self.keys:
            self.win.key(vk, False)
            self.keys.discard(vk)

    def release_all(self):
        self._two_end()
        for b in list(self.buttons):
            self._release_button(b)
        for k in list(self.keys):
            self._release_key(k)
        self.drag_kind = None

    def _center(self):
        x0, y0, x1, y1 = self.rect
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)

    # ------------------------------------------------------------ niat
    def apply(self, intents):
        self.refresh_foreground()
        if not self.fg_ok and (self.buttons or self.keys):
            self.release_all()
        for it in intents:
            kind = it[0]
            if kind == "release_all":
                self.release_all()
            elif kind == "action":
                self.do_action(it[1], it[2] if len(it) > 2 else "")
            elif kind == "two_end":
                self._two_end()  # selalu ditutup (juga bila host tidak di depan): akhiri tanda UNDO
            elif not self.fg_ok:
                continue  # host tidak di depan: abaikan gerakan mouse
            elif kind == "move_abs":
                x0, y0, x1, y1 = self.rect
                self.win.set_cursor(x0 + it[1] * (x1 - x0 - 1), y0 + it[2] * (y1 - y0 - 1))
            elif kind == "move_by":
                self._move_by(it[1], it[2])
            elif kind == "click":
                self.win.button(it[1], True)
                self.win.button(it[1], False)
                self.clicks.append(it[1])
            elif kind == "button":
                if it[2] == "down":
                    self._press_button(it[1])
                else:
                    self._release_button(it[1])
            elif kind == "drag_begin":
                self._drag_begin(it[1])
            elif kind == "drag_end":
                self._drag_end()
            elif kind == "move_rel":
                self._move_rel(it[1], it[2], it[3])
            elif kind == "wheel":
                self._wheel(it[1])
            elif kind == "two_begin":
                self._two_begin(it[1] if len(it) > 1 else "orbit")
            elif kind == "two_move":
                self._two_move(*it[1:5])

    def _wheel(self, ticks):
        if self.drag_kind is not None:
            # roda sambil tombol tengah/pengubah ditahan bisa diartikan lain oleh host:
            # lepas sebentar, zoom, lalu pegang lagi di posisi yang sama
            kind_held = self.drag_kind
            self._drag_end()
            self.win.wheel(ticks)
            self._grip(kind_held)
        else:
            self.win.wheel(ticks)

    # ------------------------------------------------------------ dua tangan
    def _two_begin(self, kind="orbit"):
        tc = self.cfg["two_hand"]
        if self.bridge is not None and self.bridge.connected and tc["camera_via_bridge"]:
            # SketchUp: kamera digerakkan langsung lewat API Ruby (halus, tanpa emulasi mouse)
            self._two_end()
            self.two_kind = "camera"
            self.two_drag = kind
            self.two_label = None
            return
        self._two_begin_mouse(kind)

    def _two_begin_mouse(self, kind="orbit"):
        """kind 'orbit' (dua kepal) / 'pan' (dua cubit). Tampilan digerakkan lewat mouse (Shift+tengah /
        tengah), zoom lewat roda dengan ZOOMFACTOR diperkecil sementara supaya halus.
        Opsi grab_selected_objects: dua kepalan memindah objek terpilih lewat COM."""
        self._two_end()
        tc = self.cfg["two_hand"]
        n = 0
        if kind == "orbit" and tc["grab_selected_objects"] and self.acad is not None \
                and hasattr(self.acad, "grab_begin"):
            n = self.acad.grab_begin()
        if n:
            self.two_kind = "object"
            self.two_label = "%d objek" % n
            return
        self.two_kind = "view"
        self.two_drag = kind
        self.two_label = None
        self.two_zoom = 0.0
        if self.acad is not None and hasattr(self.acad, "view_session_begin"):
            self.acad.view_session_begin(tc["zoomfactor"])  # sebelum tombol tengah ditekan
        self._drag_begin(kind)

    def _two_move(self, dx, dy, dturn, dlog):
        tc = self.cfg["two_hand"]
        if self.two_kind == "camera":
            self.bridge.camera(self.two_drag, dx, dy, dturn, dlog)
            return
        if self.two_kind == "object":
            g = tc["grab_gain_px"]
            self.acad.grab_move(dx * g, dy * g, dturn if tc["rotate"] else 0.0, dlog if tc["scale"] else 0.0)
        elif self.two_kind == "view":
            twist = dturn * tc["view_twist_gain"] if self.two_drag == "orbit" else 0.0
            self._move_rel(dx + twist, dy, self.two_drag)
            self.two_zoom += dlog
            ticks = int(self.two_zoom / tc["view_zoom_step"])
            if ticks:
                self.two_zoom -= ticks * tc["view_zoom_step"]
                self._wheel(ticks)  # rentangkan = zoom in

    def _two_end(self):
        kind = getattr(self, "two_kind", None)
        self.two_kind = None
        self.two_label = None
        if kind == "camera":
            return
        if kind == "object":
            self.acad.grab_end()
        elif kind == "view":
            self._drag_end()
            if self.acad is not None and hasattr(self.acad, "view_session_end"):
                self.acad.view_session_end()  # kembalikan ZOOMFACTOR asli

    def _move_by(self, dx, dy):
        """dx, dy dalam satuan lebar LAYAR (isotropik). Sisa pecahan piksel diakumulasi.

        Skala sengaja dari lebar layar, bukan lebar jendela host: dulu kursor jadi lebih lambat begitu
        masuk ke AutoCAD yang tidak layar penuh. Batas gerak tetap jendela host.
        """
        x0, y0, x1, y1 = self.rect
        sx0, _, sx1, _ = self.win.screen_rect()
        w = float(max(sx1 - sx0, x1 - x0))
        self.sub[0] += dx * w
        self.sub[1] += dy * w
        ix, iy = int(self.sub[0]), int(self.sub[1])
        if not ix and not iy:
            return
        self.sub[0] -= ix
        self.sub[1] -= iy
        cx, cy = self.win.cursor()
        nx = min(max(cx + ix, x0), x1 - 1)
        ny = min(max(cy + iy, y0), y1 - 1)
        self.win.set_cursor(nx, ny)

    def _drag_begin(self, kind):
        self._drag_end()
        self.rel = [0.0, 0.0]
        self.win.set_cursor(*self._center())
        self._grip(kind)

    def _grip(self, kind):
        """Tekan pengubah (mis. Shift) sesuai output.nav, lalu tombol tengah.
        AutoCAD: orbit = Shift+tengah, pan = tengah. SketchUp: orbit = tengah, pan = Shift+tengah."""
        self.drag_kind = kind
        for vk in self.nav.get(kind, []):
            self._press_key(vk)
        self._press_button("middle")

    def _drag_end(self):
        self._release_button("middle")
        for mods in self.nav.values():
            for vk in mods:
                self._release_key(vk)
        self._release_key(SHIFT)
        self.drag_kind = None

    def _move_rel(self, dx, dy, kind):
        if self.drag_kind is None:
            return
        mo = self.cfg["motion"]
        gain = mo["orbit_gain_px"] if kind == "orbit" else mo["pan_gain_px"]
        self.rel[0] += dx * gain
        self.rel[1] += dy * gain
        ix, iy = int(self.rel[0]), int(self.rel[1])
        if not ix and not iy:
            return
        self.rel[0] -= ix
        self.rel[1] -= iy
        cx, cy = self.win.cursor()
        nx, ny = cx + ix, cy + iy
        x0, y0, x1, y1 = self.rect
        m = mo["edge_margin_px"]
        if nx < x0 + m or nx > x1 - m or ny < y0 + m or ny > y1 - m:
            # Kursor mentok tepi: lepas, pindah ke tengah, tekan lagi (seperti mengangkat mouse)
            self._release_button("middle")
            self.win.set_cursor(*self._center())
            self._press_button("middle")
            return
        self.win.set_cursor(nx, ny)

    # ------------------------------------------------------------ perintah
    def type_command(self, cmd, cancel_first=True):
        """Fallback keyboard: ESC ESC, ketik perintah, ENTER. Hanya bila AutoCAD di depan."""
        _, name = self.win.foreground()
        if self.gate and name not in self.targets:
            return False
        if cancel_first:
            self.win.tap_combo("ESC")
            self.win.tap_combo("ESC")
        self.win.type_text(cmd.strip())
        self.win.tap_combo("ENTER")
        return True

    def do_action(self, action, label=""):
        t = action["type"]
        if t == "sketchup":
            if self.bridge is not None and self.bridge.connected:
                self.bridge.send(action["op"], action.get("arg"))
            elif action.get("fallback_key") and self.fg_ok:
                self.win.tap_combo(action["fallback_key"])  # shortcut bawaan SketchUp
            else:
                self.notice = "%s batal: jembatan SketchUp belum terhubung" % label
                self.log(self.notice)
            return
        if t == "command":
            cancel = action.get("cancel_first", True)
            # COM sedang menunggu perintah sebelumnya selesai (mis. BOX menunggu klik): ketik lewat keyboard
            # supaya ESC ESC membatalkannya sekarang, bukan mengantre di belakangnya.
            if self.acad is not None and not (getattr(self.acad, "busy", False) and self.fg_ok):
                self.acad.send(action["cmd"], cancel)
            elif not self.type_command(action["cmd"], cancel):
                self.notice = "%s batal: AutoCAD tidak di depan" % label
                self.log(self.notice)
            return
        if not self.fg_ok:
            self.notice = "%s batal: AutoCAD tidak di depan" % label
            self.log(self.notice)
            return
        if t == "key":
            self.win.tap_combo(action["key"])
        elif t == "keys":
            for k in action["keys"]:
                self.win.tap_combo(k)
