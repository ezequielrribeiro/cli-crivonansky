"""Tarefa env:check."""

import os
import urllib.request

from ..catalog import register
from ..config import get_tool, get_tool_path
from ..runner import run_process
from ..task_types import TaskResult, TaskSpec
from ..util import looks_like_path
from .rag import tools_problem


def _http_ok(url: str, timeout: float = 3) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200, resp.read().decode("utf-8", "replace")[:300]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _line(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK   " if ok else "FALHA"
    suffix = f" - {detail}" if detail else ""
    return f"- [{mark}] {label}{suffix}"


def _check_command(label: str, cmd: list[str], timeout: float = 15) -> tuple[str, bool]:
    """Roda um comando externo sem derrubar o env:check quando ele não existe."""
    try:
        res = run_process(cmd, timeout=timeout)
    except (OSError, ValueError) as exc:
        return _line(label, False, f"não foi possível executar: {exc}"), False

    if res.timed_out:
        return _line(label, False, "timeout"), False

    ok = res.exit_code == 0
    detail = (res.combined.splitlines() or [""])[0]
    if not ok:
        lines = [line.strip() for line in res.combined.splitlines() if line.strip()]
        detail = lines[-1] if lines else f"exit code {res.exit_code}"
    return _line(label, ok, detail), ok


def handle(ctx, params):
    lines: list[str] = []
    ok_all = True

    def add(line: str, ok: bool) -> None:
        nonlocal ok_all
        lines.append(line)
        ok_all = ok_all and ok

    add(*_check_command("git", ["git", "--version"], timeout=10))
    add(*_check_command("docker", ["docker", "info"], timeout=15))

    workspace_path = os.path.abspath(ctx.workspace)
    try:
        os.makedirs(workspace_path, exist_ok=True)
        probe = os.path.join(workspace_path, f".env-check-{os.getpid()}.tmp")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        add(_line("workspace", True, workspace_path), True)
    except OSError as exc:
        add(_line("workspace", False, f"{workspace_path}: {exc}"), False)

    plugin_python = get_tool_path(ctx.config, "python")
    if plugin_python and looks_like_path(plugin_python):
        exists = os.path.isfile(plugin_python)
        add(
            _line(
                "python do plugin",
                exists,
                plugin_python if exists else f"não encontrado: {plugin_python}",
            ),
            exists,
        )

    codeknow = get_tool_path(ctx.config, "codeknow") or "codeknow"
    add(*_check_command("codeknow", [codeknow, "--version"], timeout=60))

    problem = tools_problem(ctx.config)
    add(
        _line("rag (tools.rag)", problem is None, problem or "path/python/main.py ok"),
        problem is None,
    )

    rag_api = get_tool(ctx.config, "rag", "api")
    if rag_api:
        ok, detail = _http_ok(rag_api.rstrip("/") + "/health")
        add(_line("rag (api)", ok, detail), ok)

    summary = "ambiente OK" if ok_all else "há verificações com falha"
    return TaskResult(
        success=ok_all,
        summary=summary,
        details="\n".join(lines),
        exit_code=0 if ok_all else 1,
    )


register(
    TaskSpec(
        name="env:check",
        intent="read",
        description="Verifica o ambiente do harness (git, docker, python, codeknow, rag)",
        required=[],
        optional=[],
        handler=handle,
    )
)
