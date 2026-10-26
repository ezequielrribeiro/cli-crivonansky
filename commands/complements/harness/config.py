"""Carregamento e acesso ao harness.yaml."""

import os

import yaml

DEFAULT_CONFIG_PATH = os.environ.get(
    "HARNESS_CONFIG",
    os.path.join(os.getcwd(), "harness.yaml"),
)

FALLBACK_CONFIG_PATHS = [
    "C:/projetos/harness-workspace/harness.yaml",
]


class ConfigError(Exception):
    pass


def _candidates(path: str | None) -> list[str]:
    if path:
        return [path]
    candidates = [DEFAULT_CONFIG_PATH]
    candidates.extend(FALLBACK_CONFIG_PATHS)
    return [c for c in candidates if c]


def load_config(path: str | None = None) -> dict:
    for candidate in _candidates(path):
        if candidate and os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ConfigError(f"configuração inválida em {candidate}")
            data["_path"] = os.path.abspath(candidate)
            return data

    raise ConfigError(
        "harness.yaml não encontrado. Informe --config, defina HARNESS_CONFIG "
        "ou execute a partir do diretório que contém o arquivo."
    )


def get_workspace(config: dict) -> str:
    workspace = config.get("workspace")
    if not workspace:
        raise ConfigError("campo 'workspace' ausente no harness.yaml")
    workspace = os.path.abspath(workspace)
    os.makedirs(workspace, exist_ok=True)
    return workspace


def get_output(config: dict) -> dict:
    return config.get("output") or {}


def get_tool(config: dict, *keys: str) -> str | None:
    node = config.get("tools") or {}
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return None
    return node


def get_legacy(config: dict, key: str, default=None):
    return (config.get("legacy") or {}).get(key, default)
