@echo off
rem Persiapan SEKALI: lingkungan Python (.venv), paket, model tangan MediaPipe, lalu pengecekan.
rem   siapkan.bat            -> untuk AutoCAD (config.json)
rem   siapkan.bat sketchup   -> juga memasang ekstensi SketchUp + cek profil SketchUp
rem Membutuhkan internet: paket Python dari PyPI dan model tangan ~7.8 MB dari Google MediaPipe.
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 if not exist ".venv\Scripts\python.exe" (
  echo Python belum terpasang. Pasang Python 3.12 64-bit dari https://www.python.org/downloads/
  echo ^(centang "Add python.exe to PATH" dan "py launcher"^), lalu jalankan file ini lagi.
  goto gagal
)
if not exist ".venv\Scripts\python.exe" (
  echo Membuat lingkungan Python...
  py -3.12 -m venv .venv || py -3.11 -m venv .venv || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" goto gagal
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --timeout 120 --retries 8 -r requirements.txt || goto gagal
if not exist "models\hand_landmarker.task" (
  ".venv\Scripts\python.exe" -m gesture_cad --download-model || goto gagal
)
if /i "%~1"=="sketchup" (
  ".venv\Scripts\python.exe" pasang_di_sketchup.py || goto gagal
  ".venv\Scripts\python.exe" -m gesture_cad --config config_sketchup.json --check
) else (
  ".venv\Scripts\python.exe" -m gesture_cad --check
)
echo.
echo Selesai.
if /i not "%~2"=="nopause" pause
exit /b 0

:gagal
echo.
echo GAGAL - lihat pesan di atas.
if /i not "%~2"=="nopause" pause
exit /b 1
