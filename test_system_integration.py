"""
Comprehensive Integration Tests for Zombie Data Purger
Validates end-to-end workflow, duplicate detection, quarantine lifecycle,
integrity verification, and database persistence.
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from config import MODE_SAFE_DEMO, MODE_REAL_SYSTEM_ACTIVE, QUARANTINE_RETENTION_DAYS
from scanner import FileScanner
from classifier import ZombieDataClassifier
from safety_policy import SafetyPolicy, Decision
from quarantine import QuarantineManager
from database import AuditStore
from app_discovery import ApplicationDiscovery
from utils import compute_file_sha256


class SystemIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_audit.sqlite3")
        self.store = AuditStore(self.db_path)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except OSError:
            pass

    def test_duplicate_file_detection_sha256(self):
        # Create identical files with same size and hash
        f1 = os.path.join(self.test_dir, "dup1.tmp")
        f2 = os.path.join(self.test_dir, "dup2.tmp")
        f3 = os.path.join(self.test_dir, "unique.tmp")

        content = b"IDENTICAL_CACHE_BLOB_FOR_DUPLICATE_TEST" * 50
        with open(f1, "wb") as f:
            f.write(content)
        with open(f2, "wb") as f:
            f.write(content)
        with open(f3, "wb") as f:
            f.write(b"UNIQUE_CONTENT_STRING_XYZ")

        files_list = [
            FileScanner.extract_file_metadata(f1),
            FileScanner.extract_file_metadata(f2),
            FileScanner.extract_file_metadata(f3)
        ]

        report = FileScanner.identify_duplicates_sha256(files_list)
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["duplicate_savings_bytes"], len(content))
        self.assertTrue(files_list[1].get("is_duplicate"))
        self.assertFalse(files_list[2].get("is_duplicate"))

    def test_quarantine_restore_lifecycle_with_sha256(self):
        demo_base = os.path.join(self.test_dir, "DemoBase")
        demo_quarantine = os.path.join(demo_base, "Quarantine")
        demo_manifest = os.path.join(demo_base, "quarantine_manifest.json")
        sample_path = os.path.join(demo_base, "Chrome_Demo", "Cache", "old_cache_01.tmp")

        os.makedirs(os.path.dirname(sample_path), exist_ok=True)
        sample_content = b"STALE_CACHE_DATA_FOR_INTEGRITY_TEST"
        with open(sample_path, "wb") as f:
            f.write(sample_content)

        expected_hash = compute_file_sha256(sample_path)
        stat_res = os.stat(sample_path)

        file_record = {
            "full_path": sample_path,
            "file_name": "old_cache_01.tmp",
            "size_bytes": len(sample_content),
            "mtime": stat_res.st_mtime,
            "file_identity": {"device": stat_res.st_dev, "inode": stat_res.st_ino},
            "age_days": 45,
            "accessible": True,
            "app_name": "Chrome Demo Application",
            "score": 100,
            "classification": "POTENTIAL ZOMBIE DATA"
        }

        with patch("quarantine.DEMO_BASE_DIR", demo_base), \
             patch("quarantine.DEMO_QUARANTINE_DIR", demo_quarantine), \
             patch("quarantine.DEMO_MANIFEST_FILE", demo_manifest), \
             patch("safety_policy.DEMO_BASE_DIR", demo_base), \
             patch("safety_policy.DEMO_QUARANTINE_DIR", demo_quarantine), \
             patch("quarantine.get_audit_store", return_value=self.store):

            # 1. Quarantine candidate
            q_res = QuarantineManager.quarantine_candidate(file_record, MODE_SAFE_DEMO)
            self.assertTrue(q_res["success"], q_res.get("message"))
            self.assertFalse(os.path.exists(sample_path), "Original file should have been moved")
            entry = q_res["entry"]
            self.assertEqual(entry["sha256"], expected_hash)

            # 2. Verify vault record
            quarantine_path = entry["quarantine_path"]
            self.assertTrue(os.path.exists(quarantine_path))

            # 3. Test purge eligibility (retention not elapsed)
            elig_res = QuarantineManager.validate_purge_eligibility(entry, retention_days=30, mode=MODE_SAFE_DEMO, demo_simulate_retention=False)
            self.assertFalse(elig_res["eligible"])

            # 4. Restore file
            r_res = QuarantineManager.restore_quarantined_file(entry["manifest_id"], MODE_SAFE_DEMO)
            self.assertTrue(r_res["success"], r_res.get("message"))
            self.assertTrue(os.path.exists(sample_path), "File should be restored to original path")
            self.assertFalse(os.path.exists(quarantine_path), "File should no longer be in quarantine")

            # 5. Verify integrity after restoration
            int_res = QuarantineManager.verify_restoration_integrity(sample_path, expected_hash)
            self.assertTrue(int_res["verified"])
            self.assertEqual(int_res["status"], "INTEGRITY_VERIFIED")

    def test_database_dashboard_aggregation(self):
        # Record a test scan session
        scan_data = {
            "app_name": "Google Chrome",
            "target_path": "C:\\AppData\\Chrome",
            "scanned_count": 150,
            "zombie_count": 45,
            "uncertain_count": 15,
            "keep_count": 90,
            "potential_reclaimable_bytes": 1024 * 1024 * 12, # 12 MB
            "files": [
                {
                    "full_path": "C:\\AppData\\Chrome\\test.tmp",
                    "size_bytes": 1024 * 50,
                    "score": 90,
                    "classification": "POTENTIAL ZOMBIE DATA",
                    "risk_level": "CRITICAL",
                    "reasons": ["Old file"]
                }
            ]
        }
        self.store.record_scan(MODE_SAFE_DEMO, scan_data)

        # Check metrics
        metrics = self.store.get_dashboard_metrics()
        self.assertEqual(metrics["total_scanned_files"], 150)
        self.assertEqual(metrics["total_zombies"], 45)
        self.assertEqual(metrics["potential_reclaimable_bytes"], 1024 * 1024 * 12)

        # Check risk distribution
        dist = self.store.get_risk_distribution()
        self.assertEqual(dist["ZOMBIE"], 1)


if __name__ == "__main__":
    unittest.main()
