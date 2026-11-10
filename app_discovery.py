import os
from pathlib import Path
from config import (
    DEMO_BASE_DIR,
    APP_DEFINITIONS,
    CACHE_LAYOUTS,
    MODE_SAFE_DEMO,
    MODE_REAL_SYSTEM_READONLY,
    MODE_REAL_SYSTEM_ACTIVE,
    KNOWN_CACHE_DIR_KEYWORDS,
)
from utils import canonicalize_path, is_symlink_or_reparse_point

class ApplicationDiscovery:
    """
    Module 1 / Task 1.1: Application Discovery
    Activity 1.1.1: Browser and Electron application identification.
    Activity 1.1.2: Supported cache directory detection.
    Activity 1.1.3: Application path verification.
    """

    @staticmethod
    def identify_applications(mode: str) -> list:
        """
        Activity 1.1.1: Browser and Electron application identification.
        Discovers target Browser and Electron applications according to active mode.
        """
        if mode == MODE_SAFE_DEMO:
            return ApplicationDiscovery.discover_demo_applications()
        elif mode in (MODE_REAL_SYSTEM_READONLY, MODE_REAL_SYSTEM_ACTIVE):
            return ApplicationDiscovery.discover_real_system_applications()
        else:
            return []

    @staticmethod
    def discover_demo_applications():
        """Returns application targets configured inside the isolated Demo sandbox."""
        chrome_demo_path = os.path.join(DEMO_BASE_DIR, "Chrome_Demo")
        electron_demo_path = os.path.join(DEMO_BASE_DIR, "Electron_Demo")

        return [
            {
                "name": "Chrome Demo Application",
                "app_id": "chrome_demo",
                "path": chrome_demo_path,
                "process_name": "chrome.exe",
                "type": "Browser (Demo Sandbox)",
                "scan_supported": True,
                "exists": os.path.exists(chrome_demo_path)
            },
            {
                "name": "Electron Demo Application",
                "app_id": "electron_demo",
                "path": electron_demo_path,
                "process_name": "electron.exe",
                "type": "Electron (Demo Sandbox)",
                "scan_supported": True,
                "exists": os.path.exists(electron_demo_path)
            }
        ]

    @staticmethod
    def discover_real_system_applications():
        """Inspects local Windows user directories for installed Browser and Electron apps."""
        discovered = []
        for app_name, info in APP_DEFINITIONS.items():
            path = info["relative_path"]
            exists = os.path.exists(path)
            discovered.append({
                "name": app_name,
                "app_id": app_name.lower().replace(" ", "_"),
                "path": path,
                "process_name": info["process_name"],
                "type": info["type"],
                "scan_supported": CACHE_LAYOUTS.get(app_name, {}).get("kind") != "disabled",
                "exists": exists
            })
        return discovered

    @classmethod
    def get_applications_for_mode(cls, mode: str):
        """Backward-compatible entry point for application discovery."""
        return cls.identify_applications(mode)

    @staticmethod
    def detect_supported_cache_directories(app_info: dict) -> list:
        """
        Activity 1.1.2: Supported cache directory detection.
        Inspects application root directory and finds verified cache/temp subdirectories.
        """
        target_path = app_info.get("path", "")
        app_name = app_info.get("name", "")
        detected_cache_dirs = []

        if not target_path or not os.path.exists(target_path):
            return detected_cache_dirs

        layout = CACHE_LAYOUTS.get(app_name, {})
        kind = layout.get("kind", "")

        # Safe inspection of top-level directories
        try:
            for entry in os.scandir(target_path):
                if entry.is_dir(follow_symlinks=False):
                    entry_name_lower = entry.name.lower()
                    # Check for direct cache matches
                    is_cache = any(kw in entry_name_lower for kw in KNOWN_CACHE_DIR_KEYWORDS)
                    
                    if is_cache:
                        detected_cache_dirs.append({
                            "directory_name": entry.name,
                            "full_path": entry.path,
                            "type": "Direct Cache Directory",
                            "exists": True
                        })
                    elif kind == "browser_profile" and (entry_name_lower in {"default", "guest profile", "system profile"} or entry_name_lower.startswith("profile ")):
                        # Look inside browser profile for cache folders
                        try:
                            for sub_entry in os.scandir(entry.path):
                                if sub_entry.is_dir(follow_symlinks=False):
                                    sub_name_lower = sub_entry.name.lower()
                                    if any(kw in sub_name_lower for kw in KNOWN_CACHE_DIR_KEYWORDS):
                                        detected_cache_dirs.append({
                                            "directory_name": f"{entry.name}/{sub_entry.name}",
                                            "full_path": sub_entry.path,
                                            "type": "Profile Cache Directory",
                                            "exists": True
                                        })
                        except (PermissionError, OSError):
                            pass
        except (PermissionError, OSError):
            pass

        return detected_cache_dirs

    @staticmethod
    def verify_application_path(path_str: str) -> dict:
        """
        Activity 1.1.3: Application path verification.
        Validates path existence, readability, canonicalization, and ensures it is
        free of symlinks, junction points, or unauthorized reparse points.
        """
        if not path_str:
            return {"verified": False, "error": "Empty path string provided."}

        canonical = canonicalize_path(path_str)
        exists = os.path.exists(canonical)
        if not exists:
            return {
                "verified": False,
                "canonical_path": canonical,
                "exists": False,
                "error": "Directory does not exist on disk."
            }

        reparse = is_symlink_or_reparse_point(canonical)
        if reparse:
            return {
                "verified": False,
                "canonical_path": canonical,
                "exists": True,
                "is_reparse": True,
                "error": "Path contains a symbolic link, junction point, or reparse point (Security Denied)."
            }

        readable = os.access(canonical, os.R_OK)
        return {
            "verified": readable,
            "canonical_path": canonical,
            "exists": True,
            "is_reparse": False,
            "readable": readable,
            "error": None if readable else "Permission denied for reading directory."
        }
