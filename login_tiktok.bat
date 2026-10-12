@echo off
title TikTok Login Session Helper - VanClipper
echo ========================================================
echo   VanClipper - TikTok Login Helper (Playwright)
echo ========================================================
echo.
echo Menjalankan Chromium untuk login akun TikTok...
echo Silakan scan QR Code atau login manual di browser.
echo.
".venv\Scripts\python.exe" "Backend_API\tiktok_uploader.py" --login
echo.
echo Selesai! Tekan tombol apa saja untuk menutup...
pause
