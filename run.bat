@echo off
rem Double-click to open the LulaMacaroni back office. Options: run.bat sync ^| demo ^| check
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
if errorlevel 1 pause
