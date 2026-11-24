"""State machine gestur -> niat (intent) abstrak. Murni: tidak menyentuh Windows maupun kamera.

Niat yang dikeluarkan (tuple):
  ("move_by", dx, dy)             geser kursor relatif (satuan: lebar jendela target, untuk x DAN y)
  ("move_abs", nx, ny)            kursor ke posisi 0..1 di jendela target (mode kursor "absolute")
  ("click", "left"|"right")       klik penuh (tekan + lepas)
  ("button", "left", "down"|"up") tahan / lepas (drag)
  ("drag_begin", "orbit"|"pan")   tekan tombol tengah (+Shift untuk orbit)
  ("drag_end", "orbit"|"pan")
  ("move_rel", dx, dy, kind)      gerak orbit/pan (satuan: lebar frame kamera)
  ("wheel", ticks)                + = zoom in
  ("action", action_dict, label)  perintah AutoCAD / tombol
  ("release_all",)

Kursor presisi (mode "relative", bawaan):
  - Seperti mouse: tangan menggeser kursor, bukan menunjuk posisi layar. Gerak pelan = gain kecil (presisi),
    gerak cepat = gain besar (menyeberang layar). Telapak terbuka = "angkat mouse" untuk memindah tangan.
  - Tangan diam sebentar -> kursor TERKUNCI; getaran kecil diabaikan sampai tangan sengaja bergeser.
  - Jepit TIDAK langsung menekan tombol. Lepas jepit tanpa bergerak = klik di titik semula; jepit lalu geser
    = drag; jepit diam lama = klik kanan. Gerak kursor ~120 ms sebelum jepit dibatalkan (diputar mundur).
"""

import math
from collections import deque

from . import gestures as G
from .config import normalize_action
from .filters import OneEuro2D
from .menu import Menu

DISARMED = "JEDA"
IDLE = "SIAGA"
POINTER = "KURSOR"
DRAG = "KLIK/DRAG"
ORBIT = "ORBIT"
PAN = "PAN"
ZOOM = "ZOOM"
MENU = "MENU"
HOLO = "DUA TANGAN"  # dua kepalan: pegang objek terpilih, atau putar tampilan bila tak ada

MODE_OF = {"pointer": POINTER, "drag": DRAG, "orbit": ORBIT, "pan": PAN, "zoom": ZOOM, "idle": IDLE}


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class PoseStabilizer:
    """Pose baru baru diterima setelah bertahan `stable_ms[pose]`; tangan hilang setelah `lost_grace_ms`."""

    def __init__(self, stable_ms, lost_grace_ms):
        self.stable_ms = stable_ms
        self.lost_ms = lost_grace_ms
        self.stable = None
        self.candidate = None
        self.since = 0.0

    def update(self, raw, t):
        if raw != self.candidate:
            self.candidate, self.since = raw, t
        if raw != self.stable:
            if raw is None:
                need = self.lost_ms
            else:
                need = self.stable_ms.get(raw, self.stable_ms.get("default", 120))
            if (t - self.since) * 1000.0 >= need:
                self.stable = raw
        return self.stable


class Controller:
    def __init__(self, cfg):
        self.cfg = cfg
        tm = cfg["timing"]
        stable = dict(tm["stable_ms"])
        stable.setdefault(G.UNKNOWN, 250)
        self.stab = PoseStabilizer(stable, tm["lost_grace_ms"])
        self.th = cfg["thresholds"]
        self.cont = cfg["continuous"]
        self.disc = {p: (it.get("label", p), normalize_action(it)) for p, it in cfg["discrete"].items()}
        self.menu = Menu(cfg["menu"])
        self.armed = bool(cfg["output"]["start_armed"])
        self.mode = IDLE if self.armed else DISARMED

        pf = cfg["pointer"]["filter"]
        mf = cfg["motion"]["filter"]
        self.f_ptr = OneEuro2D(pf["min_cutoff"], pf["beta"], pf["d_cutoff"])
        self.f_tip = OneEuro2D(pf["min_cutoff"], pf["beta"], pf["d_cutoff"])
        self.f_palm = OneEuro2D(mf["min_cutoff"], mf["beta"], mf["d_cutoff"])

        self.quit_requested = False
        self.primary = None
        self.menu_cursor = None
        self.edge = False
        self.pinching = False
        self.pinch_r = 9.0
        self.raw_pose = None
        self.pose = None
        self.prev_pose = None
        self.hold = None
        self.hold_progress = 0.0
        self.latched = None
        self.arm_since = None
        self.arm_progress = 0.0
        self.toasts = []
        # kursor
        self.cursor = None
        self.hist = deque()          # absolute: (t, (nx, ny))
        self.moves = deque()         # relative: (t, dx, dy) untuk putar-mundur klik
        self.freeze_until = 0.0
        self.ptr_prev = None
        self.locked = False
        self.lock_p = None
        self.still = 0.0
        self.ptr_state = "free"
        self.press = None
        # orbit/pan/zoom
        self.ref = None
        self.ref_t = 0.0
        self.zoom_acc = 0.0
        # dua tangan
        self.holo_cand = None
        self.holo_seen = 0.0
        self.h_ref = None
        self.h_dist0 = None
        self.holo_scale = 1.0
        self.holo_pts = None
        self.two_kind = None      # "orbit" (dua kepal) | "pan" (dua cubit)
        self.two_active = None
        # menu
        self.menu_opened_at = 0.0
        self.hover = None
        self.last_hover = None
        self.dwell_id = None
        self.dwell_start = 0.0
        self.dwell_lock = None
        self.dwell_progress = 0.0

    # ------------------------------------------------------------------ util
    def toast(self, text, t):
        self.toasts.append((text, t))

    def _ms(self, key):
        return self.cfg["timing"][key] / 1000.0

    @property
    def relative(self):
        return self.cfg["pointer"].get("mode", "relative") == "relative"

    def _select(self, hands):
        if not hands:
            return None
        dom = self.cfg["hand"]["dominant"]
        for h in hands:
            if h.label == dom:
                return h
        if self.cfg["hand"]["fallback_any"] or str(dom).lower() == "any":
            return max(hands, key=lambda h: G.hand_size(h.iso))
        return None

    # ------------------------------------------------------------- mode switch
    def _set_mode(self, new, out, t):
        old = self.mode
        if new == old:
            return
        if old == DRAG:
            st = self.press["state"] if self.press else None
            if st == "pending":
                # lepas jepit tanpa bergeser = klik; tangan hilang / pindah ke pose lain = batal
                if new in (POINTER, IDLE) and self.pose is not None:
                    out.append(("click", "left"))
                    self.toast("KLIK", t)
            elif st == "drag":
                out.append(("button", "left", "up"))
            self.press = None
            self.freeze_until = t + self._ms("click_freeze_ms")
        elif old == ORBIT:
            out.append(("drag_end", "orbit"))
        elif old == PAN:
            out.append(("drag_end", "pan"))
        elif old == HOLO:
            out.append(("two_end",))
        elif old == MENU:
            self.menu.close()
            self.hover = None

        self.mode = new
        if new == DRAG:
            self._rewind(t, out)
            self.press = {"t": t, "p": None, "state": "pending"}
        elif new == POINTER and old != DRAG:
            self.f_ptr.reset()
            self.ptr_prev = None
            self.locked = False
            self.still = 0.0
        elif new in (ORBIT, PAN):
            self.f_palm.reset()
            self.ref = None
            out.append(("drag_begin", "orbit" if new == ORBIT else "pan"))
        elif new == ZOOM:
            self.f_palm.reset()
            self.ref = None
            self.zoom_acc = 0.0
        elif new == HOLO:
            self.f_palm.reset()
            self.h_ref = None
            self.h_dist0 = None
            self.two_active = self.two_kind
            out.append(("two_begin", self.two_kind))
        elif new == MENU:
            self.menu.open()
            self.menu_opened_at = t
            self.f_tip.reset()
            self.dwell_id = self.dwell_lock = self.last_hover = None
        elif new == DISARMED:
            out.append(("release_all",))

    def _rewind(self, t, out):
        """Batalkan gerak kursor sesaat sebelum jepit (jari yang menutup ikut menggeser tangan)."""
        horizon = t - self.cfg["timing"].get("click_rewind_ms", 120) / 1000.0
        if self.relative:
            sx = sum(dx for ts, dx, dy in self.moves if ts > horizon)
            sy = sum(dy for ts, dx, dy in self.moves if ts > horizon)
            self.moves.clear()
            if sx or sy:
                out.append(("move_by", -sx, -sy))
        else:
            best = None
            for ts, pos in self.hist:
                if ts <= horizon:
                    best = pos
            if best is not None:
                self.cursor = best
                out.append(("move_abs", best[0], best[1]))

    def toggle_arm(self, t, out):
        self.armed = not self.armed
        if self.armed:
            self._set_mode(IDLE, out, t)
            self.toast("KONTROL AKTIF", t)
        else:
            self._set_mode(DISARMED, out, t)
            self.toast("KONTROL DIJEDA", t)

    def external(self, action, label, t):
        """Perintah dari luar gestur (suara). Kembalikan list niat."""
        out = []
        if action.get("type") == "internal" and action.get("op") == "toggle_arm":
            self.toggle_arm(t, out)
            return out
        if not self.armed and action.get("type") == "internal":
            return out
        if self.mode in (DRAG, ORBIT, PAN, HOLO):
            self._set_mode(IDLE, out, t)
        self._fire(action, label, t, out)
        return out

    # ------------------------------------------------------------------ main
    def update(self, hands, t):
        out = []
        self.toasts = [x for x in self.toasts if t - x[1] < 2.0]

        margin = self.th.get("edge_margin", 0.025)
        both_open = len(hands) >= 2 and all(
            G.classify(h.iso, False, self.th)[0] == G.OPEN and not G.fingers_near_edge(h.norm, margin)
            for h in hands[:2])
        if both_open:
            if self.arm_since is None:
                self.arm_since = t
            if self.arm_since is not False:
                self.arm_progress = min(1.0, (t - self.arm_since) / self._ms("arm_hold_ms"))
                if self.arm_progress >= 1.0:
                    self.toggle_arm(t, out)
                    self.arm_since = False  # tunggu tangan turun dulu
        else:
            self.arm_since = None
            self.arm_progress = 0.0

        hand = self._select(hands)
        self.primary = hand
        raw = None
        self.edge = False
        self.pinch_r = 9.0
        if hand is not None:
            raw, info = G.classify(hand.iso, self.pinching, self.th)
            self.pinch_r = info["pinch"]
            if G.fingers_near_edge(hand.norm, margin):
                self.edge = True
                raw = G.UNKNOWN  # jari terpotong frame: jangan percaya pose-nya
        self.raw_pose = raw
        self.pinching = raw == G.PINCH

        prev = self.pose
        pose = self.stab.update(raw, t)
        self.prev_pose, self.pose = prev, pose
        if self.latched is not None and pose != self.latched:
            self.latched = None

        if both_open:
            if self.armed:
                self._set_mode(IDLE, out, t)
            self.hold, self.hold_progress = None, 0.0
            return out
        if not self.armed:
            self._set_mode(DISARMED, out, t)
            return out
        if self.mode == MENU:
            self._menu_update(hand, pose, prev, t, out)
            return out

        # Dua tangan mengepal = pegang objek terpilih / putar tampilan (mendahului gestur satu tangan)
        if self._holo_detect(hands, t):
            self.hold, self.hold_progress = None, 0.0
            if self.mode == HOLO and self.two_kind != self.two_active:
                self._set_mode(IDLE, out, t)  # ganti pegangan (kepal <-> cubit): sesi baru
            self._set_mode(HOLO, out, t)
            self._holo_frame(hands, t, out)
            return out
        if self.mode == HOLO:
            if (t - self.holo_seen) * 1000.0 < self.cfg["two_hand"]["grace_ms"]:
                return out  # tangan sempat hilang sebentar: tahan, jangan lepas orbit
            self._set_mode(IDLE, out, t)
        elif self.holo_cand is not None:
            # dua kepalan sedang dikonfirmasi: jangan mulai orbit satu tangan dulu (mencegah sentakan)
            if self.mode in (ORBIT, PAN, ZOOM):
                self._set_mode(IDLE, out, t)
            return out

        if pose in self.disc:
            self._set_mode(IDLE, out, t)
            self._hold_update(pose, t, out)
            return out
        self.hold, self.hold_progress = None, 0.0

        target = "idle" if pose is None else self.cont.get(pose, "idle")
        if target == "drag" and self.mode not in (POINTER, DRAG):
            target = "idle"  # klik hanya dari mode kursor: mencegah klik liar
        self._set_mode(MODE_OF[target], out, t)
        if hand is not None:
            self._mode_frame(hand, t, out)
        return out

    # ------------------------------------------------------------- dua tangan
    def _holo_detect(self, hands, t):
        hc = self.cfg["two_hand"]
        if not hc["enabled"] or len(hands) < 2:
            self.holo_cand = None
            return False
        margin = self.th.get("edge_margin", 0.025)
        if any(G.fingers_near_edge(h.norm, margin) for h in hands[:2]):
            self.holo_cand = None
            return False
        poses = [G.classify(h.iso, self.mode == HOLO, self.th)[0] for h in hands[:2]]
        kind = None
        if poses[0] == poses[1] == hc["orbit_pose"]:
            kind = "orbit"
        elif poses[0] == poses[1] == hc["pan_pose"]:
            kind = "pan"
        if kind is None:
            self.holo_cand = None
            return False
        self.two_kind = kind
        self.holo_seen = t
        if self.holo_cand is None:
            self.holo_cand = t
        return self.mode == HOLO or (t - self.holo_cand) * 1000.0 >= hc["stable_ms"]

    def _holo_frame(self, hands, t, out):
        """Dua kepalan / dua cubitan -> ("two_move", dx, dy, dputar, dlog_skala).

        dx, dy  : geser titik tengah kedua tangan (lebar frame, sudah diberi akselerasi)
        dputar  : perubahan sudut garis antar-tangan (radian; + = searah jarum jam di layar)
        dlog    : perubahan log jarak antar-tangan (+ = merentang)
        Aktuator: kepal -> orbit tampilan (+setir), cubit -> pan; rentang -> zoom halus.
        """
        hc, mo = self.cfg["two_hand"], self.cfg["motion"]
        a, b = sorted(hands[:2], key=lambda h: G.palm_center(h.norm)[0])
        pl, pr = G.palm_center(a.norm), G.palm_center(b.norm)
        asp = a.aspect
        mid = self.f_palm(((pl[0] + pr[0]) / 2.0, (pl[1] + pr[1]) / 2.0 * asp), t)
        vx, vy = pr[0] - pl[0], (pr[1] - pl[1]) * asp
        dist = max(math.hypot(vx, vy), 1e-3)
        ang = math.atan2(vy, vx)
        self.holo_pts = (pl, pr)
        if self.h_ref is None:
            self.h_ref = {"mid": mid, "dist": dist, "ang": ang, "t": t}
            self.h_dist0 = dist
            return
        r = self.h_ref
        dx, dy = mid[0] - r["mid"][0], mid[1] - r["mid"][1]
        dang = math.atan2(math.sin(ang - r["ang"]), math.cos(ang - r["ang"]))
        dlog = math.log(dist / r["dist"])
        move = math.hypot(dx, dy) >= hc["deadzone"]
        turn = abs(dang) >= hc["twist_deadzone"]
        grow = abs(dlog) >= hc["scale_deadzone"]
        if not (move or turn or grow):
            return
        acc = 1.0
        if move:
            speed = math.hypot(dx, dy) / max(t - r["t"], 1e-3)
            pc = self.cfg["pointer"]
            k = _smooth((speed - pc["speed_slow"]) / max(pc["speed_fast"] - pc["speed_slow"], 1e-6))
            acc = mo["accel_min"] + (mo["accel_max"] - mo["accel_min"]) * k
            r["mid"], r["t"] = mid, t
        if turn:
            r["ang"] = ang
        if grow:
            r["dist"] = dist
        out.append(("two_move", dx * acc if move else 0.0, dy * acc if move else 0.0,
                    dang if turn else 0.0, dlog if grow else 0.0))
        self.holo_scale = dist / self.h_dist0

    # ------------------------------------------------------------- per frame
    def _zone_point(self, hand, t, filt):
        """Titik tunjuk (antara pangkal dan ujung telunjuk), difilter, dipetakan dari zona ke 0..1."""
        w = self.cfg["pointer"]["tip_weight"]
        mcp, tip = hand.norm[G.INDEX[0]], hand.norm[G.INDEX[3]]
        a = (mcp[0] + (tip[0] - mcp[0]) * w, mcp[1] + (tip[1] - mcp[1]) * w)
        fx, fy = filt(a, t)
        x0, y0, x1, y1 = self.cfg["pointer"]["zone"]
        return (min(1.0, max(0.0, (fx - x0) / (x1 - x0))), min(1.0, max(0.0, (fy - y0) / (y1 - y0))))

    def _gain(self, speed):
        pc = self.cfg["pointer"]
        k = _smooth((speed - pc["speed_slow"]) / max(pc["speed_fast"] - pc["speed_slow"], 1e-6))
        return pc["gain_slow"] + (pc["gain_fast"] - pc["gain_slow"]) * k

    def _emit_move(self, dx, dy, speed, t, out):
        g = self._gain(speed)
        mx, my = dx * g, dy * g
        if not mx and not my:
            return
        out.append(("move_by", mx, my))
        self.moves.append((t, mx, my))
        while self.moves and t - self.moves[0][0] > 0.5:
            self.moves.popleft()

    def _pointer_relative(self, hand, t, out):
        pc = self.cfg["pointer"]
        # Jangkar = rata-rata pangkal telunjuk & jari tengah: hampir tidak bergerak saat jari menjepit
        a5, a9 = hand.norm[G.INDEX[0]], hand.norm[G.MIDDLE[0]]
        a = ((a5[0] + a9[0]) / 2.0, (a5[1] + a9[1]) / 2.0 * hand.aspect)
        p = self.f_ptr(a, t)
        if self.ptr_prev is None:
            self.ptr_prev = (p, t)
            if self.press is not None and self.press["p"] is None:
                self.press["p"] = p
            return
        (pp, pt_) = self.ptr_prev
        dt = max(t - pt_, 1e-3)
        dx, dy = p[0] - pp[0], p[1] - pp[1]
        self.ptr_prev = (p, t)
        speed = math.hypot(dx, dy) / dt

        if self.mode == DRAG:
            pr = self.press
            if pr["p"] is None:
                pr["p"] = p
            if pr["state"] == "pending":
                self.ptr_state = "pending"
                if math.hypot(p[0] - pr["p"][0], p[1] - pr["p"][1]) > pc["drag_threshold"]:
                    out.append(("button", "left", "down"))
                    pr["state"] = "drag"
                    self.ptr_state = "drag"
                elif (t - pr["t"]) * 1000.0 >= pc["longpress_ms"]:
                    out.append(("click", "right"))
                    self.toast("KLIK KANAN", t)
                    pr["state"] = "right"
                return
            if pr["state"] == "drag":
                self.ptr_state = "drag"
                self._emit_move(dx, dy, speed, t, out)
            return

        if t < self.freeze_until:
            self.ptr_state = "locked"
            return
        if self.locked:
            if math.hypot(p[0] - self.lock_p[0], p[1] - self.lock_p[1]) <= pc["unlock_dist"]:
                self.ptr_state = "locked"
                return
            self.locked = False  # sengaja digeser: lanjut dari posisi ini (tanpa lompatan)
            self.still = 0.0
            self.ptr_state = "free"
            return
        if speed < pc["lock_speed"]:
            self.still += dt
            if self.still * 1000.0 >= pc["lock_ms"]:
                self.locked, self.lock_p = True, p
                self.ptr_state = "locked"
                return
        else:
            self.still = 0.0
        self.ptr_state = "free"
        self._emit_move(dx, dy, speed, t, out)

    def _pointer_absolute(self, hand, t, out):
        nx, ny = self._zone_point(hand, t, self.f_ptr)
        self.hist.append((t, (nx, ny)))
        while self.hist and t - self.hist[0][0] > 0.5:
            self.hist.popleft()
        if self.mode == DRAG:
            pr = self.press
            if pr["p"] is None:
                pr["p"] = (nx, ny)
            if pr["state"] == "pending":
                self.ptr_state = "pending"
                if math.hypot(nx - pr["p"][0], ny - pr["p"][1]) > self.cfg["pointer"]["drag_threshold"]:
                    out.append(("button", "left", "down"))
                    pr["state"] = "drag"
                elif (t - pr["t"]) * 1000.0 >= self.cfg["pointer"]["longpress_ms"]:
                    out.append(("click", "right"))
                    pr["state"] = "right"
                return
            if pr["state"] != "drag":
                return
        if t >= self.freeze_until:
            self.ptr_state = "drag" if self.mode == DRAG else "free"
            self.cursor = (nx, ny)
            out.append(("move_abs", nx, ny))

    def _mode_frame(self, hand, t, out):
        if self.mode in (POINTER, DRAG):
            if self.relative:
                self._pointer_relative(hand, t, out)
            else:
                self._pointer_absolute(hand, t, out)
            return

        if self.mode in (ORBIT, PAN, ZOOM):
            c = self.f_palm(G.palm_center(hand.norm), t)
            c = (c[0], c[1] * hand.aspect)
            if self.ref is None:
                self.ref, self.ref_t = c, t
                return
            mo = self.cfg["motion"]
            dx, dy = c[0] - self.ref[0], c[1] - self.ref[1]
            if self.mode == ZOOM:
                if abs(dy) >= mo["deadzone"]:
                    self.zoom_acc += dy
                    self.ref, self.ref_t = c, t
                ticks = int(self.zoom_acc / mo["zoom_step"])
                if ticks:
                    self.zoom_acc -= ticks * mo["zoom_step"]
                    out.append(("wheel", ticks if mo["zoom_invert"] else -ticks))
            elif math.hypot(dx, dy) >= mo["deadzone"]:
                speed = math.hypot(dx, dy) / max(t - self.ref_t, 1e-3)
                pc = self.cfg["pointer"]
                k = _smooth((speed - pc["speed_slow"]) / max(pc["speed_fast"] - pc["speed_slow"], 1e-6))
                acc = mo["accel_min"] + (mo["accel_max"] - mo["accel_min"]) * k
                out.append(("move_rel", dx * acc, dy * acc, "orbit" if self.mode == ORBIT else "pan"))
                self.ref, self.ref_t = c, t

    def _hold_update(self, pose, t, out):
        if self.latched == pose:
            self.hold_progress = 0.0
            return
        if self.hold is None or self.hold[0] != pose:
            self.hold = (pose, t)
        self.hold_progress = min(1.0, (t - self.hold[1]) / self._ms("hold_ms"))
        if self.hold_progress >= 1.0:
            label, action = self.disc[pose]
            self.latched = pose
            self.hold, self.hold_progress = None, 0.0
            self._fire(action, label, t, out)

    def _fire(self, action, label, t, out):
        if action["type"] == "internal":
            op = action["op"]
            if op == "open_menu":
                self._set_mode(MENU, out, t)
            elif op == "close_menu":
                self._set_mode(IDLE, out, t)
            elif op == "toggle_arm":
                self.toggle_arm(t, out)
                return
            elif op == "quit":
                self.quit_requested = True
        else:
            out.append(("action", action, label))
        self.toast(label, t)

    # ------------------------------------------------------------------ menu
    def _menu_update(self, hand, pose, prev, t, out):
        self.hover = None
        self.dwell_progress = 0.0
        if hand is None:
            self.dwell_id = None
            return
        # Kursor menu memakai zona tetap (absolut): tombol menu besar, jadi posisi langsung paling cepat,
        # dan seluruh menu terjangkau tanpa tangan keluar frame.
        self.menu_cursor = self._zone_point(hand, t, self.f_tip)
        b = self.menu.hit(*self.menu_cursor)
        self.hover = b

        if pose == G.ROCK or (pose == G.SHAKA and self.latched != G.SHAKA):
            self.latched = pose
            self._set_mode(IDLE, out, t)
            self.toast("MENU DITUTUP", t)
            return
        if (t - self.menu_opened_at) < self._ms("menu_open_grace_ms"):
            return

        if pose == G.PINCH and prev != G.PINCH:
            target = self.last_hover or b
            if target is not None:
                self._menu_select(target, t, out)
            return
        if pose != G.PINCH:
            self.last_hover = b

        if self.dwell_lock is not None and (b is None or b.id != self.dwell_lock):
            self.dwell_lock = None
        dwell_ms = self.cfg["menu"].get("dwell_ms", 0)
        if dwell_ms and pose == G.POINT and b is not None and b.id != self.dwell_lock:
            if self.dwell_id != b.id:
                self.dwell_id, self.dwell_start = b.id, t
            self.dwell_progress = min(1.0, (t - self.dwell_start) * 1000.0 / dwell_ms)
            if self.dwell_progress >= 1.0:
                self.dwell_lock = b.id
                self.dwell_id = None
                self._menu_select(b, t, out)
        else:
            self.dwell_id = None

    def _menu_select(self, b, t, out):
        if b.kind == "tab":
            self.menu.page = b.payload
            self.dwell_lock = b.id
            return
        if b.kind == "close":
            self._set_mode(IDLE, out, t)
            self.toast("MENU DITUTUP", t)
            return
        self._fire(b.payload, b.label, t, out)
        if self.cfg["menu"].get("close_after_select", True) and self.mode == MENU:
            self._set_mode(IDLE, out, t)

    # ------------------------------------------------------------------ HUD
    def view(self):
        pc = self.cfg["pointer"]
        on, pre = self.th["pinch_on"], pc["preclick_ratio"]
        preclick = 0.0
        if self.mode == POINTER and self.pinch_r < pre:
            preclick = min(1.0, max(0.0, (pre - self.pinch_r) / max(pre - on, 1e-6)))
        return {
            "mode": self.mode,
            "armed": self.armed,
            "pose": self.pose,
            "raw_pose": self.raw_pose,
            "hold": (self.hold[0] if self.hold else None, self.hold_progress),
            "arm_progress": self.arm_progress,
            "menu": self.menu if self.mode == MENU else None,
            "hover": self.hover,
            "dwell_progress": self.dwell_progress,
            "toasts": list(self.toasts),
            "cursor": self.cursor,
            "zone": pc["zone"],
            "primary": self.primary,
            "edge": self.edge,
            "menu_cursor": self.menu_cursor if self.mode == MENU else None,
            "ptr_state": self.ptr_state if self.mode in (POINTER, DRAG) else None,
            "preclick": preclick,
            "press_t": self.press["t"] if (self.press and self.press["state"] == "pending") else None,
            "longpress_ms": pc["longpress_ms"],
            "discrete": {p: lbl for p, (lbl, _) in self.disc.items()},
            "continuous": dict(self.cont),
            "two": ({"scale": self.holo_scale, "pts": self.holo_pts, "kind": self.two_active}
                    if self.mode == HOLO else None),
            "two_enabled": bool(self.cfg["two_hand"]["enabled"]),
        }
