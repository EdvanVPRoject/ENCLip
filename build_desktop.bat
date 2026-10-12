@echo off
setlocal
title ENCLip - Build Standalone Desktop Executable (.exe)

echo ========================================================
echo             ENCLip - PyInstaller Build Script           
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv belum ditemukan!
    echo Silakan jalankan install_dependencies.bat terlebih dahulu.
    echo.
    pause
    exit /b 1
)

echo [INFO] Mengaktifkan virtual environment...
call .venv\Scripts\activate.bat

echo [INFO] Memeriksa paket PyInstaller...
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Memasang PyInstaller...
    pip install pyinstaller
)

echo.
echo [INFO] Memulai proses kompilasi PyInstaller...
cd /d "%~dp0Desktop_UI"
..\.venv\Scripts\pyinstaller.exe --noconfirm VanClipper.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo         BUILD BERHASIL! APLIKASI TELAH DIBUAT          
    echo ========================================================
    echo Output Executable:
    echo   D:\ProjekAntigravity\VanClipper\Desktop_UI\dist\ENCLip\ENCLip.exe
    echo.
) else (
    echo.
    echo [ERROR] Terjadi kesalahan saat kompilasi PyInstaller.
)

cd /d "%~dp0"
pause
