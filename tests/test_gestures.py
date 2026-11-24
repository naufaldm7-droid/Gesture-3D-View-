import pytest

import synth
from gesture_cad import gestures as G
from gesture_cad.filters import OneEuro


@pytest.mark.parametrize("name", ["POINT", "PINCH", "FIST", "OPEN", "VICTORY", "THREE", "ROCK", "SHAKA",
                                  "THUMB_UP", "THUMB_DOWN"])
@pytest.mark.parametrize("roll", [-25, 0, 25])
def test_pose_classified(name, roll):
    pts = synth.pose_points(name)
    if not name.startswith("THUMB"):
        pts = synth.rotate(pts, roll)  # tangan sedikit miring tetap dikenali
    h = synth.make_hand(pts)
    pose, _ = G.classify(h.iso)
    assert pose == name


def test_mirrored_hand_same_pose():
    for name in ("POINT", "VICTORY", "SHAKA", "THUMB_UP"):
        pts = [(-x, y, z) for (x, y, z) in synth.pose_points(name)]  # tangan kiri
        assert G.classify(synth.make_hand(pts).iso)[0] == name


def test_fist_is_not_pinch():
    pose, info = G.classify(synth.hand("FIST").iso, was_pinching=True)
    assert pose == G.FIST


def test_thumb_sideways_is_not_thumb_up():
    pose, _ = G.classify(synth.make_hand(synth.base_points(thumb=True)).iso)
    assert pose == G.UNKNOWN


def test_pinch_hysteresis():
    th = dict(G.DEFAULT_THRESHOLDS)
    pts = synth.pose_points("PINCH")
    # buka jepitan sedikit: ujung ibu jari digeser ke kiri sampai rasio ~0.27
    x, y, z = pts[4]
    shift = 0.0
    while True:  # buka jepitan sedikit demi sedikit sampai rasio di antara ambang on/off
        shift += 0.01
        pts[4] = (x - shift, y, z)
        h = synth.make_hand(pts)
        r = G.pinch_ratio(h.iso)
        if r > th["pinch_on"] + 0.02:
            break
    assert th["pinch_on"] < r < th["pinch_off"]
    assert G.classify(h.iso, was_pinching=False)[0] != G.PINCH
    assert G.classify(h.iso, was_pinching=True)[0] == G.PINCH


def test_one_euro_reduces_jitter():
    import random

    random.seed(1)
    f = OneEuro(min_cutoff=1.0, beta=10.0)
    raw, out = [], []
    for i in range(300):
        v = 0.5 + random.uniform(-0.01, 0.01)
        raw.append(v)
        out.append(f(v, i / 30.0))
    tail = out[100:]
    assert max(tail) - min(tail) < 0.5 * (max(raw) - min(raw))
    assert abs(sum(tail) / len(tail) - 0.5) < 0.003


def test_thumb_pressed_on_side_of_index_counts_as_pinch():
    pts = synth.pose_points("POINT")
    pts[4] = (pts[7][0] - 0.12, pts[7][1], 0.0)   # ujung jempol menempel ruas atas telunjuk
    pose, info = G.classify(synth.make_hand(pts).iso)
    assert pose == G.PINCH
