# Menyetel config_sketchup.json

Ubah **satu nilai** setiap kali, lalu mulai ulang aplikasi (tombol toolbar 2×: mati, lalu nyala) dan minta
pengguna mencoba lagi. Cek format dengan `--config config_sketchup.json --check`.

| Gejala yang dikatakan pengguna | Kunci | Bawaan | Arah |
|---|---|---|---|
| "licin", kursor meluncur saat pelan | `pointer.gain_slow` | 0.6 | turun (0.45) |
| kursor lambat menyeberang layar | `pointer.gain_fast` | 2.4 | naik (2.8) |
| kursor "lengket", susah mulai bergerak | `pointer.unlock_dist`, `pointer.lock_ms` | 0.009, 200 | turun |
| kursor bergetar saat diam | `pointer.lock_ms` / `pointer.lock_speed` | 200 / 0.03 | `lock_ms` turun / `lock_speed` naik |
| klik malah jadi drag | `pointer.drag_threshold` | 0.025 | naik (0.035) |
| klik kanan tak sengaja | `pointer.longpress_ms` | 800 | naik (1100) |
| jepitan sering tidak terbaca | `thresholds.pinch_on` / `pinch_off` | 0.25 / 0.38 | naik sedikit (0.28 / 0.42) |
| jepitan terbaca padahal tidak menjepit | `thresholds.pinch_on` | 0.25 | turun (0.22) |
| perintah (👍 👎 🤘) tertembak tak sengaja | `timing.hold_ms` | 600 | naik (800) |
| orbit/pan satu tangan terlalu cepat | `motion.orbit_gain_px`, `motion.pan_gain_px` | 1100, 1400 | turun |
| zoom tiga jari terlalu peka | `motion.zoom_step` | 0.05 | naik |
| dua tangan memutar terlalu cepat | `two_hand.camera_orbit_gain` | 3.0 | turun (2.0) |
| dua tangan terasa terbalik | `two_hand.camera_invert_x` / `camera_invert_y` | false | true |
| zoom dua tangan terlalu peka | `two_hand.camera_zoom_gain` | 1.0 | turun (0.6) |
| geser dua cubitan terlalu cepat | `two_hand.camera_pan_gain` | 1.5 | turun |
| pengguna kidal | `hand.dominant` | "Right" | "Left" |
| fps rendah (kartu kamera <20) | ruangan redup | – | tambah cahaya dari depan; cek `camera.fourcc = "MJPG"` |
| "geser tangan ke tengah" terus muncul | tangan terlalu dekat tepi kamera | – | posisikan laptop / layar lebih tegak |

Untuk menambah atau mengubah isi menu, edit `menu.pages[*].items`. Untuk perintah suara, edit
`voice.commands[*]` (`say` = frasa bahasa Inggris). Batasnya: label maksimal 14 huruf dan 16 item per halaman.
