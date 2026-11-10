"""Non-destructive real-system safety assertions; never touch AppData or suspend processes."""
import os
import unittest

from config import MODE_REAL_SYSTEM_ACTIVE
from safety_policy import Decision, SafetyPolicy
from task_suspender import TaskSuspender


class RealSystemSafetyTests(unittest.TestCase):
    def test_outside_path_never_authorized_for_quarantine(self):
        decision = SafetyPolicy.authorize(
            "quarantine", os.path.abspath(__file__), mode=MODE_REAL_SYSTEM_ACTIVE,
            app_name="Google Chrome", process_running=False,
            metadata={"accessible": True, "size_bytes": 1, "mtime": 1,
                      "file_identity": {"device": 1, "inode": 1}}, age_days=100,
        )
        self.assertEqual(decision.decision, Decision.DENY)

    def test_process_suspension_is_always_blocked(self):
        self.assertFalse(TaskSuspender.suspend_task(
            os.getpid(), "Safety Test", "python.exe", 0, "must be blocked",
            mode=MODE_REAL_SYSTEM_ACTIVE,
        ))


if __name__ == "__main__":
    unittest.main()
