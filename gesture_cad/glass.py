"""Penggambar komponen UI bergaya kaca (ala iOS): panel buram transparan, sudut membulat, bayangan lembut.

Semua fungsi murni (PIL): masukan keadaan -> gambar RGBA. Tidak menyentuh Windows, jadi bisa diuji
dan dipratinjau sebagai PNG. Elemen digambar 2x lalu diperkecil (box filter) supaya tepi dan teks halus.

Catatan PIL: menggambar warna semi-transparan langsung ke gambar RGBA MENIMPA piksel (bukan memadukan).
Karena itu isian transparan selalu digambar di lapisan terpisah lalu dipadukan (`_blend`).
"""

import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import controller as C
from . import gestures as G

S = 2  # skala supersampling
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

WHITE = (255, 255, 255, 255)
SOFT = (235, 235, 245, 175)
FAINT = (235, 235, 245, 110)
GREEN = (52, 199, 89, 255)
AMBER = (255, 179, 64, 255)
RED = (255, 69, 58, 255)
BLUE = (10, 132, 255, 255)
GREY = (142, 142, 147, 255)
TINT = (24, 24, 28)

POSE_EMOJI = {
    "HOLO": "\U0001f64c",
    "HOLO_PAN": "\U0001f90f",
    G.POINT: "\u261d", G.PINCH: "\U0001f90f", G.FIST: "\u270a", G.OPEN: "\U0001f590",
    G.VICTORY: "\u270c", G.THREE: "\U0001f91f", G.ROCK: "\U0001f918", G.SHAKA: "\U0001f919",
    G.THUMB_UP: "\U0001f44d", G.THUMB_DOWN: "\U0001f44e",
}
MODE_EMOJI = {
    C.DISARMED: "\u23f8", C.IDLE: "\U0001f590", C.POINTER: "\U0001f5b1", C.DRAG: "\U0001f90f",
    C.ORBIT: "\U0001f504", C.PAN: "\u270b", C.ZOOM: "\U0001f50d", C.MENU: "\u2728", C.HOLO: "\U0001f64c",
}
MODE_COLOR = {
    C.DISARMED: GREY, C.IDLE: SOFT, C.POINTER: GREEN, C.DRAG: RED, C.ORBIT: BLUE,
    C.PAN: (100, 210, 255, 255), C.ZOOM: (191, 90, 242, 255), C.MENU: AMBER, C.HOLO: (64, 224, 255, 255),
}
MODE_NAME = {
    C.DISARMED: "Dijeda", C.IDLE: "Siaga", C.POINTER: "Kursor", C.DRAG: "Klik / drag", C.ORBIT: "Orbit",
    C.PAN: "Pan", C.ZOOM: "Zoom", C.MENU: "Menu", C.HOLO: "Dua tangan",
}
MODE_TEXT = {"pointer": "Kursor", "drag": "Klik / drag", "orbit": "Orbit 3D", "pan": "Pan",
             "zoom": "Zoom naik/turun", "idle": "Berhenti"}
QUIET_TOASTS = ("KONTROL AKTIF", "KONTROL DIJEDA", "MENU DITUTUP", "KLIK", "KLIK KANAN", "HOLOGRAM",
                "SUARA AKTIF", "SUARA MATI")


# ----------------------------------------------------------------- dasar
@lru_cache(maxsize=64)
def font(name, size):
    for n in (name, "segoeui.ttf", "arial.ttf"):
        path = n if os.path.isabs(n) else os.path.join(FONT_DIR, n)
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


@lru_cache(maxsize=1)
def artifakt():
    """Font antarmuka Autodesk (Artifakt Element) dari instalasi AutoCAD/Autodesk pengguna, bila ada.

    Hanya dibaca dari tempatnya; tidak disalin. Kalau tidak ditemukan -> Segoe UI.
    """
    import glob

    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    found = {}
    pats = [os.path.join(pf, "Autodesk", "AutoCAD *", "HTMLDialog", "*", "ArtifaktElement", "WOFF2",
                         "Artifakt_Element_%s.woff2"),
            os.path.join(pf, "Autodesk", "AdskIdentityManager", "*", "html", "assets", "font",
                         "Artifakt Element %s.woff")]
    for weight, names in (("reg", ("Regular",)), ("med", ("Medium", "Semi Bold")), ("bold", ("Bold",))):
        for pat in pats:
            for nm in names:
                hits = sorted(glob.glob(pat % nm))
                if hits and weight not in found:
                    try:
                        ImageFont.truetype(hits[-1], 12)
                        found[weight] = hits[-1]
                    except OSError:
                        pass
    return found


def f_reg(px):
    return font(artifakt().get("reg", "segoeui.ttf"), px * S)


def f_semi(px):
    return font(artifakt().get("med", "seguisb.ttf"), px * S)


def f_bold(px):
    return font(artifakt().get("bold", "segoeuib.ttf"), px * S)


def f_emoji(px):
    return font("seguiemj.ttf", px * S)


def text_w(txt, fnt):
    if not txt:
        return 0
    l, t, r, b = fnt.getbbox(txt)
    return r - l


@lru_cache(maxsize=128)
def emoji_tile(ch, px):
    """Emoji berwarna dipotong rapat ke pikselnya (skala S), supaya bisa dipusatkan dengan tepat."""
    size = px * S
    im = Image.new("RGBA", (size * 3, size * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    try:
        d.text((size, size), ch, font=f_emoji(px), embedded_color=True)
    except (TypeError, ValueError, OSError):
        d.text((size, size), ch, font=f_emoji(px), fill=WHITE)
    box = im.getbbox()
    return im.crop(box) if box else im.crop((0, 0, 1, 1))


def paste_emoji(img, cx, cy, ch, px):
    """Tempel emoji berpusat di (cx, cy) (koordinat skala S); px = tinggi tampil dalam piksel layar."""
    tile = emoji_tile(ch, px)
    img.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))


def _blend(img, paint):
    """Gambar bentuk semi-transparan di lapisan terpisah lalu padukan ke `img`."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    paint(ImageDraw.Draw(layer))
    img.alpha_composite(layer)


@lru_cache(maxsize=96)
def rounded_mask(w, h, r):
    k = 2
    big = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, w * k - 1, h * k - 1], r * k, fill=255)
    return big.reduce(k)


@lru_cache(maxsize=96)
def shadow_layer(w, h, r, pad, strength=95):
    q = 4  # bayangan dihitung di resolusi rendah (blur besar mahal)
    sw, sh_, sp = max(1, w // q), max(1, h // q), max(1, pad // q)
    sh = Image.new("L", (sw + 2 * sp, sh_ + 2 * sp), 0)
    sh.paste(rounded_mask(sw, sh_, max(1, r // q)).point(lambda v: v * strength // 255), (sp, sp + max(1, sp // 3)))
    sh = sh.filter(ImageFilter.GaussianBlur(sp / 2.2)).resize((w + 2 * pad, h + 2 * pad), Image.BILINEAR)
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.putalpha(sh)
    return out


@lru_cache(maxsize=96)
def sheen(w, h, r):
    """Kilau tipis di separuh atas panel (kesan kaca)."""
    grad = Image.linear_gradient("L").resize((w, h)).point(lambda v: max(0, 34 - v * 34 // 128))
    a = ImageChops.multiply(grad, rounded_mask(w, h, r))
    out = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    out.putalpha(a)
    return out


def _sdf_inside(w, h, r):
    """Jarak (piksel) setiap titik di dalam persegi panjang membulat ke tepinya (0 di tepi, + di dalam)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    px, py = np.abs(xx - (w - 1) / 2.0), np.abs(yy - (h - 1) / 2.0)
    qx, qy = px - (w / 2.0 - r), py - (h / 2.0 - r)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    return -outside, xx, yy


@lru_cache(maxsize=96)
def refraction_maps(w, h, r):
    """Peta cv2.remap: tepi panel 'membiaskan' latar ke dalam seperti lensa (ciri Liquid Glass)."""
    depth, xx, yy = _sdf_inside(w, h, r)
    band = max(4.0, min(min(w, h) * 0.22, 26.0 * S))
    k = np.clip(1.0 - depth / band, 0.0, 1.0) ** 2
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    pull = 1.0 - 0.10 * k
    return (cx + (xx - cx) * pull).astype(np.float32), (cy + (yy - cy) * pull).astype(np.float32)


@lru_cache(maxsize=96)
def rim_light(w, h, r):
    """Tepi kaca yang menangkap cahaya: terang di sudut kiri-atas, pantulan lemah di kanan-bawah."""
    depth, xx, yy = _sdf_inside(w, h, r)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    ang = np.arctan2((yy - cy) / max(h, 1), (xx - cx) / max(w, 1))
    light = np.radians(-135.0)
    key = np.clip(np.cos(ang - light), 0, 1) ** 3
    bounce = 0.45 * np.clip(np.cos(ang - light - np.pi), 0, 1) ** 3
    inten = 0.22 + 0.78 * np.maximum(key, bounce)
    outer = np.clip(1.0 - np.abs(depth - 0.8 * S) / (0.9 * S), 0, 1)          # garis tepi tajam
    inner = 0.35 * np.clip(1.0 - np.abs(depth - 2.6 * S) / (1.4 * S), 0, 1)   # pantulan ketebalan kaca
    a = np.clip((outer + inner) * inten * 235, 0, 255).astype(np.uint8)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = a
    return Image.fromarray(rgba, "RGBA")


@lru_cache(maxsize=96)
def specular(w, h, r):
    """Sorotan lembut di sudut kiri-atas, di dalam panel."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rad = max(w, h) * 0.55
    d = np.hypot(xx / rad, yy / (rad * 0.7))
    a = np.clip(1.0 - d, 0, 1) ** 2 * 30
    mask = np.asarray(rounded_mask(w, h, r), np.float32) / 255.0
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * mask).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def glass(w, h, r, bg=None, tint=TINT, tint_amount=0.5, opacity=0.9, shadow=True, border=True):
    """Panel Liquid Glass ukuran (w, h) (sudah dalam skala S). Kembalikan (gambar, pad).

    Lapisan: bayangan tipis -> latar buram (dibiaskan di tepi, sedikit lebih jenuh) + warna dasar gelap
    -> kilau atas + sorotan sudut -> tepi kaca yang menangkap cahaya.
    """
    pad = 12 * S if shadow else 0
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        img.alpha_composite(shadow_layer(w, h, r, pad, 70))
    if bg is not None:
        import cv2

        src = np.asarray(bg.convert("RGB").resize((w, h), Image.BILINEAR))
        mx, my = refraction_maps(w, h, r)
        src = cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        base = ImageEnhance.Color(Image.fromarray(src)).enhance(1.35)
        base = Image.blend(base, Image.new("RGB", (w, h), tint), tint_amount)
        panel = base.convert("RGBA")
        alpha = int(255 * min(1.0, opacity + 0.05))
    else:
        panel = Image.new("RGBA", (w, h), tint + (255,))
        alpha = int(255 * opacity * 0.82)
    panel.putalpha(rounded_mask(w, h, r).point(lambda v: v * alpha // 255))
    panel.alpha_composite(sheen(w, h, r))
    panel.alpha_composite(specular(w, h, r))
    if border:
        panel.alpha_composite(rim_light(w, h, r))
    img.alpha_composite(panel, (pad, pad))
    return img, pad


def finish(img):
    """Perkecil dari skala S ke ukuran layar (box filter: cepat dan halus)."""
    return img.reduce(S)


def ring(d, cx, cy, rad, progress, color, width, back=(255, 255, 255, 45)):
    box = [cx - rad, cy - rad, cx + rad, cy + rad]
    if back:
        d.ellipse(box, outline=back, width=width)
    if progress > 0:
        d.arc(box, -90, -90 + int(360 * min(progress, 1.0)), fill=color, width=width)


# ----------------------------------------------------------------- pulau dinamis
def island_content(view, status, t):
    """Isi pulau dinamis (dipakai juga untuk menghitung lebar animasi)."""
    toasts = [x for x in view["toasts"] if t - x[1] < 1.6]
    voice = status.get("voice") or {}
    c = {"expanded": False, "title": MODE_NAME.get(view["mode"], view["mode"]), "sub": "",
         "icon": MODE_EMOJI.get(view["mode"], "\u2022"), "color": MODE_COLOR.get(view["mode"], SOFT)}
    if not view["armed"]:
        c.update(sub="Ctrl+Alt+G atau dua telapak untuk aktif")
    elif not status.get("gate_ok", True):
        host = status.get("host_label", "AutoCAD")
        c.update(title="Menunggu %s" % host, sub="klik jendela %s" % host, color=AMBER, icon="\u23f3")
    elif view.get("edge"):
        c.update(sub="jari terpotong tepi kamera", color=AMBER)
    if view["mode"] == C.HOLO:
        if status.get("two"):
            c.update(title="Pegang %s" % status["two"], color=MODE_COLOR[C.HOLO],
                     sub="geser = pindah  \u00b7  setir = rotasi  \u00b7  rentang = skala")
        elif (view.get("two") or {}).get("kind") == "pan":
            c.update(title="Geser tampilan", color=MODE_COLOR[C.PAN],
                     sub="gerakkan kedua cubitan = pan  \u00b7  rentang / rapat = zoom")
        else:
            c.update(title="Putar tampilan 3D", color=MODE_COLOR[C.HOLO],
                     sub="gerak = putar  \u00b7  setir = putar tegak  \u00b7  rentang = zoom")
    warn = status.get("cam_warn")
    if warn == "dark":
        c.update(expanded=True, icon="\U0001f4f7", title="Kamera gelap / tertutup", color=AMBER,
                 sub="buka penutup kamera, tombol kamera (F8/F9), atau sambungkan webcam")
    elif warn == "static":
        c.update(expanded=True, icon="\U0001f4f7", title="Tidak ada kamera asli", color=AMBER,
                 sub="hanya kamera virtual; aktifkan kamera laptop (tombol F8/F9) atau sambungkan webcam")
    elif warn and warn.startswith("slow"):
        c.update(expanded=True, icon="\U0001f4f7", title="Kamera lambat (%s fps)" % warn.split(":")[1], color=AMBER,
                 sub="tambah cahaya dari depan; tutup aplikasi lain yang memakai kamera")
    if voice.get("state") == "listening":
        heard = voice.get("partial") or voice.get("heard") or "katakan perintah\u2026"
        c.update(expanded=True, icon="\U0001f399", title="Mendengarkan", sub=heard, color=RED)
    if toasts:
        label = toasts[-1][0]
        c.update(expanded=True, icon="\u2705", title=label,
                 sub="" if label in QUIET_TOASTS else "dikirim ke %s" % status.get("host_label", "AutoCAD"),
                 color=GREEN)
    return c


def island_width(c):
    tw = max(text_w(c["title"], f_semi(16 if c["expanded"] else 14)), text_w(c["sub"][:60], f_reg(12)))
    return int(min(600, max(230, 96 + tw / S + 56)))


def draw_island(view, status, t, width, bg=None):
    c = island_content(view, status, t)
    h = 60 if (c["expanded"] or c["sub"]) else 44
    W, H = width * S, h * S
    img, pad = glass(W, H, H // 2, bg=bg, tint=(10, 10, 12), tint_amount=0.62, opacity=0.94)
    cy = pad + H // 2
    x = pad + 14 * S
    dot = GREEN if (view["armed"] and status.get("gate_ok", True)) else (AMBER if view["armed"] else GREY)
    rx = pad + W - 30 * S
    hold_pose, prog = view["hold"]

    def shapes(d):
        d.ellipse([x, cy - 4 * S, x + 8 * S, cy + 4 * S], fill=dot)
        if view.get("arm_progress", 0) > 0:
            ring(d, rx, cy, 16 * S, view["arm_progress"], GREEN, 3 * S)
        elif hold_pose and prog > 0:
            ring(d, rx, cy, 16 * S, prog, AMBER, 3 * S)
    _blend(img, shapes)
    paste_emoji(img, x + 32 * S, cy, c["icon"], 22)
    d = ImageDraw.Draw(img)
    tx = x + 54 * S
    if c["sub"]:
        d.text((tx, cy - 20 * S), c["title"], font=f_semi(16 if c["expanded"] else 14), fill=WHITE)
        d.text((tx, cy + 2 * S), c["sub"][:60], font=f_reg(12), fill=SOFT)
    else:
        d.text((tx, cy - 11 * S), c["title"], font=f_semi(14), fill=WHITE)
    pose = view.get("pose")
    if pose in POSE_EMOJI:
        paste_emoji(img, rx, cy, POSE_EMOJI[pose], 19)
    return finish(img), pad // S


# ----------------------------------------------------------------- kartu kamera
@lru_cache(maxsize=8)
def camera_base(fw, fh, mode, info, edge):
    """Bingkai kaca kartu kamera (di-cache; hanya video yang berubah tiap frame). Skala 1x."""
    m = 8
    W, H = (fw + 2 * m) * S, (fh + 2 * m + 26) * S
    img, pad = glass(W, H, 20 * S, opacity=0.9)
    y = pad + (fh + m + 5) * S
    col = MODE_COLOR.get(mode, SOFT)
    _blend(img, lambda d: d.ellipse([pad + 12 * S, y + 6 * S, pad + 20 * S, y + 14 * S], fill=col))
    d = ImageDraw.Draw(img)
    d.text((pad + 26 * S, y), MODE_NAME.get(mode, mode), font=f_semi(12), fill=WHITE)
    d.text((pad + W - text_w(info, f_reg(11)) - 12 * S, y + 1 * S), info, font=f_reg(11), fill=SOFT)
    out = finish(img)
    pad1 = pad // S
    if edge:
        chip = "geser tangan ke tengah"
        f = font(artifakt().get("med", "seguisb.ttf"), 11)
        cw = text_w(chip, f) + 20
        cx0 = pad1 + (out.width - 2 * pad1 - cw) // 2
        chip_img = Image.new("RGBA", out.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(chip_img)
        cd.rounded_rectangle([cx0, pad1 + 16, cx0 + cw, pad1 + 38], 11, fill=(255, 149, 0, 225))
        cd.text((cx0 + 10, pad1 + 19), chip, font=f, fill=WHITE)
        # chip digambar DI ATAS video: simpan terpisah
        return out, pad1, chip_img
    return out, pad1, None


def draw_camera_card(rgb_frame, view, status, width=300):
    """rgb_frame: PIL RGB (sudah dicerminkan & berkerangka). Kembalikan (RGBA, pad)."""
    fw = int(width)
    fh = int(round(rgb_frame.height * fw / float(rgb_frame.width)))
    host = status.get("host_label", "AutoCAD")
    info = "%s  \u00b7  %d fps" % ("%s terhubung" % host if status.get("acad_ok") else "%s belum" % host,
                                  int(round(status.get("fps", 0) / 5.0) * 5))
    base, pad, chip = camera_base(fw, fh, view["mode"], info, bool(view.get("edge")))
    img = base.copy()
    vid = rgb_frame.resize((fw, fh), Image.BILINEAR).convert("RGBA")
    vid.putalpha(rounded_mask(fw, fh, 14).point(lambda v: v * 235 // 255))
    img.alpha_composite(vid, (pad + 8, pad + 8))
    if chip is not None:
        img.alpha_composite(chip)
    return img, pad


# ----------------------------------------------------------------- panduan
def draw_guide(view, bg=None):
    rows = [(p, MODE_TEXT.get(m, m)) for p, m in view["continuous"].items()]
    rows += [(p, lbl + "  (tahan)") for p, lbl in view["discrete"].items()]
    if view.get("two_enabled"):
        rows.append(("HOLO", "Dua kepal: putar 3D"))
        rows.append(("HOLO_PAN", "Dua cubit: geser + zoom"))
    W = 236 * S
    H = (46 + 28 * len(rows) + 30) * S
    img, pad = glass(W, H, 22 * S, bg=bg, opacity=0.86)
    cur = view.get("pose")
    if view.get("mode") == C.HOLO:
        cur = "HOLO_PAN" if (view.get("two") or {}).get("kind") == "pan" else "HOLO"
    y0 = pad + 46 * S

    def shapes(d):
        for i, (pose, _) in enumerate(rows):
            if pose == cur:
                y = y0 + i * 28 * S
                d.rounded_rectangle([pad + 8 * S, y - 4 * S, pad + W - 8 * S, y + 24 * S], 10 * S,
                                    fill=(255, 255, 255, 42))
    _blend(img, shapes)
    d = ImageDraw.Draw(img)
    d.text((pad + 16 * S, pad + 12 * S), "Gestur", font=f_semi(15), fill=WHITE)
    for i, (pose, label) in enumerate(rows):
        y = y0 + i * 28 * S
        paste_emoji(img, pad + 26 * S, y + 10 * S, POSE_EMOJI.get(pose, "\u2022"), 19)
        d.text((pad + 46 * S, y + 1 * S), label, font=f_reg(13), fill=WHITE)
    d.text((pad + 16 * S, y0 + len(rows) * 28 * S + 4 * S), "Ctrl+Alt+H sembunyikan", font=f_reg(11), fill=FAINT)
    return finish(img), pad // S


# ----------------------------------------------------------------- halo kursor
def draw_halo(view, ripples, t, size=96):
    W = size * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    c = W // 2
    mode, st = view["mode"], view.get("ptr_state")

    def shapes(d):
        for (t0, kind) in ripples:
            k = (t - t0) / 0.35
            if 0 <= k <= 1:
                rad = int((10 + 30 * k) * S)
                col = (RED if kind == "right" else WHITE)[:3] + (int(230 * (1 - k)),)
                d.ellipse([c - rad, c - rad, c + rad, c + rad], outline=col, width=3 * S)
        if mode in (C.POINTER, C.DRAG):
            if st == "drag":
                d.ellipse([c - 12 * S, c - 12 * S, c + 12 * S, c + 12 * S], outline=RED, width=3 * S)
                d.ellipse([c - 4 * S, c - 4 * S, c + 4 * S, c + 4 * S], fill=RED)
            elif st == "pending":
                d.ellipse([c - 7 * S, c - 7 * S, c + 7 * S, c + 7 * S], fill=AMBER)
                if view.get("press_t") is not None:
                    prog = (t - view["press_t"]) * 1000.0 / max(view.get("longpress_ms", 800), 1)
                    if prog > 0.35:  # tampil hanya saat jelas menahan (menuju klik kanan)
                        ring(d, c, c, 18 * S, prog, RED, 3 * S, back=(255, 255, 255, 30))
            else:
                pre = view.get("preclick", 0.0)
                rad = int((18 - 10 * pre) * S)
                col = AMBER if pre > 0 else (255, 255, 255, 215)
                d.ellipse([c - rad - S, c - rad - S, c + rad + S, c + rad + S], outline=(0, 0, 0, 90), width=S)
                d.ellipse([c - rad, c - rad, c + rad, c + rad], outline=col, width=2 * S + int(pre * 2 * S))
                if st == "locked":
                    d.ellipse([c - 3 * S, c - 3 * S, c + 3 * S, c + 3 * S], fill=GREEN)
        elif mode in (C.ORBIT, C.PAN, C.ZOOM):
            d.ellipse([c - 19 * S, c - 19 * S, c + 19 * S, c + 19 * S], fill=(20, 20, 24, 175),
                      outline=MODE_COLOR[mode], width=2 * S)
    _blend(img, shapes)
    if mode in (C.ORBIT, C.PAN, C.ZOOM):
        paste_emoji(img, c, c, MODE_EMOJI[mode], 20)
    return finish(img)


def draw_menu_cursor(dwell, size=64):
    """Titik kursor menu + cincin tunggu (jendela kecil terpisah, jadi menu tak perlu digambar ulang)."""
    W = size * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    c = W // 2

    def shapes(d):
        d.ellipse([c - 15 * S, c - 15 * S, c + 15 * S, c + 15 * S], outline=(0, 0, 0, 90), width=4 * S)
        ring(d, c, c, 15 * S, 1.0 if dwell <= 0 else dwell, GREEN if dwell > 0 else AMBER, 3 * S,
             back=AMBER if dwell > 0 else None)
        d.ellipse([c - 4 * S, c - 4 * S, c + 4 * S, c + 4 * S], fill=AMBER)
    _blend(img, shapes)
    return finish(img)


# ----------------------------------------------------------------- menu
def draw_menu(view, width, height, bg=None, hover_all=False):
    """Menu kaca. hover_all=True: semua tombol digambar tersorot (untuk dipotong jadi ubin sorotan)."""
    menu = view["menu"]
    W, H = width * S, height * S
    img, pad = glass(W, H, 28 * S, bg=bg, tint=(14, 14, 18), tint_amount=0.6, opacity=0.94)
    hover = view.get("hover")
    btns = menu.buttons()

    def box(b):
        x0, y0, x1, y1 = b.rect
        return (pad + int(x0 * W), pad + int(y0 * H)), (pad + int(x1 * W), pad + int(y1 * H))

    def shapes(d):
        for b in btns:
            p0, p1 = box(b)
            is_hover = hover_all or (hover is not None and hover.id == b.id)
            active = b.kind == "tab" and b.payload == menu.page
            if b.kind == "tab":
                fill = (10, 132, 255, 235) if active else (255, 255, 255, 90 if is_hover else 34)
                rad = (p1[1] - p0[1]) // 2
            elif b.kind == "close":
                fill = (255, 69, 58, 235 if is_hover else 175)
                rad = (p1[1] - p0[1]) // 2
            else:
                fill = (255, 255, 255, 80 if is_hover else 26)
                rad = 16 * S
            d.rounded_rectangle([p0, p1], rad, fill=fill,
                                outline=(255, 255, 255, 170 if is_hover else 50), width=(2 if is_hover else 1) * S)
    _blend(img, shapes)
    d = ImageDraw.Draw(img)
    for b in btns:
        p0, p1 = box(b)
        fnt = f_semi(16) if b.kind == "item" else f_semi(13)
        tw = text_w(b.label, fnt)
        l, t_, r, bt = fnt.getbbox(b.label)
        d.text(((p0[0] + p1[0] - tw) // 2 - l, (p0[1] + p1[1] - (bt - t_)) // 2 - t_), b.label, font=fnt, fill=WHITE)
    hint = "Arahkan telunjuk  \u00b7  tahan diam atau jepit = pilih  \u00b7  telunjuk+kelingking = tutup"
    d.text((pad + 26 * S, pad + H - 30 * S), hint, font=f_reg(12), fill=SOFT)
    return finish(img), pad // S


class MenuPainter:
    """Cache gambar menu: versi normal + versi semua-tersorot per halaman. Sorotan = tempel satu ubin."""

    def __init__(self, width, height):
        self.w, self.h = width, height
        self.key = None
        self.normal = self.lit = None
        self.pad = 0

    def render(self, view, bg=None, bg_id=0):
        menu = view["menu"]
        key = (menu.page, bg_id)
        if key != self.key:
            v = dict(view, hover=None)
            self.normal, self.pad = draw_menu(v, self.w, self.h, bg=bg)
            self.lit, _ = draw_menu(v, self.w, self.h, bg=bg, hover_all=True)
            self.key = key
        img = self.normal.copy()
        hover = view.get("hover")
        if hover is not None:
            x0, y0, x1, y1 = hover.rect
            box = (self.pad + int(x0 * self.w) - 2, self.pad + int(y0 * self.h) - 2,
                   self.pad + int(x1 * self.w) + 3, self.pad + int(y1 * self.h) + 3)
            img.paste(self.lit.crop(box), box[:2])
        return img, self.pad



# ----------------------------------------------------------------- tombol kontrol (bisa diklik)
CTRL_BTN = (96, 34)


def draw_controls(armed, hover=None, bg=None):
    """Pil kaca berisi [Jeda/Aktif] [Tutup]. Kembalikan (gambar, pad, {nama: kotak lokal 1x})."""
    bw, bh = CTRL_BTN
    gap, m = 6, 5
    W, H = (2 * bw + gap + 2 * m) * S, (bh + 2 * m) * S
    img, pad = glass(W, H, H // 2, bg=bg, tint=(10, 10, 12), tint_amount=0.6, opacity=0.95)
    boxes = {}
    names = ("pause", "quit")
    for i, name in enumerate(names):
        x0 = pad + (m + i * (bw + gap)) * S
        y0 = pad + m * S
        boxes[name] = (x0 // S, y0 // S, x0 // S + bw, y0 // S + bh)

    def shapes(d):
        for name in names:
            x0, y0, x1, y1 = [v * S for v in boxes[name]]
            lit = hover == name
            if name == "quit":
                fill = (255, 69, 58, 235 if lit else 175)
            else:
                fill = (255, 255, 255, 70 if lit else 26)
            d.rounded_rectangle([x0, y0, x1, y1], (y1 - y0) // 2, fill=fill,
                                outline=(255, 255, 255, 150 if lit else 45), width=S)
            ix, iy = x0 + 18 * S, (y0 + y1) // 2
            if name == "quit":
                k = 5 * S
                d.line([(ix - k, iy - k), (ix + k, iy + k)], fill=WHITE, width=2 * S)
                d.line([(ix - k, iy + k), (ix + k, iy - k)], fill=WHITE, width=2 * S)
            elif armed:
                d.rounded_rectangle([ix - 5 * S, iy - 6 * S, ix - 2 * S, iy + 6 * S], S, fill=WHITE)
                d.rounded_rectangle([ix + 2 * S, iy - 6 * S, ix + 5 * S, iy + 6 * S], S, fill=WHITE)
            else:
                d.polygon([(ix - 4 * S, iy - 6 * S), (ix - 4 * S, iy + 6 * S), (ix + 6 * S, iy)], fill=GREEN)
    _blend(img, shapes)
    d = ImageDraw.Draw(img)
    for name, label in (("pause", "Jeda" if armed else "Aktifkan"), ("quit", "Tutup")):
        x0, y0, x1, y1 = [v * S for v in boxes[name]]
        fnt = f_semi(13)
        l, t_, r, b = fnt.getbbox(label)
        d.text((x0 + 32 * S - l, (y0 + y1 - (b - t_)) // 2 - t_), label, font=fnt, fill=WHITE)
    return finish(img), pad // S, boxes
