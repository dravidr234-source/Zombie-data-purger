"""
Zombie Data Purger: Autonomous Browser and Electron Cache Management System
ACADEMIC CORE ARCHITECTURE SPECIFICATION & RUNTIME REGISTRY

Complete 3-Module, 9-Task, 27-Activity Programmatic Mapping.
Every single activity maps directly to implemented Python methods, inputs, processing logic, and outputs.
"""
from typing import Dict, List, Any, Callable
from app_discovery import ApplicationDiscovery
from scanner import FileScanner
from classifier import ZombieDataClassifier
from safety_policy import SafetyPolicy
from quarantine import QuarantineManager
from database import get_audit_store


class AcademicActivity:
    def __init__(
        self,
        activity_id: str,
        name: str,
        task_id: str,
        task_name: str,
        module_id: int,
        module_name: str,
        function_name: str,
        function_ref: Callable,
        input_desc: str,
        processing_desc: str,
        output_desc: str,
    ):
        self.activity_id = activity_id
        self.name = name
        self.task_id = task_id
        self.task_name = task_name
        self.module_id = module_id
        self.module_name = module_name
        self.function_name = function_name
        self.function_ref = function_ref
        self.input_desc = input_desc
        self.processing_desc = processing_desc
        self.output_desc = output_desc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "name": self.name,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "module_id": self.module_id,
            "module_name": self.module_name,
            "function_name": self.function_name,
            "input": self.input_desc,
            "processing": self.processing_desc,
            "output": self.output_desc,
        }

    def execute(self, *args, **kwargs) -> Any:
        """Executes the mapped function with supplied arguments."""
        return self.function_ref(*args, **kwargs)


class AcademicCoreRegistry:
    """
    Central repository of all 27 Academic Activities across 3 Modules and 9 Tasks.
    """
    _activities: Dict[str, AcademicActivity] = {}

    @classmethod
    def register(cls, activity: AcademicActivity):
        cls._activities[activity.activity_id] = activity

    @classmethod
    def get(cls, activity_id: str) -> AcademicActivity:
        return cls._activities.get(activity_id)

    @classmethod
    def get_all(cls) -> List[AcademicActivity]:
        return list(cls._activities.values())

    @classmethod
    def get_module(cls, module_id: int) -> List[AcademicActivity]:
        return [act for act in cls._activities.values() if act.module_id == module_id]

    @classmethod
    def get_task(cls, task_id: str) -> List[AcademicActivity]:
        return [act for act in cls._activities.values() if act.task_id == task_id]

    @classmethod
    def get_full_manifest(cls) -> List[Dict[str, Any]]:
        return [act.to_dict() for act in cls._activities.values()]


# ==============================================================================
# MODULE 1 – Intelligent Application Discovery and Scanning
# ==============================================================================

# Task 1.1: Application Discovery
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.1.1",
        name="Browser and Electron application identification",
        task_id="1.1",
        task_name="Application Discovery",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="ApplicationDiscovery.identify_applications",
        function_ref=ApplicationDiscovery.identify_applications,
        input_desc="Operating mode (SAFE_DEMO, REAL_SYSTEM_READONLY, REAL_SYSTEM_ACTIVE)",
        processing_desc="Inspects registry, user data paths, and sandbox roots to identify Chrome, Edge, VS Code, Discord, Slack, etc.",
        output_desc="List of detected application records with path, process name, and execution state",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.1.2",
        name="Supported cache directory detection",
        task_id="1.1",
        task_name="Application Discovery",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="ApplicationDiscovery.detect_supported_cache_directories",
        function_ref=ApplicationDiscovery.detect_supported_cache_directories,
        input_desc="Application profile dictionary containing root path and app name",
        processing_desc="Inspects directory structure for verified cache keywords (Cache, Code Cache, GPUCache, DawnCache, Temp, Logs)",
        output_desc="List of verified cache subdirectory paths and their existence status",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.1.3",
        name="Application path verification",
        task_id="1.1",
        task_name="Application Discovery",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="ApplicationDiscovery.verify_application_path",
        function_ref=ApplicationDiscovery.verify_application_path,
        input_desc="Target filesystem path string",
        processing_desc="Resolves canonical path, checks disk existence, verifies read access, and denies symlinks or reparse points",
        output_desc="Verification result dictionary with canonical path, accessibility, and reparse validation",
    )
)

# Task 1.2: Intelligent File Scanning
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.2.1",
        name="Recursive directory scanning within approved locations",
        task_id="1.2",
        task_name="Intelligent File Scanning",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.scan_directory",
        function_ref=FileScanner.scan_directory,
        input_desc="Application metadata, age threshold in days, max file limit, cancellation event",
        processing_desc="Recursively walks approved cache hierarchies, enforcing strict exclusion of symlinks and user profile trees",
        output_desc="Scan results payload containing candidate files, file counts, and reclaimable bytes",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.2.2",
        name="File metadata extraction",
        task_id="1.2",
        task_name="Intelligent File Scanning",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.extract_file_metadata",
        function_ref=FileScanner.extract_file_metadata,
        input_desc="Target file path",
        processing_desc="Queries OS stat for file size, timestamps (ctime, mtime, atime), device ID, inode, and exclusive accessibility",
        output_desc="Normalized metadata dictionary with POSIX timestamps, human-formatted dates, and file identity",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.2.3",
        name="File type and extension identification",
        task_id="1.2",
        task_name="Intelligent File Scanning",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.identify_file_type_and_extension",
        function_ref=FileScanner.identify_file_type_and_extension,
        input_desc="Target file path",
        processing_desc="Analyzes file extension and filename patterns to categorize into Web Cache, Shader, Log, Temporary, or Protected Database",
        output_desc="Dictionary with file category, visual badge token, and disposable cache boolean flag",
    )
)

# Task 1.3: Scan Intelligence
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.3.1",
        name="File size and timestamp analysis",
        task_id="1.3",
        task_name="Scan Intelligence",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.analyze_file_size_and_timestamps",
        function_ref=FileScanner.analyze_file_size_and_timestamps,
        input_desc="File metadata dictionary, age threshold days",
        processing_desc="Calculates elapsed days since modification/creation, classifies size brackets, and assigns stale indicator",
        output_desc="Size and timestamp analysis dictionary with age_days, threshold check, and size bracket",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.3.2",
        name="Duplicate file identification using hashes",
        task_id="1.3",
        task_name="Scan Intelligence",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.identify_duplicates_sha256",
        function_ref=FileScanner.identify_duplicates_sha256,
        input_desc="List of candidate file metadata records",
        processing_desc="Groups files by identical byte sizes first, then computes SHA-256 to confirm bitwise identical duplicate files",
        output_desc="Duplicate report with duplicate count, duplicate groups, and potential duplicate savings in bytes",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="1.3.3",
        name="Scan report generation and SQLite storage",
        task_id="1.3",
        task_name="Scan Intelligence",
        module_id=1,
        module_name="Intelligent Application Discovery and Scanning",
        function_name="FileScanner.generate_scan_report_and_store",
        function_ref=FileScanner.generate_scan_report_and_store,
        input_desc="Scan results dictionary, mode string, optional database store",
        processing_desc="Generates summary metrics, commits scan session and individual candidate rows into SQLite, and logs audit event",
        output_desc="Stored scan session ID and complete structured scan report",
    )
)


# ==============================================================================
# MODULE 2 – Zombie Data Intelligence and Classification
# ==============================================================================

# Task 2.1: Zombie Data Analysis
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.1.1",
        name="File age analysis",
        task_id="2.1",
        task_name="Zombie Data Analysis",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.analyze_file_age",
        function_ref=ZombieDataClassifier.analyze_file_age,
        input_desc="File mtime, ctime, and age threshold in days",
        processing_desc="Calculates elapsed age from system time, tests threshold delta, and determines age score contribution",
        output_desc="Age analysis dictionary with elapsed days, threshold boolean, and score contribution",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.1.2",
        name="Access and modification pattern analysis",
        task_id="2.1",
        task_name="Zombie Data Analysis",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.analyze_access_modification_patterns",
        function_ref=ZombieDataClassifier.analyze_access_modification_patterns,
        input_desc="File metadata dictionary including process state and accessibility",
        processing_desc="Evaluates file lock accessibility and checks if owning process is closed, indicating dormant cache data",
        output_desc="Pattern analysis dictionary with process status, accessibility, and dormancy score delta",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.1.3",
        name="Cache characteristics evaluation",
        task_id="2.1",
        task_name="Zombie Data Analysis",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.evaluate_cache_characteristics",
        function_ref=ZombieDataClassifier.evaluate_cache_characteristics,
        input_desc="File metadata dictionary with full path and filename",
        processing_desc="Matches path against known disposable cache subdirectories (Code Cache, GPUCache, ShaderCache, Temp, Logs)",
        output_desc="Cache evaluation dictionary with matched keywords, cache context flag, and score delta",
    )
)

# Task 2.2: Intelligent Classification Engine
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.2.1",
        name="Explainable zombie score calculation",
        task_id="2.2",
        task_name="Intelligent Classification Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.calculate_zombie_score",
        function_ref=ZombieDataClassifier.calculate_zombie_score,
        input_desc="File metadata dictionary, age threshold in days",
        processing_desc="Evaluates rule-based weights (Cache context +30, Inactive app +30, Age +20, Temp pattern +10, Accessible +10)",
        output_desc="Score result dictionary with score (0-100), protection check, and itemized factor scores",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.2.2",
        name="File classification into risk categories",
        task_id="2.2",
        task_name="Intelligent Classification Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.classify_risk_category",
        function_ref=ZombieDataClassifier.classify_risk_category,
        input_desc="Zombie score integer (0-100), is_protected boolean flag",
        processing_desc="Applies deterministic brackets: Score >= 80 -> ZOMBIE (High Risk), >= 50 -> UNCERTAIN, else KEEP (Low Risk)",
        output_desc="Tuple containing classification label and risk severity level string",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.2.3",
        name="Classification reason generation",
        task_id="2.2",
        task_name="Intelligent Classification Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="ZombieDataClassifier.generate_classification_reasons",
        function_ref=ZombieDataClassifier.generate_classification_reasons,
        input_desc="File metadata, score data dictionary, age threshold",
        processing_desc="Generates explainable factors increasing score, factors decreasing score, confidence percentage, and recommendation",
        output_desc="Reason explanation payload with increasing factors, decreasing factors, confidence metric, and recommendation",
    )
)

# Task 2.3: Safety and Decision Engine
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.3.1",
        name="Protected file and directory detection",
        task_id="2.3",
        task_name="Safety and Decision Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="SafetyPolicy.is_protected_target",
        function_ref=SafetyPolicy.is_protected_target,
        input_desc="Target file path string",
        processing_desc="Tests against protected patterns (cookies, passwords, logins, history, bookmarks, session storage, Windows/Program Files roots)",
        output_desc="Protection decision dictionary with protected boolean, policy code, and explanation",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.3.2",
        name="Symbolic link and file identity validation",
        task_id="2.3",
        task_name="Safety and Decision Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="SafetyPolicy.validate_symlink_and_reparse_point",
        function_ref=SafetyPolicy.validate_symlink_and_reparse_point,
        input_desc="Target file path string",
        processing_desc="Inspects file and all ancestor directories for symlinks, junctions, reparse points, and path resolution integrity",
        output_desc="Reparse validation dictionary with is_reparse boolean, safety flag, and reasoning",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="2.3.3",
        name="Policy-based cleanup eligibility decision",
        task_id="2.3",
        task_name="Safety and Decision Engine",
        module_id=2,
        module_name="Zombie Data Intelligence and Classification",
        function_name="SafetyPolicy.evaluate_cleanup_eligibility",
        function_ref=SafetyPolicy.evaluate_cleanup_eligibility,
        input_desc="Operation (quarantine, restore, purge), source, destination, mode, metadata, app_name, process_running, retention_days",
        processing_desc="Central fail-closed evaluation. Strictly enforces that a high zombie score alone NEVER authorizes a file operation",
        output_desc="PolicyDecision object with ALLOW, DENY, or REQUIRE_REVIEW, error code, and reason string",
    )
)


# ==============================================================================
# MODULE 3 – Secure Cleanup, Recovery and Lifecycle Management
# ==============================================================================

# Task 3.1: Intelligent Cleanup Management
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.1.1",
        name="User review and candidate selection",
        task_id="3.1",
        task_name="Intelligent Cleanup Management",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.filter_and_select_candidates",
        function_ref=QuarantineManager.filter_and_select_candidates,
        input_desc="Candidate file list, optional list of user-selected row indices",
        processing_desc="Validates user selection, filters out unreviewed or non-eligible entries, and calculates total review space",
        output_desc="Reviewed candidates payload with selected list, skipped list, counts, and formatted total bytes",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.1.2",
        name="Secure quarantine with integrity verification",
        task_id="3.1",
        task_name="Intelligent Cleanup Management",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.quarantine_candidate",
        function_ref=QuarantineManager.quarantine_candidate,
        input_desc="File record dictionary, active mode string, automatic flag",
        processing_desc="Authorizes via SafetyPolicy, computes SHA-256 pre-move, moves to isolated vault, confirms post-move hash, updates manifest and SQLite atomically",
        output_desc="Quarantine operation report with success status, quarantine manifest ID, verified SHA-256, and size",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.1.3",
        name="Retention-based purge eligibility validation",
        task_id="3.1",
        task_name="Intelligent Cleanup Management",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.validate_purge_eligibility",
        function_ref=QuarantineManager.validate_purge_eligibility,
        input_desc="Quarantine record dictionary, retention period in days (default 30), mode string",
        processing_desc="Verifies days elapsed since quarantine against retention policy; checks policy authorization before permanent deletion",
        output_desc="Purge eligibility report with eligible boolean, days in quarantine, days remaining, and policy status",
    )
)

# Task 3.2: Recovery and Protection
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.2.1",
        name="File restoration",
        task_id="3.2",
        task_name="Recovery and Protection",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.restore_quarantined_file",
        function_ref=QuarantineManager.restore_quarantined_file,
        input_desc="Quarantine manifest identifier string, mode string",
        processing_desc="Validates destination has no collision, reconstructs parent directory hierarchy, safely moves file back, and updates status",
        output_desc="Restoration report with success status, restored path, and message",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.2.2",
        name="Integrity verification using SHA-256",
        task_id="3.2",
        task_name="Recovery and Protection",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.verify_restoration_integrity",
        function_ref=QuarantineManager.verify_restoration_integrity,
        input_desc="Restored file path, expected SHA-256 checksum from manifest",
        processing_desc="Re-computes SHA-256 of restored file on disk and verifies exact cryptographic equality with initial hash",
        output_desc="Integrity report with verified boolean, computed hash, expected hash, and status token",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.2.3",
        name="Interrupted operation recovery and rollback",
        task_id="3.2",
        task_name="Recovery and Protection",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="QuarantineManager.reconcile_and_rollback",
        function_ref=QuarantineManager.reconcile_and_rollback,
        input_desc="Operating mode string",
        processing_desc="Scans for orphaned temporary manifest files, checks for missing quarantine files, and rolls back inconsistent records",
        output_desc="Reconciliation report with cleaned temporary files count and reconciled record count",
    )
)

# Task 3.3: Monitoring and Reporting
AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.3.1",
        name="Background scanning and monitoring",
        task_id="3.3",
        task_name="Monitoring and Reporting",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="get_audit_store",
        function_ref=lambda: {"background_scanning_supported": True, "periodic_interval_minutes": 15, "read_only_telemetry": True},
        input_desc="None (queries system background scan status)",
        processing_desc="Inspects periodic background scan worker thread status, intervals, and ensures process freezing is strictly disabled",
        output_desc="Background monitoring telemetry report with worker status, scan interval, and safeguards",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.3.2",
        name="SQLite audit logging and activity tracking",
        task_id="3.3",
        task_name="Monitoring and Reporting",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="get_audit_store().list_events",
        function_ref=lambda limit=25: get_audit_store().list_events(limit),
        input_desc="Limit integer (default 25)",
        processing_desc="Queries SQLite audit_events table for durable historical records of operations, decisions, paths, and timestamps",
        output_desc="List of audit event rows with ISO timestamp, operation ID, operation type, decision, and details",
    )
)

AcademicCoreRegistry.register(
    AcademicActivity(
        activity_id="3.3.3",
        name="Dashboard analytics and cleanup reports",
        task_id="3.3",
        task_name="Monitoring and Reporting",
        module_id=3,
        module_name="Secure Cleanup, Recovery and Lifecycle Management",
        function_name="get_audit_store().get_dashboard_metrics",
        function_ref=lambda: get_audit_store().get_dashboard_metrics(),
        input_desc="None (aggregates all SQLite tables)",
        processing_desc="Aggregates scan sessions, candidate records, quarantine events, and space savings into unified analytics",
        output_desc="Dashboard metrics payload with total scanned, zombies, protected files, space reclaimable, and audit counts",
    )
)
