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
)

echo Memasang dependency dan PyInstaller...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Instalasi dependency gagal.
    pause
    exit /b 1
)

echo Menutup aplikasi VanClipper yang mungkin masih berjalan...
taskkill /IM VanClipper.exe /F >nul 2>&1
taskkill /IM HermesClipper.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo Membuat aplikasi VanClipper...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name VanClipper --add-data "web;web" --collect-all PyQt6 --collect-all faster_whisper --collect-all imageio_ffmpeg --collect-all llama_cpp --collect-submodules cv2 desktop_app.py
if errorlevel 1 (
    echo Proses packaging gagal.
    pause
    exit /b 1
)

echo Memastikan DLL llama.cpp ikut masuk ke paket aplikasi...
if not exist "dist\VanClipper\_internal\llama_cpp\lib" mkdir "dist\VanClipper\_internal\llama_cpp\lib"
robocopy ".venv\Lib\site-packages\llama_cpp\lib" "dist\VanClipper\_internal\llama_cpp\lib" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
if errorlevel 8 (
    echo Penyalinan DLL llama.cpp gagal.
    pause
    exit /b 1
)

if exist "build\VanClipper" rmdir /s /q "build\VanClipper"

if exist "models\*.gguf" (
    echo Menyalin model GGUF ke paket aplikasi. Ukuran model sangat besar, proses ini bisa lama...
    if not exist "dist\VanClipper\models" mkdir "dist\VanClipper\models"
    robocopy "models" "dist\VanClipper\models" *.gguf /S /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if errorlevel 8 (
        echo Penyalinan model gagal.
        pause
        exit /b 1
    )
)

echo.
echo Selesai. Jalankan aplikasi dari:
echo dist\VanClipper\VanClipper.exe
pause
