"""Execução de subprocessos com timeout, streaming opcional e kill da árvore."""

import os
import subprocess
import threading
from dataclasses import dataclass


@dataclass
class ProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def combined(self) -> str:
        parts = [self.stdout or ""]
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(part for part in parts if part).strip()


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )
    else:
        proc.kill()


def run_process(
    cmd,
    cwd: str | None = None,
    timeout: float = 60,
    shell: bool = False,
    env: dict | None = None,
    stream=None,
) -> ProcessResult:
    """Executa ``cmd`` e devolve a saída combinada.

    ``stream`` é um callback opcional ``(linha: str) -> None`` chamado em tempo
    real para cada linha de stdout/stderr — usado para publicar o progresso de
    instalações demoradas sem esperar o processo terminar.
    """
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creationflags,
        )
    except OSError as exc:
        # WinError 2/3 aqui quase sempre é caminho errado no harness.yaml:
        # deixe explícito qual comando e qual diretório falharam.
        if isinstance(cmd, (list, tuple)):
            command = " ".join(str(part) for part in cmd)
        else:
            command = str(cmd)
        detail = (
            f"{exc.strerror or exc} "
            f"(comando: {command}; cwd: {cwd or os.getcwd()})"
        )
        error = type(exc)(exc.errno, detail)
        winerror = getattr(exc, "winerror", None)
        if winerror:
            error.winerror = winerror
        raise error from exc

    chunks_out: list[str] = []
    chunks_err: list[str] = []

    def pump(pipe, chunks):
        try:
            for line in iter(pipe.readline, ""):
                chunks.append(line)
                if stream is not None:
                    text = line.rstrip("\r\n")
                    if text:
                        try:
                            stream(text)
                        except Exception:  # noqa: BLE001 - stream é best-effort
                            pass
        except (ValueError, OSError):
            pass
        finally:
            try:
                pipe.close()
            except OSError:
                pass

    readers = [
        threading.Thread(target=pump, args=(proc.stdout, chunks_out), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr, chunks_err), daemon=True),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    for reader in readers:
        reader.join(timeout=5)

    exit_code = proc.returncode if proc.returncode is not None else -1
    return ProcessResult(exit_code, "".join(chunks_out), "".join(chunks_err), timed_out)
