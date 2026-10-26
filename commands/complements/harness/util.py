"""Utilitários compartilhados pelas tarefas."""

import os

from .config import get_legacy


def legacy_repo(ctx) -> str:
    return os.path.abspath(get_legacy(ctx.config, "repo_path", "."))


def workspace(ctx) -> str:
    return os.path.abspath(ctx.workspace)


def allowed_roots(ctx) -> list[str]:
    raw = (ctx.config.get("policy") or {}).get("allowed_roots") or []
    repo = legacy_repo(ctx)
    ws = workspace(ctx)
    roots = []
    for item in raw:
        value = str(item).replace("${LEGACY_REPO}", repo).replace("${HARNESS_WORKSPACE}", ws)
        roots.append(os.path.abspath(value))
    if not roots:
        roots = [repo, ws]
    return roots


def is_within(path: str, roots: list[str]) -> bool:
    path = os.path.abspath(path)
    for root in roots:
        try:
            if os.path.commonpath([path, root]) == root:
                return True
        except ValueError:
            continue
    return False


def resolve_path(ctx, path: str) -> str:
    if os.path.isabs(path):
        return os.path.abspath(path)

    for base in (legacy_repo(ctx), workspace(ctx)):
        candidate = os.path.abspath(os.path.join(base, path))
        if os.path.exists(candidate):
            return candidate

    return os.path.abspath(os.path.join(legacy_repo(ctx), path))


def ensure_allowed(ctx, path: str) -> str:
    resolved = resolve_path(ctx, path)
    if not is_within(resolved, allowed_roots(ctx)):
        raise PermissionError(f"caminho fora das raízes permitidas: {path}")
    return resolved


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def write_text(path: str, content: str) -> None:
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def write_json(path: str, data) -> None:
    import json

    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
