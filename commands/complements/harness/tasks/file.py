"""Tarefas file:read e context:pack."""

import os

from ..catalog import register
from ..types import TaskResult, TaskSpec
from ..util import as_int, as_list, ensure_allowed, read_text


def handle_read(ctx, params):
    path = params.get("path")
    if not path:
        return TaskResult(False, "parâmetro 'path' obrigatório", exit_code=2)

    try:
        full = ensure_allowed(ctx, str(path))
    except PermissionError as exc:
        return TaskResult(False, str(exc), exit_code=3)

    if not os.path.isfile(full):
        return TaskResult(False, f"arquivo não encontrado: {path}", exit_code=2)

    lines = read_text(full).splitlines()
    start = max(1, as_int(params.get("start"), 1))
    end = min(len(lines), as_int(params.get("end"), len(lines)))
    numbered = "\n".join(f"{i:>5}  {lines[i - 1]}" for i in range(start, end + 1))
    return TaskResult(
        True,
        f"{path}: linhas {start}-{end} de {len(lines)}",
        details=numbered,
    )


def handle_pack(ctx, params):
    files = as_list(params.get("files"))
    if not files:
        return TaskResult(False, "parâmetro 'files' obrigatório", exit_code=2)

    budget = as_int(params.get("budget"), 12000)
    chunks = []
    used = 0

    for item in files:
        try:
            full = ensure_allowed(ctx, str(item))
        except PermissionError as exc:
            chunks.append(f"## {item}\n\n(acesso negado: {exc})")
            continue

        if not os.path.isfile(full):
            chunks.append(f"## {item}\n\n(não encontrado)")
            continue

        content = read_text(full)
        block = f"## {item}\n\n```\n{content}\n```"

        if used + len(block) > budget:
            remaining = budget - used
            if remaining > 200:
                chunks.append(block[:remaining] + "\n... (truncado) ...\n```")
                used = budget
            break

        chunks.append(block)
        used += len(block)

    return TaskResult(
        True,
        f"{len(files)} arquivo(s) empacotado(s) em ~{used} caracteres",
        details="\n\n".join(chunks),
    )


register(
    TaskSpec(
        name="file:read",
        intent="read",
        description="Lê um arquivo do repositório com números de linha",
        required=["path"],
        optional=["start", "end"],
        handler=handle_read,
    )
)

register(
    TaskSpec(
        name="context:pack",
        intent="read",
        description="Empacota arquivos em Markdown respeitando um orçamento",
        required=["files"],
        optional=["ranges", "budget"],
        handler=handle_pack,
    )
)
