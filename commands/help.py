from core.command import Command


class HelpCommand(Command):
    name = "help"
    description = "Lista comandos disponíveis"

    def execute(self, args):
        print("Comandos disponíveis:\n")

        for name, cmd in self.context.registry.all().items():
            print(f"{name} - {cmd.description}")
