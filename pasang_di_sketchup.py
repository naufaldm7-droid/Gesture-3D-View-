r"""Pasang ekstensi "TCI Gesture Control" ke SketchUp (semua versi 20xx yang terpasang di laptop ini).

Pemakaian (dari folder aplikasi):
    .venv\Scripts\python.exe pasang_di_sketchup.py           # pasang / perbarui
    .venv\Scripts\python.exe pasang_di_sketchup.py --hapus   # lepas

Yang dipasang di %APPDATA%\SketchUp\SketchUp 20xx\SketchUp\Plugins\:
    tci_gesture_control.rb          pemuat ekstensi (berisi lokasi folder aplikasi ini)
    tci_gesture_control\main.rb     jembatan + tombol "Gesture Control (nyala/mati)"
    tci_gesture_control\icons\      ikon toolbar

Setelah memasang: buka SketchUp -> Extensions > Gesture Control (nyala/mati), atau tombol toolbar
"Gesture Control". Shortcut: Window > Preferences > Shortcuts, cari "Gesture Control".
"""

import glob
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sketchup_ext", "tci_gesture_control")
NAME = "tci_gesture_control"


def plugin_dirs():
    """Folder Plugins per versi SketchUp yang terpasang (dibuat bila SketchUp belum pernah dibuka)."""
    out = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    appdata = os.environ.get("APPDATA", "")
    for exe_dir in sorted(glob.glob(os.path.join(pf, "SketchUp", "SketchUp 20*"))):
        ver = os.path.basename(exe_dir)          # "SketchUp 2025"
        if not re.match(r"^SketchUp 20\d\d$", ver):
            continue
        out.append(os.path.join(appdata, "SketchUp", ver, "SketchUp", "Plugins"))
    for p in glob.glob(os.path.join(appdata, "SketchUp", "SketchUp 20*", "SketchUp", "Plugins")):
        if p not in out:
            out.append(p)
    return out


def loader_rb(app_dir):
    path = app_dir.replace("\\", "/").replace("'", "\\'")
    return """# Dibuat oleh pasang_di_sketchup.py - jangan diedit manual (pasang ulang untuk memperbarui).
require 'sketchup.rb'
require 'extensions.rb'

module TCI
  module GestureControl
    APP_DIR = '%s'.freeze unless defined?(APP_DIR)
    unless file_loaded?(__FILE__)
      ext = SketchupExtension.new('TCI Gesture Control', 'tci_gesture_control/main')
      ext.description = 'Kendali gestur tangan lewat kamera laptop: kursor, klik, orbit/pan/zoom, tool SketchUp.'
      ext.version = '1.0.0'
      ext.creator = 'TCI'
      Sketchup.register_extension(ext, true)
      file_loaded(__FILE__)
    end
  end
end
""" % path


def make_icons(dst):
    """Ikon tangan sederhana 24/32 px (tanpa aset luar)."""
    from PIL import Image, ImageDraw

    os.makedirs(dst, exist_ok=True)
    for size in (24, 32):
        k = 4
        s = size * k
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([s * 0.08, s * 0.08, s * 0.92, s * 0.92], s * 0.22, fill=(10, 132, 255, 255))
        cx = s * 0.5
        d.rounded_rectangle([cx - s * 0.17, s * 0.42, cx + s * 0.17, s * 0.80], s * 0.08, fill="white")  # telapak
        for i, h in enumerate((0.36, 0.26, 0.28, 0.36)):                                                # jari
            x = cx - s * 0.17 + i * s * 0.09
            d.rounded_rectangle([x, s * h, x + s * 0.07, s * 0.55], s * 0.035, fill="white")
        d.rounded_rectangle([cx - s * 0.30, s * 0.50, cx - s * 0.13, s * 0.60], s * 0.04, fill="white")  # jempol
        im.reduce(k).save(os.path.join(dst, "hand_%d.png" % size))


def install(pdir):
    os.makedirs(pdir, exist_ok=True)
    dst = os.path.join(pdir, NAME)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    make_icons(os.path.join(dst, "icons"))
    with open(os.path.join(pdir, NAME + ".rb"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(loader_rb(HERE))


def remove(pdir):
    shutil.rmtree(os.path.join(pdir, NAME), ignore_errors=True)
    try:
        os.remove(os.path.join(pdir, NAME + ".rb"))
    except OSError:
        pass


def main(argv):
    rm = "--hapus" in argv
    dirs = plugin_dirs()
    if not dirs:
        print("SketchUp tidak ditemukan (C:\\Program Files\\SketchUp\\SketchUp 20xx).")
        return 1
    if not rm:
        need = [os.path.join(HERE, ".venv", "Scripts", "pythonw.exe"), os.path.join(HERE, "gesture_cad_start.pyw"),
                os.path.join(HERE, "config_sketchup.json"), os.path.join(SRC, "main.rb")]
        missing = [p for p in need if not os.path.exists(p)]
        if missing:
            print("Belum lengkap:\n  " + "\n  ".join(missing) + "\nJalankan siapkan.bat dulu.")
            return 1
    for d in dirs:
        (remove if rm else install)(d)
        print("%s: %s" % ("Dilepas" if rm else "Terpasang", d))
    if not rm:
        print("Buka (atau mulai ulang) SketchUp -> Extensions > Gesture Control (nyala/mati).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
