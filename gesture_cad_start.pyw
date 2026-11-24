r"""Peluncur tanpa konsol, dipanggil oleh perintah GESTURE / KAMERA di AutoCAD.

- Belum berjalan  -> jalankan Gesture CAD (log ke %LOCALAPPDATA%\TCI_GestureCAD\gesture_cad.log).
- Sudah berjalan  -> minta instance itu berhenti (perintah yang sama = tombol nyala/mati).
"""

import ctypes
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

MUTEX = "Local\\TCI_GestureCAD_SingleInstance"
STOP_FLAG = os.path.join(tempfile.gettempdir(), "tci_gesture_cad.stop")
ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = ctypes.c_void_p
handle = kernel32.CreateMutexW(None, False, MUTEX)
if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    open(STOP_FLAG, "w").close()   # instance lain melihat file ini dalam <0,5 detik lalu berhenti
    sys.exit(0)

logdir = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "TCI_GestureCAD")
os.makedirs(logdir, exist_ok=True)
log = open(os.path.join(logdir, "gesture_cad.log"), "w", encoding="utf-8", buffering=1)
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
