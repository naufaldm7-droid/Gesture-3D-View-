"""Buka AutoCAD dan buat gambar latihan 3D untuk mencoba Gesture CAD.

Pemakaian (dari folder 17_GESTURE_CAD):
    .venv\\Scripts\\python.exe buat_latihan_3d.py

Isi gambar (satuan mm, angka bebas untuk latihan — bukan data desain):
  pelat alas abu-abu, kubus merah, silinder hijau, bola biru, kerucut kuning, torus cyan, baji magenta,
  dan satu balok berlubang (hasil SUBTRACT) supaya ada contoh solid hasil boolean.
Objek sengaja dipisah agar bisa dilatih UNION/SUBTRACT/MOVE/3DROTATE dengan gestur.
"""

import os
import sys
import time

import pythoncom
import pywintypes
import win32com.client

PROGIDS = ("AutoCAD.Application", "AutoCAD.Application.25.1", "AutoCAD.Application.25")
BUSY = (-2147418111, -2147417846)  # RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER
AC_SUBTRACTION = 2


def retry(fn, tries=240, wait=0.5):
    """AutoCAD menolak panggilan COM selama masih memuat/sibuk: coba lagi sampai siap."""
    for _ in range(tries):
        try:
            return fn()
        except pywintypes.com_error as e:
            if e.args and e.args[0] in BUSY:
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("AutoCAD tidak merespons")


def pt(x, y, z=0.0):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y), float(z)))


def get_or_start_autocad():
    for pid in PROGIDS:
        try:
            app = win32com.client.GetActiveObject(pid)
            print("AutoCAD sudah berjalan, dipakai.")
            return app
        except pywintypes.com_error:
            continue
    print("Membuka AutoCAD (bisa 30-90 detik)...", flush=True)
    for pid in PROGIDS:
        try:
            return win32com.client.Dispatch(pid)
        except pywintypes.com_error:
            continue
    raise RuntimeError("AutoCAD tidak bisa dibuka lewat COM")


def colorize(obj, aci):
    try:
        retry(lambda: setattr(obj, "Color", aci))
    except Exception:
        pass


HERE = os.path.dirname(os.path.abspath(__file__))
DWG = os.path.join(HERE, "latihan", "latihan_gestur_3d.dwg")


def main():
    app = get_or_start_autocad()
    retry(lambda: setattr(app, "Visible", True))
    retry(lambda: app.WindowState)  # tunggu sampai AutoCAD selesai memuat
    print("AutoCAD %s siap." % retry(lambda: app.Version), flush=True)

    docs = retry(lambda: app.Documents)
    if os.path.exists(DWG) and "--baru" not in sys.argv:
        doc = retry(lambda: docs.Open(DWG))
        retry(lambda: doc.Activate())
        print("Gambar latihan dibuka: %s  (buat ulang: tambahkan --baru)" % DWG, flush=True)
        return
    doc = None
    for tpl in ("acadiso.dwt", ""):
        try:
            doc = retry(lambda: docs.Add(tpl) if tpl else docs.Add())
            break
        except pywintypes.com_error:
            continue
    retry(lambda: doc.Activate())
    for var, val in (("INSUNITS", 4), ("MEASUREMENT", 1)):  # 4 = milimeter
        try:
            retry(lambda: doc.SetVariable(var, val))
        except pywintypes.com_error:
            pass
    ms = retry(lambda: doc.ModelSpace)

    def add(fn, aci, label):
        obj = retry(fn)
        colorize(obj, aci)
        print("  + %s" % label, flush=True)
        return obj

    add(lambda: ms.AddBox(pt(0, 0, -50), 9000, 6000, 100), 8, "pelat alas 9000x6000x100")
    add(lambda: ms.AddBox(pt(-3000, 1500, 750), 1500, 1500, 1500), 1, "kubus 1500")
    add(lambda: ms.AddCylinder(pt(0, 1500, 800), 600, 1600), 3, "silinder r600 t1600")
    add(lambda: ms.AddSphere(pt(3000, 1500, 750), 750), 5, "bola r750")
    add(lambda: ms.AddCone(pt(-3000, -1500, 800), 700, 1600), 2, "kerucut r700 t1600")
    add(lambda: ms.AddTorus(pt(0, -1500, 200), 700, 200), 4, "torus R700 r200")
    add(lambda: ms.AddWedge(pt(3000, -1500, 500), 1500, 1200, 1000), 6, "baji 1500x1200x1000")

    # Balok berlubang: contoh hasil SUBTRACT
    block = add(lambda: ms.AddBox(pt(0, 0, 400), 2400, 900, 800), 30, "balok 2400x900x800")
    hole = retry(lambda: ms.AddCylinder(pt(0, 0, 400), 300, 1200))
    # putar 90 derajat terhadap sumbu X: lubang tembus arah Y (lebar balok 900 < panjang silinder 1200)
    retry(lambda: hole.Rotate3D(pt(0, 0, 400), pt(1, 0, 400), 3.141592653589793 / 2))
    retry(lambda: block.Boolean(AC_SUBTRACTION, hole))
    print("  + lubang r300 menembus balok (SUBTRACT)", flush=True)

    for cmd in ("_-VIEW _SWISO ", "_VSCURRENT _Conceptual ", "_ZOOM _E "):
        retry(lambda: doc.SendCommand(cmd))
    try:
        retry(lambda: doc.SetVariable("WSCURRENT", "3D Modeling"))
    except pywintypes.com_error:
        pass  # nama workspace bisa berbeda (bahasa lain); tidak penting
    os.makedirs(os.path.dirname(DWG), exist_ok=True)
    target = DWG
    if os.path.exists(target):  # --baru: jangan timpa file lama
        target = DWG.replace(".dwg", time.strftime("_%Y%m%d_%H%M%S.dwg"))
    retry(lambda: doc.SaveAs(target))
    print("Selesai: tampilan SW ISO, gaya Conceptual. Disimpan: %s" % target, flush=True)


if __name__ == "__main__":
    main()
