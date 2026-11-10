"""
Demo Tasks Manager for Zombie Task Purger.
Controls lifecycle of simulated application processes for college viva demonstrations.
Ensures zero impact on real laptop applications.
"""

import os
import sys
import subprocess
import psutil
from typing import Dict, List, Optional
from config import DEMO_BASE_DIR

DEMO_ROLES_METADATA = {
    "chrome_download": {
        "display_name": "Google Chrome (Active Download)",
        "simulated_process_name": "chrome.exe",
        "category": "Browser",
        "simulated_window": "Minimized to Taskbar",
        "has_active_audio": False,
        "is_foreground": False,
        "simulated_idle_minutes": 5,
        "expected_action": "PROTECTED (Active Download > 50 KB/s)",
    },
    "whatsapp_closed": {
        "display_name": "WhatsApp Desktop (Closed to Tray)",
        "simulated_process_name": "WhatsApp.exe",
        "category": "Messaging / Tray",
        "simulated_window": "Closed to Tray (0 Visible Windows)",
        "has_active_audio": False,
        "is_foreground": False,
        "simulated_idle_minutes": 52,
        "expected_action": "POTENTIAL ZOMBIE (Auto-Freeze Eligible)",
    },
    "oracle_db": {
        "display_name": "Oracle Database Engine (XE Service)",
        "simulated_process_name": "oracle.exe",
        "category": "Database Service",
        "simulated_window": "Background Daemon (0 Windows)",
        "has_active_audio": False,
        "is_foreground": False,
        "simulated_idle_minutes": 2880,  # 2 days idle
        "expected_action": "POTENTIAL ZOMBIE (Auto-Freeze Eligible)",
    },
    "node_server": {
        "display_name": "Node.js Background Dev Server",
        "simulated_process_name": "node.exe",
        "category": "Dev Runtime",
        "simulated_window": "Hidden Console",
        "has_active_audio": False,
        "is_foreground": False,
        "simulated_idle_minutes": 180,  # 3 hours idle
        "expected_action": "POTENTIAL ZOMBIE (Auto-Freeze Eligible)",
    },
    "python_script": {
        "display_name": "Python Orphaned Worker (worker.py)",
        "simulated_process_name": "python.exe",
        "category": "Dev Runtime",
        "simulated_window": "Background Process",
        "has_active_audio": False,
        "is_foreground": False,
        "simulated_idle_minutes": 120,  # 2 hours idle
        "expected_action": "POTENTIAL ZOMBIE (Auto-Freeze Eligible)",
    },
    "spotify_audio": {
        "display_name": "Spotify Music Player (Audio Playing)",
        "simulated_process_name": "Spotify.exe",
        "category": "Media",
        "simulated_window": "Minimized to Taskbar",
        "has_active_audio": True,
        "is_foreground": False,
        "simulated_idle_minutes": 15,
        "expected_action": "PROTECTED (Active Audio Stream)",
    },
}

class DemoTaskManager:
    """Manages the isolated set of safe demo processes."""
    _active_workers: Dict[str, subprocess.Popen] = {}

    @classmethod
    def spawn_all_demo_tasks(cls) -> List[dict]:
        """Spawns 6 safe mock worker processes."""
        cls.terminate_all_demo_tasks()
        os.makedirs(DEMO_BASE_DIR, exist_ok=True)
        worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_worker.py")

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        results = []
        for role, meta in DEMO_ROLES_METADATA.items():
            try:
                proc = subprocess.Popen(
                    [sys.executable, worker_script, "--role", role, "--work-dir", DEMO_BASE_DIR],
                    creationflags=creation_flags
                )
                cls._active_workers[role] = proc
                results.append({
                    "role": role,
                    "pid": proc.pid,
                    **meta
                })
            except Exception as e:
                print(f"[DemoTaskManager] Failed to spawn {role}: {e}")

        return results

    @classmethod
    def get_active_demo_tasks(cls) -> Dict[str, dict]:
        """Returns currently alive demo tasks with their metadata."""
        alive = {}
        for role, proc in list(cls._active_workers.items()):
            if proc.poll() is None:
                meta = DEMO_ROLES_METADATA.get(role, {})
                alive[role] = {
                    "role": role,
                    "pid": proc.pid,
                    "popen": proc,
                    **meta
                }
            else:
                del cls._active_workers[role]
        return alive

    @classmethod
    def terminate_all_demo_tasks(cls):
        """Cleanly terminates all demo worker processes."""
        for role, proc in list(cls._active_workers.items()):
            try:
                if proc.poll() is None:
                    # If suspended, resume first so it can handle termination cleanly
                    try:
                        p = psutil.Process(proc.pid)
                        p.resume()
                    except Exception:
                        pass
                    proc.terminate()
                    proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        cls._active_workers.clear()

        # Clean up any demo temp download file
        temp_file = os.path.join(DEMO_BASE_DIR, "demo_chrome_download.bin")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
