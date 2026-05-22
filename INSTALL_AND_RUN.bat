@echo off
title GameVPN
color 0B

echo ==================================================
echo   GameVPN - Install and Run
echo ==================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
pip install PyQt6 websockets --quiet
echo       [OK] Done
echo.

echo [2/2] Starting GameVPN...
echo.
python run_client.py
