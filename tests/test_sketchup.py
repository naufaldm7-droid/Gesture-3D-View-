"""Uji profil SketchUp: konfigurasi, navigasi (tengah = orbit, Shift+tengah = pan), aksi lewat jembatan +
cadangan shortcut, kamera dua tangan lewat jembatan, klien TCP terhadap server tiruan, pemasang, dan suara.
Ekstensi Ruby sendiri hanya bisa diuji di dalam SketchUp (lihat --verify-sketchup)."""

import json
import os
import socket
import sys
import threading
import time

import pytest

from gesture_cad import config as CFG
from gesture_cad.actuator import Actuator, SimInput
from gesture_cad.keys import VK
from gesture_cad.sketchup import SketchUpLink
from gesture_cad.voice import VoiceMatcher

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import pasang_di_sketchup as PS  # noqa: E402

SU_CFG = os.path.join(APP, "config_sketchup.json")


@pytest.fixture
def cfg():
    return CFG.load(SU_CFG)


def test_profile_is_valid_and_sketchup(cfg):
    assert CFG.validate(cfg) == []
    assert cfg["host"]["name"] == "sketchup" and cfg["output"]["target_processes"] == ["sketchup.exe"]
    assert cfg["output"]["nav"] == {"orbit": [], "pan": ["SHIFT"]}
    labels = [it["label"] for p in cfg["menu"]["pages"] for it in p["items"]]
    for must in ("LINE", "PUSH/PULL", "FOLLOW ME", "MOVE", "ROTATE", "TAPE", "ZOOM EXT", "X-RAY"):
        assert must in labels


def test_su_item_normalizes_with_fallback_key():
    a = CFG.normalize_action({"label": "LINE", "su": "selectLineTool:", "key": "L"})
    assert a == {"type": "sketchup", "op": "action", "arg": "selectLineTool:", "fallback_key": "L"}
    assert CFG.normalize_action({"su_render": 1}) == {"type": "sketchup", "op": "render", "arg": 1}
    errs = []
    CFG.validate_action({"type": "sketchup", "op": "action", "arg": "rm -rf"}, "x", errs)
    assert errs  # nama aksi wajib berbentuk 'namaAksi:'


class FakeBridge:
    def __init__(self, connected=True):
        self.connected = connected
        self.sent, self.cams = [], []

    def send(self, op, arg=None):
        self.sent.append((op, arg))

    def camera(self, *a):
        self.cams.append(a)


def make(cfg, bridge=None):
    win = SimInput(rect=(0, 0, 1000, 800), foreground_name="sketchup.exe")
    act = Actuator(cfg, win, gate=True, log=lambda s: None)
    act.bridge = bridge
    return act, win


def test_sketchup_navigation_mapping(cfg):
    act, win = make(cfg)
    act.apply([("drag_begin", "orbit")])
    assert "middle" in act.buttons and VK["SHIFT"] not in act.keys      # SketchUp: tengah = orbit
    act.apply([("drag_end", "orbit"), ("drag_begin", "pan")])
    assert "middle" in act.buttons and VK["SHIFT"] in act.keys          # Shift + tengah = pan
    act.apply([("wheel", 1)])                                           # zoom saat menahan: lepas-zoom-pegang
    assert VK["SHIFT"] in act.keys and "middle" in act.buttons
    act.apply([("drag_end", "pan")])
    assert act.buttons == set() and act.keys == set()


def test_actions_go_to_bridge_or_fallback_key(cfg):
    line = CFG.normalize_action({"su": "selectLineTool:", "key": "L"})
    br = FakeBridge()
    act, win = make(cfg, br)
    act.apply([("action", line, "LINE")])
    assert br.sent == [("action", "selectLineTool:")]
    act, win = make(cfg, FakeBridge(connected=False))
    act.apply([("action", line, "LINE")])
    assert ("combo", "L") in win.events                                 # cadangan shortcut bawaan
    act, win = make(cfg, None)
    act.apply([("action", CFG.normalize_action({"su": "viewTop:"}), "TOP")])
    assert "belum terhubung" in act.notice


def test_two_hands_drive_camera_through_bridge(cfg):
    br = FakeBridge()
    act, win = make(cfg, br)
    act.apply([("two_begin", "orbit"), ("two_move", 0.01, -0.02, 0.1, 0.05), ("two_end",)])
    assert br.cams == [("orbit", 0.01, -0.02, 0.1, 0.05)]
    assert act.buttons == set() and not [e for e in win.events if e[0] == "button"]   # tanpa emulasi mouse
    act, win = make(cfg, FakeBridge(connected=False))
    act.apply([("two_begin", "orbit")])
    assert "middle" in act.buttons                                      # cadangan: mouse
    act.apply([("two_end",)])


# ------------------------------------------------------------------ klien TCP vs server tiruan
class MockSketchUp(threading.Thread):
    """Meniru protokol ekstensi Ruby: hello & action dijawab, camera tidak (kecuali ada id)."""

    def __init__(self):
        threading.Thread.__init__(self, daemon=True)
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.got = []

    def run(self):
        conn, _ = self.srv.accept()
        buf = b""
        while True:
            try:
                data = conn.recv(65536)
            except OSError:
                return
            if not data:
                return
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line)
                self.got.append(msg)
                if msg["op"] == "hello":
                    rep = {"ok": True, "sketchup": "25.0.test"}
                elif msg["op"] == "action":
                    rep = {"ok": msg["arg"] != "bogusTool:"}
                else:
                    rep = None
                if rep is not None and "id" in msg:
                    rep["id"] = msg["id"]
                    conn.sendall((json.dumps(rep) + "\n").encode())


def test_link_handshake_request_and_camera_coalescing(cfg):
    srv = MockSketchUp()
    srv.start()
    link = SketchUpLink(srv.port, cfg, log=lambda s: None)
    for _ in range(50):
        if link.connected:
            break
        time.sleep(0.05)
    assert link.connected and link.version == "25.0.test"
    assert link.request("action", "selectLineTool:")["ok"] is True
    assert link.request("action", "bogusTool:")["ok"] is False
    for _ in range(20):                       # 20 gerak cepat -> sedikit pesan, total tetap sama
        link.camera("orbit", 0.001, 0.0, 0.0, 0.01)
    time.sleep(0.5)
    cams = [m for m in srv.got if m["op"] == "camera"]
    assert cams and len(cams) <= 20
    assert sum(m["dx"] for m in cams) == pytest.approx(0.02)
    assert sum(m["zoom"] for m in cams) == pytest.approx(0.2)
    assert cams[0]["orbit_gain"] == cfg["two_hand"]["camera_orbit_gain"]
    link.stop()


def test_link_reports_not_connected_without_sketchup(cfg):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                   # port kosong: tidak ada SketchUp
    link = SketchUpLink(port, cfg, log=lambda s: None)
    time.sleep(0.6)
    assert not link.connected and "belum" in link.status
    assert link.request("action", "selectLineTool:", timeout=0.3) is None
    link.stop()


# ------------------------------------------------------------------ pemasang
def test_installer_writes_loader_and_removes_cleanly(tmp_path, monkeypatch):
    plug = tmp_path / "SketchUp" / "SketchUp 2025" / "SketchUp" / "Plugins"
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    plug.mkdir(parents=True)
    dirs = PS.plugin_dirs()
    assert dirs == [str(plug)]
    PS.install(dirs[0])
    rb = (plug / "tci_gesture_control.rb").read_text(encoding="utf-8")
    assert "APP_DIR = '%s'" % PS.HERE.replace("\\", "/") in rb and "\\" not in rb.split("APP_DIR = ")[1].split("'")[1]
    assert (plug / "tci_gesture_control" / "main.rb").exists()
    assert (plug / "tci_gesture_control" / "icons" / "hand_24.png").exists()
    PS.remove(dirs[0])
    assert not any(p.name.startswith("tci_") for p in plug.iterdir())


def test_loader_escapes_quotes():
    assert "O\\'Neil" in PS.loader_rb(r"C:\Users\O'Neil\app")


# ------------------------------------------------------------------ suara
def test_sketchup_voice_commands(cfg):
    m = VoiceMatcher(cfg["voice"])
    assert m.decide("sketch up please help me", False) == ("wake", None)
    st, c = m.decide("sketch up push pull", False)
    assert st == "wake" and c[1] == "PUSH/PULL"
    assert m.decide("follow me", True)[1][1] == "FOLLOW ME"
    assert m.decide("x ray", True)[1][1] == "X-RAY"
    assert m.decide("we need to move fast", False) == (None, None)
    v = m.vocabulary()
    assert "sketch" in v and "sketchup" not in v and "pushpull" not in v
