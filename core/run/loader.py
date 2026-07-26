import os
import importlib.util
import sys
from pathlib import Path

from core.run.api import set_executor, clear_registry


def load_runfile(executor, path: str = "runfile.py") -> bool:
    runfile_path = Path.cwd() / path

    if not runfile_path.exists():
        return False

    set_executor(executor)
    clear_registry()

    spec = importlib.util.spec_from_file_location("runfile_module", str(runfile_path))
    if spec is None or spec.loader is None:
        print(f"[red]Nao foi possivel carregar {path}[/red]")
        return False

    module = importlib.util.module_from_spec(spec)
    sys.modules["runfile_module"] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"[red]Erro ao executar {path}: {e}[/red]")
        return False

    return True
