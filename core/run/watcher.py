import typing
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from core.run.task_registry import TaskRegistry
from core.run.task import TaskDefinition
from core.run.series_parallel import _resolve_ref


class Watcher:
    def __init__(
        self,
        patterns: typing.Union[str, list[str]],
        task_refs: tuple[typing.Any, ...],
        debounce: int = 200,
    ):
        if isinstance(patterns, str):
            patterns = [patterns]
        self.patterns = patterns
        self.task_refs = task_refs
        self.debounce = debounce / 1000.0
        self._observer = None
        self._last_trigger = 0.0

    def _on_event(self, event):
        now = time.time()
        if now - self._last_trigger < self.debounce:
            return
        self._last_trigger = now

        if event.is_directory:
            return

        path = Path(event.src_path)
        rel = path.relative_to(Path.cwd())
        print(f"[green]Arquivo alterado:[/green] {rel}")

        registry = _get_registry()
        for ref in self.task_refs:
            task_def = _resolve_ref(ref, registry)
            if task_def:
                try:
                    task_def.run(registry)
                except Exception as e:
                    print(f"[red]Erro ao executar task: {e}[/red]")

    def start(self):
        event_handler = PatternMatchingEventHandler(
            patterns=self.patterns,
            ignore_directories=True,
            case_sensitive=False,
        )
        event_handler.on_modified = self._on_event
        event_handler.on_created = self._on_event

        self._observer = Observer()
        self._observer.schedule(event_handler, str(Path.cwd()), recursive=True)
        self._observer.start()
        print(f"[green]Watch ativo para: {', '.join(self.patterns)}[/green]")

        try:
            while self._observer.is_alive():
                self._observer.join(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()


def _get_registry():
    from core.run.api import get_registry
    return get_registry()
