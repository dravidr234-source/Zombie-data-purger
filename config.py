import os
from pathlib import Path

# Application Metadata
APP_NAME = "Zombie Data Purger for Browser & Electron Applications"
APP_VERSION = "1.0.0 (College Demonstration Build)"
ACADEMIC_MODULE_NAME = "Zombie Data Purger"

# Operating Modes
MODE_SAFE_DEMO = "SAFE DEMO MODE"
MODE_REAL_SYSTEM_READONLY = "REAL SYSTEM READ-ONLY MODE"
MODE_REAL_SYSTEM_ACTIVE = "REAL SYSTEM ACTIVE MODE (SAFE GUARDED)"

# Base Paths
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
ROAMING_APP_DATA = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))

# Safe Demo Mode Sandbox Directory
DEMO_BASE_DIR = os.path.join(LOCAL_APP_DATA, "ZombieDataPurgerDemo")
DEMO_QUARANTINE_DIR = os.path.join(DEMO_BASE_DIR, "Quarantine")
DEMO_MANIFEST_FILE = os.path.join(DEMO_BASE_DIR, "quarantine_manifest.json")
DEMO_REPORT_FILE = os.path.join(DEMO_BASE_DIR, "audit_report.json")
DEMO_SAMPLE_RELATIVE_PATHS = {
    "Chrome_Demo/Cache/old_cache_01.tmp", "Chrome_Demo/Cache/old_cache_02.tmp",
    "Chrome_Demo/Cache/old_cache_03.dat", "Chrome_Demo/Temp/old_temp_01.tmp",
    "Chrome_Demo/Logs/old_log_01.log", "Chrome_Demo/Active/recent_data.db",
    "Chrome_Demo/Active/Cookies", "Electron_Demo/Cache/old_cache_01.tmp",
    "Electron_Demo/Cache/old_cache_02.tmp", "Electron_Demo/Temp/old_temp_01.tmp",
    "Electron_Demo/Active/current_session.db",
}
# Real System Active Mode Sandbox Directory & Manifests
REAL_BASE_DIR = os.path.join(LOCAL_APP_DATA, "ZombieDataPurger")
REAL_QUARANTINE_DIR = os.path.join(REAL_BASE_DIR, "RealQuarantine")
REAL_MANIFEST_FILE = os.path.join(REAL_BASE_DIR, "real_quarantine_manifest.json")
REAL_REPORT_FILE = os.path.join(REAL_BASE_DIR, "real_audit_report.json")
REAL_FROZEN_MANIFEST_FILE = os.path.join(REAL_BASE_DIR, "real_frozen_manifest.json")
REAL_TASK_AUDIT_FILE = os.path.join(REAL_BASE_DIR, "real_task_audit_report.json")

# Scanner & Classifier Thresholds
DEFAULT_AGE_THRESHOLD_DAYS = 14
QUARANTINE_RETENTION_DAYS = 30

# Rule Scoring Weights (Total max = 100)
WEIGHT_KNOWN_CACHE_TEMP_DIR = 30
WEIGHT_PROCESS_INACTIVE = 30
WEIGHT_AGE_ABOVE_THRESHOLD = 20
WEIGHT_TEMP_FILE_PATTERN = 10
WEIGHT_FILE_ACCESSIBLE = 10

# Classification Threshold Brackets
CLASSIFICATION_ZOMBIE = "POTENTIAL ZOMBIE DATA"
CLASSIFICATION_UNCERTAIN = "UNCERTAIN"
CLASSIFICATION_KEEP = "KEEP"

SCORE_THRESHOLD_ZOMBIE = 80
SCORE_THRESHOLD_UNCERTAIN = 50

# Protected File & Database Patterns (ALWAYS KEEP - ZERO CORRUPTION GUARANTEE)
PROTECTED_FILE_PATTERNS = [
    "cookies",
    "login data",
    "web data",
    "bookmarks",
    "history",
    "preferences",
    "secure preferences",
    "current session",
    "current tabs",
    "session storage",
    "local storage",
    "extension state",
    "indexeddb",
    "leveldb",
    "credentials",
    "account",
    "vault",
    "keychain",
    "wallet",
    "identity",
    "sync_data",
]

PROTECTED_EXTENSIONS = [
    ".key",
    ".pem",
    ".crt",
    ".auth",
    ".credentials",
]

TEMP_CACHE_EXTENSIONS = [
    ".tmp",
    ".temp",
    ".log",
    ".cache",
    ".dat",
    ".bak",
    ".old",
    ".dmp",
    ".chk",
]

KNOWN_CACHE_DIR_KEYWORDS = [
    "cache",
    "code cache",
    "gpu cache",
    "gpucache",
    "shadercache",
    "temp",
    "tmp",
    "logs",
    "crashpad",
    "dawncache",
]

# Allowed Cache/Temp Subdirectory Keywords for Real Quarantine
# (Files OUTSIDE these subdirectories are NEVER eligible for quarantine on real systems)
ALLOWED_CACHE_SUBDIRS = [
    "cache",
    "code cache",
    "gpucache",
    "gpu cache",
    "dawncache",
    "shadercache",
    "crashpad",
    "logs",
    "temp",
    "tmp",
]

# System Protected Root Directories (NEVER TOUCH - STRICT IMMUNITY)
SYSTEM_PROTECTED_ROOTS = [
    os.environ.get("SystemRoot", "C:\\Windows"),
    os.environ.get("ProgramFiles", "C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    os.path.join(os.path.expanduser("~"), "Documents"),
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "Downloads"),
]

# Supported Applications Configuration
APP_DEFINITIONS = {
    "Google Chrome": {
        "process_name": "chrome.exe",
        "relative_path": os.path.join(LOCAL_APP_DATA, "Google", "Chrome", "User Data"),
        "type": "Browser",
    },
    "Microsoft Edge": {
        "process_name": "msedge.exe",
        "relative_path": os.path.join(LOCAL_APP_DATA, "Microsoft", "Edge", "User Data"),
        "type": "Browser",
    },
    "Visual Studio Code": {
        "process_name": "Code.exe",
        "relative_path": os.path.join(ROAMING_APP_DATA, "Code"),
        "type": "Electron",
    },
    "Discord": {
        "process_name": "Discord.exe",
        "relative_path": os.path.join(ROAMING_APP_DATA, "discord"),
        "type": "Electron",
    },
    "Microsoft Teams": {
        "process_name": "ms-teams.exe",
        "relative_path": os.path.join(LOCAL_APP_DATA, "Packages"),
        "type": "Electron",
    },
    "Slack": {
        "process_name": "slack.exe",
        "relative_path": os.path.join(ROAMING_APP_DATA, "Slack"),
        "type": "Electron",
    },
}

# Reviewed layouts relative to each application's configured data root.
# Browser profiles use an approved profile component followed by a cache component.
CACHE_LAYOUTS = {
    "Google Chrome": {"kind": "browser_profile"},
    "Microsoft Edge": {"kind": "browser_profile"},
    "Visual Studio Code": {"kind": "direct", "directories": {"cache", "cacheddata", "cachedextensionvsixs", "code cache", "gpucache", "logs"}},
    "Discord": {"kind": "direct", "directories": {"cache", "code cache", "gpucache", "dawncache", "crashpad"}},
    "Slack": {"kind": "direct", "directories": {"cache", "code cache", "gpucache", "dawncache", "crashpad"}},
    # Teams points at the broad Packages root; keep it inspect-only until an
    # installation-specific profile path can be identified and reviewed.
    "Microsoft Teams": {"kind": "disabled"},
}

# ==============================================================================
# ZOMBIE TASK & MEMORY PURGER CONFIGURATION (ENHANCEMENT)
# ==============================================================================

# Demo Frozen Manifest & Task Audit Files
DEMO_FROZEN_MANIFEST_FILE = os.path.join(DEMO_BASE_DIR, "frozen_tasks_manifest.json")
DEMO_TASK_AUDIT_FILE = os.path.join(DEMO_BASE_DIR, "task_audit_report.json")

# Task Monitoring Thresholds
TASK_IO_ACTIVE_THRESHOLD_BYTES = 50 * 1024  # 50 KB/s - Active download guard
TASK_MEM_HIGH_THRESHOLD_MB = 100            # 100 MB - Dormant memory threshold
TASK_IDLE_MINUTES_THRESHOLD = 30            # 30 minutes idle threshold
TASK_WATCHDOG_INTERVAL_SECONDS = 4          # Watchdog scan cycle

# Task Scoring Weights (0 to 100 Points)
WEIGHT_TASK_WINDOW_CLOSED_OR_MINIMIZED = 35  # Window closed to tray or minimized
WEIGHT_TASK_IDLE_DURATION = 30               # No user interaction for > threshold
WEIGHT_TASK_ZERO_IO = 20                     # Zero disk/network write activity (< 5 KB/s)
WEIGHT_TASK_HIGH_MEM_IDLE = 15               # Holding > 100 MB RAM while CPU is 0%

# Task Classification Brackets
TASK_CLASSIFICATION_ZOMBIE = "POTENTIAL ZOMBIE TASK"
TASK_CLASSIFICATION_UNCERTAIN = "UNCERTAIN TASK"
TASK_CLASSIFICATION_KEEP = "KEEP (ACTIVE WORK)"

TASK_SCORE_THRESHOLD_ZOMBIE = 80
TASK_SCORE_THRESHOLD_UNCERTAIN = 50

# Core Protected OS Processes (NEVER SUSPEND OR TOUCH - ZERO CORRUPTION SHIELD)
PROTECTED_OS_PROCESSES = [
    "explorer.exe",
    "svchost.exe",
    "csrss.exe",
    "smss.exe",
    "winlogon.exe",
    "lsass.exe",
    "services.exe",
    "system",
    "registry",
    "taskmgr.exe",
    "conhost.exe",
    "dwm.exe",
    "sihost.exe",
    "fontdrvhost.exe",
    "spoolsv.exe",
    "antigravity ide.exe",
    "antigravity.exe",
]

# Monitored Task Profiles (Browsers, Electron, Background Services, Dev Runtimes)
MONITORED_TASK_PROFILES = {
    "Google Chrome": {
        "process_name": "chrome.exe",
        "category": "Browser",
        "protect_downloads": True,
    },
    "Microsoft Edge": {
        "process_name": "msedge.exe",
        "category": "Browser",
        "protect_downloads": True,
    },
    "Microsoft Edge WebView2": {
        "process_name": "msedgewebview2.exe",
        "category": "Browser Runtime",
        "protect_downloads": True,
    },
    "Brave Browser": {
        "process_name": "brave.exe",
        "category": "Browser",
        "protect_downloads": True,
    },
    "WhatsApp Desktop": {
        "process_name": "WhatsApp.exe",
        "category": "Tray / Messaging",
        "protect_downloads": False,
    },
    "Discord": {
        "process_name": "Discord.exe",
        "category": "Electron / Voice",
        "protect_downloads": False,
    },
    "Spotify": {
        "process_name": "Spotify.exe",
        "category": "Media",
        "protect_downloads": False,
    },
    "Visual Studio Code": {
        "process_name": "Code.exe",
        "category": "Electron / IDE",
        "protect_downloads": False,
    },
    "Slack": {
        "process_name": "slack.exe",
        "category": "Electron / Collab",
        "protect_downloads": False,
    },
    "Microsoft Teams": {
        "process_name": "ms-teams.exe",
        "category": "Electron / Collab",
        "protect_downloads": False,
    },
    "Oracle Database Service": {
        "process_name": "oracle.exe",
        "category": "Database Engine",
        "protect_downloads": False,
    },
    "Node.js Background Server": {
        "process_name": "node.exe",
        "category": "Dev Runtime",
        "protect_downloads": False,
    },
    "Python Background Worker": {
        "process_name": "python.exe",
        "category": "Dev Runtime",
        "protect_downloads": False,
    },
}

