"""Tarefas de pipeline: test:run, verify e lint."""

from ..catalog import get_task, register
from ..types import TaskResult, TaskSpec


def _run_pipeline(ctx, name: str, params: dict) -> TaskResult:
    pipeline = (ctx.config.get("pipelines") or {}).get(name)
    if not pipeline:
        return TaskResult(False, f"pipeline '{name}' não configurada", exit_code=2)

    logs = []
    ok = True

    for step in pipeline:
        if not isinstance(step, dict) or not step:
            logs.append(f"[?] passo inválido: {step}")
            ok = False
            break

        task_name, task_params = next(iter(step.items()))
        spec = get_task(task_name)
        if spec is None:
            logs.append(f"[{task_name}] tarefa desconhecida")
            ok = False
            break

        resolved = {}
        for key, value in (task_params or {}).items():
            if isinstance(value, str):
                resolved[key] = value.replace("{filter}", str(params.get("filter", "")))
            else:
                resolved[key] = value

        result = spec.handler(ctx, resolved)
        logs.append(f"[{task_name}] {result.summary}")
        if result.details:
            logs.append(result.details)

        if not result.success:
            ok = False
            break

    return TaskResult(
        success=ok,
        summary=f"pipeline {name}: {'OK' if ok else 'falhou'}",
        details="\n".join(logs),
        exit_code=0 if ok else 1,
    )


def _handler(name: str):
    def handle(ctx, params):
        return _run_pipeline(ctx, name, params)

    return handle


for _name in ("test:run", "verify", "lint"):
    register(
        TaskSpec(
            name=_name,
            intent="read",
            description=f"Executa a pipeline '{_name}' definida no harness.yaml",
            required=[],
            optional=["filter"],
            handler=_handler(_name),
        )
    )
