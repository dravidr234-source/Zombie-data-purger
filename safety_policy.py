"""Central fail-closed authorization for file-changing operations."""
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from config import (
    APP_DEFINITIONS, CACHE_LAYOUTS, DEMO_BASE_DIR, DEMO_QUARANTINE_DIR, DEMO_SAMPLE_RELATIVE_PATHS, REAL_QUARANTINE_DIR,
    MODE_SAFE_DEMO, MODE_REAL_SYSTEM_ACTIVE, MODE_REAL_SYSTEM_READONLY,
    SYSTEM_PROTECTED_ROOTS, PROTECTED_FILE_PATTERNS, PROTECTED_EXTENSIONS,
)


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    code: str
    reason: str


class SafetyPolicy:
    """
    Module 2 / Task 2.3 – Safety and Decision Engine
    Activity 2.3.1: Protected file and directory detection.
    Activity 2.3.2: Symbolic link, reparse point and file identity validation.
    Activity 2.3.3: Policy-based cleanup eligibility evaluation.
    
    Single fail-closed authorization point.
    Uncertain or incomplete inputs are denied.
    A high zombie score alone NEVER authorizes cleanup.
    """
    paused = False
    auto_quarantine_enabled = False
    real_purge_enabled = False
    demo_purge_enabled = False
    safe_extensions = {".tmp", ".temp", ".cache", ".log", ".dmp"}
    cache_components = {"cache", "code cache", "gpucache", "gpu cache", "dawncache", "shadercache", "crashpad", "logs", "temp", "tmp"}

    @classmethod
    def approved_cache_index(cls, app_name, relative_parts):
        """Return the cache-directory position for a reviewed application layout."""
        parts = [str(part).casefold() for part in relative_parts]
        if "demo" in (app_name or "").casefold():
            return next((i for i, part in enumerate(parts) if part in cls.cache_components), None)
        layout = CACHE_LAYOUTS.get(app_name, {"kind": "disabled"})
        if layout.get("kind") == "browser_profile":
            profile_names = {"default", "guest profile", "system profile"}
            if len(parts) >= 2 and (parts[0] in profile_names or parts[0].startswith("profile ")) and parts[1] in cls.cache_components:
                return 1
            return None
        if layout.get("kind") == "direct":
            approved = {name.casefold() for name in layout.get("directories", set())}
            if parts and parts[0] in approved:
                return 0
        return None

    @staticmethod
    def _contains_reparse_point(path):
        try:
            candidate = Path(path).absolute()
            for part in (candidate, *candidate.parents):
                try:
                    st = part.lstat()
                    attrs = getattr(st, "st_file_attributes", 0)
                    if stat.S_ISLNK(st.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                        return True
                except FileNotFoundError:
                    continue
            return False
        except (OSError, RuntimeError, ValueError):
            return True

    @classmethod
    def is_protected_target(cls, file_path: str) -> dict:
        """
        Activity 2.3.1: Protected file and directory detection.
        Detects if path targets passwords, cookies, history, bookmarks, sessions,
        IndexedDB, credentials, or protected Windows OS / User personal directories.
        """
        if not file_path:
            return {"protected": True, "code": "EMPTY_PATH", "reason": "Path is empty."}
        
        path_str = str(file_path).casefold()
        fname = os.path.basename(file_path).casefold()
        _, ext = os.path.splitext(fname)

        # 1. System Roots Check
        for root in SYSTEM_PROTECTED_ROOTS:
            if root and cls._inside(Path(file_path), root):
                return {
                    "protected": True,
                    "code": "SYSTEM_PROTECTED_ROOT",
                    "reason": f"Path is inside protected system directory ('{root}'). Strict zero-touch immunity."
                }

        # 2. File Pattern Whitelist
        for pattern in PROTECTED_FILE_PATTERNS:
            if pattern in fname or pattern in path_str:
                return {
                    "protected": True,
                    "code": "PROTECTED_DATA_PATTERN",
                    "reason": f"Matches critical data pattern '{pattern}' (browser credential/cookie/session/database)."
                }

        # 3. Extension Protection
        if ext in PROTECTED_EXTENSIONS:
            return {
                "protected": True,
                "code": "PROTECTED_EXTENSION",
                "reason": f"Extension '{ext}' is protected credential or cryptographic material."
            }

        return {
            "protected": False,
            "code": "SAFE_PATTERN",
            "reason": "Path does not match any protected database or system root rule."
        }

    @classmethod
    def validate_symlink_and_reparse_point(cls, file_path: str) -> dict:
        """
        Activity 2.3.2: Symbolic link, reparse point and file identity validation.
        Inspects file and all ancestor directories for symlinks, junctions, and reparse points.
        """
        if not file_path:
            return {"is_reparse": True, "safe": False, "reason": "Empty path."}
        
        is_reparse = cls._contains_reparse_point(file_path)
        if is_reparse:
            return {
                "is_reparse": True,
                "safe": False,
                "reason": "Path or parent directory contains a symbolic link, directory junction, or reparse point."
            }
        
        return {
            "is_reparse": False,
            "safe": True,
            "reason": "Path is free of symbolic links and reparse points."
        }

    @classmethod
    def evaluate_cleanup_eligibility(cls, operation: str, source: str, destination: str = None,
                                     mode: str = None, metadata: dict = None, app_name: str = None,
                                     process_running: bool = None, retention_days: int = None,
                                     age_days: int = None, user_purge_enabled: bool = False,
                                     automatic: bool = False) -> PolicyDecision:
        """
        Activity 2.3.3: Policy-based cleanup eligibility evaluation.
        Central fail-closed decision ensuring that a high zombie score alone NEVER authorizes cleanup.
        """
        return cls.authorize(
            operation=operation,
            source=source,
            destination=destination,
            mode=mode,
            metadata=metadata,
            app_name=app_name,
            process_running=process_running,
            retention_days=retention_days,
            age_days=age_days,
            user_purge_enabled=user_purge_enabled,
            automatic=automatic,
        )

    @classmethod
    def authorize(cls, operation, source, destination=None, mode=None, metadata=None,
                  app_name=None, process_running=None, retention_days=None,
                  age_days=None, user_purge_enabled=False, automatic=False):
        metadata = metadata or {}
        if cls.paused:
            return PolicyDecision(Decision.DENY, "GLOBAL_PAUSE", "Global pause is active.")
        if operation not in {"inspect", "quarantine", "restore", "purge", "demo_create"}:
            return PolicyDecision(Decision.DENY, "UNKNOWN_OPERATION", "Operation type is not authorized.")
        if mode not in (MODE_SAFE_DEMO, MODE_REAL_SYSTEM_ACTIVE, MODE_REAL_SYSTEM_READONLY):
            return PolicyDecision(Decision.DENY, "INVALID_MODE", "Operating mode is unknown.")
        if mode == MODE_REAL_SYSTEM_READONLY and operation != "inspect":
            return PolicyDecision(Decision.DENY, "READ_ONLY_MODE", "Read-only mode blocks file changes.")
        if not source:
            return PolicyDecision(Decision.DENY, "MISSING_SOURCE", "Source path is required.")
        if cls._contains_reparse_point(source):
            return PolicyDecision(Decision.DENY, "REPARSE_POINT", "Source path includes a symbolic link or reparse point.")
        if operation == "demo_create":
            if mode != MODE_SAFE_DEMO or not cls._inside(Path(source), DEMO_BASE_DIR):
                return PolicyDecision(Decision.DENY, "DEMO_CREATE_SCOPE", "Synthetic data may be created only under the demo sandbox.")
            if metadata.get("root") is True:
                if Path(source).absolute() != Path(DEMO_BASE_DIR).absolute():
                    return PolicyDecision(Decision.DENY, "DEMO_CREATE_ROOT", "Only the configured demo root may be initialized.")
                return PolicyDecision(Decision.ALLOW, "DEMO_ROOT_ALLOWED", "Configured demo root is approved.")
            try:
                rel = str(Path(source).resolve().relative_to(Path(DEMO_BASE_DIR).resolve())).replace("\\", "/")
            except (OSError, ValueError):
                return PolicyDecision(Decision.DENY, "DEMO_CREATE_SCOPE", "Synthetic path could not be resolved under the demo root.")
            if rel not in DEMO_SAMPLE_RELATIVE_PATHS or Path(source).exists():
                return PolicyDecision(Decision.DENY, "DEMO_SAMPLE_NOT_APPROVED", "Only missing, predefined synthetic sample files may be created.")
            return PolicyDecision(Decision.ALLOW, "DEMO_SAMPLE_ALLOWED", "Predefined synthetic sample path is approved.")
        try:
            src = Path(source).resolve(strict=True)
            if not src.is_file() or src.is_symlink():
                return PolicyDecision(Decision.DENY, "NOT_REGULAR_FILE", "Source must be a regular file.")
            # Reject reparse points/symlink components rather than trusting resolved paths.
            cur = Path(source).absolute()
            for part in (cur, *cur.parents):
                try:
                    mode_bits = part.lstat().st_mode
                    attrs = getattr(part.lstat(), "st_file_attributes", 0)
                    reparse = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
                    if stat.S_ISLNK(mode_bits) or reparse:
                        return PolicyDecision(Decision.DENY, "REPARSE_POINT", "Source path includes a symbolic link or reparse point.")
                except FileNotFoundError:
                    continue
        except (OSError, RuntimeError, ValueError):
            return PolicyDecision(Decision.DENY, "SOURCE_UNAVAILABLE", "Source path cannot be safely resolved.")

        if operation == "quarantine":
            if automatic and not cls.auto_quarantine_enabled:
                return PolicyDecision(Decision.DENY, "AUTO_QUARANTINE_DISABLED", "Automatic quarantine is not enabled by the user.")
            from utils import is_file_exclusively_accessible
            if metadata.get("accessible") is not True or not is_file_exclusively_accessible(str(src)):
                return PolicyDecision(Decision.DENY, "FILE_INACCESSIBLE", "File is locked or cannot be opened exclusively.")
            if mode == MODE_SAFE_DEMO:
                if not cls._inside(src, DEMO_BASE_DIR):
                    return PolicyDecision(Decision.DENY, "OUTSIDE_DEMO", "Demo files must remain inside the demo sandbox.")
                try:
                    demo_parts = [part.casefold() for part in src.relative_to(Path(DEMO_BASE_DIR).resolve()).parts]
                except (OSError, ValueError):
                    return PolicyDecision(Decision.DENY, "OUTSIDE_DEMO", "Demo path could not be verified.")
                if not any(part in {"chrome_demo", "electron_demo"} for part in demo_parts) or cls.approved_cache_index(app_name, demo_parts) is None:
                    return PolicyDecision(Decision.DENY, "UNAPPROVED_DEMO_DIRECTORY", "Only synthetic cache files in demo cache folders may be quarantined.")
                if src.suffix.casefold() not in cls.safe_extensions:
                    return PolicyDecision(Decision.DENY, "UNKNOWN_FILE_TYPE", "File type is not approved for quarantine.")
                if metadata.get("accessible") is not True or age_days is None or age_days < 14:
                    return PolicyDecision(Decision.DENY, "DEMO_FACTS_UNCONFIRMED", "Demo file accessibility and minimum age must be confirmed.")
                if not cls._identity_matches(src, metadata):
                    return PolicyDecision(Decision.DENY, "FILE_IDENTITY_UNKNOWN", "Demo file identity is missing or changed since scanning.")
            else:
                app_root = APP_DEFINITIONS.get(app_name, {}).get("relative_path")
                if not app_root or not cls._inside(src, app_root):
                    return PolicyDecision(Decision.DENY, "UNAPPROVED_ROOT", "File is outside a recognized application data root.")
                if any(root and cls._inside(src, root) for root in SYSTEM_PROTECTED_ROOTS):
                    return PolicyDecision(Decision.DENY, "PROTECTED_ROOT", "File is inside a protected system or personal directory.")
                try:
                    rel = src.relative_to(Path(app_root).resolve()).parts
                except (OSError, ValueError):
                    return PolicyDecision(Decision.DENY, "UNAPPROVED_ROOT", "File is outside the recognized application root.")
                if cls.approved_cache_index(app_name, rel) is None:
                    return PolicyDecision(Decision.DENY, "UNAPPROVED_DIRECTORY", "File is not inside an explicitly approved cache directory.")
                if src.suffix.casefold() not in cls.safe_extensions:
                    return PolicyDecision(Decision.DENY, "UNKNOWN_FILE_TYPE", "File type is not approved for quarantine.")
                if not cls._identity_matches(src, metadata):
                    return PolicyDecision(Decision.DENY, "FILE_IDENTITY_UNKNOWN", "File identity was not recorded or no longer matches.")
                if process_running is not False:
                    return PolicyDecision(Decision.DENY, "APP_STATE_UNCERTAIN", "Application state is running or unknown.")
                if not metadata.get("accessible"):
                    return PolicyDecision(Decision.DENY, "FILE_INACCESSIBLE", "File accessibility is not confirmed.")
                if age_days is None or age_days < 14:
                    return PolicyDecision(Decision.DENY, "AGE_NOT_CONFIRMED", "Minimum age requirement is not confirmed.")
            for protected in PROTECTED_FILE_PATTERNS:
                if protected.casefold() in src.name.casefold() or protected.casefold() in str(src).casefold():
                    return PolicyDecision(Decision.DENY, "PROTECTED_PATTERN", "Path matches a protected-data rule.")
            if src.suffix.casefold() in PROTECTED_EXTENSIONS:
                return PolicyDecision(Decision.DENY, "PROTECTED_EXTENSION", "File extension is protected.")
            if destination:
                if cls._contains_reparse_point(destination):
                    return PolicyDecision(Decision.DENY, "DESTINATION_REPARSE_POINT", "Destination path includes a reparse point.")
                root = DEMO_QUARANTINE_DIR if mode == MODE_SAFE_DEMO else REAL_QUARANTINE_DIR
                if not cls._inside(Path(destination), root):
                    return PolicyDecision(Decision.DENY, "INVALID_DESTINATION", "Destination is outside the managed quarantine.")
                if Path(destination).exists():
                    return PolicyDecision(Decision.DENY, "DESTINATION_EXISTS", "Quarantine destination already exists; no overwrite is permitted.")
            return PolicyDecision(Decision.ALLOW, "QUARANTINE_ALLOWED", "Approved quarantine operation.")

        if operation == "restore":
            from utils import is_file_exclusively_accessible
            if not is_file_exclusively_accessible(str(src)):
                return PolicyDecision(Decision.DENY, "FILE_INACCESSIBLE", "Quarantined file is locked or inaccessible.")
            root = DEMO_QUARANTINE_DIR if mode == MODE_SAFE_DEMO else REAL_QUARANTINE_DIR
            if not cls._inside(src, root):
                return PolicyDecision(Decision.DENY, "INVALID_QUARANTINE_SOURCE", "Restore source is outside quarantine.")
            if not destination:
                return PolicyDecision(Decision.DENY, "MISSING_DESTINATION", "Restore destination is required.")
            if cls._contains_reparse_point(destination):
                return PolicyDecision(Decision.DENY, "DESTINATION_REPARSE_POINT", "Restore target includes a reparse point.")
            if mode == MODE_SAFE_DEMO and not cls._inside(Path(destination), DEMO_BASE_DIR):
                return PolicyDecision(Decision.DENY, "INVALID_RESTORE_TARGET", "Demo restore target is outside its sandbox.")
            if mode == MODE_REAL_SYSTEM_ACTIVE:
                app_root = APP_DEFINITIONS.get(app_name, {}).get("relative_path")
                if not app_root or not cls._inside(Path(destination), app_root):
                    return PolicyDecision(Decision.DENY, "INVALID_RESTORE_TARGET", "Restore target is not a known application root.")
            if Path(destination).exists():
                return PolicyDecision(Decision.DENY, "RESTORE_COLLISION", "Restore target already exists; no overwrite is permitted.")
            return PolicyDecision(Decision.ALLOW, "RESTORE_ALLOWED", "Restore target is validated.")

        if operation == "purge":
            from utils import is_file_exclusively_accessible
            if not is_file_exclusively_accessible(str(src)):
                return PolicyDecision(Decision.DENY, "FILE_INACCESSIBLE", "Quarantined file is locked or inaccessible.")
            root = DEMO_QUARANTINE_DIR if mode == MODE_SAFE_DEMO else REAL_QUARANTINE_DIR
            if not cls._inside(src, root):
                return PolicyDecision(Decision.DENY, "INVALID_PURGE_SOURCE", "Purge source is outside quarantine.")
            purge_policy_enabled = cls.demo_purge_enabled if mode == MODE_SAFE_DEMO else cls.real_purge_enabled
            if not user_purge_enabled or not purge_policy_enabled:
                return PolicyDecision(Decision.REQUIRE_REVIEW, "PURGE_REVIEW_REQUIRED", "Permanent purge requires an explicit enabled policy and review.")
            if age_days is None or retention_days is None or age_days < retention_days:
                return PolicyDecision(Decision.DENY, "RETENTION_ACTIVE", "Quarantine retention period has not elapsed.")
            return PolicyDecision(Decision.ALLOW, "PURGE_ALLOWED", "Demo quarantine retention and policy checks passed.")
        return PolicyDecision(Decision.DENY, "UNKNOWN_OPERATION", "Operation type is not authorized.")

    @staticmethod
    def _identity_matches(path, metadata):
        try:
            current = Path(path).stat()
            expected = metadata.get("file_identity")
            return (metadata.get("size_bytes") == current.st_size
                    and metadata.get("mtime") == current.st_mtime
                    and expected is not None
                    and expected.get("device") == current.st_dev
                    and expected.get("inode") == current.st_ino)
        except (OSError, AttributeError, TypeError):
            return False

    @staticmethod
    def _inside(path, root):
        try:
            Path(path).resolve().relative_to(Path(root).resolve())
            return True
        except (OSError, ValueError, RuntimeError):
            return False
