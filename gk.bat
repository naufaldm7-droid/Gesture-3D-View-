@echo off
rem Dipanggil oleh perintah GESTURE / KAMERA / GK di AutoCAD (acad.pgp). Nyala/mati Gesture CAD tanpa jendela.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0gesture_cad_start.pyw" %*
