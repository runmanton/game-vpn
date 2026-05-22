@echo off
title GameVPN Builder
color 0B

echo ==================================================
echo   GameVPN - Auto Build Tool
echo   Install dependencies and build .exe
echo ==================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Python not found. Installing via winget...
    echo.
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [ERROR] Failed to install Python via winget.
        echo Please install manually: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo.
    echo [OK] Python installed!
    echo.
    echo *** IMPORTANT ***
    echo Close this window and double-click BUILD.bat again.
    echo Python PATH needs a new terminal to take effect.
    echo.
    pause
    exit /b 0
)

echo [1/4] Installing dependencies...
pip install PyQt6 websockets pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo       [OK] Dependencies installed
echo.

echo [2/4] Cleaning old build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "GameVPN.spec" del "GameVPN.spec"
echo       [OK] Cleaned
echo.

echo [3/4] Building GameVPN.exe ...
echo       (This takes 1-3 minutes, please wait)
echo.

pyinstaller ^
    --name=GameVPN ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "engine;engine" ^
    --add-data "client;client" ^
    --hidden-import=websockets ^
    --hidden-import=websockets.legacy ^
    --hidden-import=websockets.legacy.client ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=asyncio ^
    --hidden-import=json ^
    --hidden-import=secrets ^
    --hidden-import=struct ^
    --hidden-import=socket ^
    run_client.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    echo Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   [OK] BUILD SUCCESSFUL!
echo.
echo   EXE file: dist\GameVPN.exe
echo.
echo   Send GameVPN.exe to your friends!
echo   (No Python needed on their PC)
echo ==================================================
echo.

:: Open the dist folder
explorer "dist"

pause
