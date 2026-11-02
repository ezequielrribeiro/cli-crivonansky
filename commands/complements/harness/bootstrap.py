"""Bootstrap das dependências Python do plugin harness.

O instalador cria um venv próprio em ``commands/complements/harness/.venv``
(ou instala em ``vendor/python``). Como o plugin é importado pelo interpretador
do crivonansky, este módulo adiciona o site-packages do plugin ao ``sys.path``
quando alguma dependência ainda não está disponível no interpretador atual.

A checagem é feita por importabilidade: se o venv do crivonansky já tem
``yaml``/``sqlglot``/``pyperclip``, nada é alterado.
"""

import importlib.util
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REQUIRED = ("yaml", "sqlglot", "pyperclip")


def site_packages(venv_root: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_root, "Lib", "site-packages")
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return os.path.join(venv_root, "lib", version, "site-packages")


def candidates() -> list[str]:
    return [
        site_packages(os.path.join(PLUGIN_ROOT, ".venv")),
        os.path.join(PLUGIN_ROOT, "vendor", "python"),
    ]


def _available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def missing(required=DEFAULT_REQUIRED) -> list[str]:
    return [name for name in required if not _available(name)]


def ensure_deps(required=DEFAULT_REQUIRED) -> bool:
    """Torna as dependências do plugin importáveis.

    Devolve ``True`` quando todas estão disponíveis ao final (mesmo que já
    estivessem no interpretador atual) e ``False`` quando o install ainda não
    foi executado.
    """
    if not missing(required):
        return True

    for candidate in candidates():
        if not os.path.isdir(candidate) or candidate in sys.path:
            continue
        sys.path.insert(0, candidate)
        if not missing(required):
            return True

    return not missing(required)
