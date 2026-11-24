import pytest

import synth
from gesture_cad import config as CFG
from gesture_cad import controller as C

DT = 1.0 / 30


@pytest.fixture
def cfg():
    return CFG.load()


class Clock:
    def __init__(self, ctl):
        self.ctl = ctl
        self.t = 100.0
        self.log = []

    def feed(self, hands_fn, seconds):
        """hands_fn(k) -> list Hand untuk frame ke-k. Kembalikan niat selama periode ini."""
        out = []
        n = int(round(seconds / DT))
        for k in range(n):
            self.t += DT
            out += self.ctl.update(hands_fn(k), self.t)
        self.log += out
        return out


def kinds(intents, kind):
    return [i for i in intents if i[0] == kind]


def still(name, **kw):
    h = synth.hand(name, **kw)
    return lambda k: [h]


def nothing(k):
    return []


def test_pinch_without_pointer_does_not_click(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("OPEN"), 0.3)
    ck.feed(still("PINCH"), 0.3)
    assert kinds(ck.log, "button") == []


def test_fist_orbit_moves_relative_and_releases(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(lambda k: [synth.hand("FIST", center=(0.4 + 0.01 * k, 0.6))], 0.6)
    assert ck.ctl.mode == C.ORBIT
    assert ("drag_begin", "orbit") in ck.log
    rel = kinds(ck.log, "move_rel")
    assert rel and sum(r[1] for r in rel) > 0.05  # tangan bergerak ke kanan -> dx positif
    ck.feed(still("OPEN"), 0.3)
    assert ck.log.count(("drag_end", "orbit")) == 1
    assert ck.ctl.mode == C.IDLE


def test_victory_pans(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(lambda k: [synth.hand("VICTORY", center=(0.5, 0.6 - 0.01 * k))], 0.5)
    assert ("drag_begin", "pan") in ck.log
    assert sum(r[2] for r in kinds(ck.log, "move_rel")) < -0.03


def test_three_fingers_zoom_up_is_zoom_in(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(lambda k: [synth.hand("THREE", center=(0.5, 0.7 - 0.012 * k))], 0.8)
    wheel = kinds(ck.log, "wheel")
    assert wheel and sum(w[1] for w in wheel) > 0


def test_short_flicker_is_ignored(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT"), 0.4)
    ck.feed(still("FIST"), 0.05)  # 50 ms < stable_ms
    ck.feed(still("POINT"), 0.2)
    assert ("drag_begin", "orbit") not in ck.log


def test_thumb_up_hold_fires_enter_once(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("THUMB_UP"), 0.4)
    assert kinds(ck.log, "action") == []  # belum cukup lama
    ck.feed(still("THUMB_UP"), 2.0)
    acts = kinds(ck.log, "action")
    assert len(acts) == 1 and acts[0][1] == {"type": "key", "key": "ENTER"}
    ck.feed(still("OPEN"), 0.3)
    ck.feed(still("THUMB_UP"), 1.0)
    assert len(kinds(ck.log, "action")) == 2


def test_thumb_down_is_undo_command(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("THUMB_DOWN"), 1.0)
    acts = kinds(ck.log, "action")
    assert acts and acts[0][1]["type"] == "command" and acts[0][1]["cmd"] == "_U"


def test_menu_open_select_by_pinch(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(still("SHAKA"), 1.0)
    assert ctl.mode == C.MENU
    target = [b for b in ctl.menu.buttons() if b.kind == "item"][0]  # item pertama halaman pertama
    x0, y0, x1, y1 = target.rect
    at = ((x0 + x1) / 2, (y0 + y1) / 2)
    ck.feed(lambda k: [synth.hand_aim("POINT", at, cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"])], 0.5)  # < dwell
    assert kinds(ck.log, "action") == []
    ck.feed(lambda k: [synth.hand_aim("PINCH", at, cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"])], 0.2)
    acts = kinds(ck.log, "action")
    assert len(acts) == 1 and acts[0][1] == target.payload and acts[0][2] == target.label
    assert ctl.mode == C.IDLE


def test_menu_dwell_selects_and_tab_switches_page(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(still("SHAKA"), 1.0)
    tab = [b for b in ctl.menu.buttons() if b.kind == "tab" and b.label == "VIEW"][0]
    at = ((tab.rect[0] + tab.rect[2]) / 2, (tab.rect[1] + tab.rect[3]) / 2)
    ck.feed(lambda k: [synth.hand_aim("POINT", at, cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"])], 1.5)
    assert ctl.menu.page == tab.payload and ctl.mode == C.MENU
    item = [b for b in ctl.menu.buttons() if b.kind == "item" and b.label == "ZOOM EXT"][0]
    at = ((item.rect[0] + item.rect[2]) / 2, (item.rect[1] + item.rect[3]) / 2)
    ck.feed(lambda k: [synth.hand_aim("POINT", at, cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"])], 1.5)
    acts = kinds(ck.log, "action")
    assert len(acts) == 1 and acts[0][1]["cmd"] == "_ZOOM _E"


def test_rock_closes_menu_without_esc(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(still("SHAKA"), 1.0)
    ck.feed(still("ROCK"), 1.5)
    assert ctl.mode == C.IDLE
    assert kinds(ck.log, "action") == []  # ROCK menutup menu, tidak ikut menembak ESC


def test_two_open_palms_toggle_pause(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    both = lambda k: [synth.hand("OPEN", center=(0.3, 0.6), label="Left"),
                      synth.hand("OPEN", center=(0.7, 0.6), label="Right")]
    ck.feed(both, 2.0)
    assert ctl.armed is False and ("release_all",) in ck.log
    n = len(ck.log)
    ck.feed(still("POINT"), 0.5)
    assert kinds(ck.log[n:], "move_abs") == []  # dijeda: tidak ada gerak kursor
    ck.feed(nothing, 0.5)
    ck.feed(both, 2.0)
    assert ctl.armed is True


def test_dominant_hand_preferred(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(lambda k: [synth.hand("FIST", center=(0.3, 0.6), label="Left"),
                       synth.hand("POINT", center=(0.7, 0.6), label="Right")], 0.4)
    assert ctl.mode == C.POINTER


def test_fingers_cut_by_frame_edge_are_ignored(cfg):
    from gesture_cad import gestures as G

    # telapak terbuka di tepi kanan: kelingking keluar frame -> jangan jadi THREE/zoom
    h = synth.hand("OPEN", center=(0.93, 0.7))
    assert G.fingers_near_edge(h.norm, 0.025)
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(lambda k: [h], 1.0)
    assert ctl.raw_pose == G.UNKNOWN and ctl.view()["edge"] is True
    assert ctl.mode == C.IDLE and kinds(ck.log, "wheel") == []


def test_wrist_below_frame_is_allowed(cfg):
    from gesture_cad import gestures as G

    h = synth.hand("POINT", center=(0.6, 1.02))  # pergelangan terpotong bawah, jari masih di dalam
    assert not G.fingers_near_edge(h.norm, 0.025)


@pytest.mark.parametrize("size_px", [100.0, 150.0])  # tangan jauh / dekat (uji kamera: ~150 px)
def test_every_menu_button_reachable_with_hand_inside_frame(cfg, size_px, monkeypatch):
    from gesture_cad import gestures as G

    monkeypatch.setattr(synth, "SIZE_PX", size_px)

    ctl = C.Controller(cfg)
    z, w = cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"]
    for page in range(len(ctl.menu.pages)):
        ctl.menu.page = page
        for b in ctl.menu.buttons():
            at = ((b.rect[0] + b.rect[2]) / 2, (b.rect[1] + b.rect[3]) / 2)
            h = synth.hand_aim("POINT", at, z, w)
            assert not G.fingers_near_edge(h.norm, cfg["thresholds"]["edge_margin"]), b.label


@pytest.mark.parametrize("size_px", [100.0, 150.0])
def test_pointer_zone_corners_keep_fingers_in_frame(cfg, size_px, monkeypatch):
    """Kursor harus bisa ke pojok jendela AutoCAD tanpa jari terpotong tepi kamera."""
    from gesture_cad import gestures as G

    monkeypatch.setattr(synth, "SIZE_PX", size_px)
    z, w = cfg["pointer"]["zone"], cfg["pointer"]["tip_weight"]
    for at in ((0, 0), (1, 0), (0, 1), (1, 1)):
        for pose in ("POINT", "PINCH"):
            h = synth.hand_aim(pose, at, z, w)
            assert not G.fingers_near_edge(h.norm, cfg["thresholds"]["edge_margin"]), (pose, at)


# ---------------------------------------------------------------- kursor presisi (relative)
def moving(name, x0=0.45, vx=0.004, vy=0.0, y0=0.6):
    return lambda k: [synth.hand(name, center=(x0 + vx * k, y0 + vy * k))]


def total(intents, kind="move_by"):
    ms = kinds(intents, kind)
    return (sum(m[1] for m in ms), sum(m[2] for m in ms))


def test_point_moves_cursor_relative(cfg):
    ck = Clock(C.Controller(cfg))
    out = ck.feed(moving("POINT", vx=0.006), 0.6)
    assert ck.ctl.mode == C.POINTER
    sx, sy = total(out)
    assert sx > 0.01 and abs(sy) < 0.2 * sx          # tangan ke kanan -> kursor ke kanan


def _travel(cfg, vx, seconds, x0=0.3):
    """Diam dulu (kursor terkunci) -> gerak ke kanan -> diam lagi sampai filter selesai."""
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT", center=(x0, 0.6)), 0.4)
    ck.feed(moving("POINT", x0=x0, vx=vx), seconds)
    ck.feed(still("POINT", center=(x0 + vx * int(round(seconds / DT)), 0.6)), 0.8)
    return total(ck.log)[0]


def test_fast_hand_moves_cursor_further_than_slow(cfg):
    slow = _travel(cfg, 0.002, 2.0)   # 0.12 lebar frame, pelan (~0.06 frame/detik)
    fast = _travel(cfg, 0.02, 0.2)    # jarak sama, 10x lebih cepat (~0.6 frame/detik)
    assert slow > 0 and fast > 2.0 * slow
def test_still_hand_locks_and_ignores_jitter(cfg):
    ctl = C.Controller(cfg)
    ck = Clock(ctl)
    ck.feed(still("POINT"), 0.6)
    assert ctl.ptr_state == "locked"
    n = len(ck.log)
    ck.feed(lambda k: [synth.hand("POINT", center=(0.5 + (0.003 if k % 2 else -0.003), 0.6))], 0.6)
    assert kinds(ck.log[n:], "move_by") == []        # getaran +-2 px kamera diabaikan
    ck.feed(moving("POINT", x0=0.5, vx=0.01), 0.5)
    assert total(ck.log[n:])[0] > 0                   # geseran sungguhan melepas kunci


def test_quick_pinch_is_one_click_without_drag(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT"), 0.4)
    ck.feed(still("PINCH"), 0.2)
    assert ck.ctl.mode == C.DRAG
    ck.feed(still("POINT"), 0.3)
    assert kinds(ck.log, "click") == [("click", "left")]
    assert kinds(ck.log, "button") == []


def test_pinch_rewinds_motion_just_before_click(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(moving("POINT", x0=0.4, vx=0.008), 0.5)
    n = len(ck.log)
    ck.feed(still("PINCH", center=(0.4 + 0.008 * 15, 0.6)), 0.1)
    back = kinds(ck.log[n:], "move_by")
    assert any(m[1] < 0 for m in back)                # gerak terakhir dibatalkan (diputar mundur)


def test_pinch_and_move_is_drag(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT"), 0.4)
    ck.feed(moving("PINCH", x0=0.5, vx=0.006), 0.6)
    btn = kinds(ck.log, "button")
    assert btn == [("button", "left", "down")]
    assert total(ck.log)[0] > 0
    ck.feed(still("POINT", center=(0.5 + 0.006 * 18, 0.6)), 0.3)
    assert kinds(ck.log, "button")[-1] == ("button", "left", "up")
    assert kinds(ck.log, "click") == []


def test_long_still_pinch_is_right_click(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT"), 0.4)
    ck.feed(still("PINCH"), 1.2)
    ck.feed(still("POINT"), 0.3)
    assert kinds(ck.log, "click") == [("click", "right")]
    assert kinds(ck.log, "button") == []


def test_hand_lost_during_pinch_does_not_click(cfg):
    ck = Clock(C.Controller(cfg))
    ck.feed(still("POINT"), 0.4)
    ck.feed(still("PINCH"), 0.2)
    ck.feed(nothing, 0.1)
    assert ck.ctl.mode == C.DRAG  # masih dalam masa tenggang
    ck.feed(nothing, 0.4)
    assert ck.ctl.mode == C.IDLE
    assert kinds(ck.log, "click") == [] and kinds(ck.log, "button") == []


def test_absolute_mode_still_available(cfg):
    cfg["pointer"]["mode"] = "absolute"
    ck = Clock(C.Controller(cfg))
    out = ck.feed(still("POINT"), 0.3)
    moves = kinds(out, "move_abs")
    assert moves and all(0 <= m[1] <= 1 and 0 <= m[2] <= 1 for m in moves)
    ck.feed(still("PINCH"), 0.2)
    ck.feed(still("POINT"), 0.3)
    assert kinds(ck.log, "click") == [("click", "left")]


def test_voice_style_external_action(cfg):
    ctl = C.Controller(cfg)
    out = ctl.external({"type": "command", "cmd": "_LINE"}, "LINE", 1.0)
    assert out == [("action", {"type": "command", "cmd": "_LINE"}, "LINE")]
    out = ctl.external({"type": "internal", "op": "open_menu"}, "MENU", 1.1)
    assert ctl.mode == C.MENU
