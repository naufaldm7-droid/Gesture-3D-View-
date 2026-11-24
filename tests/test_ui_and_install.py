"""Uji komponen baru: penggambar kaca, pemasang perintah AutoCAD, aktuator gerak relatif & klik."""

import os
import sys

import pytest
from PIL import Image

import synth
from gesture_cad import config as CFG
from gesture_cad import controller as C
from gesture_cad import glass
from gesture_cad.actuator import Actuator, SimInput

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pasang_di_autocad as P  # noqa: E402


@pytest.fixture
def cfg():
    return CFG.load()


def _view(cfg, pose="POINT", seconds=0.5):
    ctl = C.Controller(cfg)
    t = 0.0
    for _ in range(int(seconds * 30)):
        t += 1 / 30.0
        ctl.update([synth.hand(pose)], t)
    return ctl, t


# ------------------------------------------------------------------ kaca
@pytest.mark.parametrize("state", [{"voice": {"state": "sleep"}, "gate_ok": True},
                                   {"voice": {"state": "listening", "partial": "poly line"}, "gate_ok": True},
                                   {"voice": {"state": "off"}, "gate_ok": False}])
def test_island_renders_with_transparent_corners(cfg, state):
    ctl, t = _view(cfg)
    c = glass.island_content(ctl.view(), state, t)
    w = glass.island_width(c)
    img, pad = glass.draw_island(ctl.view(), state, t, w)
    assert img.mode == "RGBA" and img.width == w + 2 * pad
    assert img.getpixel((0, 0))[3] == 0                      # sudut luar transparan
    assert img.getpixel((img.width // 2, img.height // 2))[3] > 150  # isi panel cukup pekat untuk teks


def test_glass_with_backdrop_and_rim(cfg):
    bg = Image.new("RGB", (100, 30), (200, 40, 40))
    img, pad = glass.glass(400, 120, 40, bg=bg)
    a = img.getpixel((pad + 2, pad + 60))[3]                 # tepi kiri: ada garis kilau
    assert a > 0
    assert img.getpixel((pad + 200, pad + 60))[0] > img.getpixel((pad + 200, pad + 60))[2]  # latar merah tembus


def test_camera_card_and_halo_and_guide(cfg):
    ctl, t = _view(cfg)
    frame = Image.new("RGB", (640, 480), (90, 90, 90))
    img, pad = glass.draw_camera_card(frame, ctl.view(), {"acad_ok": True, "fps": 30}, 300)
    assert img.width == 300 + 16 + 2 * pad
    halo = glass.draw_halo(ctl.view(), [(t - 0.1, "left")], t)
    assert halo.size == (96, 96) and halo.getbbox() is not None
    g, _ = glass.draw_guide(ctl.view())
    assert g.height > 300


def test_menu_painter_hover_is_fast_and_changes_pixels(cfg):
    ctl, t = _view(cfg, "SHAKA", 1.0)
    v = ctl.view()
    mp = glass.MenuPainter(600, 340)
    plain, pad = mp.render(v)
    b = [x for x in ctl.menu.buttons() if x.kind == "item"][0]
    lit, _ = mp.render(dict(v, hover=b))
    cx = pad + int((b.rect[0] + b.rect[2]) / 2 * 600)
    cy = pad + int((b.rect[1] + b.rect[3]) / 2 * 340) + 12
    assert plain.getpixel((cx, cy)) != lit.getpixel((cx, cy))


def test_font_falls_back_cleanly():
    f = glass.f_reg(12)
    assert f.getbbox("BOX")[2] > 0


# ------------------------------------------------------------------ pemasang acad.pgp
SAMPLE = ("; header\r\nSH,        ,               1,*OS Command: ,\r\n"
          "EXPLORER,  START EXPLORER, 1,,\r\n\r\n3A,        *3DARRAY\r\n")


def test_pgp_block_after_explorer_and_short_lines():
    out = P.insert_block(SAMPLE)
    assert out.index("EXPLORER,") < out.index(P.BEGIN) < out.index(P.END) < out.index("3A,")
    for ln in P.block().splitlines():
        if not ln.startswith(";"):
            assert len(ln) < 90, ln                           # baris panjang ditolak parser PGP
            assert '"' not in ln
            assert ln.rstrip().endswith(", 5,,")


def test_pgp_install_remove_roundtrip_is_exact():
    once = P.insert_block(SAMPLE)
    twice = P.insert_block(P.strip_block(once))
    assert once == twice                                    # pasang ulang idempoten
    assert P.strip_block(once) == SAMPLE                    # lepas = persis asli


# ------------------------------------------------------------------ aktuator
def _act(cfg, fg="acad.exe"):
    win = SimInput(rect=(0, 0, 1000, 800), foreground_name=fg)
    return Actuator(cfg, win, acad=None, gate=True, log=lambda s: None), win


def test_move_by_accumulates_subpixels_and_clamps(cfg):
    act, win = _act(cfg)
    win.pos = (500, 400)
    for _ in range(10):
        act.apply([("move_by", 0.00035, 0.0)])               # 0.35 px per langkah
    assert win.pos[0] == 503                                 # 10 x 0.35 px = 3.5 px -> 3 px, sisa disimpan
    act.apply([("move_by", 5.0, 5.0)])
    assert win.pos == (999, 799)                             # tidak keluar jendela


def test_click_is_down_up_and_reported_to_ui(cfg):
    act, win = _act(cfg)
    act.apply([("click", "right")])
    assert [e for e in win.events if e[0] == "button"] == [("button", "right", True), ("button", "right", False)]
    assert act.clicks == ["right"] and act.buttons == set()


class BusyLink:
    busy = True

    def __init__(self):
        self.sent = []

    def send(self, cmd, cancel):
        self.sent.append(cmd)


def test_busy_com_falls_back_to_keyboard(cfg):
    act, win = _act(cfg)
    act.acad = BusyLink()
    act.apply([("action", {"type": "command", "cmd": "_LINE", "cancel_first": True}, "LINE")])
    assert act.acad.sent == []
    assert ("type", "_LINE") in win.events                  # ESC ESC _LINE ENTER lewat keyboard
    act.acad.busy = False
    act.apply([("action", {"type": "command", "cmd": "_BOX", "cancel_first": True}, "BOX")])
    assert act.acad.sent == ["_BOX"]
