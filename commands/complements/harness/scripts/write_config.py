"""Gera ``workspace/harness.yaml`` a partir de ``harness.example.yaml``.

Chamado pelo ``install.ps1`` depois de criar o venv do plugin, para que o
arquivo final fique com caminhos absolutos (independentes do diretório atual).
"""

import argparse
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from config_template import write_default_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="sobrescreve o config")
    args = parser.parse_args()

    target = write_default_config(PLUGIN_ROOT, force=args.force)
    print(f"config: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
