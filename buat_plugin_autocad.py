"""Bangun plugin AutoCAD siap-pasang: GestureControl.exe (tanpa Python) di dalam GestureControl.bundle.

    .venv\\Scripts\\python.exe buat_plugin_autocad.py

Hasil:
  plugin_build/GestureControl.bundle/                  plugin Autodesk (autoloader ApplicationPlugins)
      PackageContents.xml
      Contents/GestureControl.lsp                      perintah GK / GESTURE / KAMERA
      Contents/app/GestureControl.exe (+ _internal/)       mesin gestur beku (PyInstaller)
      Contents/app/config.json, models/hand_landmarker.task, LICENSE, THIRD_PARTY_NOTICES.txt
  plugin_build/release/GestureControl-AutoCAD-v<versi>.zip   (bundle + INSTAL.bat + HAPUS.bat + BACA-SAYA.txt)
"""

import glob
import os
import shutil
import subprocess
import sys
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gesture_cad import __version__ as VERSION  # noqa: E402

OUT = os.path.join(HERE, "plugin_build")
PYI = os.path.join(OUT, "pyi", "GestureControl")
BUNDLE = os.path.join(OUT, "GestureControl.bundle")
APP = os.path.join(BUNDLE, "Contents", "app")
RELEASE = os.path.join(OUT, "release")
NS = uuid.UUID("6f1d2b4e-8a5c-4e0b-9a51-2c7e8d3f4a10")  # tetap -> ProductCode/UpgradeCode stabil antar versi
REPO_URL = "https://github.com/naufaldm7-droid/Gesture-3D-View-"

PACKAGE_XML = """<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage SchemaVersion="1.0" AutodeskProduct="AutoCAD" ProductType="Application"
    Name="Gesture Control" AppVersion="{ver}" FriendlyVersion="{ver}"
    Description="Kendali AutoCAD dengan gerakan tangan lewat kamera laptop. Perintah: GK / GESTURE / KAMERA."
    ProductCode="{{{product}}}" UpgradeCode="{{{upgrade}}}" Author="Gesture Control" HelpFile="{url}">
  <CompanyDetails Name="Gesture Control" Url="{url}" />
  <Components Description="Perintah LISP nyala/mati">
    <RuntimeRequirements OS="Win64" Platform="AutoCAD*" SeriesMin="R24.0" />
    <ComponentEntry AppName="GestureControl" Version="{ver}" ModuleName="./Contents/GestureControl.lsp"
        AppDescription="Perintah GK / GESTURE / KAMERA" LoadOnAutoCADStartup="True" PerDocument="True" />
  </Components>
</ApplicationPackage>
"""

INSTALL_BAT = r"""@echo off
rem Pasang Gesture Control untuk AutoCAD (per pengguna, tanpa hak admin).
set "DEST=%APPDATA%\Autodesk\ApplicationPlugins\GestureControl.bundle"
tasklist /fi "imagename eq GestureControl.exe" | find /i "GestureControl.exe" >nul && (
  echo Gesture Control sedang berjalan. Matikan dulu ^(ketik GK di AutoCAD atau tombol Tutup^), lalu ulangi.
  pause
  exit /b 1
)
robocopy "%~dp0GestureControl.bundle" "%DEST%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo GAGAL menyalin ke %DEST%
  pause
  exit /b 1
)
echo Terpasang di: %DEST%
echo.
echo Buka (atau mulai ulang) AutoCAD, lalu ketik  GK  dan Enter untuk menyalakan kamera gestur.
pause
"""

UNINSTALL_BAT = r"""@echo off
rem Lepas Gesture Control dari AutoCAD.
set "DEST=%APPDATA%\Autodesk\ApplicationPlugins\GestureControl.bundle"
taskkill /im GestureControl.exe >nul 2>nul
if exist "%DEST%" rmdir /s /q "%DEST%"
echo Gesture Control sudah dilepas. Mulai ulang AutoCAD.
pause
"""

README_TXT = """Gesture Control untuk AutoCAD  v{ver}
=========================================

Kendalikan AutoCAD dengan gerakan tangan lewat kamera laptop. Tidak perlu Python.

PASANG
  1. Ekstrak ZIP ini.
  2. Klik dua kali INSTAL.bat.
  3. Buka (atau mulai ulang) AutoCAD 2021 atau lebih baru.
  4. Ketik GK lalu Enter -> kamera gestur menyala. Ketik GK lagi -> mati.
     (GESTURE dan KAMERA juga bisa.)

Pertama kali dijalankan, Windows SmartScreen mungkin menampilkan "Windows protected your PC" karena program
belum bertanda tangan digital: klik "More info" -> "Run anyway".

GESTUR UTAMA
  Telunjuk              : kursor (pelan = presisi, diam = terkunci)
  Jepit lalu lepas      : klik        | jepit lalu geser : drag | jepit diam : klik kanan
  Kepal / dua jari / tiga jari : orbit / pan / zoom
  Dua kepalan           : putar tampilan 3D, rentangkan tangan = zoom
  Dua cubitan           : geser tampilan
  Jempol atas / bawah / telunjuk+kelingking (tahan) : Enter / Undo / Esc
  Jempol+kelingking (tahan) : menu perintah
  Tutup : tombol Tutup di atas kartu kamera, Ctrl+Alt+Q, atau tutup AutoCAD.

MENYETEL
  Edit config.json di:
  %APPDATA%\\Autodesk\\ApplicationPlugins\\GestureControl.bundle\\Contents\\app\\config.json
  (lalu GK dua kali). Panduan: {url}

LEPAS
  Klik dua kali HAPUS.bat.

PRIVASI
  Gambar kamera diproses hanya di laptop ini; tidak ada yang dikirim ke internet.
"""

NOTICES = """Pihak ketiga yang dibundel di GestureControl.exe (lisensi masing-masing berlaku):
- MediaPipe + model hand_landmarker.task  - Apache License 2.0 (Google)
- OpenCV (opencv-contrib-python)          - Apache License 2.0
- NumPy                                   - BSD-3-Clause
- Pillow                                  - MIT-CMU (HPND)
- Matplotlib (dimuat MediaPipe)           - Matplotlib License (PSF-based)
- pywin32                                 - PSF License
- Python 3.12                             - PSF License
Font Artifakt Element (Autodesk) TIDAK dibundel; hanya dibaca dari instalasi Autodesk pengguna bila ada.
"""


def make_icon(path):
    from PIL import Image, ImageDraw

    s = 256
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([12, 12, s - 12, s - 12], 56, fill=(10, 132, 255, 255))
    cx = s // 2
    d.rounded_rectangle([cx - 44, 108, cx + 44, 205], 22, fill="white")
    for i, top in enumerate((92, 66, 72, 92)):
        x = cx - 44 + i * 23
        d.rounded_rectangle([x, top, x + 18, 140], 9, fill="white")
    d.rounded_rectangle([cx - 78, 128, cx - 34, 154], 12, fill="white")
    im.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def build_exe():
    icon = os.path.join(OUT, "GestureControl.ico")
    os.makedirs(OUT, exist_ok=True)
    make_icon(icon)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "GestureControl",
           "--icon", icon, "--paths", HERE, "--distpath", os.path.join(OUT, "pyi"),
           "--workpath", os.path.join(OUT, "work"), "--specpath", OUT, "--collect-all", "mediapipe",
           "--exclude-module", "tkinter", "--exclude-module", "vosk", "--exclude-module", "pytest",
           "--exclude-module", "sounddevice", os.path.join(HERE, "gesture_cad_start.pyw")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(os.path.join(PYI, "GestureControl.exe")):
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit("PyInstaller gagal")
    for dll in glob.glob(os.path.join(PYI, "_internal", "cv2", "opencv_videoio_ffmpeg*.dll")):
        os.remove(dll)  # hanya untuk berkas video; webcam lewat DirectShow tidak memakainya


def assemble():
    if os.path.isdir(BUNDLE):
        shutil.rmtree(BUNDLE)
    shutil.copytree(PYI, APP)
    shutil.copy2(os.path.join(HERE, "config.json"), os.path.join(APP, "config.json"))
    os.makedirs(os.path.join(APP, "models"))
    shutil.copy2(os.path.join(HERE, "models", "hand_landmarker.task"), os.path.join(APP, "models"))
    for lic in (os.path.join(HERE, "LICENSE"), os.path.join(HERE, "dist", "repo", "gesture-control", "LICENSE")):
        if os.path.exists(lic):  # repo publik: LICENSE di akar; folder kerja: salinan repo
            shutil.copy2(lic, os.path.join(APP, "LICENSE"))
            break
    with open(os.path.join(APP, "THIRD_PARTY_NOTICES.txt"), "w", encoding="utf-8") as fh:
        fh.write(NOTICES)
    shutil.copy2(os.path.join(HERE, "plugin_src", "autocad", "GestureControl.lsp"),
                 os.path.join(BUNDLE, "Contents", "GestureControl.lsp"))
    xml = PACKAGE_XML.format(ver=VERSION, url=REPO_URL, product=str(uuid.uuid5(NS, "product-" + VERSION)).upper(),
                             upgrade=str(uuid.uuid5(NS, "upgrade")).upper())
    with open(os.path.join(BUNDLE, "PackageContents.xml"), "w", encoding="utf-8") as fh:
        fh.write(xml)


def release():
    os.makedirs(RELEASE, exist_ok=True)
    out = os.path.join(RELEASE, "GestureControl-AutoCAD-v%s.zip" % VERSION)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in glob.glob(os.path.join(BUNDLE, "**", "*"), recursive=True):
            if os.path.isfile(p):
                z.write(p, os.path.relpath(p, OUT))
        z.writestr("INSTAL.bat", INSTALL_BAT.replace("\n", "\r\n"))
        z.writestr("HAPUS.bat", UNINSTALL_BAT.replace("\n", "\r\n"))
        z.writestr("BACA-SAYA.txt", README_TXT.format(ver=VERSION, url=REPO_URL).replace("\n", "\r\n"))
    return out


def size_mb(path):
    return sum(os.path.getsize(p) for p in glob.glob(os.path.join(path, "**", "*"), recursive=True)
               if os.path.isfile(p)) / 1e6


if __name__ == "__main__":
    if "--skip-exe" not in sys.argv:
        build_exe()
    assemble()
    z = release()
    print("Bundle : %s (%.0f MB)" % (BUNDLE, size_mb(BUNDLE)))
    print("Rilis  : %s (%.0f MB)" % (z, os.path.getsize(z) / 1e6))
