"""Tarefa env:check."""

import urllib.request

from ..catalog import register
from ..config import get_tool
from ..runner import run_process
from ..types import TaskResult, TaskSpec


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


def handle(ctx, params):
    lines = []
    ok_all = True

    res = run_process(["git", "--version"], timeout=10)
    ok = res.exit_code == 0 and not res.timed_out
    ok_all = ok_all and ok
    lines.append(_line("git", ok, (res.combined.splitlines() or [""])[0]))

    res = run_process(["docker", "info"], timeout=15)
    ok = res.exit_code == 0 and not res.timed_out
    ok_all = ok_all and ok
    lines.append(_line("docker", ok, "daemon acessível" if ok else "daemon indisponível"))

    codeknow = get_tool(ctx.config, "codeknow") or "codeknow"
    res = run_process([codeknow, "--version"], timeout=60)
    ok = res.exit_code == 0 and not res.timed_out
    ok_all = ok_all and ok
    lines.append(_line("codeknow", ok, (res.combined.splitlines() or [""])[0]))

    rag_api = get_tool(ctx.config, "rag", "api")
    if rag_api:
        ok, detail = _http_ok(rag_api.rstrip("/") + "/health")
        ok_all = ok_all and ok
        lines.append(_line("rag", ok, detail))

    summary = "ambiente OK" if ok_all else "há verificações com falha"
    return TaskResult(success=ok_all, summary=summary, details="\n".join(lines))


register(
    TaskSpec(
        name="env:check",
        intent="read",
        description="Verifica o ambiente do harness (git, docker, codeknow, rag)",
        required=[],
        optional=[],
        handler=handle,
    )
)
