r"""Pasang perintah GESTURE / KAMERA / GK di AutoCAD untuk menyalakan & mematikan Gesture CAD.

Pemakaian (dari folder 17_GESTURE_CAD):
    .venv\Scripts\python.exe pasang_di_autocad.py          # pasang / perbarui
    .venv\Scripts\python.exe pasang_di_autocad.py --hapus  # lepas lagi

Cara kerja: menambah "external command" di acad.pgp milik pengguna, tepat setelah baris EXPLORER bawaan.
Ini mekanisme bawaan AutoCAD: tanpa LISP, tanpa mengubah pengaturan keamanan. Barisnya memanggil gk.bat
(baris pendek; baris panjang ditolak parser PGP). Cadangan dibuat sekali: acad.pgp.sebelum_gesturecad.bak.
Blok ditandai sehingga bisa diperbarui / dilepas dengan aman.

Di AutoCAD: ketik GESTURE (atau KAMERA, atau GK) lalu Enter -> kamera gestur menyala.
Ketik lagi -> mati.
"""

import glob
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYW = os.path.join(HERE, ".venv", "Scripts", "pythonw.exe")
LAUNCHER = os.path.join(HERE, "gesture_cad_start.pyw")
BAT = os.path.join(HERE, "gk.bat")
COMMANDS = ("GESTURE", "KAMERA", "GK")
BEGIN = "; >>> Gesture Control (dikelola oleh pasang_di_autocad.py) >>>"
END = "; <<< Gesture Control <<<"


def pgp_files():
    root = os.path.join(os.environ.get("APPDATA", ""), "Autodesk")
    return sorted(glob.glob(os.path.join(root, "AutoCAD *", "R*", "*", "Support", "acad.pgp")))


def short_path(p):
    """Path pendek 8.3 Windows (mis. C:\\PROGRA~1\\GESTUR~1\\gk.bat) supaya baris PGP tetap pendek walau
    aplikasi ada di folder yang dalam. Kalau 8.3 dimatikan di drive itu, kembalikan path apa adanya."""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, len(buf))
        if 0 < n < len(buf) and " " not in buf.value:
            return buf.value
    except (AttributeError, OSError):
        pass
    return p


MAX_TARGET = 60  # panjang path di baris PGP yang masih aman (baris panjang/berkutip ditolak diam-diam)
RELAY = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GestureControlPGP", "gk.bat")


def pgp_target(create=False):
    """Path yang ditulis di acad.pgp. Bila gk.bat ada di folder yang dalam, pakai perantara pendek
    %LOCALAPPDATA%\\GestureControlPGP\\gk.bat yang memanggil gk.bat asli (create=True menulis perantaranya)."""
    p = short_path(BAT)
    if len(p) <= MAX_TARGET and " " not in p:
        return p
    if create:
        os.makedirs(os.path.dirname(RELAY), exist_ok=True)
        with open(RELAY, "w", encoding="ascii", errors="replace", newline="\r\n") as fh:
            fh.write('@echo off\nrem Perantara pendek untuk acad.pgp -> gk.bat asli Gesture CAD\ncall "%s" %%*\n' % BAT)
    return short_path(RELAY)


def block(target=None):
    """Baris PGP sependek mungkin: memanggil gk.bat (yang menjalankan pythonw tanpa jendela).

    Baris panjang (path pythonw + path skrip) ditolak diam-diam oleh parser acad.pgp.
    """
    target = target or pgp_target()
    lines = [BEGIN]
    for c in COMMANDS:
        lines.append("%-10s %s, 5,," % (c + ",", target))  # 5 = jangan tunggu + jendela tersembunyi
    lines.append(END)
    return "\r\n".join(lines) + "\r\n"


def insert_block(text, target=None):
    """Sisipkan blok tepat setelah baris EXPLORER bawaan (bagian external commands); kalau tidak ada,
    taruh setelah baris external command terakhir yang dikenal, atau di akhir file."""
    blk = block(target)
    lines = text.split("\r\n") if "\r\n" in text else text.split("\n")
    for anchor in ("EXPLORER,", "START,", "SHELL,"):
        for i, ln in enumerate(lines):
            if ln.upper().startswith(anchor):
                return "\r\n".join(lines[:i + 1]) + "\r\n" + blk + "\r\n".join(lines[i + 1:])
    return text.rstrip("\r\n") + "\r\n\r\n" + blk


def strip_block(text):
    if BEGIN not in text:
        return text
    i = text.index(BEGIN)
    j = text.index(END, i) + len(END)
    rest = text[j:]
    for nl in ("\r\n", "\n"):  # buang tepat satu akhir baris milik blok -> file kembali persis
        if rest.startswith(nl):
            rest = rest[len(nl):]
            break
    return text[:i] + rest


def reload_pgp():
    """Minta AutoCAD yang sedang berjalan memuat ulang acad.pgp (RE-INIT 16). Gagal = tidak apa-apa."""
    try:
        import win32com.client

        app = win32com.client.GetActiveObject("AutoCAD.Application")
        app.ActiveDocument.SendCommand('(setvar "RE-INIT" 16)\r')
        return True
    except Exception:
        return False


def main(argv):
    remove = "--hapus" in argv
    if not remove:
        for p in (PYW, LAUNCHER, BAT):
            if not os.path.exists(p):
                print("Tidak ditemukan: %s\nJalankan jalankan.bat sekali dulu untuk menyiapkan .venv." % p)
                return 1
    files = pgp_files()
    if not files:
        print("acad.pgp tidak ditemukan di %APPDATA%\\Autodesk. Buka AutoCAD sekali dulu, lalu ulangi.")
        return 1
    for f in files:
        raw = open(f, "rb").read()
        text = raw.decode("latin-1")  # pertahankan byte apa adanya
        new = strip_block(text)
        if not remove:
            backup = f + ".sebelum_gesturecad.bak"
            if not os.path.exists(backup):
                shutil.copy2(f, backup)
                print("Cadangan: %s" % backup)
            new = insert_block(new, pgp_target(create=True))
        if new != text:
            open(f, "wb").write(new.encode("latin-1"))
        print("%s: %s" % ("Dilepas" if remove else "Terpasang", f))
    if reload_pgp():
        print("AutoCAD yang terbuka sudah memuat ulang perintah.")
    else:
        print("Buka/mulai ulang AutoCAD (atau ketik REINIT > PGP file) agar perintah dikenali.")
    if not remove:
        print("Di AutoCAD ketik:  %s  lalu Enter (ketik lagi untuk mematikan)." % " / ".join(COMMANDS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
