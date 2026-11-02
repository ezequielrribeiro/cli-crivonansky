import json
import os
import subprocess

from core.command import Command

SAMPLE_CONFIG = {
    "environments": {
        "meu-projeto": "C:/caminho/para/o/docker-compose.yml",
    }
}


class EnvironmentCommand(Command):
    name = "environment"
    description = "Gerencia ambientes Docker via docker-compose"
    help_text = (
        "Uso: /environment list [--running]\n"
        "     /environment start <env> [env2 ...]\n"
        "     /environment stop <env> [env2 ...]\n"
        "     /environment init [--force]"
    )

    def __init__(self):
        self.environments = self._load_config()

    def _config_path(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root, "environment_conf.json")

    def _load_config(self):
        config_path = self._config_path()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("environments", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def execute(self, args):
        if not args:
            self._print_usage()
            return False, {"error": "uso incompleto"}

        action = args[0].lower()

        # 1. LIST
        if action == "list":
            show_running = "--running" in args
            data = self._list_environments(only_running=show_running)
            return True, {"environments": data}

        # 2. INIT
        if action == "init":
            return self._init_config(force="--force" in args)

        # 3. START / STOP
        if action not in ("start", "stop"):
            print(f"[red]Ação inválida: {action}[/red]")
            self._print_usage()
            return False, {"error": f"ação inválida: {action}"}

        if len(args) < 2:
            self._print_usage()
            return False, {"error": "uso incompleto"}

        envs = [arg.lower() for arg in args[1:] if not arg.startswith("--")]
        if not envs:
            self._print_usage()
            return False, {"error": "nenhum ambiente informado"}

        invalid_envs = [e for e in envs if e not in self.environments]

        if invalid_envs:
            print(f"[red]Ambientes inválidos: {', '.join(invalid_envs)}[/red]")
            self._print_available_envs()
            return False, {"invalid_envs": invalid_envs}

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

    def _init_config(self, force=False):
        path = self._config_path()

        if os.path.exists(path) and not force:
            print(f"[yellow]environment_conf.json já existe: {path}[/yellow]")
            print("Use [bold]/environment init --force[/bold] para sobrescrever.")
            return False, {"error": "environment_conf.json já existe", "path": path}

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(SAMPLE_CONFIG, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            print(f"[red]Falha ao criar {path}: {e}[/red]")
            return False, {"error": str(e), "path": path}

        self.environments = self._load_config()

        print(f"[green]environment_conf.json criado em {path}[/green]")
        print()
        print('Preencha "environments" com nome -> caminho absoluto do docker-compose.yml:')
        print()
        print(json.dumps(SAMPLE_CONFIG, indent=2, ensure_ascii=False))
        print()
        print("Use barras normais (C:/...) ou escape as invertidas (C:\\...).")
        print()
        print("Depois:")
        print("  /environment list")
        print("  /environment start meu-projeto")
        print("  /environment stop meu-projeto")

        return True, {"path": path, "created": True}

    # LIST COM CONTAINERS
    def _list_environments(self, only_running=False):
        data = {}
        print("Ambientes disponíveis:\n")

        if not self.environments:
            print("  (nenhum ambiente configurado)")
            print("  Crie um environment_conf.json com: /environment init")
            return data

        for name, path in self.environments.items():
            if not os.path.exists(path):
                print(f"  - {name}")
                print("    status: MISSING\n")
                data[name] = "MISSING"
                continue

            containers = self._get_containers(path)
            status = self._get_env_status_from_containers(containers)

            if only_running and status != "RUNNING":
                continue

            print(f"  - {name}")
            print(f"    status: {status}")
            data[name] = status

            print("    containers:")
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

        # Se pelo menos um container está rodando -> RUNNING
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
        print("  environment init [--force]")
        self._print_available_envs()

    def _print_available_envs(self):
        print("\nAmbientes disponíveis:")
        for name in self.environments:
            print(f"  - {name}")
