@echo off
setlocal enabledelayedexpansion
title ENCLip - Setup Environment & Dependensi

echo ========================================================
echo        ENCLip - Video AI Clipper Environment Setup      
echo ========================================================
echo.

:: 1. Cek Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python tidak terdeteksi di sistem PATH!
    echo Silakan install Python 3.10 atau lebih baru dari:
    echo https://www.python.org/downloads/
    echo Pastikan mencentang opsi "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python terdeteksi: %PYTHON_VERSION%
echo.

:: 2. Siapkan Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Membuat virtual environment di .venv...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment berhasil dibuat.
) else (
    echo [OK] Virtual environment .venv sudah tersedia.
)
echo.

:: 3. Upgrade pip & Install requirements
echo [INFO] Menginstal dependensi Python dari requirements.txt...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [WARNING] Ada paket yang gagal diinstall secara otomatis.
    echo Silakan cek koneksi internet atau jalankan:
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] Semua dependensi Python berhasil dipasang.
echo.

:: 4. Buat folder kerja jika belum ada
if not exist "Core_Data\models" mkdir "Core_Data\models"
if not exist "Core_Data\VideoMentah" mkdir "Core_Data\VideoMentah"
if not exist "Core_Data\HasilClip" mkdir "Core_Data\HasilClip"

echo ========================================================
echo          SETUP SELESAI & ENCLip SIAP DIGUNAKAN!         
echo ========================================================
echo.
echo Langkah berikutnya:
echo  1. Jalankan aplikasi desktop:
echo     run_desktop.bat
echo.
echo  2. Atau compile ke file executable .exe:
echo     build_desktop.bat
echo.
pause
