import sys

from core.bootstrap import build_executor
from core.output import strip_markup


def _ensure_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def _run_non_interactive(argv: list[str]) -> int:
    """Executa um comando a partir dos argumentos e devolve o exit code.

    Aceita o comando com ou sem o prefixo "/". O texto de saída é impresso
    sem marcação Rich (REQ-N06) e o exit code reflete o resultado do comando.
    """
    if not argv:
        return 1

    executor = build_executor()
    output = executor.execute_args(argv)

    if output:
        print(strip_markup(output))

    success, _ = executor.last_result
    return 0 if success else 1


def main():
    _ensure_utf8()

    if len(sys.argv) > 1:
        sys.exit(_run_non_interactive(sys.argv[1:]))

    from tui_app import MyCLIApp

    executor = build_executor()
    app = MyCLIApp(executor)
    app.run()


if __name__ == "__main__":
    main()
