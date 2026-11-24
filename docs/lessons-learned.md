# Pelajaran dari pengujian nyata

Daftar ini berisi temuan dari uji langsung di laptop + AutoCAD 2026. Setiap butir menjelaskan gejala, penyebab,
dan perbaikan yang sekarang ada di kode. Kalau pengguna di laptop lain melaporkan gejala serupa, periksa butir
ini dulu.

## Kamera & pelacakan

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Aplikasi 15–17 fps padahal deteksi cuma ~19 ms | Webcam laptop memperpanjang eksposur di ruangan redup, sehingga kamera sendiri turun ke ~17 fps. Eksposur manual memang 30 fps, tetapi terlalu gelap: tangan tidak terdeteksi. | Bukan bug. Sarankan lampu dari depan. Kartu kamera menampilkan fps. |
| Kamera hanya ~22 fps di ruangan terang | Format bawaan DirectShow (YUY2) lambat di banyak webcam | `camera.fourcc = "MJPG"` (30 fps). MSMF juga 30 fps, tetapi gambarnya jauh lebih gelap. |
| Telapak terbuka terbaca "tiga jari", sehingga zoom terpicu sendiri | Kelingking keluar frame, dan MediaPipe menebaknya menekuk | Pose = UNKNOWN bila titik jari (selain pergelangan & pangkal jempol) ada dalam 2,5 % dari tepi. Overlay menulis "geser tangan ke tengah". |
| Label Left/Right terbalik | Tasks API MediaPipe ≥1.x menganggap gambar TIDAK dicerminkan | Deteksi dijalankan pada frame asli, baru koordinat x dicerminkan. Opsi `hand.swap_labels`. |
| `mp.solutions` tidak ada | mediapipe 1.2.x hanya punya Tasks API | `HandLandmarker` mode VIDEO + file model `hand_landmarker.task` |

## Kursor & klik (keluhan "licin, susah dikontrol")

- **Kursor absolut (tunjuk posisi layar) terasa licin.** Jitter 1 px di kamera menjadi ~5 px di layar.
  Penggantinya kursor **relatif** dengan akselerasi: gerak pelan = gain kecil, gerak cepat = gain besar.
- **Kunci diam:** tangan lebih pelan dari `lock_speed` selama `lock_ms` membuat kursor terkunci. Kunci baru
  lepas setelah tangan bergeser `unlock_dist`.
- **Klik saat jepitan dilepas**, bukan saat jari mulai menjepit. Lepas tanpa bergeser = klik di titik semula;
  geser lebih dari `drag_threshold` = drag; diam selama `longpress_ms` = klik kanan; tangan hilang = batal.
  Gerak kursor ±120 ms sebelum jepitan dibatalkan ("rewind"), karena jari yang menutup ikut menggeser tangan.
- **Jangkar kursor** = rata-rata pangkal telunjuk dan jari tengah. Titik ini hampir diam saat menjepit.
  Jepitan juga dihitung ke ruas atas telunjuk, jadi "menekan jempol ke sisi telunjuk" ikut menjadi klik.
- **Kursor melambat begitu masuk jendela host** karena skalanya diambil dari lebar jendela. Saat jendela hanya
  setengah layar, kursor jadi setengah lebih lambat. Sekarang skalanya dari lebar layar.

## Overlay

- PIL menggambar warna semi-transparan pada gambar RGBA dengan **menimpa** piksel, bukan memadukannya.
  Akibatnya tombol menu tampak "bolong". Isian transparan harus digambar di lapisan terpisah lalu dipadukan
  dengan `alpha_composite` (`glass._blend`).
- Biaya render: menu kaca 2× supersampling memakan 110–590 ms. Solusinya di-cache per halaman: versi normal dan
  versi semua tersorot, lalu sorotan cukup menempel satu ubin (<1 ms). Lebar pulau dinamis dikuantisasi per
  16 px supaya efek kaca ter-cache.
- Latar buram diambil dengan BitBlt area kecil. `ImageGrab` memotret seluruh layar (~20 ms).
  `WDA_EXCLUDEFROMCAPTURE` mencegah overlay ikut terpotret (sehingga tidak ada pantulan). Efek sampingnya,
  overlay tidak terlihat di screenshot. Untuk verifikasi visual, jalankan dengan `--no-blur`.
- Tombol Jeda/Tutup adalah satu-satunya jendela yang bisa diklik: tanpa `WS_EX_TRANSPARENT`, dengan
  `WM_MOUSEACTIVATE → MA_NOACTIVATE` supaya host tetap aktif. Jepitan gestur juga bisa mengkliknya.
- Kamera dan MediaPipe berjalan di thread sendiri (pembaca frame + pelacak). Loop UI tidak pernah menunggu
  kamera.
- Font: Artifakt Element dibaca dari instalasi Autodesk bila ada (tanpa disalin), selain itu Segoe UI.
  Emoji dari `seguiemj.ttf` dipotong sesuai kotak pikselnya agar bisa dipusatkan.

## Integrasi host

- Pengguna ingin **memakai aplikasi seperti biasa**, lalu menyalakan kamera dari dalam aplikasi CAD-nya, bukan
  menjalankan `.bat`. AutoCAD memakai perintah PGP `GK`; SketchUp memakai tombol toolbar/menu ekstensi Ruby.
  Peluncur `gesture_cad_start.pyw` bersifat satu instance: memanggilnya kedua kali = mematikan (lewat file
  bendera di `%TEMP%`).
- Overlay sempat **tetap tampil setelah host ditutup**. Sekarang aplikasi keluar otomatis bila jendela host
  terakhir (`act.target_hwnd`) sudah tidak ada.
- Pengguna menolak **animasi tanpa fungsi** (bola "hologram"). Yang mereka mau: dua tangan benar-benar
  menggerakkan tampilan 3D (putar, geser, zoom halus). Setiap elemen visual harus memberi umpan balik nyata.
- AutoCAD: `SendCommand` lewat COM menunggu sampai perintah selesai. Bila COM sedang sibuk, perintah baru
  diketik lewat keyboard (ESC ESC + perintah) supaya tidak mengantre. SketchUp tidak punya masalah ini,
  karena jembatan Ruby tidak menunggu.
- AutoCAD PGP menolak baris external command yang panjang atau bertanda kutip secara diam-diam. Solusinya baris
  pendek yang memanggil `gk.bat`.
- Saat menguji, jangan jalankan peluncur ketika pengguna sedang memakai aplikasi, karena itu mematikan sesinya.
  Cek `pythonw.exe` dulu.
