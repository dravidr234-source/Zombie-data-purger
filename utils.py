import os
import stat
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import logging

def compute_file_sha256(file_path: str) -> str:
    """
    Computes SHA-256 checksum for audit and integrity verification.
    Reads file in 64 KB chunks to handle large files efficiently.
    Returns empty string if file cannot be read.
    """
    if not os.path.isfile(file_path):
        return ""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def is_symlink_or_reparse_point(path_str: str) -> bool:
    """
    Detects if path or any of its parent components is a symbolic link,
    junction point, or NTFS reparse point.
    """
    try:
        p = Path(path_str).absolute()
        for part in (p, *p.parents):
            try:
                st = part.lstat()
                attrs = getattr(st, "st_file_attributes", 0)
                reparse = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
                if stat.S_ISLNK(st.st_mode) or reparse:
                    return True
            except FileNotFoundError:
                continue
        return False
    except (OSError, RuntimeError, ValueError):
        return True

def canonicalize_path(path_str: str) -> str:
    """
    Resolves canonical absolute path, normalizing case on Windows.
    """
    try:
        return os.path.normcase(os.path.abspath(os.path.realpath(path_str)))
    except Exception:
        return os.path.normcase(os.path.abspath(path_str))

def get_file_type_category(file_path: str) -> dict:
    """
    Categorizes file type based on extension and filename patterns.
    Returns category name, extension, and risk profile.
    """
    fname = os.path.basename(file_path).lower()
    _, ext = os.path.splitext(fname)
    ext = ext.lower()

    if ext in {".tmp", ".temp", ".bak", ".old", ".dmp", ".chk"}:
        return {"category": "Temporary Artifact", "extension": ext, "disposable": True, "badge": "TEMP"}
    elif ext in {".cache", ".dat"} or "cache" in fname:
        return {"category": "Web / HTTP Cache", "extension": ext, "disposable": True, "badge": "CACHE"}
    elif ext in {".log", ".txt"} or "log" in fname:
        return {"category": "Application Log", "extension": ext, "disposable": True, "badge": "LOG"}
    elif "gpu" in fname or "shader" in fname or ext in {".bin"}:
        return {"category": "Compiled GPU / Shader", "extension": ext, "disposable": True, "badge": "SHADER"}
    elif ext in {".db", ".sqlite", ".sqlite3", ".ldb"} or "cookies" in fname or "session" in fname:
        return {"category": "Database / Profile State", "extension": ext, "disposable": False, "badge": "PROTECTED"}
    elif ext in {".key", ".pem", ".crt", ".auth", ".credentials"}:
        return {"category": "Security Credential", "extension": ext, "disposable": False, "badge": "IMMUNE"}
    else:
        return {"category": "General Application File", "extension": ext, "disposable": False, "badge": "GENERAL"}

def is_file_exclusively_accessible(file_path: str) -> bool:
    """Fail closed unless the file can be opened without sharing (Windows)."""
    if not os.path.isfile(file_path):
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create_file.restype = wintypes.HANDLE
        handle = create_file(os.path.abspath(file_path), 0x80000000, 0, None, 3, 0x00200000, None)
        invalid = ctypes.c_void_p(-1).value
        if handle == invalid:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        with open(file_path, "rb") as stream:
            stream.read(1)
        return True
    except (PermissionError, OSError):
        return False

def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable strings (KB, MB, GB)."""
    if size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}" if unit != 'B' else f"{int(size_bytes)} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def calculate_file_age_days(mtime_timestamp: float) -> int:
    """Calculate file age in days based on modification timestamp."""
    try:
        file_datetime = datetime.fromtimestamp(mtime_timestamp)
        now = datetime.now()
        delta = now - file_datetime
        return max(0, delta.days)
    except Exception:
        return 0

def format_timestamp(timestamp: float) -> str:
    """Convert POSIX timestamp to human readable string."""
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Unknown"

def is_file_accessible(file_path: str) -> bool:
    """Check if file can be opened for reading without permission/lock errors."""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'rb') as f:
            f.read(1)
        return True
    except (PermissionError, OSError):
        return False

def is_path_inside_allowed_directory(target_path: str, allowed_root: str) -> bool:
    """
    ABSOLUTE SAFETY FUNCTION:
    Enforces that target_path is strictly inside allowed_root directory.
    Uses resolved absolute paths to prevent symlink bypasses or path traversal.
    """
    try:
        resolved_target = Path(target_path).resolve()
        resolved_root = Path(allowed_root).resolve()
        return resolved_target.is_relative_to(resolved_root)
    except (ValueError, Exception):
        return False
