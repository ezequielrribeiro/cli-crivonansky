import typing
from core.run.task_registry import TaskRegistry


class TaskDefinition:
    def __init__(
        self,
        name: str,
        fn: typing.Callable | None = None,
        deps: list[str] | None = None,
        description: str = "",
    ):
        self.name = name
        self.fn = fn
        self.deps = deps or []
        self.description = description

    def run(self, registry: TaskRegistry) -> bool:
        """Executa a task e devolve True em caso de sucesso."""
        for dep_name in self.deps:
            dep = registry.get(dep_name)
            if dep is None:
                print(f"[red]Dependencia '{dep_name}' nao encontrada para task '{self.name}'[/red]")
                return False
            if not dep.run(registry):
                return False

        if self.fn is None:
            print(f"[yellow]Task '{self.name}' nao possui funcao[/yellow]")
            return False

        result = self.fn()

        if result is not None and hasattr(result, "run"):
            return bool(result.run(registry))

        return True
