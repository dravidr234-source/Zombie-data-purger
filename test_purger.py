"""Read-only scanner integration tests; all files live in temporary directories."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner import FileScanner
import demo.demo_data as demo_data_module
import safety_policy as safety_policy_module


class ScannerTests(unittest.TestCase):
    def test_scans_cache_files_and_skips_profile_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "profile"
            cache = root / "Default" / "Cache"
            cache.mkdir(parents=True)
            (cache / "old.tmp").write_bytes(b"cache")
            (cache / "Cookies").write_bytes(b"protected")
            (root / "Bookmarks").write_text("private", encoding="utf-8")
            result = FileScanner.scan_directory({
                "name": "Google Chrome", "path": str(root),
                "process_name": "not-running-app.exe", "type": "Browser (Demo Sandbox)",
            })
            paths = {Path(item["full_path"]).name for item in result["files"]}
            self.assertEqual(paths, {"old.tmp", "Cookies"})
            self.assertNotIn("Bookmarks", paths)
            cookie = next(item for item in result["files"] if item["file_name"] == "Cookies")
            self.assertEqual(cookie["classification"], "KEEP")
            old = next(item for item in result["files"] if item["file_name"] == "old.tmp")
            self.assertEqual(old["classification"], "POTENTIAL ZOMBIE DATA")

    def test_demo_generation_is_confined_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "demo"
            with patch.object(demo_data_module, "DEMO_BASE_DIR", str(base)), \
                 patch.object(safety_policy_module, "DEMO_BASE_DIR", str(base)):
                result = demo_data_module.create_safe_demo_environment()
                self.assertEqual(result["files_created"], 11)
                sample = base / "Chrome_Demo" / "Cache" / "old_cache_01.tmp"
                original = sample.read_bytes()
                sample.write_bytes(b"user edit stays intact")
                second = demo_data_module.create_safe_demo_environment()
                self.assertEqual(second["files_created"], 0)
                self.assertEqual(sample.read_bytes(), b"user edit stays intact")

if __name__ == "__main__":
    unittest.main()
