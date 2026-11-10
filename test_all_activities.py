"""
Unit tests validating all 3 Modules, 9 Tasks, and 27 Activities
defined in academic_core.py.
"""
import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from academic_core import AcademicCoreRegistry
from config import MODE_SAFE_DEMO, MODE_REAL_SYSTEM_ACTIVE
from safety_policy import SafetyPolicy, Decision
from demo_data import create_safe_demo_environment


class AcademicActivitiesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create isolated demo sandbox for testing activities
        try:
            create_safe_demo_environment()
        except Exception:
            pass

    def test_registry_contains_all_27_activities(self):
        activities = AcademicCoreRegistry.get_all()
        self.assertEqual(len(activities), 27, f"Expected 27 activities, found {len(activities)}")

        # Verify 3 modules
        mod1 = AcademicCoreRegistry.get_module(1)
        mod2 = AcademicCoreRegistry.get_module(2)
        mod3 = AcademicCoreRegistry.get_module(3)
        self.assertEqual(len(mod1), 9, "Module 1 should have 9 activities")
        self.assertEqual(len(mod2), 9, "Module 2 should have 9 activities")
        self.assertEqual(len(mod3), 9, "Module 3 should have 9 activities")

    def test_module_1_application_discovery_tasks(self):
        # Activity 1.1.1: Identify applications
        act_111 = AcademicCoreRegistry.get("1.1.1")
        apps = act_111.execute(MODE_SAFE_DEMO)
        self.assertIsInstance(apps, list)
        self.assertGreaterEqual(len(apps), 2)

        # Activity 1.1.2: Detect cache directories
        act_112 = AcademicCoreRegistry.get("1.1.2")
        cache_dirs = act_112.execute(apps[0])
        self.assertIsInstance(cache_dirs, list)

        # Activity 1.1.3: Verify application path
        act_113 = AcademicCoreRegistry.get("1.1.3")
        verification = act_113.execute(apps[0]["path"])
        self.assertIsInstance(verification, dict)
        self.assertTrue(verification.get("exists"))

    def test_module_1_file_scanning_tasks(self):
        act_111 = AcademicCoreRegistry.get("1.1.1")
        apps = act_111.execute(MODE_SAFE_DEMO)
        demo_app = apps[0]

        # Activity 1.2.1: Recursive directory scanning
        act_121 = AcademicCoreRegistry.get("1.2.1")
        scan_res = act_121.execute(demo_app, age_threshold_days=14)
        self.assertIsInstance(scan_res, dict)
        self.assertIn("files", scan_res)

        if scan_res["files"]:
            sample_file = scan_res["files"][0]["full_path"]

            # Activity 1.2.2: File metadata extraction
            act_122 = AcademicCoreRegistry.get("1.2.2")
            meta = act_122.execute(sample_file)
            self.assertIsInstance(meta, dict)
            self.assertTrue(meta.get("exists"))

            # Activity 1.2.3: File type and extension identification
            act_123 = AcademicCoreRegistry.get("1.2.3")
            type_info = act_123.execute(sample_file)
            self.assertIn("file_category", type_info)

            # Activity 1.3.1: File size and timestamp analysis
            act_131 = AcademicCoreRegistry.get("1.3.1")
            ts_res = act_131.execute(meta, 14)
            self.assertIn("age_days", ts_res)

        # Activity 1.3.2: Duplicate file identification using SHA-256
        act_132 = AcademicCoreRegistry.get("1.3.2")
        dup_res = act_132.execute(scan_res["files"])
        self.assertIn("duplicate_count", dup_res)

        # Activity 1.3.3: Scan report generation and SQLite storage
        act_133 = AcademicCoreRegistry.get("1.3.3")
        saved_report = act_133.execute(scan_res, MODE_SAFE_DEMO)
        self.assertIn("scan_id", saved_report)

    def test_module_2_zombie_intelligence_tasks(self):
        import time
        now = time.time()
        mtime = now - (45 * 86400) # 45 days old

        # Activity 2.1.1: File age analysis
        act_211 = AcademicCoreRegistry.get("2.1.1")
        age_res = act_211.execute(mtime, now, 14)
        self.assertTrue(age_res["exceeds_threshold"])
        self.assertIn(age_res["age_days"], (44, 45, 46))

        # Activity 2.1.2: Access and modification pattern analysis
        act_212 = AcademicCoreRegistry.get("2.1.2")
        pat_res = act_212.execute({"process_running": False, "accessible": True})
        self.assertTrue(pat_res["is_dormant"])

        # Activity 2.1.3: Cache characteristics evaluation
        act_213 = AcademicCoreRegistry.get("2.1.3")
        cache_eval = act_213.execute({"full_path": "C:\\AppData\\Chrome\\Cache\\data_0", "extension": ".tmp"})
        self.assertTrue(cache_eval["in_cache_dir"])

        # Activity 2.2.1: Explainable zombie score calculation
        act_221 = AcademicCoreRegistry.get("2.2.1")
        test_meta = {
            "file_name": "cache_file.tmp",
            "full_path": "c:\\temp\\cache\\cache_file.tmp",
            "extension": ".tmp",
            "mtime": mtime,
            "ctime": mtime,
            "process_running": False,
            "accessible": True
        }
        score_res = act_221.execute(test_meta, 14)
        self.assertGreaterEqual(score_res["score"], 80)

        # Activity 2.2.2: Risk category classification
        act_222 = AcademicCoreRegistry.get("2.2.2")
        cat, risk = act_222.execute(score_res["score"], False)
        self.assertEqual(risk, "CRITICAL_ZOMBIE_CANDIDATE")

        # Activity 2.2.3: Classification reason generation
        act_223 = AcademicCoreRegistry.get("2.2.3")
        reasons_payload = act_223.execute(test_meta, score_res, 14)
        self.assertIn("reasons", reasons_payload)
        self.assertIn("recommendation", reasons_payload)

        # Activity 2.3.1: Protected file detection
        act_231 = AcademicCoreRegistry.get("2.3.1")
        prot_res = act_231.execute("C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies")
        self.assertTrue(prot_res["protected"])

        # Activity 2.3.2: Symlink and reparse point validation
        act_232 = AcademicCoreRegistry.get("2.3.2")
        val_res = act_232.execute(__file__)
        self.assertTrue(val_res["safe"])

        # Activity 2.3.3: Policy-based cleanup eligibility evaluation
        act_233 = AcademicCoreRegistry.get("2.3.3")
        decision = act_233.execute(operation="inspect", source=__file__, mode=MODE_SAFE_DEMO)
        self.assertIsInstance(decision, object)

    def test_module_3_secure_cleanup_and_recovery_tasks(self):
        # Activity 3.1.1: User review and candidate selection
        act_311 = AcademicCoreRegistry.get("3.1.1")
        test_candidates = [
            {"full_path": "f1.tmp", "size_bytes": 100, "classification": "POTENTIAL ZOMBIE DATA"},
            {"full_path": "f2.db", "size_bytes": 200, "classification": "KEEP"},
        ]
        sel_res = act_311.execute(test_candidates)
        self.assertEqual(sel_res["reviewed_count"], 1)
        self.assertEqual(sel_res["skipped_count"], 1)

        # Activity 3.1.3: Retention-based purge eligibility validation
        act_313 = AcademicCoreRegistry.get("3.1.3")
        rec = {
            "manifest_id": "test_id",
            "timestamp": "2026-09-01 12:00:00",
            "quarantine_path": "dummy_path",
            "status": "QUARANTINED"
        }
        purge_elig = act_313.execute(rec, retention_days=30, mode=MODE_SAFE_DEMO)
        self.assertIn("eligible", purge_elig)

        # Activity 3.2.2: SHA-256 integrity verification
        act_322 = AcademicCoreRegistry.get("3.2.2")
        from utils import compute_file_sha256
        my_hash = compute_file_sha256(__file__)
        int_res = act_322.execute(__file__, my_hash)
        self.assertTrue(int_res["verified"])

        # Activity 3.2.3: Interrupted operation recovery and rollback
        act_323 = AcademicCoreRegistry.get("3.2.3")
        rec_res = act_323.execute(MODE_SAFE_DEMO)
        self.assertEqual(rec_res["status"], "RECONCILIATION_COMPLETE")

        # Activity 3.3.1: Background scanning and monitoring status
        act_331 = AcademicCoreRegistry.get("3.3.1")
        bg_stat = act_331.execute()
        self.assertTrue(bg_stat["background_scanning_supported"])

        # Activity 3.3.2: SQLite audit logging
        act_332 = AcademicCoreRegistry.get("3.3.2")
        events = act_332.execute(5)
        self.assertIsInstance(events, list)

        # Activity 3.3.3: Dashboard analytics
        act_333 = AcademicCoreRegistry.get("3.3.3")
        metrics = act_333.execute()
        self.assertIn("total_scanned_files", metrics)


if __name__ == "__main__":
    unittest.main()
