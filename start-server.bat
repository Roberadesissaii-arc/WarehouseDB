@echo off
REM Start WarehouseDB so ESP32 robots on your Wi-Fi can connect (not localhost-only).
set HOST=0.0.0.0
set PORT=8000
cd /d "%~dp0"
python run.py
pause
