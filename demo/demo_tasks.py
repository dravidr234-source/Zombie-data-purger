"""Read-only compatibility surface for the retired process-control demo."""

DEMO_ROLES_METADATA = {}


class DemoTaskManager:
    """No demo processes are spawned, terminated, suspended, or resumed."""

    @classmethod
    def spawn_all_demo_tasks(cls):
        return []

    @classmethod
    def get_active_demo_tasks(cls):
        return {}

    @classmethod
    def terminate_all_demo_tasks(cls):
        return []
