"""Cancellable, read-only periodic filesystem scan worker."""
import threading

from scanner import FileScanner


class BackgroundScanWorker:
    def __init__(self, app_provider, mode_provider, on_result, interval_seconds=900):
        self.app_provider = app_provider
        self.mode_provider = mode_provider
        self.on_result = on_result
        self.interval_seconds = max(60, int(interval_seconds))
        self._stop = threading.Event()
        self._thread = None
        self._scan_cancel = threading.Event()

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ZombieDiskScan", daemon=True)
        self._thread.start()

    def stop(self, timeout=5):
        self._stop.set()
        self._scan_cancel.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(0, timeout))
        return not self.is_running

    def _run(self):
        while not self._stop.is_set():
            mode = self.mode_provider()
            apps = self.app_provider(mode)
            for app in apps:
                if self._stop.is_set():
                    break
                if not app.get("exists"):
                    continue
                self._scan_cancel.clear()
                result = FileScanner.scan_directory(app, cancel_event=self._scan_cancel)
                result["mode"] = mode
                result["background"] = True
                if not self._stop.is_set():
                    self.on_result(result)
            if not self._stop.is_set():
                self.on_result({"mode": mode, "maintenance": True, "files": []})
            self._stop.wait(self.interval_seconds)
