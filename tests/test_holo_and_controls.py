"""Uji gestur dua tangan (kepal = putar 3D, cubit = geser, rentang = zoom), pegang objek (opsional),
tombol kontrol yang bisa diklik, dan kecepatan kursor yang sama di dalam/di luar jendela AutoCAD."""

import math

import pytest

import synth
from gesture_cad import config as CFG
from gesture_cad import controller as C
from gesture_cad import glass, overlay
from gesture_cad.actuator import Actuator, SimInput
from gesture_cad.autocad import grab_step, view_axes
from gesture_cad.keys import VK

DT = 1.0 / 30


@pytest.fixture
def cfg():
    return CFG.load()


def run(ctl, fn, seconds, t0=100.0, log=None):
    log = [] if log is None else log
    t = t0
    for k in range(int(round(seconds / DT))):
        t += DT
        log += ctl.update(fn(k), t)
    return t, log


def two(pose="FIST", cx=0.5, cy=0.62, half=0.18, angle=0.0):
    """Dua tangan simetris terhadap (cx, cy), berjarak 2*half, diputar `angle` radian seperti setir."""
    dx, dy = half * math.cos(angle), half * math.sin(angle) * (640 / 480.0)
    return [synth.hand(pose, center=(cx - dx, cy - dy), label="Left"),
            synth.hand(pose, center=(cx + dx, cy + dy), label="Right")]


def kinds(log, kind):
    return [i for i in log if i[0] == kind]


def moves(log):
    return kinds(log, "two_move")


# ------------------------------------------------------------------ pengendali
def test_two_fists_start_orbit_session_and_release(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(), 0.5)
    assert ctl.mode == C.HOLO and ctl.view()["two"]["kind"] == "orbit"
    assert kinds(log, "two_begin") == [("two_begin", "orbit")]
    assert kinds(log, "drag_begin") == []          # orbit satu tangan tidak sempat menyala (tanpa sentakan)
    t, log = run(ctl, lambda k: [synth.hand("OPEN")], 0.6, t, log)
    assert ctl.mode != C.HOLO and kinds(log, "two_end") == [("two_end",)]


def test_two_pinches_start_pan_session(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two("PINCH"), 0.5)
    assert kinds(log, "two_begin") == [("two_begin", "pan")]
    assert kinds(log, "click") == [] and kinds(log, "button") == []   # cubitan dua tangan bukan klik


def test_switching_fists_to_pinches_restarts_session(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(), 0.4)
    t, log = run(ctl, lambda k: two("PINCH"), 0.4, t, log)
    assert kinds(log, "two_begin") == [("two_begin", "orbit"), ("two_begin", "pan")]
    assert kinds(log, "two_end") == [("two_end",)]


def test_single_fist_is_still_normal_orbit(cfg):
    ctl = C.Controller(cfg)
    run(ctl, lambda k: [synth.hand("FIST")], 0.5)
    assert ctl.mode == C.ORBIT


def test_moving_both_hands(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(), 0.4)
    n = len(log)
    t, log = run(ctl, lambda k: two(cx=0.5 + 0.004 * k), 0.6, t, log)
    assert sum(m[1] for m in moves(log[n:])) > 0.02


def test_steering_twist(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(), 0.4)
    n = len(log)
    t, log = run(ctl, lambda k: two(angle=0.02 * k), 0.6, t, log)
    assert sum(m[3] for m in moves(log[n:])) > 0.2         # ~0.34 rad diputar


def test_spread_and_close(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(half=0.14), 0.4)
    n = len(log)
    t, log = run(ctl, lambda k: two(half=0.14 + 0.003 * k), 0.6, t, log)
    assert sum(m[4] for m in moves(log[n:])) > 0.2
    n = len(log)
    t, log = run(ctl, lambda k: two(half=0.20 - 0.003 * k), 0.6, t, log)
    assert sum(m[4] for m in moves(log[n:])) < -0.2


def test_brief_hand_dropout_keeps_session(cfg):
    ctl = C.Controller(cfg)
    t, log = run(ctl, lambda k: two(), 0.4)
    t, log = run(ctl, lambda k: [], 0.1, t, log)
    assert ctl.mode == C.HOLO and kinds(log, "two_end") == []


def test_two_hand_disabled_in_config(cfg):
    cfg["two_hand"]["enabled"] = False
    ctl = C.Controller(cfg)
    run(ctl, lambda k: two(), 0.5)
    assert ctl.mode != C.HOLO


# ------------------------------------------------------------------ aktuator
class FakeLink:
    busy = False

    def __init__(self, objects=0):
        self.objects = objects
        self.calls = []

    def grab_begin(self):
        self.calls.append("grab_begin")
        return self.objects

    def grab_move(self, *a):
        self.calls.append(("grab_move",) + a)

    def grab_end(self):
        self.calls.append("grab_end")

    def view_session_begin(self, zf):
        self.calls.append(("zf", zf))

    def view_session_end(self):
        self.calls.append("zf_restore")

    def send(self, cmd, cancel):
        self.calls.append(("send", cmd))


def act_with(cfg, link):
    win = SimInput(rect=(0, 0, 1000, 800))
    return Actuator(cfg, win, acad=link, gate=True, log=lambda s: None), win


def test_view_orbit_session_presses_shift_middle_and_zooms_smoothly(cfg):
    link = FakeLink()
    act, win = act_with(cfg, link)
    act.apply([("two_begin", "orbit")])
    assert ("zf", cfg["two_hand"]["zoomfactor"]) in link.calls      # ZOOMFACTOR diperkecil dulu
    assert act.drag_kind == "orbit" and VK["SHIFT"] in act.keys and "middle" in act.buttons
    act.apply([("two_move", 0.0, 0.0, 0.0, 0.2)])                   # rentang -> beberapa langkah roda
    wheel = [e for e in win.events if e[0] == "wheel"]
    assert wheel and sum(e[1] for e in wheel) >= 3
    act.apply([("two_end",)])
    assert act.buttons == set() and act.keys == set() and link.calls[-1] == "zf_restore"


def test_view_pan_session_uses_middle_without_shift(cfg):
    act, win = act_with(cfg, FakeLink())
    act.apply([("two_begin", "pan"), ("two_move", 0.02, 0.0, 0.5, 0.0)])
    assert act.drag_kind == "pan" and VK["SHIFT"] not in act.keys
    assert ("key", VK["SHIFT"], True) not in win.events
    act.apply([("two_end",)])


def test_selected_objects_are_grabbed_only_when_enabled(cfg):
    link = FakeLink(objects=3)
    act, win = act_with(cfg, link)
    act.apply([("two_begin", "orbit")])
    assert act.two_kind == "view" and "grab_begin" not in link.calls   # bawaan: tampilan, bukan objek
    act.apply([("two_end",)])
    cfg["two_hand"]["grab_selected_objects"] = True
    link = FakeLink(objects=3)
    act, win = act_with(cfg, link)
    act.apply([("two_begin", "orbit"), ("two_move", 0.01, 0.0, 0.1, 0.05), ("two_end",)])
    assert act.two_label is None and link.calls[0] == "grab_begin"
    gm = [c for c in link.calls if c[0] == "grab_move"][0]
    assert gm[1] == pytest.approx(0.01 * cfg["two_hand"]["grab_gain_px"]) and gm[3] == 0.1
    assert link.calls[-1] == "grab_end" and act.buttons == set()


def test_two_end_runs_even_when_autocad_not_in_front(cfg):
    link = FakeLink()
    act, win = act_with(cfg, link)
    act.apply([("two_begin", "orbit")])
    win.fg_name = "chrome.exe"
    act.apply([("two_end",)])
    assert link.calls[-1] == "zf_restore" and act.buttons == set()


def test_cursor_speed_same_inside_half_width_autocad(cfg):
    """Dulu: AutoCAD setengah layar -> kursor setengah lebih lambat. Sekarang skala = lebar layar."""
    full = SimInput(rect=(0, 0, 1920, 1080))
    half = SimInput(rect=(0, 0, 1920, 1080), window=(960, 0, 1920, 1080))
    out = []
    for win in (full, half):
        act = Actuator(cfg, win, gate=True, log=lambda s: None)
        win.pos = (1300, 500)
        act.apply([("move_by", 0.05, 0.0)])
        out.append(win.pos[0] - 1300)
    assert out[0] == out[1] == 96                                  # 0.05 x 1920 px


def test_view_axes_and_grab_step():
    r, u, toward = view_axes((0.0, 0.0, 1.0))                     # tampak atas
    assert r == pytest.approx((1, 0, 0)) and u == pytest.approx((0, 1, 0))
    r, u, toward = view_axes((0.0, -1.0, 0.0))                    # tampak depan
    assert r == pytest.approx((1, 0, 0)) and u == pytest.approx((0, 0, 1))
    r, u, toward = view_axes((-1.0, -1.0, 1.0))                   # SW isometric
    assert sum(r[i] * toward[i] for i in range(3)) == pytest.approx(0, abs=1e-9)
    assert u[2] > 0                                               # "atas" layar condong ke +Z
    d = grab_step((1, 0, 0), (0, 1, 0), 2.0, 10, -5)              # kanan 10 px, naik 5 px
    assert d == pytest.approx((20, 10, 0))


# ------------------------------------------------------------------ tombol kontrol & UI
def test_controls_render_with_two_hit_boxes():
    img, pad, boxes = glass.draw_controls(True, hover="quit")
    assert set(boxes) == {"pause", "quit"}
    q = boxes["quit"]
    assert img.getpixel(((q[0] + q[2]) // 2, (q[1] + q[3]) // 2))[3] > 200
    assert img.getpixel((0, 0))[3] == 0


def test_click_handler_dispatch_without_window():
    hits = []
    fake = 0x12345
    overlay._click_handlers[fake] = lambda x, y: hits.append((x, y))
    try:
        assert overlay._wndproc(fake, overlay.WM_MOUSEACTIVATE, 0, 0) == overlay.MA_NOACTIVATE
        overlay._wndproc(fake, overlay.WM_LBUTTONUP, 0, (40 << 16) | 25)
        assert hits == [(25, 40)]
    finally:
        overlay._click_handlers.pop(fake, None)


def test_island_explains_two_hand_mode(cfg):
    ctl = C.Controller(cfg)
    t, _ = run(ctl, lambda k: two(), 0.5)
    c = glass.island_content(ctl.view(), {"gate_ok": True}, t + 5)
    assert c["title"] == "Putar tampilan 3D" and "zoom" in c["sub"]
    ctl2 = C.Controller(cfg)
    t, _ = run(ctl2, lambda k: two("PINCH"), 0.5)
    assert glass.island_content(ctl2.view(), {"gate_ok": True}, t + 5)["title"] == "Geser tampilan"
    g, _ = glass.draw_guide(ctl.view())
    assert g.height > 300
