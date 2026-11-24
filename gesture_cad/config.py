"""Memuat dan memvalidasi config.json (nilai bawaan di sini, file pengguna menimpanya)."""

import copy
import json
import os
import re

from . import gestures as G
from .keys import parse_combo

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

CONTINUOUS_MODES = ("pointer", "drag", "orbit", "pan", "zoom", "idle")
ACTION_TYPES = ("command", "key", "keys", "internal", "sketchup")
SKETCHUP_OPS = ("action", "render", "xray")
INTERNAL_OPS = ("open_menu", "close_menu", "toggle_arm", "quit")
MAX_ITEMS_PER_PAGE = 16
MAX_LABEL = 14

DEFAULTS = {
    "camera": {"index": 0, "width": 640, "height": 480, "fps": 30, "backend": "dshow", "fourcc": "MJPG", "mirror": True},
    "tracker": {
        "max_hands": 2, "model_complexity": 1, "min_detection": 0.6, "min_tracking": 0.5,
        "task_model": "models/hand_landmarker.task",
    },
    "thresholds": dict(G.DEFAULT_THRESHOLDS),
    "hand": {"dominant": "Right", "fallback_any": True, "swap_labels": False},
    "timing": {
        "stable_ms": {"default": 120, "PINCH": 40, "POINT": 70},
        "lost_grace_ms": 250,
        "hold_ms": 600,
        "arm_hold_ms": 1500,
        "click_freeze_ms": 120,
        "click_rewind_ms": 120,
        "menu_open_grace_ms": 600,
    },
    "pointer": {
        "mode": "relative",        # "relative" (seperti mouse, presisi) atau "absolute" (tunjuk posisi layar)
        "gain_slow": 0.6,          # lebar layar per lebar frame kamera saat tangan bergerak pelan
        "gain_fast": 2.4,          # ... saat tangan bergerak cepat
        "speed_slow": 0.12,        # kecepatan tangan (lebar frame/detik) batas "pelan"
        "speed_fast": 0.9,         # ... batas "cepat"
        "lock_speed": 0.03,        # tangan lebih pelan dari ini selama lock_ms -> kursor terkunci
        "lock_ms": 200,
        "unlock_dist": 0.009,      # tangan harus bergeser sejauh ini (lebar frame) untuk melepas kunci
        "preclick_ratio": 0.5,     # rasio jepit di bawah ini: cincin kursor mulai mengecil (umpan balik)
        "drag_threshold": 0.025,   # jepit lalu geser sejauh ini = drag; kurang dari ini = klik
        "longpress_ms": 800,       # jepit diam selama ini = klik kanan
        "zone": [0.2, 0.25, 0.75, 0.68],   # mode absolute & kursor menu
        "tip_weight": 0.3,
        "filter": {"min_cutoff": 0.8, "beta": 3.0, "d_cutoff": 1.0},
    },
    "motion": {
        "deadzone": 0.004,
        "orbit_gain_px": 1100,
        "pan_gain_px": 1400,
        "accel_min": 0.5,          # gerak pelan: orbit/pan setengah kecepatan (halus)
        "accel_max": 1.6,          # gerak cepat: lebih jauh
        "zoom_step": 0.05,
        "zoom_invert": False,
        "edge_margin_px": 60,
        "filter": {"min_cutoff": 1.5, "beta": 5.0, "d_cutoff": 1.0},
    },
    "host": {
        "name": "autocad",         # "autocad" (COM) | "sketchup" (jembatan Ruby)
        "label": "AutoCAD",        # nama yang tampil di overlay
        "bridge_port": 47820,      # SketchUp: port TCP lokal ekstensi Ruby (127.0.0.1)
    },
    "output": {
        "nav": {"orbit": ["SHIFT"], "pan": []},  # pengubah + tombol tengah per gerak (AutoCAD)
        "require_foreground": True,
        "target_processes": ["acad.exe"],
        "progids": ["AutoCAD.Application", "AutoCAD.Application.25.1", "AutoCAD.Application.25",
                    "BricscadApp.AcadApplication"],
        "toggle_hotkey": "CTRL+ALT+G",
        "start_armed": True,
        "activate_autocad_on_start": True,
    },
    "continuous": {"POINT": "pointer", "PINCH": "drag", "FIST": "orbit", "VICTORY": "pan",
                   "THREE": "zoom", "OPEN": "idle"},
    "discrete": {
        "THUMB_UP": {"label": "ENTER", "key": "ENTER"},
        "THUMB_DOWN": {"label": "UNDO", "cmd": "_U"},
        "ROCK": {"label": "ESC", "key": "ESC"},
        "SHAKA": {"label": "MENU", "internal": "open_menu"},
    },
    "menu": {"dwell_ms": 900, "columns": 4, "close_after_select": True, "pages": []},
    "hud": {"scale": 1.0, "topmost": True, "show_help": True, "corner": "bottom-right"},
    "two_hand": {
        "enabled": True,
        "orbit_pose": "FIST",      # dua kepalan = pegang & putar tampilan 3D
        "pan_pose": "PINCH",       # dua cubitan = geser (pan) tampilan, seperti peta di ponsel
        "stable_ms": 150,
        "grace_ms": 250,
        "deadzone": 0.003,         # geser minimum (lebar frame)
        "twist_deadzone": 0.012,   # putar minimum (radian)
        "scale_deadzone": 0.012,   # rentang minimum (log jarak)
        "zoomfactor": 20,          # ZOOMFACTOR AutoCAD selama sesi dua tangan (bawaan 60): zoom lebih halus
        "grab_selected_objects": False,  # True: dua kepalan memindah objek yang sedang terpilih (bukan tampilan)
        "grab_gain_px": 1400,      # OBJEK: piksel layar per lebar frame gerak tangan
        "rotate": True,            # OBJEK: putar kedua kepalan seperti setir = rotasi objek
        "scale": True,             # OBJEK: rentang/rapat tangan = skala objek
        "view_twist_gain": 0.25,   # TAMPILAN (tanpa objek terpilih): putar setir -> orbit horizontal
        "view_zoom_step": 0.035,   # TAMPILAN: log jarak per satu langkah roda (kecil = halus)
        "camera_via_bridge": True,  # SketchUp: kamera lewat API Ruby, bukan emulasi mouse
        "camera_orbit_gain": 3.0,  # radian per lebar frame gerak tangan
        "camera_pan_gain": 1.5,    # (jarak kamera) per lebar frame
        "camera_zoom_gain": 1.0,   # pengali perubahan log rentang tangan
        "camera_invert_x": False,
        "camera_invert_y": False,
    },
    "ui": {
        "style": "glass",          # "glass" (overlay transparan tembus-klik) atau "classic" (jendela OpenCV)
        "blur": True,              # kaca buram (latar diambil dari layar; overlay disembunyikan dari tangkapan layar)
        "camera_card": True,
        "guide": True,
        "cursor_halo": True,
        "camera_width": 300,
        "quit_hotkey": "CTRL+ALT+Q",
        "guide_hotkey": "CTRL+ALT+H",
        "camera_hotkey": "CTRL+ALT+C",
    },
    "voice": {
        "enabled": True,
        "model": "models/vosk-model-small-en-us-0.15",
        "listen_seconds": 12,
        "speak": True,
        "hotkey": "CTRL+ALT+V",
        "host_word": "autocad",
        "wake": ["autocad"],
        "sleep": ["thank you", "thanks", "stop listening", "go to sleep", "that is all"],
        "fillers": [],
        "commands": [],
    },
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k.startswith("_"):
            continue  # kunci komentar
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in ("continuous", "discrete"):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalize_action(item):
    """Bentuk singkat {"cmd": ...} / {"key": ...} / {"keys": [...]} / {"internal": ...} -> dict aksi baku."""
    if "action" in item:
        return dict(item["action"])
    if "su" in item or "su_render" in item or "su_xray" in item:
        if "su" in item:        # aksi SketchUp: Sketchup.send_action("selectLineTool:")
            out = {"type": "sketchup", "op": "action", "arg": item["su"]}
        elif "su_render" in item:  # gaya tampilan: rendering_options["RenderMode"]
            out = {"type": "sketchup", "op": "render", "arg": int(item["su_render"])}
        else:
            out = {"type": "sketchup", "op": "xray", "arg": None}
        if "key" in item:       # cadangan bila jembatan belum tersambung (shortcut bawaan SketchUp)
            out["fallback_key"] = item["key"]
        return out
    if "cmd" in item:
        return {"type": "command", "cmd": item["cmd"], "cancel_first": item.get("cancel_first", True)}
    if "key" in item:
        return {"type": "key", "key": item["key"]}
    if "keys" in item:
        return {"type": "keys", "keys": list(item["keys"])}
    if "internal" in item:
        return {"type": "internal", "op": item["internal"]}
    raise ValueError("item tanpa aksi: %r" % (item,))


def validate_action(action, where, errors):
    t = action.get("type")
    if t not in ACTION_TYPES:
        errors.append("%s: tipe aksi %r tidak dikenal" % (where, t))
    elif t == "command":
        cmd = action.get("cmd", "")
        if not isinstance(cmd, str) or not cmd.strip():
            errors.append("%s: perintah kosong" % where)
    elif t == "key":
        try:
            parse_combo(action.get("key"))
        except ValueError as e:
            errors.append("%s: %s" % (where, e))
    elif t == "keys":
        for k in action.get("keys", []):
            try:
                parse_combo(k)
            except ValueError as e:
                errors.append("%s: %s" % (where, e))
    elif t == "sketchup":
        if action.get("op") not in SKETCHUP_OPS:
            errors.append("%s: operasi SketchUp %r tidak dikenal" % (where, action.get("op")))
        elif action["op"] == "action" and not re.match(r"^[A-Za-z0-9]+:$", str(action.get("arg"))):
            errors.append("%s: nama aksi SketchUp %r harus seperti 'selectLineTool:'" % (where, action.get("arg")))
        if action.get("fallback_key"):
            try:
                parse_combo(action["fallback_key"])
            except ValueError as e:
                errors.append("%s: %s" % (where, e))
    elif t == "internal" and action.get("op") not in INTERNAL_OPS:
        errors.append("%s: operasi internal %r tidak dikenal" % (where, action.get("op")))


def validate(cfg):
    errors = []
    for pose, mode in cfg["continuous"].items():
        if pose not in G.ALL_POSES:
            errors.append("continuous: pose %r tidak dikenal" % pose)
        if mode not in CONTINUOUS_MODES:
            errors.append("continuous.%s: mode %r tidak dikenal" % (pose, mode))
    for pose, item in cfg["discrete"].items():
        if pose not in G.ALL_POSES:
            errors.append("discrete: pose %r tidak dikenal" % pose)
        if pose in cfg["continuous"]:
            errors.append("pose %s dipakai di continuous dan discrete sekaligus" % pose)
        try:
            validate_action(normalize_action(item), "discrete.%s" % pose, errors)
        except ValueError as e:
            errors.append("discrete.%s: %s" % (pose, e))
    z = cfg["pointer"]["zone"]
    if not (len(z) == 4 and 0 <= z[0] < z[2] <= 1 and 0 <= z[1] < z[3] <= 1):
        errors.append("pointer.zone harus [x0, y0, x1, y1] dengan 0 <= x0 < x1 <= 1")
    th = cfg["thresholds"]
    if th["pinch_on"] >= th["pinch_off"]:
        errors.append("thresholds: pinch_on harus lebih kecil dari pinch_off (histeresis)")
    try:
        parse_combo(cfg["output"]["toggle_hotkey"])
    except ValueError as e:
        errors.append("output.toggle_hotkey: %s" % e)
    for key in ("quit_hotkey", "guide_hotkey", "camera_hotkey"):
        try:
            parse_combo(cfg["ui"][key])
        except ValueError as e:
            errors.append("ui.%s: %s" % (key, e))
    for k in ("orbit_pose", "pan_pose"):
        if cfg["two_hand"][k] not in G.ALL_POSES:
            errors.append("two_hand.%s %r tidak dikenal" % (k, cfg["two_hand"][k]))
    if cfg["host"]["name"] not in ("autocad", "sketchup"):
        errors.append("host.name harus 'autocad' atau 'sketchup'")
    for kind, mods in cfg["output"]["nav"].items():
        for m in mods:
            if m.upper() not in ("SHIFT", "CTRL", "ALT"):
                errors.append("output.nav.%s: pengubah %r harus SHIFT/CTRL/ALT" % (kind, m))
    if cfg["ui"]["style"] not in ("glass", "classic"):
        errors.append("ui.style harus 'glass' atau 'classic'")
    if cfg["pointer"].get("mode") not in ("relative", "absolute"):
        errors.append("pointer.mode harus 'relative' atau 'absolute'")
    seen = {}
    for ci, item in enumerate(cfg["voice"]["commands"]):
        where = "voice.commands[%d]" % ci
        says = item.get("say") or []
        if not says:
            errors.append("%s: 'say' kosong" % where)
        for phrase in says:
            ph = " ".join(phrase.lower().split())
            if ph in seen:
                errors.append("%s: ucapan %r sudah dipakai di %s" % (where, ph, seen[ph]))
            seen[ph] = where
        try:
            validate_action(normalize_action(item), where, errors)
        except ValueError as e:
            errors.append("%s: %s" % (where, e))
    pages = cfg["menu"]["pages"]
    if not pages:
        errors.append("menu.pages kosong")
    for pi, page in enumerate(pages):
        items = page.get("items", [])
        if not items:
            errors.append("menu.pages[%d] (%s) tanpa item" % (pi, page.get("name")))
        if len(items) > MAX_ITEMS_PER_PAGE:
            errors.append("menu.pages[%d] (%s): %d item, maks %d" % (pi, page.get("name"), len(items), MAX_ITEMS_PER_PAGE))
        for ii, item in enumerate(items):
            where = "menu.%s[%d]" % (page.get("name"), ii)
            label = item.get("label", "")
            if not label or len(label) > MAX_LABEL:
                errors.append("%s: label %r kosong atau lebih dari %d huruf" % (where, label, MAX_LABEL))
            try:
                validate_action(normalize_action(item), where, errors)
            except ValueError as e:
                errors.append("%s: %s" % (where, e))
    return errors


def load(path=None):
    path = path or CONFIG_PATH
    user = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
    cfg = _merge(DEFAULTS, user)
    errors = validate(cfg)
    if errors:
        raise ValueError("config.json tidak valid:\n  - " + "\n  - ".join(errors))
    return cfg
