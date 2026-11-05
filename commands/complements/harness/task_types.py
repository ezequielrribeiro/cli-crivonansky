"""Tipos compartilhados do plugin harness."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TaskResult:
    """Resultado de uma tarefa."""

    success: bool
    summary: str
    details: str = ""
    artifacts: list[str] = field(default_factory=list)
    exit_code: int = 0
    status: str | None = None


@dataclass
class TaskContext:
    """Contexto de execução passado a cada tarefa."""

    config: dict
    workspace: str
    run_dir: str
    interactive: bool = True
    yes: bool = False
    dry_run: bool = False


@dataclass
class TaskSpec:
    """Definição de uma tarefa do catálogo."""

    name: str
    intent: str  # "read" | "write"
    description: str
    required: list[str]
    optional: list[str]
    handler: Callable[[TaskContext, dict], TaskResult]
    intent_fn: Callable[[dict], str] | None = None
