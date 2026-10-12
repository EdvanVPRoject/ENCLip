@echo off
setlocal
cd /d "%~dp0"
title ENCLip - Video AI Clipper

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Environment belum terpasang. Menjalankan instalasi otomatis...
    call install_dependencies.bat
)

echo Membuka ENCLip Desktop...
start "" ".venv\Scripts\pythonw.exe" Desktop_UI\desktop_gui.py
if %ERRORLEVEL% neq 0 (
    ".venv\Scripts\python.exe" Desktop_UI\desktop_gui.py
    if %ERRORLEVEL% neq 0 pause
)
