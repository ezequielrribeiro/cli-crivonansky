from core.command import Command
import os


class GeneratePluginCommand(Command):
    name = "generate-plugin"
    description = "Gera um novo plugin de comando"
    help_text = "Uso: /generate-plugin --name <nome>\nExemplo: /generate-plugin --name meu-comando"

    def execute(self, args):
        parsed = self.parse_args(args)

        plugin_name = parsed.get("name")

        if not plugin_name:
            print("[erro] Informe o nome do plugin (--name)")
            return False, {"error": "informe o nome do plugin"}

        if "_" in plugin_name or any(c.isspace() for c in plugin_name) or len(args) > 2:
            print("[erro] O nome do comando não pode conter sublinhados (_) ou espaços em branco.")
            return False, {"error": "nome do comando inválido"}

        file_name = f"{plugin_name.replace('-', '_').lower()}.py"
        class_name = self.to_class_name(plugin_name) + "Command"

        content = self.build_template(plugin_name, class_name)

        path = os.path.join("commands", file_name)

        if os.path.exists(path):
            print(f"[erro] Plugin já existe: {path}")
            return False, {"error": "plugin já existe", "path": path}

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Plugin criado com sucesso: {path}")
        return True, {"name": plugin_name, "path": path}

    def to_class_name(self, name: str):
        clean_name = name.replace("-", " ")
        return "".join(word.capitalize() for word in clean_name.split())

    def build_template(self, plugin_name: str, class_name: str):
        command_name = plugin_name.lower()

        return f'''from core.command import Command


class {class_name}(Command):
    name = "{command_name}"
    description = "Descreva o que este comando faz"
    help_text = "Uso: /{command_name} --<parametro> <valor>\\nExemplo: /{command_name} --exemplo valor"

    def execute(self, args):
        parsed = self.parse_args(args)
        print("Executando {command_name}")

        # Exemplo de args:
        print("Args:", parsed)

        # Exemplo usando contexto
        # registry = self.context.registry

        # Retorno padrão: (sucesso: bool, dados: dict | None)
        return True, {{"args": parsed}}
'''