from core.registry import CommandRegistry
from core.context import CLIContext
from core.loader import load_commands
from core.executor import CommandExecutor

from tui_app import MyCLIApp


def main():
    registry = CommandRegistry()
    context = CLIContext(registry)

    load_commands(registry, context)

    executor = CommandExecutor(registry)

    app = MyCLIApp(executor)
    app.run()


if __name__ == "__main__":
    main()
