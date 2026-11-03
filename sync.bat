@echo off
rem Double-click to refresh the Sheet from Shopify and Prodigi.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" sync
pause
