import os
import stat
import threading
from pathlib import Path
from safety_policy import SafetyPolicy
from utils import (
    calculate_file_age_days,
    is_file_accessible,
    format_file_size,
    format_timestamp,
    compute_file_sha256,
    get_file_type_category,
    is_symlink_or_reparse_point,
)
from process_analyzer import ProcessAnalyzer
from classifier import ZombieDataClassifier
from database import get_audit_store
from config import CLASSIFICATION_ZOMBIE, CLASSIFICATION_UNCERTAIN, CLASSIFICATION_KEEP, DEFAULT_AGE_THRESHOLD_DAYS

class FileScanner:
    """
    Module 1 / Task 1.2 & Task 1.3:
    Task 1.2 – Intelligent File Scanning:
      Activity 1.2.1: Recursive directory scanning within approved locations.
      Activity 1.2.2: File metadata extraction.
      Activity 1.2.3: File type and extension identification.
    Task 1.3 – Scan Intelligence:
      Activity 1.3.1: File size and timestamp analysis.
      Activity 1.3.2: Duplicate file identification using SHA-256 hashes.
      Activity 1.3.3: Scan report generation and SQLite storage.
    """
    _active_scan_lock = threading.Lock()
    _active_scan_paths = set()

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        return is_symlink_or_reparse_point(str(path))

    @classmethod
    def scan_directory(cls, app_info: dict, age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS, max_files: int = 2500, cancel_event=None) -> dict:
        """Entry point for directory scan with concurrency lock protection."""
        target = app_info.get("path", "")
        key = os.path.normcase(os.path.abspath(target)) if target else ""
        with cls._active_scan_lock:
            if key and key in cls._active_scan_paths:
                return {
                    "app_name": app_info.get("name", "Unknown Application"), "target_path": target,
                    "scanned_count": 0, "zombie_count": 0, "uncertain_count": 0,
                    "keep_count": 0, "potential_reclaimable_bytes": 0, "files": [],
                    "skipped": "A scan of this path is already running."
                }
            if key:
                cls._active_scan_paths.add(key)
        try:
            return cls._scan_directory_impl(app_info, age_threshold_days, max_files, cancel_event)
        finally:
            if key:
                with cls._active_scan_lock:
                    cls._active_scan_paths.discard(key)

    @classmethod
    def _scan_directory_impl(cls, app_info: dict, age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS, max_files: int = 2500, cancel_event=None) -> dict:
        """
        Activity 1.2.1: Recursive scanning of approved directories.
        Restricted strictly to approved cache layouts, rejecting reparse points and protected trees.
        """
        app_name = app_info.get("name", "Unknown Application")
        target_path = app_info.get("path", "")
        process_name = app_info.get("process_name", "")

        # 1. Process Telemetry (Read-only)
        if "demo sandbox" in app_info.get("type", "").casefold():
            proc_status = {
                "running": False,
                "status_text": "DEMO (NO REAL PROCESS)",
                "explanation": "Synthetic demo data has no associated real application process."
            }
        else:
            proc_status = ProcessAnalyzer.get_process_status(process_name)
        process_running = proc_status["running"]

        files_records = []
        issues = []
        scanned_count = 0
        zombie_count = 0
        uncertain_count = 0
        keep_count = 0
        potential_reclaimable_bytes = 0

        if not target_path or not os.path.exists(target_path):
            return {
                "app_name": app_name,
                "target_path": target_path,
                "scanned_count": 0,
                "zombie_count": 0,
                "uncertain_count": 0,
                "keep_count": 0,
                "potential_reclaimable_bytes": 0,
                "files": [],
                "error": f"Directory not found: {target_path}"
            }
        if cls._is_reparse_point(Path(target_path)):
            return {
                "app_name": app_name, "target_path": target_path, "scanned_count": 0,
                "zombie_count": 0, "uncertain_count": 0, "keep_count": 0,
                "potential_reclaimable_bytes": 0, "files": [],
                "error": "Scan root is a symbolic link or reparse point."
            }

        # 2. File Walk with Safety Exception Catching
        try:
            for root, dirs, files in os.walk(target_path, followlinks=False,
                                             onerror=lambda error: issues.append({"path": error.filename, "reason": "Directory could not be read."})):
                if cancel_event is not None and cancel_event.is_set():
                    return {
                        "app_name": app_name, "target_path": target_path,
                        "scanned_count": scanned_count, "zombie_count": zombie_count,
                        "uncertain_count": uncertain_count, "keep_count": keep_count,
                        "potential_reclaimable_bytes": potential_reclaimable_bytes,
                        "files": files_records, "issues": issues, "cancelled": True
                    }
                root_path = Path(root)
                if "quarantine" in str(root_path).casefold():
                    dirs[:] = []
                    continue
                try:
                    rel_parts = root_path.resolve().relative_to(Path(target_path).resolve()).parts
                except (ValueError, OSError):
                    dirs[:] = []
                    continue

                def may_descend(parts):
                    layout = app_name.casefold()
                    if "demo" in layout:
                        return SafetyPolicy.approved_cache_index(app_name, parts) is not None
                    from config import CACHE_LAYOUTS
                    rule = CACHE_LAYOUTS.get(app_name, {"kind": "disabled"})
                    if rule.get("kind") == "browser_profile" and len(parts) == 1:
                        name = parts[0].casefold()
                        return name in {"default", "guest profile", "system profile"} or name.startswith("profile ")
                    return SafetyPolicy.approved_cache_index(app_name, parts) is not None

                dirs[:] = [d for d in dirs if not cls._is_reparse_point(root_path / d) and may_descend(rel_parts + (d,))]
                if SafetyPolicy.approved_cache_index(app_name, rel_parts) is None:
                    files = []
                if scanned_count >= max_files:
                    break

                for fname in files:
                    if scanned_count >= max_files:
                        break
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    full_path = os.path.join(root, fname)
                    if cls._is_reparse_point(Path(full_path)):
                        continue
                    
                    try:
                        # Activity 1.2.2: File metadata extraction
                        meta = cls.extract_file_metadata(full_path)
                        if not meta.get("exists"):
                            continue

                        meta["app_name"] = app_name
                        meta["process_name"] = process_name
                        meta["process_running"] = process_running
                        meta["process_status_text"] = proc_status["status_text"]

                        # Activity 1.2.3: File type and extension identification
                        type_info = cls.identify_file_type_and_extension(full_path)
                        meta.update(type_info)

                        # Activity 1.3.1: File size and timestamp analysis
                        ts_analysis = cls.analyze_file_size_and_timestamps(meta, age_threshold_days)
                        meta.update(ts_analysis)

                        # Pass through Classifier
                        class_result = ZombieDataClassifier.classify_file(meta, age_threshold_days)
                        meta["score"] = class_result["score"]
                        meta["classification"] = class_result["classification"]
                        meta["risk_level"] = class_result.get("risk_level", "NORMAL")
                        meta["reasons"] = class_result["reasons"]
                        meta["factors"] = class_result.get("factors", {})

                        scanned_count += 1
                        if class_result["classification"] == CLASSIFICATION_ZOMBIE:
                            zombie_count += 1
                            potential_reclaimable_bytes += meta["size_bytes"]
                        elif class_result["classification"] == CLASSIFICATION_UNCERTAIN:
                            uncertain_count += 1
                        else:
                            keep_count += 1

                        files_records.append(meta)
                        if not meta["accessible"]:
                            issues.append({"path": full_path, "reason": "File could not be opened for reading."})

                    except (PermissionError, OSError, FileNotFoundError) as exc:
                        issues.append({"path": full_path, "reason": f"File metadata could not be read: {type(exc).__name__}."})
                        continue

        except Exception as e:
            return {
                "app_name": app_name,
                "target_path": target_path,
                "scanned_count": scanned_count,
                "zombie_count": zombie_count,
                "uncertain_count": uncertain_count,
                "keep_count": keep_count,
                "potential_reclaimable_bytes": potential_reclaimable_bytes,
                "files": files_records,
                "issues": issues,
                "error": str(e)
            }

        # Activity 1.3.2: Duplicate file identification using SHA-256
        duplicate_report = cls.identify_duplicates_sha256(files_records)

        return {
            "app_name": app_name,
            "target_path": target_path,
            "scanned_count": scanned_count,
            "zombie_count": zombie_count,
            "uncertain_count": uncertain_count,
            "keep_count": keep_count,
            "potential_reclaimable_bytes": potential_reclaimable_bytes,
            "potential_space_formatted": format_file_size(potential_reclaimable_bytes),
            "duplicate_files_count": duplicate_report.get("duplicate_count", 0),
            "duplicate_savings_bytes": duplicate_report.get("duplicate_savings_bytes", 0),
            "duplicate_savings_formatted": format_file_size(duplicate_report.get("duplicate_savings_bytes", 0)),
            "files": files_records,
            "issues": issues,
        }

    @staticmethod
    def extract_file_metadata(file_path: str) -> dict:
        """
        Activity 1.2.2: File metadata extraction.
        Extracts size, timestamps, device/inode identities, and read access.
        """
        if not os.path.exists(file_path):
            return {"exists": False, "full_path": file_path}
        
        stat_res = os.stat(file_path)
        size_bytes = stat_res.st_size
        mtime = stat_res.st_mtime
        ctime = stat_res.st_ctime
        atime = getattr(stat_res, "st_atime", mtime)
        fname = os.path.basename(file_path)
        ext = os.path.splitext(fname)[1].lower()
        accessible = is_file_accessible(file_path)

        return {
            "exists": True,
            "file_name": fname,
            "full_path": file_path,
            "parent_dir": os.path.dirname(file_path),
            "extension": ext,
            "size_bytes": size_bytes,
            "size_formatted": format_file_size(size_bytes),
            "file_identity": {"device": stat_res.st_dev, "inode": stat_res.st_ino},
            "ctime": ctime,
            "ctime_formatted": format_timestamp(ctime),
            "mtime": mtime,
            "mtime_formatted": format_timestamp(mtime),
            "atime": atime,
            "atime_formatted": format_timestamp(atime),
            "accessible": accessible,
            "sha256": "",
            "is_duplicate": False,
        }

    @staticmethod
    def identify_file_type_and_extension(file_path: str) -> dict:
        """
        Activity 1.2.3: File type and extension identification.
        Categorizes file extension into structural types (Web Cache, Shader, Log, Protected DB, etc.).
        """
        type_info = get_file_type_category(file_path)
        return {
            "file_category": type_info["category"],
            "category_badge": type_info["badge"],
            "disposable_cache_type": type_info["disposable"]
        }

    @staticmethod
    def analyze_file_size_and_timestamps(metadata: dict, age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS) -> dict:
        """
        Activity 1.3.1: File size and timestamp analysis.
        Computes elapsed age in days, time delta brackets, and size category.
        """
        mtime = metadata.get("mtime", 0)
        size_bytes = metadata.get("size_bytes", 0)
        age_days = calculate_file_age_days(mtime)

        if size_bytes < 1024 * 10:
            size_bracket = "TINY (< 10 KB)"
        elif size_bytes < 1024 * 1024:
            size_bracket = "SMALL (< 1 MB)"
        elif size_bytes < 1024 * 1024 * 50:
            size_bracket = "MEDIUM (1 - 50 MB)"
        else:
            size_bracket = "LARGE (> 50 MB)"

        return {
            "age_days": age_days,
            "age_exceeds_threshold": age_days >= age_threshold_days,
            "size_bracket": size_bracket,
            "stale_indicator": "STALE (>= threshold)" if age_days >= age_threshold_days else "RECENT (< threshold)"
        }

    @classmethod
    def identify_duplicates_sha256(cls, files_list: list) -> dict:
        """
        Activity 1.3.2: Duplicate file identification using SHA-256 hashes.
        Groups files by size first to optimize hashing performance.
        Computes SHA-256 for files with matching non-zero sizes to detect true bitwise duplicates.
        """
        size_groups = {}
        for f in files_list:
            size = f.get("size_bytes", 0)
            if size > 0:
                size_groups.setdefault(size, []).append(f)

        duplicate_count = 0
        duplicate_savings_bytes = 0
        duplicate_groups = {}

        for size, candidates in size_groups.items():
            if len(candidates) < 2:
                continue
            # Multiple files with identical size — compute hashes
            hashes = {}
            for item in candidates:
                path = item.get("full_path")
                if not item.get("sha256"):
                    item["sha256"] = compute_file_sha256(path)
                h = item["sha256"]
                if h:
                    hashes.setdefault(h, []).append(item)

            for h, matching_files in hashes.items():
                if len(matching_files) > 1:
                    primary = matching_files[0]
                    for duplicate in matching_files[1:]:
                        duplicate["is_duplicate"] = True
                        duplicate["duplicate_of"] = primary["full_path"]
                        duplicate_count += 1
                        duplicate_savings_bytes += duplicate["size_bytes"]
                    duplicate_groups[h] = [f["full_path"] for f in matching_files]

        return {
            "duplicate_count": duplicate_count,
            "duplicate_savings_bytes": duplicate_savings_bytes,
            "duplicate_groups": duplicate_groups
        }

    @classmethod
    def generate_scan_report_and_store(cls, scan_result: dict, mode: str, db_store=None) -> dict:
        """
        Activity 1.3.3: Scan report generation and SQLite storage.
        Compiles the complete scan report and persists session and discovered candidate files to SQLite.
        """
        store = db_store or get_audit_store()
        scan_id = store.record_scan(mode, scan_result)
        store.record_event(
            operation="scan",
            mode=mode,
            decision="RECORDED",
            code="SCAN_SESSION_SAVED",
            detail=f"Scan of {scan_result.get('app_name')} completed. Scanned: {scan_result.get('scanned_count')}, Zombies: {scan_result.get('zombie_count')}, Reclaimable: {scan_result.get('potential_space_formatted')}",
            source_path=scan_result.get("target_path")
        )
        scan_result["scan_id"] = scan_id
        return scan_result
