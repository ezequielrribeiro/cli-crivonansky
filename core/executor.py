from core.parser import CommandParser
import io
import contextlib


class CommandExecutor:
    def __init__(self, registry):
        self.registry = registry

    def execute(self, input_line: str):
        name, args = CommandParser.parse(input_line)

        if not name:
            return ""

        command = self.registry.get(name)

        if not command:
            return "[red]Comando não encontrado[/red]"

        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            command.execute(args)

        return buffer.getvalue().strip()
