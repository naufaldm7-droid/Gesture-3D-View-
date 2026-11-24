"""Jendela overlay Win32 (ctypes): alpha per piksel, tembus-klik, tidak pernah mengambil fokus.

Sifat setiap jendela:
  WS_EX_LAYERED     -> gambar RGBA dengan transparansi per piksel (UpdateLayeredWindow)
  WS_EX_TRANSPARENT -> semua klik mouse (termasuk dari gestur) tembus ke AutoCAD di bawahnya
  WS_EX_NOACTIVATE  -> tidak pernah menjadi jendela aktif, jadi AutoCAD tetap "di depan"
  WS_EX_TOOLWINDOW  -> tidak muncul di taskbar / Alt+Tab
  WDA_EXCLUDEFROMCAPTURE (opsional) -> overlay tidak ikut tertangkap layar, sehingga latar untuk efek
                       kaca buram bisa diambil dari layar tanpa memantulkan overlay itu sendiri.
"""

import ctypes
from ctypes import wintypes

import numpy as np

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
ULW_ALPHA = 0x02
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01
DIB_RGB_COLORS = 0
WDA_EXCLUDEFROMCAPTURE = 0x11
PM_REMOVE = 0x0001
SPI_GETWORKAREA = 0x0030


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT),
                ("lPrivate", wintypes.DWORD)]


user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = (ctypes.POINTER(WNDCLASSEXW),)
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = (wintypes.HWND,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.UINT)
user32.GetDC.argtypes = (wintypes.HWND,)
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
user32.UpdateLayeredWindow.argtypes = (wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD)
user32.PeekMessageW.argtypes = (ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT)
user32.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
user32.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
user32.SystemParametersInfoW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT)
gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = (wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD)
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (wintypes.HDC,)
try:
    user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
except AttributeError:
    pass
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

_CLASS = "TCI_GestureCAD_Overlay"
_proc_ref = None
_click_handlers = {}  # hwnd -> fungsi(x, y) untuk jendela yang bisa diklik

WM_MOUSEACTIVATE = 0x0021
WM_LBUTTONUP = 0x0202
MA_NOACTIVATE = 3


def _wndproc(h, m, w, l):
    if m == WM_MOUSEACTIVATE and h in _click_handlers:
        return MA_NOACTIVATE  # diklik tetap tidak merebut fokus dari AutoCAD
    if m == WM_LBUTTONUP and h in _click_handlers:
        x = ctypes.c_short(l & 0xFFFF).value
        y = ctypes.c_short((l >> 16) & 0xFFFF).value
        try:
            _click_handlers[h](x, y)
        except Exception:
            pass
        return 0
    return user32.DefWindowProcW(h, m, w, l)


def _ensure_class():
    global _proc_ref
    if _proc_ref is not None:
        return
    _proc_ref = WNDPROC(_wndproc)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = _proc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = _CLASS
    if not user32.RegisterClassExW(ctypes.byref(wc)):
        err = ctypes.get_last_error()
        if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
            raise ctypes.WinError(err)


def work_area():
    r = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return (r.left, r.top, r.right, r.bottom)


def pump_messages():
    msg = MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


gdi32.BitBlt.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD)
SRCCOPY = 0x00CC0020


def grab_region(box):
    """Potret area layar (x0, y0, x1, y1) -> PIL RGB. Tanpa CAPTUREBLT, jadi overlay sendiri tidak ikut."""
    from PIL import Image

    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    screen = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(screen)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h
    bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
    bits = ctypes.c_void_p()
    bmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if not gdi32.BitBlt(mem, 0, 0, w, h, screen, x0, y0, SRCCOPY):
            raise OSError("BitBlt gagal")
        buf = (ctypes.c_ubyte * (w * h * 4)).from_address(bits.value)
        arr = np.frombuffer(buf, np.uint8).reshape(h, w, 4)
        return Image.fromarray(arr[..., 2::-1].copy(), "RGB")
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)


def to_bgra_premultiplied(rgba):
    """numpy RGBA uint8 (h, w, 4) -> BGRA premultiplied (kebutuhan UpdateLayeredWindow)."""
    a = rgba[..., 3:4].astype(np.uint16)
    rgb = (rgba[..., :3].astype(np.uint16) * a + 127) // 255
    out = np.empty_like(rgba)
    out[..., 0] = rgb[..., 2]
    out[..., 1] = rgb[..., 1]
    out[..., 2] = rgb[..., 0]
    out[..., 3] = rgba[..., 3]
    return np.ascontiguousarray(out)


class OverlayWindow:
    def __init__(self, exclude_from_capture=True, on_click=None):
        """on_click=None: tembus-klik penuh. on_click=fn(x, y): jendela menerima klik kiri (koordinat lokal)
        pada piksel yang tidak transparan, tetap tanpa merebut fokus."""
        _ensure_class()
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if on_click is None:
            ex |= WS_EX_TRANSPARENT
        self.hwnd = user32.CreateWindowExW(ex, _CLASS, "Gesture CAD", WS_POPUP, 0, 0, 1, 1,
                                           None, None, kernel32.GetModuleHandleW(None), None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        if on_click is not None:
            _click_handlers[self.hwnd] = on_click
        if exclude_from_capture:
            try:
                user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE)
            except (AttributeError, OSError):
                pass
        self.visible = False
        self.pos = (0, 0)
        self.size = (0, 0)
        self._mem = None
        self._bmp = None
        self._old = None
        self._bits = ctypes.c_void_p()

    def _alloc(self, w, h):
        self._free()
        screen = user32.GetDC(None)
        self._mem = gdi32.CreateCompatibleDC(screen)
        user32.ReleaseDC(None, screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        self._bmp = gdi32.CreateDIBSection(self._mem, ctypes.byref(bmi), DIB_RGB_COLORS,
                                           ctypes.byref(self._bits), None, 0)
        self._old = gdi32.SelectObject(self._mem, self._bmp)
        self.size = (w, h)

    def _free(self):
        if self._mem:
            gdi32.SelectObject(self._mem, self._old)
            gdi32.DeleteObject(self._bmp)
            gdi32.DeleteDC(self._mem)
        self._mem = self._bmp = self._old = None

    def update(self, rgba, x, y):
        """rgba: numpy (h, w, 4) uint8. Gambar ulang jendela di posisi layar (x, y)."""
        h, w = rgba.shape[:2]
        if (w, h) != self.size:
            self._alloc(w, h)
        data = to_bgra_premultiplied(rgba)
        ctypes.memmove(self._bits, data.ctypes.data, w * h * 4)
        screen = user32.GetDC(None)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wintypes.POINT(int(x), int(y))),
                                   ctypes.byref(wintypes.SIZE(w, h)), self._mem,
                                   ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
        user32.ReleaseDC(None, screen)
        self.pos = (int(x), int(y))
        self.show()

    def move(self, x, y):
        if (int(x), int(y)) != self.pos:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)
            self.pos = (int(x), int(y))

    def raise_top(self):
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

    def show(self):
        if not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True

    def hide(self):
        if self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def destroy(self):
        self._free()
        if self.hwnd:
            _click_handlers.pop(self.hwnd, None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
