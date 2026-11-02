"""Carregamento e acesso ao harness.yaml."""

import os

import yaml

# Raiz do plugin (commands/complements/harness).
PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))

# Configuração gerada pelo instalador dentro do próprio plugin.
DEFAULT_WORKSPACE = os.path.join(PLUGIN_ROOT, "workspace")

class ConfigError(Exception):
    pass


def default_config_path() -> str:
    return os.environ.get(
        "HARNESS_CONFIG",
        os.path.join(DEFAULT_WORKSPACE, "harness.yaml"),
    )


def _candidates(path: str | None) -> list[str]:
    if path:
        return [path]
    return [default_config_path()]


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
        "harness.yaml não encontrado. Rode '/harness install', informe --config "
        "ou defina HARNESS_CONFIG."
    )


def _base_dir(config: dict) -> str:
    return os.path.dirname(os.path.abspath(config.get("_path") or default_config_path()))


def resolve_path(config: dict, value: str | None) -> str | None:
    """Resolve caminhos relativos ao diretório do harness.yaml."""
    if not value:
        return value
    if os.path.isabs(value):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(_base_dir(config), value))


def get_workspace(config: dict) -> str:
    workspace = config.get("workspace")
    if not workspace:
        raise ConfigError("campo 'workspace' ausente no harness.yaml")
    workspace = resolve_path(config, workspace)
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


def get_tool_path(config: dict, *keys: str) -> str | None:
    """Como get_tool, mas resolve caminhos relativos ao harness.yaml."""
    value = get_tool(config, *keys)
    if not value:
        return value
    if os.path.isabs(value) or "/" in value or "\\" in value or value.lower().endswith(".exe"):
        return resolve_path(config, value)
    return value


def get_legacy(config: dict, key: str, default=None):
    return (config.get("legacy") or {}).get(key, default)


def get_legacy_path(config: dict, key: str, default=None):
    return resolve_path(config, get_legacy(config, key, default))
