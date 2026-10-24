@echo off
title ENCLip - Auto Upload 1 Clip Every 2 Hours
cd /d "D:\ProjekAntigravity\ENCLip"
echo [%date% %time%] Memulai Upload 1 Klip Otomatis (Jadwal 2 Jam Sekali)... >> "D:\ProjekAntigravity\ENCLip\Core_Data\uploader_2hours.log"

:: Jalankan upload 1 klip dari antrean stok
"C:\Python314\python.exe" auto_clipper_tiktok.py --upload-only >> "D:\ProjekAntigravity\ENCLip\Core_Data\uploader_2hours.log" 2>&1

echo [%date% %time%] Selesai proses upload klip 2 jam sekali. >> "D:\ProjekAntigravity\ENCLip\Core_Data\uploader_2hours.log"
