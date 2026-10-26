"""Instalação de git hooks para disparar tarefas do harness (T4.5)."""

import os
import shutil
import stat
import sys

from .config import get_legacy, get_workspace
from .util import ensure_dir

HOOK_NAMES = ("post-commit", "post-merge")
MARKER = "# harness-hook"
BACKUP_SUFFIX = ".harness-bak"


def _hooks_dir(repo_path: str) -> str:
    return os.path.join(repo_path, ".git", "hooks")


def _is_ours(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return MARKER in fh.read(400)
    except OSError:
        return False


def _q(path: str) -> str:
    return str(path).replace("\\", "/")


def _build_script(
    tasks: list[str],
    python_exe: str,
    crivo_path: str,
    config_path: str,
    log_path: str,
) -> str:
    lines = [
        "#!/bin/sh",
        f"{MARKER}: gerado automaticamente pelo crivonansky; nao edite.",
        f'PYTHON="{_q(python_exe)}"',
        f'CRIVO="{_q(crivo_path)}"',
        f'CONFIG="{_q(config_path)}"',
        f'LOG="{_q(log_path)}"',
        'mkdir -p "$(dirname "$LOG")"',
        "(",
    ]
    for task in tasks:
        lines.append(
            f'  "$PYTHON" "$CRIVO" harness run "{task}" --config "$CONFIG" >> "$LOG" 2>&1'
        )
    lines.append(") &")
    return "\n".join(lines) + "\n"


def _settings(config: dict) -> tuple[list[str], str, str]:
    hooks_cfg = config.get("hooks") or {}
    tasks = hooks_cfg.get("tasks") or ["rag:sync"]
    log = hooks_cfg.get("log") or os.path.join(get_workspace(config), "runs", "hooks.log")
    if not os.path.isabs(log):
        log = os.path.join(get_workspace(config), log)

    repo = get_legacy(config, "repo_path")
    if not repo:
        raise ValueError("legacy.repo_path ausente no harness.yaml")

    repo = os.path.abspath(repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        raise ValueError(f"nao e um repositorio git: {repo}")

    return tasks, log, repo


def install(config: dict) -> list[str]:
    from core.loader import PROJECT_ROOT

    tasks, log, repo = _settings(config)
    hooks_dir = ensure_dir(_hooks_dir(repo))

    python_exe = sys.executable
    crivo_path = os.path.join(PROJECT_ROOT, "crivonansky.py")
    config_path = config.get("_path") or os.path.join(get_workspace(config), "harness.yaml")

    script = _build_script(tasks, python_exe, crivo_path, config_path, log)
    installed = []

    for name in HOOK_NAMES:
        target = os.path.join(hooks_dir, name)
        if os.path.exists(target) and not _is_ours(target):
            shutil.copy2(target, target + BACKUP_SUFFIX)

        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(script)

        os.chmod(target, os.stat(target).st_mode | stat.S_IEXEC)
        installed.append(name)

    return installed


def uninstall(config: dict) -> list[str]:
    _, _, repo = _settings(config)
    hooks_dir = _hooks_dir(repo)
    removed = []

    for name in HOOK_NAMES:
        target = os.path.join(hooks_dir, name)
        if not os.path.exists(target):
            continue
        if _is_ours(target):
            os.remove(target)
            backup = target + BACKUP_SUFFIX
            if os.path.exists(backup):
                shutil.move(backup, target)
            removed.append(name)

    return removed


def status(config: dict) -> dict:
    _, log, repo = _settings(config)
    hooks_dir = _hooks_dir(repo)
    result = {}
    for name in HOOK_NAMES:
        target = os.path.join(hooks_dir, name)
        result[name] = _is_ours(target)
    result["log"] = log
    return result
