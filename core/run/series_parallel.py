import typing
import concurrent.futures
import threading

from core.run.task_registry import TaskRegistry


class Composite:
    def __init__(self, kind: str, *task_refs: typing.Any):
        self.kind = kind
        self.task_refs = task_refs

    def run(self, registry: TaskRegistry):
        resolved = [_resolve_ref(r, registry) for r in self.task_refs]

        if self.kind == "series":
            for task_def in resolved:
                if task_def is None:
                    continue
                task_def.run(registry)
        elif self.kind == "parallel":
            threads = []
            for task_def in resolved:
                if task_def is None:
                    continue
                t = threading.Thread(target=task_def.run, args=(registry,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()


def series(*task_refs: typing.Any) -> Composite:
    return Composite("series", *task_refs)


def parallel(*task_refs: typing.Any) -> Composite:
    return Composite("parallel", *task_refs)


def _resolve_ref(ref: typing.Any, registry: TaskRegistry):
    from core.run.task import TaskDefinition

    if isinstance(ref, str):
        return registry.get(ref)
    if isinstance(ref, TaskDefinition):
        return ref
    if callable(ref) and hasattr(ref, "_is_task"):
        return ref
    return None
