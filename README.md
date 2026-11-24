# TCI Gesture Control — kendalikan SketchUp & AutoCAD dengan tangan

Gerakkan kursor, klik, putar, geser, dan zoom model 3D **dengan tangan di depan kamera laptop**, tanpa sentuh
mouse. Aplikasi ini berjalan di Windows untuk **SketchUp** dan **AutoCAD**.

*Hand-gesture control for SketchUp and AutoCAD on Windows using your laptop webcam (MediaPipe). Everything runs
locally; documentation is in Indonesian.*

- **Kursor presisi seperti mouse:** gerak pelan = presisi, gerak cepat = jauh, tangan diam = kursor terkunci.
- **Klik dengan jepitan:** jepit lalu lepas = klik, jepit lalu geser = drag, jepit diam = klik kanan.
- **Navigasi satu tangan:** ✊ orbit, ✌ pan, 🤟 zoom.
- **Dua tangan memegang tampilan 3D:** ✊✊ putar, 🤏🤏 geser, rentangkan/rapatkan = zoom halus.
- **Menu kaca** berisi tool, misalnya Line, Push/Pull, Follow Me, Move, Rotate, Tape, tampilan standar, dan gaya
  tampilan.
- **Overlay transparan** di atas aplikasi CAD yang tembus-klik, plus tombol Jeda dan Tutup.
- **Nyala/mati dari dalam aplikasi:** tombol toolbar di SketchUp, atau ketik `GK` di AutoCAD.
- **Asisten suara opsional** yang berjalan offline, misalnya "SketchUp please help me", lalu "push pull".

> **Privasi:** gambar kamera dan suara diproses **hanya di laptop Anda**. Tidak ada yang dikirim ke internet.
> Internet hanya dipakai sekali saat persiapan, untuk mengunduh paket Python dan model tangan.

## Status

| Bagian | Status |
|---|---|
| Mesin gestur, overlay, kamera | dipakai dan diuji langsung di Windows 11 + AutoCAD 2026; 133 uji otomatis |
| AutoCAD (COM, perintah `GK`) | diuji langsung di AutoCAD 2026 |
| SketchUp (ekstensi Ruby) | **beta**: belum pernah dijalankan di SketchUp sungguhan. Jalankan langkah verifikasi di bawah, dan laporkan masalah lewat *Issues*. |

## Kebutuhan

- Windows 10/11 64-bit dengan webcam.
- **Python 3.12 64-bit** dari [python.org](https://www.python.org/downloads/). Saat memasang, centang
  "Add python.exe to PATH" dan "py launcher".
- SketchUp 2017+ dan/atau AutoCAD (yang mendukung COM).
- Ruangan cukup terang. Di ruangan redup, webcam otomatis turun ke ~15 fps.

## Pasang

1. **Unduh**: tombol hijau **Code → Download ZIP**, lalu ekstrak ke folder permanen, misalnya
   `C:\Users\<nama>\TCI-Gesture-Control`. Jangan dipindah setelah dipasang, karena ekstensi menyimpan lokasi ini.
   Path tanpa spasi paling aman.
2. **Persiapan**: buka folder itu, klik kanan di ruang kosong → *Open in Terminal*, lalu jalankan:

   ```powershell
   .\siapkan.bat sketchup
   ```

   Untuk AutoCAD saja, jalankan `.\siapkan.bat`. Langkah ini membuat lingkungan Python, memasang paket, mengunduh
   model tangan (~7.8 MB), memasang ekstensi SketchUp, lalu mengecek semuanya.
3. **AutoCAD** (opsional), untuk memasang perintah `GESTURE` / `KAMERA` / `GK`:

   ```powershell
   .venv\Scripts\python.exe pasang_di_autocad.py
   ```

   Skrip ini membuat cadangan `acad.pgp` dulu. `--hapus` melepasnya kembali persis seperti semula.

## Verifikasi SketchUp (sekali)

1. Buka SketchUp, lalu **Window → Ruby Console**. Harus ada baris `[Gesture Control] jembatan siap di 127.0.0.1:47820`.
2. Di terminal folder aplikasi, cek sambungan:

   ```powershell
   .venv\Scripts\python.exe -m gesture_cad --config config_sketchup.json --check
   ```

   Hasilnya harus "SketchUp terhubung".
3. Uji semua nama tool. Uji ini hanya mengganti tool dan tampilan, tidak mengubah model:

   ```powershell
   .venv\Scripts\python.exe -m gesture_cad --config config_sketchup.json --verify-sketchup
   ```

   Tool yang "DITOLAK" bisa diganti di `config_sketchup.json` (lihat [docs/sketchup-bridge.md](docs/sketchup-bridge.md)).

## Pakai

- **SketchUp:** klik tombol toolbar **Gesture Control** (atau *Extensions → Gesture Control*). Klik lagi untuk
  mematikan. Shortcut bisa dipasang lewat *Window → Preferences → Shortcuts*.
- **AutoCAD:** ketik `GK` lalu Enter. Ketik lagi untuk mematikan.
- **Tutup:** tombol ✕ Tutup di atas kartu kamera, `Ctrl+Alt+Q`, atau tutup aplikasi CAD-nya.

| Gestur | Aksi |
|---|---|
| ☝ telunjuk | kursor |
| 🤏 jepit-lepas / jepit-geser / jepit diam 0,8 s | klik / drag / klik kanan |
| ✊ / ✌ / 🤟 | orbit / pan / zoom |
| ✊✊ dua kepalan | putar tampilan 3D (setir = putar tegak; rentang = zoom) |
| 🤏🤏 dua cubitan | geser tampilan (rentang = zoom) |
| 👍 / 👎 / 🤘 ditahan | Enter / Undo / Esc |
| 🤙 ditahan | menu kaca berisi tool |
| 🖐 telapak | berhenti, atau "angkat mouse" untuk memindah tangan |
| dua telapak 1,5 s, atau `Ctrl+Alt+G` | jeda / aktif |

Coba tanpa mengirim input apa pun:
`.venv\Scripts\python.exe -m gesture_cad --config config_sketchup.json --simulate`

## Menyetel

Semua kecepatan dan ambang ada di `config_sketchup.json` (SketchUp) dan `config.json` (AutoCAD). Panduan
"gejala → kunci" ada di [docs/tuning.md](docs/tuning.md). Contoh: kursor terasa licin → turunkan
`pointer.gain_slow`.

## Suara (opsional)

```powershell
.venv\Scripts\python.exe -m pip install vosk
.venv\Scripts\python.exe -m gesture_cad --download-voice-model
```

Unduhan model sekitar 40 MB, dari alphacephei.com. Setelah itu ucapkan "SketchUp please help me" (atau
"AutoCAD please help me"), lalu perintah dalam bahasa Inggris, misalnya "line", "push pull", "zoom extents",
atau "thank you" untuk menidurkan asisten.

## Dokumentasi

- [docs/how-it-works.md](docs/how-it-works.md): arsitektur dan modul.
- [docs/lessons-learned.md](docs/lessons-learned.md): kenapa desainnya begini; temuan dari uji nyata.
- [docs/sketchup-bridge.md](docs/sketchup-bridge.md): protokol jembatan, nama tool, debug Ruby.
- [docs/tuning.md](docs/tuning.md): menyetel rasa.

## Uji (untuk pengembang)

```powershell
.venv\Scripts\python.exe -m pytest -q tests
```

## Keamanan

- Mouse dan keyboard hanya dikirim bila jendela SketchUp atau AutoCAD sedang aktif. Semua tombol dilepas saat
  tangan hilang, jeda, atau keluar.
- Ekstensi SketchUp membuka port **lokal** `127.0.0.1:47820` yang hanya menerima daftar operasi tetap (pilih
  tool, tampilan, kamera). Port ini tidak bisa menjalankan kode bebas.
- Library ini hanya mengoperasikan aplikasi. Hasil gambar tetap tanggung jawab penggunanya.

## Lisensi

Lihat [LICENSE](LICENSE).
