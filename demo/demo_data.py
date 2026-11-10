import os
import time
from config import DEMO_BASE_DIR, DEMO_QUARANTINE_DIR, DEMO_MANIFEST_FILE
from safety_policy import SafetyPolicy
from config import MODE_SAFE_DEMO

def create_safe_demo_environment():
    """
    Creates an isolated test environment under %LOCALAPPDATA%\\ZombieDataPurgerDemo\\
    Populates sample files with specific ages and characteristics for testing scanning,
    classification, quarantine, restore, and purging.
    """
    root_decision = SafetyPolicy.authorize("demo_create", DEMO_BASE_DIR, mode=MODE_SAFE_DEMO, metadata={"root": True})
    if root_decision.decision.value != "ALLOW":
        raise PermissionError(root_decision.reason)
    # Ensure only the configured synthetic-data root exists; quarantine is
    # created later by the authorized quarantine service when needed.
    os.makedirs(DEMO_BASE_DIR, exist_ok=True)

    # Base current time reference
    now = time.time()
    day = 86400

    # Define File Map with relative path, content, size multiplier, and age in days
    demo_files = [
        # Chrome Demo Files
        {
            "rel_path": os.path.join("Chrome_Demo", "Cache", "old_cache_01.tmp"),
            "content": "STALE_CACHE_DATA_BUFFER_01_" * 2000, # ~50 KB
            "age_days": 45
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Cache", "old_cache_02.tmp"),
            "content": "STALE_CACHE_DATA_BUFFER_02_" * 5000, # ~125 KB
            "age_days": 60
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Cache", "old_cache_03.dat"),
            "content": "EXPIRED_INDEXED_CACHE_DAT_" * 8000, # ~190 KB
            "age_days": 35
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Temp", "old_temp_01.tmp"),
            "content": "ORPHANED_DOWNLOAD_TEMP_CHUNK_" * 10000, # ~280 KB
            "age_days": 40
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Logs", "old_log_01.log"),
            "content": "[2026-07-01 10:15:22] CRASH_LOG_DUMP_PROCESS_ID_88412\n" * 3000, # ~150 KB
            "age_days": 50
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Active", "recent_data.db"),
            "content": "ACTIVE_USER_PROFILE_DATABASE_V1_KEY_VALUE_STORE_" * 400, # ~20 KB
            "age_days": 1 # Active file (recent)
        },
        {
            "rel_path": os.path.join("Chrome_Demo", "Active", "Cookies"),
            "content": "CRITICAL_USER_SESSION_COOKIES_DO_NOT_DELETE",
            "age_days": 60 # Old, but PROTECTED file pattern!
        },
        
        # Electron Demo Files
        {
            "rel_path": os.path.join("Electron_Demo", "Cache", "old_cache_01.tmp"),
            "content": "ELECTRON_GPU_CACHE_BLOB_CHUNK_1_" * 3000, # ~90 KB
            "age_days": 35
        },
        {
            "rel_path": os.path.join("Electron_Demo", "Cache", "old_cache_02.tmp"),
            "content": "ELECTRON_SHADER_CACHE_RECORD_" * 4000, # ~110 KB
            "age_days": 45
        },
        {
            "rel_path": os.path.join("Electron_Demo", "Temp", "old_temp_01.tmp"),
            "content": "ELECTRON_UPDATE_EXTRACTED_TEMP_FRAMEWORK_" * 6000, # ~240 KB
            "age_days": 50
        },
        {
            "rel_path": os.path.join("Electron_Demo", "Active", "current_session.db"),
            "content": "ELECTRON_ACTIVE_STATE_SESSION_STORAGE_PROD_",
            "age_days": 0 # Active file (recent)
        }
    ]

    created_paths = []
    total_bytes = 0

    for item in demo_files:
        full_path = os.path.join(DEMO_BASE_DIR, item["rel_path"])
        decision = SafetyPolicy.authorize("demo_create", full_path, mode=MODE_SAFE_DEMO)
        if decision.decision.value != "ALLOW":
            continue
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write actual file content
        # Never overwrite a pre-existing file in the application data area.
        try:
            decision = SafetyPolicy.authorize("demo_create", full_path, mode=MODE_SAFE_DEMO)
            if decision.decision.value != "ALLOW":
                continue
            with open(full_path, "x", encoding="utf-8") as f:
                f.write(item["content"])
        except FileExistsError:
            continue
        
        # Modify file timestamp
        file_mtime = now - (item["age_days"] * day)
        os.utime(full_path, (file_mtime, file_mtime))

        created_paths.append(full_path)
        total_bytes += os.path.getsize(full_path)

    return {
        "base_dir": DEMO_BASE_DIR,
        "files_created": len(created_paths),
        "total_bytes": total_bytes,
        "paths": created_paths
    }

def clean_safe_demo_environment():
    """No-op retained for compatibility; demo files are not recursively cleaned."""
    return 0
