from core.parser import CommandParser
import io
import contextlib


class CommandExecutor:
    def __init__(self, registry):
        self.registry = registry
        self.last_result = (True, None)

    def execute(self, input_line: str):
        name, args = CommandParser.parse(input_line)

        if not name:
            self.last_result = (False, {"error": "comando vazio"})
            return ""

        command = self.registry.get(name)

        if not command:
            self.last_result = (False, {"error": "comando não encontrado"})
            return "[red]Comando não encontrado[/red]"

        if any(arg in ("--help", "-h") for arg in args):
            self.last_result = (True, {"help": True})
            return command.get_usage()

        buffer = io.StringIO()

        try:
            with contextlib.redirect_stdout(buffer):
                result = command.execute(args)
        except Exception as e:
            self.last_result = (False, {"error": str(e)})
            printed = buffer.getvalue().strip()
            if printed:
                return printed + f"\n[red]Erro: {e}[/red]"
            return f"[red]Erro ao executar comando: {e}[/red]"

        if result is None:
            result = (True, None)

        self.last_result = result

        return buffer.getvalue().strip()
