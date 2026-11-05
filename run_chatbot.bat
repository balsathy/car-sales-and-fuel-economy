@echo off
setlocal
cd /d "%~dp0"

if not defined PORT set "PORT=8001"

echo [1/3] Downloading 2025 sales...
call python download_data.py sales 2025
if errorlevel 1 goto :failed

echo [2/3] Downloading 2026 sales...
call python download_data.py sales 2026
if errorlevel 1 goto :failed

echo [3/3] Downloading EPA mileage...
call python download_data.py epa
if errorlevel 1 goto :failed

echo All downloads completed. Starting the chatbot on port %PORT%...
start "Vehicle Data Chatbot Server" /D "%~dp0" cmd /k "set PORT=%PORT% && python app.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/"
echo The chatbot is opening at http://127.0.0.1:%PORT%/
exit /b 0

:failed
echo A download failed. The chatbot was not started.
pause
exit /b 1
