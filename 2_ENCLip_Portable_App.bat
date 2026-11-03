@echo off
title ENCLip Studio v2.0 (Portable Edition)
cd /d "%~dp0portable"
if exist "ENCLip.exe" (
    start "" "ENCLip.exe"
) else (
    cd /d "%~dp0"
    start "" "C:\Python314\pythonw.exe" -m Desktop_UI.desktop_gui
)
