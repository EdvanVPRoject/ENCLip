@echo off
cd /d "D:\ProjekAntigravity\ENCLip"
echo [%date% %time%] Memulai Auto Clipper Subuh 1080p (Silent Mode)... >> "D:\ProjekAntigravity\ENCLip\Core_Data\autoclipper_4am.log"

:: Tampilkan UI Live HUD secara native tanpa jendela CMD hitam
start "" "C:\Python314\pythonw.exe" "D:\ProjekAntigravity\ENCLip\clipper_hud.py"

:: Jalankan proses produksi video klip
"C:\Python314\python.exe" auto_clipper_tiktok.py --produce-only --produce-now --no-upload --layout standard --aspect-ratio 16:9 --quality 1080 >> "D:\ProjekAntigravity\ENCLip\Core_Data\autoclipper_4am.log" 2>&1

echo [%date% %time%] Selesai proses klip subuh 1080p. >> "D:\ProjekAntigravity\ENCLip\Core_Data\autoclipper_4am.log"
