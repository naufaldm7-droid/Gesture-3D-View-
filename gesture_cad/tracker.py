"""Pelacak tangan MediaPipe (Tasks API, HandLandmarker mode VIDEO).

Deteksi dijalankan pada frame ASLI (tidak dicerminkan) supaya label Left/Right sesuai tangan pengguna;
koordinat x baru dicerminkan sesudahnya agar tampilan seperti cermin.
"""

import os

from .config import APP_DIR
from .gestures import Hand

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")


def model_path(cfg):
    p = cfg["tracker"]["task_model"]
    return p if os.path.isabs(p) else os.path.join(APP_DIR, p)


class HandTracker:
    def __init__(self, cfg):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision

        path = model_path(cfg)
        if not os.path.exists(path):
            raise FileNotFoundError(
                "Model tangan belum ada: %s\nUnduh dulu: python -m gesture_cad --download-model" % path)
        tc = cfg["tracker"]
        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=int(tc["max_hands"]),
            min_hand_detection_confidence=float(tc["min_detection"]),
            min_hand_presence_confidence=float(tc["min_tracking"]),
            min_tracking_confidence=float(tc["min_tracking"]),
        )
        self._mp = mp
        self._lm = vision.HandLandmarker.create_from_options(opts)
        self._last_ts = -1
        self.mirror = bool(cfg["camera"]["mirror"])
        self.swap = bool(cfg["hand"].get("swap_labels", False))

    def process(self, frame_bgr, t_seconds):
        """frame_bgr: frame kamera ASLI (belum dicerminkan). Kembalikan list Hand."""
        import cv2

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = self._mp.Image(self._mp.ImageFormat.SRGB, rgb)
        ts = int(t_seconds * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1  # timestamp wajib naik
        self._last_ts = ts
        res = self._lm.detect_for_video(img, ts)

        hands = []
        for i, lms in enumerate(res.hand_landmarks):
            cat = res.handedness[i][0] if i < len(res.handedness) and res.handedness[i] else None
            label = cat.category_name if cat is not None else "Unknown"
            if self.swap and label in ("Left", "Right"):
                label = "Left" if label == "Right" else "Right"
            score = cat.score if cat is not None else 0.0
            norm = [((1.0 - p.x) if self.mirror else p.x, p.y, p.z) for p in lms]
            hands.append(Hand.from_norm(label, score, norm, w, h))
        return hands

    def close(self):
        try:
            self._lm.close()
        except Exception:
            pass


def download_model(cfg, log=print):
    import urllib.request

    path = model_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    log("Mengunduh %s\n  -> %s" % (MODEL_URL, path))
    with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(tmp, "wb") as fh:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            fh.write(chunk)
    os.replace(tmp, path)
    log("Selesai: %.1f MB" % (os.path.getsize(path) / 1e6))
    return path
