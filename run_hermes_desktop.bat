@echo off
setlocal
cd /d "%~dp0"

if exist "dist\VanClipper\VanClipper.exe" (
    echo Menjalankan paket VanClipper...
    start "" "%~dp0dist\VanClipper\VanClipper.exe"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo Membuat environment Python lokal...
    python -m venv .venv
    if errorlevel 1 (
        echo Gagal membuat virtual environment. Pastikan Python terpasang dan bisa dipanggil dari PATH.
        pause
        exit /b 1
    )
)

echo Memastikan dependency terpasang...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Instalasi dependency gagal.
    pause
    exit /b 1
)

echo Menjalankan VanClipper Desktop...
".venv\Scripts\python.exe" desktop_app.py
pause
