# Zombie Data Purger: Autonomous Browser and Electron Cache Management System

Zombie Data Purger is a Windows desktop application engineered for intelligent cache discovery, explainable stale-data intelligence, and zero-corruption lifecycle management across modern Browser (Google Chrome, Microsoft Edge) and Electron (VS Code, Discord, Slack) applications.

---

## 🏛️ Academic Three-Module Architecture

The project is structured into **Three Academic Modules**, containing **Nine Tasks**, and **Twenty-Seven Activities**. Every activity maps directly to implemented Python methods, inputs, processing logic, and outputs.

### Summary Overview:
| Main Module | Tasks | Activities | Focus Area |
|---|:---:|:---:|---|
| **Module 1 – Intelligent Application Discovery and Scanning** | 3 | 9 | Application identification, cache layout verification, recursive scanning & SHA-256 duplicate detection |
| **Module 2 – Zombie Data Intelligence and Classification** | 3 | 9 | Explainable heuristic scoring, risk categorization & fail-closed safety policy enforcement |
| **Module 3 – Secure Cleanup, Recovery and Lifecycle Management** | 3 | 9 | Reversible quarantine with SHA-256 integrity, 1-click restore, retention-based purge & audit logging |
| **Total** | **9** | **27** | **100% Fully Implemented in `academic_core.py`** |

---

## 📋 Comprehensive 27-Activity Mapping Table

| Activity ID | Activity Name | Program / Function | Input | Processing Logic | Output |
|:---:|---|---|---|---|---|
| **1.1.1** | Browser and Electron application identification | `ApplicationDiscovery.identify_applications` | Operating mode | Inspects registry, user data paths, and sandbox roots to identify targets | List of application records |
| **1.1.2** | Supported cache directory detection | `ApplicationDiscovery.detect_supported_cache_directories` | Application profile dict | Inspects directories for verified cache keywords (`Cache`, `Code Cache`, `GPUCache`, etc.) | List of verified cache paths |
| **1.1.3** | Application path verification | `ApplicationDiscovery.verify_application_path` | Target filesystem path | Canonicalizes path, checks readability, verifies free of symlinks/reparse points | Path verification status |
| **1.2.1** | Recursive directory scanning within approved locations | `FileScanner.scan_directory` | App info, age threshold, limit | Recursively walks approved cache hierarchies, enforcing strict exclusion of symlinks | Scan results dictionary |
| **1.2.2** | File metadata extraction | `FileScanner.extract_file_metadata` | File path string | Queries OS stat for size, timestamps, device ID, inode, and exclusive accessibility | Normalized metadata dict |
| **1.2.3** | File type and extension identification | `FileScanner.identify_file_type_and_extension` | File path string | Categorizes extension into Web Cache, Shader, Log, Temporary, or Protected Database | Category and badge token |
| **1.3.1** | File size and timestamp analysis | `FileScanner.analyze_file_size_and_timestamps` | Metadata, threshold days | Calculates elapsed age in days, time delta, and assigns size brackets | Size and age analysis dict |
| **1.3.2** | Duplicate file identification using hashes | `FileScanner.identify_duplicates_sha256` | Candidate file list | Groups identical byte sizes first, computes SHA-256 to confirm bitwise duplicates | Duplicate savings report |
| **1.3.3** | Scan report generation and SQLite storage | `FileScanner.generate_scan_report_and_store` | Scan result, mode, db store | Commits scan session and individual candidate rows into SQLite and logs audit event | Saved scan ID and report |
| **2.1.1** | File age analysis | `ZombieDataClassifier.analyze_file_age` | mtime, ctime, threshold | Calculates elapsed age from system clock, tests threshold delta | Age analysis dict |
| **2.1.2** | Access and modification pattern analysis | `ZombieDataClassifier.analyze_access_modification_patterns` | Metadata dictionary | Evaluates file locks and checks if owning process is closed (dormant cache) | Dormancy pattern dict |
| **2.1.3** | Cache characteristics evaluation | `ZombieDataClassifier.evaluate_cache_characteristics` | Metadata dictionary | Matches path against disposable cache subdirectories (GPUCache, Code Cache, Temp) | Cache characteristics dict |
| **2.2.1** | Explainable zombie score calculation | `ZombieDataClassifier.calculate_zombie_score` | Metadata, threshold days | Evaluates transparent weights (Cache +30, App closed +30, Age +20, Temp +10, Access +10) | Heuristic score (0-100) |
| **2.2.2** | Risk category classification | `ZombieDataClassifier.classify_risk_category` | Score, is_protected | Applies brackets: >=80 Zombie (High Risk), >=50 Uncertain, else Keep | Risk category and level |
| **2.2.3** | Classification reason generation | `ZombieDataClassifier.generate_classification_reasons` | Metadata, score data | Generates positive/negative factors, confidence metric, and recommendation | Explainable reasons dict |
| **2.3.1** | Protected file and directory detection | `SafetyPolicy.is_protected_target` | File path string | Verifies against protected patterns (cookies, passwords, bookmarks, sessions, OS roots) | Protection decision dict |
| **2.3.2** | Symbolic link and file identity validation | `SafetyPolicy.validate_symlink_and_reparse_point` | File path string | Inspects path and all ancestors for symlinks, junctions, and reparse points | Reparse validation dict |
| **2.3.3** | Policy-based cleanup eligibility decision | `SafetyPolicy.evaluate_cleanup_eligibility` | Operation, paths, mode, meta | Central fail-closed authorization. High zombie score alone NEVER authorizes cleanup | `PolicyDecision` (ALLOW/DENY) |
| **3.1.1** | User review and candidate selection | `QuarantineManager.filter_and_select_candidates` | Candidate list, indices | Validates user selection, excludes unreviewed files, calculates review space | Reviewed candidate list |
| **3.1.2** | Secure quarantine with integrity verification | `QuarantineManager.quarantine_candidate` | File record, mode, auto flag | Computes SHA-256 pre-move, moves to isolated vault, confirms hash, records manifest | Quarantine report |
| **3.1.3** | Retention-based purge eligibility validation | `QuarantineManager.validate_purge_eligibility` | Quarantine record, days, mode | Verifies days elapsed against retention policy (default 30 days) before permanent delete | Purge eligibility report |
| **3.2.1** | File restoration | `QuarantineManager.restore_quarantined_file` | Manifest ID, mode | Validates destination, reconstructs parent folders, safely restores file | Restoration report |
| **3.2.2** | Integrity verification using SHA-256 | `QuarantineManager.verify_restoration_integrity` | Restored path, expected hash | Re-computes SHA-256 of restored file and verifies exact cryptographic match | Integrity status report |
| **3.2.3** | Interrupted operation recovery and rollback | `QuarantineManager.reconcile_and_rollback` | Mode string | Cleans orphaned temporary manifest files and reconciles inconsistent records | Reconciliation report |
| **3.3.1** | Background scanning and monitoring | `BackgroundScanWorker` | Mode, interval | Runs periodic background scans without freezing UI or touching processes | Background telemetry report |
| **3.3.2** | SQLite audit logging and activity tracking | `AuditStore.record_event` | Operation, mode, decision | Persists durable audit row in SQLite with ISO timestamp and UUID | Audit event row |
| **3.3.3** | Dashboard analytics and cleanup reports | `AuditStore.get_dashboard_analytics` | None (queries SQLite) | Aggregates scan sessions, candidates, quarantine events, and space savings | Dashboard metrics dict |

---

## 🎨 Futuristic Light UI Design

The user interface has been completely redesigned with a **premium light aesthetic** inspired by modern cybersecurity and file analytics dashboards (Filetio, Dashbox, FortifyData Enterprise):
- **Surfaces**: Clean white (`#ffffff`) card surfaces with soft-slate backgrounds (`#f8fafc`, `#f1f5f9`) and subtle border lines (`#e2e8f0`).
- **Accent Palette**: Deep Indigo (`#4f46e5`, `#6366f1`), Emerald Green (`#10b981`), Amber (`#f59e0b`), and Rose (`#ef4444`).
- **Interactive Visualizations**:
  - Vector Circular Storage Gauge with percentage arc and category legend.
  - 7-Day Activity & Scan Trend Line Chart with connected data points and hover dates.
  - Cyber Risk and Zombie Severity Indicators.
- **11 Dedicated Functional Screens**:
  1. **Command Center** — Overall project KPI cards, circular storage gauge, 7-day trend chart, recent sessions.
  2. **Application Discovery** — Detected applications, verified cache directories, and path verification.
  3. **Intelligent Scanner** — Interactive scan controls, age slider, live progress, filterable candidate file table.
  4. **Zombie Intelligence** — Explainable scoring breakdown, rule weight visualizer, and confidence metric.
  5. **Safety Center** — Fail-closed policy status, hard whitelist immunity, and interactive policy evaluator.
  6. **Quarantine Vault** — Isolated artifacts table, SHA-256 checksums, 1-click restore, and retention status.
  7. **Recovery Center** — Restoration controls, cryptographic SHA-256 integrity verifier, and crash reconciler.
  8. **Monitoring Center** — Periodic background scanner scheduler and read-only process telemetry.
  9. **Audit & Reports** — Durable SQLite audit trail with JSON export capabilities.
  10. **Presentation Mode** — 11-stage guided demonstration workflow for university examination.
  11. **Settings & Configuration** — Thresholds, retention rules, and full 27-activity architecture mapping.

---

## 🛡️ Zero-Corruption Safety Principles

1. **Central Fail-Closed Policy**: Any unknown operating mode, missing file identity, locked file, or unapproved path fails closed immediately.
2. **Hard Whitelist Immunity**: Credentials, passwords, cookies, history, bookmarks, sessions, IndexedDB, and LevelDB databases are permanently immune from quarantine or purge.
3. **No Process Interference**: Process freezing, suspension, and killing are strictly dropped and disabled. Process monitoring is 100% read-only telemetry.
4. **Symlink and Reparse Point Immunity**: Symlinks, directory junctions, and reparse points are rejected during directory traversal and quarantine.
5. **Cryptographic Integrity**: Every quarantined file has its SHA-256 checksum calculated before move, after move, and upon restoration.
6. **No-Overwrite Guarantee**: Restoration will never overwrite an existing file at destination.

---

## 🚀 Installation & Execution

### Prerequisites:
- Windows 10 or Windows 11
- Python 3.10 or newer (with Tkinter included)

### Setup Instructions:
```powershell
# 1. Clone / Navigate to project directory
cd C:\Users\ADMIN\.gemini\antigravity\scratch\zombie_data_purger

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install required dependencies
python -m pip install -r requirements.txt

# 4. Launch Application GUI
python main.py
```

---

## 🎓 Examination Demonstration Workflow (11 Stages)

To demonstrate the full project to college examiners:
1. Launch `python main.py`.
2. Ensure **🟢 Safe Demo Mode** is selected in the top navigation bar.
3. In the left sidebar, click **🚀 Presentation Mode**.
4. Click **▶️ Run Complete 11-Stage Demonstration**:
   - **Stage 1**: Application Discovery (`Chrome_Demo`, `Electron_Demo`).
   - **Stage 2**: Cache Directory Identification (`Cache`, `Temp`, `Logs`).
   - **Stage 3**: File Scanning and Metadata Extraction.
   - **Stage 4**: Zombie Data Analysis (Age & Dormancy calculation).
   - **Stage 5**: Explainable Score Calculation (0 to 100).
   - **Stage 6**: Safety Policy Evaluation (Allow cache files, block `Cookies`).
   - **Stage 7**: User Review and Approval.
   - **Stage 8**: Quarantine with SHA-256 Checksum Verification.
   - **Stage 9**: File Restoration and Cryptographic Hash Check.
   - **Stage 10**: Retention-based Purge Eligibility Validation.
   - **Stage 11**: Durable SQLite Audit Log & Summary Report.
5. The live console displays all inputs, processing status, outputs, and safeguard enforcements.
6. Operates purely within `%LOCALAPPDATA%\ZombieDataPurgerDemo\` without touching real browser data.

---

## 🧪 Testing and Verification

Run the complete 24-test unit and integration suite:
```powershell
python -m unittest discover -s . -p "test_*.py"
```

All 24 tests run non-destructively in temporary sandboxes, verifying:
- All 27 individual academic activities (`test_all_activities.py`).
- Duplicate detection and SHA-256 matching (`test_system_integration.py`).
- Safety policy fail-closed authorization (`test_safety_policy.py`).
- Quarantine and restoration fidelity (`test_real_system_safety.py`).
- Cache-confined scanning and immunity (`test_purger.py`).
#   Z o m b i e - d a t a - p u r g e r  
 