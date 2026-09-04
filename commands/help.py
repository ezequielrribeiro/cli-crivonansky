from core.command import Command


class HelpCommand(Command):
    name = "help"
    description = "Lista comandos disponíveis"
    help_text = "Uso: /help\nLista todos os comandos registrados com nome e descrição.\nUse /<comando> --help para ajuda específica."

    def execute(self, args):
        print("Comandos disponíveis:\n")

        commands = self.context.registry.all()
        for name, cmd in commands.items():
            print(f"{name} - {cmd.description}")

        return True, {"count": len(commands)}
