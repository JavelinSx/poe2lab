@echo off
rem poe2lab: double-click to set up (first time) and start. See scripts\bootstrap.ps1.
rem The interface runs in the background with no window; stop it with its "Stop poe2lab" button.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
if errorlevel 1 pause
