@echo off
title Login TikTok - ENCLip
cd /d "D:\ProjekAntigravity\ENCLip"
echo =======================================================
echo          ENCLIP - LOGIN TIKTOK STUDIO (1 KALI)
echo =======================================================
echo.
echo Browser Chromium akan terbuka. Silakan Login ke akun TikTok Anda.
echo (Bisa scan QR code menggunakan aplikasi TikTok di HP Anda)
echo.
C:\Python314\python.exe auto_clipper_tiktok.py --login-tiktok
echo.
pause
