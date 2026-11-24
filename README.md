# TCI Gesture Control untuk AutoCAD

Kendalikan **AutoCAD** dengan **gerakan tangan di depan kamera laptop**: kursor, klik, putar, geser, dan zoom
model 3D, serta menu perintah, tanpa menyentuh mouse.

*Hand-gesture control for AutoCAD on Windows using your laptop webcam (MediaPipe). Installs as a regular
Autodesk plugin, no Python needed. Everything runs locally; documentation is in Indonesian.*

- **Kursor presisi seperti mouse:** gerak pelan = presisi, gerak cepat = jauh, tangan diam = kursor terkunci.
- **Klik dengan jepitan:** jepit lalu lepas = klik, jepit lalu geser = drag, jepit diam = klik kanan.
- **Navigasi satu tangan:** ✊ orbit, ✌ pan, 🤟 zoom.
- **Dua tangan memegang tampilan 3D:** ✊✊ putar, 🤏🤏 geser, rentangkan/rapatkan = zoom halus.
- **Menu kaca 7 halaman:** 2D, SOLID, EDIT, UBAH, VIEW, UMUM, WINDOW.
- **Overlay transparan** di atas AutoCAD yang tembus-klik, plus tombol Jeda dan Tutup.
- **Nyala/mati dari AutoCAD:** ketik `GK` (atau `GESTURE` / `KAMERA`).

> **Privasi:** gambar kamera diproses **hanya di laptop Anda**. Tidak ada yang dikirim ke internet.

## Pasang (pengguna)

**[⬇ Download TCIGestureControl-Setup.exe](../../releases/latest/download/TCIGestureControl-Setup.exe)**
(~80 MB). Halaman unduhan juga ada di GitHub Pages repo ini.

1. Jalankan `TCIGestureControl-Setup.exe`, lalu **Next → Install**. Tidak perlu hak admin.
2. Buka (atau mulai ulang) **AutoCAD 2021 atau lebih baru**. Command line menampilkan
   *"TCI Gesture Control siap"*.
3. Ketik **`GK`** lalu Enter untuk menyalakan kamera gestur. Ketik `GK` lagi untuk mematikannya.

Catatan pemasangan:
- Kalau AutoCAD menampilkan dialog keamanan untuk `TCIGestureControl.lsp`, pilih **Always Load**.
- Windows SmartScreen mungkin menampilkan *"Windows protected your PC"*, karena penginstal belum bertanda
  tangan digital. Klik *More info → Run anyway*.
- Untuk melepas: **Settings → Apps → TCI Gesture Control untuk AutoCAD → Uninstall**.
- Alternatif tanpa penginstal: unduh ZIP dari [Releases](../../releases), ekstrak, lalu jalankan `INSTAL.bat`
  (lepas dengan `HAPUS.bat`).

Kebutuhan: Windows 10/11 64-bit, webcam, AutoCAD 2021+, dan ruangan yang cukup terang (di ruangan redup,
webcam turun ke ~15 fps).

## Gestur

| Gestur | Aksi |
|---|---|
| ☝ telunjuk | kursor |
| 🤏 jepit-lepas / jepit-geser / jepit diam 0,8 s | klik / drag / klik kanan |
| ✊ / ✌ / 🤟 | orbit / pan / zoom |
| ✊✊ dua kepalan | putar tampilan 3D (setir = putar tegak; rentang = zoom) |
| 🤏🤏 dua cubitan | geser tampilan (rentang = zoom) |
| 👍 / 👎 / 🤘 ditahan | Enter / Undo / Esc |
| 🤙 ditahan | menu kaca berisi perintah |
| 🖐 telapak | berhenti, atau "angkat mouse" untuk memindah tangan |
| dua telapak 1,5 s, atau `Ctrl+Alt+G` | jeda / aktif |

Untuk menutup: tombol **✕ Tutup** di atas kartu kamera, `Ctrl+Alt+Q`, `GK`, atau tutup AutoCAD.

## Menyetel

Edit `config.json` di
`%APPDATA%\Autodesk\ApplicationPlugins\TCIGestureControl.bundle\Contents\app\`, lalu ketik `GK` dua kali.
Panduan "gejala → kunci" ada di [docs/tuning.md](docs/tuning.md). Contoh: kursor terasa licin → turunkan
`pointer.gain_slow`.

## Dari kode sumber (pengembang)

Butuh Python 3.12 64-bit ([python.org](https://www.python.org/downloads/); centang "Add python.exe to PATH" dan
"py launcher").

```powershell
.\siapkan.bat                                           # .venv, paket, model tangan, pengecekan
.venv\Scripts\python.exe -m pytest -q tests             # uji otomatis
.venv\Scripts\python.exe -m gesture_cad --simulate      # coba tanpa mengirim input
.venv\Scripts\python.exe pasang_di_autocad.py           # perintah GK lewat acad.pgp (mode pengembang)
```

Untuk membangun plugin dan penginstal sendiri (hasilnya di `plugin_build\release\`):

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller
winget install JRSoftware.InnoSetup --scope user          # sekali, untuk Setup.exe
.venv\Scripts\python.exe buat_plugin_autocad.py            # exe + bundle + ZIP
.venv\Scripts\python.exe buat_setup_autocad.py             # TCIGestureControl-Setup.exe
```

Suara opsional (offline, hanya mode kode sumber):

```powershell
.venv\Scripts\python.exe -m pip install vosk
.venv\Scripts\python.exe -m gesture_cad --download-voice-model
```

Setelah itu ucapkan "AutoCAD please help me", lalu perintah seperti "line" atau "zoom extents".

## Dokumentasi

- [docs/how-it-works.md](docs/how-it-works.md): arsitektur dan modul.
- [docs/lessons-learned.md](docs/lessons-learned.md): temuan dari uji nyata, dan kenapa desainnya begini.
- [docs/tuning.md](docs/tuning.md): menyetel rasa.

## Keamanan

- Mouse dan keyboard hanya dikirim bila jendela AutoCAD sedang aktif. Semua tombol dilepas saat tangan hilang,
  jeda, atau keluar.
- Plugin hanya menambah perintah `GK` / `GESTURE` / `KAMERA` dan tidak mengubah `acad.pgp` maupun pengaturan
  keamanan AutoCAD.
- Library ini hanya mengoperasikan AutoCAD. Hasil gambar tetap tanggung jawab penggunanya.

## Lisensi

Lihat [LICENSE](LICENSE). Pustaka pihak ketiga di dalam plugin tercantum di
`Contents\app\THIRD_PARTY_NOTICES.txt`.
