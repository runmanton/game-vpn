"""
GameVPN - Launch Client
=======================
Double-click this file or run: python run_client.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.gui import main

if __name__ == "__main__":
    main()
