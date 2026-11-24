# Jembatan SketchUp

## Isi

1. [Komponen](#komponen)
2. [Protokol](#protokol)
3. [Nama aksi `Sketchup.send_action`](#nama-aksi)
4. [Matematika kamera](#matematika-kamera)
5. [Debug di Ruby Console](#debug-di-ruby-console)
6. [Masalah umum](#masalah-umum)

## Komponen

- `sketchup_ext/tci_gesture_control/main.rb` (sumber) disalin oleh `pasang_di_sketchup.py` ke
  `%APPDATA%\SketchUp\SketchUp 20xx\SketchUp\Plugins\tci_gesture_control\`.
- Pemasang juga menulis pemuat `Plugins\tci_gesture_control.rb`. File ini mendaftarkan `SketchupExtension` dan
  berisi `APP_DIR` (folder aplikasi, garis miring maju) untuk tombol nyala/mati.
- `gesture_cad/sketchup.py` → `SketchUpLink`: klien TCP di thread sendiri. Klien ini menyambung ulang tiap
  2 detik, punya `connected`/`status`/`version`, dan menggabungkan gerak kamera.
- Di aplikasi: `host.name = "sketchup"` membuat `SketchUpLink`. Actuator lalu menyalurkan aksi `type: sketchup`
  dan gerak dua tangan (`camera_via_bridge`) ke jembatan. Bila jembatan belum tersambung, aksi memakai
  `fallback_key` (shortcut bawaan) dan dua tangan memakai emulasi mouse.

## Protokol

TCP `127.0.0.1:47820` (`host.bridge_port`), satu objek JSON per baris (UTF-8, diakhiri `\n`). Ruby membaca
dengan `IO.select` di `UI.start_timer(0.02)`, jadi tidak pernah memblokir antarmuka SketchUp.

| Kirim | Jawab | Fungsi |
|---|---|---|
| `{"op":"hello","id":N}` | `{"id":N,"ok":true,"sketchup":"25.0.x","port":47820}` | jabat tangan |
| `{"op":"action","arg":"selectLineTool:","id":N}` | `{"id":N,"ok":true/false}` | `Sketchup.send_action`; nama wajib cocok `/\A[A-Za-z0-9]+:\z/` |
| `{"op":"render","arg":0..5}` | – | `rendering_options["RenderMode"]` |
| `{"op":"xray"}` | – | `ModelTransparency` nyala/mati |
| `{"op":"camera","kind":"orbit"/"pan","dx","dy","turn","zoom","orbit_gain","pan_gain","zoom_gain","invert_x","invert_y"}` | – | gerak kamera dua tangan |

Tanpa `id`, operasi yang berhasil tidak dijawab (menghemat lalu lintas untuk ~30 gerak kamera per detik).
Kesalahan selalu dijawab dengan `{"ok":false,"error":...}`.

**Keamanan:** hanya operasi di atas yang diterima. Jangan menambah operasi yang menjalankan string Ruby (`eval`,
`instance_eval`, `send` bebas), karena semua proses lokal bisa menyambung ke port itu.

## Nama aksi

Nama yang dipakai di `config_sketchup.json` (dari dokumentasi API `Sketchup.send_action`):

- **Tool:** `selectSelectionTool:` `selectLineTool:` `selectRectangleTool:` `selectCircleTool:`
  `selectArcTool:` `selectPolygonTool:` `selectFreehandTool:` `selectOffsetTool:` `selectPushPullTool:`
  `selectExtrudeTool:` (= Follow Me) `select3dTextTool:` `selectPaintTool:` `selectEraseTool:`
  `selectMoveTool:` `selectRotateTool:` `selectScaleTool:` `selectMeasureTool:` `selectProtractorTool:`
  `selectDimensionTool:` `selectTextTool:` `selectAxisTool:` `selectSectionPlaneTool:` `selectOrbitTool:`
  `selectDollyTool:` (= Pan) `selectZoomTool:` `selectWalkTool:`
- **Tampilan:** `viewIso:` `viewTop:` `viewFront:` `viewRight:` `viewBack:` `viewLeft:` `viewBottom:`
  `viewZoomExtents:` `viewZoomToSelection:` `viewPerspective:`
- **Edit:** `editUndo:` `editRedo:` `editCopy:` `editPaste:` `editCut:` `editDelete:` `editSelectAll:`
  `editSelectNone:` `editHide:`

Statusnya **belum diverifikasi** di versi SketchUp tujuan. `--verify-sketchup` mencoba semua aksi yang aman
dan melaporkan yang ditolak. Untuk aksi yang ditolak:
1. coba di Ruby Console: `Sketchup.send_action("namaAksi:")`;
2. cari nama lain di dokumentasi Ruby API SketchUp untuk versi itu;
3. atau hapus `"su"` dan sisakan `"key"` (shortcut bawaan SketchUp: Space, L, R, C, A, F, P, B, E, M, Q, S,
   T, O, H, Z, Shift+Z, G).

`Make Component` sengaja hanya memakai shortcut `G`, karena nama aksinya tidak pasti. RenderMode yang dipakai:
0 wireframe, 1 hidden line, 2 shaded, 3 textures, 5 monochrome. Verifikasi juga nilai-nilai ini di Ruby
Console bila hasilnya tidak sesuai.

## Matematika kamera

`camera_step` di Ruby (`dx`, `dy` dalam lebar frame kamera, y ke bawah; `turn` dalam radian, + = searah jarum
jam di layar; `zoom` = perubahan log rentang tangan):

- **orbit:**
  - `yaw = −dx·orbit_gain − turn` mengelilingi sumbu Z dunia melalui target. Tangan ke kanan membuat muka
    depan model ikut ke kanan.
  - `pitch = −dy·orbit_gain` mengelilingi sumbu kanan kamera. Pitch ditolak bila kamera akan melewati kutub
    (±2°).
- **pan:** `geser = kanan·(−dx·k) + atas·(dy·k)`, dengan `k = pan_gain · (jarak mata–target, atau tinggi
  kamera ortografis)`. Mata dan target sama-sama digeser.
- **zoom:** `f = exp(zoom·zoom_gain)`. Pada kamera perspektif jarak mata–target dibagi `f`; pada kamera
  ortografis `camera.height` dibagi `f`.
- Lalu `camera.set(eye, target, up)` dan `view.invalidate`.

Arah terasa terbalik? Ubah `two_hand.camera_invert_x` / `camera_invert_y`, tanpa menyentuh Ruby.

## Debug di Ruby Console

```ruby
TCI::GestureControl.start_server            # bila server belum jalan
Sketchup.send_action("selectLineTool:")     # uji satu nama aksi
TCI::GestureControl.camera_step({'kind'=>'orbit','dx'=>0.05,'dy'=>0,'turn'=>0,'zoom'=>0,
  'orbit_gain'=>3.0,'pan_gain'=>1.5,'zoom_gain'=>1.0})
TCI::GestureControl.toggle_app              # sama dengan tombol toolbar
```

Pesan jembatan selalu diawali `[Gesture Control]`.

## Masalah umum

| Gejala | Penyebab / tindakan |
|---|---|
| "jembatan gagal dibuka: Address already in use" | Jendela SketchUp kedua (tiap jendela = proses sendiri) atau aplikasi lain memakai 47820. Jembatan dimiliki jendela pertama. Ganti `PORT` di `main.rb` **dan** `host.bridge_port` di `config_sketchup.json` bila perlu. |
| Tombol toolbar tidak muncul | View > Toolbars > "Gesture Control"; atau Extension Manager: pastikan "TCI Gesture Control" aktif. |
| "Gesture Control belum lengkap terpasang" | `.venv`, peluncur, atau `config_sketchup.json` tidak ada di `APP_DIR`. Folder aplikasi dipindah? Jalankan ulang `pasang_di_sketchup.py` dari lokasi baru. |
| Tool tidak berganti, overlay menulis "jembatan SketchUp belum terhubung" | SketchUp dibuka sebelum ekstensi terpasang (mulai ulang SketchUp), atau server gagal (lihat Ruby Console). Aksi yang punya `key` tetap jalan lewat shortcut. |
| Dua tangan tidak menggerakkan kamera, tetapi orbit satu tangan jalan | `two_hand.camera_via_bridge` = false atau jembatan putus. Jalur cadangannya mouse. |
| Kursor/klik tidak masuk SketchUp | Gerbang jendela: `sketchup.exe` harus jendela aktif (klik sekali jendela SketchUp). Nama proses lain? Ubah `output.target_processes`. |
