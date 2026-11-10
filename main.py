import sys
import os
from gui import launch_gui
from config import APP_NAME, APP_VERSION, ACADEMIC_MODULE_NAME

def main():
    print("=" * 60)
    print(f"  {APP_NAME}")
    print(f"  Version: {APP_VERSION}")
    print(f"  Academic Main Module: {ACADEMIC_MODULE_NAME}")
    print("=" * 60)
    print("  Status: Launching Desktop Graphical Interface...")
    print("  Offline Mode: Active (No Internet Required)")
    print("=" * 60)
    
    launch_gui()

if __name__ == "__main__":
    main()
