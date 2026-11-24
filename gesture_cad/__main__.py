"""Titik masuk:  python -m gesture_cad [--simulate] [--check] [--download-model] ...

Jalankan dari folder 17_GESTURE_CAD (atau pakai jalankan.bat).
"""

import argparse
import os
import sys
import tempfile
import threading
import time

from . import config as CFG
from .keys import parse_combo

WINDOW = "Gesture CAD"


def _p(msg):
    print(msg, flush=True)


DARK = 12.0       # kecerahan rata-rata (0..255) di bawah ini = gambar hitam (penutup kamera / mode privasi)
SLOW_FPS = 8.0
STATIC = 0.15     # beda rata-rata antar-frame di bawah ini = gambar diam total (kamera virtual, bukan sensor)


def _open_one(cfg, idx):
    import cv2

    cc = cfg["camera"]
    backends = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "any": cv2.CAP_ANY}
    cap = cv2.VideoCapture(idx, backends.get(cc.get("backend", "dshow"), cv2.CAP_ANY))
    if not cap.isOpened():
        cap.release()
        return None
    if cc.get("fourcc"):  # MJPG: banyak webcam laptop hanya ~17-22 fps dalam format bawaan (YUY2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*cc["fourcc"]))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cc["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cc["height"])
    cap.set(cv2.CAP_PROP_FPS, cc["fps"])
    return cap


def _probe(cap, seconds=0.8):
    """(fps, kecerahan rata-rata, gerak) beberapa frame pertama.

    gerak = beda rata-rata antar-frame. Sensor kamera asli selalu berderau (>~0.5) walau pemandangan diam;
    kamera virtual (mis. "Windows Virtual Camera" yang menampilkan logo) persis 0.
    """
    t0, n, br, diff, prev = time.monotonic(), 0, 0.0, [], None
    while time.monotonic() - t0 < seconds:
        ok, f = cap.read()
        if ok and f is not None:
            n += 1
            small = f[::8, ::8].astype("float32")
            br += float(small.mean())
            if prev is not None:
                diff.append(float(abs(small - prev).mean()))
            prev = small
    return n / seconds, (br / n if n else 0.0), (sum(diff) / len(diff) if diff else 0.0)


def open_camera(cfg, index=None, log=None):
    """Buka kamera. camera.index = "auto": pakai kamera pertama yang mengirim gambar terang & cukup cepat.

    Kenapa: laptop sering punya dua kamera (bawaan + USB). Kamera bawaan Lenovo dengan penutup/mode privasi
    aktif tetap "terbuka" tetapi hanya mengirim gambar hitam ~1 fps, sehingga gestur terasa macet.
    """
    want = cfg["camera"]["index"] if index is None else index
    if want != "auto":
        cap = _open_one(cfg, int(want))
        if cap is None:
            raise RuntimeError(
                "Kamera %s tidak bisa dibuka. Tutup aplikasi lain yang memakai kamera (Zoom/Teams), "
                "cek Settings > Privacy > Camera, atau coba --camera 1." % want)
        return cap
    tried = []
    for idx in range(int(cfg["camera"].get("auto_max", 3))):
        cap = _open_one(cfg, idx)
        if cap is None:
            continue
        fps, br, motion = _probe(cap)
        tried.append((idx, fps, br, motion))
        if log:
            log("Kamera %d: %.0f fps, kecerahan %.0f, gerak %.2f%s" % (idx, fps, br, motion,
                                                                     " (gambar diam: kamera virtual?)" if motion < STATIC else ""))
        if br >= DARK and fps >= SLOW_FPS and motion >= STATIC:
            return cap
        cap.release()
    if not tried:
        raise RuntimeError("Tidak ada kamera yang bisa dibuka. Sambungkan webcam atau cek Settings > Privacy > Camera.")
    # pakai yang terbaik walau kurang ideal: kamera asli (bergerak) dulu, lalu terang, lalu cepat
    best = max(tried, key=lambda x: (x[3] >= STATIC, x[2] >= DARK, x[1]))
    if log:
        log("Tidak ada kamera yang terang & lancar; memakai kamera %d (overlay akan memberi peringatan)." % best[0])
    return _open_one(cfg, best[0])


def doctor(cfg):
    """Cek kesiapan tanpa membuka kamera. Kembalikan jumlah masalah kritis."""
    from .tracker import model_path

    bad = 0
    _p("config.json             : OK (%d halaman menu, %d gestur sekali-tembak)"
       % (len(cfg["menu"]["pages"]), len(cfg["discrete"])))
    for mod, why in (("cv2", "opencv-python"), ("mediapipe", "mediapipe"), ("numpy", "numpy")):
        try:
            __import__(mod)
            _p("%-24s: OK" % mod)
        except ImportError:
            bad += 1
            _p("%-24s: BELUM ADA -> pip install %s" % (mod, why))
    mp = model_path(cfg)
    if os.path.exists(mp):
        _p("model tangan            : OK (%.1f MB)" % (os.path.getsize(mp) / 1e6))
    else:
        bad += 1
        _p("model tangan            : BELUM ADA -> python -m gesture_cad --download-model")
    try:
        import vosk  # noqa: F401
        vm = cfg["voice"]["model"]
        vm = vm if os.path.isabs(vm) else os.path.join(CFG.APP_DIR, vm)
        _p("suara (opsional)        : %s" % ("OK" if os.path.isdir(vm) else
                                             "model belum ada -> --download-voice-model"))
    except ImportError:
        _p("suara (opsional)        : tidak aktif (pip install vosk, lalu --download-voice-model)")
    if cfg["host"]["name"] == "sketchup":
        return bad + doctor_sketchup(cfg)
    if getattr(sys, "frozen", False):
        _p("perintah GESTURE/KAMERA : dari plugin TCIGestureControl.bundle (ApplicationPlugins)")
    else:
        bad += _doctor_pgp()
    return bad + _doctor_autocad(cfg)


def _doctor_pgp():
    try:
        sys.path.insert(0, CFG.APP_DIR)
        import pasang_di_autocad as PG
        pg = PG.pgp_files()
        ok = [f for f in pg if PG.BEGIN in open(f, "rb").read().decode("latin-1")]
        _p("perintah GESTURE/KAMERA : %s" % ("terpasang di AutoCAD" if ok else
                                             "belum -> python pasang_di_autocad.py"))
    except Exception as e:
        _p("perintah GESTURE/KAMERA : tidak bisa dicek (%s)" % e)
    return 0


def _doctor_autocad(cfg):
    bad = 0
    try:
        import win32com.client  # noqa: F401
        _p("pywin32 (COM)           : OK")
    except ImportError:
        _p("pywin32 (COM)           : tidak ada -> perintah diketik lewat keyboard (tetap jalan)")
        return bad
    try:
        import winreg
        found = []
        for pid in cfg["output"]["progids"]:
            try:
                winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, pid))
                found.append(pid)
            except OSError:
                pass
        _p("AutoCAD terdaftar       : %s" % (", ".join(found) if found else "TIDAK ditemukan"))
    except ImportError:
        pass
    try:
        import win32com.client
        app = None
        for pid in cfg["output"]["progids"]:
            try:
                app = win32com.client.GetActiveObject(pid)
                break
            except Exception:
                continue
        _p("AutoCAD berjalan        : %s" % ("ya, versi %s" % app.Version if app else
                                              "tidak (buka AutoCAD dulu sebelum mulai)"))
    except Exception as e:
        _p("AutoCAD berjalan        : tidak bisa dicek (%s)" % e)
    return bad


def doctor_sketchup(cfg):
    """Cek ekstensi SketchUp & jembatan Ruby. --check tidak menjalankan aksi apa pun di SketchUp."""
    bad = 0
    try:
        sys.path.insert(0, CFG.APP_DIR)
        import pasang_di_sketchup as PS
        dirs = PS.plugin_dirs()
        done = [d for d in dirs if os.path.exists(os.path.join(d, PS.NAME + ".rb"))]
        _p("ekstensi SketchUp       : %s" % ("terpasang di %d versi" % len(done) if done else
                                            "belum -> python pasang_di_sketchup.py"))
        if not dirs:
            bad += 1
            _p("SketchUp                : TIDAK ditemukan di Program Files")
    except Exception as e:
        _p("ekstensi SketchUp       : tidak bisa dicek (%s)" % e)
    from .sketchup import SketchUpLink
    link = SketchUpLink(cfg["host"]["bridge_port"], cfg, log=lambda s: None)
    for _ in range(30):
        if link.connected:
            break
        time.sleep(0.1)
    _p("jembatan SketchUp       : %s" % (link.status if link.connected else
                                         "belum tersambung (buka SketchUp; ekstensi aktif saat SketchUp mulai)"))
    link.stop()
    return bad


def verify_sketchup(cfg):
    """Coba setiap aksi 'su' yang AMAN dari profil (pemilih tool & tampilan) lewat jembatan; laporkan yang
    ditolak SketchUp. Aksi yang mengubah model (hapus, tempel, potong, undo/redo) dilewati."""
    from .sketchup import SketchUpLink

    unsafe = {"editDelete:", "editPaste:", "editCut:", "editUndo:", "editRedo:", "editHide:"}
    names = []
    for page in cfg["menu"]["pages"]:
        for it in page["items"]:
            if "su" in it and it["su"] not in names:
                names.append(it["su"])
    for it in cfg["voice"]["commands"]:
        if "su" in it and it["su"] not in names:
            names.append(it["su"])
    link = SketchUpLink(cfg["host"]["bridge_port"], cfg, log=lambda s: None)
    for _ in range(40):
        if link.connected:
            break
        time.sleep(0.1)
    if not link.connected:
        _p("Jembatan SketchUp belum tersambung. Buka SketchUp dulu (ekstensi TCI Gesture Control aktif).")
        link.stop()
        return 1
    _p("SketchUp %s. Menguji %d aksi aman (tool & tampilan akan berganti-ganti sebentar)..."
       % (link.version, len([n for n in names if n not in unsafe])))
    failed = []
    for n in names:
        if n in unsafe:
            _p("  lewati (mengubah model): %s" % n)
            continue
        r = link.request("action", n, timeout=2.0)
        ok = bool(r and r.get("ok"))
        _p("  %-26s %s" % (n, "OK" if ok else "DITOLAK %s" % ((r or {}).get("error", "")),))
        if not ok:
            failed.append(n)
        time.sleep(0.15)
    link.request("action", "selectSelectionTool:", timeout=2.0)
    link.stop()
    _p("Hasil: %d OK, %d ditolak%s" % (len(names) - len(failed) - len([n for n in names if n in unsafe]),
                                       len(failed), (": " + ", ".join(failed)) if failed else ""))
    return 1 if failed else 0


STOP_FLAG = os.path.join(tempfile.gettempdir(), "tci_gesture_cad.stop")


class FrameGrabber(threading.Thread):
    """Membaca kamera terus-menerus dan hanya menyimpan frame TERBARU (tidak ada antrean basi)."""

    def __init__(self, cap):
        threading.Thread.__init__(self, name="camera", daemon=True)
        self.cap = cap
        self.cond = threading.Condition()
        self.frame = None
        self.seq = 0
        self.error = None
        self.stopping = False
        self.started = time.monotonic()
        self.stamps = []        # waktu frame 2 detik terakhir -> fps nyata kamera
        self.brightness = 128.0  # rata-rata bergerak (dicek tiap 10 frame, murah)
        self.motion = 1.0        # beda antar-frame (0 = gambar diam: kamera virtual / bukan sensor)
        self._prev_small = None

    def health(self):
        """(fps kamera 2 s terakhir, kecerahan) untuk peringatan di overlay."""
        now = time.monotonic()
        recent = [s for s in self.stamps if now - s <= 2.0]
        return len(recent) / 2.0, self.brightness

    def run(self):
        fails = 0
        while not self.stopping:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                fails += 1
                if fails > 60:
                    self.error = "Kamera berhenti mengirim gambar."
                    break
                time.sleep(0.01)
                continue
            fails = 0
            now = time.monotonic()
            self.stamps = [s for s in self.stamps if now - s <= 2.0] + [now]
            if self.seq % 10 == 0:
                small = frame[::16, ::16].astype("float32")
                self.brightness = 0.7 * self.brightness + 0.3 * float(small.mean())
                if self._prev_small is not None and self._prev_small.shape == small.shape:
                    self.motion = 0.7 * self.motion + 0.3 * float(abs(small - self._prev_small).mean())
                self._prev_small = small
            with self.cond:
                self.frame = frame
                self.seq += 1
                self.cond.notify_all()
        with self.cond:
            self.cond.notify_all()

    def wait_next(self, last_seq, timeout=1.0):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq or self.error or self.stopping, timeout)
            return self.seq, self.frame


class TrackWorker(threading.Thread):
    """MediaPipe di thread sendiri, selalu pada frame kamera terbaru; UI menggambar secara paralel."""

    def __init__(self, cap, tracker):
        threading.Thread.__init__(self, name="tracker", daemon=True)
        self.grabber = FrameGrabber(cap)
        self.tracker = tracker
        self.cond = threading.Condition()
        self.latest = None
        self.seq = 0
        self.error = None
        self.stopping = False
        self.detect_s = 0.0  # total waktu deteksi (untuk --bench)

    def run(self):
        self.grabber.start()
        gseq = 0
        while not self.stopping:
            gseq, frame = self.grabber.wait_next(gseq)
            if self.grabber.error:
                self.error = self.grabber.error
                break
            if frame is None:
                continue
            t = time.monotonic()
            try:
                t0 = time.perf_counter()
                hands = self.tracker.process(frame, t)
                self.detect_s += time.perf_counter() - t0
            except Exception as e:  # jangan biarkan thread mati diam-diam
                self.error = "Pelacak tangan error: %s" % e
                break
            with self.cond:
                self.latest = (frame, hands, t)
                self.seq += 1
                self.cond.notify_all()
        with self.cond:
            self.cond.notify_all()

    def wait_next(self, last_seq, timeout=1.0):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq or self.error or self.stopping, timeout)
            return self.seq, self.latest

    def stop(self):
        self.stopping = True
        self.grabber.stopping = True
        self.join(timeout=2.0)
        self.grabber.join(timeout=2.0)


def camera_warning(grabber):
    """None | "dark" | "static" | "slow:N" (setelah 2,5 detik pertama, supaya tidak berkedip saat menyala)."""
    if time.monotonic() - grabber.started < 2.5:
        return None
    fps, br = grabber.health()
    if br < DARK:
        return "dark"
    if getattr(grabber, "motion", 1.0) < STATIC:
        return "static"
    if fps < SLOW_FPS:
        return "slow:%d" % int(round(fps))
    return None


def _status(acad, act, voice, fps, args, rect=None, cam_warn=None):
    return {
        "cam_warn": cam_warn,
        "host_label": act.host_label,
        "two": act.two_label,
        "rect": rect,
        "acad_ok": bool(acad is not None and acad.connected) or args.simulate,
        "gate_ok": act.fg_ok,
        "voice": voice.status() if voice is not None else {"state": "off"},
        "fps": fps,
    }


def run(cfg, args):
    import cv2

    from . import hud
    from .actuator import Actuator, SimInput
    from .autocad import AutoCADLink
    from .controller import Controller
    from .tracker import HandTracker
    from .winapi import WinInput, set_dpi_aware

    set_dpi_aware()
    style = args.ui or cfg["ui"]["style"]
    probe = WinInput()
    win = SimInput(log=_p) if args.simulate else probe
    act = Actuator(cfg, win, None, gate=not args.any_window, log=_p)
    acad = None
    host = cfg["host"]["name"]
    if host == "autocad" and not args.no_com and not args.simulate:
        acad = AutoCADLink(cfg["output"]["progids"], fallback=act.type_command, log=_p)
        act.acad = acad
    elif host == "sketchup" and not args.simulate:
        from .sketchup import SketchUpLink
        acad = SketchUpLink(cfg["host"]["bridge_port"], cfg, log=_p)  # punya .connected/.status/.stop()
        act.bridge = acad

    tracker = HandTracker(cfg)
    cap = open_camera(cfg, args.camera, log=_p)
    ctl = Controller(cfg)
    if args.start_paused and ctl.armed:
        ctl.toggle_arm(time.monotonic(), [])

    ui = None
    if style == "glass":
        from .glassui import GlassUI
        ui = GlassUI(cfg, log=_p)
        ui.prewarm(ctl.menu)

    voice = None
    if cfg["voice"]["enabled"] and not args.no_voice:
        try:
            from .voice import VoiceAssistant
            voice = VoiceAssistant(cfg, log=_p)
            _p("Suara siap (offline). Ucapkan: '%s please help me' lalu perintah."
               % cfg["voice"]["host_word"].title())
        except Exception as e:  # vosk/model/mikrofon tidak ada: tetap jalan dengan tangan saja
            _p("Suara tidak aktif: %s" % e)

    uc = cfg["ui"]
    hotkeys = {"arm": cfg["output"]["toggle_hotkey"], "quit": uc["quit_hotkey"], "guide": uc["guide_hotkey"],
               "camera": uc["camera_hotkey"], "voice": cfg["voice"]["hotkey"]}
    hotkeys = {k: parse_combo(v) for k, v in hotkeys.items()}
    held = {k: False for k in hotkeys}
    show_help = bool(cfg["hud"]["show_help"])
    mirror = bool(cfg["camera"]["mirror"])
    targets = [n.lower() for n in cfg["output"]["target_processes"]]
    if not os.environ.get("TCI_GC_LAUNCHER"):  # lewat peluncur: sinyal basi sudah dibersihkan saat kunci diambil
        try:
            os.remove(STOP_FLAG)
        except OSError:
            pass

    _p("Gesture CAD berjalan (%s, host %s). %s. Keluar: tombol Tutup, Ctrl+Alt+Q, atau perintah nyala/mati di %s."
       % (style, act.host_label, "MODE SIMULASI (tidak ada input dikirim)" if args.simulate else
          "Input dikirim ke %s" % act.host_label, act.host_label))

    if ui is None:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    placed = False
    activated = False
    fps, t_prev, last_flag, seq = 0.0, time.monotonic(), 0.0, 0
    acad_rect = None
    acad_seen = False
    worker = TrackWorker(cap, tracker)
    worker.start()
    t_start, frames = time.monotonic(), 0
    try:
        while True:
            seq, item = worker.wait_next(seq)
            if worker.error:
                raise RuntimeError(worker.error)
            if item is None:
                continue
            frame, hands, _t_cap = item
            t = time.monotonic()
            frames += 1
            if args.bench and t - t_start >= args.bench:
                el = t - t_start
                _p("Bench: %d frame dalam %.1f s = %.1f fps (UI %s) | kamera %.1f fps | deteksi rata2 %.0f ms"
                   % (frames, el, frames / el, style, worker.grabber.seq / el,
                      1000.0 * worker.detect_s / max(worker.seq, 1)))
                break

            intents = []
            pressed = []
            for name, vks in hotkeys.items():
                down = all(probe.key_down_now(vk) for vk in vks)
                if down and not held[name]:
                    pressed.append(name)
                held[name] = down
            if "quit" in pressed:
                break
            if "arm" in pressed:
                ctl.toggle_arm(t, intents)
            if "guide" in pressed:
                if ui is not None:
                    ui.toggle_guide()
                show_help = not show_help
            if "camera" in pressed and ui is not None:
                ui.toggle_camera()
            if "voice" in pressed and voice is not None:
                ctl.toast("SUARA AKTIF" if voice.toggle() else "SUARA MATI", t)
            if voice is not None:
                for action, label in voice.poll():
                    intents += ctl.external(action, label, t)
            intents += ctl.update(hands, t)
            act.apply(intents)
            if ctl.quit_requested:
                break
            if t - last_flag > 0.5:
                last_flag = t
                if os.path.exists(STOP_FLAG):
                    _p("Diminta berhenti dari AutoCAD (perintah GESTURE).")
                    break
                host_hwnd = (acad.hwnd if (acad is not None and acad.hwnd) else act.target_hwnd)
                if host_hwnd and not args.simulate:
                    acad_seen = True
                    if not probe.window_alive(host_hwnd):
                        _p("%s ditutup -> Gesture CAD ikut berhenti." % act.host_label)
                        break

            if (acad is not None and getattr(acad, "hwnd", None) and not activated
                    and cfg["output"]["activate_autocad_on_start"]):
                probe.activate(acad.hwnd)
                activated = True

            dt = t - t_prev
            t_prev = t
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

            shown = cv2.flip(frame, 1) if mirror else frame.copy()
            if ui is not None:
                if act.fg_name in targets:
                    acad_rect = act.rect  # overlay menempel ke jendela AutoCAD (terakhir terlihat)
                clicks, act.clicks = act.clicks, []
                ui.frame(shown, hands, ctl.view(),
                         _status(acad, act, voice, fps, args, acad_rect, camera_warning(worker.grabber)),
                         probe.cursor(), clicks, t)
                req = ui.take_request()
                if req == "quit":
                    _p("Ditutup lewat tombol Tutup.")
                    break
                if req == "pause":
                    extra = []
                    ctl.toggle_arm(t, extra)
                    act.apply(extra)
                continue

            # ---- tampilan classic (jendela OpenCV)
            if acad is not None:
                acad_status = acad.status
            elif args.simulate:
                acad_status = "Simulasi: tanpa AutoCAD"
            else:
                acad_status = "COM mati: perintah diketik"
            if not act.gate:
                gate_text = "Gerbang jendela: mati"
            elif act.fg_name in targets:
                gate_text = "Target: AutoCAD di depan"
            else:
                gate_text = "Ditahan: %s di depan" % (act.fg_name or "?")
            img = hud.render(shown, hands, ctl.view(), acad_status, gate_text, fps, show_help,
                             cfg["timing"]["hold_ms"])
            cv2.imshow(WINDOW, img)
            if not placed:
                placed = True
                _place_window(cv2, probe, img, cfg)
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), ord("Q"), 27):
                break
            if k in (ord("h"), ord("H")):
                show_help = not show_help
            if k == ord(" "):
                extra = []
                ctl.toggle_arm(t, extra)
                act.apply(extra)
            try:
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    finally:
        worker.stop()
        act.release_all()
        cap.release()
        tracker.close()
        if acad is not None:
            acad.stop()
        if voice is not None:
            voice.stop()
        if ui is not None:
            ui.close()
        else:
            cv2.destroyAllWindows()
        try:
            os.remove(STOP_FLAG)
        except OSError:
            pass
        _p("Gesture CAD berhenti; semua tombol mouse/keyboard sudah dilepas.")


def _place_window(cv2, probe, img, cfg):
    hc = cfg["hud"]
    scale = float(hc.get("scale", 1.0))
    w, h = int(img.shape[1] * scale), int(img.shape[0] * scale)
    cv2.resizeWindow(WINDOW, w, h)
    sx0, sy0, sx1, sy1 = probe.screen_rect()
    corner = hc.get("corner", "bottom-right")
    x = sx1 - w - 20 if "right" in corner else sx0 + 20
    y = sy1 - h - 80 if "bottom" in corner else sy0 + 40
    cv2.moveWindow(WINDOW, max(0, x), max(0, y))
    prop = getattr(cv2, "WND_PROP_TOPMOST", None)
    if hc.get("topmost", True) and prop is not None:
        try:
            cv2.setWindowProperty(WINDOW, prop, 1)
        except cv2.error:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gesture_cad",
                                 description="Operasikan AutoCAD 3D dengan gerakan tangan lewat kamera laptop.")
    ap.add_argument("--config", help="path config.json (bawaan: 17_GESTURE_CAD/config.json)")
    ap.add_argument("--camera", type=int, help="indeks kamera (0 = kamera laptop)")
    ap.add_argument("--simulate", action="store_true", help="jangan kirim input apa pun; hanya tampilkan & catat")
    ap.add_argument("--any-window", action="store_true", help="kirim input walau AutoCAD tidak di depan (hati-hati)")
    ap.add_argument("--no-com", action="store_true", help="jangan pakai COM; perintah diketik lewat keyboard")
    ap.add_argument("--start-paused", action="store_true", help="mulai dalam keadaan dijeda")
    ap.add_argument("--check", action="store_true", help="cek kesiapan (config, model, AutoCAD) lalu keluar")
    ap.add_argument("--download-model", action="store_true", help="unduh model tangan MediaPipe (~7.5 MB)")
    ap.add_argument("--download-voice-model", action="store_true",
                    help="unduh model suara Vosk bahasa Inggris kecil (~40 MB, opsional)")
    ap.add_argument("--ui", choices=("glass", "classic"), help="gaya tampilan (bawaan dari config ui.style)")
    ap.add_argument("--no-voice", action="store_true", help="matikan asisten suara")
    ap.add_argument("--bench", type=float, metavar="DETIK", help="jalan sekian detik lalu cetak rata-rata fps")
    ap.add_argument("--verify-sketchup", action="store_true",
                    help="uji semua aksi tool/tampilan SketchUp lewat jembatan (SketchUp harus terbuka)")
    ap.add_argument("--no-blur", action="store_true",
                    help="kaca tanpa blur latar (overlay jadi ikut terlihat di tangkapan layar/rekaman)")
    args = ap.parse_args(argv)

    try:
        cfg = CFG.load(args.config)
    except ValueError as e:
        _p(str(e))
        return 2

    if args.no_blur:
        cfg["ui"]["blur"] = False
    if args.download_voice_model:
        from .voice import download_voice_model
        download_voice_model(cfg, _p)
        return 0
    if args.download_model:
        from .tracker import download_model
        download_model(cfg, _p)
        return 0
    if args.verify_sketchup:
        return verify_sketchup(cfg)
    if args.check:
        bad = doctor(cfg)
        _p("SIAP" if bad == 0 else "%d masalah perlu dibereskan" % bad)
        return 0 if bad == 0 else 1
    try:
        run(cfg, args)
    except (RuntimeError, FileNotFoundError) as e:
        _p("GAGAL: %s" % e)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
