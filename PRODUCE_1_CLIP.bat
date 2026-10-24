@echo off
title Render 1 Video Podcast ke Antrean - ENCLip
cd /d "D:\ProjekAntigravity\ENCLip"
echo =======================================================
echo       ENCLIP - PRODUCE 1 PODCAST KE ANTREAN STOK
echo =======================================================
echo.
C:\Python314\python.exe auto_clipper_tiktok.py --produce-only --produce-now
echo.
pause
