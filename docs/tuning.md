# Menyetel config.json (AutoCAD)

Lokasi `config.json`:
- **Plugin:** `%APPDATA%\Autodesk\ApplicationPlugins\TCIGestureControl.bundle\Contents\app\config.json`
- **Kode sumber:** di folder repo.

Ubah **satu nilai** setiap kali, lalu mulai ulang dengan mengetik `GK` dua kali (mati, lalu nyala). Kalau
memakai kode sumber, cek formatnya dengan `python -m gesture_cad --check`. Nilai yang tidak ditulis di
`config.json` memakai bawaan `gesture_cad/config.py`.

| Gejala | Kunci | Bawaan | Arah |
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
| dua tangan: zoom kurang halus | `two_hand.zoomfactor` | 20 | turun (10–15) |
| dua tangan: rentang terlalu peka | `two_hand.view_zoom_step` | 0.035 | naik |
| dua tangan: setir terlalu peka | `two_hand.view_twist_gain` | 0.25 | turun |
| dua kepalan sebaiknya memindah objek terpilih | `two_hand.grab_selected_objects` | false | true |
| pengguna kidal | `hand.dominant` | "Right" | "Left" |
| fps rendah (kartu kamera <20) | ruangan redup | – | tambah cahaya dari depan; cek `camera.fourcc = "MJPG"` |
| "geser tangan ke tengah" terus muncul | tangan terlalu dekat tepi kamera | – | layar laptop lebih tegak |

Isi menu kaca ada di `menu.pages[*].items`. Bentuk itemnya `{"label": "LINE", "cmd": "_LINE"}` atau
`{"label": "ORTHO", "key": "F8"}`, dengan label maksimal 14 huruf dan 16 item per halaman.
