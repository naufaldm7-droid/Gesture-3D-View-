import copy

import pytest

from gesture_cad import config as CFG
from gesture_cad.actuator import Actuator, SimInput
from gesture_cad.autocad import build_command_string
from gesture_cad.keys import VK, parse_combo
from gesture_cad.menu import Menu


@pytest.fixture
def cfg():
    return CFG.load()


def test_shipped_config_is_valid(cfg):
    assert CFG.validate(cfg) == []


def test_bad_config_reports_errors(cfg):
    bad = copy.deepcopy(cfg)
    bad["continuous"]["WAVE"] = "pointer"
    bad["discrete"]["FIST"] = {"label": "X", "key": "NOPE"}
    bad["thresholds"]["pinch_on"] = 0.5
    errs = CFG.validate(bad)
    assert any("WAVE" in e for e in errs)
    assert any("NOPE" in e for e in errs)
    assert any("FIST" in e and "sekaligus" in e for e in errs)
    assert any("histeresis" in e for e in errs)


def test_parse_combo():
    assert parse_combo("ctrl+shift+z") == [VK["CTRL"], VK["SHIFT"], VK["Z"]]
    assert parse_combo("F8") == [0x77]
    with pytest.raises(ValueError):
        parse_combo("CTRL+WOW")


def test_menu_layout_inside_frame_and_no_overlap(cfg):
    m = Menu(cfg["menu"])
    for page in range(len(m.pages)):
        m.page = page
        bs = m.buttons()
        for b in bs:
            x0, y0, x1, y1 = b.rect
            assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                ox = min(a.rect[2], b.rect[2]) - max(a.rect[0], b.rect[0])
                oy = min(a.rect[3], b.rect[3]) - max(a.rect[1], b.rect[1])
                assert ox <= 0 or oy <= 0, (a.label, b.label)
        centre = bs[-1]
        assert m.hit((centre.rect[0] + centre.rect[2]) / 2, (centre.rect[1] + centre.rect[3]) / 2).id == centre.id


def test_command_string():
    assert build_command_string("_BOX") == "\x1b\x1b_BOX "
    assert build_command_string(" _ZOOM _E ", cancel_first=False) == "_ZOOM _E "


def make_act(cfg, fg="acad.exe"):
    win = SimInput(rect=(0, 0, 1000, 800), foreground_name=fg)
    return Actuator(cfg, win, acad=None, gate=True, log=lambda s: None), win


def evs(win, kind):
    return [e for e in win.events if e[0] == kind]


def test_move_abs_maps_into_window(cfg):
    act, win = make_act(cfg)
    act.apply([("move_abs", 0.5, 0.5)])
    assert win.pos == pytest.approx((499.5, 399.5))


def test_gate_blocks_mouse_when_autocad_not_in_front(cfg):
    act, win = make_act(cfg, fg="notepad.exe")
    act.apply([("move_abs", 0.1, 0.1), ("button", "left", "down"), ("wheel", 2)])
    assert evs(win, "cursor") == [] and evs(win, "button") == [] and evs(win, "wheel") == []


def test_gate_releases_held_buttons(cfg):
    act, win = make_act(cfg)
    act.apply([("button", "left", "down")])
    win.fg_name = "chrome.exe"
    act.apply([])
    assert evs(win, "button") == [("button", "left", True), ("button", "left", False)]


def test_orbit_holds_shift_and_middle_then_releases(cfg):
    act, win = make_act(cfg)
    act.apply([("drag_begin", "orbit"), ("move_rel", 0.01, 0.0, "orbit"), ("drag_end", "orbit")])
    assert ("key", VK["SHIFT"], True) in win.events and ("key", VK["SHIFT"], False) in win.events
    assert evs(win, "button") == [("button", "middle", True), ("button", "middle", False)]
    assert act.buttons == set() and act.keys == set()


def test_pan_reclutches_at_edge(cfg):
    act, win = make_act(cfg)
    act.apply([("drag_begin", "pan")])
    for _ in range(40):
        act.apply([("move_rel", 0.05, 0.0, "pan")])  # 90 px per langkah ke kanan
    presses = [e for e in evs(win, "button") if e[2]]
    assert len(presses) >= 2  # sempat dilepas & ditekan ulang di tengah
    assert 0 < win.pos[0] < 1000
    act.release_all()
    assert act.buttons == set()


def test_command_falls_back_to_typing(cfg):
    act, win = make_act(cfg)
    act.apply([("action", {"type": "command", "cmd": "_BOX", "cancel_first": True}, "BOX")])
    assert [e for e in win.events if e[0] in ("combo", "type")] == [
        ("combo", "ESC"), ("combo", "ESC"), ("type", "_BOX"), ("combo", "ENTER")]


def test_key_action_blocked_when_not_in_front(cfg):
    act, win = make_act(cfg, fg="explorer.exe")
    act.apply([("action", {"type": "key", "key": "ENTER"}, "ENTER")])
    assert evs(win, "combo") == [] and "batal" in act.notice
