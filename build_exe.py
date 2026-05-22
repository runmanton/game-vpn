"""
GameVPN - Build Windows EXE
============================
Creates a standalone .exe file that friends can run without installing Python.

Requirements:
    pip install pyinstaller

Usage:
    python build_exe.py
"""
import subprocess
import sys

def build():
    print("Building GameVPN.exe ...")
    print("This may take a few minutes...\n")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=GameVPN",
        "--onefile",
        "--windowed",           # No console window
        "--noconfirm",
        "--clean",
        # Add icon if available
        # "--icon=assets/icon.ico",
        "--add-data=engine;engine",
        "--add-data=client;client",
        "--add-data=server;server",
        "--hidden-import=websockets",
        "--hidden-import=PyQt6",
        "run_client.py",
    ]

    result = subprocess.run(cmd, cwd=".")
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("  Build successful!")
        print("  EXE location: dist/GameVPN.exe")
        print("  Share this file with your friends!")
        print("=" * 50)
    else:
        print("\nBuild failed! Make sure PyInstaller is installed:")
        print("  pip install pyinstaller")

if __name__ == "__main__":
    build()
