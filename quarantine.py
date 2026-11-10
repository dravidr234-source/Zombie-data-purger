import os
import shutil
import json
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path

from config import (
    DEMO_BASE_DIR,
    DEMO_QUARANTINE_DIR,
    DEMO_MANIFEST_FILE,
    REAL_BASE_DIR,
    REAL_QUARANTINE_DIR,
    REAL_MANIFEST_FILE,
    MODE_SAFE_DEMO,
    MODE_REAL_SYSTEM_READONLY,
    MODE_REAL_SYSTEM_ACTIVE,
    PROTECTED_FILE_PATTERNS,
    PROTECTED_EXTENSIONS,
    ALLOWED_CACHE_SUBDIRS,
    SYSTEM_PROTECTED_ROOTS,
    QUARANTINE_RETENTION_DAYS,
)
from utils import (
    is_path_inside_allowed_directory,
    is_file_exclusively_accessible,
    format_file_size,
    compute_file_sha256 as _utils_compute_sha256,
)
from safety_policy import SafetyPolicy
from database import get_audit_store
from process_analyzer import ProcessAnalyzer

def compute_file_sha256(file_path: str) -> str:
    """Computes SHA-256 checksum for audit and integrity verification."""
    return _utils_compute_sha256(file_path)

class QuarantineManager:
    """
    Module 3 – Secure Cleanup, Recovery and Lifecycle Management
    Task 3.1 – Intelligent Cleanup Management:
      Activity 3.1.1: User review and candidate selection.
      Activity 3.1.2: Secure quarantine with integrity verification.
      Activity 3.1.3: Retention-based purge eligibility validation.
    Task 3.2 – Recovery and Protection:
      Activity 3.2.1: File restoration.
      Activity 3.2.2: SHA-256 integrity verification.
      Activity 3.2.3: Interrupted operation recovery and rollback.
    """

    audit_store = None

    @classmethod
    def get_manifest_file(cls, mode: str = None) -> str:
        """Returns the appropriate manifest file path based on operating mode."""
        if mode == MODE_REAL_SYSTEM_ACTIVE or mode == MODE_REAL_SYSTEM_READONLY:
            return REAL_MANIFEST_FILE
        return DEMO_MANIFEST_FILE

    @classmethod
    def get_quarantine_dir(cls, mode: str = None) -> str:
        """Returns the appropriate quarantine directory based on operating mode."""
        if mode == MODE_REAL_SYSTEM_ACTIVE or mode == MODE_REAL_SYSTEM_READONLY:
            return REAL_QUARANTINE_DIR
        return DEMO_QUARANTINE_DIR

    @classmethod
    def load_manifest(cls, mode: str = None) -> list:
        """Loads quarantine records from JSON manifest."""
        manifest_file = cls.get_manifest_file(mode)
        if not os.path.exists(manifest_file):
            return []
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list) or any(not isinstance(entry, dict) for entry in records):
                raise ValueError("Quarantine manifest must be a list of records")
            return records
        except Exception as exc:
            raise RuntimeError(f"Quarantine manifest is unreadable; operations are blocked: {manifest_file}: {exc}") from exc

    @classmethod
    def save_manifest(cls, records: list, mode: str = None):
        """Saves quarantine records to JSON manifest atomically."""
        manifest_file = cls.get_manifest_file(mode)
        os.makedirs(os.path.dirname(manifest_file), exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".manifest-", suffix=".tmp", dir=os.path.dirname(manifest_file))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, manifest_file)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    # --------------------------------------------------------------------------
    # TASK 3.1: Intelligent Cleanup Management Activities
    # --------------------------------------------------------------------------

    @classmethod
    def filter_and_select_candidates(cls, candidates_list: list, selected_indices: list = None) -> dict:
        """
        Activity 3.1.1: User review and candidate selection.
        Filters candidate files, applying user review selections and separating
        eligible candidates from protected or skipped files.
        """
        if selected_indices is None:
            # Select all classified as zombie candidates by default for review
            reviewed = [c for c in candidates_list if "ZOMBIE" in c.get("classification", "").upper()]
            skipped = [c for c in candidates_list if "ZOMBIE" not in c.get("classification", "").upper()]
        else:
            idx_set = set(selected_indices)
            reviewed = [c for i, c in enumerate(candidates_list) if i in idx_set]
            skipped = [c for i, c in enumerate(candidates_list) if i not in idx_set]

        total_review_bytes = sum(c.get("size_bytes", 0) for c in reviewed)

        return {
            "reviewed_candidates": reviewed,
            "reviewed_count": len(reviewed),
            "skipped_candidates": skipped,
            "skipped_count": len(skipped),
            "total_review_bytes": total_review_bytes,
            "total_review_formatted": format_file_size(total_review_bytes)
        }

    @classmethod
    def quarantine_candidate(cls, file_record: dict, mode: str, automatic: bool = False) -> dict:
        """
        Activity 3.1.2: Quarantine with integrity verification.
        Aliases quarantine_file with full pre/post SHA-256 verification and atomic recording.
        """
        return cls.quarantine_file(file_record, mode, automatic)

    @classmethod
    def validate_purge_eligibility(cls, quarantine_record: dict, retention_days: int = QUARANTINE_RETENTION_DAYS,
                                   mode: str = None, demo_simulate_retention: bool = False) -> dict:
        """
        Activity 3.1.3: Retention-based purge eligibility validation.
        Validates whether a quarantined file meets retention period (default 30 days)
        and all security criteria before permanent purge can be authorized.
        """
        timestamp_str = quarantine_record.get("timestamp") or quarantine_record.get("quarantined_at", "")
        quarantine_path = quarantine_record.get("quarantine_path", "")
        
        try:
            quarantined_at = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.now() - quarantined_at).days
        except Exception:
            age_days = 0

        simulated = bool(demo_simulate_retention and mode == MODE_SAFE_DEMO and cls._is_approved_demo_entry(quarantine_record))
        effective_age = max(age_days, retention_days) if simulated else age_days

        days_remaining = max(0, retention_days - effective_age)
        is_eligible = effective_age >= retention_days and quarantine_record.get("status") == "QUARANTINED"

        # Check policy authorization
        decision = SafetyPolicy.authorize(
            operation="purge",
            source=quarantine_path,
            mode=mode or quarantine_record.get("mode", MODE_SAFE_DEMO),
            age_days=effective_age,
            retention_days=retention_days,
            user_purge_enabled=True
        )

        return {
            "eligible": is_eligible and (decision.decision.value == "ALLOW"),
            "days_in_quarantine": effective_age,
            "retention_required_days": retention_days,
            "days_remaining": days_remaining,
            "is_simulated_demo": simulated,
            "policy_decision": decision.decision.value,
            "policy_reason": decision.reason,
            "quarantine_id": quarantine_record.get("manifest_id") or quarantine_record.get("quarantine_id")
        }

    # --------------------------------------------------------------------------
    # TASK 3.2: Recovery and Protection Activities
    # --------------------------------------------------------------------------

    @classmethod
    def restore_quarantined_file(cls, quarantine_id: str, mode: str) -> dict:
        """
        Activity 3.2.1: File restoration.
        Safely restores a quarantined file back to its verified original location.
        """
        return cls.restore_file(quarantine_id, mode)

    @classmethod
    def verify_restoration_integrity(cls, original_path: str, expected_sha256: str) -> dict:
        """
        Activity 3.2.2: SHA-256 integrity verification.
        Verifies that restored file exactly matches the cryptographic checksum recorded before quarantine.
        """
        if not os.path.exists(original_path):
            return {
                "verified": False,
                "error": "Restored file does not exist at destination path.",
                "computed_hash": "",
                "expected_hash": expected_sha256
            }

        computed = compute_file_sha256(original_path)
        is_match = (computed.lower() == expected_sha256.lower()) if expected_sha256 else False

        return {
            "verified": is_match,
            "computed_hash": computed,
            "expected_hash": expected_sha256,
            "status": "INTEGRITY_VERIFIED" if is_match else "INTEGRITY_MISMATCH"
        }

    @classmethod
    def reconcile_and_rollback(cls, mode: str = None) -> dict:
        """
        Activity 3.2.3: Interrupted operation recovery and rollback.
        Detects orphaned temporary files or incomplete quarantine operations and cleans or rolls back.
        """
        quarantine_dir = cls.get_quarantine_dir(mode)
        manifest_file = cls.get_manifest_file(mode)
        reconciled = 0
        cleaned_temps = 0

        # 1. Clean temporary manifest files (.manifest-*.tmp)
        if os.path.exists(quarantine_dir):
            try:
                base_dir = os.path.dirname(manifest_file)
                for fname in os.listdir(base_dir):
                    if fname.startswith(".manifest-") and fname.endswith(".tmp"):
                        try:
                            os.unlink(os.path.join(base_dir, fname))
                            cleaned_temps += 1
                        except OSError:
                            pass
            except OSError:
                pass

        # 2. Check manifest records for missing quarantine files
        try:
            records = cls.load_manifest(mode)
            updated = False
            for rec in records:
                if rec.get("status") == "QUARANTINED":
                    q_path = rec.get("quarantine_path", "")
                    if not os.path.exists(q_path):
                        # File missing in quarantine vault
                        orig = rec.get("original_path", "")
                        if os.path.exists(orig):
                            # File is still at original location: roll back record
                            rec["status"] = "ROLLED_BACK"
                            rec["rollback_reason"] = "Restoration reconciliation detected file at source."
                            reconciled += 1
                            updated = True
            if updated:
                cls.save_manifest(records, mode)
        except Exception:
            pass

        return {
            "status": "RECONCILIATION_COMPLETE",
            "reconciled_records": reconciled,
            "cleaned_temp_files": cleaned_temps
        }

    # --------------------------------------------------------------------------
    # Core Quarantine, Restore, and Purge Operations
    # --------------------------------------------------------------------------

    @classmethod
    def quarantine_file(cls, file_record: dict, mode: str, automatic: bool = False) -> dict:
        """
        Safely moves candidate file to isolated Quarantine sandbox.
        Preserves relative folder structure and generates manifest record.
        """
        if mode == MODE_REAL_SYSTEM_READONLY:
            cls._audit("quarantine", mode, "DENY", "READ_ONLY_MODE", "Quarantine is disabled in read-only mode.", file_record.get("full_path"))
            return {
                "success": False,
                "message": "Quarantine is disabled in Real System Read-Only Mode. Switch to Active Mode to quarantine."
            }

        if mode not in (MODE_SAFE_DEMO, MODE_REAL_SYSTEM_ACTIVE):
            cls._audit("quarantine", mode, "DENY", "INVALID_MODE", "Unsupported operating mode.", file_record.get("full_path"))
            return {
                "success": False,
                "message": f"SAFETY BLOCKED: Unsupported operating mode '{mode}'."
            }

        original_path = file_record.get("full_path", "")
        if not original_path or not os.path.isfile(original_path):
            cls._audit("quarantine", mode, "DENY", "SOURCE_UNAVAILABLE", "Source does not exist or is not a regular file.", original_path)
            return {
                "success": False,
                "message": f"Source file does not exist or is not a regular file: {original_path}"
            }

        norm_path = os.path.normcase(os.path.abspath(original_path))
        fname_lower = os.path.basename(original_path).lower()
        ext_lower = os.path.splitext(fname_lower)[1]

        quarantine_target_path = None
        # -------------------------------------------------------------
        # SAFETY CHECK 1: Mode-specific sandbox validation
        # -------------------------------------------------------------
        if mode == MODE_SAFE_DEMO:
            if not is_path_inside_allowed_directory(original_path, DEMO_BASE_DIR):
                return {
                    "success": False,
                    "message": f"SAFETY BLOCKED: Target path '{original_path}' is outside Demo sandbox!"
                }
        else:
            # REAL SYSTEM ACTIVE MODE SAFETY CHECKS:
            for sys_root in SYSTEM_PROTECTED_ROOTS:
                if sys_root and norm_path.startswith(os.path.normcase(os.path.abspath(sys_root))):
                    return {
                        "success": False,
                        "message": f"SAFETY BLOCKED: Path '{original_path}' is inside protected system/personal folder!"
                    }

            for protected_pattern in PROTECTED_FILE_PATTERNS:
                if protected_pattern in fname_lower or protected_pattern in norm_path:
                    return {
                        "success": False,
                        "message": f"SAFETY BLOCKED: Protected essential browser/user pattern ('{protected_pattern}')."
                    }

            if ext_lower in PROTECTED_EXTENSIONS:
                return {
                    "success": False,
                    "message": f"SAFETY BLOCKED: Protected security/credential file extension ('{ext_lower}')."
                }

            in_allowed_cache_dir = any(kw in norm_path for kw in ALLOWED_CACHE_SUBDIRS)
            if not in_allowed_cache_dir:
                return {
                    "success": False,
                    "message": f"SAFETY BLOCKED: Target file is outside verified Cache/Temp subdirectories."
                }

            proc_name = file_record.get("process_name", "")
            if proc_name:
                proc_status = ProcessAnalyzer.get_process_status(proc_name)
                if proc_status["running"] is not False:
                    return {
                        "success": False,
                        "message": f"SAFETY BLOCKED: Application process '{proc_name}' is currently RUNNING or UNKNOWN."
                    }

            if not is_file_exclusively_accessible(original_path):
                return {
                    "success": False,
                    "message": f"SAFETY BLOCKED: File is currently locked or in use by another Windows process."
                }

        # -------------------------------------------------------------
        # Quarantine Execution with SHA-256 Checksum Calculation
        # -------------------------------------------------------------
        try:
            file_sha256 = compute_file_sha256(original_path)
            if not file_sha256:
                return {
                    "success": False,
                    "message": "Quarantine aborted: Could not compute SHA-256 checksum (file locked or unreadable)."
                }

            file_size = os.path.getsize(original_path)
            quarantine_root = cls.get_quarantine_dir(mode)
            unique_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
            quarantined_fname = f"{unique_prefix}_{os.path.basename(original_path)}"

            if mode == MODE_SAFE_DEMO:
                rel_sub = os.path.relpath(original_path, DEMO_BASE_DIR)
                quarantine_target_path = os.path.join(quarantine_root, os.path.dirname(rel_sub), quarantined_fname)
            else:
                rel_sub = os.path.relpath(original_path, REAL_BASE_DIR) if original_path.startswith(REAL_BASE_DIR) else os.path.basename(original_path)
                quarantine_target_path = os.path.join(quarantine_root, quarantined_fname)

            decision = SafetyPolicy.authorize(
                "quarantine", original_path, quarantine_target_path, mode,
                metadata=file_record, app_name=file_record.get("app_name"),
                process_running=file_record.get("process_running"),
                age_days=file_record.get("age_days"), automatic=automatic,
            )
            if decision.decision.value != "ALLOW":
                cls._audit("quarantine", mode, decision.decision.value, decision.code, decision.reason, original_path, quarantine_target_path)
                return {"success": False, "message": f"SAFETY BLOCKED [{decision.code}]: {decision.reason}"}

            current_stat = os.stat(original_path)
            if current_stat.st_size != file_record.get("size_bytes") or current_stat.st_mtime != file_record.get("mtime"):
                cls._audit("quarantine", mode, "DENY", "FILE_CHANGED_SINCE_SCAN", "File modified after scanning completed.", original_path)
                return {"success": False, "message": "SAFETY BLOCKED: File modified after scanning completed."}

            expected_identity = file_record.get("file_identity")
            if mode == MODE_REAL_SYSTEM_ACTIVE and (
                not expected_identity
                or expected_identity.get("device") != current_stat.st_dev
                or expected_identity.get("inode") != current_stat.st_ino
            ):
                cls._audit("quarantine", mode, "DENY", "FILE_IDENTITY_CHANGED", "File identity changed after scanning.", original_path)
                return {"success": False, "message": "SAFETY BLOCKED: File identity changed after scanning."}

            os.makedirs(os.path.dirname(quarantine_target_path), exist_ok=True)
            shutil.move(original_path, quarantine_target_path)

            # Move verification
            src_exists = os.path.exists(original_path)
            dest_exists = os.path.exists(quarantine_target_path)

            if not src_exists and dest_exists and compute_file_sha256(quarantine_target_path) == file_sha256:
                manifest = cls.load_manifest(mode)
                prefix = "Q_DEMO" if mode == MODE_SAFE_DEMO else "Q_REAL"
                manifest_id = f"{prefix}_{int(datetime.now().timestamp())}_{len(manifest)+1}"
                entry = {
                    "manifest_id": manifest_id,
                    "mode": mode,
                    "original_path": original_path,
                    "quarantine_path": quarantine_target_path,
                    "app_name": file_record.get("app_name", ""),
                    "file_name": file_record.get("file_name", ""),
                    "file_size": file_size,
                    "size_formatted": format_file_size(file_size),
                    "sha256": file_sha256,
                    "mtime_formatted": file_record.get("mtime_formatted", ""),
                    "score": file_record.get("score", 0),
                    "classification": file_record.get("classification", ""),
                    "reasons": file_record.get("reasons", []),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "QUARANTINED",
                    "status": "QUARANTINED"
                }
                manifest.append(entry)
                cls.save_manifest(manifest, mode)

                # Sync with SQLite database
                try:
                    get_audit_store().record_quarantine(
                        quarantine_id=manifest_id,
                        mode=mode,
                        original_path=original_path,
                        quarantine_path=quarantine_target_path,
                        file_size=file_size,
                        sha256_hash=file_sha256,
                        retention_days=QUARANTINE_RETENTION_DAYS
                    )
                except Exception:
                    pass

                audit_ok = cls._audit("quarantine", mode, "ALLOW", "QUARANTINED", "File quarantined and integrity verified.", original_path, quarantine_target_path)

                return {
                    "success": True,
                    "message": (f"QUARANTINE SUCCESSFUL: File isolated in sandbox ({format_file_size(file_size)})."
                                if audit_ok else f"File quarantined at {quarantine_target_path}; database audit write failed."),
                    "entry": entry
                }
            else:
                if dest_exists and not src_exists:
                    try:
                        os.makedirs(os.path.dirname(original_path), exist_ok=True)
                        shutil.move(quarantine_target_path, original_path)
                    except OSError:
                        pass
                cls._audit("quarantine", mode, "DENY", "MOVE_VERIFY_FAILED", "Move verification failed; rollback was attempted.", original_path, quarantine_target_path)
                return {
                    "success": False,
                    "message": "Move verification failed; recovery to the original path was attempted."
                }
        except Exception as e:
            if quarantine_target_path and os.path.exists(quarantine_target_path) and not os.path.exists(original_path):
                try:
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)
                    shutil.move(quarantine_target_path, original_path)
                except OSError:
                    return {
                        "success": False,
                        "message": f"Quarantine failed and automatic rollback failed. File remains at: {quarantine_target_path}. Error: {e}",
                    }
            cls._audit("quarantine", mode, "DENY", "OPERATION_ERROR", str(e), original_path, quarantine_target_path)
            return {
                "success": False,
                "message": f"Quarantine error: {str(e)}"
            }

    @classmethod
    def restore_file(cls, manifest_id: str, mode: str) -> dict:
        """
        Restores a quarantined file back to its exact original location.
        Verifies directory reconstruction and status update.
        """
        if mode == MODE_REAL_SYSTEM_READONLY:
            cls._audit("restore", mode, "DENY", "READ_ONLY_MODE", "Restore is disabled in read-only mode.")
            return {
                "success": False,
                "message": "Restore is disabled in Real System Read-Only Mode. Switch to Active Mode to restore."
            }

        try:
            manifest = cls.load_manifest(mode)
        except RuntimeError as exc:
            return {"success": False, "message": str(exc)}
        entry = next((e for e in manifest if e.get("manifest_id") == manifest_id and e.get("status") == "QUARANTINED"), None)

        if not entry:
            cls._audit("restore", mode, "DENY", "ENTRY_NOT_FOUND", "Quarantine entry is missing or already restored.")
            return {
                "success": False,
                "message": "Quarantine entry not found or file already restored."
            }

        quarantine_path = entry.get("quarantine_path", "")
        original_path = entry.get("original_path", "")
        expected_sha256 = entry.get("sha256", "")

        if not os.path.exists(quarantine_path):
            cls._audit("restore", mode, "DENY", "QUARANTINE_FILE_MISSING", "Quarantine file does not exist on disk.", quarantine_path)
            return {
                "success": False,
                "message": f"Quarantine file missing on disk: {quarantine_path}"
            }

        current_hash = compute_file_sha256(quarantine_path)
        if current_hash != expected_sha256:
            cls._audit("restore", mode, "DENY", "INTEGRITY_MISMATCH", "SHA-256 checksum does not match manifest.", quarantine_path)
            return {
                "success": False,
                "message": "INTEGRITY COMPROMISED: SHA-256 hash does not match quarantine record!"
            }

        decision = SafetyPolicy.authorize("restore", quarantine_path, original_path, mode, app_name=entry.get("app_name"))
        if decision.decision.value != "ALLOW":
            cls._audit("restore", mode, decision.decision.value, decision.code, decision.reason, quarantine_path, original_path)
            return {"success": False, "message": f"SAFETY BLOCKED [{decision.code}]: {decision.reason}"}

        if os.path.exists(original_path):
            cls._audit("restore", mode, "DENY", "DESTINATION_CONFLICT", "Destination already exists; will not overwrite.", original_path)
            return {
                "success": False,
                "message": f"SAFETY BLOCKED: A file already exists at original location: {original_path}"
            }

        try:
            os.makedirs(os.path.dirname(original_path), exist_ok=True)
            shutil.move(quarantine_path, original_path)

            if os.path.exists(original_path) and not os.path.exists(quarantine_path):
                entry["status"] = "RESTORED"
                entry["restored_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cls.save_manifest(manifest, mode)

                try:
                    get_audit_store().update_quarantine_status(manifest_id, "RESTORED")
                except Exception:
                    pass

                audit_ok = cls._audit("restore", mode, "ALLOW", "RESTORED", "File restored to original path and verified.", quarantine_path, original_path)
                return {
                    "success": True,
                    "message": ("RESTORE SUCCESSFUL: File restored and verified."
                                if audit_ok else f"File restored to {original_path}, but audit write failed."),
                    "entry": entry
                }
            else:
                return {
                    "success": False,
                    "message": "Restore failed: File move operation incomplete."
                }
        except Exception as e:
            cls._audit("restore", mode, "DENY", "OPERATION_ERROR", str(e), quarantine_path, original_path)
            return {
                "success": False,
                "message": f"Restore error: {str(e)}"
            }

    @classmethod
    def purge_file(cls, manifest_id: str, mode: str, user_purge_enabled: bool = False,
                   demo_simulate_retention: bool = False) -> dict:
        """
        Permanently deletes a quarantined file from sandbox after retention verification.
        Requires explicit policy authorization.
        """
        if mode == MODE_REAL_SYSTEM_READONLY:
            cls._audit("purge", mode, "DENY", "READ_ONLY_MODE", "Purge is disabled in read-only mode.")
            return {
                "success": False,
                "message": "Purge is disabled in Real System Read-Only Mode."
            }

        try:
            manifest = cls.load_manifest(mode)
        except RuntimeError as exc:
            return {"success": False, "message": str(exc)}
        entry = next((e for e in manifest if e.get("manifest_id") == manifest_id and e.get("status") == "QUARANTINED"), None)

        if not entry:
            cls._audit("purge", mode, "DENY", "ENTRY_NOT_FOUND", "Quarantine entry is missing or already processed.")
            return {
                "success": False,
                "message": "Quarantine entry not found or file already processed."
            }

        quarantine_path = entry.get("quarantine_path", "")

        try:
            quarantined_at = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.now() - quarantined_at).days
        except (KeyError, ValueError, TypeError):
            age_days = None
        simulated_retention = bool(
            demo_simulate_retention
            and mode == MODE_SAFE_DEMO
            and cls._is_approved_demo_entry(entry)
        )
        if simulated_retention:
            age_days = max(age_days or 0, QUARANTINE_RETENTION_DAYS)
        decision = SafetyPolicy.authorize(
            "purge", quarantine_path, mode=mode,
            age_days=age_days, retention_days=QUARANTINE_RETENTION_DAYS,
            user_purge_enabled=user_purge_enabled,
        )
        if decision.decision.value != "ALLOW":
            cls._audit("purge", mode, decision.decision.value, decision.code, decision.reason, quarantine_path)
            return {"success": False, "message": f"SAFETY BLOCKED [{decision.code}]: {decision.reason}"}

        if not os.path.exists(quarantine_path):
            entry["status"] = "PURGED"
            entry["purged_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cls.save_manifest(manifest, mode)
            try:
                get_audit_store().update_quarantine_status(manifest_id, "PURGED")
            except Exception:
                pass
            audit_detail = "Demo presentation simulated 30-day retention; missing quarantine file reconciled." if simulated_retention else "Quarantine file was already missing; manifest reconciled."
            cls._audit("purge", mode, "ALLOW", "ALREADY_MISSING", audit_detail, quarantine_path)
            return {
                "success": True,
                "message": "File was already missing. Manifest updated.",
                "entry": entry,
                "bytes_recovered": 0
            }

        try:
            file_size = os.path.getsize(quarantine_path)
            os.remove(quarantine_path)

            if not os.path.exists(quarantine_path):
                entry["status"] = "PURGED"
                entry["purged_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cls.save_manifest(manifest, mode)
                try:
                    get_audit_store().update_quarantine_status(manifest_id, "PURGED")
                except Exception:
                    pass
                audit_code = "DEMO_SIMULATED_RETENTION_PURGED" if simulated_retention else "PURGED"
                audit_detail = "Demo presentation simulated 30-day retention; synthetic quarantined file permanently purged." if simulated_retention else "Expired quarantine file purged."
                audit_ok = cls._audit("purge", mode, "ALLOW", audit_code, audit_detail, quarantine_path)
                return {
                    "success": True,
                    "message": (f"PURGE SUCCESSFUL: Permanently removed quarantined cache file. Recovered {format_file_size(file_size)}."
                                if audit_ok else f"File purged ({format_file_size(file_size)}), but database audit write failed."),
                    "entry": entry,
                    "bytes_recovered": file_size
                }
            else:
                return {
                    "success": False,
                    "message": "Purge failed: file still exists on disk."
                }
        except Exception as e:
            cls._audit("purge", mode, "DENY", "OPERATION_ERROR", str(e), quarantine_path)
            return {
                "success": False,
                "message": f"Purge error: {str(e)}"
            }

    @classmethod
    def _audit(cls, operation, mode, decision, code, detail, source=None, destination=None):
        try:
            (cls.audit_store or get_audit_store()).record_event(
                operation, mode, decision, code, detail, source, destination
            )
        except Exception:
            return False
        return True

    @staticmethod
    def _is_approved_demo_entry(entry):
        """Allow accelerated retention only for known synthetic demo samples."""
        if entry.get("mode") != MODE_SAFE_DEMO:
            return False
        try:
            original = Path(entry["original_path"]).resolve()
            original.relative_to(Path(DEMO_BASE_DIR).resolve())
            relative = str(original.relative_to(Path(DEMO_BASE_DIR).resolve())).replace("\\", "/")
            quarantine = Path(entry["quarantine_path"]).resolve()
            quarantine.relative_to(Path(DEMO_QUARANTINE_DIR).resolve())
            from config import DEMO_SAMPLE_RELATIVE_PATHS
            return relative in DEMO_SAMPLE_RELATIVE_PATHS
        except (KeyError, OSError, ValueError, RuntimeError):
            return False

    @classmethod
    def purge_expired(cls, mode: str, limit: int = 100, demo_simulate_retention: bool = False) -> list:
        """Automatically purge only expired quarantine entries when the explicit mode policy is enabled."""
        enabled = SafetyPolicy.demo_purge_enabled if mode == MODE_SAFE_DEMO else SafetyPolicy.real_purge_enabled
        if not enabled or SafetyPolicy.paused or mode == MODE_REAL_SYSTEM_READONLY:
            return []
        try:
            records = cls.load_manifest(mode)
        except RuntimeError:
            return []
        results = []
        for entry in records:
            if len(results) >= max(1, min(int(limit), 1000)):
                break
            if entry.get("status") != "QUARANTINED":
                continue
            try:
                age = (datetime.now() - datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")).days
            except (KeyError, ValueError, TypeError):
                continue
            simulate = bool(demo_simulate_retention and mode == MODE_SAFE_DEMO and cls._is_approved_demo_entry(entry))
            if age < QUARANTINE_RETENTION_DAYS and not simulate:
                continue
            results.append(cls.purge_file(
                entry.get("manifest_id"), mode, user_purge_enabled=True,
                demo_simulate_retention=simulate,
            ))
        return results
