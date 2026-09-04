from core.command import Command
import subprocess
import time
import json
import os
import shutil


class LoadAppCommand(Command):
    name = "load-app"
    description = "Inicia aplicativos e move para Virtual Desktop (Windows) com suporte a params brutos"
    help_text = (
        "Uso: /load-app --app <nome> [--desktop <num>] [--params \"...\"]\n"
        "     /load-app --workspace <nome>"
    )

    def __init__(self):
        super().__init__()
        self.workspaces = self._load_workspace_config()

    def execute(self, args):
        parsed_args = self.parse_args(args)
        workspace = parsed_args.get("workspace")

        if workspace:
            if isinstance(workspace, str):
                return self._run_workspace(workspace)
            else:
                print("Use --workspace <nome> para carregar um workspace")
                return False, {"error": "--workspace requer um nome"}

        app = parsed_args.get("app")
        desktop = parsed_args.get("desktop")
        params = parsed_args.get("params", "")

        if not app:
            print("Favor informar o app a ser iniciado, o caminho para o executável, ou use --workspace <nome>")
            return False, {"error": "app não informado"}

        ok = self._launch_and_move(app, desktop, params)
        return ok, {"app": app} if ok else {"app": app, "error": "falha ao iniciar"}

    def _launch_and_move(self, app_name, desktop=None, params_str=""):
        app_command = self.resolve_app_command(app_name)
        if not app_command:
            print(f"  [SKIP] '{app_name}' não localizado")
            return False

        try:
            self._spawn_app(app_command, params_str)

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
        if pid and self.move_window(exe_path, desktop_int, pid):
            return

        pid = self.get_window_pid_fallback(app_term, timeout=6)
        if pid and self.move_window(exe_path, desktop_int, pid):
            return

        self.move_active_window(exe_path, desktop_int)

    def _run_workspace(self, workspace_name):
        if workspace_name not in self.workspaces:
            print(f"Workspace '{workspace_name}' não encontrado")
            self._list_workspaces()
            return False, {"error": f"workspace '{workspace_name}' não encontrado"}

        apps = self.workspaces[workspace_name].get("apps", [])
        if not apps:
            print(f"Workspace '{workspace_name}' não possui aplicações")
            return False, {"error": f"workspace '{workspace_name}' sem aplicações"}

        print(f"Carregando workspace '{workspace_name}'...\n")
        launched = []
        failed = []
        for entry in apps:
            app_name = entry.get("app")
            if not app_name:
                print("  [SKIP] entrada sem 'app'")
                failed.append("<sem app>")
                continue

            desktop = entry.get("desktop")
            entry_params = entry.get("params", "")

            print(f"  Iniciando '{app_name}'...")
            if self._launch_and_move(app_name, desktop, entry_params):
                launched.append(app_name)
            else:
                failed.append(app_name)
            time.sleep(0.5)

        print(f"\nWorkspace '{workspace_name}' carregado")

        return (len(failed) == 0), {
            "workspace": workspace_name,
            "launched": launched,
            "failed": failed,
        }

    def _list_workspaces(self):
        if not self.workspaces:
            print("Nenhum workspace disponível (workspace_conf.json não encontrado ou vazio)")
            return

        print("Workspaces disponíveis:")
        for name in self.workspaces:
            apps = self.workspaces[name].get("apps", [])
            print(f"  - {name} ({len(apps)} aplicações)")

    def _project_root(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_workspace_config(self):
        config_path = os.path.join(self._project_root(), "workspace_conf.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("workspaces", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get_window_pid(self, app, timeout=5):
        start = time.time()
        term = app.lower().replace(".exe", "")
        while time.time() - start < timeout:
            try:
                result = subprocess.run(["powershell", "-Command", f"""
                        Get-Process |
                        Where-Object {{
                            $_.MainWindowHandle -ne 0 -and
                            $_.ProcessName -like '*{term}*'
                        }} |
                        Sort-Object StartTime -Descending |
                        Select-Object -First 1 -ExpandProperty Id
                        """], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                pid = result.stdout.strip()
                if pid.isdigit():
                    return pid
            except Exception:
                pass
            time.sleep(0.3)
        return None

    def get_window_pid_fallback(self, app, timeout=6):
        start = time.time()
        term = app.lower().replace(".exe", "")
        while time.time() - start < timeout:
            try:
                result = subprocess.run(["powershell", "-Command", f"""
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
                        """], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                pid = result.stdout.strip()
                if pid.isdigit():
                    return pid
            except Exception:
                pass
            time.sleep(0.4)
        return None

    def move_window(self, exe_path, desktop, pid):
        try:
            subprocess.Popen([exe_path, f"/gd:{desktop}", f"/mw:{pid}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def move_active_window(self, exe_path, desktop):
        time.sleep(2)
        for _ in range(4):
            try:
                subprocess.Popen([exe_path, f"/gd:{desktop}", "/ma"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"erro ao mover janela ativa: {e}")
            time.sleep(0.5)

    def get_virtual_desktop_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        exe_path = os.path.join(base_dir, "VirtualDesktop11.exe")
        if os.path.exists(exe_path):
            return exe_path
        return os.path.join("commands", "complements", "load_app_plugin", "VirtualDesktop11.exe")

    def resolve_app_command(self, app):
        if os.path.isfile(app):
            return os.path.abspath(app)

        resolved = shutil.which(app)
        if resolved:
            return resolved

        config_path = os.path.join(self._project_root(), "load_apps.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if app in data:
                    configured = data[app]
                    if isinstance(configured, str):
                        return configured
                    if isinstance(configured, list) and configured:
                        return configured
            except Exception:
                pass

        return None

    def _as_command_list(self, app_command):
        if isinstance(app_command, str):
            return [app_command]
        return list(app_command)

    def _needs_cmd_wrapper(self, app_command):
        command = self._as_command_list(app_command)
        if not command:
            return False
        ext = os.path.splitext(command[0])[1].lower()
        return ext in (".cmd", ".bat")

    def _decode_params_block(self, value):
        # Decodifica apenas: \\ -> \\ e \\\" -> \".
        if value is None:
            return ""

        text = str(value)
        result = []
        i = 0

        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                nxt = text[i + 1]
                if nxt == "\\":
                    result.append("\\")
                    i += 2
                    continue
                if nxt == '"':
                    result.append('"')
                    i += 2
                    continue
            result.append(ch)
            i += 1

        return "".join(result).strip()

    def _build_command_line(self, app_command, raw_params=""):
        base_parts = self._as_command_list(app_command)
        base_cmd = subprocess.list2cmdline(base_parts)

        raw_params = (raw_params or "").strip()
        if raw_params:
            return f"{base_cmd} {raw_params}"
        return base_cmd

    def _spawn_app(self, app_command, params_str=""):
        raw_params = ""
        if isinstance(params_str, str) and params_str.strip():
            raw_params = self._decode_params_block(params_str)

        if raw_params:
            full_command = self._build_command_line(app_command, raw_params)
            return subprocess.Popen(full_command, shell=True)

        command = self._as_command_list(app_command)
        if self._needs_cmd_wrapper(command):
            command = ["cmd", "/c", *command]

        return subprocess.Popen(command)

    def try_shell(self, cmd):
        try:
            result = subprocess.run(f'where "{cmd}"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
