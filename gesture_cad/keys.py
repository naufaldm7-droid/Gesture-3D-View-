"""Tabel virtual-key Windows dan parser kombinasi tombol ("CTRL+Z", "ENTER", "F8")."""

VK = {
    "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "SHIFT": 0x10, "CTRL": 0x11, "ALT": 0x12,
    "PAUSE": 0x13, "CAPSLOCK": 0x14, "ESC": 0x1B, "SPACE": 0x20, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "INSERT": 0x2D, "DELETE": 0x2E, "SCROLLLOCK": 0x91,
}
for _i in range(10):
    VK[str(_i)] = 0x30 + _i
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    VK[_c] = ord(_c)
for _i in range(1, 13):
    VK["F%d" % _i] = 0x6F + _i

# Tombol yang butuh flag EXTENDEDKEY di SendInput
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}
MODIFIERS = ("CTRL", "SHIFT", "ALT")


def parse_combo(text):
    """'CTRL+SHIFT+Z' -> [0x11, 0x10, 0x5A]. ValueError jika ada nama tombol yang tidak dikenal."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("kombinasi tombol kosong")
    names = [n.strip().upper() for n in text.split("+")]
    out = []
    for n in names:
        if n not in VK:
            raise ValueError("tombol tidak dikenal: %r (dari %r)" % (n, text))
        out.append(VK[n])
    return out
