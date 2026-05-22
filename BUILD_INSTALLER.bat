@echo off
chcp 437 >nul 2>&1
cd /d "%~dp0"
title GameVPN - Full Installer Builder
color 0B

echo ==================================================
echo   GameVPN - Full Installer Builder
echo ==================================================
echo.
echo   This script will:
echo     1. Build GameVPN.exe (PyInstaller)
echo     2. Download WireGuard MSI
echo     3. Create GameVPN_Setup.exe (Inno Setup)
echo.
echo   Requirements:
echo     - Python 3.10+
echo     - Inno Setup 6 (iscc.exe)
echo.
echo   Press any key to start, or Ctrl+C to cancel.
pause >nul
echo.

:: Step 0: Check tools
echo [0/4] Checking required tools...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Python not found. Installing via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo   [!] Python installed. Please close this window and run again.
    pause
    exit /b 0
)
echo   [OK] Python found

:: Check Inno Setup
set ISCC_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC_PATH%"=="" (
    echo   [!] Inno Setup 6 not found. Installing via winget...
    winget install JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
    echo.
    echo   Checking again...
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    )
    if "%ISCC_PATH%"=="" (
        echo   [ERROR] Inno Setup still not found.
        echo   Download manually: https://jrsoftware.org/isdl.php
        pause
        exit /b 1
    )
)
echo   [OK] Inno Setup found
echo.

:: Step 1: Build GameVPN.exe
echo [1/4] Building GameVPN.exe with PyInstaller...
echo       (This takes 1-3 minutes)
echo.

pip install PyQt6 websockets pyinstaller --quiet

if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

pyinstaller --name=GameVPN --onefile --windowed --noconfirm --clean --add-data "engine;engine" --add-data "client;client" --hidden-import=websockets --hidden-import=websockets.legacy --hidden-import=websockets.legacy.client --hidden-import=PyQt6.QtWidgets --hidden-import=PyQt6.QtCore --hidden-import=PyQt6.QtGui --hidden-import=asyncio --hidden-import=json --hidden-import=secrets --hidden-import=struct --hidden-import=socket run_client.py

if not exist "dist\GameVPN.exe" (
    echo   [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)
echo   [OK] GameVPN.exe built successfully
echo.

:: Step 2: Download WireGuard MSI
echo [2/4] Downloading WireGuard installer...

if not exist "installer" mkdir installer

if not exist "installer\wireguard-amd64.msi" (
    echo   Downloading from download.wireguard.com ...
    curl -L -o "installer\wireguard-amd64.msi" "https://download.wireguard.com/windows-client/wireguard-installer.exe"
    if errorlevel 1 (
        echo.
        echo   [WARNING] Auto-download failed. Trying PowerShell...
        powershell -Command "Invoke-WebRequest -Uri 'https://download.wireguard.com/windows-client/wireguard-amd64-0.5.3.msi' -OutFile 'installer\wireguard-amd64.msi'"
        if not exist "installer\wireguard-amd64.msi" (
            echo   [ERROR] Download failed. Please download manually.
            echo   Go to https://www.wireguard.com/install/
            pause
            exit /b 1
        )
    )
)
echo   [OK] WireGuard installer ready
echo.

:: Step 3: Create icon if not exists
echo [3/4] Preparing assets...

if not exist "assets" mkdir assets
if not exist "assets\icon.ico" (
    echo   Creating default icon...
    python -c "from PIL import Image, ImageDraw, ImageFont; import os; sizes=[16,32,48,64,128,256]; imgs=[]; [exec('img=Image.new(chr(82)+chr(71)+chr(66)+chr(65),(s,s),(0,0,0,0)); d=ImageDraw.Draw(img); m=s//8; d.rounded_rectangle([m,m,s-m,s-m],radius=s//5,fill=(0,212,255)); imgs.append(img)') for s in sizes]; os.makedirs('assets',exist_ok=True); imgs[0].save('assets/icon.ico',format='ICO',sizes=[(s,s) for s in sizes],append_images=imgs[1:]); print('  [OK] Icon created')" 2>nul
    if not exist "assets\icon.ico" (
        echo   [SKIP] Icon creation failed, using default
    )
)

:: Create wizard images for Inno Setup
if not exist "installer\wizard_image.bmp" (
    python -c "from PIL import Image; img=Image.new('RGB',(164,314),(26,26,46)); img.save('installer/wizard_image.bmp','BMP'); small=Image.new('RGB',(55,58),(26,26,46)); small.save('installer/wizard_small.bmp','BMP'); print('  [OK] Wizard images created')" 2>nul
)
echo   [OK] Assets ready
echo.

:: Step 4: Compile Installer
echo [4/4] Building GameVPN_Setup.exe with Inno Setup...
echo.

"%ISCC_PATH%" "installer\GameVPN_Setup.iss"

if errorlevel 1 (
    echo.
    echo   [ERROR] Inno Setup compilation failed!
    echo   Check the .iss script for errors.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   [OK] INSTALLER BUILD SUCCESSFUL!
echo.
echo   Output: installer\output\GameVPN_Setup.exe
echo.
echo   This single file includes:
echo     - GameVPN application
echo     - WireGuard (auto-install)
echo     - User Manual (PDF)
echo     - Desktop shortcut
echo.
echo   Send GameVPN_Setup.exe to your friends!
echo ==================================================
echo.

if exist "installer\output" explorer "installer\output"

pause
