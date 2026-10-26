"""Catálogo fechado de tarefas do harness."""

from .types import TaskSpec

_TASKS: dict[str, TaskSpec] = {}
_loaded = False


def register(spec: TaskSpec) -> None:
    _TASKS[spec.name] = spec


def get_task(name: str) -> TaskSpec | None:
    return _TASKS.get(name)


def all_tasks() -> list[TaskSpec]:
    return sorted(_TASKS.values(), key=lambda spec: spec.name)


def load_tasks() -> None:
    global _loaded
    if _loaded:
        return

    from .tasks import (  # noqa: F401
        code,
        db,
        docker,
        docs,
        env,
        file,
        git,
        links,
        patch,
        pipelines,
        prompt,
        rag,
        shell,
    )

    _loaded = True
