@echo off
setlocal
cd /d "%~dp0"

echo Menutup aplikasi ENCLip yang mungkin masih berjalan...
taskkill /IM ENCLip.exe /F >nul 2>&1
ping 127.0.0.1 -n 2 >nul

echo [1/3] Mempaketkan aplikasi Portable terbaru (PyInstaller)...
python -m PyInstaller --noconfirm --clean VanClipper.spec
if errorlevel 1 (
    echo Proses packaging gagal.
    exit /b 1
)

if exist "dist\ENCLip\ENCLip.exe" (
    echo [2/3] Memperbarui folder portable dengan build terbaru...
    if not exist "..\portable" mkdir "..\portable"
    copy /Y "dist\ENCLip\ENCLip.exe" "..\portable\ENCLip.exe" >nul
    if exist "..\portable\_internal" rmdir /s /q "..\portable\_internal"
    xcopy /E /I /Y "dist\ENCLip\_internal" "..\portable\_internal" >nul
)

echo [3/3] Membersihkan file sementara build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    echo Membuat Native Windows Installer di folder Native_Installer...
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "enclip_installer.iss"
)

echo.
echo Selesai! Versi Portable dan Native Installer telah diperbarui.
