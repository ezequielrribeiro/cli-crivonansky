from core.command import Command

import subprocess

from rich.markup import escape


class DockerContainerRunCommand(Command):
    name = "docker-container-run"
    description = "Executa um comando dentro de um container Docker Linux"
    help_text = (
        "Uso: /docker-container-run --container <container> --command \"<comando>\"\n"
        "Exemplo: /docker-container-run --container php-5 --command \"php -v\""
    )

    def execute(self, args):
        parsed = self.parse_args(args)

        container = parsed.get("container")
        command = parsed.get("command")

        if not container:
            print("[erro] Informe o container (--container <container>)")
            return False, {"error": "informe o container"}

        if not command:
            print("[erro] Informe o comando (--command \"<comando>\")")
            return False, {"error": "informe o comando"}

        state, error = self._check_container(container)

        if error:
            print(f"[erro] {error}")
            return False, {"error": error, "container": container}

        if state != "true":
            message = f"container '{container}' nao esta em execucao"
            print(f"[erro] {message}")
            return False, {"error": message, "container": container}

        try:
            result = subprocess.run(
                ["docker", "exec", container, "sh", "-c", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            print(f"[erro] Falha ao executar no container: {e}")
            return False, {"error": str(e), "container": container}

        output = self._combine_output(result)

        print(f"[cyan]$ docker exec {escape(container)} sh -c \"{escape(command)}\"[/cyan]")
        if output:
            print(escape(output))
        else:
            print(f"[yellow](sem saida) exit code {result.returncode}[/yellow]")

        return result.returncode == 0, {
            "container": container,
            "command": command,
            "returncode": result.returncode,
            "output": output,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _check_container(self, container: str):
        """Valida se o container existe e esta em execucao.

        Retorna (state, error): state e "true"/"false" (State.Running) ou None
        quando o container nao existe; error e uma mensagem quando a checagem
        falha (docker ausente ou container inexistente).
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            return None, "executavel 'docker' nao encontrado no PATH"
        except Exception as e:
            return None, f"falha ao consultar o container: {e}"

        if result.returncode != 0:
            return None, f"container '{container}' nao encontrado"

        return (result.stdout or "").strip().lower(), None

    @staticmethod
    def _combine_output(result) -> str:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stdout and stderr:
            return f"{stdout}\n{stderr}"
        return stdout or stderr
