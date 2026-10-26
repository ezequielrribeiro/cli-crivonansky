"""Execução de subprocessos com timeout e encerramento da árvore."""

import os
import subprocess
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
) -> ProcessResult:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

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

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return ProcessResult(proc.returncode, stdout or "", stderr or "", False)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        stdout, stderr = proc.communicate()
        return ProcessResult(proc.returncode, stdout or "", stderr or "", True)
