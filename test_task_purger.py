"""Deterministic task-score tests using synthetic telemetry only."""
import unittest
from task_analyzer import TaskAnalyzer


class TaskAnalysisTests(unittest.TestCase):
    def test_active_io_is_protected(self):
        result = TaskAnalyzer.calculate_task_score({
            "io_rate_bytes": 250 * 1024, "has_audio": False,
            "is_foreground": False, "window_state": "Background",
            "idle_minutes": 120, "memory_mb": 400,
        })
        self.assertEqual(result["score"], 0)
        self.assertTrue(result["is_protected"])

    def test_media_is_protected(self):
        result = TaskAnalyzer.calculate_task_score({
            "io_rate_bytes": 0, "has_audio": True, "is_foreground": False,
            "window_state": "Background", "idle_minutes": 120, "memory_mb": 200,
        })
        self.assertEqual(result["score"], 0)
        self.assertTrue(result["is_protected"])


if __name__ == "__main__":
    unittest.main()
