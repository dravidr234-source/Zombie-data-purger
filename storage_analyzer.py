"""
Zombie Data Purger — Browser Storage Analysis Engine
Module: storage_analyzer.py

Enhancement: Browser Folder-Level and Individual File-Level Storage Analysis
- Module A: Browser Folder-Level Storage Analysis & Combined Percentage Calculation
- Module B: Individual File-Level Storage Analysis (Top 5 Largest Files + Remaining Files Aggregate)
- Module C: Visual Storage Metrics & Data Formatting
- Module D: Integration with ZombieDataClassifier & SafetyPolicy (Read-Only)

STRICT SAFETY GUARANTEE:
This module is strictly READ-ONLY. It never deletes, moves, or modifies original
browser files, never terminates or interferes with processes, and enforces
zero-corruption immunity for protected files and directories.
"""

import os
import stat
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from config import (
    LOCAL_APP_DATA,
    ROAMING_APP_DATA,
    DEMO_BASE_DIR,
    MODE_SAFE_DEMO,
    MODE_REAL_SYSTEM_READONLY,
    MODE_REAL_SYSTEM_ACTIVE,
    KNOWN_CACHE_DIR_KEYWORDS,
    DEFAULT_AGE_THRESHOLD_DAYS,
)
from utils import (
    format_file_size,
    format_timestamp,
    calculate_file_age_days,
    is_file_accessible,
    get_file_type_category,
    is_symlink_or_reparse_point,
    canonicalize_path,
)
from safety_policy import SafetyPolicy, Decision
from classifier import ZombieDataClassifier


# ==============================================================================
# SUPPORTED BROWSER SPECIFICATIONS
# ==============================================================================

BROWSER_SPECS = {
    "Google Chrome": {
        "id": "chrome",
        "name": "Google Chrome",
        "process_name": "chrome.exe",
        "data_path": os.path.join(LOCAL_APP_DATA, "Google", "Chrome", "User Data"),
        "layout_kind": "chromium",
        "icon": "🌐",
    },
    "Microsoft Edge": {
        "id": "edge",
        "name": "Microsoft Edge",
        "process_name": "msedge.exe",
        "data_path": os.path.join(LOCAL_APP_DATA, "Microsoft", "Edge", "User Data"),
        "layout_kind": "chromium",
        "icon": "🌊",
    },
    "Mozilla Firefox": {
        "id": "firefox",
        "name": "Mozilla Firefox",
        "process_name": "firefox.exe",
        "data_path": os.path.join(LOCAL_APP_DATA, "Mozilla", "Firefox", "Profiles"),
        "layout_kind": "firefox",
        "icon": "🦊",
    },
    "Brave Browser": {
        "id": "brave",
        "name": "Brave Browser",
        "process_name": "brave.exe",
        "data_path": os.path.join(LOCAL_APP_DATA, "BraveSoftware", "Brave-Browser", "User Data"),
        "layout_kind": "chromium",
        "icon": "🦁",
    },
}

DEMO_BROWSER_SPECS = {
    "Chrome Demo Application": {
        "id": "chrome_demo",
        "name": "Chrome Demo Application",
        "process_name": "chrome.exe",
        "data_path": os.path.join(DEMO_BASE_DIR, "Chrome_Demo"),
        "layout_kind": "demo",
        "icon": "🌐",
    },
    "Edge Demo Application": {
        "id": "edge_demo",
        "name": "Edge Demo Application",
        "process_name": "msedge.exe",
        "data_path": os.path.join(DEMO_BASE_DIR, "Edge_Demo"),
        "layout_kind": "demo",
        "icon": "🌊",
    },
}

# Approved cache directory keyword signatures for browser profiles
APPROVED_CACHE_KEYWORDS = {
    "cache",
    "code cache",
    "gpucache",
    "gpu cache",
    "dawncache",
    "shadercache",
    "cache2",
    "startupcache",
    "jumplistcache",
    "crashpad",
    "logs",
    "temp",
    "tmp",
}


class BrowserStorageAnalyzer:
    """
    Core engine for folder-level and file-level browser storage analysis.
    Provides mathematically accurate size aggregations, percentage calculations,
    top-file ranking, and seamless classification inspection.
    """

    @classmethod
    def get_supported_browsers(cls, mode: str = MODE_SAFE_DEMO) -> List[Dict[str, Any]]:
        """
        Discovers and returns list of supported browser targets according to active mode.
        Checks for path existence, directory accessibility, and verified cache layouts.
        """
        targets = []
        specs = DEMO_BROWSER_SPECS if mode == MODE_SAFE_DEMO else BROWSER_SPECS

        for app_name, spec in specs.items():
            path = spec["data_path"]
            exists = os.path.exists(path) if path else False
            is_reparse = is_symlink_or_reparse_point(path) if exists else False

            accessible = False
            if exists and not is_reparse:
                try:
                    with os.scandir(path) as it:
                        next(it, None)
                    accessible = True
                except (PermissionError, OSError):
                    accessible = False

            targets.append({
                "name": app_name,
                "id": spec["id"],
                "process_name": spec["process_name"],
                "path": path,
                "layout_kind": spec["layout_kind"],
                "icon": spec.get("icon", "🌐"),
                "exists": exists and not is_reparse,
                "accessible": accessible,
                "is_reparse": is_reparse,
            })

        return targets

    @classmethod
    def detect_cache_directories(cls, browser_info: Dict[str, Any], mode: str = MODE_SAFE_DEMO) -> List[str]:
        """
        Activity: Identifies verified cache subdirectories inside a browser's data root.
        Strictly enforces layout rules and excludes non-cache profile data.
        """
        root_path = browser_info.get("path", "")
        layout_kind = browser_info.get("layout_kind", "chromium")
        verified_dirs = []

        if not root_path or not os.path.exists(root_path) or is_symlink_or_reparse_point(root_path):
            return verified_dirs

        try:
            if layout_kind == "demo":
                # Demo layout: direct subdirectories like Cache, Temp, Logs
                for entry in os.scandir(root_path):
                    if entry.is_dir(follow_symlinks=False) and not is_symlink_or_reparse_point(entry.path):
                        if any(kw in entry.name.lower() for kw in APPROVED_CACHE_KEYWORDS):
                            verified_dirs.append(entry.path)

            elif layout_kind == "chromium":
                # Chromium layout: root -> profiles (Default, Profile *, Guest Profile) -> Cache dirs
                for entry in os.scandir(root_path):
                    if entry.is_dir(follow_symlinks=False) and not is_symlink_or_reparse_point(entry.path):
                        name_lower = entry.name.lower()
                        # Direct cache in root (rare)
                        if any(kw in name_lower for kw in APPROVED_CACHE_KEYWORDS):
                            verified_dirs.append(entry.path)
                            continue

                        # Profile folder
                        if name_lower in {"default", "guest profile", "system profile"} or name_lower.startswith("profile "):
                            try:
                                for sub in os.scandir(entry.path):
                                    if sub.is_dir(follow_symlinks=False) and not is_symlink_or_reparse_point(sub.path):
                                        sub_lower = sub.name.lower()
                                        if any(kw in sub_lower for kw in APPROVED_CACHE_KEYWORDS):
                                            verified_dirs.append(sub.path)
                            except (PermissionError, OSError):
                                pass

            elif layout_kind == "firefox":
                # Firefox layout: root -> profiles (*.default, *.default-release) -> cache2, startupCache
                for entry in os.scandir(root_path):
                    if entry.is_dir(follow_symlinks=False) and not is_symlink_or_reparse_point(entry.path):
                        try:
                            for sub in os.scandir(entry.path):
                                if sub.is_dir(follow_symlinks=False) and not is_symlink_or_reparse_point(sub.path):
                                    sub_lower = sub.name.lower()
                                    if sub_lower in {"cache2", "startupcache", "jumplistcache"} or any(kw in sub_lower for kw in APPROVED_CACHE_KEYWORDS):
                                        verified_dirs.append(sub.path)
                        except (PermissionError, OSError):
                            pass

        except (PermissionError, OSError):
            pass

        return verified_dirs

    @classmethod
    def scan_browser_files(
        cls,
        browser_info: Dict[str, Any],
        mode: str = MODE_SAFE_DEMO,
        age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS,
        max_files: int = 5000,
        cancel_event=None
    ) -> Dict[str, Any]:
        """
        Module B: Scans all eligible cache files for a given browser.
        Collects file metadata, computes sizes, handles locks/errors safely,
        prevents duplicate counting, and attaches classification details.
        """
        browser_name = browser_info.get("name", "Unknown Browser")
        root_path = browser_info.get("path", "")
        verified_cache_dirs = cls.detect_cache_directories(browser_info, mode)

        if not browser_info.get("exists"):
            return {
                "browser_name": browser_name,
                "browser_id": browser_info.get("id", ""),
                "status": "NOT_INSTALLED",
                "status_label": "Not Installed",
                "target_path": root_path,
                "verified_cache_dirs": [],
                "files": [],
                "file_count": 0,
                "total_bytes": 0,
                "skipped_count": 0,
                "error": "Application root directory does not exist.",
            }

        if not verified_cache_dirs:
            return {
                "browser_name": browser_name,
                "browser_id": browser_info.get("id", ""),
                "status": "NO_CACHE_DIRS",
                "status_label": "No Cache Directories",
                "target_path": root_path,
                "verified_cache_dirs": [],
                "files": [],
                "file_count": 0,
                "total_bytes": 0,
                "skipped_count": 0,
                "error": None,
            }

        files_list = []
        seen_identities = set()  # Track (st_dev, st_ino) or canonical path to prevent duplicates
        total_bytes = 0
        skipped_count = 0

        for cache_dir in verified_cache_dirs:
            if cancel_event is not None and cancel_event.is_set():
                break

            for root, dirs, filenames in os.walk(cache_dir, followlinks=False):
                if cancel_event is not None and cancel_event.is_set():
                    break

                # Exclude symlinks and quarantine folders
                dirs[:] = [
                    d for d in dirs
                    if not is_symlink_or_reparse_point(os.path.join(root, d))
                    and "quarantine" not in d.lower()
                ]

                for fname in filenames:
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    if len(files_list) >= max_files:
                        break

                    full_path = os.path.join(root, fname)
                    if is_symlink_or_reparse_point(full_path):
                        skipped_count += 1
                        continue

                    # Safety Check: Skip protected credential/cookie files
                    protection_check = SafetyPolicy.is_protected_target(full_path)
                    if protection_check.get("protected"):
                        skipped_count += 1
                        continue

                    try:
                        st = os.stat(full_path)
                        # Duplicate prevention via filesystem identity
                        identity = (st.st_dev, st.st_ino) if st.st_ino != 0 else canonicalize_path(full_path)
                        if identity in seen_identities:
                            continue
                        seen_identities.add(identity)

                        file_size = int(st.st_size)
                        mtime = float(st.st_mtime)
                        ctime = float(st.st_ctime)
                        age_days = calculate_file_age_days(mtime)
                        accessible = is_file_accessible(full_path)
                        type_info = get_file_type_category(full_path)

                        # Metadata dictionary for classification
                        meta = {
                            "file_name": fname,
                            "full_path": full_path,
                            "extension": type_info.get("extension", ""),
                            "size_bytes": file_size,
                            "mtime": mtime,
                            "ctime": ctime,
                            "age_days": age_days,
                            "accessible": accessible,
                            "process_running": False,
                            "app_name": browser_name,
                        }

                        # Compute classification & score via ZombieDataClassifier
                        score_data = ZombieDataClassifier.calculate_zombie_score(meta, age_threshold_days)
                        score = score_data.get("score", 0)
                        category, risk_level = ZombieDataClassifier.classify_risk_category(score, score_data.get("is_protected", False))
                        reasons_data = ZombieDataClassifier.generate_classification_reasons(meta, score_data, age_threshold_days)

                        # Check quarantine eligibility under SafetyPolicy (fail-closed check)
                        decision = SafetyPolicy.authorize(
                            operation="inspect",
                            source=full_path,
                            mode=mode,
                            metadata=meta,
                            app_name=browser_name,
                        )

                        files_list.append({
                            "name": fname,
                            "full_path": full_path,
                            "extension": type_info.get("extension", ""),
                            "category_label": type_info.get("category", "General Cache"),
                            "badge": type_info.get("badge", "CACHE"),
                            "size_bytes": file_size,
                            "size_fmt": format_file_size(file_size),
                            "mtime": mtime,
                            "mtime_fmt": format_timestamp(mtime),
                            "age_days": age_days,
                            "accessible": accessible,
                            "zombie_score": score,
                            "classification": category,
                            "risk_level": risk_level,
                            "reasons": reasons_data.get("reasons", []),
                            "factors": score_data.get("factors", {}),
                            "is_protected": score_data.get("is_protected", False),
                            "quarantine_eligible": decision.decision == Decision.ALLOW,
                            "quarantine_reason": decision.reason,
                        })

                        total_bytes += file_size

                    except (PermissionError, OSError, FileNotFoundError):
                        skipped_count += 1
                        continue

        status = "SUCCESS" if files_list else "EMPTY"
        status_label = "Active & Scanned" if files_list else "Zero-Byte / Empty Cache"

        return {
            "browser_name": browser_name,
            "browser_id": browser_info.get("id", ""),
            "status": status,
            "status_label": status_label,
            "target_path": root_path,
            "verified_cache_dirs": verified_cache_dirs,
            "files": files_list,
            "file_count": len(files_list),
            "total_bytes": total_bytes,
            "total_bytes_fmt": format_file_size(total_bytes),
            "skipped_count": skipped_count,
            "error": None,
        }

    @classmethod
    def calculate_browser_storage_distribution(
        cls,
        browser_scan_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Module A: Calculates total combined browser storage and each browser's percentage.
        Formula:
          Browser Storage Percentage = (Browser Cache Folder Size / Total Detected Browser Cache Size) * 100
        """
        # Sum only successful scanned folders with actual bytes
        combined_bytes = sum(b.get("total_bytes", 0) for b in browser_scan_results if b.get("status") == "SUCCESS")
        total_files = sum(b.get("file_count", 0) for b in browser_scan_results)

        enriched_browsers = []
        for b in browser_scan_results:
            b_bytes = b.get("total_bytes", 0)
            status = b.get("status", "NOT_INSTALLED")

            if combined_bytes > 0 and status == "SUCCESS":
                pct = (b_bytes / combined_bytes) * 100.0
            else:
                pct = 0.0

            enriched_browsers.append({
                **b,
                "percentage": pct,
                "percentage_fmt": f"{pct:.2f}%",
                "total_bytes_fmt": format_file_size(b_bytes),
            })

        return {
            "browsers": enriched_browsers,
            "total_combined_bytes": combined_bytes,
            "total_combined_fmt": format_file_size(combined_bytes),
            "total_files_count": total_files,
            "active_browser_count": sum(1 for b in browser_scan_results if b.get("status") == "SUCCESS"),
            "timestamp": time.time(),
        }

    @classmethod
    def analyze_individual_file_storage(
        cls,
        browser_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Module B: Computes individual file-level storage distribution for a selected browser.
        Shows 5 largest eligible files + remaining files aggregate row.
        CRITICAL FORMULA:
          File Storage Percentage = (Individual File Size / Complete Selected Folder Size) * 100
        Denominator is strictly the complete folder size, NOT just the top 5 files.
        """
        all_files = list(browser_result.get("files", []))
        complete_folder_size = int(browser_result.get("total_bytes", 0))
        total_file_count = len(all_files)

        # Sort descending by size_bytes
        all_files.sort(key=lambda item: item["size_bytes"], reverse=True)

        top_files = []
        top_5 = all_files[:5]

        for file_item in top_5:
            f_size = file_item["size_bytes"]
            if complete_folder_size > 0:
                pct = (f_size / complete_folder_size) * 100.0
            else:
                pct = 0.0

            top_files.append({
                **file_item,
                "percentage": pct,
                "percentage_fmt": f"{pct:.2f}%",
                "is_aggregate": False,
            })

        # Calculate remaining files row if more than 5 files exist
        remaining_row = None
        if total_file_count > 5:
            remaining_slice = all_files[5:]
            rem_count = len(remaining_slice)
            rem_bytes = sum(f["size_bytes"] for f in remaining_slice)

            if complete_folder_size > 0:
                rem_pct = (rem_bytes / complete_folder_size) * 100.0
            else:
                rem_pct = 0.0

            remaining_row = {
                "name": f"Remaining Files ({rem_count:,} items)",
                "full_path": "Aggregate row for non-top-5 cache artifacts",
                "extension": "—",
                "category_label": "Multiple Cache Types",
                "badge": "REMAINING",
                "size_bytes": rem_bytes,
                "size_fmt": format_file_size(rem_bytes),
                "mtime_fmt": "—",
                "age_days": "—",
                "accessible": True,
                "percentage": rem_pct,
                "percentage_fmt": f"{rem_pct:.2f}%",
                "is_aggregate": True,
                "zombie_score": "—",
                "classification": "AGGREGATE",
                "risk_level": "NORMAL",
                "quarantine_eligible": False,
            }

        # Complete folder total summary row
        total_pct = 100.0 if complete_folder_size > 0 else 0.0
        total_row = {
            "name": "Total Selected Browser Cache",
            "full_path": browser_result.get("target_path", ""),
            "extension": "—",
            "category_label": "Complete Cache Folder",
            "badge": "TOTAL",
            "size_bytes": complete_folder_size,
            "size_fmt": format_file_size(complete_folder_size),
            "mtime_fmt": "—",
            "age_days": "—",
            "accessible": True,
            "percentage": total_pct,
            "percentage_fmt": f"{total_pct:.1f}%",
            "is_aggregate": True,
            "zombie_score": "—",
            "classification": "SUMMARY",
            "risk_level": "SUMMARY",
            "quarantine_eligible": False,
        }

        return {
            "browser_name": browser_result.get("browser_name", "Unknown Browser"),
            "complete_folder_size": complete_folder_size,
            "complete_folder_fmt": format_file_size(complete_folder_size),
            "total_file_count": total_file_count,
            "top_files": top_files,
            "remaining_row": remaining_row,
            "total_row": total_row,
        }

    @classmethod
    def ensure_demo_browser_fixtures(cls, base_dir: str = DEMO_BASE_DIR) -> Dict[str, Any]:
        """
        Creates synthetic multi-browser demo cache fixtures for examination demonstration.
        Adds Edge_Demo cache files alongside Chrome_Demo to demonstrate multi-browser percentages.
        Guarantees isolated sandbox location and fail-closed safety authorization.
        """
        edge_demo_dir = os.path.join(base_dir, "Edge_Demo")
        cache_dir = os.path.join(edge_demo_dir, "Cache")
        temp_dir = os.path.join(edge_demo_dir, "Temp")

        decision = SafetyPolicy.authorize("demo_create", edge_demo_dir, mode=MODE_SAFE_DEMO, metadata={"root": True})
        if decision.decision != Decision.ALLOW:
            return {"created": False, "reason": decision.reason}

        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        edge_fixtures = [
            ("edge_cache_blob_01.tmp", cache_dir, "EDGE_CRITICAL_CACHE_BLOB_PART_01_" * 3500, 30),  # ~90 KB
            ("edge_cache_blob_02.tmp", cache_dir, "EDGE_CRITICAL_CACHE_BLOB_PART_02_" * 6000, 40),  # ~160 KB
            ("edge_temp_download.tmp", temp_dir, "EDGE_PARTIAL_DOWNLOAD_CHUNK_V2_" * 9000, 45),     # ~270 KB
        ]

        created_count = 0
        now = time.time()
        day = 86400

        for fname, folder, content, age_days in edge_fixtures:
            target_file = os.path.join(folder, fname)
            if not os.path.exists(target_file):
                try:
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    mtime = now - (age_days * day)
                    os.utime(target_file, (mtime, mtime))
                    created_count += 1
                except (PermissionError, OSError):
                    pass

        return {"created": True, "files_created": created_count, "path": edge_demo_dir}

