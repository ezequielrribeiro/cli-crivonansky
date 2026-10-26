"""Tarefas docker:exec e logs:tail."""

from ..catalog import register
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import as_int

READ_ONLY_PREFIXES = (
    "php -v",
    "php -l",
    "php -m",
    "php -r",
    "php --version",
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "pwd",
    "whoami",
    "env",
    "printenv",
    "mysql --version",
    "mysql -v",
    "mysqladmin ping",
    "composer --version",
    "node -v",
    "npm -v",
    "git --version",
    "echo",
    "date",
    "uname",
)


def intent_for(params) -> str:
    command = str(params.get("command", "")).strip().lower()
    return "read" if any(command.startswith(prefix) for prefix in READ_ONLY_PREFIXES) else "write"


def handle_exec(ctx, params):
    container = params.get("container")
    command = params.get("command")
    if not container or not command:
        return TaskResult(False, "parâmetros 'container' e 'command' obrigatórios", exit_code=2)

    timeout = float(params.get("timeout") or 120)
    res = run_process(
        ["docker", "exec", str(container), "sh", "-c", str(command)],
        timeout=timeout,
    )

    if res.timed_out:
        return TaskResult(False, "docker exec: timeout", details=res.combined, exit_code=124, status="timeout")

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"docker exec {container} (exit {res.exit_code})",
        details=res.combined,
        exit_code=res.exit_code,
    )


def handle_logs(ctx, params):
    container = params.get("container")
    if not container:
        return TaskResult(False, "parâmetro 'container' obrigatório", exit_code=2)

    lines = as_int(params.get("lines"), 50)
    res = run_process(["docker", "logs", "--tail", str(lines), str(container)], timeout=60)

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"logs de {container} (últimas {lines} linhas)",
        details=res.combined,
        exit_code=res.exit_code,
    )


register(
    TaskSpec(
        name="docker:exec",
        intent="write",
        description="Executa um comando dentro de um contêiner Docker",
        required=["container", "command"],
        optional=["timeout"],
        handler=handle_exec,
        intent_fn=intent_for,
    )
)

register(
    TaskSpec(
        name="logs:tail",
        intent="read",
        description="Lê as últimas linhas de log de um contêiner",
        required=["container"],
        optional=["lines"],
        handler=handle_logs,
    )
)
