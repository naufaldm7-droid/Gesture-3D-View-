# Arsitektur aplikasi (assets/app)

## Alur data

```
kamera ─▶ FrameGrabber (thread) ─▶ TrackWorker: tracker.py / MediaPipe (thread)
                                        │ (frame, hands, t)
                                        ▼
                     controller.py  (state machine murni → "niat")
                                        │
                     actuator.py   (mouse/keyboard SendInput, gerbang jendela, pelepas tombol)
                       ├─ autocad.py   (host autocad: COM SendCommand, pegang objek, ZOOMFACTOR)
                       └─ sketchup.py  (host sketchup: klien TCP → ekstensi Ruby)
                     glassui.py + glass.py + overlay.py  (overlay kaca Win32, tembus-klik)
                     voice.py (opsional, Vosk offline)
```

## Modul

| File | Isi |
|---|---|
| `gestures.py` | klasifikasi pose dari 21 landmark (POINT, PINCH, FIST, OPEN, VICTORY, THREE, ROCK, SHAKA, THUMB_UP/DOWN), aturan tepi frame |
| `filters.py` | One Euro filter |
| `controller.py` | mode (SIAGA, KURSOR, KLIK/DRAG, ORBIT, PAN, ZOOM, MENU, DUA TANGAN, JEDA), stabilisasi pose, kursor relatif + kunci + klik tertunda, tahan-untuk-perintah, menu, deteksi dua tangan |
| `actuator.py` | niat → Windows: `move_by`, `click`, `button`, `drag_begin/end` (pemetaan `output.nav`), `wheel`, `two_begin/move/end`, `action` |
| `config.py` | nilai bawaan + gabung dengan file profil + validasi (`--check`) |
| `menu.py` | tata letak menu kaca (koordinat 0..1) |
| `glass.py` | penggambar PIL: pulau dinamis, kartu kamera, panduan, halo kursor, menu, tombol Jeda/Tutup, efek Liquid Glass |
| `glassui.py` | jendela overlay, penempatan menempel ke jendela host, cache, latar buram |
| `overlay.py` | jendela berlapis Win32 (ctypes), klik khusus tombol kontrol, BitBlt |
| `winapi.py` | SendInput, jendela aktif, DPI |
| `voice.py` | asisten suara: kata bangun, tidur, pencocokan frasa |
| `__main__.py` | loop utama, `--check`, `--verify-sketchup`, `--simulate`, `--bench`, `--download-model` |
| `gesture_cad_start.pyw` | peluncur tanpa konsol, satu instance; panggilan kedua = matikan |

## Niat (controller → actuator)

`move_by dx dy` (lebar layar) · `move_abs nx ny` · `click left|right` · `button left down|up` ·
`drag_begin orbit|pan` · `drag_end` · `move_rel dx dy kind` · `wheel n` · `two_begin orbit|pan` ·
`two_move dx dy dputar dlog` · `two_end` · `action dict label` · `release_all`.

Controller murni (tanpa Windows), jadi semua perilaku gestur diuji dengan tangan sintetis (`tests/synth.py`).

## Profil

`config.json` = AutoCAD. `config_sketchup.json` = SketchUp. Keduanya digabung di atas `DEFAULTS`
(`gesture_cad/config.py`). `continuous`, `discrete`, dan daftar (`menu.pages`, `voice.commands`) **diganti utuh**,
tidak digabung.

Item aksi (menu, suara, `discrete`):

- `{"cmd": "_LINE"}` → AutoCAD COM
- `{"key": "CTRL+Z"}` → tombol
- `{"su": "selectLineTool:", "key": "L"}` → aksi SketchUp + shortcut cadangan
- `{"su_render": 0}` → gaya tampilan SketchUp
- `{"su_xray": true}` → X-ray
- `{"internal": "open_menu" | "close_menu" | "toggle_arm" | "quit"}`
