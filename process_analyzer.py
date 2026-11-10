try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class ProcessAnalyzer:
    """
    Sub-component of Zombie Data Purger responsible for checking 
    if associated browser/Electron application processes are running.
    """

    @staticmethod
    def is_process_running(process_name: str) -> bool:
        """
        Queries Windows active process list for given process executable name.
        Safe against permission errors or missing psutil library.
        """
        if not process_name or not PSUTIL_AVAILABLE:
            return False

        proc_lower = process_name.lower()
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info.get('name')
                    if name and name.lower() == proc_lower:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            return False
        return False

    @classmethod
    def get_process_status(cls, process_name: str) -> dict:
        """Returns structured process status and clear academic explanation."""
        if not process_name or not PSUTIL_AVAILABLE:
            running = None
        else:
            try:
                running = False
                for proc in psutil.process_iter(['name']):
                    try:
                        name = proc.info.get('name')
                        if name and name.casefold() == process_name.casefold():
                            running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except Exception:
                running = None
        status_text = "RUNNING" if running is True else ("NOT RUNNING" if running is False else "UNKNOWN")

        if running is True:
            explanation = f"Process '{process_name}' is currently active — data may be actively used by the application."
        elif running is False:
            explanation = f"Application process '{process_name}' is not currently running — this is one indicator supporting stale-data classification."
        else:
            explanation = f"Application process '{process_name}' status is unknown — cleanup must remain blocked."

        return {
            "process_name": process_name,
            "running": running,
            "status_text": status_text,
            "explanation": explanation
        }
