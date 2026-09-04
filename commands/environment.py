import subprocess
import os
import json
from core.command import Command


class EnvironmentCommand(Command):
    name = "environment"
    description = "Gerencia ambientes Docker via docker-compose"
    help_text = (
        "Uso: /environment list [--running]\n"
        "     /environment start <env> [env2 ...]\n"
        "     /environment stop <env> [env2 ...]"
    )

    def __init__(self):
        self.environments = self._load_config()

    def _load_config(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "environment_conf.json"
        )
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            return config.get("environments", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def execute(self, args):
        if not args:
            self._print_usage()
            return False, {"error": "uso incompleto"}

        action = args[0].lower()

        # ✅ LIST
        if action == "list":
            show_running = "--running" in args
            data = self._list_environments(only_running=show_running)
            return True, {"environments": data}

        # ✅ START / STOP
        if len(args) < 2:
            self._print_usage()
            return False, {"error": "uso incompleto"}

        envs = [arg.lower() for arg in args[1:] if not arg.startswith("--")]

        invalid_envs = [e for e in envs if e not in self.environments]

        if invalid_envs:
            print(f"Ambientes inválidos: {', '.join(invalid_envs)}")
            self._print_available_envs()
            return False, {"invalid_envs": invalid_envs}

        if action not in ["start", "stop"]:
            print(f"Ação inválida: {action}")
            self._print_usage()
            return False, {"error": f"ação inválida: {action}"}

        ok = []
        failed = []
        for env in envs:
            compose_file = self.environments[env]

            if not os.path.exists(compose_file):
                print(f"[ERRO] Arquivo não encontrado: {compose_file}")
                failed.append(env)
                continue

            if action == "start":
                command = f'docker compose -f "{compose_file}" up --build -d'
            else:
                command = f'docker compose -f "{compose_file}" down -v'

            if self._run_in_powershell(command):
                verb = "iniciado" if action == "start" else "encerrado"
                print(f"[OK] Ambiente '{env}' {verb}")
                ok.append(env)
            else:
                failed.append(env)

        return (len(failed) == 0), {"ok": ok, "failed": failed}

    # ✅ LIST COM CONTAINERS
    def _list_environments(self, only_running=False):
        data = {}
        print("Ambientes disponíveis:\n")

        for name, path in self.environments.items():
            if not os.path.exists(path):
                print(f"  - {name}")
                print(f"    status: MISSING\n")
                data[name] = "MISSING"
                continue

            containers = self._get_containers(path)
            status = self._get_env_status_from_containers(containers)

            if only_running and status != "RUNNING":
                continue

            print(f"  - {name}")
            print(f"    status: {status}")
            data[name] = status

            print(f"    containers:")
            if not containers:
                print("      (nenhum)")
            else:
                for c in containers:
                    print(f"      - {c['name']} ({c['state']})")

            print()

        return data

    def _get_containers(self, compose_file):
        try:
            result = subprocess.run(
                f'docker compose -f "{compose_file}" ps --format json',
                shell=True,
                capture_output=True,
                text=True
            )

            output = result.stdout.strip()

            if not output:
                return []

            containers = []

            for line in output.splitlines():
                data = json.loads(line)

                containers.append({
                    "name": data.get("Name"),
                    "state": data.get("State").lower()
                })

            return containers

        except Exception:
            return []

    def _get_env_status_from_containers(self, containers):
        if not containers:
            return "STOPPED"

        # Se pelo menos um container está rodando → RUNNING
        for c in containers:
            if c["state"] == "running":
                return "RUNNING"

        return "STOPPED"

    def _run_in_powershell(self, command: str):
        ps_command = f'start powershell -NoExit -Command "{command}"'

        try:
            subprocess.Popen(ps_command, shell=True)
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")
            return False

    def _print_usage(self):
        print("Uso:")
        print("  environment list")
        print("  environment list --running")
        print("  environment start <env> [env2 ...]")
        print("  environment stop <env> [env2 ...]")
        self._print_available_envs()

    def _print_available_envs(self):
        print("\nAmbientes disponíveis:")
        for name in self.environments:
            print(f"  - {name}")