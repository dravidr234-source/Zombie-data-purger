"""Synthetic scoring demo checks; does not spawn or modify operating-system processes."""
import unittest
from task_analyzer import TaskAnalyzer


class SyntheticTaskDemoTests(unittest.TestCase):
    def test_active_download_protection_example(self):
        result = TaskAnalyzer.calculate_task_score({
            "display_name": "Synthetic download", "io_rate_bytes": 220 * 1024,
            "has_audio": False, "is_foreground": False,
            "window_state": "Background", "idle_minutes": 60, "memory_mb": 10,
        })
        self.assertTrue(result["is_protected"])
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main()
