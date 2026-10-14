@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title ENCLip - Autonomous Viral Clipper & TikTok Uploader

:: Pindah ke direktori skrip ini berada
cd /d "%~dp0"

:: Deteksi virtual environment Python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:MENU
cls
echo ===============================================================================
echo        ENCLIP - AUTONOMOUS VIRAL CLIPPER ^& TIKTOK UPLOADER PIPELINE
echo ===============================================================================
echo  Sistem otomatis pencarian podcast/video viral Indonesia, pemotongan momen
echo  terbaik menggunakan ENCLip Core, dan auto-upload ke TikTok tanpa API key!
echo ===============================================================================
echo.
echo  [1] Login ke Akun TikTok (Cukup 1x - Buka Browser ^& Simpan Sesi)
echo  [2] Jalankan Otomasi Penuh (Cari Video Viral -^> ENCLip -^> Upload TikTok)
echo  [3] Cari ^& Klip Saja (Simpan di Lokal, Tanpa Upload TikTok)
echo  [4] Klip dari URL YouTube Tertentu ^& Upload ke TikTok
echo  [5] Jalankan dengan Pengaturan Kustom (Query, Views, Gaya Klip, Layout)
echo  [0] Keluar
echo.
echo ===============================================================================
set /p "PILIHAN=Masukkan pilihan Anda [0-5]: "

if "%PILIHAN%"=="1" goto LOGIN_TIKTOK
if "%PILIHAN%"=="2" goto RUN_FULL
if "%PILIHAN%"=="3" goto RUN_NO_UPLOAD
if "%PILIHAN%"=="4" goto RUN_CUSTOM_URL
if "%PILIHAN%"=="5" goto RUN_CUSTOM_CONFIG
if "%PILIHAN%"=="0" goto KELUAR

echo.
echo Pilihan tidak valid! Silakan masukkan angka 0 sampai 5.
timeout /t 2 >nul
goto MENU

:LOGIN_TIKTOK
cls
echo ===============================================================================
echo [1] LOGIN KE AKUN TIKTOK (SATU KALI SAJA)
echo ===============================================================================
echo Browser Chromium akan terbuka. Silakan login ke akun TikTok Anda.
echo Setelah berhasil login dan profil terbuka di browser, kembali ke jendela
echo terminal ini dan tekan ENTER untuk menyimpan sesi login secara permanen.
echo ===============================================================================
echo.
"%PYTHON_EXE%" auto_clipper_tiktok.py --login-tiktok
echo.
echo Tekan tombol apa saja untuk kembali ke menu utama...
pause >nul
goto MENU

:RUN_FULL
cls
echo ===============================================================================
echo [2] MENJALANKAN OTOMASI PENUH
echo ===============================================================================
echo 1. Mencari video podcast/konten viral Indonesia dengan views tinggi via yt-dlp
echo 2. Memotong momen viral, karaoke subtitle, hook banner, audio energy via ENCLip
echo 3. Mengunggah klip hasil render ke TikTok Studio secara otomatis
echo ===============================================================================
echo.
"%PYTHON_EXE%" auto_clipper_tiktok.py --run
echo.
echo ===============================================================================
echo Proses selesai! Tekan tombol apa saja untuk kembali ke menu utama...
pause >nul
goto MENU

:RUN_NO_UPLOAD
cls
echo ===============================================================================
echo [3] CARI ^& KLIP SAJA (TANPA UPLOAD TIKTOK)
echo ===============================================================================
echo Klip video 9:16 vertikal akan dipotong dan dirender ke folder Core_Data\HasilClip
echo ===============================================================================
echo.
"%PYTHON_EXE%" auto_clipper_tiktok.py --run --no-upload
echo.
echo ===============================================================================
echo Selesai! Video tersimpan di Core_Data\HasilClip.
pause >nul
goto MENU

:RUN_CUSTOM_URL
cls
echo ===============================================================================
echo [4] KLIP DARI URL YOUTUBE TERTENTU
echo ===============================================================================
set /p "CUSTOM_URL=Masukkan URL Video YouTube: "
if "%CUSTOM_URL%"=="" (
    echo URL tidak boleh kosong!
    timeout /t 2 >nul
    goto MENU
)
echo.
echo Memproses URL: %CUSTOM_URL%
"%PYTHON_EXE%" auto_clipper_tiktok.py --video-url "%CUSTOM_URL%"
echo.
pause >nul
goto MENU

:RUN_CUSTOM_CONFIG
cls
echo ===============================================================================
echo [5] PENGATURAN KUSTOM PIPELINE OTOMATIS
echo ===============================================================================
set /p "QUERY_INPUT=Kata Kunci Pencarian (default: podcast viral indonesia): "
if "%QUERY_INPUT%"=="" set "QUERY_INPUT=podcast viral indonesia"

set /p "VIEWS_INPUT=Batas Minimal Views (default: 50000): "
if "%VIEWS_INPUT%"=="" set "VIEWS_INPUT=50000"

echo.
echo Pilih Gaya Pemotongan AI:
echo 1. spicy_drama   (Drama panas, intrik, pengakuan kontroversial)
echo 2. viral_all     (Kombinasi universal ramah algoritma TikTok)
echo 3. funny_blunder (Momen lucu, tawa lepas, blunder kocak)
echo 4. deep_meat     (Wawasan mendalam, kisah inspiratif, quotes)
echo 5. hype_rage     (Reaksi emosional tinggi, debat panas)
set /p "FLAVOR_CHOICE=Pilihan gaya [1-5, default 1]: "

set "FLAVOR_PARAM=spicy_drama"
if "%FLAVOR_CHOICE%"=="2" set "FLAVOR_PARAM=viral_all"
if "%FLAVOR_CHOICE%"=="3" set "FLAVOR_PARAM=funny_blunder"
if "%FLAVOR_CHOICE%"=="4" set "FLAVOR_PARAM=deep_meat"
if "%FLAVOR_CHOICE%"=="5" set "FLAVOR_PARAM=hype_rage"

echo.
echo Jalankan upload ke TikTok setelah render?
set /p "UPLOAD_CHOICE=Upload ke TikTok? [Y/N, default Y]: "
set "EXTRA_FLAGS="
if /i "%UPLOAD_CHOICE%"=="N" set "EXTRA_FLAGS=--no-upload"

echo.
echo Menjalankan dengan konfigurasi kustom:
echo - Query  : %QUERY_INPUT%
echo - Views  : %VIEWS_INPUT%
echo - Flavor : %FLAVOR_PARAM%
echo.
"%PYTHON_EXE%" auto_clipper_tiktok.py --query "%QUERY_INPUT%" --min-views %VIEWS_INPUT% --flavor %FLAVOR_PARAM% %EXTRA_FLAGS%
echo.
pause >nul
goto MENU

:KELUAR
cls
echo Terima kasih telah menggunakan ENCLip Autonomous Pipeline.
exit /b 0
