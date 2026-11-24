"""Jembatan ke AutoCAD lewat COM (pywin32), dari thread terpisah.

1) Perintah: masuk antrean, thread pekerja mengirim lewat SendCommand. Kalau COM gagal/ditolak,
   perintah diketik lewat keyboard (fallback) asalkan AutoCAD di depan.
2) Pegang objek (dua kepalan): objek yang sedang terpilih (grip tampil) dipindah, dirotasi, dan diskala
   LANGSUNG lewat COM mengikuti tangan. Satu sesi pegang = satu langkah UNDO.

Asumsi (dicatat juga di README): UCS = World dan VIEWTWIST = 0 saat memegang objek.
"""

import math
import queue
import threading
import time

RPC_E_CALL_REJECTED = -2147418111
RPC_E_SERVERCALL_RETRYLATER = -2147417846
_STOP = object()


def build_command_string(cmd, cancel_first=True):
    """'_BOX' -> '\\x1b\\x1b_BOX ' (ESC ESC membatalkan perintah aktif, spasi = Enter)."""
    s = cmd.strip()
    return ("\x1b\x1b" if cancel_first else "") + s + " "


# ------------------------------------------------------------------ geometri (murni, diuji)
def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v) if n > 1e-12 else (0.0, 0.0, 0.0)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def view_axes(viewdir):
    """VIEWDIR (target -> kamera) -> (kanan_layar, atas_layar, sumbu_ke_penonton) dalam koordinat dunia."""
    toward = _norm(viewdir)
    fwd = tuple(-c for c in toward)
    right = _cross(fwd, (0.0, 0.0, 1.0))
    if math.sqrt(sum(c * c for c in right)) < 1e-6:       # tampak atas/bawah: Z sejajar arah pandang
        right = (1.0, 0.0, 0.0) if toward[2] > 0 else (-1.0, 0.0, 0.0)
    right = _norm(right)
    up = _norm(_cross(right, fwd))
    return right, up, toward


def grab_step(right, up, units_per_px, dx_px, dy_px):
    """Geser layar (piksel, y ke bawah) -> vektor pindah di dunia (bidang layar)."""
    return tuple(right[i] * dx_px * units_per_px - up[i] * dy_px * units_per_px for i in range(3))


class AutoCADLink:
    def __init__(self, progids, fallback=None, log=print):
        self.progids = list(progids)
        self.fallback = fallback      # fungsi(cmd, cancel_first) -> bool, dipanggil bila COM gagal
        self.log = log
        self.status = "mencari AutoCAD..."
        self.connected = False
        self.busy = False
        self.hwnd = None
        self.version = ""
        self._app = None
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._grab = None             # keadaan sesi pegang (hanya disentuh thread pekerja)
        self._pending = None          # [dx_px, dy_px, dputar, dlog] menunggu diterapkan
        self._zf_old = None           # ZOOMFACTOR asli selama sesi dua tangan
        self._th = threading.Thread(target=self._run, name="autocad-com", daemon=True)
        self._th.start()

    # ------------------------------------------------------------ API (dipanggil thread utama)
    def send(self, cmd, cancel_first=True):
        self._q.put(("cmd", cmd, cancel_first))

    def stop(self):
        self._q.put(_STOP)
        self._th.join(timeout=2.0)

    def grab_begin(self, timeout=0.6):
        """Mulai memegang objek terpilih. Kembalikan jumlah objek (0 = tidak ada / AutoCAD sibuk)."""
        if self.busy:
            return 0
        box = {"ev": threading.Event(), "res": 0}
        self._q.put(("grab_begin", box))
        box["ev"].wait(timeout)
        return box["res"]

    def grab_move(self, dx_px, dy_px, dturn=0.0, dlog=0.0):
        """Tambahkan gerak; digabung bila pekerja belum sempat menerapkan (tidak pernah antre panjang)."""
        with self._lock:
            if self._pending is None:
                self._pending = [0.0, 0.0, 0.0, 0.0]
                self._q.put(("grab_apply",))
            p = self._pending
            p[0] += dx_px
            p[1] += dy_px
            p[2] += dturn
            p[3] += dlog

    def grab_end(self):
        self._q.put(("grab_end",))

    def view_session_begin(self, zoomfactor, timeout=0.4):
        """Perkecil ZOOMFACTOR selama sesi dua tangan (zoom roda lebih halus). Dikembalikan di akhir sesi."""
        if self.busy:
            return False
        box = {"ev": threading.Event(), "res": False}
        self._q.put(("zf_set", zoomfactor, box))
        box["ev"].wait(timeout)
        return box["res"]

    def view_session_end(self):
        self._q.put(("zf_restore",))

    # ------------------------------------------------------------ thread COM
    def _connect(self):
        import win32com.client

        for pid in self.progids:
            try:
                app = win32com.client.GetActiveObject(pid)
            except Exception:
                continue
            try:
                self.hwnd = int(app.HWND)
            except Exception:
                self.hwnd = None
            try:
                self.version = str(app.Version)
            except Exception:
                self.version = "?"
            self.connected = True
            self.status = "AutoCAD terhubung (%s)" % self.version
            return app
        self.connected = False
        self.status = "AutoCAD belum terbuka"
        return None

    def _send_com(self, app, text):
        import pywintypes

        for _ in range(20):
            try:
                app.ActiveDocument.SendCommand(text)
                return True
            except pywintypes.com_error as e:
                if e.args and e.args[0] in (RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER):
                    time.sleep(0.1)  # AutoCAD sedang sibuk; coba lagi
                    continue
                raise
        return False

    def _pt(self, p):
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(float(c) for c in p))

    def _w_grab_begin(self, app):
        doc = app.ActiveDocument
        if int(doc.GetVariable("CMDACTIVE")):
            return 0  # sedang di dalam perintah: jangan ganggu
        ss = doc.PickfirstSelectionSet
        objs = [ss.Item(i) for i in range(ss.Count)]
        if not objs:
            return 0
        lo, hi = [1e300] * 3, [-1e300] * 3
        for o in objs:
            mn, mx = o.GetBoundingBox()
            for i in range(3):
                lo[i], hi[i] = min(lo[i], mn[i]), max(hi[i], mx[i])
        center = tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
        right, up, toward = view_axes(tuple(doc.GetVariable("VIEWDIR")))
        view_h = float(doc.GetVariable("VIEWSIZE"))
        screen_h = float(doc.GetVariable("SCREENSIZE")[1]) or 1.0
        doc.StartUndoMark()
        self._grab = {"doc": doc, "objs": objs, "center": center, "right": right, "up": up,
                      "axis": toward, "upp": view_h / screen_h}
        return len(objs)

    def _w_grab_apply(self):
        with self._lock:
            p, self._pending = self._pending, None
        g = self._grab
        if g is None or p is None:
            return
        dx, dy, dturn, dlog = p
        c0 = g["center"]
        if dx or dy:
            d = grab_step(g["right"], g["up"], g["upp"], dx, dy)
            c1 = tuple(c0[i] + d[i] for i in range(3))
            a, b = self._pt(c0), self._pt(c1)
            for o in g["objs"]:
                o.Move(a, b)
            g["center"] = c0 = c1
        if dturn:
            # + = searah jarum jam di layar = negatif terhadap sumbu yang menghadap penonton
            tip = tuple(c0[i] + g["axis"][i] for i in range(3))
            a, b = self._pt(c0), self._pt(tip)
            for o in g["objs"]:
                o.Rotate3D(a, b, -dturn)
        if dlog:
            f = math.exp(dlog)
            a = self._pt(c0)
            for o in g["objs"]:
                o.ScaleEntity(a, f)
        for o in g["objs"]:
            try:
                o.Update()
            except Exception:
                pass

    def _w_grab_end(self):
        g, self._grab = self._grab, None
        with self._lock:
            self._pending = None
        if g is not None:
            try:
                g["doc"].EndUndoMark()
            except Exception:
                pass

    def _w_zf_restore(self, app):
        if self._zf_old is None or app is None:
            return
        for _ in range(10):  # orbit transparan baru selesai saat tombol dilepas: coba beberapa kali
            try:
                app.ActiveDocument.SetVariable("ZOOMFACTOR", self._zf_old)
                self._zf_old = None
                return
            except Exception:
                time.sleep(0.1)

    def _run(self):
        try:
            import pythoncom
        except ImportError:
            self.status = "pywin32 belum terpasang - pakai keyboard"
            pythoncom = None
        if pythoncom is not None:
            pythoncom.CoInitialize()
        app = None
        last_try = 0.0
        try:
            while True:
                try:
                    item = self._q.get(timeout=1.0)
                except queue.Empty:
                    item = None
                if item is _STOP:
                    break
                now = time.monotonic()
                if pythoncom is not None and (item is not None or now - last_try > 3.0):
                    if app is not None and item is None:
                        last_try = now
                        try:
                            app.Name  # ping: AutoCAD masih hidup?
                        except Exception:
                            app = None
                    if app is None:
                        last_try = now
                        app = self._connect()
                if item is None:
                    continue
                kind = item[0]
                if kind == "grab_begin":
                    box = item[1]
                    try:
                        box["res"] = self._w_grab_begin(app) if app is not None else 0
                    except Exception as e:
                        self.log("Pegang objek gagal mulai: %s" % e)
                        box["res"] = 0
                    box["ev"].set()
                    continue
                if kind == "grab_apply":
                    try:
                        self._w_grab_apply()
                    except Exception as e:
                        self.log("Pegang objek: %s" % e)
                    continue
                if kind == "grab_end":
                    self._w_grab_end()
                    continue
                if kind == "zf_set":
                    _, zf, box = item
                    try:
                        doc = app.ActiveDocument
                        if not int(doc.GetVariable("CMDACTIVE")):
                            if self._zf_old is None:
                                self._zf_old = int(doc.GetVariable("ZOOMFACTOR"))
                            doc.SetVariable("ZOOMFACTOR", int(zf))
                            box["res"] = True
                    except Exception:
                        pass
                    box["ev"].set()
                    continue
                if kind == "zf_restore":
                    self._w_zf_restore(app)
                    continue
                _, cmd, cancel_first = item
                if self._grab is not None:
                    self._w_grab_end()  # perintah baru menutup sesi pegang
                text = build_command_string(cmd, cancel_first)
                ok = False
                if app is not None:
                    try:
                        self.busy = True  # SendCommand menunggu sampai perintah AutoCAD selesai
                        ok = self._send_com(app, text)
                    except Exception as e:
                        self.log("COM gagal (%s); sambung ulang" % (e,))
                        app = None
                        self.connected = False
                        self.status = "COM terputus - pakai keyboard"
                self.busy = False
                if not ok and self.fallback is not None:
                    if not self.fallback(cmd, cancel_first):
                        self.log("Perintah %s tidak terkirim: AutoCAD tidak di depan" % cmd)
        finally:
            self._w_grab_end()
            self._w_zf_restore(app)
            if pythoncom is not None:
                pythoncom.CoUninitialize()
