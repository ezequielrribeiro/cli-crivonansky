"""Formatação do bloco de resultado, truncamento e mascaramento de segredos."""

import json
import os
import re

from .config import get_legacy

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def collapse_repeats(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        j = i + 1
        while j < len(lines) and lines[j] == lines[i]:
            j += 1
        count = j - i
        if count >= 3:
            out.append(lines[i])
            out.append(f"... ({count - 1} linha(s) repetida(s) omitida(s)) ...")
        else:
            out.extend(lines[i:j])
        i = j
    return "\n".join(out)


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if not text or max_chars <= 0 or len(text) <= max_chars:
        return text, False

    text = collapse_repeats(text)
    if len(text) <= max_chars:
        return text, False

    head_len = max(int(max_chars * 0.6), 1)
    tail_len = max(int(max_chars * 0.3), 1)
    note = "\n... (saída truncada; log completo em artifacts) ...\n"
    return text[:head_len] + note + text[-tail_len:], True


def mask_secrets(text: str, config: dict) -> str:
    if not text:
        return text

    names = []
    for key in ("db_user_env", "db_password_env"):
        value = get_legacy(config, key)
        if value:
            names.append(value)

    for name in names:
        secret = os.environ.get(name)
        if secret and len(secret) >= 3:
            text = text.replace(secret, "***")
    return text


def format_result(
    block_id: str,
    task: str,
    status: str,
    exit_code: int,
    duration_ms: int,
    summary: str,
    details: str,
    artifacts: list[str],
    max_chars: int,
) -> tuple[str, bool]:
    details_text, truncated = truncate(strip_ansi(details or ""), max_chars)

    lines = [
        "```crivonansky-result",
        "harness: 1",
        f"id: {block_id}",
        f"task: {task}",
        f"status: {status}",
        f"exit_code: {exit_code}",
        f"duration_ms: {duration_ms}",
        f"summary: {json.dumps(summary, ensure_ascii=False)}",
        f"truncated: {'true' if truncated else 'false'}",
    ]
    if artifacts:
        lines.append("artifacts:")
        for artifact in artifacts:
            lines.append(f"  - {artifact}")
    if details_text:
        lines.append("details: |")
        for line in details_text.splitlines():
            lines.append(f"  {line}")
    lines.append("```")

    return "\n".join(lines), truncated
