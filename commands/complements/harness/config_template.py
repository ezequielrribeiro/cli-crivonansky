"""Geração do ``workspace/harness.yaml`` a partir do template do plugin."""

import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
TEMPLATE_NAME = "harness.example.yaml"
TOKEN = "{{PLUGIN_ROOT}}"


def workspace_dir(plugin_root=None, create: bool = True) -> Path:
    root = Path(plugin_root or PLUGIN_ROOT)
    workspace = root / "workspace"
    if create:
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def config_path(plugin_root=None) -> Path:
    return workspace_dir(plugin_root, create=False) / "harness.yaml"


def render(plugin_root=None) -> str:
    root = Path(plugin_root or PLUGIN_ROOT).resolve()
    template = (root / TEMPLATE_NAME).read_text(encoding="utf-8")
    return template.replace(TOKEN, root.as_posix())


def write_default_config(plugin_root=None, force: bool = False) -> Path:
    root = Path(plugin_root or PLUGIN_ROOT).resolve()
    target = config_path(root)
    if target.exists() and not force:
        return target

    workspace_dir(root)
    target.write_text(render(root), encoding="utf-8", newline="\n")
    return target


def resolve(plugin_root=None, path: str | None = None) -> str:
    """Resolve um caminho relativo ao plugin (útil para paths do template)."""
    root = Path(plugin_root or PLUGIN_ROOT).resolve()
    if not path:
        return str(root)
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return os.path.abspath(root / candidate)
