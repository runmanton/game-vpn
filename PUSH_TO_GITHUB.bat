@echo off
chcp 437 >nul 2>&1
cd /d "%~dp0"
title GameVPN - Push to GitHub
color 0B

echo ==================================================
echo   GameVPN - Push to GitHub
echo ==================================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Git is not installed!
    echo   Download from: https://git-scm.com/download/win
    echo   Or run: winget install Git.Git
    pause
    exit /b 1
)
echo   [OK] Git found
echo.

if exist ".git" (
    echo   [INFO] Removing old .git folder...
    rmdir /s /q .git
)

echo [1/4] Initializing git repository...
git init -b main
echo.

echo [2/4] Adding all files...
git add -A
git status
echo.

echo [3/4] Creating first commit...
git commit -m "Initial commit: GameVPN - Virtual LAN for Gaming"
echo.

echo [4/4] Pushing to GitHub...
git remote add origin https://github.com/runmanton/game-vpn.git
git push -u origin main

if errorlevel 1 (
    echo.
    echo   [NOTE] If push failed, you may need to:
    echo     1. Create repo "game-vpn" on GitHub first
    echo        Go to: https://github.com/new
    echo        Repository name: game-vpn
    echo        Click "Create repository"
    echo     2. Run this script again
    echo.
    echo   If authentication failed:
    echo     Run: git config --global user.name "runmanton"
    echo     Run: git config --global user.email "your-email"
    echo.
)

echo.
echo ==================================================
echo   Done! Check: https://github.com/runmanton/game-vpn
echo ==================================================
pause
