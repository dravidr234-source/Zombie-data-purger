"""Non-destructive unit checks for the centralized safety policy."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from config import MODE_REAL_SYSTEM_ACTIVE, MODE_SAFE_DEMO
from safety_policy import Decision, SafetyPolicy
from classifier import ZombieDataClassifier
from database import AuditStore
import quarantine as quarantine_module
from quarantine import QuarantineManager


class SafetyPolicyTests(unittest.TestCase):
    def test_reviewed_real_cache_layout_can_pass_policy_checks(self):
        import safety_policy as policy_module
        with tempfile.TemporaryDirectory() as temp:
            app_root = Path(temp) / "ChromeData"
            source = app_root / "Default" / "Cache" / "sample.tmp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"synthetic")
            st = source.stat()
            definitions = dict(policy_module.APP_DEFINITIONS)
            definitions["Google Chrome"] = {"relative_path": str(app_root)}
            with patch.object(policy_module, "APP_DEFINITIONS", definitions), \
                 patch.object(policy_module, "REAL_QUARANTINE_DIR", str(Path(temp) / "Quarantine")):
                decision = SafetyPolicy.authorize(
                    "quarantine", source, Path(temp) / "Quarantine" / "sample.tmp",
                    MODE_REAL_SYSTEM_ACTIVE, app_name="Google Chrome", process_running=False,
                    metadata={"accessible": True, "size_bytes": st.st_size, "mtime": st.st_mtime,
                              "file_identity": {"device": st.st_dev, "inode": st.st_ino}},
                    age_days=30,
                )
            self.assertEqual(decision.decision, Decision.ALLOW, decision.reason)

    def test_unknown_real_path_is_denied_even_with_zombie_score(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "old_cache.tmp"
            source.write_bytes(b"synthetic")
            decision = SafetyPolicy.authorize(
                "quarantine", source, mode=MODE_REAL_SYSTEM_ACTIVE,
                app_name="Unknown Application", process_running=False,
                metadata={"accessible": True, "score": 100}, age_days=900,
            )
            self.assertEqual(decision.decision, Decision.DENY)
            self.assertEqual(decision.code, "UNAPPROVED_ROOT")

    def test_pause_blocks_operation(self):
        SafetyPolicy.paused = True
        try:
            decision = SafetyPolicy.authorize("quarantine", "missing", mode=MODE_SAFE_DEMO)
            self.assertEqual(decision.code, "GLOBAL_PAUSE")
        finally:
            SafetyPolicy.paused = False

    def test_missing_operation_facts_fail_closed(self):
        decision = SafetyPolicy.authorize("quarantine", "", mode=MODE_REAL_SYSTEM_ACTIVE)
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.code, "MISSING_SOURCE")

    def test_unknown_operation_is_denied(self):
        decision = SafetyPolicy.authorize("delete-parent", "somewhere", mode=MODE_SAFE_DEMO)
        self.assertEqual(decision.decision, Decision.DENY)
        self.assertEqual(decision.code, "UNKNOWN_OPERATION")

    def test_unknown_process_state_does_not_add_inactive_points(self):
        candidate = {
            "file_name": "old.tmp", "full_path": "C:/profile/Cache/old.tmp",
            "extension": ".tmp", "age_days": 100, "process_running": None,
            "accessible": True,
        }
        first = ZombieDataClassifier.classify_file(candidate)
        second = ZombieDataClassifier.classify_file(candidate)
        self.assertEqual(first, second)
        self.assertNotIn("+30 Associated application process is inactive (not running)", first["reasons"])

    def test_sqlite_audit_persists_across_store_instances(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audit.sqlite3"
            AuditStore(path).record_event("quarantine", MODE_SAFE_DEMO, "DENY", "TEST", "synthetic")
            self.assertEqual(len(AuditStore(path).list_events()), 1)

    def test_quarantine_restore_and_collision_are_confined_to_temp_sandbox(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "sandbox"
            source = base / "Chrome_Demo" / "Cache" / "sample.tmp"
            quarantine = base / "Quarantine"
            manifest_path = base / "manifest.json"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"synthetic cache bytes")
            store = AuditStore(Path(temp) / "audit.sqlite3")
            QuarantineManager.audit_store = store
            try:
                with patch.multiple(quarantine_module,
                                    DEMO_BASE_DIR=str(base), DEMO_QUARANTINE_DIR=str(quarantine),
                                    DEMO_MANIFEST_FILE=str(manifest_path)), \
                     patch.multiple(__import__("safety_policy"),
                                    DEMO_BASE_DIR=str(base), DEMO_QUARANTINE_DIR=str(quarantine)):
                    stat = source.stat()
                    record = {"full_path": str(source), "file_name": source.name,
                              "app_name": "Chrome Demo Application", "size_bytes": stat.st_size,
                              "mtime": stat.st_mtime, "accessible": True,
                              "file_identity": {"device": stat.st_dev, "inode": stat.st_ino},
                              "process_running": False, "age_days": 100}
                    moved = QuarantineManager.quarantine_file(record, MODE_SAFE_DEMO)
                    self.assertTrue(moved["success"], moved["message"])
                    entry = moved["entry"]
                    self.assertFalse(source.exists())
                    self.assertEqual(entry["sha256"], quarantine_module.compute_file_sha256(entry["quarantine_path"]))

                    source.write_bytes(b"do not overwrite")
                    collision = QuarantineManager.restore_file(entry["manifest_id"], MODE_SAFE_DEMO)
                    self.assertFalse(collision["success"])
                    source.unlink()
                    restored = QuarantineManager.restore_file(entry["manifest_id"], MODE_SAFE_DEMO)
                    self.assertTrue(restored["success"], restored["message"])
                    self.assertEqual(source.read_bytes(), b"synthetic cache bytes")
                    self.assertGreaterEqual(len(store.list_events()), 3)
            finally:
                QuarantineManager.audit_store = None

    def test_purge_requires_explicit_policy_and_elapsed_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "sandbox"
            source = base / "Chrome_Demo" / "Cache" / "sample.tmp"
            quarantine = base / "Quarantine"
            manifest_path = base / "manifest.json"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"synthetic cache")
            old = (datetime.now() - timedelta(days=45)).timestamp()
            import os
            os.utime(source, (old, old))
            stat = source.stat()
            store = AuditStore(Path(temp) / "audit.sqlite3")
            QuarantineManager.audit_store = store
            original_policy = SafetyPolicy.demo_purge_enabled
            try:
                with patch.multiple(quarantine_module,
                                    DEMO_BASE_DIR=str(base), DEMO_QUARANTINE_DIR=str(quarantine),
                                    DEMO_MANIFEST_FILE=str(manifest_path)), \
                     patch.multiple(__import__("safety_policy"),
                                    DEMO_BASE_DIR=str(base), DEMO_QUARANTINE_DIR=str(quarantine)):
                    result = QuarantineManager.quarantine_file({
                        "full_path": str(source), "file_name": source.name,
                        "app_name": "Chrome Demo Application", "size_bytes": stat.st_size,
                        "mtime": stat.st_mtime, "accessible": True, "age_days": 45,
                        "file_identity": {"device": stat.st_dev, "inode": stat.st_ino},
                        "process_running": False,
                    }, MODE_SAFE_DEMO)
                    self.assertTrue(result["success"], result["message"])
                    entry = result["entry"]
                    entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    QuarantineManager.save_manifest([entry], MODE_SAFE_DEMO)
                    SafetyPolicy.demo_purge_enabled = True
                    recent = QuarantineManager.purge_file(entry["manifest_id"], MODE_SAFE_DEMO, user_purge_enabled=True)
                    self.assertFalse(recent["success"])
                    self.assertTrue(Path(entry["quarantine_path"]).exists())

                    entry["timestamp"] = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
                    QuarantineManager.save_manifest([entry], MODE_SAFE_DEMO)
                    expired = QuarantineManager.purge_file(entry["manifest_id"], MODE_SAFE_DEMO, user_purge_enabled=True)
                    self.assertTrue(expired["success"], expired["message"])
                    self.assertFalse(Path(entry["quarantine_path"]).exists())
            finally:
                SafetyPolicy.demo_purge_enabled = original_policy
                QuarantineManager.audit_store = None


if __name__ == "__main__":
    unittest.main()
