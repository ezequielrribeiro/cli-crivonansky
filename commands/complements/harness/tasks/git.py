"""Tarefa git:run."""

import shlex

from ..catalog import register
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import ensure_allowed, legacy_repo

READ_ONLY = {
    "status",
    "log",
    "diff",
    "show",
    "blame",
    "branch",
    "rev-parse",
    "ls-files",
    "remote",
    "tag",
    "describe",
    "shortlog",
    "reflog",
    "config",
}


def _args(params) -> list[str]:
    raw = params.get("args")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        return shlex.split(raw)
    return []


def intent_for(params) -> str:
    args = _args(params)
    if not args:
        return "read"
    return "read" if args[0] in READ_ONLY else "write"


def handle(ctx, params):
    args = _args(params)
    if not args:
        return TaskResult(False, "parâmetro 'args' obrigatório", exit_code=2)

    repo = params.get("repo")
    cwd = ensure_allowed(ctx, str(repo)) if repo else legacy_repo(ctx)

    timeout = float(params.get("timeout") or 60)
    res = run_process(["git", *args], cwd=cwd, timeout=timeout)

    if res.timed_out:
        return TaskResult(False, "git: timeout", details=res.combined, exit_code=124, status="timeout")

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"git {' '.join(args)} (exit {res.exit_code})",
        details=res.combined,
        exit_code=res.exit_code,
    )


register(
    TaskSpec(
        name="git:run",
        intent="read",
        description="Executa um comando git no repositório legado",
        required=["args"],
        optional=["repo"],
        handler=handle,
        intent_fn=intent_for,
    )
)
