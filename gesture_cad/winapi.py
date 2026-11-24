"""Input mouse/keyboard Windows lewat ctypes (SendInput) + info jendela aktif. Tanpa dependensi luar."""

import ctypes
import os
from ctypes import wintypes

from .keys import EXTENDED, parse_combo

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0001, 0x0002, 0x0004
WHEEL_DELTA = 120
BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD))

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2


def set_dpi_aware():
    """Supaya koordinat kursor = piksel fisik di layar ber-skala 125%/150%."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _mouse(flags, data=0):
    i = INPUT(type=INPUT_MOUSE)
    i.mi = MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    return i


def _key(vk, up=False):
    flags = KEYEVENTF_KEYUP if up else 0
    if vk in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    i = INPUT(type=INPUT_KEYBOARD)
    i.ki = KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), flags, 0, 0)
    return i


def _unicode(ch, up=False):
    i = INPUT(type=INPUT_KEYBOARD)
    i.ki = KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0), 0, 0)
    return i


class WinInput:
    """Implementasi nyata. SimInput (di actuator.py) punya antarmuka yang sama untuk mode simulasi."""

    simulated = False

    def __init__(self):
        self._proc_cache = {}

    # --- mouse
    def cursor(self):
        p = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return (p.x, p.y)

    def set_cursor(self, x, y):
        user32.SetCursorPos(int(round(x)), int(round(y)))

    def button(self, name, down):
        d, u = BUTTON_FLAGS[name]
        _send(_mouse(d if down else u))

    def wheel(self, ticks):
        _send(_mouse(MOUSEEVENTF_WHEEL, int(ticks) * WHEEL_DELTA))

    # --- keyboard
    def key(self, vk, down):
        _send(_key(vk, up=not down))

    def tap_combo(self, combo):
        vks = parse_combo(combo)
        seq = [_key(v) for v in vks] + [_key(v, up=True) for v in reversed(vks)]
        _send(*seq)

    def type_text(self, text):
        seq = []
        for ch in text:
            seq += [_unicode(ch), _unicode(ch, up=True)]
        if seq:
            _send(*seq)

    def key_down_now(self, vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    # --- jendela
    def foreground(self):
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None, ""
        root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
        if root in self._proc_cache:
            return root, self._proc_cache[root]
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
        name = ""
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if h:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(buf))
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    name = os.path.basename(buf.value).lower()
            finally:
                kernel32.CloseHandle(h)
        if len(self._proc_cache) > 256:
            self._proc_cache.clear()
        self._proc_cache[root] = name
        return root, name

    def window_rect(self, hwnd):
        r = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return (r.left, r.top, r.right, r.bottom)
        return self.screen_rect()

    def screen_rect(self):
        return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def window_alive(self, hwnd):
        return bool(hwnd) and bool(user32.IsWindow(hwnd))

    def activate(self, hwnd):
        if not hwnd:
            return False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        if self.foreground()[0] == hwnd:
            return True  # sudah di depan; jangan tekan ALT (memunculkan keytip ribbon AutoCAD)
        # Tekan-lepas ALT agar Windows mengizinkan SetForegroundWindow dari proses latar
        _send(_key(0x12), _key(0x12, up=True))
        return bool(user32.SetForegroundWindow(hwnd))
