import json
import os
from datetime import datetime
from config import APP_NAME, APP_VERSION, ACADEMIC_MODULE_NAME, DEMO_REPORT_FILE, REAL_REPORT_FILE
from quarantine import QuarantineManager
from database import get_audit_store

class AuditLogger:
    """
    Sub-component of Zombie Data Purger responsible for logging operations,
    audit records, and exporting scan/quarantine summaries to JSON.
    """

    @classmethod
    def generate_audit_report(cls, mode: str, scan_results: dict, export_file_path: str = None) -> str:
        """Generates comprehensive audit report JSON."""
        manifest = QuarantineManager.load_manifest(mode)
        store = get_audit_store()

        report = {
            "application_metadata": {
                "name": APP_NAME,
                "version": APP_VERSION,
                "academic_module": ACADEMIC_MODULE_NAME,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "session_context": {
                "operating_mode": mode,
                "is_demo_mode": "SAFE DEMO MODE" in mode,
                "is_read_only": "READ-ONLY" in mode
            },
            "scan_summary": {
                "scanned_files_count": scan_results.get("scanned_count", 0),
                "zombie_candidates_count": scan_results.get("zombie_count", 0),
                "uncertain_count": scan_results.get("uncertain_count", 0),
                "keep_count": scan_results.get("keep_count", 0),
                "potential_reclaimable_bytes": scan_results.get("potential_reclaimable_bytes", 0),
                "potential_space_formatted": scan_results.get("potential_space_formatted", "0 B")
            },
            "quarantine_history": manifest,
            "detected_files": scan_results.get("files", []),
            "recent_audit_events": store.list_events(250),
            "recent_scan_sessions": store.list_scans(250),
        }

        target_file = export_file_path or (DEMO_REPORT_FILE if "DEMO" in (mode or "") else REAL_REPORT_FILE)
        os.makedirs(os.path.dirname(target_file), exist_ok=True)

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return target_file
