@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Membuat environment Python lokal...
    python -m venv .venv
    if errorlevel 1 (
        echo Gagal membuat virtual environment. Pastikan Python terpasang dan bisa dipanggil dari PATH.
        pause
        exit /b 1
    )
    echo Memasang dependency...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo Menjalankan VanClipper Desktop...
".venv\Scripts\python.exe" Desktop_UI\desktop_gui.py
if errorlevel 1 pause
