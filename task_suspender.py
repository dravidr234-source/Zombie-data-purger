"""Compatibility API that explicitly disables all process control."""
import json
import os
from datetime import datetime, timezone

from config import MODE_SAFE_DEMO


class TaskSuspender:
    """Legacy name retained for imports; no suspend, resume, terminate, or signal calls exist."""

    @staticmethod
    def suspend_task(*args, **kwargs):
        print("[ProcessMonitor] BLOCKED: Process suspension is not supported.")
        return False

    @staticmethod
    def resume_task(*args, **kwargs):
        print("[ProcessMonitor] BLOCKED: Process control is not supported.")
        return False

    @staticmethod
    def get_frozen_tasks(mode=None):
        # Legacy manifests are not treated as proof of a currently suspended PID.
        return []

    @staticmethod
    def export_task_audit_log(file_path=None, mode=None):
        if not file_path:
            raise ValueError("Choose an export path for the process-monitor report.")
        parent = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(parent, exist_ok=True)
        report = {
            "title": "Read-only Process Monitor Report",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode or MODE_SAFE_DEMO,
            "process_control": "disabled",
            "frozen_processes": [],
            "note": "No process was suspended, resumed, terminated, or modified by this application.",
        }
        with open(file_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        return file_path
