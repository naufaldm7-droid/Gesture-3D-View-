"""Jembatan ke SketchUp: klien TCP lokal ke ekstensi Ruby `tci_gesture_control` di dalam SketchUp.

Protokol: satu objek JSON per baris, ke 127.0.0.1:<port> (bawaan 47820). Ekstensi Ruby hanya menerima
operasi dari daftar putih — tidak ada eksekusi kode Ruby bebas dari luar.

  {"op": "hello", "id": 1}                         -> {"id": 1, "ok": true, "sketchup": "25.0.x"}
  {"op": "action", "arg": "selectLineTool:", "id": 2} -> {"id": 2, "ok": true|false}   (Sketchup.send_action)
  {"op": "render", "arg": 0..5}                    gaya tampilan (rendering_options["RenderMode"])
  {"op": "xray"}                                   X-ray nyala/mati
  {"op": "camera", "kind": "orbit"|"pan", "dx", "dy", "turn", "zoom", ...gain}   kamera langsung

Gerak kamera digabung (dijumlahkan) bila belum terkirim, jadi tidak pernah ada antrean basi.
"""

import json
import queue
import socket
import threading
import time


class SketchUpLink:
    def __init__(self, port=47820, cfg=None, log=print, host="127.0.0.1"):
        self.addr = (host, int(port))
        self.cfg = cfg or {}
        self.log = log
        self.connected = False
        self.version = ""
        self.status = "mencari SketchUp..."
        self.busy = False
        self.hwnd = None
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._cam = None
        self._sock = None
        self._buf = b""
        self._next_id = 1
        self._waiters = {}
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, name="sketchup-bridge", daemon=True)
        self._th.start()

    # ------------------------------------------------------------ API
    def send(self, op, arg=None):
        msg = {"op": op}
        if arg is not None:
            msg["arg"] = arg
        self._q.put(msg)

    def request(self, op, arg=None, timeout=1.0):
        """Kirim dan tunggu jawaban (dipakai --check / verifikasi aksi). Kembalikan dict atau None."""
        box = {"ev": threading.Event(), "res": None}
        msg = {"op": op}
        if arg is not None:
            msg["arg"] = arg
        with self._lock:
            msg["id"] = self._next_id
            self._next_id += 1
            self._waiters[msg["id"]] = box
        self._q.put(msg)
        box["ev"].wait(timeout)
        return box["res"]

    def camera(self, kind, dx, dy, turn, zoom):
        tc = self.cfg.get("two_hand", {})
        with self._lock:
            if self._cam is None or self._cam["kind"] != kind:
                if self._cam is not None:
                    self._q.put(self._cam)
                self._cam = {"op": "camera", "kind": kind, "dx": 0.0, "dy": 0.0, "turn": 0.0, "zoom": 0.0,
                             "orbit_gain": tc.get("camera_orbit_gain", 3.0),
                             "pan_gain": tc.get("camera_pan_gain", 1.5),
                             "zoom_gain": tc.get("camera_zoom_gain", 1.0),
                             "invert_x": bool(tc.get("camera_invert_x", False)),
                             "invert_y": bool(tc.get("camera_invert_y", False))}
                self._q.put("cam")
            c = self._cam
            c["dx"] += dx
            c["dy"] += dy
            c["turn"] += turn
            c["zoom"] += zoom

    def stop(self):
        self._stop.set()
        self._q.put(None)
        self._th.join(timeout=2.0)
        self._close()

    # ------------------------------------------------------------ thread
    def _close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.connected = False

    def _connect(self):
        try:
            s = socket.create_connection(self.addr, timeout=0.5)
            s.settimeout(0.5)
            self._sock = s
            self._buf = b""
            self._write({"op": "hello", "id": 0})
            reply = self._read_line(timeout=1.5)
            if reply and reply.get("ok"):
                self.version = str(reply.get("sketchup", "?"))
                self.connected = True
                self.status = "SketchUp terhubung (%s)" % self.version
                return True
        except OSError:
            pass
        self._close()
        self.status = "SketchUp belum terbuka / ekstensi belum aktif"
        return False

    def _write(self, msg):
        self._sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))

    def _read_line(self, timeout=0.0):
        end = time.monotonic() + timeout
        while b"\n" not in self._buf:
            self._sock.settimeout(max(0.0, end - time.monotonic()) or 0.001)
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout:
                return None
            if not chunk:
                raise OSError("jembatan ditutup SketchUp")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        try:
            return json.loads(line.decode("utf-8"))
        except ValueError:
            return None

    def _drain_replies(self):
        while True:
            r = self._read_line(timeout=0.0)
            if r is None:
                return
            if r.get("ok") is False:
                self.log("SketchUp menolak: %s" % r)
            box = self._waiters.pop(r.get("id"), None) if "id" in r else None
            if box is not None:
                box["res"] = r
                box["ev"].set()

    def _run(self):
        last_try = 0.0
        while not self._stop.is_set():
            if not self.connected:
                if time.monotonic() - last_try > 2.0:
                    last_try = time.monotonic()
                    self._connect()
                if not self.connected:
                    try:
                        item = self._q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if item is None:
                        break
                    if isinstance(item, dict) and "id" in item:
                        box = self._waiters.pop(item["id"], None)
                        if box:
                            box["ev"].set()
                    continue
            try:
                item = self._q.get(timeout=0.05)
            except queue.Empty:
                item = "idle"
            if item is None:
                break
            try:
                if item == "cam":
                    with self._lock:
                        msg, self._cam = self._cam, None
                    if msg:
                        self._write(msg)
                elif isinstance(item, dict):
                    self._write(item)
                self._drain_replies()
            except OSError as e:
                self.log("Jembatan SketchUp terputus: %s" % e)
                self._close()
