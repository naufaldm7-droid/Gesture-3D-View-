"""Asisten suara opsional (offline, Vosk) dengan kata bangun.

Alur:
  TIDUR  --"AutoCAD please help me" / "AutoCAD are you ready" / "hey AutoCAD"-->  MENDENGARKAN
  MENDENGARKAN: "line", "poly line please", "cut", "extend", "enter", "undo", "box", "zoom extents", ...
                setiap perintah memperpanjang waktu dengar; diam `listen_seconds` -> kembali TIDUR
  "thank you" / "stop listening" -> TIDUR
  Kata bangun + perintah sekaligus juga bisa: "AutoCAD, line please".

Pengenalan dibatasi ke kosakata perintah (grammar Vosk) sehingga jauh lebih akurat daripada dikte bebas,
dan percakapan biasa di sekitar tidak memicu apa pun selama TIDUR.

Bagian pencocokan teks (`VoiceMatcher`) murni dan diuji tanpa mikrofon.
"""

import json
import os
import queue
import re
import threading
import time

from .config import APP_DIR, normalize_action

SPOKEN_FIXES = [  # model bahasa Inggris memecah/menyalah-dengar beberapa nama AutoCAD
    (r"\bauto ?(cad|cat|card|cads|kad)\b", "autocad"),
    (r"\bsketch ?ups?\b", "sketchup"),
    (r"\bpush ?pull\b", "pushpull"),
    (r"\bfollow ?me\b", "followme"),
    (r"\bx ?ray\b", "xray"),
    (r"\bpoly ?lines?\b", "polyline"),
    (r"\bp ?line\b", "polyline"),
    (r"\bpress ?pull\b", "presspull"),
    (r"\bthree ?d\b", "3d"),
    (r"\bzoom extent\b", "zoom extents"),
]


def normalize(text):
    t = " ".join(text.lower().replace("[unk]", " ").split())
    for pat, rep in SPOKEN_FIXES:
        t = re.sub(pat, rep, t)
    return t


class VoiceMatcher:
    """Teks hasil pengenalan -> keputusan. Tanpa audio, jadi bisa diuji."""

    def __init__(self, vcfg):
        self.wake = [normalize(w) for w in vcfg["wake"]]
        self.sleep = [normalize(s) for s in vcfg["sleep"]]
        self.fillers = set(normalize(" ".join(vcfg.get("fillers", []))).split())
        self.host_word = normalize(vcfg.get("host_word", "autocad"))  # "autocad" / "sketchup"
        self.commands = []
        for item in vcfg["commands"]:
            action = normalize_action(item)
            label = item.get("label") or item["say"][0].upper()
            for say in item["say"]:
                self.commands.append((normalize(say), action, label))
        self.commands.sort(key=lambda c: -len(c[0]))  # frasa terpanjang dicocokkan dulu

    SPOKEN = {"autocad": "auto cad", "polyline": "poly line", "presspull": "press pull", "3d": "three d",
              "pline": "poly line", "sketchup": "sketch up", "pushpull": "push pull", "followme": "follow me",
              "xray": "x ray"}

    def vocabulary(self):
        """Kata-kata lisan untuk grammar Vosk (bentuk seperti diucapkan, bukan bentuk ternormalisasi)."""
        words = set()
        for phrase in self.wake + self.sleep + [c[0] for c in self.commands] + sorted(self.fillers):
            for w in phrase.split():
                words.update(self.SPOKEN.get(w, w).split())
        return sorted(w for w in words if w.isalpha() or w == "'")

    def _strip(self, text):
        return " ".join(w for w in text.split() if w not in self.fillers and w != self.host_word)

    def find_command(self, text):
        core = " %s " % self._strip(text)
        for phrase, action, label in self.commands:
            if " %s " % phrase in core:
                return action, label
        return None

    def decide(self, text, listening):
        """Kembalikan (aksi_status, perintah) — aksi_status: 'wake' | 'sleep' | None."""
        t = normalize(text)
        if not t:
            return None, None
        if any(s in t for s in self.sleep) and listening:
            return "sleep", None
        woke = any(w in t for w in self.wake) or t.startswith(self.host_word)
        if not listening:
            if not woke:
                return None, None
            return "wake", self.find_command(t)
        return ("wake" if woke else None), self.find_command(t)


class VoiceAssistant:
    """Thread mikrofon + Vosk. Peristiwa dibaca main loop lewat `poll()`."""

    def __init__(self, cfg, log=print):
        vc = cfg["voice"]
        import sounddevice  # noqa: F401  (gagal di sini = suara tidak tersedia)
        import vosk

        path = vc["model"] if os.path.isabs(vc["model"]) else os.path.join(APP_DIR, vc["model"])
        if not os.path.isdir(path):
            raise FileNotFoundError("model suara belum ada: %s" % path)
        vosk.SetLogLevel(-1)
        self.log = log
        self.matcher = VoiceMatcher(vc)
        self.model = vosk.Model(path)
        self.listen_s = float(vc["listen_seconds"])
        self.speak_enabled = bool(vc.get("speak", True))
        self.state = "sleep"
        self.until = 0.0
        self.heard = ""
        self.partial = ""
        self.enabled = True
        self.mute_until = 0.0
        self.events = queue.Queue()
        self._audio = queue.Queue(maxsize=50)
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, name="voice", daemon=True)
        self._th.start()

    # --------------------------------------------------------------- API
    def poll(self):
        """Kembalikan list (action, label) yang siap dieksekusi, dan kelola batas waktu dengar."""
        if self.state == "listening" and time.monotonic() > self.until:
            self._sleep(quiet=True)
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def status(self):
        if not self.enabled:
            return {"state": "off"}
        return {"state": self.state, "heard": self.heard, "partial": self.partial}

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.state = "sleep"
        return self.enabled

    def stop(self):
        self._stop.set()
        self._th.join(timeout=2.0)

    # ------------------------------------------------------------ internal
    def _wake(self):
        self.state = "listening"
        self.until = time.monotonic() + self.listen_s
        self._say("Ready.")

    def _sleep(self, quiet=False):
        self.state = "sleep"
        self.partial = ""
        if not quiet:
            self._say("Okay.")

    def _say(self, text):
        if not self.speak_enabled:
            return
        try:
            import win32com.client

            v = win32com.client.Dispatch("SAPI.SpVoice")
            v.Speak(text, 1)  # asinkron
            self.mute_until = time.monotonic() + 0.25 + 0.09 * len(text)  # jangan dengar suara sendiri
        except Exception:
            pass

    def _handle(self, text):
        if not self.enabled or time.monotonic() < self.mute_until:
            return
        status, cmd = self.matcher.decide(text, self.state == "listening")
        if not status and not cmd:
            return
        self.heard = text
        if status == "sleep":
            self._sleep()
            return
        if status == "wake" and self.state != "listening" and cmd is None:
            self._wake()
            return
        if status == "wake":
            self.state = "listening"
        if cmd is not None:
            self.until = time.monotonic() + self.listen_s
            self.events.put(cmd)
            self.log("Suara: %r -> %s" % (text, cmd[1]))

    def _run(self):
        import sounddevice as sd
        import vosk

        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        grammar = json.dumps(self.matcher.vocabulary() + ["[unk]"])
        rec = vosk.KaldiRecognizer(self.model, 16000, grammar)

        def cb(indata, frames, t, status):
            try:
                self._audio.put_nowait(bytes(indata))
            except queue.Full:
                pass

        try:
            with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1, callback=cb):
                while not self._stop.is_set():
                    try:
                        data = self._audio.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        self.partial = ""
                        self._handle(json.loads(rec.Result()).get("text", ""))
                    elif self.state == "listening":
                        self.partial = normalize(json.loads(rec.PartialResult()).get("partial", ""))
        except Exception as e:  # mikrofon tidak ada / diblokir privasi
            self.log("Suara berhenti: %s" % e)
            self.enabled = False


VOICE_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def download_voice_model(cfg, log=print):
    """Unduh & ekstrak model Vosk kecil ke folder models/. Isi zip diperiksa (tanpa path keluar folder)."""
    import shutil
    import urllib.request
    import zipfile

    target = cfg["voice"]["model"]
    target = target if os.path.isabs(target) else os.path.join(APP_DIR, target)
    root = os.path.dirname(target)
    os.makedirs(root, exist_ok=True)
    tmp = os.path.join(root, "_voice_model.zip.part")
    log("Mengunduh %s" % VOICE_MODEL_URL)
    with urllib.request.urlopen(VOICE_MODEL_URL, timeout=120) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh, 1 << 16)
    with zipfile.ZipFile(tmp) as z:
        top = os.path.basename(target) + "/"
        for name in z.namelist():
            if not name.startswith(top) or ".." in name.split("/") or os.path.isabs(name):
                raise RuntimeError("isi zip tidak terduga: %s" % name)
        z.extractall(root)
    os.remove(tmp)
    log("Model suara siap: %s" % target)
    return target
