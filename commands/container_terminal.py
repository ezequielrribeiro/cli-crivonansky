import subprocess
import shlex
from core.command import Command


class ContainerTerminalCommand(Command):
    name = "container-terminal"
    description = "Abre um novo terminal PowerShell conectado a um container Docker"
    help_text = "Uso: /container-terminal <nome_do_container>"

    def execute(self, args):

        if not args:
            print("Erro: informe o nome do container")
            print("Uso: container-terminal <container_name>")
            return

        container_name = args[0]

        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Container '{container_name}' não encontrado")
            return

        print(f"Abrindo terminal para o container: {container_name}")

        docker_cmd = f"Set-ExecutionPolicy Bypass -Scope Process; docker exec -it {container_name} bash"

        self._run_in_powershell(docker_cmd)

    def _run_in_powershell(self, command: str):
        ps_command = f'start powershell -NoExit -Command "{command}"'

        try:
            subprocess.Popen(ps_command, shell=True)
        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")