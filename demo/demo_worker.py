"""
Safe Demo Worker Process for Zombie Task Purger.
Simulates realistic application behavior with real Windows PIDs, RAM allocation, and I/O rates
without touching any user applications.
"""

import os
import sys
import time
import argparse

def run_chrome_download(work_dir: str):
    """Simulates active file download in Google Chrome (high I/O rate > 200 KB/s)."""
    os.makedirs(work_dir, exist_ok=True)
    temp_file = os.path.join(work_dir, "demo_chrome_download.bin")
    chunk = b"Z" * (64 * 1024)  # 64 KB chunk
    try:
        with open(temp_file, "wb") as f:
            while True:
                f.write(chunk)
                f.flush()
                time.sleep(0.25)  # ~250 KB/s active download write rate
                if os.path.getsize(temp_file) > 10 * 1024 * 1024:  # Cap at 10 MB and loop
                    f.seek(0)
    except Exception:
        pass

def run_whatsapp_closed():
    """Simulates WhatsApp Desktop lingering in system tray after window close."""
    # Allocate realistic memory (~80 MB)
    mem_holder = bytearray(80 * 1024 * 1024)
    while True:
        time.sleep(1.0)

def run_oracle_db():
    """Simulates Oracle Database engine (oracle.exe) running idle in background."""
    # Allocate realistic memory (~180 MB)
    mem_holder = bytearray(180 * 1024 * 1024)
    while True:
        time.sleep(1.0)

def run_node_server():
    """Simulates forgotten Node.js background dev server."""
    # Allocate realistic memory (~75 MB)
    mem_holder = bytearray(75 * 1024 * 1024)
    while True:
        time.sleep(1.0)

def run_python_script():
    """Simulates orphaned background Python worker script."""
    # Allocate realistic memory (~50 MB)
    mem_holder = bytearray(50 * 1024 * 1024)
    while True:
        time.sleep(1.0)

def run_spotify_audio():
    """Simulates Spotify playing audio in background."""
    mem_holder = bytearray(60 * 1024 * 1024)
    while True:
        time.sleep(1.0)

def main():
    parser = argparse.ArgumentParser(description="Zombie Task Purger Demo Worker")
    parser.add_argument("--role", required=True, choices=[
        "chrome_download", "whatsapp_closed", "oracle_db", 
        "node_server", "python_script", "spotify_audio"
    ])
    parser.add_argument("--work-dir", default=os.path.join(os.environ.get("LOCALAPPDATA", "."), "ZombieDataPurgerDemo"))
    args = parser.parse_args()

    if args.role == "chrome_download":
        run_chrome_download(args.work_dir)
    elif args.role == "whatsapp_closed":
        run_whatsapp_closed()
    elif args.role == "oracle_db":
        run_oracle_db()
    elif args.role == "node_server":
        run_node_server()
    elif args.role == "python_script":
        run_python_script()
    elif args.role == "spotify_audio":
        run_spotify_audio()

if __name__ == "__main__":
    main()
