import typing
from pathlib import Path

from core.run.task_registry import TaskRegistry
from core.run.task import TaskDefinition
from core.run.series_parallel import series, parallel, Composite
from core.run.src import src
from core.run.dest import dest
from core.run.pipeline import PipeStream
from core.run.transforms import rename, replace, filter, through

_registry = TaskRegistry()
_executor = None


def task(name=None, deps=None):
    if callable(name):
        fn = name
        task_name = fn.__name__
        desc = (fn.__doc__ or "").strip()
        _registry.register(task_name, TaskDefinition(task_name, fn=fn, deps=[], description=desc))
        return fn

    def decorator(fn):
        task_name = name or fn.__name__
        desc = (fn.__doc__ or "").strip()
        _registry.register(task_name, TaskDefinition(task_name, fn=fn, deps=deps or [], description=desc))
        return fn
    return decorator


def cmd(command_line: str):
    if _executor is None:
        print("[red]Executor nao disponivel (cmd() usado fora de runfile?)[/red]")
        return
    result = _executor.execute(command_line)
    if result:
        print(result)


def watch(patterns: typing.Union[str, list[str]], *task_refs: typing.Any, debounce: int = 200):
    from core.run.watcher import Watcher
    watcher = Watcher(patterns, task_refs, debounce=debounce)
    watcher.start()


def set_executor(executor):
    global _executor
    _executor = executor


def get_registry() -> TaskRegistry:
    return _registry


def clear_registry():
    _registry.clear()
