"""Read-only task telemetry watcher. It never freezes or modifies a process."""

import time
import threading
from typing import Callable, Optional, List, Dict, Any

from config import TASK_WATCHDOG_INTERVAL_SECONDS, MODE_SAFE_DEMO
from task_analyzer import TaskAnalyzer
from task_suspender import TaskSuspender

class TaskWatchdog:
    """Read-only background process telemetry monitor. It never changes processes."""

    def __init__(
        self,
        get_current_mode_fn: Callable[[], str],
        on_event_fn: Optional[Callable[[str, str], None]] = None,
        on_update_fn: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], None]] = None,
    ):
        self.get_current_mode_fn = get_current_mode_fn
        self.on_event_fn = on_event_fn
        self.on_update_fn = on_update_fn
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """Starts background watchdog thread."""
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ZombieTaskWatchdog")
        self._thread.start()
        if self.on_event_fn:
            self.on_event_fn("WATCHDOG_STARTED", "Background Zombie Task Watchdog is now ACTIVE.")

    def stop(self):
        """Stops background watchdog thread gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=max(1.0, TASK_WATCHDOG_INTERVAL_SECONDS + 1))
        self.is_running = bool(self._thread and self._thread.is_alive())
        if self.on_event_fn:
            self.on_event_fn("WATCHDOG_STOPPED", "Background Zombie Task Watchdog paused.")

    def run_one_scan(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Executes a single scan cycle immediately."""
        mode = self.get_current_mode_fn()
        if mode == MODE_SAFE_DEMO:
            scanned_tasks = TaskAnalyzer.scan_demo_tasks()
        else:
            scanned_tasks = TaskAnalyzer.scan_real_tasks()

        frozen_tasks = TaskSuspender.get_frozen_tasks(mode)
        return scanned_tasks, frozen_tasks

    def _run_loop(self):
        """Continuous background execution loop."""
        while not self._stop_event.is_set():
            try:
                scanned_tasks, frozen_tasks = self.run_one_scan()
                if self.on_update_fn:
                    self.on_update_fn(scanned_tasks, frozen_tasks)
            except Exception as e:
                print(f"[TaskWatchdog] Scan cycle error: {e}")

            # Sleep in smaller increments for responsive shutdown
            for _ in range(int(TASK_WATCHDOG_INTERVAL_SECONDS * 10)):
                if self._stop_event.is_set():
                    break
                self._stop_event.wait(0.1)
        self.is_running = False
