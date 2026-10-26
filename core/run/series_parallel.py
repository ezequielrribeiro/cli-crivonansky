import typing
import threading

from core.run.task_registry import TaskRegistry


class Composite:
    def __init__(self, kind: str, *task_refs: typing.Any):
        self.kind = kind
        self.task_refs = task_refs

    def run(self, registry: TaskRegistry) -> bool:
        resolved = [_resolve_ref(r, registry) for r in self.task_refs]

        if self.kind == "series":
            for task_def in resolved:
                if task_def is None:
                    print("[red]Task nao encontrada na serie[/red]")
                    return False
                if not task_def.run(registry):
                    return False
            return True

        if self.kind == "parallel":
            results: list[bool] = []

            def _run(task_def):
                results.append(bool(task_def.run(registry)) if task_def is not None else False)

            threads = []
            for task_def in resolved:
                thread = threading.Thread(target=_run, args=(task_def,))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            return all(results) if results else True

        return True


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
    if callable(ref) and getattr(ref, "_is_task", False):
        name = getattr(ref, "_task_name", None) or getattr(ref, "__name__", None)
        return registry.get(name) if name else None
    return None
