class TaskRegistry:
    def __init__(self):
        self._tasks: dict[str, "TaskDefinition"] = {}

    def register(self, name: str, task: "TaskDefinition"):
        self._tasks[name] = task

    def get(self, name: str) -> "TaskDefinition | None":
        return self._tasks.get(name)

    def all(self) -> dict[str, "TaskDefinition"]:
        return dict(self._tasks)

    def clear(self):
        self._tasks.clear()
