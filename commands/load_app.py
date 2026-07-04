from core.command import Command
import subprocess
import time
import json
import os
import shlex


class LoadAppCommand(Command):
    name = "load-app"
    description = "Inicia aplicativos e move para Virtual Desktop (Windows) com fallback híbrido"

    def __init__(self):
        super().__init__()
        self.workspaces = self._load_workspace_config()

    def execute(self, args):
        parsed_args = self.parse_args(args)

        workspace = parsed_args.get("workspace")

        if workspace:
            if isinstance(workspace, str):
                self._run_workspace(workspace)
            else:
                print("Use --workspace <nome> para carregar um workspace")
            return

        app = parsed_args.get("app")
        desktop = parsed_args.get("desktop")
        params = parsed_args.get("params", "")

        if not app:
            print("Favor informar o app a ser iniciado, o caminho para o executável, ou use --workspace <nome>")
            return

        self._launch_and_move(app, desktop, params)

    # =========================
    # 🔹 Helpers (workspace + launch)
    # =========================
    def _launch_and_move(self, app_name, desktop=None, params_str=""):
        app_command = self.resolve_app_command(app_name)

        if not app_command:
            print(f"  [SKIP] '{app_name}' não localizado")
            return False

        if isinstance(params_str, str) and params_str.strip():
            try:
                params = shlex.split(params_str)
            except ValueError as e:
                print(f"  [ERRO] Parâmetros mal formatados para '{app_name}': {e}")
                return False

            if params:
                if isinstance(app_command, str):
                    app_command = [app_command] + params
                else:
                    app_command = list(app_command) + params

        try:
            subprocess.Popen(app_command)

            if desktop is not None and desktop != "":
                try:
                    desktop_int = int(desktop)
                except ValueError:
                    print(f"  desktop inválido para '{app_name}', ignorando")
                    return True

                self._move_to_desktop(app_name, desktop_int)

            return True
        except Exception as e:
            print(f"  [ERRO] '{app_name}': {e}")
            return False

    def _move_to_desktop(self, app_term, desktop_int):
        exe_path = self.get_virtual_desktop_path()

        pid = self.get_window_pid(app_term, timeout=5)
        if pid:
            if self.move_window(exe_path, desktop_int, pid):
                return

        pid = self.get_window_pid_fallback(app_term, timeout=6)
        if pid:
            if self.move_window(exe_path, desktop_int, pid):
                return

        self.move_active_window(exe_path, desktop_int)

    def _run_workspace(self, workspace_name):
        if workspace_name not in self.workspaces:
            print(f"Workspace '{workspace_name}' não encontrado")
            self._list_workspaces()
            return

        apps = self.workspaces[workspace_name].get("apps", [])

        if not apps:
            print(f"Workspace '{workspace_name}' não possui aplicações")
            return

        print(f"Carregando workspace '{workspace_name}'...\n")

        for entry in apps:
            app_name = entry.get("app")
            if not app_name:
                print("  [SKIP] entrada sem 'app'")
                continue

            desktop = entry.get("desktop")
            entry_params = entry.get("params", "")

            print(f"  Iniciando '{app_name}'...")
            self._launch_and_move(app_name, desktop, entry_params)
            time.sleep(0.5)

        print(f"\nWorkspace '{workspace_name}' carregado")

    def _list_workspaces(self):
        if not self.workspaces:
            print("Nenhum workspace disponível (workspace_conf.json não encontrado ou vazio)")
            return

        print("Workspaces disponíveis:")
        for name in self.workspaces:
            apps = self.workspaces[name].get("apps", [])
            print(f"  - {name} ({len(apps)} aplicações)")

    def _load_workspace_config(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "workspace_conf.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("workspaces", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    # =========================
    # 🔹 Estratégia 1
    # =========================
    def get_window_pid(self, app, timeout=5):
        start = time.time()
        term = app.lower().replace(".exe", "")

        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"""
                        Get-Process |
                        Where-Object {{
                            $_.MainWindowHandle -ne 0 -and
                            $_.ProcessName -like '*{term}*'
                        }} |
                        Sort-Object StartTime -Descending |
                        Select-Object -First 1 -ExpandProperty Id
                        """
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                pid = result.stdout.strip()

                if pid.isdigit():
                    return pid

            except Exception:
                pass

            time.sleep(0.3)

        return None

    # =========================
    # 🔹 Estratégia 2 (fallback)
    # =========================
    def get_window_pid_fallback(self, app, timeout=6):
        start = time.time()
        term = app.lower().replace(".exe", "")

        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"""
                        Get-Process |
                        Where-Object {{
                            $_.MainWindowHandle -ne 0 -and
                            (
                                $_.ProcessName -like '*{term}*' -or
                                $_.MainWindowTitle -like '*{term}*'
                            )
                        }} |
                        Sort-Object StartTime -Descending |
                        Select-Object -First 1 -ExpandProperty Id
                        """
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                pid = result.stdout.strip()

                if pid.isdigit():
                    return pid

            except Exception:
                pass

            time.sleep(0.4)

        return None

    # =========================
    # 🔹 Move específico (PID)
    # =========================
    def move_window(self, exe_path, desktop, pid):
        try:
            subprocess.Popen(
                [
                    exe_path,
                    f"/gd:{desktop}",
                    f"/mw:{pid}"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    # =========================
    # 🔹 Estratégia final (Active Window)
    # =========================
    def move_active_window(self, exe_path, desktop):
        time.sleep(2)

        for _ in range(4):
            try:
                subprocess.Popen(
                    [
                        exe_path,
                        f"/gd:{desktop}",
                        "/ma"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"erro ao mover janela ativa: {e}")

            time.sleep(0.5)

    # =========================
    # 🔹 Util
    # =========================
    def get_virtual_desktop_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        exe_path = os.path.join(base_dir, "VirtualDesktop11.exe")

        if os.path.exists(exe_path):
            return exe_path

        return "commands\\complements\\load_app_plugin\\VirtualDesktop11.exe"

    def resolve_app_command(self, app):
        if os.path.isfile(app):
            return app

        if self.try_shell(app):
            return app

        config_path = "load_apps.json"

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if app in data:
                        return data[app]
            except Exception:
                pass

        return None

    def try_shell(self, cmd):
        try:
            result = subprocess.run(
                f'where "{cmd}"',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.returncode == 0
        except Exception:
            return False

    def parse_args(self, args):
        result = {}
        positional = []
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
                positional.append(args[i])
                i += 1

        if "app" not in result and positional:
            result["app"] = positional[0]

        return result