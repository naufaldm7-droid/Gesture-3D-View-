r"""Peluncur tanpa konsol, dipanggil oleh perintah GESTURE / KAMERA di AutoCAD.

- Belum berjalan  -> jalankan Gesture CAD (log ke %LOCALAPPDATA%\GestureControl\gesture_cad.log).
- Sudah berjalan  -> minta instance itu berhenti (perintah yang sama = tombol nyala/mati).
"""

import ctypes
import os
import sys
import tempfile
import traceback

os.environ.setdefault("MPLBACKEND", "Agg")  # mediapipe mengimpor matplotlib; jangan sampai membuka GUI Tk
FROZEN = getattr(sys, "frozen", False)  # GestureControl.exe (PyInstaller)
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
if not FROZEN:
    sys.path.insert(0, HERE)
os.chdir(HERE)

MUTEX = "Local\\GestureControl_SingleInstance"
STOP_FLAG = os.path.join(tempfile.gettempdir(), "gesture_control.stop")
ERROR_ALREADY_EXISTS = 183
# Perintah diagnosa tidak ikut aturan nyala/mati (tidak boleh mematikan sesi yang sedang dipakai)
DIAG = ("--check", "--download-model", "--download-voice-model", "--verify-sketchup", "--bench")
diag = any(a in DIAG for a in sys.argv[1:])

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = ctypes.c_void_p
if not diag:
    handle = kernel32.CreateMutexW(None, False, MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        open(STOP_FLAG, "w").close()   # instance lain melihat file ini dalam <0,5 detik lalu berhenti
        sys.exit(0)
    # Kita pemilik kunci: bersihkan sinyal basi SEKARANG (bukan setelah kamera & UI siap), supaya perintah
    # "matikan" yang datang selagi aplikasi masih memuat tidak ikut terhapus (race pada peluncuran pertama
    # exe yang lambat karena dipindai antivirus).
    try:
        os.remove(STOP_FLAG)
    except OSError:
        pass
    os.environ["GC_LAUNCHER"] = "1"

logdir = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "GestureControl")
os.makedirs(logdir, exist_ok=True)
log = open(os.path.join(logdir, "gesture_cad_diag.log" if diag else "gesture_cad.log"), "w",
           encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = log

try:
    from gesture_cad.__main__ import main
    code = main(sys.argv[1:])
    if code:
        log.flush()
        ctypes.windll.user32.MessageBoxW(
            None, "Gesture CAD tidak bisa mulai. Lihat log:\n%s" % log.name, "Gesture CAD", 0x30)
except Exception:
    traceback.print_exc()
    log.flush()
    ctypes.windll.user32.MessageBoxW(None, "Gesture CAD berhenti karena error. Lihat log:\n%s" % log.name,
                                     "Gesture CAD", 0x10)
