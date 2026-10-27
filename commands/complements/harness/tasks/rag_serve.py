"""Tarefa rag:serve — inicia/para/consulta a API local do RAG.

A ingestão (`rag:sync`) usa subprocesso e não precisa da API. Já a busca
(`rag:search`) usa `POST /api/search`, então a API precisa estar no ar. Esta
tarefa permite controlar o serviço de dentro da TUI do crivonansky.
"""

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from ..catalog import register
from ..config import get_tool
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import as_int, ensure_dir, workspace

ACTIONS = {"start", "stop", "status", "restart"}


def _target(ctx, params) -> tuple[str, int, str]:
    api = get_tool(ctx.config, "rag", "api") or "http://127.0.0.1:8000"
    parsed = urllib.parse.urlparse(api)
    host = str(params.get("host") or parsed.hostname or "127.0.0.1")
    port = as_int(params.get("port"), parsed.port or 8000)
    client_host = "127.0.0.1" if host in ("0.0.0.0", "::", "[::]") else host
    return host, port, f"http://{client_host}:{port}"


def _health(api_base: str, timeout: float = 2.0) -> tuple[bool, object]:
    try:
        with urllib.request.urlopen(api_base.rstrip("/") + "/health", timeout=timeout) as response:
            return True, json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, str(exc)


def _check(api_base: str, timeout: float = 2.0) -> tuple[bool, object]:
    """Confirma que o endpoint respondeu no formato do RAG (status == ok)."""
    ok, data = _health(api_base, timeout=timeout)
    healthy = ok and isinstance(data, dict) and data.get("status") == "ok"
    return healthy, data


def _port_in_use(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "[::]") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((probe_host, port)) == 0


def _run_dir(ctx) -> str:
    return ensure_dir(os.path.join(workspace(ctx), "runs"))


def _pid_path(ctx) -> str:
    return os.path.join(_run_dir(ctx), "rag-api.pid")


def _log_paths(ctx) -> tuple[str, str]:
    run_dir = _run_dir(ctx)
    return (
        os.path.join(run_dir, "rag-api.log"),
        os.path.join(run_dir, "rag-api.err.log"),
    )


def _read_pid(ctx) -> int | None:
    try:
        with open(_pid_path(ctx), "r", encoding="utf-8") as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def _write_pid(ctx, pid: int) -> None:
    with open(_pid_path(ctx), "w", encoding="utf-8") as fh:
        fh.write(str(pid))


def _remove_pid(ctx) -> None:
    try:
        os.remove(_pid_path(ctx))
    except OSError:
        pass


def _tail(path: str, limit: int = 2000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()[-limit:]
    except OSError:
        return ""


def _pids_on_port(port: int) -> list[int]:
    """Descobre PIDs escutando na porta (Windows via netstat; POSIX via lsof)."""
    if os.name == "nt":
        res = run_process(["netstat", "-ano", "-p", "tcp"], timeout=20)
        pids = set()
        for line in res.combined.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0].upper() != "TCP":
                continue
            if parts[3].upper() != "LISTENING":
                continue
            if not parts[1].endswith(f":{port}"):
                continue
            try:
                pids.add(int(parts[4]))
            except ValueError:
                continue
        return sorted(pids)

    res = run_process(["lsof", "-ti", f"tcp:{port}"], timeout=20)
    pids = []
    for line in res.combined.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def _kill_pid(pid: int) -> bool:
    if os.name == "nt":
        res = run_process(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            timeout=20,
        )
        # PID inexistente também é um estado aceitável para "parar".
        return res.exit_code == 0 or "not found" in res.combined.lower() or "não encontrado" in res.combined.lower()

    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def _rag_tools(ctx) -> tuple[str | None, str | None]:
    rag = (ctx.config.get("tools") or {}).get("rag") or {}
    return rag.get("path"), rag.get("python")


def _status(ctx, api_base: str) -> TaskResult:
    ok, data = _check(api_base, timeout=2.0)
    pid = _read_pid(ctx)
    pid_line = f"PID: {pid}" if pid else "PID: não registrado"

    if ok:
        details = json.dumps(data, ensure_ascii=False, indent=2)
        return TaskResult(
            True,
            f"API do RAG rodando em {api_base}",
            details=f"{details}\n{pid_line}",
        )

    details = f"{data}\n{pid_line}"
    if pid:
        details += f"\nLog: {_log_paths(ctx)[1]}"
    return TaskResult(True, f"API do RAG parada em {api_base}", details=details)


def _start(ctx, host: str, port: int, api_base: str, timeout: float) -> TaskResult:
    ok, data = _check(api_base, timeout=2.0)
    if ok:
        return TaskResult(
            True,
            f"API do RAG já está rodando em {api_base}",
            details=json.dumps(data, ensure_ascii=False, indent=2),
        )

    rag_path, rag_python = _rag_tools(ctx)
    if not rag_path or not rag_python:
        return TaskResult(False, "tools.rag.path/python ausentes no harness.yaml", exit_code=2)
    if not os.path.isdir(rag_path):
        return TaskResult(False, f"diretório do RAG não encontrado: {rag_path}", exit_code=2)
    if not os.path.isfile(rag_python):
        return TaskResult(False, f"Python do RAG não encontrado: {rag_python}", exit_code=2)
    if _port_in_use(host, port):
        return TaskResult(
            False,
            f"porta {port} ocupada por outro processo; não iniciando",
            exit_code=2,
        )

    stdout_path, stderr_path = _log_paths(ctx)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [
        rag_python,
        "main.py",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]

    stdout = open(stdout_path, "a", encoding="utf-8")
    stderr = open(stderr_path, "a", encoding="utf-8")
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(
            cmd,
            cwd=rag_path,
            stdout=stdout,
            stderr=stderr,
            env=env,
            **kwargs,
        )
    except OSError as exc:
        return TaskResult(False, "falha ao iniciar a API do RAG", details=str(exc), exit_code=1)
    finally:
        stdout.close()
        stderr.close()

    _write_pid(ctx, proc.pid)

    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, data = _check(api_base, timeout=1.0)
        if ok:
            listening = _pids_on_port(port)
            api_pid = listening[0] if listening else proc.pid
            _write_pid(ctx, api_pid)
            details = json.dumps(data, ensure_ascii=False, indent=2)
            return TaskResult(
                True,
                f"API do RAG iniciada em {api_base} (PID {api_pid})",
                details=f"{details}\nLog: {stdout_path}",
            )
        if proc.poll() is not None:
            _remove_pid(ctx)
            return TaskResult(
                False,
                "a API do RAG encerrou durante a inicialização",
                details=_tail(stderr_path),
                exit_code=1,
            )
        time.sleep(0.5)

    return TaskResult(
        False,
        f"a API do RAG não respondeu em {int(timeout)}s",
        details=f"PID {proc.pid} ainda em execução.\nLog: {stdout_path}\nErros: {_tail(stderr_path)}",
        exit_code=124,
        status="timeout",
    )


def _stop(ctx, host: str, port: int, api_base: str) -> TaskResult:
    registered = _read_pid(ctx)
    listening = set(_pids_on_port(port))
    killed: list[int] = []

    if not listening:
        # Nada escutando na porta: o RAG não está no ar. Não mata um PID
        # registrado que pode ter sido reutilizado por outro processo.
        _remove_pid(ctx)
        return TaskResult(True, f"API do RAG já estava parada em {api_base}")

    # Só interrompe processos da porta se o /health confirmar que é o RAG.
    ok, _data = _check(api_base, timeout=2.0)
    if not ok:
        return TaskResult(
            False,
            f"porta {port} ocupada por processo desconhecido; nada foi interrompido",
            details=f"PIDs na porta: {', '.join(map(str, sorted(listening)))}",
            exit_code=2,
        )

    for pid in sorted(listening):
        if _kill_pid(pid):
            killed.append(pid)

    if not killed:
        return TaskResult(
            False,
            f"não foi possível encerrar a API do RAG (PID registrado: {registered})",
            details=f"PIDs na porta: {', '.join(map(str, sorted(listening)))}",
            exit_code=1,
        )

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if not _check(api_base, timeout=1.0)[0] and not _port_in_use(host, port):
            break
        time.sleep(0.3)

    _remove_pid(ctx)
    return TaskResult(
        True,
        f"API do RAG parada em {api_base}",
        details=f"PID(s) encerrado(s): {', '.join(map(str, sorted(set(killed))))}",
    )


def handle(ctx, params):
    action = str(params.get("action") or "start").strip().lower()
    if action not in ACTIONS:
        return TaskResult(
            False,
            f"action inválida: {action} (use {'|'.join(sorted(ACTIONS))})",
            exit_code=2,
        )

    host, port, api_base = _target(ctx, params)
    timeout = float(as_int(params.get("timeout"), 60))

    if action == "status":
        return _status(ctx, api_base)

    if action == "start":
        return _start(ctx, host, port, api_base, timeout)

    if action == "stop":
        return _stop(ctx, host, port, api_base)

    stopped = _stop(ctx, host, port, api_base)
    if not stopped.success:
        return stopped
    return _start(ctx, host, port, api_base, timeout)


register(
    TaskSpec(
        name="rag:serve",
        intent="read",
        description="Inicia, para ou consulta a API local do RAG",
        required=[],
        optional=["action", "host", "port", "timeout"],
        handler=handle,
    )
)
