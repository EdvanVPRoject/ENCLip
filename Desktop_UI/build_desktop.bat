@echo off
setlocal
cd /d "%~dp0"

echo Menutup aplikasi ENCLip yang mungkin masih berjalan...
taskkill /IM ENCLip.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo Membuat aplikasi native Windows ENCLip...
python -m PyInstaller --noconfirm --clean VanClipper.spec
if errorlevel 1 (
    echo Proses packaging gagal.
    pause
    exit /b 1
)

if exist "dist\ENCLip\ENCLip.exe" (
    echo Menyalin executable dan runtime package ke folder utama...
    copy /Y "dist\ENCLip\ENCLip.exe" "..\ENCLip.exe" >nul
    if exist "dist\ENCLip\_internal" (
        if not exist "..\_internal" mkdir "..\_internal"
        xcopy /E /I /Y "dist\ENCLip\_internal" "..\_internal" >nul
    )
)

if exist "build" rmdir /s /q "build"

echo.
echo Selesai. Executable ENCLip.exe siap di:
echo dist\ENCLip\ENCLip.exe dan di root folder ENCLip.
pause
