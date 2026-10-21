from core.command import Command

import os
import shlex
import subprocess

from rich.markup import escape


class RunGitCmdCommand(Command):
    name = "run-git-cmd"
    description = "Executa um comando git em um diretorio raiz informado"
    help_text = (
        "Uso: /run-git-cmd --root-dir \"<root-dir>\" --command \"<git-command>\"\n"
        "Exemplo: /run-git-cmd --root-dir \"C:\\projetos\\projeto-exemplo\" --command \"git diff --check\""
    )

    def execute(self, args):
        parsed = self.parse_args(args)

        root_dir = parsed.get("root-dir")
        command = parsed.get("command")

        if not root_dir:
            print("[erro] Informe o diretorio raiz (--root-dir \"<root-dir>\")")
            return False, {"error": "informe o diretorio raiz"}

        if not command:
            print("[erro] Informe o comando git (--command \"<git-command>\")")
            return False, {"error": "informe o comando git"}

        if not os.path.isdir(root_dir):
            print(f"[erro] Diretorio nao encontrado: {root_dir}")
            return False, {"error": f"diretorio nao encontrado: {root_dir}", "root_dir": root_dir}

        try:
            parts = self._split_command(command)
        except ValueError as e:
            print(f"[erro] Comando invalido: {e}")
            return False, {"error": f"comando invalido: {e}", "root_dir": root_dir}

        if not parts or parts[0].lower() != "git":
            print("[erro] O comando deve iniciar com 'git' (evita execucao arbitraria)")
            return False, {"error": "o comando deve iniciar com 'git'", "root_dir": root_dir}

        try:
            result = subprocess.run(
                parts,
                cwd=root_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            print("[erro] Executavel 'git' nao encontrado no PATH")
            return False, {"error": "executavel 'git' nao encontrado no PATH", "root_dir": root_dir}
        except Exception as e:
            print(f"[erro] Falha ao executar git: {e}")
            return False, {"error": str(e), "root_dir": root_dir}

        output = self._combine_output(result)

        print(f"[cyan]$ {escape(' '.join(parts))}[/cyan]")
        print(f"[cyan](em {root_dir})[/cyan]")
        if output:
            print(escape(output))
        else:
            print(f"[yellow](sem saida) exit code {result.returncode}[/yellow]")

        return result.returncode == 0, {
            "root_dir": root_dir,
            "command": " ".join(parts),
            "returncode": result.returncode,
            "output": output,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _split_command(self, command: str) -> list:
        """Divide a linha de comando sem interpretar o shell do sistema."""
        lexer = shlex.shlex(command, posix=False)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return [self._strip_quotes(part) for part in lexer]

    @staticmethod
    def _strip_quotes(token: str) -> str:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
            return token[1:-1]
        return token

    @staticmethod
    def _combine_output(result) -> str:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stdout and stderr:
            return f"{stdout}\n{stderr}"
        return stdout or stderr
