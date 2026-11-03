@echo off
title Install ENCLip Studio v2.0 (Native Windows Setup)
cd /d "%~dp0"
if exist "Native_Installer\ENCLip_Setup_v2.0_Terbaru.exe" (
    echo Membuka Windows Setup Installer (.exe)...
    start "" "Native_Installer\ENCLip_Setup_v2.0_Terbaru.exe"
) else (
    start "" "C:\Python314\pythonw.exe" -m Desktop_UI.desktop_gui
)
