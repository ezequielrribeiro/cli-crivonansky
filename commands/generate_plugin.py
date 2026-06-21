from core.command import Command
import os


class GeneratePluginCommand(Command):
    name = "generate-plugin"
    description = "Gera um novo plugin de comando"

    def execute(self, args):
        parsed = self.parse_args(args)

        plugin_name = parsed.get("name")

        if not plugin_name:
            print("[erro] Informe o nome do plugin (--name)")
            return

        if "_" in plugin_name or any(c.isspace() for c in plugin_name) or len(args) > 2:
            print("[erro] O nome do comando não pode conter sublinhados (_) ou espaços em branco.")
            return

        file_name = f"{plugin_name.replace('-', '_').lower()}.py"
        class_name = self.to_class_name(plugin_name) + "Command"

        content = self.build_template(plugin_name, class_name)

        path = os.path.join("commands", file_name)

        if os.path.exists(path):
            print(f"[erro] Plugin já existe: {path}")
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Plugin criado com sucesso: {path}")

    # -------------------------
    # Helpers
    # -------------------------

    def parse_args(self, args):
        result = {}
        i = 0

        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]

                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    result[key] = args[i + 1]
                    i += 2
                else:
                    result[key] = True
                    i += 1
            else:
                i += 1

        return result

    def to_class_name(self, name: str):
        clean_name = name.replace("-", " ")
        return "".join(word.capitalize() for word in clean_name.split())

    def build_template(self, plugin_name: str, class_name: str):
        command_name = plugin_name.lower()

        return f'''from core.command import Command


class {class_name}(Command):
    name = "{command_name}"
    description = "Descreva o que este comando faz"

    def execute(self, args):
        print("Executando {command_name}")

        # Exemplo de args:
        print("Args:", args)

        # Exemplo usando contexto
        # registry = self.context.registry
'''