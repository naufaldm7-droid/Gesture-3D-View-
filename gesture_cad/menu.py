"""Menu udara: tombol perintah digambar di atas gambar kamera, dipilih dengan jari (jepit atau tahan diam).

Tata letak dalam koordinat ternormalisasi 0..1 gambar kamera; HUD tinggal mengalikan dengan ukuran frame.
"""

import math

from .config import normalize_action

TAB_Y = (0.08, 0.17)    # di bawah bar status HUD
GRID_Y = (0.21, 0.93)   # di atas baris petunjuk bawah
MARGIN_X = 0.03
GAP = 0.012


class Button:
    def __init__(self, bid, label, rect, kind, payload=None):
        self.id = bid
        self.label = label
        self.rect = rect      # (x0, y0, x1, y1)
        self.kind = kind      # "tab" | "item" | "close"
        self.payload = payload

    def contains(self, x, y):
        x0, y0, x1, y1 = self.rect
        return x0 <= x <= x1 and y0 <= y <= y1


class Menu:
    def __init__(self, menu_cfg):
        self.pages = []
        for page in menu_cfg["pages"]:
            items = [(it["label"], normalize_action(it)) for it in page["items"]]
            self.pages.append((page["name"], items))
        self.columns = max(1, int(menu_cfg.get("columns", 4)))
        self.page = 0
        self.is_open = False

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def buttons(self):
        out = []
        n_tabs = len(self.pages) + 1  # + tombol tutup
        w = (1.0 - 2 * MARGIN_X - GAP * (n_tabs - 1)) / n_tabs
        for i, (name, _) in enumerate(self.pages):
            x0 = MARGIN_X + i * (w + GAP)
            out.append(Button("tab:%d" % i, name, (x0, TAB_Y[0], x0 + w, TAB_Y[1]), "tab", i))
        x0 = MARGIN_X + len(self.pages) * (w + GAP)
        out.append(Button("close", "TUTUP", (x0, TAB_Y[0], x0 + w, TAB_Y[1]), "close"))

        items = self.pages[self.page][1]
        cols = self.columns
        rows = max(1, int(math.ceil(len(items) / float(cols))))
        rows = max(rows, 3)  # tombol tidak terlalu tinggi untuk halaman pendek
        cw = (1.0 - 2 * MARGIN_X - GAP * (cols - 1)) / cols
        rh = (GRID_Y[1] - GRID_Y[0] - GAP * (rows - 1)) / rows
        for k, (label, action) in enumerate(items):
            r, c = divmod(k, cols)
            x0 = MARGIN_X + c * (cw + GAP)
            y0 = GRID_Y[0] + r * (rh + GAP)
            out.append(Button("item:%d:%d" % (self.page, k), label, (x0, y0, x0 + cw, y0 + rh), "item", action))
        return out

    def hit(self, x, y):
        for b in self.buttons():
            if b.contains(x, y):
                return b
        return None
