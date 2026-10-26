"""Tarefas shell:run e py:run."""

import shutil
import sys

from ..catalog import register
from ..config import get_tool
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import ensure_allowed, legacy_repo


def _cwd(ctx, params) -> str:
    cwd = params.get("cwd")
    return ensure_allowed(ctx, str(cwd)) if cwd else legacy_repo(ctx)


def handle_shell(ctx, params):
    command = params.get("command")
    if not command:
        return TaskResult(False, "parâmetro 'command' obrigatório", exit_code=2)

    shell = str(params.get("shell") or "powershell").lower()
    if shell in ("cmd", "cmd.exe"):
        cmd = ["cmd", "/c", str(command)]
    else:
        exe = "pwsh" if shutil.which("pwsh") else "powershell"
        cmd = [exe, "-NoProfile", "-NonInteractive", "-Command", str(command)]

    timeout = float(params.get("timeout") or 60)
    res = run_process(cmd, cwd=_cwd(ctx, params), timeout=timeout)

    if res.timed_out:
        return TaskResult(False, "shell: timeout", details=res.combined, exit_code=124, status="timeout")

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"shell exit {res.exit_code}",
        details=res.combined,
        exit_code=res.exit_code,
    )


def handle_py(ctx, params):
    python = get_tool(ctx.config, "python") or sys.executable
    script = params.get("script")
    module = params.get("module")
    args = params.get("args") or []
    if isinstance(args, str):
        import shlex

        args = shlex.split(args)
    args = [str(item) for item in args]

    if script:
        cmd = [python, ensure_allowed(ctx, str(script)), *args]
    elif module:
        cmd = [python, "-m", str(module), *args]
    else:
        return TaskResult(False, "informe 'script' ou 'module'", exit_code=2)

    timeout = float(params.get("timeout") or 120)
    res = run_process(cmd, cwd=_cwd(ctx, params), timeout=timeout)

    if res.timed_out:
        return TaskResult(False, "python: timeout", details=res.combined, exit_code=124, status="timeout")

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"python exit {res.exit_code}",
        details=res.combined,
        exit_code=res.exit_code,
    )


register(
    TaskSpec(
        name="shell:run",
        intent="write",
        description="Executa um comando no shell do Windows",
        required=["command"],
        optional=["shell", "cwd"],
        handler=handle_shell,
    )
)

register(
    TaskSpec(
        name="py:run",
        intent="write",
        description="Executa um script ou módulo Python",
        required=[],
        optional=["script", "module", "args", "cwd"],
        handler=handle_py,
    )
)
