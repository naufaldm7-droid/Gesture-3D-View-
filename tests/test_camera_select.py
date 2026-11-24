"""Pemilihan kamera otomatis & peringatan kamera gelap/lambat (tanpa kamera sungguhan)."""

import time

import pytest

from gesture_cad import __main__ as M
from gesture_cad import config as CFG
from gesture_cad import glass


class FakeCap:
    def __init__(self, idx):
        self.idx = idx
        self.released = False

    def release(self):
        self.released = True


def setup(monkeypatch, cams):
    """cams: {index: (fps, kecerahan[, gerak])}; indeks yang tidak ada = tidak bisa dibuka."""
    opened = []

    def fake_open(cfg, idx):
        if idx not in cams:
            return None
        c = FakeCap(idx)
        opened.append(c)
        return c

    monkeypatch.setattr(M, "_open_one", fake_open)
    monkeypatch.setattr(M, "_probe", lambda cap, seconds=0.8: tuple(cams[cap.idx]) + ((1.5,) if len(cams[cap.idx]) == 2 else ()))
    return opened


@pytest.fixture
def cfg():
    c = CFG.load()
    assert c["camera"]["index"] == "auto"
    return c


def test_skips_black_privacy_camera(cfg, monkeypatch):
    # kamera bawaan dengan penutup privasi: hitam ~1 fps; webcam USB di indeks 1 normal
    opened = setup(monkeypatch, {0: (1.0, 0.0), 1: (30.0, 140.0)})
    cap = M.open_camera(cfg)
    assert cap.idx == 1 and opened[0].released and not cap.released


def test_first_good_camera_is_used_without_trying_others(cfg, monkeypatch):
    opened = setup(monkeypatch, {0: (30.0, 120.0), 1: (30.0, 140.0)})
    assert M.open_camera(cfg).idx == 0 and len(opened) == 1


def test_all_bad_still_opens_best_and_overlay_warns(cfg, monkeypatch):
    setup(monkeypatch, {0: (1.0, 0.0), 1: (6.0, 90.0)})
    assert M.open_camera(cfg).idx == 1          # lebih baik: terang walau lambat


def test_explicit_index_and_missing_camera(cfg, monkeypatch):
    setup(monkeypatch, {0: (1.0, 0.0)})
    assert M.open_camera(cfg, 0).idx == 0        # indeks eksplisit: dipakai apa adanya
    with pytest.raises(RuntimeError):
        M.open_camera(cfg, 2)
    setup(monkeypatch, {})
    with pytest.raises(RuntimeError):
        M.open_camera(cfg)


def test_skips_static_virtual_camera(cfg, monkeypatch):
    # "Windows Virtual Camera" menampilkan logo diam: terang & 30 fps tetapi tanpa derau sensor
    opened = setup(monkeypatch, {0: (30.0, 241.0, 0.0), 1: (30.0, 120.0, 1.8)})
    cap = M.open_camera(cfg)
    assert cap.idx == 1 and opened[0].released


def test_prefers_real_camera_even_if_dark_over_virtual(cfg, monkeypatch):
    setup(monkeypatch, {0: (30.0, 241.0, 0.0), 1: (1.0, 0.0, 0.0), 2: (6.0, 40.0, 0.9)})
    assert M.open_camera(cfg).idx == 2


class FakeGrabber:
    def __init__(self, fps, br, age=5.0, motion=1.0):
        self.started = time.monotonic() - age
        self.motion = motion
        self._h = (fps, br)

    def health(self):
        return self._h


def test_camera_warning_levels():
    assert M.camera_warning(FakeGrabber(30, 120)) is None
    assert M.camera_warning(FakeGrabber(1, 0)) == "dark"
    assert M.camera_warning(FakeGrabber(5, 120)) == "slow:5"
    assert M.camera_warning(FakeGrabber(1, 0, age=1.0)) is None   # baru menyala: belum dinilai
    assert M.camera_warning(FakeGrabber(30, 241, motion=0.0)) == "static"


def test_island_shows_camera_warning(cfg):
    from gesture_cad.controller import Controller

    v = Controller(cfg).view()
    c = glass.island_content(v, {"gate_ok": True, "cam_warn": "dark"}, 0.0)
    assert "Kamera gelap" in c["title"] and "F8/F9" in c["sub"]
    c = glass.island_content(v, {"gate_ok": True, "cam_warn": "static"}, 0.0)
    assert c["title"] == "Tidak ada kamera asli"
    c = glass.island_content(v, {"gate_ok": True, "cam_warn": "slow:5"}, 0.0)
    assert c["title"] == "Kamera lambat (5 fps)"


def test_config_rejects_bad_camera_index(cfg):
    cfg["camera"]["index"] = "kamera1"
    assert any("camera.index" in e for e in CFG.validate(cfg))
