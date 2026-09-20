from core.registry import CommandRegistry
from core.context import CLIContext
from core.loader import load_commands
from core.executor import CommandExecutor


def build_executor() -> CommandExecutor:
    registry = CommandRegistry()
    executor = CommandExecutor(registry)
    context = CLIContext(registry, executor)

    load_commands(registry, context)

    return executor