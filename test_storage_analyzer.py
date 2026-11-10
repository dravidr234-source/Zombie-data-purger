"""
Unit and integration tests for Browser Storage Analysis engine
Validates folder-level storage calculation, multi-browser percentage distribution,
top-5 largest files extraction, remaining files aggregate, empty/zero-byte handling,
duplicate prevention, and classification inspection.
"""

import unittest
import tempfile
import os
import time
from pathlib import Path

from config import MODE_SAFE_DEMO, MODE_REAL_SYSTEM_READONLY
from storage_analyzer import BrowserStorageAnalyzer
from classifier import ZombieDataClassifier


class BrowserStorageAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = self.test_dir.name

    def tearDown(self):
        self.test_dir.cleanup()

    def test_folder_size_and_percentage_calculation_multi_browser(self):
        """Validates Module A: Multi-browser folder sizes and percentage distribution."""
        # Simulated Chrome: 300 KB
        # Simulated Edge: 100 KB
        # Total combined: 400 KB -> Chrome: 75%, Edge: 25%
        chrome_result = {
            "browser_name": "Google Chrome",
            "status": "SUCCESS",
            "file_count": 3,
            "total_bytes": 300000,
        }
        edge_result = {
            "browser_name": "Microsoft Edge",
            "status": "SUCCESS",
            "file_count": 2,
            "total_bytes": 100000,
        }
        firefox_result = {
            "browser_name": "Mozilla Firefox",
            "status": "NOT_INSTALLED",
            "file_count": 0,
            "total_bytes": 0,
        }

        dist = BrowserStorageAnalyzer.calculate_browser_storage_distribution([
            chrome_result, edge_result, firefox_result
        ])

        self.assertEqual(dist["total_combined_bytes"], 400000)
        self.assertEqual(dist["active_browser_count"], 2)

        browsers = {b["browser_name"]: b for b in dist["browsers"]}
        self.assertAlmostEqual(browsers["Google Chrome"]["percentage"], 75.0, places=2)
        self.assertAlmostEqual(browsers["Microsoft Edge"]["percentage"], 25.0, places=2)
        self.assertEqual(browsers["Mozilla Firefox"]["percentage"], 0.0)

    def test_top_five_and_remaining_files_calculation(self):
        """Validates Module B: Top 5 files extraction + remaining files aggregate row."""
        # Create 8 dummy files with known sizes
        sizes = [50000, 40000, 30000, 20000, 10000, 5000, 3000, 2000]
        total_folder_size = sum(sizes)  # 160,000 bytes
        files = []

        for i, s in enumerate(sizes):
            files.append({
                "name": f"cache_item_{i}.tmp",
                "full_path": f"C:\\dummy\\cache_item_{i}.tmp",
                "size_bytes": s,
                "size_fmt": f"{s} B",
                "extension": ".tmp",
                "category_label": "Web Cache",
                "badge": "CACHE",
                "mtime": time.time(),
                "mtime_fmt": "2026-11-04 10:00:00",
                "age_days": 30,
                "accessible": True,
                "zombie_score": 85,
                "classification": "POTENTIAL ZOMBIE DATA",
                "risk_level": "CRITICAL_ZOMBIE_CANDIDATE",
                "quarantine_eligible": False,
            })

        browser_data = {
            "browser_name": "Test Browser",
            "total_bytes": total_folder_size,
            "files": files,
        }

        analysis = BrowserStorageAnalyzer.analyze_individual_file_storage(browser_data)

        # 1. Exactly 5 top files
        self.assertEqual(len(analysis["top_files"]), 5)
        self.assertEqual(analysis["top_files"][0]["size_bytes"], 50000)
        # Denominator check: 50,000 / 160,000 = 31.25%
        self.assertAlmostEqual(analysis["top_files"][0]["percentage"], 31.25, places=2)

        # 2. Remaining files aggregate row exists
        rem = analysis["remaining_row"]
        self.assertIsNotNone(rem)
        self.assertTrue(rem["is_aggregate"])
        # Sum of remaining 3 files: 5000 + 3000 + 2000 = 10,000 bytes
        self.assertEqual(rem["size_bytes"], 10000)
        # Remaining percentage: 10,000 / 160,000 = 6.25%
        self.assertAlmostEqual(rem["percentage"], 6.25, places=2)

        # 3. Sum of top 5 + remaining must equal 100%
        top_5_pct_sum = sum(f["percentage"] for f in analysis["top_files"])
        self.assertAlmostEqual(top_5_pct_sum + rem["percentage"], 100.0, places=2)

        # 4. Total row
        self.assertEqual(analysis["total_row"]["size_bytes"], total_folder_size)
        self.assertEqual(analysis["total_row"]["percentage"], 100.0)

    def test_five_or_fewer_files_no_remaining_row(self):
        """When total files <= 5, no remaining row should be created."""
        sizes = [300, 200, 100]
        files = [{
            "name": f"f_{i}.dat",
            "full_path": f"C:\\dummy\\f_{i}.dat",
            "size_bytes": s,
            "size_fmt": f"{s} B",
            "extension": ".dat",
            "category_label": "Web Cache",
            "badge": "CACHE",
            "mtime": time.time(),
            "mtime_fmt": "2026-11-04 10:00:00",
            "age_days": 10,
            "accessible": True,
            "zombie_score": 40,
            "classification": "KEEP",
            "risk_level": "LOW_RISK_ACTIVE",
            "quarantine_eligible": False,
        } for i, s in enumerate(sizes)]

        browser_data = {
            "browser_name": "Small Browser",
            "total_bytes": 600,
            "files": files,
        }

        analysis = BrowserStorageAnalyzer.analyze_individual_file_storage(browser_data)
        self.assertEqual(len(analysis["top_files"]), 3)
        self.assertIsNone(analysis["remaining_row"])
        self.assertAlmostEqual(analysis["top_files"][0]["percentage"], 50.0, places=2)

    def test_empty_and_zero_byte_handling(self):
        """Validates safe division-by-zero protection for empty/zero-byte folders."""
        browser_data = {
            "browser_name": "Empty Browser",
            "total_bytes": 0,
            "files": [],
        }
        analysis = BrowserStorageAnalyzer.analyze_individual_file_storage(browser_data)
        self.assertEqual(len(analysis["top_files"]), 0)
        self.assertIsNone(analysis["remaining_row"])
        self.assertEqual(analysis["total_row"]["percentage"], 0.0)

        # Multi-browser calculation with all zeros
        dist = BrowserStorageAnalyzer.calculate_browser_storage_distribution([browser_data])
        self.assertEqual(dist["total_combined_bytes"], 0)
        self.assertEqual(dist["browsers"][0]["percentage"], 0.0)

    def test_duplicate_file_prevention_during_scan(self):
        """Validates that scanning a directory structure prevents duplicate counting."""
        # Create a mock cache directory
        cache_dir = Path(self.root) / "Default" / "Cache"
        cache_dir.mkdir(parents=True)

        f1 = cache_dir / "cache_01.tmp"
        f1.write_bytes(b"STALE_CACHE_PAYLOAD_ABC" * 100)
        f2 = cache_dir / "cache_02.tmp"
        f2.write_bytes(b"ANOTHER_CACHE_PAYLOAD_XYZ" * 200)

        mock_browser = {
            "name": "Mock Chrome",
            "id": "mock_chrome",
            "path": self.root,
            "layout_kind": "chromium",
            "exists": True,
            "accessible": True,
        }

        res = BrowserStorageAnalyzer.scan_browser_files(mock_browser, mode=MODE_SAFE_DEMO)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["file_count"], 2)
        expected_size = f1.stat().st_size + f2.stat().st_size
        self.assertEqual(res["total_bytes"], expected_size)

    def test_classification_integration_read_only(self):
        """Validates that files in storage analysis have correct ZombieDataClassifier details."""
        cache_dir = Path(self.root) / "Cache"
        cache_dir.mkdir(parents=True)

        # Create an old cache file (45 days old)
        old_file = cache_dir / "old_blob.tmp"
        old_file.write_bytes(b"OLD_CACHE_BLOB" * 50)
        old_mtime = time.time() - (45 * 86400)
        os.utime(str(old_file), (old_mtime, old_mtime))

        mock_browser = {
            "name": "Mock Browser",
            "id": "mock",
            "path": self.root,
            "layout_kind": "demo",
            "exists": True,
            "accessible": True,
        }

        res = BrowserStorageAnalyzer.scan_browser_files(mock_browser, mode=MODE_SAFE_DEMO, age_threshold_days=14)
        self.assertEqual(len(res["files"]), 1)
        item = res["files"][0]

        # Verify classification fields are populated
        self.assertIn("zombie_score", item)
        self.assertGreaterEqual(item["zombie_score"], 60)
        self.assertIn("classification", item)
        self.assertIn("reasons", item)
        self.assertTrue(item["accessible"])


if __name__ == "__main__":
    unittest.main()

