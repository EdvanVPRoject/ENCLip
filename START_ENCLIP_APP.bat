@echo off
title ENCLip Desktop App
cd /d "%~dp0"
echo =======================================================
echo               MEMBUKA ENCLIP DESKTOP APP
echo =======================================================
echo.
if exist "ENCLip.exe" (
    start "" "ENCLip.exe"
) else (
    C:\Python314\python.exe -m Desktop_UI.desktop_gui
)
