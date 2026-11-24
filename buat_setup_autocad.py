"""Bangun penginstal sekali-klik TCIGestureControl-Setup.exe (Inno Setup) dari plugin yang sudah dibangun.

    .venv\\Scripts\\python.exe buat_plugin_autocad.py      # dulu: exe + bundle
    .venv\\Scripts\\python.exe buat_setup_autocad.py       # lalu: penginstal

Penginstal:
  - per pengguna, TANPA hak admin, ke %APPDATA%\\Autodesk\\ApplicationPlugins\\TCIGestureControl.bundle
    (folder plugin yang dimuat otomatis AutoCAD 2021+)
  - mematikan Gesture Control yang sedang berjalan dengan rapi sebelum menimpa / melepas
  - config.json pengguna dipertahankan saat memperbarui versi
  - tercatat di Settings > Apps (Uninstall)
Nama file tetap (tanpa versi) supaya tautan .../releases/latest/download/TCIGestureControl-Setup.exe stabil.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gesture_cad import __version__ as VERSION  # noqa: E402

OUT = os.path.join(HERE, "plugin_build")
BUNDLE = os.path.join(OUT, "TCIGestureControl.bundle")
RELEASE = os.path.join(OUT, "release")
REPO_URL = "https://github.com/naufaldm7-droid/Gesture-3D-View-"
APP_ID = "{{7C1A4E2B-5D3F-4A8E-9B6C-2E8F1D4A7C30}"  # tetap selamanya: Windows mengenali versi baru sbg pembaruan
ISCC_PATHS = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
              r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]

ISS = r"""; Dibuat oleh buat_setup_autocad.py - jangan diedit manual.
#define AppVer "{ver}"
#define RepoUrl "{url}"

[Setup]
AppId={appid}
AppName=TCI Gesture Control untuk AutoCAD
AppVersion={{#AppVer}}
AppVerName=TCI Gesture Control {{#AppVer}}
AppPublisher=TCI Gesture Control
AppPublisherURL={{#RepoUrl}}
AppSupportURL={{#RepoUrl}}/issues
AppUpdatesURL={{#RepoUrl}}/releases
VersionInfoVersion={{#AppVer}}.0
VersionInfoDescription=Penginstal TCI Gesture Control untuk AutoCAD
PrivilegesRequired=lowest
DefaultDirName={{userappdata}}\Autodesk\ApplicationPlugins\TCIGestureControl.bundle
DisableDirPage=yes
DisableProgramGroupPage=yes
UninstallDisplayName=TCI Gesture Control untuk AutoCAD
UninstallDisplayIcon={{app}}\Contents\app\GestureControl.exe
OutputDir={release}
OutputBaseFilename=TCIGestureControl-Setup
SetupIconFile={icon}
WizardImageFile={wiz_large}
WizardSmallImageFile={wiz_small}
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no

[Messages]
WelcomeLabel1=Selamat datang di TCI Gesture Control
WelcomeLabel2=Penginstal ini memasang plugin kendali gestur tangan untuk AutoCAD 2021 atau lebih baru.%n%nKamera laptop membaca tangan Anda untuk menggerakkan kursor, klik, orbit, pan, dan zoom. Gambar kamera diproses hanya di komputer ini.%n%nKlik Next untuk melanjutkan.
FinishedHeadingLabel=TCI Gesture Control sudah terpasang
FinishedLabel=Buka (atau mulai ulang) AutoCAD, lalu ketik  GK  dan Enter untuk menyalakan kamera gestur. Ketik GK lagi untuk mematikannya.%n%nJika AutoCAD menampilkan peringatan keamanan untuk TCIGestureControl.lsp, pilih "Always Load".

[Files]
Source: "{bundle}\*"; DestDir: "{{app}}"; Excludes: "\Contents\app\config.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{bundle}\Contents\app\config.json"; DestDir: "{{app}}\Contents\app"; Flags: onlyifdoesntexist

[UninstallDelete]
Type: filesandordirs; Name: "{{app}}"

[Run]
Filename: "{{#RepoUrl}}"; Description: "Buka panduan gestur di browser"; Flags: postinstall shellexec skipifsilent unchecked

[Code]
procedure StopGestureControl();
var
  ResultCode: Integer;
begin
  // minta berhenti dengan rapi (melepas tombol mouse/keyboard), lalu paksa bila masih ada
  SaveStringToFile(GetEnv('TEMP') + '\tci_gesture_cad.stop', '', False);
  Sleep(2500);
  Exec(ExpandConstant('{{sys}}\taskkill.exe'), '/im GestureControl.exe /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopGestureControl();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopGestureControl();
  Result := True;
end;
"""


def make_wizard_images(large, small):
    from PIL import Image, ImageDraw, ImageFont

    def hand(d, cx, top, s, color):
        d.rounded_rectangle([cx - 0.17 * s, top + 0.42 * s, cx + 0.17 * s, top + 0.80 * s], 0.08 * s, fill=color)
        for i, h in enumerate((0.36, 0.26, 0.28, 0.36)):
            x = cx - 0.17 * s + i * 0.09 * s
            d.rounded_rectangle([x, top + h * s, x + 0.07 * s, top + 0.55 * s], 0.035 * s, fill=color)
        d.rounded_rectangle([cx - 0.30 * s, top + 0.50 * s, cx - 0.13 * s, top + 0.60 * s], 0.04 * s, fill=color)

    w, h = 164 * 2, 314 * 2
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            t = (x / w + y / h) / 2.0
            px[x, y] = (int(10 + 20 * t), int(30 + 60 * (1 - t)), int(80 + 140 * (1 - t)))
    d = ImageDraw.Draw(im)
    hand(d, w / 2, 120, 220, (255, 255, 255))
    try:
        f1 = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguisb.ttf"), 38)
        f2 = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"), 26)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    for text, f, y in (("Gesture", f1, 400), ("Control", f1, 445), ("untuk AutoCAD", f2, 505)):
        tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, y), text, font=f, fill=(255, 255, 255))
    im.resize((164, 314), Image.LANCZOS).save(large)

    s = 58 * 4
    sm = Image.new("RGB", (s, s), (255, 255, 255))
    d = ImageDraw.Draw(sm)
    d.rounded_rectangle([8, 8, s - 8, s - 8], 44, fill=(10, 132, 255))
    hand(d, s / 2, 0, s, (255, 255, 255))
    sm.resize((58, 58), Image.LANCZOS).save(small)


def main():
    if not os.path.isdir(BUNDLE):
        raise SystemExit("Bundle belum ada. Jalankan dulu: buat_plugin_autocad.py")
    iscc = next((p for p in ISCC_PATHS if os.path.exists(p)), None)
    if not iscc:
        raise SystemExit("Inno Setup 6 belum terpasang: winget install JRSoftware.InnoSetup --scope user")
    os.makedirs(RELEASE, exist_ok=True)
    large = os.path.join(OUT, "wizard_large.bmp")
    small = os.path.join(OUT, "wizard_small.bmp")
    make_wizard_images(large, small)
    iss = os.path.join(OUT, "TCIGestureControl.iss")
    with open(iss, "w", encoding="utf-8-sig") as fh:
        fh.write(ISS.format(ver=VERSION, url=REPO_URL, appid=APP_ID, release=RELEASE, bundle=BUNDLE,
                            icon=os.path.join(OUT, "GestureControl.ico"), wiz_large=large, wiz_small=small))
    r = subprocess.run([iscc, "/Q", iss], capture_output=True, text=True)
    exe = os.path.join(RELEASE, "TCIGestureControl-Setup.exe")
    if r.returncode != 0 or not os.path.exists(exe):
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("Inno Setup gagal")
    print("Penginstal: %s (%.0f MB, versi %s)" % (exe, os.path.getsize(exe) / 1e6, VERSION))


if __name__ == "__main__":
    main()
